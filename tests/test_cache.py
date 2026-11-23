"""Tests de cwm_lab.cache (P8 : cache deux niveaux mémoire + disque).

Lancer depuis la racine du dépôt :
    python3 -m unittest -v tests.test_cache
ou : make test-lab
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

import json
import os
import shutil
import tempfile
import threading
import time
import unittest
import urllib.request

from cwm_lab import cache, server


def make_config(tmpdir, **over):
    """Config de test : cache dans un répertoire temporaire."""
    cfg = dict(cache.DEFAULTS)
    cfg["cache_dir"] = os.path.join(tmpdir, "cache")
    cfg.update(over)
    return cfg


class TestParsers(unittest.TestCase):
    def test_flat_yaml(self):
        text = """
# commentaire
ttl_disk: 7d
max_disk_mb: 200

memory_entries: 64
sans deux points du tout
"""
        flat = cache.parse_flat_yaml(text)
        self.assertEqual(flat["ttl_disk"], "7d")
        self.assertEqual(flat["max_disk_mb"], "200")
        self.assertEqual(flat["memory_entries"], "64")
        self.assertEqual(len(flat), 3)

    def test_flat_env(self):
        text = """
# commentaire
CACHE_DIR=/tmp/x
IA_API_KEY="abc"
"""
        env = cache.parse_flat_env(text)
        self.assertEqual(env["CACHE_DIR"], "/tmp/x")
        self.assertEqual(env["IA_API_KEY"], "abc")

    def test_parse_duration(self):
        self.assertEqual(cache._parse_duration("7d", 0), 7 * 86400)
        self.assertEqual(cache._parse_duration("12h", 0), 12 * 3600)
        self.assertEqual(cache._parse_duration("30m", 0), 1800)
        self.assertEqual(cache._parse_duration("45", 0), 45)
        self.assertEqual(cache._parse_duration("45s", 0), 45)
        self.assertEqual(cache._parse_duration("??", 99), 99)
        self.assertEqual(cache._parse_duration(None, 99), 99)


class TestLoadConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cwm-tp-cfg.")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_defauts_sans_fichiers(self):
        cfg = cache.load_config(self.tmp)
        self.assertEqual(cfg["ttl_disk"], 7 * 86400)
        self.assertEqual(cfg["ttl_memory"], 300)
        self.assertEqual(cfg["max_disk_bytes"], 200 * 1024 * 1024)
        self.assertEqual(cfg["memory_entries"], 64)
        self.assertEqual(cfg["ia_provider"], "")

    def test_config_yaml_et_env(self):
        with open(os.path.join(self.tmp, "config.yaml"), "w",
                  encoding="utf-8") as f:
            f.write("ttl_disk: 2d\nttl_memory: 1m\nmax_disk_mb: 10\n"
                    "memory_entries: 8\n")
        with open(os.path.join(self.tmp, ".env"), "w",
                  encoding="utf-8") as f:
            f.write("CACHE_DIR=/tmp/autre\nIA_PROVIDER=ProxyIAg\n"
                    "IA_MODEL=qwen\nIA_API_KEY=k\n")
        cfg = cache.load_config(self.tmp)
        self.assertEqual(cfg["ttl_disk"], 2 * 86400)
        self.assertEqual(cfg["ttl_memory"], 60)
        self.assertEqual(cfg["max_disk_bytes"], 10 * 1024 * 1024)
        self.assertEqual(cfg["memory_entries"], 8)
        self.assertEqual(cfg["cache_dir"], "/tmp/autre")
        self.assertEqual(cfg["ia_provider"], "ProxyIAg")
        self.assertEqual(cfg["ia_model"], "qwen")
        self.assertEqual(cfg["ia_api_key"], "k")

    def test_config_casse_ne_bloque_pas(self):
        with open(os.path.join(self.tmp, "config.yaml"), "w",
                  encoding="utf-8") as f:
            f.write("max_disk_mb: pas-un-nombre\nmemory_entries: xx\n")
        cfg = cache.load_config(self.tmp)  # valeurs par défaut conservées
        self.assertEqual(cfg["max_disk_bytes"], 200 * 1024 * 1024)
        self.assertEqual(cfg["memory_entries"], 64)


class TestCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cwm-tp-cache.")
        self.now = [1000.0]
        self.cfg = make_config(self.tmp)
        self.c = cache.Cache(self.cfg, clock=lambda: self.now[0])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_put_get_memoire(self):
        k = cache.Cache.make_key("parse", {"text": ":a :b :c ."})
        self.assertIsNone(self.c.get(k))
        self.c.put(k, {"ok": True, "n": 1})
        self.assertEqual(self.c.get(k), {"ok": True, "n": 1})

    def test_cle_sensible_au_payload(self):
        k1 = cache.Cache.make_key("parse", {"text": ":a :b :c ."})
        k2 = cache.Cache.make_key("parse", {"text": ":a :b :d ."})
        k3 = cache.Cache.make_key("infer", {"text": ":a :b :c ."})
        self.assertNotEqual(k1, k2)   # 1 caractère de différence
        self.assertNotEqual(k1, k3)   # endpoint différent
        self.assertEqual(cache.Cache.make_key("parse", {"text": ":a :b :c ."}),
                         k1)         # stable

    def test_cle_sensible_a_l_empreinte_du_code(self):
        """Une entrée écrite par une autre version du code (empreinte
        différente) n'est jamais servie : le cache disque est partagé
        entre instances et survit aux redémarrages (TTL 7 j)."""
        k1 = cache.Cache.make_key("parse", {"text": "x"}, sig="aaa")
        k2 = cache.Cache.make_key("parse", {"text": "x"}, sig="bbb")
        k3 = cache.Cache.make_key("parse", {"text": "x"})  # sig vide
        self.assertNotEqual(k1, k2)
        self.assertNotEqual(k1, k3)
        self.assertEqual(k1, cache.Cache.make_key("parse", {"text": "x"},
                                                   sig="aaa"))  # stable
        # et la persistance respecte l'empreinte : une instance au
        # code « bbb » ne voit pas l'entrée écrite au code « aaa »
        self.c.put(k1, {"ok": True, "n": 1})
        self.assertIsNone(self.c.get(k2))
        self.assertEqual(self.c.get(k1), {"ok": True, "n": 1})

    def test_code_signature(self):
        sig = cache.code_signature()
        self.assertTrue(sig)
        # stable (même contenu → même empreinte)
        self.assertEqual(sig, cache.code_signature())
        # sensible au contenu d'un fichier du paquet
        import cwm_lab
        pkg = os.path.dirname(os.path.abspath(cwm_lab.__file__))
        cible = os.path.join(pkg, "exercises", "README.md")
        try:
            with open(cible, "rb") as f:
                original = f.read()
            with open(cible, "ab") as f:
                f.write(b"# test\n")
            self.assertNotEqual(sig, cache.code_signature())
        finally:
            with open(cible, "wb") as f:
                f.write(original)
        self.assertEqual(sig, cache.code_signature())
        # dossier introuvable → "" (le cache reste fonctionnel)
        self.assertEqual(cache.code_signature("/chemin/introuvable"), "")

    def test_persistance_disque(self):
        """Un nouveau Cache (mémoire vide) retrouve la donnée sur disque."""
        k = cache.Cache.make_key("infer", {"kb": "x"})
        self.c.put(k, {"ok": True, "n": 42})
        c2 = cache.Cache(self.cfg, clock=lambda: self.now[0])
        self.assertEqual(c2.get(k), {"ok": True, "n": 42})

    def test_ttl_memoire(self):
        k = cache.Cache.make_key("parse", {"text": "x"})
        self.c.put(k, {"ok": True})
        self.now[0] += 301  # > ttl_memory (300 s)
        # plus en mémoire, mais encore sur disque (ttl_disk 7 j)
        self.assertEqual(self.c.get(k), {"ok": True})
        self.now[0] += 8 * 86400  # > ttl_disk
        self.assertIsNone(self.c.get(k))

    def test_eviction_memoire(self):
        """Éviction mémoire : k1 sort de la mémoire (mais reste sur
        disque, TTL disque 7 j) — l'observeur le vérifie directement
        sur la structure mémoire."""
        cfg = make_config(self.tmp, memory_entries=2)
        c = cache.Cache(cfg, clock=lambda: self.now[0])
        k1 = cache.Cache.make_key("a", {"i": 1})
        k2 = cache.Cache.make_key("a", {"i": 2})
        k3 = cache.Cache.make_key("a", {"i": 3})
        c.put(k1, {"n": 1})
        c.put(k2, {"n": 2})
        c.put(k3, {"n": 3})
        with c._lock:
            self.assertNotIn(k1, c._mem)   # sorti de la mémoire (LRU)
            self.assertIn(k2, c._mem)
            self.assertIn(k3, c._mem)
        # … mais toujours récupérable via le disque
        self.assertEqual(c.get(k1), {"n": 1})
        self.assertEqual(c.get(k2), {"n": 2})
        self.assertEqual(c.get(k3), {"n": 3})

    def test_eviction_disque_par_taille(self):
        """Le disque reste sous la taille maximale : le plus ancien
        (par mtime) est évicté, le récent reste."""
        cfg = make_config(self.tmp, max_disk_bytes=400)
        c = cache.Cache(cfg, clock=lambda: self.now[0])
        k1 = cache.Cache.make_key("a", {"i": 1})
        k2 = cache.Cache.make_key("a", {"i": 2})
        c.put(k1, {"payload": "x" * 200})
        self.now[0] += 5
        time.sleep(0.02)  # mtime réelle distincte (le LRU disque est par mtime)
        c.put(k2, {"payload": "y" * 200})
        # total > 400 octets : k1 (le plus ancien) est évicté du disque
        self.assertFalse(os.path.exists(c._disk_path(k1)))
        self.assertTrue(os.path.exists(c._disk_path(k2)))

    def test_fichier_corrompu_est_un_miss(self):
        k = cache.Cache.make_key("a", {"i": 1})
        self.c.put(k, {"ok": True})
        with open(self.c._disk_path(k), "w", encoding="utf-8") as f:
            f.write("{pas du json")
        self.assertIsNone(self.c._disk_get(k, self.now[0]))

    def test_cachable(self):
        self.assertTrue(cache.cachable({"ok": True}))
        self.assertFalse(cache.cachable({"ok": False, "errors": []}))
        self.assertFalse(cache.cachable({"ok": False, "timeout": True}))
        self.assertFalse(cache.cachable("pas un dict"))
        self.assertFalse(cache.cachable(None))

    def test_concurrence(self):
        """20 threads × put/get sur des clés distinctes : pas d'erreur."""
        errs = []

        def worker(n):
            try:
                for i in range(25):
                    k = cache.Cache.make_key("a", {"t": n, "i": i})
                    self.c.put(k, {"n": n, "i": i})
                    self.assertEqual(self.c.get(k), {"n": n, "i": i})
            except Exception as e:  # pragma: no cover
                errs.append(e)

        threads = [threading.Thread(target=worker, args=(n,))
                   for n in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errs, [])


class TestServerCache(unittest.TestCase):
    """Intégration : le serveur sert la 2e occurrence depuis le cache."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cwm-tp-srv.")
        self._old_cache = server.CACHE
        server.CACHE = cache.Cache(make_config(self.tmp))
        self.server = server.ThreadingHTTPServer(("127.0.0.1", 0),
                                                server.Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        server.CACHE = self._old_cache
        shutil.rmtree(self.tmp, ignore_errors=True)

    def post(self, path, payload):
        req = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (self.port, path),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_parse_deux_fois(self):
        payload = {"text": "@prefix : <http://example.org/> .\n"
                           ":a :b :c .", "language": "n3"}
        r1 = self.post("/api/parse", payload)
        self.assertTrue(r1["ok"])
        self.assertFalse(r1["cached"])
        r2 = self.post("/api/parse", payload)
        self.assertTrue(r2["cached"])
        self.assertEqual(r1["stats"], r2["stats"])

    def test_payload_different_n_est_pas_cache(self):
        p1 = {"text": ":a :b :c .", "language": "n3"}
        p2 = {"text": ":a :b :d .", "language": "n3"}
        self.post("/api/parse", p1)
        r2 = self.post("/api/parse", p2)
        self.assertFalse(r2["cached"])

    def test_erreur_n_est_pas_cachee(self):
        bad = {"text": ":a :b", "language": "n3"}  # cassé
        r1 = self.post("/api/parse", bad)
        self.assertFalse(r1["ok"])
        self.assertFalse(r1["cached"])
        r2 = self.post("/api/parse", bad)
        self.assertFalse(r2["cached"])  # recalculé, jamais servi du cache

    def test_infer_deux_fois(self):
        payload = {
            "kb": "@prefix : <http://example.org/> .\n"
                  ":alice :parentOf :bob .\n",
            "rules": "@prefix : <http://example.org/> .\n"
                     "@prefix log: <http://www.w3.org/2000/10/swap/log#> .\n"
                     "@forAll :x , :y .\n"
                     "{ :x :parentOf :y . } log:implies "
                     "{ :y :childOf :x } .\n",
            "mode": "think", "timeout": 10.0,
        }
        r1 = self.post("/api/infer", payload)
        self.assertTrue(r1["ok"])
        self.assertFalse(r1["cached"])
        r2 = self.post("/api/infer", payload)
        self.assertTrue(r2["cached"])
        self.assertEqual(r1["new_facts"], r2["new_facts"])


if __name__ == "__main__":
    unittest.main()
