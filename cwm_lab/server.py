"""server — serveur HTTP (stdlib) de l'outil TP Web sémantique.

Lancement :

    python3 -m cwm_lab.server               # http://127.0.0.1:8000
    python3 -m cwm_lab.server --port 8080

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
                          "store_rules": bool, "timeout": float}``
                          → résultat de :func:`cwm_lab.engine.infer` ;
- ``POST /api/query`` : body JSON ``{"kb": ..., "query": ...,
                          "rules": ..., "base_uri": ..., "reason": bool,
                          "mode": "think" | "once", "store_rules": bool,
                          "timeout": float}``
                          → résultat de :func:`cwm_lab.engine.query` ;
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

Endpoints d'exercices et de visualisation (P5) :

- ``GET /api/exercises`` : la liste des exercices disponibles
  → ``{"exercises": [{"name", "title", "files"}, …]}`` ;
- ``GET /api/exercise?name=X`` : l'exercice ``X`` (données, règles,
  énoncé, préchargements) → résultat de
  :func:`cwm_lab.engine.load_exercise` ;
- ``POST /api/graph`` : body JSON ``{"kb": ..., "rules": ...,
  "base_uri": ..., "reason": bool, "mode": "think" | "once",
  "timeout": float}`` → résultat de
  :func:`cwm_lab.engine.graph` (nœuds/arcs vis.js, ``inferred``
  si la clôture est calculée).

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
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__, cache, engine

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

#: Cache des traitements (P8) : deux niveaux (mémoire + disque
#: persisté), voir ``cache.py``. ``None`` = cache désactivé (ex.
#: répertoire non créable) — l'API fonctionne alors sans cache.
CACHE = None

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
        key = cache.Cache.make_key(api, req)
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
        if path == "/api/exercises":
            self._send_json(engine.list_exercises())
            return
        if path == "/api/exercise":
            params = urllib.parse.parse_qs(query_string)
            name = (params.get("name") or [""])[0]
            self._send_json(engine.load_exercise(name))
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
            ))
            self._send_json(result)
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
            ))
            self._send_json(result)
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
            self._send_json(result)
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
            self._send_json(result)
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
            ))
            self._send_json(result)
            return
        self._send_json({"error": "endpoint inconnu"}, status=404)

    def log_message(self, fmt, *args):  # silence le log par défaut
        sys.stderr.write("[cwm-tp] %s\n" % (fmt % args))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="cwm_lab.server",
                                 description="Outil TP Web sémantique (CWM 2.0)")
    ap.add_argument("--port", type=int, default=8000, help="port (défaut 8000)")
    ap.add_argument("--host", default="127.0.0.1", help="interface (défaut 127.0.0.1)")
    args = ap.parse_args(argv)
    # Cache des traitements (P8) : config.yaml (TTL, tailles) + .env
    # (répertoire, sensible) — absents, les valeurs par défaut.
    global CACHE
    try:
        CACHE = cache.Cache(cache.load_config())
    except Exception as e:  # le cache ne doit jamais bloquer le TP
        CACHE = None
        print("cache indisponible (%s) : mode sans cache" % e)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print("Outil TP Web sémantique — CWM 2.0 (lab %s)" % __version__)
    print("Cache : %s"
          % (CACHE.disk_dir or "mémoire seule (répertoire disque indisponible)"))
    print("Ouvrir http://%s:%d   (Ctrl-C pour arrêter)" % (args.host, args.port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
