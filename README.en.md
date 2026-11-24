# CWM Lab — semantic web lab tool (CWM 2.0)

*English version — the French original is [`README.md`](README.md).*

> A **local web application** for a semantic web lab (Master MIAGE)
> covering **consistency**, **validity** and **rules** — everything
> [CWM 2.0](https://gitlab.univ-nantes.fr/desmontils-e/cwm) can do:
> N3/Turtle parsing, reasoning (forward chaining), querying (SPARQL),
> inconsistency detection, entailment testing, and proof generation
> and checking.
>
> Standalone project: **CWM 2.0 is the only dependency** (published
> on PyPI as [`cwm`](https://pypi.org/project/cwm/), source:
> [public GitLab repository](https://gitlab.univ-nantes.fr/desmontils-e/cwm)).

## Credits

- **Author**: Emmanuel Desmontils
- **Institution**: Nantes University
- **Copyright**: © 2026 Emmanuel Desmontils — Nantes University
- **Date**: 2026-11-23 (standalone project; P0–P9 delivered + P7
  usability revamp)
- **Version**: `cwm_lab.__version__` (shown in the app footer,
  served by `GET /api/version`)
- **License**: Apache-2.0 (code, see `LICENSE`); the CWM 2.0 engine
  (dependency) is W3C Software licensed (original code) / Apache-2.0
  (fork modifications); CodeMirror 6 and vis.js vendored locally
  (MIT, see `cwm_lab/static/vendor/`).

## Status

**P0 delivered** (2026-11-21): N3/Turtle parsing with line/column
errors and stats, stdlib server, minimal page, tests (`make test`).

**P1 delivered** (2026-11-22): CodeMirror 6 editor (local bundle,
Turtle highlighting + N3 overlay), auto-parse on typing with errors
highlighted in the gutter, configurable base URI, N3 / Turtle /
NTriples / RDF/XML export (Turtle/NTriples refused if the graph is
not pure RDF, like `cwm --turtle`).

**P2 delivered** (2026-11-22): second editor for **N3 rules**
(`{ … } log:implies { … } .`, variables declared with `@forAll`),
**Reason** button → closure (`think` = convergence, `applyRules`
= 1 pass, stored rules or not), **list of new facts**,
**inconsistency** signal (`log:false` present, shown in red) and a
proper **timeout** on non-convergent rules — nothing ever blocks the
lab.

**P3 delivered** (2026-11-22): third editor for the **SPARQL query**
(`PREFIX : <…>` + `SELECT` / `ASK`), “**reason before query**”
checkbox: the same query runs on the raw KB *and* on the closure,
and the **new rows of the before/after diff are highlighted** — the
key pedagogical point of the lab. The preloaded example
(grandparent) returns 0 raw rows and 1 row after reasoning. ASK is
shown as a banner (true/false, before/after). `POST /api/query`,
`engine.query`.

**P4 delivered** (2026-11-22): **Conclusion / Proof** editor
(tabs, right column). **“Entails?”**: does the closure (data +
rules) contain the conclusion? → yes/no (`testIncludes`, *ex falso*
warning if the closure is inconsistent). **“Why?”**: generates the
N3 **proof** of the closure, shown colored in the “Proof” tab — the
proof is **self-sufficient** (its sources are `data:` URIs, the
documents' text is embedded) and **tamperable by hand**. **“Check
proof”**: `check` replays the derivation in a subprocess → **valid
/ invalid** verdict + numbered derivation steps. A tampered proof
(one predicate of the conclusion, a source, …) is **rejected**.
`engine.entail` / `engine.prove` / `engine.check_proof`,
`POST /api/entail` / `/api/prove` / `/api/check`.

**P5 delivered** (2026-11-22): **lab pack**. The header **Exercise**
menu loads an exercise into the editors (data, rules, query,
conclusion) and shows its **statement**:

- `cwm_lab/exercises/famille/` — warm-up (~30 min): walks through
  every function of the tool in miniature;
- `cwm_lab/exercises/recettes/` — main exercise (~60–90 min):
  food contraindications computed by N3 rules (absolute allergens +
  threshold nutrients with `math:` calculations), 9 recipes, 5
  patients, 6 exercises + **model answers** (`recettes/corriges/`)
  + discussion of the model's limits;
- `cwm_lab/exercises/GUIDE_ENSEIGNANT.md` (+
  `GUIDE_ENSEIGNANT.en.md`) — 2 h run-of-show, watchpoints,
  suggested grading;
- exercise convention (folder `enonce.md` + `*.n3` + optional
  `context.json`) documented in `cwm_lab/exercises/README.md` — a
  new exercise is added without code. Exercises are **in the
  package**: they ship with `pip install` (source or PyPI).

`engine.list_exercises` / `engine.load_exercise`,
`GET /api/exercises`, `GET /api/exercise?name=…`.

The **triple graph** (vis.js roadmap option, vendored locally) —
resources (blue), literals (green), blank nodes (grey); with “after
reasoning”, nodes created by the rules and new edges are highlighted
in orange. `engine.graph`, `POST /api/graph`. (Since P7, it is
**always visible** — see below.)

**P8 delivered** (2026-11-23): **processing cache**. In a lab, the
same processing (parse, reasoning, query, proof, proof check,
graph, serialization) is very likely to recur: it is served from a
**two-level cache** — memory (LRU, TTL 5 min) and **persistent
disk** (TTL 7 days, bounded at 200 MB) — instead of being
recomputed. The second occurrence of a processing is nearly
instantaneous, and the cache **survives restarts**: the gain
accumulates over several sessions. Key = SHA-256 of the full
payload (any edit forces recomputation); only complete, successful
results are cached; the response carries the `cached` flag.
Optional configuration (non-sensitive `config.yaml`, sensitive
git-ignored `.env` — examples committed); `cache.py`, 19 tests
including server integration.

**P9 delivered** (2026-11-23): **generative-AI KB filling** — the
**“Fill the KB (AI)”** button (action bar, size configurable:
≈ N facts / M entities) generates a realistic N3 dataset and
injects it **into the “data” editor** (visible, editable,
deletable — never a hidden KB), with a “generated by AI, verify”
banner that is hidden by any manual edit. The prompt is
constrained (N3 **data only**, no `log:implies` rule; domain = the
loaded exercise's statement + rules, else a generic domain;
realistic values that trigger **and do not trigger** the existing
rules' thresholds). The call goes **from the backend** to an
OpenAI-compatible API proxy (default: the institutional ProxyIAg):
the browser never sees the key. **Mandatory a posteriori controls**
— 1 parse (and zero rule detected), 2 coherence (reasoning on the
generated KB + existing rules, no `log:false`; timeout on
non-convergent rules → warning, not a rejection), 3 structural
plausibility (facts/entities within the requested range, every
entity typed) — and **bounded regeneration** (3 attempts, the
prompt enriched with the previous rejections) then an honest
report. **Session quotas** (requests + tokens, `config.yaml`
limits, counted in the backend, **persisted with the P8 cache**,
reset daily): exhausted → button disabled. Excluded from the P8
cache (non-deterministic, costly). Missing configuration (`.env`) →
button disabled with an explicit message; the app works without AI.
`ia.py` (+ extensions of `cache.py` and `server.py`), 43 tests
including server integration (fake proxy, network never touched).

**Privacy (opt-in)**: when the student clicks the button, the
loaded exercise's statement and rules are sent to the provider to
build the prompt (domain context). Nothing is sent without this
click; prompt size and content are bounded (statement ≤ 8 k
characters, rules ≤ 6 k).

**P10 delivered** (2026-11-23): **internationalization of the
interface** — the application is available in **French (default)
and English**, with a **language selector in the header**
(preference persisted in localStorage; `<html lang>` and the page
title follow the language). The **“CWM 2.0”** text of the header
subtitle points to the **CWM 2.0 repository README in the selected
language** (FR → `README.md`, EN → `README.en.md`,
`target="_blank"` — the `data-i18n-href` attribute). The
`static/i18n.js` module (zero dependency) carries both
dictionaries and applies the static strings via `data-i18n`
attributes (text, placeholder, tooltip, aria); dynamic strings
(results, banners, errors) go through `t(key, …)` in `app.js` and
are **re-rendered on language change** — without re-fetch, without
forcing the active tab, without rebuilding the graph (the user's
view is preserved) and without overwriting a hand-tampered proof.
On the backend, the AI messages (quota, proxy errors, controls,
generation refusal, status) are localized in `ia.py` (`MESSAGES`
fr/en table): the front sends its language
(`/api/ia/status?lang=`, `lang` in the `/api/ia/generate` body;
default and fallback `fr`). **Out of scope (content, not
interface)**: exercise statements, the model's note, CWM parse
engine errors (technical English) — and the **model prompt stays
in French** (calibrated on the lab's statements). 12 tests;
version `0.5.0`.

**P10.1 delivered** (2026-11-23): **bilingual labels of exercise
ontologies** — the data's `rdfs:label`s (`@fr` / `@en` on classes,
properties and individuals) are **resolved in the backend** in the
application's language: the interface only shows ready-to-use
strings, IRIs never change. Three-step fallback: language-labeled
→ unlabeled → first label present (deterministic, independent of
statement order after `canonicalize()`). Applied to **new query
rows** (raw / reasoned / diff), to the **new facts** of “Reason”
(diff computed on raw IRIs, then translated), to the graph's
**resource nodes, edges and hidden attributes**, and to the
**menu titles** of the exercises. On language change, these
contents are **re-fetched** in the new language (re-render in place;
the graph is updated **in place** in the vis DataSets, without
rebuilding the network — the user's view is preserved); the editors
are **never** touched. Both exercises' ontologies are bilingual
(predicates/classes typed `rdfs:Property`/`rdfs:Class` — the AI
plausibility control requires 0 untyped subject), proper names
stay **unlabeled** (fallback demo), and the **statements are
translated** (optional `enonce.en.md` per exercise, `enonce.md` =
fallback). Exercise queries select **resources** (a variable on
`rdfs:label` would double the rows). The `lang` parameter enters
the cache key; and since the disk cache is **shared between
instances** and survives restarts (TTL 7 d), the key also carries a
**signature of the code and exercise data**
(`cache.code_signature`, computed at startup): a code change
automatically invalidates the whole cache — never an entry written
by an older version of the engine. The **AI model's note** (the
only natural text of the answer, shown in the banner) is requested
**in the app's language** — the prompt stays French (calibrated),
only the note instruction follows the language. 13 tests + 2 cache
signature tests + 2 AI note tests; version `0.5.1`.

**Usability** (2026-11-24): the **language selector** leaves the
toolbar for the **very first line of the header** (right of the
title), always visible before any other control. Version `0.5.2`.

**Graph — selection focus** (2026-11-24): a **click on a node hides
the nodes that do not concern it** — remaining: the node, its
direct neighbors (edges in both directions) and the edges linking
it. A click on empty space (deselection) shows everything again;
multi-selection (Ctrl + click) takes the union of the
neighborhoods. Done via `hidden` on the vis DataSets (not
removal): positions and view preserved, and the mask survives a
language change. Version `0.5.2`.

**Help** (2026-11-24): a small **“?”** button in the status bar at
the bottom (right-aligned) opens a **popup window explaining what
every button and every checkbox does** — header bar, reasoning,
querying, validation, AI generation, graph. Static content in
`data-i18n`: the popup follows the interface language (open or
closed). Closing: button, click on the backdrop, Escape key (focus
returns to the “?” button). Version `0.5.2`.

**Externalized AI prompts** (2026-11-24): the prompt texts of the
“Fill the KB (AI)” button are out of the Python code so they can be
**refined by hand** — `cwm_lab/prompts/*.md`, **written in
Markdown** (`system.md`, `user.md`, conditional constraints,
generic domain, regeneration feedback; contract and placeholders
documented in `prompts/README.md`, English version
`prompts/README.en.md`). The files are **re-read on every
generation** (an edit is effective without restarting the server),
shipped in the wheel, and a missing file makes the prompt fall back
to the hard-coded original texts (a bad edit never breaks
generation). Version `0.5.2`.

**P7 delivered** (2026-11-23): **usability revamp** — the
interface is redesigned for a student discovering the tool:

- **2-column layout**: on the left the editors + a
  **unified action bar** grouped by goal (Reasoning / Query /
  Validate); on the right the **graph, always visible**, the
  **Conclusion/Proof editor** and the **results consolidated in
  tabs** (Parse / Reasoning / Query / Entailment / Proof / Export)
  — no more N stacked blocks. The Conclusion/Proof editor is on
  the right: a generated proof is dozens of lines long (`data:`
  URIs of thousands of characters), it no longer bloats the editors
  column;
- **adjustable column widths**: drag handle between the two columns
  (25–75 %, persisted in localStorage); the grid tracks are
  `minmax(0, …)` — **a result never changes the column widths**;
- **graph always visible and up to date**: the “Graph” button is
  gone — the persistent panel re-renders on every action (data/rule
  edit, Reason, Query with reasoning, exercise load, option
  change); the “after reasoning” and “hidden attributes”
  checkboxes are in the panel header;
- **“hidden attributes” mode**: literal nodes are replaced by a
  **counter badge** on the node (the hidden attributes are listed
  in the tooltip on hover) — the graph becomes readable when a
  resource carries many literals (`recettes`);
- **statements rendered Markdown → HTML**: minimal **stdlib**
  converter (`engine.render_markdown`: headings, nested lists,
  tables, code blocks, bold/italic; text escaped first, no
  injection possible); the `.md` files remain the source of truth
  in the repository.

10 tests added (110 total); version `0.2.0`.

Settled decisions:

- **Stack**: backend in **Python stdlib only** (`http.server` +
  JSON), browser frontend with **CodeMirror 6** (vendored locally,
  no CDN); zero added dependency in the repository;
- **Dependency**: CWM 2.0 (fork) — the only dependency, published
  on PyPI as `cwm`;
- **Audience**: Master MIAGE.

## Running

```sh
pip install cwm-lab    # installs the tool + CWM 2.0 (cwm, only dependency)

cwm-lab                # → http://127.0.0.1:8000
cwm-lab --port 8080
```

`pip install cwm-lab` automatically resolves `cwm>=2.9.3` (CWM 2.0,
fork, on PyPI); for development: `pip install -e .` from this
repository. `make test` runs the unit tests (196); `make serve`
starts the server.

## Configuration (P8/P9, optional)

The app starts **without any config file** (default values; AI is
then disabled — the rest of the tool works). Two optional files,
in `cwm_lab/`:

- `config.yaml` — **non-sensitive** settings: disk/memory cache
  retention (`ttl_disk`, `ttl_memory`), max disk size, memory entry
  count, and for P9 the **AI session quota** limits
  (`ia_max_requests`, `ia_max_tokens`, `ia_max_attempts`,
  `ia_timeout`, `ia_max_tokens_response`). Install:
  `cp cwm_lab/config.yaml.example cwm_lab/config.yaml && chmod 600 cwm_lab/config.yaml`;
- `.env` — **sensitive / local** data (git-ignored): cache
  directory (`CACHE_DIR`, default `~/.cache/lab_tp`), and for P9
  the AI: `IA_URL` (default: the institutional proxy), `IA_MODEL`
  (model alias, e.g. `proxyiag/mistral-small-24b`), `IA_API_KEY`
  (`sk-…` key, revocable — **never** in a versioned config).
  Install: `cp cwm_lab/.env.example cwm_lab/.env && chmod 600 cwm_lab/.env`.

## Deployment (P6)

Three levels, documented in [`DEPLOY.en.md`](DEPLOY.en.md)
([FR](DEPLOY.md)): **lab room / LAN** (zero dependencies —
`cwm-lab --host 0.0.0.0`), **department server** (gunicorn +
systemd + Caddy), and **Internet** (+ authentication). Since P6,
reasoning runs in a **killable subprocess** (a bad-faith cyclic rule
is killed at timeout) and a **concurrency ceiling**
(`max_reason_concurrent`, default 8) answers **503 “server busy”**
beyond it: 30 simultaneous students without blocking.

## Tree

```
cwm-lab/
├── README.md            # this file (French)
├── README.en.md         # this file (English)
├── ROADMAP.md           # roadmap + delivery log (phases, criteria, risks)
├── DEPLOY.md            # P6: deployment (3 levels) — see also
│                        #   DEPLOY.en.md + requirements-deploy.txt
├── pyproject.toml       # cwm-lab package (dependency: cwm>=2.9.3)
├── Makefile             # test / serve
├── cwm_lab/
│   ├── __init__.py      # version
│   ├── server.py        # http.server + /api/* endpoints (+ P6: WSGI
│   │                    #   app for gunicorn)
│   ├── _reason_worker.py  # P6: reasoning worker (killable subprocess,
│   │                      #   run by engine._run_closure)
│   ├── engine.py        # stateless wrapper over the swap APIs (testable core)
│   ├── cache.py         # P8: two-level cache (memory + disk) + config
│   ├── ia.py            # P9: AI KB filling (proxy, controls)
│   ├── config.yaml.example  # non-sensitive config (TTL, sizes, AI quotas)
│   ├── .env.example         # sensitive config (cache dir, AI) — optional
│   ├── prompts/          # P9: AI prompt texts (hand-editable Markdown)
│   ├── static/
│   │   ├── index.html   # dashboard (2 columns — editors + action
│   │   │                #   bar | persistent graph + tabs)
│   │   ├── app.js       # CodeMirror editor + API calls + rendering
│   │   │                #   (result tabs, auto graph, badges)
│   │   ├── i18n.js      # P10: FR/EN dictionaries + t() + language
│   │   │                #   selector (persistence, i18n re-render)
│   │   ├── style.css    # dashboard styles
│   │   ├── vendor/codemirror/  # CodeMirror 6 as local bundle (esbuild)
│   │   └── vendor/vis/         # vis-network + vis-data (UMD, graph)
│   └── exercises/       # lab exercises: .n3 + .md statements + model answers
│                        #   (in the package — ship with pip install)
└── tests/               # cwm_lab tests (engine, cache, server)
```

## Principles

- **Stateless**: each request rebuilds the store from the editors'
  text; no server state to manage — the **cache** (P8) is an
  **optimization, not a state**: only the already-computed JSON
  answer is stored (memory + disk), never a store;
- **Direct CWM APIs**: `think()`, `applyRules()`,
  `applyQueries()`, `applySparqlQueries()`, `testIncludes()`,
  `why`/`explainFormula`, `notation3` parser — no CLI round-trip,
  except `check` (subprocess `python -m swap.check`, because it
  manipulates `sys.argv`/`stdin`);
- **Per-request timeout**: a recursive rule must never block the
  lab (forward chaining not guaranteed on cyclic rules);
- **Zero own dependencies**: CWM 2.0 is the only dependency;
  CodeMirror and vis.js are downloaded once into
  `cwm_lab/static/vendor/` and committed (no CDN).
