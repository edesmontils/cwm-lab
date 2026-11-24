"""server — serveur HTTP (stdlib) de CWM Lab.

Lancement :

    python3 -m cwm_lab.server               # http://127.0.0.1:8000
    python3 -m cwm_lab.server --port 8080

Déploiement (P6 — voir ``DEPLOY.md``) : le même code tourne sous
**gunicorn** (dépendance de déploiement uniquement, jamais importée
par le code du TP) via l'application WSGI :data:`app` :

    gunicorn cwm_lab.server:app --bind 0.0.0.0:8000

Les 5 endpoints de raisonnement (``infer`` / ``query`` / ``entail`` /
``prove`` / ``graph``) répondent **503** « serveur occupé » quand le
plafond de concurrence est atteint (``max_reason_concurrent`` de
``config.yaml``, défaut 8 — le raisonnement tourne alors dans un
subprocess tuable, voir :mod:`cwm_lab.engine`).

Endpoints (P0) :

- ``GET  /``            : le tableau de bord (``static/index.html``) ;
- ``GET  /static/...``  : fichiers statiques (app.js, style.css, …) ;
- ``POST /api/parse``   : body JSON ``{"text": ..., "base_uri": ...}``
                          → résultat de :func:`cwm_lab.engine.parse` ;
- ``POST /api/serialize`` : body JSON ``{"text": ..., "base_uri": ...,
                          "format": "n3" | "turtle" | "ntriples" | "rdf"}``
                          → résultat de :func:`cwm_lab.engine.serialize` ;
- ``POST /api/infer`` : body JSON ``{"kb": ..., "rules": ...,
                           "base_uri": ..., "mode": "think" | "once",
                           "store_rules": bool, "timeout": float,
                           "lang": "fr" | "en"}``
                           → résultat de :func:`cwm_lab.engine.infer`
                           (les ``new_facts`` portant un
                           ``rdfs:label`` sont affichés dans ``lang``) ;
- ``POST /api/query`` : body JSON ``{"kb": ..., "query": ...,
                           "rules": ..., "base_uri": ..., "reason": bool,
                           "mode": "think" | "once", "store_rules": bool,
                           "timeout": float, "lang": "fr" | "en"}``
                           → résultat de :func:`cwm_lab.engine.query`
                           (mêmes libellés d'affichage) ;
- ``POST /api/entail`` : body JSON ``{"kb": ..., "rules": ...,
                          "conclusion": ..., "base_uri": ...,
                          "mode": "think" | "once", "timeout": float}``
                          → résultat de :func:`cwm_lab.engine.entail` ;
- ``POST /api/prove`` : body JSON ``{"kb": ..., "rules": ...,
                          "base_uri": ..., "mode": "think" | "once",
                          "timeout": float}``
                          → résultat de :func:`cwm_lab.engine.prove` ;
- ``POST /api/check`` : body JSON ``{"proof": ...}``
                          → résultat de :func:`cwm_lab.engine.check_proof`.

Endpoints IA générative (P9 — jamais cachés : non déterministes) :

- ``GET /api/ia/status?lang=fr`` : état de l'IA pour le front
  (activée ?, modèle, quota de séance restant) → :func:`cwm_lab.ia.status` ;
  ``lang`` (``fr`` / ``en``, défaut ``fr``) localise le message du statut ;
- ``POST /api/ia/generate`` : body JSON ``{"enonce", "rules",
  "base_uri", "facts", "entities", "exercise", "timeout", "lang"}`` →
  :func:`cwm_lab.ia.generate` (prompt → proxy → contrôles parse /
  cohérence / plausibilité → régénération bornée) ; ``lang``
  (``fr`` / ``en``, défaut ``fr``) localise les messages de génération
  (le prompt du modèle reste en français).

Endpoints d'exercices et de visualisation (P5) :

- ``GET /api/exercises?lang=fr`` : la liste des exercices
  disponibles (``lang`` ``fr`` / ``en``, défaut ``fr`` — le titre
  est lu dans l'énoncé de cette langue)
  → ``{"exercises": [{"name", "title", "files"}, …]}`` ;
- ``GET /api/exercise?name=X&lang=fr`` : l'exercice ``X`` (données,
  règles, énoncé, préchargements) → résultat de
  :func:`cwm_lab.engine.load_exercise` (énoncé ``enonce.en.md`` si
  ``lang=en`` et qu'il existe) ;
- ``POST /api/graph`` : body JSON ``{"kb": ..., "rules": ...,
  "base_uri": ..., "reason": bool, "mode": "think" | "once",
  "timeout": float, "lang": "fr" | "en"}`` → résultat de
  :func:`cwm_lab.engine.graph` (nœuds/arcs vis.js, ``inferred``
  si la clôture est calculée ; libellés d'ontologie dans ``lang``).

``POST /api/parse`` accepte également ``"language": "sparql"``
(validation de syntaxe de l'éditeur de requête).

Le serveur est threadé (``ThreadingHTTPServer``) : chaque requête
travaille sur son propre store (voir ``engine.py``), aucun verouillage
n'est nécessaire.
"""

# Copyright 2026 CWM 2.0 maintainers
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import io
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__, cache, engine, ia

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

#: Cache des traitements (P8) : deux niveaux (mémoire + disque
#: persisté), voir ``cache.py``. ``None`` = cache désactivé (ex.
#: répertoire non créable) — l'API fonctionne alors sans cache.
CACHE = None

#: Empreinte du code + des données d'exercices au démarrage
#: (:func:`cwm_lab.cache.code_signature`) : incluse dans la clé de
#: cache — le cache disque (partagé, TTL 7 j) ne sert jamais une
#: entrée écrite par une autre version du code.
CODE_SIG = ""

#: Configuration (P8/P9) : ``config.yaml`` + ``.env`` (voir
#: :func:`cwm_lab.cache.load_config`). ``None`` = valeurs par défaut
#: (l'appli démarre sans config ; l'IA est alors désactivée).
CONFIG = None

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "cwm-tp/" + __version__

    # ------------------------------------------------------------------
    # utilitaires
    # ------------------------------------------------------------------
    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path):
        if not os.path.isfile(path):
            self.send_error(404, "Not Found")
            return
        ext = os.path.splitext(path)[1].lower()
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPES.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        # Outil de dev : pas de cache heuristique (rechargements propres
        # pendant les TP, sans versionner les noms de fichiers).
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _cached(self, api, req, compute):
        """Endpoint avec cache (P8) : même endpoint + même payload
        complet → réponse servie depuis le cache (drapeau
        ``cached: true``) au lieu d'être recalculée. Seuls les
        résultats complets et réussis sont mis en cache (jamais un
        timeout partiel, jamais une erreur). Sans cache actif
        (``CACHE is None``), comportement direct."""
        global CACHE
        if CACHE is None:
            return compute()
        # ``sig`` : empreinte du code — les entrées écrites par une
        # autre version du code (cache disque partagé, TTL 7 j) ne
        # sont jamais servies.
        key = cache.Cache.make_key(api, req, sig=CODE_SIG)
        hit = CACHE.get(key)
        if hit is not None:
            out = dict(hit)
            out["cached"] = True
            return out
        result = compute()
        if cache.cachable(result):
            CACHE.put(key, result)
        out = dict(result)
        out["cached"] = False
        return out

    # ------------------------------------------------------------------
    # GET : statiques + /api/version
    # ------------------------------------------------------------------
    def do_GET(self):
        path, _, query_string = self.path.partition("?")
        if path == "/api/version":
            self._send_json({"version": __version__})
            return
        if path == "/api/ia/status":
            # P9 : état de l'IA (bouton activé / désactivé + quota
            # de séance restant) — lecture seule, pas de cache.
            # i18n : ``lang`` (fr/en) — le message du statut est
            # localisé côté backend (le front envoie sa langue).
            params = urllib.parse.parse_qs(query_string)
            lang = (params.get("lang") or ["fr"])[0]
            if lang not in ia.LANGS:
                lang = "fr"
            self._send_json(ia.status(CONFIG or {},
                                      CACHE.disk_dir if CACHE else None,
                                      lang=lang))
            return
        if path == "/api/exercises":
            params = urllib.parse.parse_qs(query_string)
            lang = (params.get("lang") or ["fr"])[0]
            self._send_json(engine.list_exercises(lang=lang))
            return
        if path == "/api/exercise":
            params = urllib.parse.parse_qs(query_string)
            name = (params.get("name") or [""])[0]
            lang = (params.get("lang") or ["fr"])[0]
            self._send_json(engine.load_exercise(name, lang=lang))
            return
        if path == "/" or path == "/index.html":
            self._send_file(os.path.join(STATIC_DIR, "index.html"))
            return
        if path.startswith("/static/"):
            # anti-traversée de dossier
            rel = os.path.normpath(path[len("/static/"):])
            full = os.path.realpath(os.path.join(STATIC_DIR, rel))
            if not full.startswith(os.path.realpath(STATIC_DIR) + os.sep):
                self.send_error(403, "Forbidden")
                return
            self._send_file(full)
            return
        self.send_error(404, "Not Found")

    # ------------------------------------------------------------------
    # POST : API
    # ------------------------------------------------------------------
    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/parse":
            try:
                req = self._read_json()
            except (ValueError, UnicodeDecodeError):
                self._send_json({"error": "body JSON invalide"}, status=400)
                return
            text = req.get("text", "")
            base_uri = req.get("base_uri") or engine.DEFAULT_BASE_URI
            result = self._cached("parse", req, lambda: engine.parse(
                text, base_uri=base_uri,
                language=req.get("language", "n3")))
            self._send_json(result)
            return
        if path == "/api/serialize":
            try:
                req = self._read_json()
            except (ValueError, UnicodeDecodeError):
                self._send_json({"error": "body JSON invalide"}, status=400)
                return
            text = req.get("text", "")
            base_uri = req.get("base_uri") or engine.DEFAULT_BASE_URI
            format = req.get("format", "n3")
            result = self._cached("serialize", req, lambda: engine.serialize(
                text, format=format, base_uri=base_uri))
            self._send_json(result)
            return
        if path == "/api/infer":
            try:
                req = self._read_json()
            except (ValueError, UnicodeDecodeError):
                self._send_json({"error": "body JSON invalide"}, status=400)
                return
            base_uri = req.get("base_uri") or engine.DEFAULT_BASE_URI
            result = self._cached("infer", req, lambda: engine.infer(
                req.get("kb", ""), req.get("rules", ""),
                base_uri=base_uri,
                mode=req.get("mode", "think"),
                store_rules=bool(req.get("store_rules", False)),
                timeout=req.get("timeout", 10.0),
                lang=req.get("lang", "fr"),
            ))
            # P6 : plafond de concurrence atteint (semaphore —
            # engine.set_reason_limit) : 503 « serveur occupé »,
            # l'étudiant retente immédiatement après.
            status = 503 if result.get("busy") else 200
            self._send_json(result, status=status)
            return
        if path == "/api/query":
            try:
                req = self._read_json()
            except (ValueError, UnicodeDecodeError):
                self._send_json({"error": "body JSON invalide"}, status=400)
                return
            base_uri = req.get("base_uri") or engine.DEFAULT_BASE_URI
            result = self._cached("query", req, lambda: engine.query(
                req.get("kb", ""), req.get("query", ""),
                req.get("rules", ""),
                base_uri=base_uri,
                reason=bool(req.get("reason", False)),
                mode=req.get("mode", "think"),
                store_rules=bool(req.get("store_rules", False)),
                timeout=req.get("timeout", 10.0),
                lang=req.get("lang", "fr"),
            ))
            # P6 : plafond de concurrence atteint (semaphore —
            # engine.set_reason_limit) : 503 « serveur occupé »,
            # l'étudiant retente immédiatement après.
            status = 503 if result.get("busy") else 200
            self._send_json(result, status=status)
            return
        if path == "/api/entail":
            try:
                req = self._read_json()
            except (ValueError, UnicodeDecodeError):
                self._send_json({"error": "body JSON invalide"}, status=400)
                return
            base_uri = req.get("base_uri") or engine.DEFAULT_BASE_URI
            result = self._cached("entail", req, lambda: engine.entail(
                req.get("kb", ""), req.get("rules", ""),
                req.get("conclusion", ""),
                base_uri=base_uri,
                mode=req.get("mode", "think"),
                timeout=req.get("timeout", 10.0),
            ))
            # P6 : plafond de concurrence atteint (semaphore —
            # engine.set_reason_limit) : 503 « serveur occupé »,
            # l'étudiant retente immédiatement après.
            status = 503 if result.get("busy") else 200
            self._send_json(result, status=status)
            return
        if path == "/api/prove":
            try:
                req = self._read_json()
            except (ValueError, UnicodeDecodeError):
                self._send_json({"error": "body JSON invalide"}, status=400)
                return
            base_uri = req.get("base_uri") or engine.DEFAULT_BASE_URI
            result = self._cached("prove", req, lambda: engine.prove(
                req.get("kb", ""), req.get("rules", ""),
                base_uri=base_uri,
                mode=req.get("mode", "think"),
                timeout=req.get("timeout", 10.0),
            ))
            # P6 : plafond de concurrence atteint (semaphore —
            # engine.set_reason_limit) : 503 « serveur occupé »,
            # l'étudiant retente immédiatement après.
            status = 503 if result.get("busy") else 200
            self._send_json(result, status=status)
            return
        if path == "/api/check":
            try:
                req = self._read_json()
            except (ValueError, UnicodeDecodeError):
                self._send_json({"error": "body JSON invalide"}, status=400)
                return
            result = self._cached("check", req,
                                  lambda: engine.check_proof(
                                      req.get("proof", "")))
            self._send_json(result)
            return
        if path == "/api/graph":
            try:
                req = self._read_json()
            except (ValueError, UnicodeDecodeError):
                self._send_json({"error": "body JSON invalide"}, status=400)
                return
            base_uri = req.get("base_uri") or engine.DEFAULT_BASE_URI
            result = self._cached("graph", req, lambda: engine.graph(
                req.get("kb", ""), req.get("rules", ""),
                base_uri=base_uri,
                reason=bool(req.get("reason", False)),
                mode=req.get("mode", "think"),
                timeout=req.get("timeout", 10.0),
                # P7 : mode « attributs masqués » (littéraux → pastilles)
                hide_literals=bool(req.get("hide_literals", False)),
                # i18n P10.1 : libellés de l'ontologie dans la langue
                # du front (défaut/repli « fr »)
                lang=req.get("lang", "fr"),
            ))
            # P6 : plafond de concurrence atteint (semaphore —
            # engine.set_reason_limit) : 503 « serveur occupé »,
            # l'étudiant retente immédiatement après.
            status = 503 if result.get("busy") else 200
            self._send_json(result, status=status)
            return
        if path == "/api/ia/generate":
            # P9 : génération par IA — jamais cachée (P8) : non
            # déterministe et coûteuse ; quotas de séance comptés
            # côté backend (persistés avec le cache).
            try:
                req = self._read_json()
            except (ValueError, UnicodeDecodeError):
                self._send_json({"error": "body JSON invalide"}, status=400)
                return
            def _int(key, default, lo, hi):
                try:
                    return max(lo, min(hi, int(req.get(key, default))))
                except (TypeError, ValueError):
                    return default
            # i18n : ``lang`` (fr/en) — les messages de génération
            # sont localisés côté backend ; le prompt du modèle reste
            # en français (calibré).
            lang = req.get("lang") or "fr"
            if lang not in ia.LANGS:
                lang = "fr"
            result = ia.generate(
                CONFIG or {},
                enonce=req.get("enonce", "") or "",
                rules=req.get("rules", "") or "",
                base_uri=req.get("base_uri") or engine.DEFAULT_BASE_URI,
                n_facts=_int("facts", 40, 1, 2000),
                n_entities=_int("entities", 10, 1, 500),
                exercise=req.get("exercise"),
                timeout=req.get("timeout"),
                cache_dir=CACHE.disk_dir if CACHE else None,
                lang=lang,
            )
            # 429 : quota de séance épuisé (le bouton se désactive)
            statut = 429 if (not result["ok"]
                             and result.get("status") == 429) else 200
            self._send_json(result, status=statut)
            return
        self._send_json({"error": "endpoint inconnu"}, status=404)

    def log_message(self, fmt, *args):  # silence le log par défaut
        sys.stderr.write("[cwm-tp] %s\n" % (fmt % args))


#: Drapeau d'initialisation des globals (voir :func:`_init_globals`).
_INITIALIZED = False


def _init_globals():
    """P6 — initialise les globals partagés (``CONFIG`` / ``CACHE`` /
    ``CODE_SIG`` + plafond de concurrence des raisonnements), une
    seule fois — commune au serveur standard (``main``) et à
    l'adaptateur WSGI (``app``). Idempotent : gunicorn charge le
    module une fois par worker, mais l'initialisation ne doit jamais
    se refaire (le semaphore de :mod:`cwm_lab.engine` en dépend)."""
    global CACHE, CODE_SIG, CONFIG, _INITIALIZED
    if _INITIALIZED:
        return
    # Configuration (P8/P9) : config.yaml (TTL, tailles, quotas IA)
    # + .env (répertoire du cache, IA — sensible) ; absents, les
    # valeurs par défaut (l'IA est alors désactivée).
    CONFIG = cache.load_config()
    # Empreinte du code + des données d'exercices : incluse dans la
    # clé de cache — après un changement de code, les entrées du
    # cache disque (partagé entre instances, TTL 7 j) ne sont plus
    # servies (elles n'ont plus la même clé).
    CODE_SIG = cache.code_signature()
    try:
        CACHE = cache.Cache(CONFIG)
    except Exception as e:  # le cache ne doit jamais bloquer le TP
        CACHE = None
        print("cache indisponible (%s) : mode sans cache" % e)
    # P6 : plafond de raisonnements simultanés (``config.yaml`` —
    # défaut 8). Au-delà, une requête de raisonnement ne s'attarde
    # pas : elle reçoit immédiatement 503 « serveur occupé » (risque
    # #8 ROADMAP — une règle cyclique de mauvaise foi ne peut ni
    # bloquer ni saturer le serveur partagé).
    engine.set_reason_limit(CONFIG.get("max_reason_concurrent", 8))
    _INITIALIZED = True


# ----------------------------------------------------------------------
# P6 — adaptateur WSGI (gunicorn)
# ----------------------------------------------------------------------
# Le serveur standard repose sur ``http.server`` (zéro dépendance —
# la politique du TP). Pour un déploiement multi-étudiants,
# **gunicorn** (dépendance de *déploiement* uniquement —
# ``requirements-deploy.txt``, jamais importée par le code du TP)
# fait tourner l'application WSGI :data:`app`. L'adaptateur réutilise
# la même :class:`Handler` (mêmes ``do_GET`` / ``do_POST``, même API
# JSON) : un sous-classe capture la réponse — statut, en-têtes, corps
# — en surchargeant ``send_response`` / ``send_header`` /
# ``end_headers`` ; ``send_error`` de la base classe fonctionne alors
# tel quel.

class _WSGIHeaders:
    """Substitut minimal de ``email.message.Message`` : les en-têtes
    de l'environ WSGI (``HTTP_*``) + ``Content-Length`` /
    ``Content-Type`` — seuls ceux utilisés par :class:`Handler`."""

    def __init__(self, environ):
        self._d = {}
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                name = key[5:].replace("_", "-").title()
                self._d[name] = value
        if "CONTENT_LENGTH" in environ:
            self._d["Content-Length"] = environ["CONTENT_LENGTH"]
        if "CONTENT_TYPE" in environ:
            self._d["Content-Type"] = environ["CONTENT_TYPE"]

    def get(self, key, default=None):
        return self._d.get(key, default)


class _WSGIWFile:
    """``wfile`` de la handler WSGI : recueille le corps (les
    ``write`` de :meth:`Handler._send_json` / ``_send_file`` /
    ``send_error``)."""

    def __init__(self, chunks):
        self._chunks = chunks

    def write(self, chunk):
        if chunk:
            self._chunks.append(chunk)


class _WSGIHandler(Handler):
    """:class:`Handler` adaptée WSGI — la réponse est capturée
    (``_status`` / ``_headers`` / ``_chunks``) au lieu d'être écrite
    sur une socket. ``__init__`` de :mod:`http.server` (socket) n'est
    **pas** appelé : la requête vient de l'environ WSGI."""

    def __init__(self, path, method, headers, body):
        self.command = method
        self.path = path
        self.headers = headers
        self.rfile = io.BytesIO(body)
        self._status = "200 OK"
        self._headers = []
        self._chunks = []
        self.wfile = _WSGIWFile(self._chunks)

    def send_response(self, code, message=None):
        if message:
            self._status = "%d %s" % (code, message)
        else:
            self._status = "%d %s" % (code,
                                      BaseHTTPRequestHandler.responses.get(
                                          code, ("Erreur",))[0])

    def send_header(self, key, value):
        self._headers.append((key, str(value)))

    def end_headers(self):
        pass


def _wsgi_app(environ, start_response):
    """Application WSGI (cible ``cwm_lab.server:app`` de gunicorn).

    Convertit l'environ WSGI en :class:`_WSGIHandler` (mêmes méthodes
    ``do_GET`` / ``do_POST`` que le serveur standard) et renvoie la
    réponse capturée. Toute exception de l'application remonte à
    gunicorn (réponse 500 standard) — même comportement qu'un crash
    de la requête sur le serveur standard.
    """
    _init_globals()
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    body = environ["wsgi.input"].read(length) if length else b""
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/")
    query = environ.get("QUERY_STRING", "")
    handler = _WSGIHandler(path + (("?" + query) if query else ""),
                           method, _WSGIHeaders(environ), body)
    if method == "GET":
        handler.do_GET()
    elif method == "POST":
        handler.do_POST()
    else:
        handler.send_error(501, "Unsupported method (%s)" % method)
    start_response(handler._status, handler._headers)
    out = b"".join(handler._chunks)
    return [out] if out else []


#: Application WSGI — cible de gunicorn (déploiement, P6) :
#: ``gunicorn cwm_lab.server:app --bind 0.0.0.0:8000``
app = _wsgi_app


def main(argv=None):
    ap = argparse.ArgumentParser(prog="cwm_lab.server",
                                 description="CWM Lab (CWM 2.0)")
    ap.add_argument("--port", type=int, default=8000, help="port (défaut 8000)")
    ap.add_argument("--host", default="127.0.0.1", help="interface (défaut 127.0.0.1)")
    args = ap.parse_args(argv)
    _init_globals()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print("CWM Lab — CWM 2.0 (v%s)" % __version__)
    print("Cache : %s"
          % (CACHE.disk_dir or "mémoire seule (répertoire disque indisponible)"))
    ia_state = ia.status(CONFIG, CACHE.disk_dir if CACHE else None)
    print("IA : %s" % ("activée (%s @ %s)"
          % (ia_state["model"], ia_state["url"]) if ia_state["enabled"]
          else "désactivée — " + (ia_state["reason"] or "")))
    print("Ouvrir http://%s:%d   (Ctrl-C pour arrêter)" % (args.host, args.port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
