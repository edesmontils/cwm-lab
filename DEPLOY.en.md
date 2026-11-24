# Deploying CWM Lab (P6)

*Français : [DEPLOY.md](DEPLOY.md)*

CWM Lab is **stateless** (no sessions, no server state) and runs with
zero dependencies: any instance serves any request, and horizontal
scaling is just launching more instances. Three deployment levels,
simplest to most complete.

**What P6 provides** (regardless of level):

- **reasoning runs in a killable subprocess** — a cyclic rule
  submitted in bad faith (non-converging recursion) is killed at
  timeout: nothing keeps running in the background, neither CPU nor
  memory (before P6, an abandoned thread kept `think()`-ing until
  convergence or OOM — the shared-server DoS vector);
- a **concurrency ceiling**: at most
  `max_reason_concurrent` concurrent reasonings (default 8,
  `config.yaml`); beyond it, the request immediately gets
  **503 “server busy”** instead of queueing;
- a **WSGI application** (`cwm_lab.server:app`): the same JSON API
  as the standard server, ready for gunicorn.

## Level 1 — Lab room / LAN (zero dependencies)

The department machine (or the teacher's PC):

```sh
pip install cwm-lab
cwm-lab --host 0.0.0.0        # reachable on the local network
```

Students open `http://MACHINE-IP:8000` in their browser. ~30
students on typical lab KBs (5–500 statements, reasoning < 300 ms)
run a 2-hour session without extra resources: the ceiling of 8
concurrent reasonings + killable subprocesses guarantee no bad-faith
request blocks the others.

Tips:

- `config.yaml`: on a modest machine, lower
  `max_reason_concurrent` (e.g. 4) — reasonings are already near
  instant on lab KBs, so queueing one behind another is fine;
- do not expose port 8000 on the Internet (level 3) without
  authentication;
- logs: `cwm-lab` writes to stderr (redirect to a file if you want a
  session trace).

## Level 2 — Department server (gunicorn + systemd + Caddy)

For a permanent service (multiple sessions, several department
machines behind Caddy, which is already in place on the servers):

```sh
pip install cwm-lab
pip install -r requirements-deploy.txt    # gunicorn — deployment-only
                                          # dependency, never imported
                                          # by the app itself
```

### 1. The systemd service

`/etc/systemd/system/cwm-lab.service`:

```ini
[Unit]
Description=CWM Lab — ontology lab (CWM 2.0)
After=network.target

[Service]
User=cwmlab
WorkingDirectory=/opt/cwm-lab
ExecStart=/opt/cwm-lab/.venv/bin/gunicorn cwm_lab.server:app \
    --bind 127.0.0.1:8000 \
    --workers 2 --threads 4 \
    --timeout 120 \
    --access-logfile - --error-logfile -
# service bounds (risk #8 — memory, and protection of the machine)
LimitNOFILE=4096
MemoryMax=2G

[Install]
WantedBy=multi-user.target
```

```sh
systemctl daemon-reload
systemctl enable --now cwm-lab
journalctl -u cwm-lab -f      # follow the logs
```

Parameters:

- `--workers 2`: two processes, each with its own concurrency
  ceiling (the semaphore is per-process); 30 students with
  `--threads 4` and 2 workers is comfortable (reasoning itself is a
  subprocess: it never blocks the worker);
- `--timeout 120`: gunicorn drops a request beyond 2 min (the TP
  reasoning timeout is well below that — the UI default is 10 s);
- binding on `127.0.0.1`: only Caddy (below) exposes the service.

### 2. Caddy (reverse proxy — TLS + static files)

`Caddyfile` (the service listens on 127.0.0.1:8000; Caddy provides
TLS, HTTP→HTTPS, and can serve static files instead of the app to
keep the workers light):

```
tp-cwmlab.dept.example    # replace with the real host name
{
    # statics served by Caddy (fallback: the application)
    @static path /static/* /index.html
    redir @static /app{uri}
    handle /app* {
        uri strip_prefix /app
        reverse_proxy 127.0.0.1:8000
    }
    handle {
        # the app at the root (if not using the /app prefix)
        reverse_proxy 127.0.0.1:8000
    }
}
```

If the department machine already serves a Caddy site, add the TP's
host name as an extra block (Caddy provisions TLS automatically).

### 3. Recommended hardening (level 2)

- **per-IP rate limit** (Caddy: `rate_limit`, or an upstream reverse
  proxy) — bounds the request rate per student;
- **`ulimit` / `MemoryMax`** on the systemd service (above): a
  runaway reasoning is killed, not the machine;
- `config.yaml`: `max_reason_concurrent` matched to the machine
  (8 default; 4 with 2 workers on a modest machine);
- back up `~/.cache/lab_tp` (the disk cache is **useful but not
  essential**: losing it breaks nothing, it rebuilds).

## Level 3 — Internet

Beyond level 2:

- **authentication** (Caddy: `reverse_proxy` behind the
  institution's SSO, or an auth proxy) — the service is open but
  **unauthenticated**: do not expose it without;
- monitoring (uptime, cache size, 500 errors);
- sandbox: reasoning is already a subprocess killed at timeout (P6);
  for an external audience, add a cage (container) with a limited
  network.

## Parameter summary (config.yaml)

| Key | Default | Effect |
|---|---|---|
| `max_reason_concurrent` | 8 | Ceiling of concurrent reasonings **per process** — beyond: 503 “server busy” |
| `ttl_disk` / `ttl_memory` | 7 d / 5 min | Cache retention (useful but not essential) |
| `ia_max_requests` etc. | see `config.yaml.example` | Per-session AI quota |

## Deployment check

```sh
curl -s http://localhost:8000/api/version     # {"version": "…"}
curl -s -X POST http://localhost:8000/api/parse \
     -H 'Content-Type: application/json' \
     -d '{"text":"<http://example.org/a> a <http://example.org/B> ."}'
```

P6 acceptance criterion: 30 simultaneous students in a lab room, no
blocking from bad-faith cyclic rules, zero residual state between
two students.
