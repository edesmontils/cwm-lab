"""Tests de cwm_lab.engine (P0 : parse, P1 : serialize, P2 : infer,
P3 : query).

Lancer depuis la racine du dépôt :
    python3 -m unittest -v tests.test_engine
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

import unittest

from cwm_lab import engine


class TestParseValid(unittest.TestCase):
    def test_document_famille(self):
        doc = (
            "@prefix : <http://example.org/> .\n"
            "@prefix log: <http://www.w3.org/2000/10/swap/log#> .\n"
            ":alice a :Person .\n"
            ":bob   a :Person .\n"
            ":alice :parentOf :bob .\n"
            "@forAll :x , :y , :z .\n"
            "{ :x :parentOf :y . :y :parentOf :z . } log:implies { :x :grandparentOf :z } .\n"
        )
        r = engine.parse(doc)
        self.assertTrue(r["ok"])
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["stats"]["statements"], 4)  # 3 faits + 1 règle
        self.assertEqual(r["stats"]["rules"], 1)
        self.assertEqual(r["stats"]["blankNodes"], 0)

    def test_document_sans_regles(self):
        doc = "@prefix : <http://example.org/> .\n:alice a :Person .\n"
        r = engine.parse(doc)
        self.assertTrue(r["ok"])
        self.assertEqual(r["stats"]["statements"], 1)
        self.assertEqual(r["stats"]["rules"], 0)
        self.assertEqual(r["stats"]["blankNodes"], 0)

    def test_document_vide(self):
        r = engine.parse("")
        self.assertTrue(r["ok"])
        self.assertEqual(r["stats"]["statements"], 0)
        self.assertEqual(r["stats"]["rules"], 0)
        self.assertEqual(r["stats"]["blankNodes"], 0)

    def test_commentaires_seuls(self):
        r = engine.parse("# juste un commentaire\n# et un autre\n")
        self.assertTrue(r["ok"])
        self.assertEqual(r["stats"]["statements"], 0)

    def test_noeuds_vides(self):
        doc = (
            "@prefix : <http://example.org/> .\n"
            ":alice :knows [ :name \"bob\" ] .\n"
            ":alice :knows _:x .\n"
        )
        r = engine.parse(doc)
        self.assertTrue(r["ok"])
        # 3 énoncés au top level : les 2 faits + le triple propre au
        # nœud vide [ :name "bob" ] (le parser l'ajoute au document).
        self.assertEqual(r["stats"]["statements"], 3)
        self.assertEqual(r["stats"]["blankNodes"], 2)

    def test_noeud_vide_dans_regle(self):
        doc = (
            "@prefix : <http://example.org/> .\n"
            "@prefix log: <http://www.w3.org/2000/10/swap/log#> .\n"
            "@forAll :x .\n"
            "{ :x :p [ :r :x ] . } log:implies { :x :q :x } .\n"
        )
        r = engine.parse(doc)
        self.assertTrue(r["ok"])
        self.assertEqual(r["stats"]["rules"], 1)
        self.assertEqual(r["stats"]["blankNodes"], 1)  # bnode dans le corps

    def test_unice(self):
        doc = "@prefix : <http://example.org/> .\n:élie :prénom \"Zoë\" .\n"
        r = engine.parse(doc)
        self.assertTrue(r["ok"])
        self.assertEqual(r["stats"]["statements"], 1)


class TestParseErreur(unittest.TestCase):
    def test_point_manquant(self):
        doc = (
            "@prefix : <http://example.org/> .\n"
            ":alice a :Person\n"          # manque le point
            ":bob a :Person .\n"
        )
        r = engine.parse(doc)
        self.assertFalse(r["ok"])
        self.assertIsNone(r["stats"])
        self.assertEqual(len(r["errors"]), 1)
        er = r["errors"][0]
        self.assertIn("line", er)
        self.assertIn("column", er)
        self.assertTrue(er["message"])
        # L'erreur pointe bien vers la zone concernée (ligne 3 ou 4).
        self.assertIn(er["line"], (3, 4))

    def test_syntaxe_bang_rejetee(self):
        # La syntaxe !{…} -> {…} n'est PAS supportée par le parser CWM ;
        # le TP enseigne { … } log:implies { … } .
        doc = (
            "@prefix : <http://example.org/> .\n"
            "!{ :x :p :y . } -> { :x :q :y } .\n"
        )
        r = engine.parse(doc)
        self.assertFalse(r["ok"])
        self.assertEqual(r["errors"][0]["line"], 2)

    def test_babillage_ne_leve_pas(self):
        # Toute entrée doit rester gérable (pas d'exception au serveur).
        for garbage in ("<<<>>>", "a b c", "@bogus", ":", "<>", '"non terminé'):
            r = engine.parse(garbage)
            self.assertIsInstance(r, dict, garbage)
            self.assertIn("ok", r)
            self.assertIn("errors", r)


FAMILLE = (
    "@prefix : <http://example.org/> .\n"
    "@prefix log: <http://www.w3.org/2000/10/swap/log#> .\n"
    ":alice a :Person .\n"
    ":bob   a :Person .\n"
    ":alice :parentOf :bob .\n"
    "@forAll :x , :y , :z .\n"
    "{ :x :parentOf :y . :y :parentOf :z . } log:implies { :x :grandparentOf :z } .\n"
)
PUR_RDF = (
    "@prefix : <http://example.org/> .\n"
    ":alice a :Person .\n"
    ":alice :name \"Zoë\" .\n"
)


class TestSerialize(unittest.TestCase):
    def test_export_n3_garde_les_regles(self):
        r = engine.serialize(FAMILLE, format="n3")
        self.assertTrue(r["ok"], r["errors"])
        out = r["output"]
        self.assertIn("implies", out)
        self.assertIn("@forAll", out)
        # Le round-trip re-parsé donne le même graphe (4 énoncés, 1 règle).
        rt = engine.parse(out)
        self.assertTrue(rt["ok"], rt["errors"])
        self.assertEqual(rt["stats"]["statements"], 4)
        self.assertEqual(rt["stats"]["rules"], 1)

    def test_export_n3_uris_absolues(self):
        r = engine.serialize(FAMILLE, format="n3")
        self.assertTrue(r["ok"], r["errors"])
        # flag r : pas de URI relative dans la sortie (une URI relative
        # s'écrirait « </… » ; les URIs absolues ne contiennent que « // »).
        self.assertNotIn("</", r["output"])
        self.assertIn("<http://example.org/alice>", r["output"])

    def test_export_turtle_pur(self):
        r = engine.serialize(PUR_RDF, format="turtle")
        self.assertTrue(r["ok"], r["errors"])
        out = r["output"]
        self.assertIn("http://example.org/alice", out)
        # Le round-trip re-parsé donne le même graphe.
        rt = engine.parse(out)
        self.assertTrue(rt["ok"], rt["errors"])
        self.assertEqual(rt["stats"]["statements"], 2)

    def test_export_turtle_refuse_les_regles(self):
        # Comme --turtle de cwm : le graphe n'est pas du RDF pur.
        r = engine.serialize(FAMILLE, format="turtle")
        self.assertFalse(r["ok"])
        self.assertIsNone(r["output"])
        self.assertIn("N3", r["errors"][0]["message"])

    def test_export_ntriples_pur(self):
        r = engine.serialize(PUR_RDF, format="ntriples")
        self.assertTrue(r["ok"], r["errors"])
        out = r["output"]
        # URIs absolues, un triple par ligne, pas de préfixe.
        self.assertIn("http://www.w3.org/1999/02/22-rdf-syntax-ns#type", out)
        self.assertNotIn("@prefix", out)
        rt = engine.parse(out)
        self.assertTrue(rt["ok"], rt["errors"])
        self.assertEqual(rt["stats"]["statements"], 2)

    def test_export_ntriples_refuse_les_regles(self):
        r = engine.serialize(FAMILLE, format="ntriples")
        self.assertFalse(r["ok"])
        self.assertIsNone(r["output"])

    def test_export_rdf_xml(self):
        r = engine.serialize(PUR_RDF, format="rdf")
        self.assertTrue(r["ok"], r["errors"])
        self.assertIn("<rdf:RDF", r["output"])
        self.assertIn("http://example.org", r["output"])

    def test_export_document_vide(self):
        for fmt in ("n3", "turtle", "ntriples", "rdf"):
            r = engine.serialize("", format=fmt)
            self.assertTrue(r["ok"], (fmt, r["errors"]))
            self.assertIsInstance(r["output"], str, fmt)

    def test_export_erreur_syntaxe(self):
        r = engine.serialize(":alice a .", format="n3")
        self.assertFalse(r["ok"])
        self.assertIsNone(r["output"])
        self.assertEqual(len(r["errors"]), 1)
        self.assertEqual(r["errors"][0]["line"], 1)

    def test_export_format_inconnu(self):
        r = engine.serialize(PUR_RDF, format="json")
        self.assertFalse(r["ok"])
        self.assertIn("format inconnu", r["errors"][0]["message"])


# ----------------------------------------------------------------------
# P2 — raisonnement
# ----------------------------------------------------------------------

KB_FAMILLE = (
    "@prefix : <http://example.org/> .\n"
    ":alice a :Person .\n"
    ":bob   a :Person .\n"
    ":carl  a :Person .\n"
    ":alice :parentOf :bob .\n"
    ":bob   :parentOf :carl .\n"
)

RULES_GRANDPARENT = (
    "@prefix : <http://example.org/> .\n"
    "@prefix log: <http://www.w3.org/2000/10/swap/log#> .\n"
    "@forAll :x , :y , :z .\n"
    "{ :x :parentOf :y . :y :parentOf :z . } log:implies { :x :grandparentOf :z } .\n"
)

# Système auto-alimentant (chaque fait en engendre un nouveau) : une
# passe en produit deux, la convergence est **infinie**.
RULES_INFINIES = (
    "@prefix : <http://example.org/> .\n"
    "@prefix log: <http://www.w3.org/2000/10/swap/log#> .\n"
    "@forAll :x , :y .\n"
    "{ :x :chain :y . } log:implies { :y :chain2 [] } .\n"
    "@forAll :x , :y .\n"
    "{ :x :chain2 :y . } log:implies { :y :chain [] } .\n"
)

KB_CHAINE = "@prefix : <http://example.org/> .\n:a :chain :b .\n"


class TestInfer(unittest.TestCase):
    def test_famille_nouveaux_faits(self):
        r = engine.infer(KB_FAMILLE, RULES_GRANDPARENT, mode="think")
        self.assertTrue(r["ok"], r["errors"])
        self.assertFalse(r["timeout"])
        self.assertFalse(r["inconsistent"])
        self.assertEqual(r["new_facts"], [[
            "http://example.org/alice", "http://example.org/grandparentOf",
            "http://example.org/carl",
        ]])
        # 5 données + 1 nouveau fait
        self.assertEqual(r["closure_statements"], 6)
        self.assertEqual(r["rules_in_closure"], 0)

    def test_mode_once(self):
        # Une seule passe sur un système auto-alimentant : exactement
        # deux faits nouveaux (la convergence en produirait à l'infini).
        r = engine.infer(KB_CHAINE, RULES_INFINIES, mode="once")
        self.assertTrue(r["ok"], r["errors"])
        self.assertFalse(r["timeout"])
        self.assertEqual(len(r["new_facts"]), 2)

    def test_timeout_regle_non_convergente(self):
        r = engine.infer(KB_CHAINE, RULES_INFINIES, mode="think", timeout=2)
        self.assertFalse(r["ok"])
        self.assertTrue(r["timeout"])
        self.assertIn("timeout", r["errors"][0]["message"])
        self.assertLess(r["elapsed_ms"], 60_000)

    def test_incoherence(self):
        rules = (
            "@prefix : <http://example.org/> .\n"
            "@prefix log: <http://www.w3.org/2000/10/swap/log#> .\n"
            "@forAll :x , :y .\n"
            "{ :x :parentOf :y . } log:implies { log:false log:false log:false } .\n"
        )
        r = engine.infer(KB_FAMILLE, rules, mode="think")
        self.assertTrue(r["ok"], r["errors"])
        self.assertTrue(r["inconsistent"])
        # le triple constant log:false apparaît comme « nouveau fait »
        self.assertIn(
            [engine.LOG_FALSE_URI] * 3, r["new_facts"])

    def test_store_rules(self):
        r = engine.infer(KB_FAMILLE, RULES_GRANDPARENT, mode="think",
                         store_rules=True)
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(r["rules_in_closure"], 1)
        # l'énoncé-règle n'est PAS compté comme fait nouveau
        self.assertTrue(all(t[1] != engine.IMPLIES_URI for t in r["new_facts"]))

    def test_sans_regles(self):
        r = engine.infer(KB_FAMILLE, "", mode="think")
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(r["new_facts"], [])
        self.assertEqual(r["closure_statements"], 5)
        self.assertFalse(r["inconsistent"])

    def test_erreur_syntaxe_donnees(self):
        r = engine.infer(":alice a .", RULES_GRANDPARENT)
        self.assertFalse(r["ok"])
        self.assertEqual(r["errors"][0]["doc"], "kb")
        self.assertGreaterEqual(r["errors"][0]["line"], 1)

    def test_erreur_syntaxe_regles(self):
        r = engine.infer(KB_FAMILLE, ":pas de regle ici a . log:implies")
        self.assertFalse(r["ok"])
        self.assertEqual(r["errors"][0]["doc"], "rules")

    def test_mode_inconnu(self):
        r = engine.infer(KB_FAMILLE, RULES_GRANDPARENT, mode="xyz")
        self.assertFalse(r["ok"])
        self.assertIn("mode inconnu", r["errors"][0]["message"])


# ----------------------------------------------------------------------
# P3 — requêtes SPARQL
# ----------------------------------------------------------------------

QUERY_PERSONS = (
    "PREFIX : <http://example.org/>\n"
    "SELECT ?x\n"
    "WHERE { ?x a :Person . }\n"
)
QUERY_GRANDPARENT = (
    "PREFIX : <http://example.org/>\n"
    "SELECT ?s ?o\n"
    "WHERE { ?s :grandparentOf ?o . }\n"
)
QUERY_PARENTS = (
    "PREFIX : <http://example.org/>\n"
    "SELECT ?s ?o\n"
    "WHERE { ?s :parentOf ?o . }\n"
)
ASK_GRANDPARENT = (
    "PREFIX : <http://example.org/>\n"
    "ASK { :alice :grandparentOf :carl . }\n"
)


class TestQuerySelect(unittest.TestCase):
    def test_select_sans_raisonnement(self):
        r = engine.query(KB_FAMILLE, QUERY_PERSONS)
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(r["query_type"], "SelectQuery")
        self.assertEqual(r["variables"], ["x"])
        self.assertEqual(r["rows_raw"], [
            ["http://example.org/alice"],
            ["http://example.org/bob"],
            ["http://example.org/carl"],
        ])
        self.assertIsNone(r["rows_reasoned"])

    def test_select_ordre_variables(self):
        # L'ordre des colonnes suit la clause SELECT (pas l'ordre
        # interne du moteur).
        q = ("PREFIX : <http://example.org/>\n"
             "SELECT ?o ?s\n"
             "WHERE { ?s :parentOf ?o . }\n")
        r = engine.query(KB_FAMILLE, q)
        self.assertEqual(r["variables"], ["o", "s"])
        self.assertEqual(r["rows_raw"][0], [
            "http://example.org/bob", "http://example.org/alice"])

    def test_resultat_vide(self):
        q = ("PREFIX : <http://example.org/>\n"
             "SELECT ?x\n"
             "WHERE { ?x :inexistant ?y . }\n")
        r = engine.query(KB_FAMILLE, q)
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(r["rows_raw"], [])
        self.assertEqual(r["variables"], ["x"])


class TestQueryDiff(unittest.TestCase):
    def test_diff_avant_apres(self):
        # 0 ligne sur les données brutes, 1 ligne après raisonnement.
        r = engine.query(KB_FAMILLE, QUERY_GRANDPARENT, RULES_GRANDPARENT,
                         reason=True)
        self.assertTrue(r["ok"], r["errors"])
        self.assertFalse(r["timeout"])
        self.assertEqual(r["rows_raw"], [])
        self.assertEqual(r["rows_reasoned"], [
            ["http://example.org/alice", "http://example.org/carl"]])
        self.assertEqual(r["new_rows"], [
            ["http://example.org/alice", "http://example.org/carl"]])
        # 5 données + 1 nouveau fait
        self.assertEqual(r["closure_statements"], 6)

    def test_diff_sans_fausse_nouvelle(self):
        # Lignes déjà présentes avant raisonnement : aucune « nouvelle ».
        r = engine.query(KB_FAMILLE, QUERY_PARENTS, RULES_GRANDPARENT,
                         reason=True)
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(len(r["rows_raw"]), 2)
        self.assertEqual(r["rows_reasoned"], r["rows_raw"])
        self.assertEqual(r["new_rows"], [])

    def test_ask_avant_apres(self):
        r = engine.query(KB_FAMILLE, ASK_GRANDPARENT, RULES_GRANDPARENT,
                         reason=True)
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(r["query_type"], "AskQuery")
        self.assertFalse(r["ask_raw"])
        self.assertTrue(r["ask_reasoned"])


class TestQueryErreurs(unittest.TestCase):
    def test_erreur_syntaxe_requete_eof(self):
        r = engine.query(KB_FAMILLE, "PREFIX : <http://example.org/>\n"
                          "SELECT ?x WHERE {")
        self.assertFalse(r["ok"])
        self.assertEqual(r["errors"][0]["doc"], "query")
        self.assertIn("incomplète", r["errors"][0]["message"])

    def test_erreur_syntaxe_requete_token(self):
        r = engine.query(KB_FAMILLE, "PREFIX : <http://example.org/>\n"
                          "BLABLA ?x")
        self.assertFalse(r["ok"])
        self.assertEqual(r["errors"][0]["doc"], "query")
        self.assertIn("BLABLA", r["errors"][0]["message"])

    def test_requete_vide(self):
        r = engine.query(KB_FAMILLE, "   ")
        self.assertFalse(r["ok"])
        self.assertEqual(r["errors"][0]["message"], "requête vide")

    def test_construct_refuse(self):
        q = ("PREFIX : <http://example.org/>\n"
             "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o . }\n")
        r = engine.query(KB_FAMILLE, q)
        self.assertFalse(r["ok"])
        self.assertIn("SELECT et ASK", r["errors"][0]["message"])

    def test_erreur_syntaxe_donnees(self):
        r = engine.query(":alice a .", QUERY_PERSONS)
        self.assertFalse(r["ok"])
        self.assertEqual(r["errors"][0]["doc"], "kb")

    def test_erreur_syntaxe_regles(self):
        r = engine.query(KB_FAMILLE, QUERY_PERSONS,
                         ":pas de regle ici a . log:implies", reason=True)
        self.assertFalse(r["ok"])
        self.assertEqual(r["errors"][0]["doc"], "rules")
        # les résultats bruts restent renvoyés
        self.assertEqual(len(r["rows_raw"]), 3)

    def test_mode_inconnu(self):
        r = engine.query(KB_FAMILLE, QUERY_PERSONS, mode="xyz")
        self.assertFalse(r["ok"])
        self.assertIn("mode inconnu", r["errors"][0]["message"])


class TestQueryTimeout(unittest.TestCase):
    def test_timeout_avec_resultats_bruts(self):
        # Règle non convergente : timeout propre, résultats bruts
        # quand même renvoyés, pas de résultats après raisonnement.
        r = engine.query(KB_CHAINE,
                         "PREFIX : <http://example.org/>\n"
                         "SELECT ?x\n"
                         "WHERE { ?x :chain ?y . }\n",
                         RULES_INFINIES, reason=True, timeout=2)
        self.assertFalse(r["ok"])
        self.assertTrue(r["timeout"])
        self.assertIn("timeout", r["errors"][0]["message"])
        self.assertEqual(r["rows_raw"], [["http://example.org/a"]])
        self.assertIsNone(r["rows_reasoned"])
        self.assertLess(r["elapsed_ms"], 60_000)


class TestParseSparql(unittest.TestCase):
    def test_parse_select_valide(self):
        p = engine.parse(QUERY_PERSONS, language="sparql")
        self.assertTrue(p["ok"], p["errors"])
        self.assertEqual(p["stats"]["queryType"], "SelectQuery")
        self.assertEqual(p["stats"]["variables"], ["x"])

    def test_parse_ask_valide(self):
        p = engine.parse(ASK_GRANDPARENT, language="sparql")
        self.assertTrue(p["ok"], p["errors"])
        self.assertEqual(p["stats"]["queryType"], "AskQuery")
        self.assertEqual(p["stats"]["variables"], [])

    def test_parse_erreur(self):
        p = engine.parse("SELECT ?x WHERE {", language="sparql")
        self.assertFalse(p["ok"])
        self.assertGreaterEqual(p["errors"][0]["line"], 1)
        self.assertIn("incomplète", p["errors"][0]["message"])

    def test_parse_document_vide(self):
        p = engine.parse("", language="sparql")
        self.assertTrue(p["ok"], p["errors"])
        self.assertIsNone(p["stats"]["queryType"])

    def test_parse_langage_inconnu(self):
        p = engine.parse("x", language="foo")
        self.assertFalse(p["ok"])
        self.assertIn("langage inconnu", p["errors"][0]["message"])


# ----------------------------------------------------------------------
# P4 — validité & preuves
# ----------------------------------------------------------------------

CONCL_GRANDPARENT = (
    "@prefix : <http://example.org/> .\n"
    ":alice :grandparentOf :carl .\n"
)
CONCL_KO = (
    "@prefix : <http://example.org/> .\n"
    ":carl :grandparentOf :alice .\n"
)
CONCL_PARENT = (
    "@prefix : <http://example.org/> .\n"
    ":alice :parentOf :bob .\n"
)
RULES_INCOHERENTES = (
    "@prefix : <http://example.org/> .\n"
    "@prefix log: <http://www.w3.org/2000/10/swap/log#> .\n"
    "@forAll :x , :y .\n"
    "{ :x :parentOf :y . } log:implies { log:false log:false log:false } .\n"
)


class TestEntail(unittest.TestCase):
    def test_entrainement_oui(self):
        # Absent des données brutes, produit par la règle de
        # grand-parent : la clôture l'entraîne.
        r = engine.entail(KB_FAMILLE, RULES_GRANDPARENT, CONCL_GRANDPARENT)
        self.assertTrue(r["ok"], r["errors"])
        self.assertFalse(r["timeout"])
        self.assertTrue(r["entails"])
        self.assertFalse(r["inconsistent"])
        # 5 données + 1 nouveau fait
        self.assertEqual(r["closure_statements"], 6)

    def test_entrainement_non(self):
        # Le sens inverse n'est pas dérivable.
        r = engine.entail(KB_FAMILLE, RULES_GRANDPARENT, CONCL_KO)
        self.assertTrue(r["ok"], r["errors"])
        self.assertFalse(r["entails"])

    def test_entraiment_sans_regles(self):
        # Sans règle, le fait du grand-parent n'est pas dans la KB.
        r = engine.entail(KB_FAMILLE, "", CONCL_GRANDPARENT)
        self.assertTrue(r["ok"], r["errors"])
        self.assertFalse(r["entails"])

    def test_entraiment_fait_donne(self):
        # Un fait déjà présent dans les données est entraîné.
        r = engine.entail(KB_FAMILLE, "", CONCL_PARENT)
        self.assertTrue(r["ok"], r["errors"])
        self.assertTrue(r["entails"])

    def test_incoherence_explosion(self):
        # Clôture incohérente (log:false) : par explosion, TOUTE
        # conclusion est « entraînée » (même une absurde).
        r = engine.entail(KB_FAMILLE, RULES_INCOHERENTES, CONCL_KO)
        self.assertTrue(r["ok"], r["errors"])
        self.assertTrue(r["inconsistent"])
        self.assertTrue(r["entails"])

    def test_erreur_conclusion(self):
        r = engine.entail(KB_FAMILLE, RULES_GRANDPARENT, ":alice a .")
        self.assertFalse(r["ok"])
        self.assertEqual(r["errors"][0]["doc"], "concl")

    def test_conclusion_vide(self):
        r = engine.entail(KB_FAMILLE, RULES_GRANDPARENT, "  \n  ")
        self.assertFalse(r["ok"])
        self.assertEqual(r["errors"][0]["doc"], "concl")
        self.assertIn("conclusion vide", r["errors"][0]["message"])

    def test_erreur_donnees(self):
        r = engine.entail(":alice a .", RULES_GRANDPARENT, CONCL_GRANDPARENT)
        self.assertFalse(r["ok"])
        self.assertEqual(r["errors"][0]["doc"], "kb")

    def test_mode_inconnu(self):
        r = engine.entail(KB_FAMILLE, RULES_GRANDPARENT, CONCL_GRANDPARENT,
                          mode="xyz")
        self.assertFalse(r["ok"])
        self.assertIn("mode inconnu", r["errors"][0]["message"])


class TestProve(unittest.TestCase):
    def test_preuve_auto_contenue(self):
        r = engine.prove(KB_FAMILLE, RULES_GRANDPARENT, mode="think")
        self.assertTrue(r["ok"], r["errors"])
        proof = r["proof"]
        self.assertIsNotNone(proof)
        self.assertGreater(r["closure_statements"], 0)
        # C'est bien une preuve (namespace reason) et elle est
        # AUTO-CONTENUE : les sources sont des URIs data:, et il n'y a
        # aucune URI relative (donc check la re-vérifiera depuis n'importe
        # quel emplacement).
        self.assertIn("http://www.w3.org/2000/10/swap/reason#", proof)
        self.assertIn("data:text/rdf+n3", proof)
        import re
        self.assertEqual(re.findall(r"<(?!data:|http:|file:)[^>]*>", proof), [])

    def test_preuve_mode_once(self):
        r = engine.prove(KB_FAMILLE, RULES_GRANDPARENT, mode="once")
        self.assertTrue(r["ok"], r["errors"])
        self.assertIsNotNone(r["proof"])

    def test_preuve_sans_regles(self):
        r = engine.prove(KB_FAMILLE, "")
        self.assertTrue(r["ok"], r["errors"])
        self.assertIsNotNone(r["proof"])

    def test_preuve_erreur_syntaxe(self):
        r = engine.prove(":alice a .", RULES_GRANDPARENT)
        self.assertFalse(r["ok"])
        self.assertEqual(r["errors"][0]["doc"], "kb")

    def test_preuve_erreur_regles(self):
        r = engine.prove(KB_FAMILLE, ":pas de regle a . log:implies")
        self.assertFalse(r["ok"])
        self.assertEqual(r["errors"][0]["doc"], "rules")

    def test_preuve_timeout(self):
        r = engine.prove(KB_CHAINE, RULES_INFINIES, mode="think", timeout=2)
        self.assertFalse(r["ok"])
        self.assertTrue(r["timeout"])
        self.assertLess(r["elapsed_ms"], 60_000)


class TestCheckProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Une preuve générée une fois, réutilisée par les tests de
        # vérification (check_proof lance un subprocess par appel).
        r = engine.prove(KB_FAMILLE, RULES_GRANDPARENT, mode="think")
        cls.proof = r["proof"]

    def test_preuve_generale_valide(self):
        r = engine.check_proof(self.proof)
        self.assertTrue(r["ok"], r["errors"])
        self.assertTrue(r["valid"])
        self.assertGreater(len(r["steps"]), 0)
        self.assertIsNotNone(r["proved"])

    def test_etapes_report(self):
        r = engine.check_proof(self.proof)
        self.assertTrue(r["ok"], r["errors"])
        self.assertGreaterEqual(len(r["steps"]), 3)
        self.assertEqual(r["steps"][0]["no"], 1)
        for s in r["steps"]:
            self.assertIn("statement", s)
            self.assertIn("how", s)

    def test_preuve_alteree_rejetee(self):
        # Scénario clé : l'étudiant altère la preuve À LA MAIN (ici : un
        # prédicat de la conclusion, hors des sources data:). check rejoue
        # la dérivation et doit rejeter la preuve.
        bad = "\n".join(
            ln.replace("grandparentOf", "siblingOf")
            if "data:text" not in ln else ln
            for ln in self.proof.splitlines()
        )
        r = engine.check_proof(bad)
        self.assertTrue(r["ok"], r["errors"])
        self.assertFalse(r["valid"])
        self.assertTrue(r["reason"])

    def test_preuve_non_parseable(self):
        r = engine.check_proof("completement illisible [[[")
        self.assertFalse(r["ok"])
        self.assertIsNone(r["valid"])
        self.assertIn("N3", r["errors"][0]["message"])

    def test_preuve_vide(self):
        r = engine.check_proof("  \n ")
        self.assertFalse(r["ok"])
        self.assertIsNone(r["valid"])
        self.assertIn("preuve vide", r["errors"][0]["message"])


# ----------------------------------------------------------------------
# P5 — exercices (pack TP)
# ----------------------------------------------------------------------

class TestExercises(unittest.TestCase):
    def test_liste_contient_famille_et_recettes(self):
        r = engine.list_exercises()
        self.assertTrue(r["ok"])
        names = [e["name"] for e in r["exercises"]]
        self.assertIn("famille", names)
        self.assertIn("recettes", names)
        for e in r["exercises"]:
            self.assertTrue(e["title"])
            self.assertGreaterEqual(e["files"], 1)

    def test_charger_famille(self):
        r = engine.load_exercise("famille")
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(r["name"], "famille")
        self.assertIn("parentOf", r["kb"])
        self.assertIn("log:implies", r["rules"])
        self.assertIn("grandparentOf", r["conclusion"])
        # la requête préchargée est du SPARQL valide
        self.assertTrue(r["query"])
        p = engine.parse(r["query"], language="sparql")
        self.assertTrue(p["ok"], p["errors"])
        self.assertTrue(r["enonce"].strip())

    def test_charger_recettes(self):
        r = engine.load_exercise("recettes")
        self.assertTrue(r["ok"], r["errors"])
        # les trois fichiers de données sont concaténés dans kb,
        # regles.n3 dans rules
        self.assertIn("ingr:", r["kb"])
        self.assertIn("rec:", r["kb"])
        self.assertIn("med:", r["kb"])
        self.assertIn("log:implies", r["rules"])
        self.assertIn("math:", r["rules"])
        self.assertTrue(r["enonce"].strip())
        p = engine.parse(r["query"], language="sparql")
        self.assertTrue(p["ok"], p["errors"])

    def test_exercice_inconnu(self):
        r = engine.load_exercise("nexistepas")
        self.assertFalse(r["ok"])
        self.assertIn("inconnu", r["errors"][0]["message"])

    def test_traversee_de_dossier_refusee(self):
        for name in ("..", "../..", "a/b", "", None):
            r = engine.load_exercise(name)
            self.assertFalse(r["ok"], name)
        # un séparateur de chemin est un nom invalide ; un « .. » est
        # bloqué par le contrôle realpath (message « inconnu »)
        self.assertIn("invalide", engine.load_exercise("a/b")
                      ["errors"][0]["message"])
        self.assertFalse(engine.load_exercise("../lab_web")["ok"])

    def test_exercice_casse_n_se_charge_pas(self):
        # Un exercice dont les données ne parsent pas est rejeté avec
        # une erreur taguée « kb » (l'énoncé n'est pas masqué).
        import tempfile, os, shutil
        d = os.path.join(engine.EXERCISES_DIR, "zz_test_casse")
        os.makedirs(d, exist_ok=True)
        try:
            open(os.path.join(d, "enonce.md"), "w").write("# test\n")
            open(os.path.join(d, "donnees.n3"), "w").write(":a :b . ")
            r = engine.load_exercise("zz_test_casse")
            self.assertFalse(r["ok"])
            self.assertEqual(r["errors"][0]["doc"], "kb")
        finally:
            shutil.rmtree(d, ignore_errors=True)


# ----------------------------------------------------------------------
# P5 — visualisation du graphe (engine.graph, vis.js)
# ----------------------------------------------------------------------

GRAPH_KB = (
    "@prefix : <http://example.org/> .\n"
    ":alice a :Person .\n"
    ":alice :age 30 .\n"
    ":alice :parentOf :bob .\n"
    ":bob   :parentOf :carl .\n"
)

GRAPH_RULES = (
    "@prefix : <http://example.org/> .\n"
    "@prefix log: <http://www.w3.org/2000/10/swap/log#> .\n"
    "@forAll :x , :y , :z .\n"
    "{ :x :parentOf :y . :y :parentOf :z . } log:implies { :x :grandparentOf :z } .\n"
)


class TestGraph(unittest.TestCase):
    def _labels(self, r, kind=None):
        return sorted(n["label"] for n in r["nodes"]
                      if kind is None or n["kind"] == kind)

    def test_donnees_seules(self):
        r = engine.graph(GRAPH_KB, "")
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(self._labels(r, "resource"),
                         ["Person", "alice", "bob", "carl"])
        self.assertEqual(self._labels(r, "literal"), ["30"])
        # 4 arcs : a, age, parentOf x2
        self.assertEqual(len(r["edges"]), 4)
        self.assertEqual(r["statement_count"], 4)
        # rdf:type se lit « a »
        a_edges = [e for e in r["edges"]
                   if e["label"] == "a" and e["to"] == "http://example.org/Person"]
        self.assertEqual(len(a_edges), 1)
        self.assertFalse(r["truncated"])
        # sans raisonnement, rien d'inféré
        self.assertFalse(any(n["inferred"] for n in r["nodes"]))
        self.assertFalse(any(e["inferred"] for e in r["edges"]))

    def test_cloture_marque_le_infere(self):
        r = engine.graph(GRAPH_KB, GRAPH_RULES, reason=True)
        self.assertTrue(r["ok"], r["errors"])
        gp = [e for e in r["edges"] if e["label"] == "grandparentOf"]
        self.assertEqual(len(gp), 1)
        self.assertTrue(gp[0]["inferred"])
        self.assertEqual(gp[0]["from"], "http://example.org/alice")
        self.assertEqual(gp[0]["to"], "http://example.org/carl")
        # carl existe déjà dans les données : pas un nœud inféré
        self.assertFalse(any(n["inferred"] for n in r["nodes"]))
        # les arcs des données ne sont PAS marqués inférés
        self.assertEqual(
            [e for e in r["edges"] if e["label"] == "parentOf" and e["inferred"]],
            [])

    def test_noeuf_infere(self):
        # une règle qui crée un nouveau nœud : le nœud est marqué
        kb = "@prefix : <http://example.org/> .\n:alice a :Person .\n"
        rules = (
            "@prefix : <http://example.org/> .\n"
            "@prefix log: <http://www.w3.org/2000/10/swap/log#> .\n"
            "@forAll :x .\n"
            "{ :x a :Person . } log:implies { :x :knows :plato } .\n"
        )
        r = engine.graph(kb, rules, reason=True)
        self.assertTrue(r["ok"], r["errors"])
        plato = [n for n in r["nodes"]
                 if n["id"] == "http://example.org/plato"]
        self.assertEqual(len(plato), 1)
        self.assertTrue(plato[0]["inferred"])

    def test_attributs_masques(self):
        # P7 : les nœuds-littéraux sont masqués, leurs énoncés
        # regroupés en attributs (pastille) sur le sujet
        r = engine.graph(GRAPH_KB, "", hide_literals=True)
        self.assertTrue(r["ok"], r["errors"])
        # plus aucun nœud-littéral
        self.assertEqual(self._labels(r, "literal"), [])
        # l'arc vers le littéral « 30 » a disparu (3 arcs au lieu de 4)
        self.assertEqual(len(r["edges"]), 3)
        # mais l'énoncé compte toujours
        self.assertEqual(r["statement_count"], 4)
        # l'attribut est regroupé sur alice
        alice = "http://example.org/alice"
        self.assertIn(alice, r["attrs"])
        self.assertEqual(r["attrs"][alice], ["age 30"])
        # la bulle contextuelle du sujet liste l'attribut masqué
        alice_node = [n for n in r["nodes"] if n["id"] == alice][0]
        self.assertIn("attribut masqué", alice_node["title"])
        self.assertIn("age 30", alice_node["title"])

    def test_attributs_masques_sans_raisonnement(self):
        # le mode « attributs masqués » est orthogonal au raisonnement
        r = engine.graph(GRAPH_KB, GRAPH_RULES, reason=True,
                         hide_literals=True)
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(self._labels(r, "literal"), [])
        # l'arc inféré (grandparentOf, ressource→ressource) reste
        gp = [e for e in r["edges"] if e["label"] == "grandparentOf"]
        self.assertEqual(len(gp), 1)
        self.assertTrue(gp[0]["inferred"])

    def test_erreur_de_parse_taguee(self):
        r = engine.graph(":a :b .\n:cc ", "")
        self.assertFalse(r["ok"])
        self.assertEqual(r["errors"][0]["doc"], "kb")
        self.assertEqual(r["nodes"], [])
        self.assertEqual(r["edges"], [])

    def test_erreurs_et_timeout(self):
        # règle non bornée (la même que le test de timeout de P2) :
        # timeout propre, pas de blocage
        kb = "@prefix : <http://example.org/> .\n:a :chain :b .\n"
        rules = (
            "@prefix : <http://example.org/> .\n"
            "@prefix log: <http://www.w3.org/2000/10/swap/log#> .\n"
            "@forAll :x , :y .\n"
            "{ :x :chain :y . } log:implies { :y :chain2 [] } .\n"
            "@forAll :x , :y .\n"
            "{ :x :chain2 :y . } log:implies { :y :chain [] } .\n"
        )
        r = engine.graph(kb, rules, reason=True, timeout=2)
        self.assertFalse(r["ok"])
        self.assertTrue(r["timeout"])
        # mode inconnu
        r = engine.graph(GRAPH_KB, "", reason=True, mode="??")
        self.assertFalse(r["ok"])

    def test_troncation(self):
        # plus de triples que la limite : tronqué, signalé
        big = "@prefix : <http://example.org/> .\n" + "".join(
            ":s%d :p :o%d .\n" % (i, i) for i in range(10))
        old = engine._GRAPH_MAX_TRIPLES
        engine._GRAPH_MAX_TRIPLES = 3
        try:
            r = engine.graph(big, "")
        finally:
            engine._GRAPH_MAX_TRIPLES = old
        self.assertTrue(r["ok"], r["errors"])
        self.assertTrue(r["truncated"])
        self.assertEqual(r["statement_count"], 3)


class TestMarkdown(unittest.TestCase):
    """P7 — convertisseur Markdown minimal des énoncés (stdlib)."""

    def test_titres(self):
        html = engine.render_markdown("# Un\n## Deux\n### Trois\n")
        self.assertIn("<h1>Un</h1>", html)
        self.assertIn("<h2>Deux</h2>", html)
        self.assertIn("<h3>Trois</h3>", html)

    def test_inline(self):
        html = engine.render_markdown("du **gras**, de *l'italique*, `du code`")
        self.assertIn("<strong>gras</strong>", html)
        self.assertIn("<em>l'italique</em>", html)
        self.assertIn("<code>du code</code>", html)

    def test_listes(self):
        html = engine.render_markdown("- a\n- b\n  - c\n")
        self.assertIn("<ul>", html)
        self.assertIn("<li>a", html)
        # l'imbrication est DANS le <li> parent
        self.assertLess(html.index("<li>b"), html.index("<ul>", 10))
        self.assertLess(html.index("<ul>", 10), html.index("<li>c"))
        html = engine.render_markdown("1. un\n2. deux\n")
        self.assertIn("<ol>", html)
        self.assertIn("<li>un", html)

    def test_changement_de_type(self):
        html = engine.render_markdown("1. un\n- deux\n")
        # deux listes sœurs (ol puis ul), pas de mélange
        self.assertLess(html.index("</ol>"), html.index("<ul>"))

    def test_tableau(self):
        html = engine.render_markdown("| A | B |\n|---|---|\n| 1 | 2 |\n")
        self.assertIn("<thead><tr><th>A</th><th>B</th></tr></thead>", html)
        self.assertIn("<tr><td>1</td><td>2</td></tr>", html)
        self.assertNotIn("---", html)

    def test_bloc_code(self):
        html = engine.render_markdown("```\n:a :b :c .\n```\n")
        self.assertIn("<pre><code>:a :b :c .</code></pre>", html)

    def test_echappement_html(self):
        # aucun fragment de Markdown ne peut injecter de balise
        html = engine.render_markdown("<script>alert(1)</script>\n")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        html = engine.render_markdown("| a | <b> |\n|---|---|\n| 1 | 2 |\n")
        self.assertNotIn("<b>", html)

    def test_paragraphe(self):
        html = engine.render_markdown("ligne un\nligne deux\n\npara deux\n")
        self.assertIn("<p>ligne un ligne deux</p>", html)
        self.assertIn("<p>para deux</p>", html)

    def test_exercice_porte_enonce_html(self):
        d = engine.load_exercise("famille")
        self.assertTrue(d["ok"], d["errors"])
        self.assertIn("enonce_html", d)
        self.assertIn("<h1>", d["enonce_html"])
        # le texte brut reste fourni (source de vérité)
        self.assertTrue(d["enonce"].startswith("# "))


if __name__ == "__main__":
    unittest.main()
