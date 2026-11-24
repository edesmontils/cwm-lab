"""Tests P6 — déploiement serveur : raisonnement en subprocess
tuable, plafond de concurrence (503 « serveur occupé »), adaptateur
WSGI (gunicorn) et, si gunicorn est installé, un déploiement réel
end-to-end.

Lancer depuis la racine du dépôt :
    python3 -m unittest -v tests.test_deploy
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

import importlib.util
import io
import json
import os
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request

from cwm_lab import __version__, engine, server

#: KB + règle simple (un fait inféré).
KB = "@prefix : <http://example.org/> .\n:alice a :Person .\n"
RULES = (
    "@prefix : <http://example.org/> .\n"
    "@prefix log: <http://www.w3.org/2000/10/swap/log#> .\n"
    "@forAll :x .\n"
    "{ :x a :Person . } log:implies { :x :isPerson true } .\n"
)

#: Système auto-alimentant : la convergence est **infinie** (chaque
#: fait en engendre un nouveau) — le raisonnement doit être tué au
#: timeout, jamais laissé tourner en fond (risque #8 ROADMAP).
KB_CHAINE = "@prefix : <http://example.org/> .\n:a :chain :b .\n"
RULES_INFINIES = (
    "@prefix : <http://example.org/> .\n"
    "@prefix log: <http://www.w3.org/2000/10/swap/log#> .\n"
    "@forAll :x , :y .\n"
    "{ :x :chain :y . } log:implies { :y :chain2 [] } .\n"
    "@forAll :x , :y .\n"
    "{ :x :chain2 :y . } log:implies { :y :chain [] } .\n"
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestSubprocessTuable(unittest.TestCase):
    """Le raisonnement tourne dans un subprocess **tué** au timeout
    (risque #8) : au deadline, plus rien ne tourne en fond, et le
    moteur reste réutilisable (zéro état résiduel)."""

    def test_timeout_tue_le_subprocess(self):
        t0 = time.monotonic()
        r = engine.infer(KB_CHAINE, RULES_INFINIES, mode="think", timeout=1)
        total = time.monotonic() - t0
        self.assertFalse(r["ok"])
        self.assertTrue(r["timeout"])
        self.assertIn("timeout", r["errors"][0]["message"])
        # Le deadline est respecté (marge large : le worker démarre,
        # importe le moteur, puis tourne jusqu'au kill).
        self.assertLess(total, 30)
        self.assertLessEqual(r["elapsed_ms"], 15_000)

    def test_rerunnable_apres_kill(self):
        # Après un kill, aucune trace : un raisonnement normal
        # réussit dans le même processus.
        r = engine.infer(KB_CHAINE, RULES_INFINIES, mode="think", timeout=1)
        self.assertTrue(r["timeout"])
        r = engine.infer(KB, RULES, timeout=30)
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(len(r["new_facts"]), 1)
        self.assertFalse(r.get("busy"))


class TestPlafondConcurrence(unittest.TestCase):
    """P6 — semaphore de concurrence : au plafond, la requête
    reçoit immédiatement ``busy: true`` (503 côté serveur) au lieu
    de s'attarder en file."""

    def setUp(self):
        engine.set_reason_limit(1)
        self.addCleanup(engine.set_reason_limit, 0)

    def test_busy_au_plafond_puis_ok_apres(self):
        sem = engine._reason_sem
        self.assertIsNotNone(sem)
        sem.acquire()  # occupe la seule place
        try:
            r = engine.infer(KB, RULES, timeout=30)
            self.assertFalse(r["ok"])
            self.assertTrue(r.get("busy"))
            self.assertIn("serveur occupé", r["errors"][0]["message"])
            self.assertEqual(r["errors"][0]["doc"], "server")
        finally:
            sem.release()
        # Place libérée → la même requête réussit.
        r = engine.infer(KB, RULES, timeout=30)
        self.assertTrue(r["ok"], r["errors"])
        self.assertFalse(r.get("busy"))

    def test_sans_plafond_par_defaut(self):
        engine.set_reason_limit(0)  # mode local : aucun plafond
        self.assertIsNone(engine._reason_sem)
        r = engine.infer(KB, RULES, timeout=30)
        self.assertTrue(r["ok"], r["errors"])
        self.assertFalse(r.get("busy"))


def _wsgi_call(method, path, body=None, query=""):
    """Appelle l'application WSGI avec un environ factice ; renvoie
    ``(code, headers, body_bytes)``."""
    raw = (json.dumps(body).encode("utf-8") if body is not None
           else b"")
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "wsgi.input": io.BytesIO(raw),
        "CONTENT_LENGTH": str(len(raw)),
        "CONTENT_TYPE": "application/json",
    }
    state = {}

    def start_response(status, headers):
        state["status"] = status
        state["headers"] = headers

    chunks = server._wsgi_app(environ, start_response)
    code = int(state["status"].split(" ", 1)[0])
    return code, dict(state["headers"]), b"".join(chunks)


class TestWSGIAdapter(unittest.TestCase):
    """P6 — l'application WSGI (``cwm_lab.server:app``) sert la même
    API JSON que le serveur standard (testé avec un environ factice,
    sans gunicorn)."""

    def setUp(self):
        # Initialise les globals une fois (idempotent) : garantit que
        # l'appel ``_init_globals`` à l'intérieur de ``_wsgi_app`` ne
        # réinitialise PAS le semaphore pendant le test (sinon le
        # plafond posé ci-dessous serait écrasé).
        server._init_globals()
        self.addCleanup(engine.set_reason_limit, 0)
        # Le cache disque (persistant, partagé) est neutralisé :
        # un payload réutilisé entre tests ne doit pas servir une
        # réponse mise en cache (le 503 « busy » n'existe que pour
        # un raisonnement réellement demandé).
        self._old_cache = server.CACHE
        server.CACHE = None
        self.addCleanup(setattr, server, "CACHE", self._old_cache)

    def test_version(self):
        code, headers, body = _wsgi_call("GET", "/api/version")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["version"], __version__)

    def test_parse(self):
        code, _, body = _wsgi_call("POST", "/api/parse", {
            "text": "<http://example.org/a> a <http://example.org/B> .",
            "base_uri": "http://example.org/",
        })
        self.assertEqual(code, 200)
        out = json.loads(body)
        self.assertTrue(out["ok"], out)

    def test_404(self):
        code, _, _ = _wsgi_call("GET", "/api/inexistant")
        self.assertEqual(code, 404)

    def test_503_busy(self):
        # Plafond 1, place occupée → 503 « serveur occupé » (même
        # contrat que les 5 endpoints de raisonnement du serveur
        # standard).
        engine.set_reason_limit(1)
        engine._reason_sem.acquire()
        try:
            code, _, body = _wsgi_call("POST", "/api/infer", {
                "kb": KB, "rules": RULES,
                "base_uri": "http://example.org/", "timeout": 30,
            })
            self.assertEqual(code, 503)
            out = json.loads(body)
            self.assertTrue(out["busy"])
            self.assertIn("serveur occupé", out["errors"][0]["message"])
        finally:
            engine._reason_sem.release()


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@unittest.skipUnless(importlib.util.find_spec("gunicorn") is not None,
                     "gunicorn non installé (dépendance de déploiement — "
                     "requirements-deploy.txt)")
class TestGunicornE2E(unittest.TestCase):
    """P6 — gunicorn réel devant l'application WSGI (le mode de
    déploiement de production) : démarrage, requêtes HTTP, arrêt."""

    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.proc = subprocess.Popen(
            [sys.executable, "-m", "gunicorn", "cwm_lab.server:app",
             "--bind", "127.0.0.1:%d" % cls.port,
             "--workers", "1", "--timeout", "60",
             "--log-level", "error"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        deadline = time.time() + 30
        while time.time() < deadline:
            if cls.proc.poll() is not None:
                out = cls.proc.stdout.read().decode("utf-8", "replace")
                raise AssertionError("gunicorn a quitté au démarrage :\n%s"
                                     % out)
            try:
                with urllib.request.urlopen(
                        "http://127.0.0.1:%d/api/version" % cls.port,
                        timeout=1) as r:
                    if r.status == 200:
                        return
            except OSError:
                time.sleep(0.2)
        raise AssertionError("gunicorn n'a pas démarré en 30 s")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.proc.kill()
            cls.proc.wait()
        if cls.proc.stdout is not None:
            cls.proc.stdout.close()

    def test_version(self):
        with urllib.request.urlopen(
                "http://127.0.0.1:%d/api/version" % self.port) as r:
            self.assertEqual(r.status, 200)
            self.assertEqual(json.loads(r.read().decode())["version"],
                             __version__)

    def test_infer(self):
        req = urllib.request.Request(
            "http://127.0.0.1:%d/api/infer" % self.port,
            data=json.dumps({
                "kb": KB, "rules": RULES,
                "base_uri": "http://example.org/", "timeout": 30,
            }).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            self.assertEqual(r.status, 200)
            out = json.loads(r.read().decode())
            self.assertTrue(out["ok"], out)
            self.assertEqual(len(out["new_facts"]), 1)

    def test_404(self):
        try:
            urllib.request.urlopen(
                "http://127.0.0.1:%d/api/inexistant" % self.port)
            self.fail("404 attendu")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)


if __name__ == "__main__":
    unittest.main()
