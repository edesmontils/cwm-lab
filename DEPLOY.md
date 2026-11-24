# Déploiement de CWM Lab (P6)

*English: [DEPLOY.en.md](DEPLOY.en.md)*

CWM Lab est **stateless** (aucune session, aucun état serveur) et
tourne en zéro dépendance : n'importe quelle instance traite
n'importe quelle requête, et le scaling horizontal se limite à lancer
davantage d'instances. Trois niveaux de déploiement, du plus simple
au plus complet.

**Ce que P6 apporte** (indépendant du niveau) :

- le **raisonnement tourne dans un subprocess tuable** — une règle
  cyclique soumise de mauvaise foi (récursion sans convergence) est
  tuée au timeout : plus rien ne tourne en fond, ni CPU ni mémoire
  (avant P6, un thread abandonné continuait `think()` jusqu'à
  convergence ou OOM — le vecteur de DoS du serveur partagé) ;
- un **plafond de concurrence** : au plus
  `max_reason_concurrent` raisonnements simultanés (défaut 8,
  `config.yaml`) ; au-delà, la requête reçoit immédiatement
  **503 « serveur occupé »** au lieu de s'attarder en file ;
- une **application WSGI** (`cwm_lab.server:app`) : la même API JSON
  que le serveur standard, prête pour gunicorn.

## Niveau 1 — Salle de TP / LAN (zéro dépendance)

La machine du département (ou le PC de l'enseignant) :

```sh
pip install cwm-lab
cwm-lab --host 0.0.0.0        # accessible sur le réseau local
```

Les étudiants ouvrent `http://IP-de-la-machine:8000` dans leur
navigateur. ~30 étudiants sur des KB de TP (5–500 énoncés,
raisonnement < 300 ms) tiennent une séance de 2 h sans renfort :
le plafond de 8 raisonnements simultanés + les subprocess tuables
garantissent qu'aucune requête de mauvaise foi ne bloque les autres.

Conseils :

- `config.yaml` : si la machine est modeste, baisser
  `max_reason_concurrent` (ex. 4) — les raisonnements sériés les uns
  derrière les autres sont déjà quasi instantanés sur des KB de TP ;
- ne pas exposer le port 8000 sur Internet (niveau 3) sans
  authentification ;
- logs : `cwm-lab` écrit sur stderr (le rediriger vers un fichier si
  on veut garder une trace de la séance).

## Niveau 2 — Serveur de département (gunicorn + systemd + Caddy)

Pour un service permanent (plusieurs séances, plusieurs machines de
département derrière Caddy, qui est déjà en place sur les serveurs) :

```sh
pip install cwm-lab
pip install -r requirements-deploy.txt    # gunicorn — dépendance de
                                          # déploiement uniquement,
                                          # jamais importée par le TP
```

### 1. Le service systemd

`/etc/systemd/system/cwm-lab.service` :

```ini
[Unit]
Description=CWM Lab — TP ontologies (CWM 2.0)
After=network.target

[Service]
User=cwmlab
WorkingDirectory=/opt/cwm-lab
ExecStart=/opt/cwm-lab/.venv/bin/gunicorn cwm_lab.server:app \
    --bind 127.0.0.1:8000 \
    --workers 2 --threads 4 \
    --timeout 120 \
    --access-logfile - --error-logfile -
# bornes du service (risque #8 — mémoire, et protection de la machine)
LimitNOFILE=4096
MemoryMax=2G

[Install]
WantedBy=multi-user.target
```

```sh
systemctl daemon-reload
systemctl enable --now cwm-lab
journalctl -u cwm-lab -f      # suivez les logs
```

Paramètres :

- `--workers 2` : deux processus, chacun avec son propre plafond de
  concurrence (le semaphore est par processus) ; 30 étudiants avec
  `--threads 4` et 2 workers tiennent largement (le raisonnement,
  lui, est en subprocess : il ne bloque pas le worker) ;
- `--timeout 120` : gunicorn abandonne une requête qui dépasse 2
  min (le timeout de raisonnement du TP est bien en dessous —
  le défaut de l'interface est 10 s) ;
- le binding sur `127.0.0.1` : seul Caddy (ci-dessous) expose le
  service.

### 2. Caddy (reverse proxy — TLS + statiques)

`Caddyfile` (le service écoute en 127.0.0.1:8000 ; Caddy sert le
TLS, le HTTP→HTTPS, et peut servir les fichiers statiques à la place
de l'app pour alléger les workers) :

```
tp-cwmlab.dept.example    # remplacer par le nom réel
{
    # statiques servis par Caddy (fallback : l'application)
    @static path /static/* /index.html
    redir @static /app{uri}
    handle /app* {
        uri strip_prefix /app
        reverse_proxy 127.0.0.1:8000
    }
    handle {
        # l'app en racine (si on n'utilise pas le préfixe /app)
        reverse_proxy 127.0.0.1:8000
    }
}
```

Si la machine de département sert déjà un site Caddy, ajouter le
bloc au nom de domaine du TP (Caddy charge le TLS automatiquement).

### 3. Renforts recommandés (niveau 2)

- **rate-limit par IP** (Caddy : `rate_limit` dans `@limiter` ou un
  reverse proxy en amont) — borne le nombre de requêtes par
  étudiant ;
- **`ulimit` / `MemoryMax`** du service systemd (ci-dessus) : un
  raisonnement fuit, il est tué, pas la machine ;
- `config.yaml` : `max_reason_concurrent` adapté à la machine
  (8 par défaut ; 4 si 2 workers sur une machine modeste) ;
- sauvegarder `~/.cache/lab_tp` (le cache disque est **utile mais
  non essentiel** : le perdre ne casse rien, il se reconstruit).

## Niveau 3 — Internet

Au-delà du niveau 2 :

- **authentification** (Caddy : `reverse_proxy` derrière un provider
  SSO de l'institution, ou un proxy d'authentification) — le service
  est ouvert mais **non authentifié** : ne pas l'exposer sans ;
- monitoring (uptime, taille du cache, erreurs 500) ;
- sandbox : le raisonnement est déjà en subprocess tué au timeout
  (P6) ; pour un public extérieur, ajouter une cage (conteneur)
  avec réseau limité.

## Récapitulatif des paramètres (config.yaml)

| Clé | Défaut | Effet |
|---|---|---|
| `max_reason_concurrent` | 8 | Plafond de raisonnements simultanés **par processus** — au-delà : 503 « serveur occupé » |
| `ttl_disk` / `ttl_memory` | 7 j / 5 min | Rétention du cache (le cache est utile mais non essentiel) |
| `ia_max_requests` etc. | voir `config.yaml.example` | Quota de séance de l'IA |

## Vérification du déploiement

```sh
curl -s http://localhost:8000/api/version     # {"version": "…"}
curl -s -X POST http://localhost:8000/api/parse \
     -H 'Content-Type: application/json' \
     -d '{"text":"<http://example.org/a> a <http://example.org/B> ."}'
```

Critère d'acceptation P6 : 30 étudiants simultanés en salle de TP,
aucun blocage dû à des règles cycliques soumises de mauvaise foi,
zéro état résiduel entre deux étudiants.
