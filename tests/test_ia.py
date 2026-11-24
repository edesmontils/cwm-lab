"""Tests de cwm_lab.ia (P9 : remplissage de la base par IA générative).

Le réseau n'est JAMAIS touché : le transport de ``call_proxy`` est
injectable (``transport`` de ``generate`` / ``call_proxy``) ; les
tests de l'endpoint ``/api/ia/generate`` monkey-patchent
``ia._http_post``.

Lancer depuis la racine du dépôt :
    python3 -m unittest -v tests.test_ia
ou : make test
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
import unittest
import urllib.error
import urllib.request
from datetime import date, timedelta

from cwm_lab import cache, engine, ia, server

# KB valide de référence : l'exercice « recettes » (774 faits, 108
# entités, 0 sujet sans rdf:type, cohérent avec ses règles — vérifié
# en P5 ; les libellés bilingues P10.1 ajoutent les ontologies).
_RECETTES = engine.load_exercise("recettes")
KB_RECETTES = _RECETTES["kb"]
RULES_RECETTES = _RECETTES["rules"]
BASE_URI = _RECETTES.get("base_uri") or engine.DEFAULT_BASE_URI

#: Règles qui produisent log:false sur toute KB avec un parentOf.
RULES_INCOHERENTES = (
    "@prefix : <http://example.org/> .\n"
    "@prefix log: <http://www.w3.org/2000/10/swap/log#> .\n"
    "@forAll :x , :y .\n"
    "{ :x :parentOf :y . } log:implies { log:false log:false log:false } .\n"
)


def make_config(tmpdir, **over):
    """Config de test : IA activée (proxy fictif), cache temporaire."""
    cfg = dict(cache.DEFAULTS)
    cfg["cache_dir"] = os.path.join(tmpdir, "cache")
    cfg.update({
        "ia_url": "https://proxy.test/v1",
        "ia_model": "proxyiag/test",
        "ia_api_key": "sk-test",
    })
    cfg.update(over)
    return cfg


def ok_response(n3, note="note de test", tokens=1200):
    """Réponse proxy 200 : le modèle a répondu en JSON {"n3", "note"}."""
    return 200, json.dumps({
        "choices": [{"message": {"content": json.dumps(
                                   {"n3": n3, "note": note})},
                     "finish_reason": "stop"}],
        "usage": {"total_tokens": tokens},
    }, ensure_ascii=False)


class FakeTransport:
    """Transport injectable : file de réponses ``(code, corps)`` ;
    enregistre chaque appel (url, payload, clé)."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, payload, api_key, timeout):
        self.calls.append({"url": url, "payload": payload,
                           "api_key": api_key, "timeout": timeout})
        return self.responses.pop(0)


# ----------------------------------------------------------------------
# état (bouton du front)
# ----------------------------------------------------------------------

class TestIaStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cwm-tp-ia.")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_sans_config(self):
        s = ia.status({})
        self.assertFalse(s["enabled"])
        self.assertIn("IA_API_KEY", s["reason"])
        self.assertIn("IA_MODEL", s["reason"])

    def test_cle_sans_modele(self):
        s = ia.status({"ia_api_key": "sk", "ia_url": "https://p.test/v1"})
        self.assertFalse(s["enabled"])
        self.assertIn("IA_MODEL", s["reason"])

    def test_url_http_rejetee(self):
        # la clé ne doit jamais transiter en clair sur le réseau
        s = ia.status({"ia_api_key": "sk", "ia_model": "m",
                       "ia_url": "http://p.test/v1"})
        self.assertTrue(s["enabled"])
        self.assertIn("https", s["reason"])

    def test_url_http_locale_acceptee(self):
        s = ia.status({"ia_api_key": "sk", "ia_model": "m",
                       "ia_url": "http://127.0.0.1:9999/v1"})
        self.assertTrue(s["enabled"])
        self.assertIsNone(s["reason"])
        self.assertEqual(s["url"], "127.0.0.1:9999")

    def test_complete(self):
        s = ia.status(make_config(self.tmp), self.tmp)
        self.assertTrue(s["enabled"])
        self.assertEqual(s["model"], "proxyiag/test")
        self.assertEqual(s["url"], "proxy.test")
        self.assertEqual(s["quota"]["requests_left"], 30)
        self.assertEqual(s["quota"]["tokens_left"], 100000)

    def test_quota_epuise(self):
        cfg = make_config(self.tmp, ia_max_requests=1)
        ia.Quota(cfg, self.tmp).consume()
        s = ia.status(cfg, self.tmp)
        self.assertTrue(s["enabled"])
        self.assertIn("quota", s["reason"])
        self.assertEqual(s["quota"]["requests_left"], 0)


# ----------------------------------------------------------------------
# quota de séance
# ----------------------------------------------------------------------

class TestIaQuota(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cwm-tp-ia.")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_fraichement_disponible(self):
        q = ia.Quota(make_config(self.tmp), self.tmp)
        self.assertTrue(q.available()[0])
        self.assertEqual(q.usage()["requests"], 0)
        self.assertEqual(q.usage()["requests_left"], 30)

    def test_consume_et_plafond(self):
        cfg = make_config(self.tmp, ia_max_requests=2, ia_max_tokens=100)
        q = ia.Quota(cfg, self.tmp)
        q.consume(40)
        q.consume(40)
        ok, refus = q.available()
        self.assertFalse(ok)
        self.assertIn("requêtes", refus)
        self.assertEqual(q.usage()["tokens_left"], 20)

    def test_persistance_entre_instances(self):
        # un nouveau Quota (nouveau thread / redémarrage) relit le
        # compteur du jour — persisté avec le cache P8
        cfg = make_config(self.tmp, ia_max_requests=5)
        ia.Quota(cfg, self.tmp).consume(3)
        q2 = ia.Quota(cfg, self.tmp)
        self.assertEqual(q2.usage()["requests"], 1)
        self.assertEqual(q2.usage()["tokens"], 3)
        self.assertEqual(q2.usage()["requests_left"], 4)

    def test_reset_chaque_jour(self):
        cfg = make_config(self.tmp, ia_max_requests=1)
        q = ia.Quota(cfg, self.tmp)
        q.consume()
        self.assertFalse(q.available()[0])
        # le fichier porte la date d'hier → le compteur repart
        path = os.path.join(self.tmp, "ia_quota.json")
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        d["day"] = (date.today() - timedelta(days=1)).isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(d, f)
        self.assertTrue(ia.Quota(cfg, self.tmp).available()[0])

    def test_memoire_seule(self):
        # pas de répertoire de cache → compteur mémoire (dégradation)
        q = ia.Quota(make_config(self.tmp, ia_max_requests=2), None)
        q.consume()
        self.assertEqual(q.usage()["requests"], 1)
        self.assertEqual(q.usage()["requests_left"], 1)


# ----------------------------------------------------------------------
# extraction de la réponse du modèle
# ----------------------------------------------------------------------

class TestIaExtract(unittest.TestCase):
    def test_json_pur(self):
        n3, note = ia.extract_n3('{"n3": ":a :b :c .", "note": "un fait"}')
        self.assertEqual(n3, ":a :b :c .")
        self.assertEqual(note, "un fait")

    def test_json_entoure_de_texte(self):
        content = ("Voici le document :\n"
                   + json.dumps({"n3": ":a :b :c .", "note": "n"})
                   + "\nBonne séance.")
        n3, note = ia.extract_n3(content)
        self.assertEqual(n3, ":a :b :c .")
        self.assertEqual(note, "n")

    def test_fence_turtle(self):
        n3, note = ia.extract_n3("```turtle\n:a :b :c .\n```")
        self.assertEqual(n3, ":a :b :c .")
        self.assertEqual(note, "")

    def test_turtle_brut(self):
        n3, note = ia.extract_n3(
            "@prefix : <http://example.org/> .\n:a :b :c .")
        self.assertTrue(n3.startswith("@prefix"))
        self.assertEqual(note, "")


# ----------------------------------------------------------------------
# prompt
# ----------------------------------------------------------------------

class TestIaPrompt(unittest.TestCase):
    def test_exercice(self):
        msgs = ia.build_messages("Énoncé du test", RULES_RECETTES,
                                 BASE_URI, 40, 10, "recettes")
        self.assertEqual(msgs[0]["role"], "system")
        user = msgs[1]["content"]
        self.assertIn("Énoncé du test", user)
        self.assertIn("<domaine>", user)
        self.assertIn("<regles>", user)
        self.assertIn("40", user)
        self.assertIn("10", user)
        self.assertIn("DONNÉES SEULES", user)
        self.assertIn("log:implies", user)   # l'interdiction est explicite
        self.assertIn("JSON", user)

    def test_generique_sans_contexte(self):
        user = ia.build_messages("", "", "http://example.org/d.n3",
                                 20, 5)[1]["content"]
        self.assertIn("familial", user)
        self.assertNotIn("<domaine>", user)
        self.assertNotIn("<regles>", user)

    def test_feedback(self):
        user = ia.build_messages("", "", "http://example.org/d.n3",
                                 20, 5,
                                 feedback=["- parse : erreur de syntaxe"])
        user = user[1]["content"]
        self.assertIn("rejet_precedent", user)
        self.assertIn("parse : erreur de syntaxe", user)

    def test_note_dans_la_langue_de_l_app(self):
        """La note du modèle (seul texte naturel de la réponse,
        affichée à l'étudiant) est demandée dans la langue de
        l'app — le reste du prompt reste en français (calibré)."""
        msgs_fr = ia.build_messages("e", "", "http://example.org/d.n3",
                                    20, 5)
        self.assertIn("Tu réponds en français.", msgs_fr[0]["content"])
        self.assertNotIn("in English", msgs_fr[1]["content"])
        msgs_en = ia.build_messages("e", "", "http://example.org/d.n3",
                                    20, 5, lang="en")
        self.assertIn("You respond in English.", msgs_en[0]["content"])
        self.assertIn("written in English", msgs_en[1]["content"])
        # langue inconnue → repli français
        msgs_xx = ia.build_messages("e", "", "http://example.org/d.n3",
                                    20, 5, lang="xx")
        self.assertIn("Tu réponds en français.", msgs_xx[0]["content"])

    def test_prompt_fichiers_present(self):
        """Les textes du prompt sont dans cwm_lab/prompts/ (fichiers
        affinables à la main, embarqués dans le wheel)."""
        for name in ("system.txt", "user.txt", "rules_constraint.txt",
                     "json_fr.txt", "json_en.txt", "generic_domain.txt",
                     "feedback.txt"):
            self.assertTrue((ia.PROMPTS_DIR / name).is_file(), name)

    def test_prompt_retouche_effective_sans_redemarrage(self):
        """Une retouche d'un fichier de prompt est visible à la
        génération suivante, sans recharger le module (re-lecture au
        changement de mtime/size)."""
        import pathlib
        old_dir, old_cache = ia.PROMPTS_DIR, ia._PROMPT_CACHE
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmpdir = pathlib.Path(tmp)
                for f in old_dir.glob("*.txt"):
                    shutil.copy(f, tmpdir)
                ia.PROMPTS_DIR = tmpdir
                ia._PROMPT_CACHE.clear()
                user0 = ia.build_messages("e", "", "http://example.org/d.n3",
                                          20, 5)[1]["content"]
                self.assertNotIn("MARQUEUR_RETOUCHE_TEST", user0)
                p = tmpdir / "user.txt"
                p.write_text(p.read_text(encoding="utf-8")
                             + "\nMARQUEUR_RETOUCHE_TEST",
                             encoding="utf-8")
                os.utime(p, (p.stat().st_atime, p.stat().st_mtime + 5))
                user1 = ia.build_messages("e", "", "http://example.org/d.n3",
                                          20, 5)[1]["content"]
                self.assertIn("MARQUEUR_RETOUCHE_TEST", user1)
        finally:
            ia.PROMPTS_DIR, ia._PROMPT_CACHE = old_dir, old_cache

    def test_prompt_fichier_introuvable_repli(self):
        """Fichier de prompt supprimé à la main → repli sur les
        textes d'origine en dur : la génération ne casse pas."""
        import pathlib
        old_dir, old_cache = ia.PROMPTS_DIR, ia._PROMPT_CACHE
        try:
            with tempfile.TemporaryDirectory() as tmp:
                ia.PROMPTS_DIR = pathlib.Path(tmp)   # vide
                ia._PROMPT_CACHE.clear()
                msgs = ia.build_messages("e", RULES_RECETTES,
                                         "http://example.org/d.n3",
                                         20, 5)
                user = msgs[1]["content"]
                self.assertIn("DONNÉES SEULES", user)
                self.assertIn("Tu réponds en français.",
                              msgs[0]["content"])
                self.assertIn("<domaine>", user)
                self.assertIn("<regles>", user)
        finally:
            ia.PROMPTS_DIR, ia._PROMPT_CACHE = old_dir, old_cache


# ----------------------------------------------------------------------
# contrôles a posteriori
# ----------------------------------------------------------------------

class TestIaControls(unittest.TestCase):
    def test_parse_ok(self):
        c = ia.control_parse(KB_RECETTES, BASE_URI)
        self.assertTrue(c["ok"], c)
        self.assertEqual(c["statements"], 774)
        self.assertEqual(c["rules_detected"], 0)

    def test_parse_erreur(self):
        c = ia.control_parse(":a :b . log:implies", BASE_URI)
        self.assertFalse(c["ok"])
        self.assertIn("syntaxe", c["error"])

    def test_parse_regles_rejetees(self):
        # données seules exigées : un log:implies est un rejet
        doc = ("@prefix : <http://example.org/> .\n"
               "@prefix log: <http://www.w3.org/2000/10/swap/log#> .\n"
               "@forAll :x , :y .\n"
               "{ :x :p :y } log:implies { :x :q :y } .\n")
        c = ia.control_parse(doc, BASE_URI)
        self.assertFalse(c["ok"])
        self.assertIn("règle", c["error"])

    def test_cohérence_ok(self):
        c = ia.control_coherence(KB_RECETTES, RULES_RECETTES, BASE_URI)
        self.assertTrue(c["ok"], c)
        self.assertGreater(c["new_facts"], 0)

    def test_cohérence_incoherente(self):
        kb = "@prefix : <http://example.org/> .\n:alice :parentOf :bob .\n"
        c = ia.control_coherence(kb, RULES_INCOHERENTES, BASE_URI)
        self.assertFalse(c["ok"])
        self.assertIn("incohérentes", c["error"])

    def test_cohérence_sans_regles(self):
        c = ia.control_coherence(KB_RECETTES, "", BASE_URI)
        self.assertTrue(c["ok"])
        self.assertIn("skipped", c)

    def test_plausibilite_ok(self):
        c = ia.control_plausibilite(KB_RECETTES, BASE_URI, 600, 100)
        self.assertTrue(c["ok"], c)
        self.assertEqual(c["facts"], 774)
        self.assertEqual(c["entities"], 108)
        self.assertEqual(c["untyped_subjects"], 0)

    def test_plausibilite_trop_peu_faits(self):
        c = ia.control_plausibilite(KB_RECETTES, BASE_URI, 2000, 100)
        self.assertFalse(c["ok"])
        self.assertIn("faits", c["error"])

    def test_plausibilite_trop_faits(self):
        # tolérance haute ×3 : 2 faits demandés → 6 max
        kb = ("@prefix : <http://example.org/> .\n"
              ":a a :X .\n:b a :X .\n:c a :X .\n"
              ":d a :X .\n:e a :X .\n:f a :X .\n"
              ":g a :X .\n")
        c = ia.control_plausibilite(kb, BASE_URI, 2, 8)
        self.assertFalse(c["ok"])
        self.assertIn("faits", c["error"])

    def test_plausibilite_sujet_sans_type(self):
        kb = "@prefix : <http://example.org/> .\n:a :p :b .\n"
        c = ia.control_plausibilite(kb, BASE_URI, 1, 2)
        self.assertFalse(c["ok"])
        self.assertIn("rdf:type", c["error"])


# ----------------------------------------------------------------------
# génération (pipeline + régénération bornée + quota)
# ----------------------------------------------------------------------

class TestIaGenerate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cwm-tp-ia.")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_sans_config(self):
        t = FakeTransport([])
        r = ia.generate({}, transport=t)
        self.assertFalse(r["ok"])
        self.assertIn("non configurée", r["error"])
        self.assertEqual(len(t.calls), 0)

    def test_succes_premiere_tentative(self):
        t = FakeTransport([ok_response(KB_RECETTES, "9 recettes, 5 patients")])
        r = ia.generate(make_config(self.tmp), enonce="Énoncé test",
                        rules=RULES_RECETTES, base_uri=BASE_URI,
                        n_facts=600, n_entities=100, transport=t,
                        cache_dir=self.tmp)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["n3"], KB_RECETTES.strip())
        self.assertEqual(r["note"], "9 recettes, 5 patients")
        self.assertEqual(r["attempts"], 1)
        self.assertEqual(r["tokens"], 1200)
        self.assertTrue(all(c["ok"] for c in r["controls"]))
        # le quota a été consommé (persisté avec le cache)
        q = ia.Quota(make_config(self.tmp), self.tmp)
        self.assertEqual(q.usage()["requests"], 1)
        self.assertEqual(q.usage()["tokens"], 1200)
        # l'appel au proxy : URL, clé, modèle
        self.assertEqual(t.calls[0]["url"], "https://proxy.test/v1/chat/completions")
        self.assertEqual(t.calls[0]["api_key"], "sk-test")
        self.assertEqual(t.calls[0]["payload"]["model"], "proxyiag/test")

    def test_lang_transmise_au_prompt(self):
        """``generate(lang=…)`` → la note est demandée dans la langue
        de l'app (messages du proxy inspectés)."""
        t = FakeTransport([ok_response(KB_RECETTES)])
        ia.generate(make_config(self.tmp), rules=RULES_RECETTES,
                    base_uri=BASE_URI, n_facts=600, n_entities=100,
                    transport=t, lang="en")
        msgs = t.calls[0]["payload"]["messages"]
        self.assertIn("You respond in English.", msgs[0]["content"])
        self.assertIn("written in English", msgs[1]["content"])
        # et le repli français sans lang
        t2 = FakeTransport([ok_response(KB_RECETTES)])
        ia.generate(make_config(self.tmp), rules=RULES_RECETTES,
                    base_uri=BASE_URI, n_facts=600, n_entities=100,
                    transport=t2)
        msgs2 = t2.calls[0]["payload"]["messages"]
        self.assertIn("Tu réponds en français.", msgs2[0]["content"])
        self.assertIn("en français", msgs2[1]["content"])

    def test_rejet_syntaxe_puis_succes(self):
        t = FakeTransport([
            ok_response(":a :b . log:implies"),  # syntaxe invalide
            ok_response(KB_RECETTES),
        ])
        r = ia.generate(make_config(self.tmp), rules=RULES_RECETTES,
                        base_uri=BASE_URI, n_facts=600, n_entities=100,
                        transport=t)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["attempts"], 2)
        # le 2e prompt contient le rejet précédent (régénération)
        user2 = t.calls[1]["payload"]["messages"][1]["content"]
        self.assertIn("rejet_precedent", user2)
        self.assertIn("parse", user2)

    def test_rejet_incoherence(self):
        kb = "@prefix : <http://example.org/> .\n:alice :parentOf :bob .\n"
        t = FakeTransport([ok_response(kb)] * 3)
        r = ia.generate(make_config(self.tmp), rules=RULES_INCOHERENTES,
                        base_uri=BASE_URI, n_facts=1, n_entities=2,
                        transport=t)
        self.assertFalse(r["ok"])
        self.assertEqual(r["attempts"], 3)
        self.assertIn("refusée", r["error"])
        self.assertFalse(r["controls"][1]["ok"])  # cohérence

    def test_rejet_regles_injectees(self):
        # le modèle a glissé une règle : données seules exigées
        doc = ("@prefix : <http://example.org/> .\n"
               "@prefix log: <http://www.w3.org/2000/10/swap/log#> .\n"
               ":alice a :Person .\n"
               ":alice :parentOf :bob .\n"
               "@forAll :x , :y .\n"
               "{ :x :p :y } log:implies { :x :q :y } .\n")
        t = FakeTransport([ok_response(doc)] * 3)
        r = ia.generate(make_config(self.tmp), base_uri=BASE_URI,
                        n_facts=2, n_entities=3, transport=t)
        self.assertFalse(r["ok"])
        self.assertFalse(r["controls"][0]["ok"])  # parse
        self.assertIn("règle", r["controls"][0]["error"])

    def test_rejet_plausibilite(self):
        kb = ("@prefix : <http://example.org/> .\n"
              ":alice a :Person .\n"
              ":alice :parentOf :bob .\n")
        t = FakeTransport([ok_response(kb)] * 3)
        r = ia.generate(make_config(self.tmp), base_uri=BASE_URI,
                        n_facts=100, n_entities=2, transport=t)
        self.assertFalse(r["ok"])
        self.assertFalse(r["controls"][2]["ok"])  # plausibilité
        self.assertIn("faits", r["controls"][2]["error"])

    def test_quota_epuise(self):
        # cache_dir : le quota est persisté (sinon compteur mémoire
        # par instance de generate — pas de partage entre appels)
        cfg = make_config(self.tmp, ia_max_requests=1)
        t = FakeTransport([ok_response(KB_RECETTES)] * 2)
        r1 = ia.generate(cfg, rules=RULES_RECETTES, base_uri=BASE_URI,
                         n_facts=600, n_entities=100, transport=t,
                         cache_dir=self.tmp)
        self.assertTrue(r1["ok"], r1)
        r2 = ia.generate(cfg, rules=RULES_RECETTES, base_uri=BASE_URI,
                         n_facts=600, n_entities=100, transport=t,
                         cache_dir=self.tmp)
        self.assertFalse(r2["ok"])
        self.assertEqual(r2["status"], 429)
        self.assertIn("quota", r2["error"])
        self.assertEqual(len(t.calls), 1)  # la 2e n'appelle pas le proxy

    def test_proxy_429(self):
        t = FakeTransport([(429, '{"error": "quota proxy"}')])
        r = ia.generate(make_config(self.tmp), transport=t)
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], 429)
        self.assertEqual(len(t.calls), 1)  # pas de régénération

    def test_proxy_500(self):
        t = FakeTransport([(500, "boom")])
        r = ia.generate(make_config(self.tmp), transport=t)
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], 503)

    def test_reponse_tronquee(self):
        # finish_reason "length" : le modèle n'a pas fini — refus,
        # pas de régénération (le problème est la taille demandée)
        body = json.dumps({"choices": [
            {"message": {"content": ":a :b :c ."},
             "finish_reason": "length"}]})
        t = FakeTransport([(200, body)])
        r = ia.generate(make_config(self.tmp), transport=t)
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], 502)
        self.assertEqual(len(t.calls), 1)


# ----------------------------------------------------------------------
# intégration serveur (endpoints /api/ia/*, proxy fictif)
# ----------------------------------------------------------------------

class TestServerIa(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cwm-tp-ia-srv.")
        self._old_config = server.CONFIG
        self._old_cache = server.CACHE
        self._old_post = ia._http_post
        server.CONFIG = make_config(self.tmp)
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
        self.thread.join()
        server.CONFIG = self._old_config
        server.CACHE = self._old_cache
        ia._http_post = self._old_post
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _get(self, path):
        with urllib.request.urlopen(
                "http://127.0.0.1:%d%s" % (self.port, path)) as r:
            return r.status, json.loads(r.read().decode("utf-8"))

    def _post(self, path, body):
        req = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (self.port, path),
            data=json.dumps(body).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_status_active(self):
        code, s = self._get("/api/ia/status")
        self.assertEqual(code, 200)
        self.assertTrue(s["enabled"])
        self.assertEqual(s["quota"]["requests_left"], 30)

    def test_status_sans_config(self):
        server.CONFIG = {}
        code, s = self._get("/api/ia/status")
        self.assertEqual(code, 200)
        self.assertFalse(s["enabled"])
        self.assertIn("IA_API_KEY", s["reason"])

    def test_generate_faux_proxy(self):
        ia._http_post = lambda url, payload, key, timeout: \
            ok_response(KB_RECETTES)
        code, r = self._post("/api/ia/generate", {
            "enonce": "Énoncé", "rules": RULES_RECETTES,
            "base_uri": BASE_URI, "facts": 600, "entities": 100})
        self.assertEqual(code, 200)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["n3"], KB_RECETTES.strip())
        self.assertTrue(all(c["ok"] for c in r["controls"]))

    def test_generate_quota_429(self):
        server.CONFIG = make_config(self.tmp, ia_max_requests=1)
        ia._http_post = lambda url, payload, key, timeout: \
            ok_response(KB_RECETTES)
        body = {"rules": RULES_RECETTES, "base_uri": BASE_URI,
                "facts": 600, "entities": 100}
        code1, r1 = self._post("/api/ia/generate", body)
        self.assertEqual(code1, 200)
        self.assertTrue(r1["ok"], r1)
        code2, r2 = self._post("/api/ia/generate", body)
        self.assertEqual(code2, 429)
        self.assertIn("quota", r2["error"])

    def test_generate_body_invalide(self):
        req = urllib.request.Request(
            "http://127.0.0.1:%d/api/ia/generate" % self.port,
            data=b"pas du json", method="POST",
            headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)

    def test_status_lang_en(self):
        server.CONFIG = {}
        code, s = self._get("/api/ia/status?lang=en")
        self.assertEqual(code, 200)
        self.assertFalse(s["enabled"])
        self.assertIn("not configured", s["reason"])

    def test_status_lang_invalide_repli_fr(self):
        server.CONFIG = {}
        code, s = self._get("/api/ia/status?lang=xx")
        self.assertEqual(code, 200)
        self.assertIn("non configurée", s["reason"])

    def test_generate_lang_en(self):
        server.CONFIG = {}
        code, r = self._post("/api/ia/generate",
                             {"enonce": "x", "lang": "en"})
        self.assertEqual(code, 200)
        self.assertFalse(r["ok"])
        self.assertIn("not configured", r["error"])

    def test_generate_lang_invalide_repli_fr(self):
        server.CONFIG = {}
        code, r = self._post("/api/ia/generate",
                             {"enonce": "x", "lang": "zz"})
        self.assertEqual(code, 200)
        self.assertIn("non configurée", r["error"])


# ----------------------------------------------------------------------
# i18n : messages localisés (fr par défaut, en à la demande)
# ----------------------------------------------------------------------

class TestIaI18n(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cwm-tp-ia-i18n.")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_langs(self):
        self.assertEqual(ia.LANGS, ("fr", "en"))

    def test_msg_repli(self):
        # langue inconnue → fr ; clé absente → la clé elle-même
        self.assertIn("quota", ia._msg("zz", "quota_requests", 30))
        self.assertEqual(ia._msg("fr", "cl_absente"), "cl_absente")

    def test_quota_dispo_fr_et_en(self):
        cfg = make_config(self.tmp, ia_max_requests=1)
        q = ia.Quota(cfg, self.tmp)
        q.consume()
        _, refus_fr = q.available("fr")
        _, refus_en = q.available("en")
        self.assertIn("requêtes", refus_fr)
        self.assertIn("request quota", refus_en)

    def test_status_lang(self):
        s_fr = ia.status({}, lang="fr")
        s_en = ia.status({}, lang="en")
        self.assertIn("non configurée", s_fr["reason"])
        self.assertIn("not configured", s_en["reason"])
        # l'URL http est refusée (clé jamais en clair) — dans les deux
        # langues
        cfg = {"ia_api_key": "sk", "ia_model": "m",
               "ia_url": "http://p.test/v1"}
        self.assertIn("https", ia.status(cfg, lang="fr")["reason"])
        self.assertIn("https", ia.status(cfg, lang="en")["reason"])

    def test_proxy_erreurs_lang(self):
        cfg = make_config(self.tmp)
        for code, corps, fr, en in (
                (0, "", "injoignable", "unreachable"),
                (429, "{}", "limite du jour", "daily limit"),
                (500, "boom", "indisponible", "unavailable"),
                (403, "{}", "refusé", "refused"),
        ):
            r_fr = ia.generate(cfg, transport=FakeTransport([(code, corps)]),
                               lang="fr")
            self.assertIn(fr, r_fr["error"], r_fr)
            r_en = ia.generate(cfg, transport=FakeTransport([(code, corps)]),
                               lang="en")
            self.assertIn(en, r_en["error"], r_en)

    def test_proxy_reponse_tronquee_en(self):
        body = json.dumps({"choices": [
            {"message": {"content": ":a :b :c ."},
             "finish_reason": "length"}]})
        t = FakeTransport([(200, body)])
        r = ia.generate(make_config(self.tmp), transport=t, lang="en")
        self.assertFalse(r["ok"])
        self.assertIn("out of tokens", r["error"])

    def test_contrôles_lang(self):
        # parse : syntaxe invalide
        c_fr = ia.control_parse(":a :b . log:implies", BASE_URI, "fr")
        c_en = ia.control_parse(":a :b . log:implies", BASE_URI, "en")
        self.assertIn("syntaxe N3 invalide", c_fr["error"])
        self.assertIn("invalid N3 syntax", c_en["error"])
        # parse : règle injectée
        doc = ("@prefix : <http://example.org/> .\n"
               "@prefix log: <http://www.w3.org/2000/10/swap/log#> .\n"
               "@forAll :x , :y .\n"
               "{ :x :p :y } log:implies { :x :q :y } .\n")
        self.assertIn("règle", ia.control_parse(doc, BASE_URI, "fr")["error"])
        self.assertIn("rule statement",
                      ia.control_parse(doc, BASE_URI, "en")["error"])
        # cohérence : incohérente
        kb = "@prefix : <http://example.org/> .\n:alice :parentOf :bob .\n"
        self.assertIn("incohérentes",
                      ia.control_coherence(kb, RULES_INCOHERENTES,
                                           BASE_URI, lang="fr")["error"])
        self.assertIn("inconsistent",
                      ia.control_coherence(kb, RULES_INCOHERENTES,
                                           BASE_URI, lang="en")["error"])
        # cohérence : skip
        self.assertIn("aucune règle",
                      ia.control_coherence(kb, "", BASE_URI,
                                           lang="fr")["skipped"])
        self.assertIn("no existing rule",
                      ia.control_coherence(kb, "", BASE_URI,
                                           lang="en")["skipped"])
        # plausibilité
        self.assertIn("faits (plage demandée",
                      ia.control_plausibilite(KB_RECETTES, BASE_URI,
                                              2000, 100, "fr")["error"])
        self.assertIn("facts (requested range",
                      ia.control_plausibilite(KB_RECETTES, BASE_URI,
                                              2000, 100, "en")["error"])
        self.assertIn("sans rdf:type",
                      ia.control_plausibilite(
                          "@prefix : <http://example.org/> .\n"
                          ":a :p :b .\n", BASE_URI, 1, 2, "fr")["error"])
        self.assertIn("without rdf:type",
                      ia.control_plausibilite(
                          "@prefix : <http://example.org/> .\n"
                          ":a :p :b .\n", BASE_URI, 1, 2, "en")["error"])

    def test_generation_refusee_en(self):
        kb = "@prefix : <http://example.org/> .\n:alice :parentOf :bob .\n"
        t = FakeTransport([ok_response(kb)] * 3)
        r = ia.generate(make_config(self.tmp), rules=RULES_INCOHERENTES,
                        base_uri=BASE_URI, n_facts=1, n_entities=2,
                        transport=t, lang="en")
        self.assertFalse(r["ok"])
        self.assertIn("refused", r["error"])
        # l'erreur du contrôle cohérence est aussi en anglais
        self.assertIn("inconsistent", r["controls"][1]["error"])
        # le prompt reste en français (calibré) : même avec lang=en
        user = t.calls[0]["payload"]["messages"][1]["content"]
        self.assertIn("DONNÉES SEULES", user)
