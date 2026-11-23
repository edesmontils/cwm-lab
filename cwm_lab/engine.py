"""engine — wrapper stateless sur les API `swap` de CWM 2.0.

Chaque fonction publique crée son propre store (`llyn.RDFStore`) et ne
conserve aucun état entre deux appels : le serveur HTTP peut être
multithreadé, chaque requête est indépendante (on reconstruit le store
depuis le texte des éditeurs).

Fonctions livrées par phase (voir ROADMAP.md) :

- P0 : :func:`parse` — syntaxe N3/Turtle, erreurs ligne/colonne, stats ;
- P1 : :func:`serialize` — export N3 / Turtle / NTriples / RDF/XML ;
- P2 : :func:`infer` — raisonnement (clôture, nouveaux faits, incohérence,
  timeout) ;
- P3 : :func:`query` — requêtes SPARQL avec ou sans raisonnement
  (diff avant/après) ;
- P4 : validité (``testIncludes``), génération et vérification de preuves.
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

import ast
import io
import json
from html import escape as html_escape
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse

from swap.reasoner import diag, llyn
from swap.reasoner.diag import setVerbosity
from swap.parser import notation3
from swap.parser.notation3.helpers import BadSyntax
from swap.core.term import (AnonymousExistential, Fragment, List, Literal,
                            N3Set, Symbol)
from swap.core.formula import Formula
from swap.serialize import RDFSink, toXML

#: URI de base par défaut des documents saisis dans les éditeurs.
#: (Un document saisi sans base URI est traité comme s'il provenait
#: de cette adresse ; les préfixes et URIs relatives se résolvent là.)
DEFAULT_BASE_URI = "http://example.org/document.n3"


def _position(bad_syntax):
    """Ligne (1-indexée) et colonne (1-indexée) d'une ``BadSyntax``.

    ``BadSyntax._str`` est le document complet (on le fournit en une
    seule fois à ``feed``) et ``BadSyntax._i`` l'indice du caractère
    fautif — d'où une position exacte, indépendante du compteur de
    lignes interne au parser.
    """
    src = bad_syntax._str
    i = bad_syntax._i
    if i is None or i < 0 or not isinstance(src, str):
        return (getattr(bad_syntax, "lines", -1) + 1, 0)
    line = src.count("\n", 0, i) + 1
    column = i - src.rfind("\n", 0, i)
    return (line, column)


def _count_blank_nodes(term, found):
    """Renseigne ``found`` (set) avec les nœuds vides du document
    (``[ … ]`` et ``_:…``), y compris dans les listes, les ensembles
    et les formules emboîtées (corps / tête des règles).

    Hiérarchie des termes (swap.core.term) :

    - ``AnonymousNode``
      - ``AnonymousVariable``
        - ``AnonymousUniversal`` — variables ``@forAll`` (non comptées) ;
        - ``AnonymousExistential`` — **nœuds vides du document**
          (``[ … ]`` et ``_:…``) : ce sont les seuls comptés ;
      - ``Formula`` — corps / tête de règle (parcourus, non comptés).
    """
    if isinstance(term, Formula):
        for s in term.statements:
            _count_blank_nodes(s.subject(), found)
            _count_blank_nodes(s.predicate(), found)
            _count_blank_nodes(s.object(), found)
    elif isinstance(term, AnonymousExistential):
        found.add(term)
    elif isinstance(term, (List, N3Set)):
        for item in term:
            _count_blank_nodes(item, found)


def _parse_text(text, base_uri):
    """Parse ``text`` (UTF-8) dans un store neuf, dans la formule ouverte
    ``base_uri + "#_work"``.

    Renvoie ``(formula, None)`` en cas de succès (``formula`` est la
    formule *ouverte*, à ``close()`` si besoin) ou ``(None, error)`` où
    ``error`` est le dictionnaire d'erreur ``{"line", "column",
    "message"}`` (``line``/``column`` = 0 pour une erreur interne).
    """
    setVerbosity(0)  # état global du raisonneur : silence (risque #2 ROADMAP)
    store = llyn.RDFStore()
    formula = store.newFormula(base_uri + "#_work")
    parser = notation3.SinkParser(store, formula, thisDoc=base_uri)
    try:
        parser.startDoc()
        parser.feed(text.encode("utf-8"))
        parser.endDoc()
    except BadSyntax as e:
        line, column = _position(e)
        return None, {"line": line, "column": column, "message": e._why}
    except Exception as e:  # toute entrée d'étudiant doit rester gérable
        return None, {"line": 0, "column": 0,
                      "message": "erreur interne : %s: %s" % (type(e).__name__, e)}
    return formula, None


def parse(text, base_uri=DEFAULT_BASE_URI, language="n3"):
    """Parse un document N3/Turtle — ou une requête SPARQL — depuis une
    string.

    ``text`` : contenu du document (str, encodé UTF-8 ici).
    ``base_uri`` : URI de base pour la résolution des références.
    ``language`` : ``"n3"`` (défaut) — document N3/Turtle ; ``"sparql"``
    — requête SPARQL (validation de syntaxe de l'éditeur de requête).

    Renvoie un dictionnaire JSON-serialisable :

    - ``ok`` (bool) : le document a-t-il été parsé sans erreur ;
    - ``errors`` (list) : ``{"line", "column", "message"}`` par erreur ;
    - ``stats`` (dict ou None) :
      - N3/Turtle : ``{"statements", "rules", "blankNodes"}`` ;
      - SPARQL : ``{"queryType": "SelectQuery" | "AskQuery" |
        "ConstructQuery" | None, "variables": [...]}`` ;
      ``None`` si le parse a échoué.
    """
    if language == "sparql":
        return _parse_sparql_doc(text, base_uri)
    if language != "n3":
        return {
            "ok": False,
            "errors": [{"line": 0, "column": 0,
                        "message": "langage inconnu : %r (attendu : \"n3\" "
                                   "ou \"sparql\")" % language}],
            "stats": None,
        }
    formula, error = _parse_text(text, base_uri)
    if error is not None:
        return {"ok": False, "errors": [error], "stats": None}

    store = formula.store
    statements = list(formula.statementsMatching())
    rules = [s for s in statements if s.predicate() == store.implies]
    blank_nodes = set()
    for s in statements:
        _count_blank_nodes(s.subject(), blank_nodes)
        _count_blank_nodes(s.predicate(), blank_nodes)
        _count_blank_nodes(s.object(), blank_nodes)
    return {
        "ok": True,
        "errors": [],
        "stats": {
            "statements": len(statements),
            "rules": len(rules),
            "blankNodes": len(blank_nodes),
        },
    }


#: Formats de sortie acceptés par :func:`serialize`, et le drapeau
#: ``ToN3`` correspondant (``None`` = sérialiseur RDF/XML).
#:
#: - ``n3``       : N3 complet (règles, ``@forAll``, nœuds vides) ;
#: - ``turtle``   : Turtle (sous-ensemble strict — RDF pur uniquement) ;
#: - ``ntriples`` : NTriples (RDF pur uniquement, un triple par ligne) ;
#: - ``rdf``      : RDF/XML.
_SERIALIZE_FORMATS = {
    "n3": "qr",
    "turtle": "qr",
    "ntriples": "uspartnea",
    "rdf": None,
}


def _count_nonturtle(closed):
    """Nombre d'énoncés spécifiques à N3 (formule, universelle) dans la
    formule close ``closed`` — le même contrôle que le drapeau ``--turtle``
    de ``swap/cli/cwm.py`` (garde de sortie Turtle)."""
    uu = closed.universals()
    nonturtle = 0
    for s in closed.statements:
        for p in RDFSink.PRED, RDFSink.SUBJ, RDFSink.OBJ:
            x = s[p]
            if x in uu or isinstance(x, Formula):
                nonturtle += 1
                break
    return nonturtle


def serialize(text, format="n3", base_uri=DEFAULT_BASE_URI):
    """Sérialise un document N3/Turtle dans un autre format.

    ``text``      : contenu du document (str, encodé UTF-8) ;
    ``format``    : ``"n3"``, ``"turtle"``, ``"ntriples"`` ou ``"rdf"`` ;
    ``base_uri``  : URI de base (résolution des références à l'entrée ;
                    les sorties utilisent des URIs absolues, à l'exception
                    de l'espace de noms *par défaut* dérivé de la base —
                    comportement de ``ToN3``, identique au CLI cwm).

    Renvoie un dictionnaire JSON-serialisable :

    - ``ok`` (bool) : le document a-t-il été parsé (et, pour
      Turtle/NTriples, est-il du RDF pur exportable) ;
    - ``errors`` (list) : ``{"line", "column", "message"}`` par erreur ;
    - ``output`` (str ou None) : le document sérialisé, ``None`` si échec.

    Les formats Turtle et NTriples refusent les éléments spécifiques à
    N3 (formules, universelles) : ils n'existent pas dans ces formats —
    c'est le même refus que ``cwm --turtle``.
    """
    if format not in _SERIALIZE_FORMATS:
        return {
            "ok": False,
            "errors": [{"line": 0, "column": 0,
                        "message": "format inconnu : %r (attendu : %s)"
                                   % (format, ", ".join(sorted(_SERIALIZE_FORMATS)))}],
            "output": None,
        }
    formula, error = _parse_text(text, base_uri)
    if error is not None:
        return {"ok": False, "errors": [error], "output": None}

    store = formula.store
    closed = formula.close()
    assert closed.canonical is not None

    if format in ("turtle", "ntriples"):
        nonturtle = _count_nonturtle(closed)
        if nonturtle:
            return {
                "ok": False,
                "errors": [{"line": 0, "column": 0,
                            "message": "le document contient %d énoncé(s) "
                                       "spécifique(s) à N3 (formules, "
                                       "universelles, …) qui ne peuvent pas "
                                       "être écrits en %s. Exportez en N3."
                                       % (nonturtle,
                                          "Turtle" if format == "turtle"
                                          else "NTriples")}],
                "output": None,
            }

    buf = io.StringIO()
    flags = _SERIALIZE_FORMATS[format]
    if flags is None:  # RDF/XML
        sink = toXML.ToRDF(buf, base_uri, base=base_uri, flags="r")
    else:
        sink = notation3.ToN3(buf.write, base=base_uri, quiet=1, flags=flags)
    store.dumpNested(closed, sink)
    return {"ok": True, "errors": [], "output": buf.getvalue()}


#: URI du symbole ``log:implies`` (les énoncés-règles de la clôture).
IMPLIES_URI = "http://www.w3.org/2000/10/swap/log#implies"

#: Constante ``false`` du langage N3. Une clôture est **incohérente**
#: si elle contient cette constante — c'est la sémantique de
#: l'incohérence dans CWM (la triple canonique est
#: ``log:false log:false log:false``). NB : le mot-clé nu ``false`` du
#: parser est un *littéral booléen* qui est simplement ignoré dans une
#: formule — il n'est PAS la constante N3 (piège documenté dans le
#: ROADMAP P2).
LOG_FALSE_URI = "http://www.w3.org/2000/10/swap/log#false"


def _term_str(term):
    """Chaîne d'identification d'un terme.

    - symboles / fragments : **URI absolue** (``uriref()``) — ``value()``
      renvoie ``self`` et ``str()`` un fragment relatif dépendant de la
      base, inutilisables pour un diff stable. NB : dans la hiérarchie
      ``swap.core.term``, ``Fragment`` n'est PAS un sous-classe de
      ``Symbol`` (les deux héritent de ``LabelledNode``) — d'où le
      double contrôle ;
    - littéraux : la valeur ``value()`` (chaîne) ;
    - nœuds vides : le nom de nœud vide (``str()``) ;
    - termes composites (listes, ensembles) : ``str()``.
    """
    if isinstance(term, (Symbol, Fragment)):
        return term.uriref()
    value = term.value()
    return value if isinstance(value, str) else str(term)


def _triple_keys(formula):
    """Ensemble de clés ``(s, p, o)`` (chaînes) des énoncés *de niveau
    supérieur* de la formule — base du diff « nouveaux faits ». Les
    nœuds vides gardent leur nom dans la formule (identité stable au
    sein d'une même formule ouverte)."""
    return {(_term_str(s[2]), _term_str(s[1]), _term_str(s[3]))
            for s in formula.statements}


def _infer_result(errors=None, timeout=False, new_facts=(),
                  inconsistent=False, closure_statements=0,
                  rules_in_closure=0, elapsed_ms=0):
    return {
        "ok": errors is None and not timeout,
        "errors": errors or [],
        "timeout": timeout,
        "new_facts": [list(t) for t in sorted(new_facts)],
        "inconsistent": inconsistent,
        "closure_statements": closure_statements,
        "rules_in_closure": rules_in_closure,
        "elapsed_ms": elapsed_ms,
    }


def infer(kb_text, rules_text, base_uri=DEFAULT_BASE_URI, mode="think",
          store_rules=False, timeout=10.0):
    """Raisonnement par chaînage avant sur une base de données + règles.

    Deux documents sont parsés dans le même store :

    - ``kb_text``    : les données (N3/Turtle) — la base de connaissance ;
    - ``rules_text`` : les règles N3 (``{ … } log:implies { … } .``).

    Les règles sont appliquées à une *copie ouverte* de la KB (la KB
    close d'origine sert de référence pour le diff). La clôture se fait
    dans un thread **démon** : si ``timeout`` secondes s'écoulent sans
    convergence, la réponse revient quand même (le thread orphelin est
    abandonné) — une règle récursive ne bloque jamais le TP.

    Paramètres :

    - ``mode`` : ``"think"`` — convergence (point fixe ; ``think()``,
      comme ``cwm --think``) ; ``"once"`` — une seule passe sur les
      règles (``applyRules()``, comme ``cwm --apply=``).
    - ``store_rules`` : si ``True``, les énoncés-règles sont copiés
      dans la clôture (comportement de ``cwm --rules``) ; sinon les
      règles restent dans leur document (``cwm --think=``). Elles sont
      toujours exclues du diff des « nouveaux faits ».
    - ``timeout`` : délai maximum en secondes (``0`` = sans limite).

    Renvoie un dictionnaire JSON-serialisable :

    - ``ok`` (bool) : parse réussi ET raisonnement terminé ;
    - ``errors`` (list) : erreurs de parse, taguées ``{"doc": "kb" |
      "rules", "line", "column", "message"}`` ;
    - ``timeout`` (bool) : la clôture n'a pas convergé dans le délai ;
    - ``new_facts`` (list) : triples nouveaux ``[s, p, o]`` (chaînes),
      triés, excluant les énoncés-règles ;
    - ``inconsistent`` (bool) : la clôture contient la constante
      ``log:false`` (sémantique CWM de l'incohérence) ;
    - ``closure_statements`` (int) : nb d'énoncés de niveau supérieur
      de la clôture ;
    - ``rules_in_closure`` (int) : nb d'énoncés-règles dans la clôture
      (non nul si ``store_rules``) ;
    - ``elapsed_ms`` (int) : durée du raisonnement en millisecondes.
    """
    if mode not in ("think", "once"):
        return _infer_result(errors=[{
            "doc": "rules", "line": 0, "column": 0,
            "message": "mode inconnu : %r (attendu : \"think\" ou \"once\")" % mode,
        }])
    try:
        timeout = float(timeout)
    except (TypeError, ValueError):
        timeout = 10.0
    if timeout < 0:
        timeout = 0.0

    # import différé : le module swap.query.query est lourd et n'est
    # utile qu'ici (parse/serialize n'en ont pas besoin)
    from swap.query.query import applyRules, think

    # Les deux documents doivent vivre dans le même store (les règles
    # référencent les symboles du store).
    setVerbosity(0)
    store = llyn.RDFStore()
    formula = store.newFormula(base_uri + "#_work")
    parser = notation3.SinkParser(store, formula, thisDoc=base_uri)
    try:
        parser.startDoc()
        parser.feed(kb_text.encode("utf-8"))
        parser.endDoc()
        kb_closed = formula.close()
    except BadSyntax as e:
        line, column = _position(e)
        return _infer_result(errors=[{
            "doc": "kb", "line": line, "column": column, "message": e._why,
        }])
    except Exception as e:  # toute entrée d'étudiant doit rester gérable
        return _infer_result(errors=[{
            "doc": "kb", "line": 0, "column": 0,
            "message": "erreur interne : %s: %s" % (type(e).__name__, e),
        }])

    rules_formula = store.newFormula(base_uri + "#_rules")
    parser = notation3.SinkParser(store, rules_formula, thisDoc=base_uri)
    try:
        parser.startDoc()
        parser.feed(rules_text.encode("utf-8"))
        parser.endDoc()
        rules_closed = rules_formula.close()
    except BadSyntax as e:
        line, column = _position(e)
        return _infer_result(errors=[{
            "doc": "rules", "line": line, "column": column, "message": e._why,
        }])
    except Exception as e:
        return _infer_result(errors=[{
            "doc": "rules", "line": 0, "column": 0,
            "message": "erreur interne : %s: %s" % (type(e).__name__, e),
        }])

    # Copie ouverte de la KB : les conclusions s'y ajoutent (think exige
    # une formule ouverte) ; la KB close d'origine sert de référence.
    open_kb = store.newFormula(base_uri + "#_closure")
    store.copyFormula(kb_closed, open_kb)
    if store_rules:
        store.copyFormula(rules_closed, open_kb)
    before = _triple_keys(open_kb)

    outcome = {}

    def _run():
        if mode == "think":
            outcome["count"] = think(open_kb, rules_closed)
        else:
            outcome["count"] = applyRules(open_kb, rules_closed)

    start = time.monotonic()
    if timeout > 0:
        worker = threading.Thread(target=_run, daemon=True)
        worker.start()
        worker.join(timeout)
        if worker.is_alive():
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return _infer_result(
                timeout=True,
                errors=[{
                    "doc": "rules", "line": 0, "column": 0,
                    "message": "timeout après %g s : la clôture ne converge "
                               "pas (règle récursive produisant sans fin ?)"
                               % timeout,
                }],
                elapsed_ms=elapsed_ms,
            )
    else:
        _run()
    elapsed_ms = int((time.monotonic() - start) * 1000)

    after = _triple_keys(open_kb)
    new_facts = after - before
    # Les énoncés-règles (prédicat log:implies) ne sont pas des « faits » :
    # on les exclut du diff (cas des règles stockées ou générées).
    new_facts = {t for t in new_facts if t[1] != IMPLIES_URI}
    inconsistent = any(LOG_FALSE_URI in t for t in after)
    rules_in_closure = sum(1 for t in after if t[1] == IMPLIES_URI)
    return _infer_result(new_facts=new_facts, inconsistent=inconsistent,
                         closure_statements=len(after),
                         rules_in_closure=rules_in_closure,
                         elapsed_ms=elapsed_ms)


# ----------------------------------------------------------------------
# P3 — requêtes SPARQL
# ----------------------------------------------------------------------

#: Namespace CWM de la représentation interne des requêtes SPARQL
#: (les requêtes sont parsées en formules N3 « sparqlCwm »).
SPARQL_NS = "http://www.w3.org/2000/10/swap/sparqlCwm"

#: Une *ligne de résultat* d'un SELECT est une formule typée
#: ``sparqlCwm:Result`` ; chaque énoncé interne lie une variable
#: (littéral du nom) à un terme via le prédicat ``bound``.
SPARQL_RESULT_URI = SPARQL_NS + "#Result"

#: La réponse d'un ASK vrai est une formule typée ``sparqlCwm:Success``
#: (un ASK faux, comme un SELECT sans réponse, ne produit aucun
#: énoncé — le résultat est vide).
SPARQL_SUCCESS_URI = SPARQL_NS + "#Success"


def _parse_sparql(store, text, base_uri):
    """Parse une requête SPARQL dans la formule ouverte
    ``base_uri + "#_query"`` du store ``store``.

    Mêmes briques que le chargement ``contentType="x-application/sparql"``
    du CLI (``swap/io/webAccess.py``) : lexiqueur/générateur
    ``sparql_parser`` + convertisseur ``sparql2cwm.FromSparql`` qui
    réécrit la requête en formules N3. Lève une ``Exception`` (message
    ``Found (…token…) when expecting …``) en cas de syntaxe invalide.
    """
    from swap.query.sparql import sparql_parser
    from swap.query import sparql2cwm
    formula = store.newFormula(base_uri + "#_query")
    convertor = sparql2cwm.FromSparql(store, formula)
    parser = sparql_parser.N3Parser(io.BytesIO(text.encode("utf-8")),
                                    sparql_parser.branches, convertor)
    parsed = parser.parse(sparql_parser.start)
    if parsed is None:      # EOF : document vide
        return store.newFormula(base_uri + "#_query_empty").close()
    return parsed.close()


def _sparql_error(exc, text):
    """``(ligne 1-indexée, message lisible)`` à partir de l'exception du
    parser SPARQL.

    Deux formats de message :

    - ``Found ('…#LANGTAG', '@prefix', 0) when expecting a …#Query .
      todo_stack=[…]`` : le token porte la ligne (0-indexée, compteur
      du lexiqueur) — on l'extraie ;
    - ``found BLABLA ?x when expecting one of […]`` : seul le reste du
      document est cité (pas de ligne).

    Un token de fin de document (``'…#eof', '', -1``) est traduit en
    « requête incomplète » (la ligne signalée est la dernière du
    document). Repli : le message brut tronqué.
    """
    msg = str(exc)
    line, word = 0, None
    m = re.search(r"Found (\([^)]*\))", msg)
    if m:
        try:
            tok = ast.literal_eval(m.group(1))
            line, word = max(int(tok[2]), 0) + 1, tok[1]
        except (ValueError, SyntaxError, TypeError, IndexError):
            pass
    if word is None:
        m = re.search(r"found (.+?) when expecting", msg)
        if m:
            word = m.group(1).strip()
    if word is None:
        return (0, "erreur de syntaxe SPARQL : %s" % msg[:300])
    if word == "":
        return (max(text.count("\n") + 1, 1),
                "requête incomplète : fin de document inattendue")
    if len(word) > 60:
        word = word[:57] + "…"
    return (line, "erreur de syntaxe SPARQL : token inattendu %r" % word)


def _sparql_query_type(store, qf):
    """Type d'une requête SPARQL parsée : ``"SelectQuery"`` /
    ``"AskQuery"`` / ``"ConstructQuery"`` (ou ``None``)."""
    sparql = store.newSymbol(SPARQL_NS)
    for name in ("SelectQuery", "AskQuery", "ConstructQuery"):
        if qf.any(pred=store.type, obj=sparql[name]) is not None:
            return name
    return None


def _select_variables(text):
    """Variables de la clause SELECT, **dans l'ordre du texte** (sans
    le ``?``) — ``None`` pour ``SELECT *`` ou si la clause ne peut pas
    être lue.

    NB : l'ordre ne peut pas être lu dans la formule parsée — la clause
    SELECT y est une formule (un *ensemble* d'énoncés, sans ordre).
    Les alias ``AS`` ne sont pas pris en charge (hors périmètre TP).
    """
    m = re.search(r"SELECT\s+(?:DISTINCT\s+|REDUCED\s+)?(.*?)\s+WHERE",
                  text, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    clause = m.group(1).strip()
    if clause == "*":
        return None
    return re.findall(r"\?([A-Za-z_][A-Za-z0-9_]*)", clause)


def _row_keys(rows_dicts):
    """Union triée des noms de variables de ``rows_dicts`` (repli pour
    ``SELECT *``, où l'ordre n'est pas lisible dans le texte)."""
    keys = set()
    for r in rows_dicts:
        keys.update(r.keys())
    return sorted(keys)


def _rows_to_grid(variables, rows_dicts):
    """Grille JSON (listes de chaînes) — ``variables`` : ordre des
    colonnes (``None`` → union triée des clés)."""
    if variables is None:
        variables = _row_keys(rows_dicts)
    return [[row.get(v, "") for v in variables] for row in rows_dicts]


def _extract_query_result(store, newc, query_text):
    """``(variables_ou_None, lignes, ask)`` à partir de la formule de
    résultat ``newc`` : ``variables_ou_None`` est l'ordre de la clause
    SELECT lu dans le *texte* (``None`` pour ``SELECT *``), les lignes
    sont des dictionnaires {variable: chaîne}, ``ask`` est ``True`` si
    la formule porte ``sparqlCwm:Success`` (ASK vrai), ``False`` sinon.

    NB : l'ordre des colonnes est décidé par l'appelant à partir de la
    grille complète (avant + après), pour que le diff soit comparable.
    """
    rows, ask = [], False
    for s in newc.statements:
        obj = s[3]
        if isinstance(obj, (Symbol, Fragment)):
            uri = obj.uriref()
            if uri == SPARQL_SUCCESS_URI:
                ask = True
            elif uri == SPARQL_RESULT_URI:
                row = {}
                for i in s[2].statements:
                    # énoncé de liaison : (VALEUR, bound, "nomVariable")
                    # — la valeur est en SUJET, le nom en OBJET
                    v = i[3].value()
                    key = v if isinstance(v, str) else str(i[3])
                    row[key] = _term_str(i[2])
                rows.append(row)
    return _select_variables(query_text), rows, ask


def _run_sparql(store, kb_closed, qf, query_text):
    """Exécute la requête ``qf`` sur la KB close ``kb_closed`` — même
    cheminement que le CLI (``cwm --sparql``) : copie du contexte de
    travail + canonicalisation, résultats dans une formule neuve.
    La formule de requête n'est pas modifiée (``substitution`` en rend
    une copie) : la même requête peut s'exécuter plusieurs fois
    (avant/après raisonnement). Renvoie ``(variables_ou_None, lignes
    (dictionnaires), ask)`` — voir :func:`_extract_query_result`."""
    from swap.query.query import applySparqlQueries
    working = store.newFormula()
    store.copyFormula(kb_closed, working)
    working = working.canonicalize()
    result = store.newFormula()
    result.stayOpen = True
    applySparqlQueries(working, qf, result)
    return _extract_query_result(store, result, query_text)


def _parse_sparql_doc(text, base_uri):
    """Parse SPARQL autonome (validation de l'éditeur de requête)."""
    if not text.strip():
        # Un document vide est valide (comme en N3) — le parser, lui,
        # lève une exception « fin de document inattendue ».
        return {"ok": True, "errors": [],
                "stats": {"queryType": None, "variables": []}}
    setVerbosity(0)  # état global du raisonneur : silence (risque #2 ROADMAP)
    store = llyn.RDFStore()
    try:
        qf = _parse_sparql(store, text, base_uri)
    except Exception as e:  # toute entrée d'étudiant doit rester gérable
        line, message = _sparql_error(e, text)
        return {"ok": False,
                "errors": [{"line": line, "column": 0, "message": message}],
                "stats": None}
    qtype = _sparql_query_type(store, qf)
    variables = _select_variables(text)
    return {"ok": True, "errors": [],
            "stats": {"queryType": qtype, "variables": variables or []}}


def _query_result(errors=None, timeout=False, query_type=None,
                  variables=None, rows_raw=None, ask_raw=False,
                  rows_reasoned=None, ask_reasoned=False, new_rows=None,
                  closure_statements=None, elapsed_ms=0):
    return {
        "ok": errors is None and not timeout,
        "errors": errors or [],
        "timeout": timeout,
        "query_type": query_type,
        "variables": variables or [],
        "rows_raw": rows_raw or [],
        "ask_raw": ask_raw,
        "rows_reasoned": rows_reasoned,
        "ask_reasoned": ask_reasoned,
        "new_rows": new_rows or [],
        "closure_statements": closure_statements,
        "elapsed_ms": elapsed_ms,
    }


def query(kb_text, query_text, rules_text="", base_uri=DEFAULT_BASE_URI,
          reason=False, mode="think", store_rules=False, timeout=10.0):
    """Exécute une requête SPARQL (``SELECT`` ou ``ASK``) sur une base de
    données, avec ou sans raisonnement préalable.

    Trois documents dans le même store :

    - ``kb_text``    : les données (N3/Turtle) ;
    - ``query_text`` : la requête SPARQL (``PREFIX``/``SELECT``/``ASK``) ;
    - ``rules_text`` : les règles N3 — utilisées uniquement si
      ``reason`` est ``True``.

    La requête s'exécute toujours sur la KB brute (``rows_raw``) ; si
    ``reason``, la clôture se d'abord (même moteur et même timeout que
    :func:`infer`, dans un thread démont) puis la *même* requête est
    ré-exécutée sur la clôture (``rows_reasoned``) — ``new_rows`` est
    le diff (lignes présentes après raisonnement et absentes avant) :
    la fonctionnalité la plus pédagogique du TP. En cas de timeout,
    les résultats bruts sont quand même renvoyés.

    Paramètres : ``mode`` / ``store_rules`` / ``timeout`` — mêmes
    sémantiques que :func:`infer`.

    Renvoie un dictionnaire JSON-serialisable :

    - ``ok``, ``errors`` (taguées ``"kb"`` / ``"query"`` / ``"rules"``),
      ``timeout`` — comme :func:`infer` ;
    - ``query_type`` : ``"SelectQuery"`` ou ``"AskQuery"`` ;
    - ``variables`` (list) : variables de la clause SELECT, en ordre ;
    - ``rows_raw`` (list) : lignes ``[v1, …]`` (chaînes) sur la KB brute ;
    - ``ask_raw`` (bool) : réponse de l'ASK sur la KB brute ;
    - ``rows_reasoned`` (list ou None) : lignes sur la clôture (``None``
      si pas de raisonnement, ou timeout) ;
    - ``ask_reasoned`` (bool) : réponse de l'ASK sur la clôture ;
    - ``new_rows`` (list) : lignes du diff avant/après, triées ;
    - ``closure_statements`` (int ou None) : nb d'énoncés de la clôture ;
    - ``elapsed_ms`` (int).

    NB : N3QL n'est pas supporté (aucun exemple de référence dans le
    corpus CWM ; l'API ``applyQueries`` existe mais reste à valider) —
    le TP est calibré sur SPARQL.
    """
    if mode not in ("think", "once"):
        return _query_result(errors=[{
            "doc": "rules", "line": 0, "column": 0,
            "message": "mode inconnu : %r (attendu : \"think\" ou \"once\")" % mode,
        }])
    try:
        timeout = float(timeout)
    except (TypeError, ValueError):
        timeout = 10.0
    if timeout < 0:
        timeout = 0.0

    from swap.query.query import applyRules, think

    setVerbosity(0)
    store = llyn.RDFStore()

    # --- KB (N3/Turtle) -------------------------------------------------
    formula = store.newFormula(base_uri + "#_work")
    parser = notation3.SinkParser(store, formula, thisDoc=base_uri)
    try:
        parser.startDoc()
        parser.feed(kb_text.encode("utf-8"))
        parser.endDoc()
        kb_closed = formula.close()
    except BadSyntax as e:
        line, column = _position(e)
        return _query_result(errors=[{
            "doc": "kb", "line": line, "column": column, "message": e._why,
        }])
    except Exception as e:  # toute entrée d'étudiant doit rester gérable
        return _query_result(errors=[{
            "doc": "kb", "line": 0, "column": 0,
            "message": "erreur interne : %s: %s" % (type(e).__name__, e),
        }])

    # --- requête SPARQL -------------------------------------------------
    if not query_text.strip():
        return _query_result(errors=[{
            "doc": "query", "line": 0, "column": 0, "message": "requête vide",
        }])
    try:
        qf = _parse_sparql(store, query_text, base_uri)
    except Exception as e:
        line, message = _sparql_error(e, query_text)
        return _query_result(errors=[{
            "doc": "query", "line": line, "column": 0, "message": message,
        }])
    qtype = _sparql_query_type(store, qf)
    if qtype not in ("SelectQuery", "AskQuery"):
        return _query_result(errors=[{
            "doc": "query", "line": 0, "column": 0,
            "message": "seules les requêtes SELECT et ASK sont prises en "
                       "charge par l'outil (pas de CONSTRUCT / DESCRIBE)",
        }])

    start = time.monotonic()

    # --- requête sur la KB brute ----------------------------------------
    try:
        qvars, rows_raw_dicts, ask_raw = _run_sparql(store, kb_closed, qf,
                                                     query_text)
    except Exception as e:
        return _query_result(query_type=qtype, errors=[{
            "doc": "query", "line": 0, "column": 0,
            "message": "erreur pendant l'exécution : %s: %s"
                       % (type(e).__name__, e),
        }])
    variables = qvars or _row_keys(rows_raw_dicts)
    if not reason:
        return _query_result(query_type=qtype, variables=variables,
                             rows_raw=sorted(_rows_to_grid(variables,
                                                           rows_raw_dicts)),
                             ask_raw=ask_raw,
                             elapsed_ms=int((time.monotonic() - start) * 1000))

    rows_raw = sorted(_rows_to_grid(variables, rows_raw_dicts))

    # --- règles ----------------------------------------------------------
    rules_formula = store.newFormula(base_uri + "#_rules")
    parser = notation3.SinkParser(store, rules_formula, thisDoc=base_uri)
    try:
        parser.startDoc()
        parser.feed(rules_text.encode("utf-8"))
        parser.endDoc()
        rules_closed = rules_formula.close()
    except BadSyntax as e:
        line, column = _position(e)
        return _query_result(query_type=qtype, variables=variables,
                             rows_raw=rows_raw, ask_raw=ask_raw,
                             errors=[{
                                 "doc": "rules", "line": line, "column": column,
                                 "message": e._why,
                             }],
                             elapsed_ms=int((time.monotonic() - start) * 1000))
    except Exception as e:
        return _query_result(query_type=qtype, variables=variables,
                             rows_raw=rows_raw, ask_raw=ask_raw,
                             errors=[{
                                 "doc": "rules", "line": 0, "column": 0,
                                 "message": "erreur interne : %s: %s"
                                            % (type(e).__name__, e),
                             }],
                             elapsed_ms=int((time.monotonic() - start) * 1000))

    # --- clôture (thread démont + timeout, comme infer) ------------------
    open_kb = store.newFormula(base_uri + "#_closure")
    store.copyFormula(kb_closed, open_kb)
    if store_rules:
        store.copyFormula(rules_closed, open_kb)

    def _run():
        if mode == "think":
            think(open_kb, rules_closed)
        else:
            applyRules(open_kb, rules_closed)

    if timeout > 0:
        worker = threading.Thread(target=_run, daemon=True)
        worker.start()
        worker.join(timeout)
        if worker.is_alive():
            return _query_result(
                timeout=True,
                query_type=qtype, variables=variables,
                rows_raw=rows_raw, ask_raw=ask_raw,
                errors=[{
                    "doc": "rules", "line": 0, "column": 0,
                    "message": "timeout après %g s : la clôture ne converge "
                               "pas (règle récursive produisant sans fin ?)"
                               % timeout,
                }],
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )

    # --- requête sur la clôture ------------------------------------------
    try:
        closure_closed = open_kb.close()
        qvars2, rows_reasoned_dicts, ask_reasoned = _run_sparql(
            store, closure_closed, qf, query_text)
    except Exception as e:
        return _query_result(query_type=qtype, variables=variables,
                             rows_raw=rows_raw, ask_raw=ask_raw,
                             errors=[{
                                 "doc": "query", "line": 0, "column": 0,
                                 "message": "erreur pendant l'exécution : "
                                            "%s: %s" % (type(e).__name__, e),
                             }],
                             elapsed_ms=int((time.monotonic() - start) * 1000))

    # Ordre de colonnes final : celui de la clause SELECT, sinon l'union
    # triée des variables vues (cas SELECT * : les noms ne sont pas
    # lisibles dans le texte, et le résultat brut peut être vide).
    variables = qvars or _row_keys(rows_raw_dicts + rows_reasoned_dicts)
    rows_raw = sorted(_rows_to_grid(variables, rows_raw_dicts))
    rows_reasoned = sorted(_rows_to_grid(variables, rows_reasoned_dicts))
    new_rows = [r for r in rows_reasoned if r not in rows_raw]
    return _query_result(
        query_type=qtype, variables=variables,
        rows_raw=rows_raw, ask_raw=ask_raw,
        rows_reasoned=rows_reasoned, ask_reasoned=ask_reasoned,
        new_rows=new_rows,
        closure_statements=len(_triple_keys(closure_closed)),
        elapsed_ms=int((time.monotonic() - start) * 1000),
    )


# ----------------------------------------------------------------------
# P4 — validité & preuves
# ----------------------------------------------------------------------

#: Racine du dépôt (là où se trouve le paquet ``swap``) — le
#: subprocess ``check`` y est lancé pour utiliser le même code CWM
#: que le moteur (risque #4 ROADMAP : ``check`` manipule
#: ``sys.argv``/``stdin`` → subprocess uniquement, jamais in-process).
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

# Garde du global CWM ``diag.tracking`` (état de suivi pour la
# génération de preuves). Un thread de :func:`prove` abandonné au
# timeout reste bloqué dans sa ``think()`` non convergente : son
# ``finally`` ne s'exécutera jamais, et ``diag.tracking`` resterait
# actif — ce qui casserait tout parse ultérieur sans ``why=``
# (« Tracking reasons but no reason given »). Un jeton par génération
# de preuve + une interruption sous le même verrou que l'activation
# garantissent que :

# - un thread abandonné ne laisse pas le suivi actif ;
# - un thread en retard (démarré après le timeout) ne réactive pas
#   le suivi d'une génération déjà abandonnée ;
# - une génération ultérieure n'est pas écrasée par un ``finally``
#   d'une génération antérieure.
_tracking_guard = threading.Lock()
_tracking_gen = None
_tracking_aborted = set()


def _tracking_begin(token):
    """Activer le suivi pour la génération de preuve ``token`` (sans
    effet si la génération a été abandonnée entre-temps)."""
    global _tracking_gen
    with _tracking_guard:
        if token in _tracking_aborted:
            _tracking_aborted.discard(token)  # consommé, le thread a vécu
            return
        _tracking_gen = token
        diag.tracking = 1


def _tracking_end(token):
    """Désactiver le suivi si la génération ``token`` est toujours la
    dernière démarrée (sinon : une génération plus récente a déjà
    repris la main, on ne l'écrase pas)."""
    global _tracking_gen
    with _tracking_guard:
        _tracking_aborted.discard(token)
        if _tracking_gen is token:
            _tracking_gen = None
            diag.tracking = 0


def _tracking_abort(token):
    """Timeout : marquer la génération ``token`` comme abandonnée
    (un thread en retard ne réactivera pas le suivi) et réinitialiser
    le suivi s'il est toujours celui de ``token``."""
    global _tracking_gen
    with _tracking_guard:
        _tracking_aborted.add(token)
        if _tracking_gen is token:
            _tracking_gen = None
            diag.tracking = 0


def _data_uri(text):
    """URI ``data:`` du texte N3 ``text`` — source *intégrée* de la
    preuve (voir :func:`prove`) : ``check`` recharge chaque étape
    ``:Parsing`` par son URI ; avec une source ``data:`` la preuve est
    **auto-suffisante** (aucun fichier externe à retrouver au
    moment de la vérification)."""
    return "data:text/rdf+n3;charset=utf-8," + urllib.parse.quote(text)


def _entail_result(errors=None, timeout=False, entails=None,
                   inconsistent=False, closure_statements=0,
                   elapsed_ms=0):
    return {
        "ok": errors is None and not timeout,
        "errors": errors or [],
        "timeout": timeout,
        "entails": entails,
        "inconsistent": inconsistent,
        "closure_statements": closure_statements,
        "elapsed_ms": elapsed_ms,
    }


def entail(kb_text, rules_text, conclusion_text, base_uri=DEFAULT_BASE_URI,
           mode="think", timeout=10.0):
    """« La KB entraîne-t-elle la conclusion ? » — test d'entraînement
    par inclusion de formule (``testIncludes``).

    Trois documents dans le même store :

    - ``kb_text``         : les données (N3/Turtle) ;
    - ``rules_text``      : les règles N3 ;
    - ``conclusion_text`` : la conclusion à tester (N3/Turtle).

    La clôture se d'abord (même moteur, même timeout par thread
    démont que :func:`infer`) puis
    ``testIncludes(clôture, conclusion)`` répond oui/non.

    NB : si la clôture est **incohérente** (``log:false``), tout y est
    entraîné (explosion, *ex falso quodlibet*) — le moteur CWM ne
    l'implémente pas dans ``testIncludes`` (inclusion pure), donc
    :func:`entail` l'applique explicitement : ``entails`` vaut
    ``True`` quelle que soit la conclusion, et ``inconsistent: true``
    permet à l'interface de signaler que ce oui est vide.

    Renvoie un dictionnaire JSON-serialisable :

    - ``ok``, ``errors`` (taguées ``"kb"`` / ``"rules"`` / ``"concl"``),
      ``timeout`` — comme :func:`infer` ;
    - ``entails`` (bool ou None) : la clôture entraîne-t-elle la
      conclusion (``None`` en cas de timeout) ;
    - ``inconsistent`` (bool) : la clôture contient ``log:false`` ;
    - ``closure_statements`` (int) : nb d'énoncés de la clôture ;
    - ``elapsed_ms`` (int).
    """
    if mode not in ("think", "once"):
        return _entail_result(errors=[{
            "doc": "rules", "line": 0, "column": 0,
            "message": "mode inconnu : %r (attendu : \"think\" ou \"once\")" % mode,
        }])
    try:
        timeout = float(timeout)
    except (TypeError, ValueError):
        timeout = 10.0
    if timeout < 0:
        timeout = 0.0
    if not conclusion_text.strip():
        return _entail_result(errors=[{
            "doc": "concl", "line": 0, "column": 0,
            "message": "conclusion vide : écrivez au moins un triple dans "
                       "l'éditeur « Conclusion »",
        }])

    from swap.query.query import applyRules, think, testIncludes

    setVerbosity(0)
    store = llyn.RDFStore()

    # --- KB (N3/Turtle) -------------------------------------------------
    formula = store.newFormula(base_uri + "#_work")
    parser = notation3.SinkParser(store, formula, thisDoc=base_uri)
    try:
        parser.startDoc()
        parser.feed(kb_text.encode("utf-8"))
        parser.endDoc()
        kb_closed = formula.close()
    except BadSyntax as e:
        line, column = _position(e)
        return _entail_result(errors=[{
            "doc": "kb", "line": line, "column": column, "message": e._why,
        }])
    except Exception as e:  # toute entrée d'étudiant doit rester gérable
        return _entail_result(errors=[{
            "doc": "kb", "line": 0, "column": 0,
            "message": "erreur interne : %s: %s" % (type(e).__name__, e),
        }])

    # --- règles -----------------------------------------------------------
    rules_formula = store.newFormula(base_uri + "#_rules")
    parser = notation3.SinkParser(store, rules_formula, thisDoc=base_uri)
    try:
        parser.startDoc()
        parser.feed(rules_text.encode("utf-8"))
        parser.endDoc()
        rules_closed = rules_formula.close()
    except BadSyntax as e:
        line, column = _position(e)
        return _entail_result(errors=[{
            "doc": "rules", "line": line, "column": column, "message": e._why,
        }])
    except Exception as e:
        return _entail_result(errors=[{
            "doc": "rules", "line": 0, "column": 0,
            "message": "erreur interne : %s: %s" % (type(e).__name__, e),
        }])

    # --- conclusion -------------------------------------------------------
    concl_formula = store.newFormula(base_uri + "#_concl")
    parser = notation3.SinkParser(store, concl_formula, thisDoc=base_uri)
    try:
        parser.startDoc()
        parser.feed(conclusion_text.encode("utf-8"))
        parser.endDoc()
        concl_closed = concl_formula.close()
    except BadSyntax as e:
        line, column = _position(e)
        return _entail_result(errors=[{
            "doc": "concl", "line": line, "column": column, "message": e._why,
        }])
    except Exception as e:
        return _entail_result(errors=[{
            "doc": "concl", "line": 0, "column": 0,
            "message": "erreur interne : %s: %s" % (type(e).__name__, e),
        }])

    # --- clôture + testIncludes (thread démont + timeout, comme infer) ----
    open_kb = store.newFormula(base_uri + "#_closure")
    store.copyFormula(kb_closed, open_kb)

    outcome = {}

    def _run():
        try:
            if mode == "think":
                think(open_kb, rules_closed)
            else:
                applyRules(open_kb, rules_closed)
            closure_closed = open_kb.close()
            keys = _triple_keys(closure_closed)
            inconsistent = any(LOG_FALSE_URI in t for t in keys)
            # ``testIncludes`` est une simple inclusion : le moteur CWM
            # n'implémente pas l'explosion. Sémantique classique : une
            # clôture incohérente (``log:false``) entraîne TOUTE
            # conclusion (*ex falso quodlibet*) — l'applique ici, avec
            # ``inconsistent: true`` pour que l'interface signale que
            # le oui est vide.
            entails = bool(testIncludes(closure_closed, concl_closed))
            if inconsistent:
                entails = True
            outcome["entails"] = entails
            outcome["statements"] = len(keys)
            outcome["inconsistent"] = inconsistent
        except Exception as e:
            outcome["error"] = "erreur interne : %s: %s" % (type(e).__name__, e)

    start = time.monotonic()
    if timeout > 0:
        worker = threading.Thread(target=_run, daemon=True)
        worker.start()
        worker.join(timeout)
        if worker.is_alive():
            return _entail_result(
                timeout=True,
                errors=[{
                    "doc": "rules", "line": 0, "column": 0,
                    "message": "timeout après %g s : la clôture ne converge "
                               "pas (règle récursive produisant sans fin ?)"
                               % timeout,
                }],
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )
    else:
        _run()
    elapsed_ms = int((time.monotonic() - start) * 1000)
    if "entails" not in outcome:
        return _entail_result(errors=[{
            "doc": "rules", "line": 0, "column": 0,
            "message": outcome.get("error", "erreur interne inconnue"),
        }], elapsed_ms=elapsed_ms)
    return _entail_result(entails=outcome["entails"],
                          inconsistent=outcome["inconsistent"],
                          closure_statements=outcome["statements"],
                          elapsed_ms=elapsed_ms)


def _prove_result(errors=None, timeout=False, proof=None,
                  closure_statements=0, elapsed_ms=0):
    return {
        "ok": errors is None and not timeout,
        "errors": errors or [],
        "timeout": timeout,
        "proof": proof,
        "closure_statements": closure_statements,
        "elapsed_ms": elapsed_ms,
    }


def prove(kb_text, rules_text, base_uri=DEFAULT_BASE_URI,
          mode="think", timeout=10.0):
    """« Pourquoi ? » — génération de la **preuve** (N3) de la clôture
    des données + règles.

    Même flux que ``cwm --think --why`` :

    1. le suivi du raisonnement est activé (``diag.tracking``) ;
    2. les documents sont parsés dans une formule de travail
       (``newTopLevelFormula``) — chaque document devient une étape
       ``:Parsing`` dont la ``:source`` est une **URI ``data:``**
       (le texte intégral du document est embarqué dans la preuve) ;
    3. ``think()`` / ``applyRules()`` ;
    4. fermeture, puis ``explainFormula()`` qui transforme le
       raisonnement suivi en preuve (racine ``reason:Proof``, étapes
       ``:Inference`` avec règles et bindings, ``:Extraction``, …) ;
    5. sérialisation ``ToN3`` avec les drapeaux ``"qdr"`` (URIs
       absolues, **pas d'espace de noms par défaut** — celui-ci est
       écrit relativement à la base, ce qui casserait la
       re-vérification depuis un autre emplacement).

    La preuve est donc **auto-suffisante** : ``check`` peut la
    re-vérifier depuis n'importe quel emplacement (il recharge les
    sources ``:Parsing`` par URI — les ``data:`` URIs ne pointent
    nulle part).

    La génération entière tourne dans un thread **démon** (même
    timeout que :func:`infer`) : une règle non convergente ne bloque
    jamais le TP.

    Renvoie un dictionnaire JSON-serialisable :

    - ``ok``, ``errors`` (taguées ``"kb"`` / ``"rules"``), ``timeout``
      — comme :func:`infer` ;
    - ``proof`` (str ou None) : la preuve en N3 (``None`` en cas
      d'échec/timeout) ;
    - ``closure_statements`` (int) : nb d'énoncés de la clôture
      (la formule prouvée) ;
    - ``elapsed_ms`` (int).
    """
    if mode not in ("think", "once"):
        return _prove_result(errors=[{
            "doc": "rules", "line": 0, "column": 0,
            "message": "mode inconnu : %r (attendu : \"think\" ou \"once\")" % mode,
        }])
    try:
        timeout = float(timeout)
    except (TypeError, ValueError):
        timeout = 10.0
    if timeout < 0:
        timeout = 0.0

    from swap.reasoner.why import (BecauseOfCommandLine, explainFormula,
                                   newTopLevelFormula)
    from swap.query.query import applyRules, think

    # Syntaxe vérifiée d'abord (sans suivi) : les erreurs de parse
    # remontent propres (ligne/colonne), avant toute génération.
    setVerbosity(0)
    store = llyn.RDFStore()
    formula = store.newFormula(base_uri + "#_work")
    parser = notation3.SinkParser(store, formula, thisDoc=base_uri)
    try:
        parser.startDoc()
        parser.feed(kb_text.encode("utf-8"))
        parser.endDoc()
        formula.close()
    except BadSyntax as e:
        line, column = _position(e)
        return _prove_result(errors=[{
            "doc": "kb", "line": line, "column": column, "message": e._why,
        }])
    except Exception as e:
        return _prove_result(errors=[{
            "doc": "kb", "line": 0, "column": 0,
            "message": "erreur interne : %s: %s" % (type(e).__name__, e),
        }])
    rules_formula = store.newFormula(base_uri + "#_rules")
    parser = notation3.SinkParser(store, rules_formula, thisDoc=base_uri)
    try:
        parser.startDoc()
        parser.feed(rules_text.encode("utf-8"))
        parser.endDoc()
        rules_formula.close()
    except BadSyntax as e:
        line, column = _position(e)
        return _prove_result(errors=[{
            "doc": "rules", "line": line, "column": column, "message": e._why,
        }])
    except Exception as e:
        return _prove_result(errors=[{
            "doc": "rules", "line": 0, "column": 0,
            "message": "erreur interne : %s: %s" % (type(e).__name__, e),
        }])

    outcome = {}
    token = object()

    def _gen():
        _tracking_begin(token)
        try:
            pstore = llyn.RDFStore()
            wc = pstore.newFormula(base_uri + "#_work")
            newTopLevelFormula(wc)
            wc.stayOpen = 1
            wc.isWorkingContext = True
            cmd = BecauseOfCommandLine(
                "lab-tp (CWM 2.0) — %s : données + règles"
                % ("convergence" if mode == "think" else "1 passe"))
            p = notation3.SinkParser(pstore, wc, thisDoc=_data_uri(kb_text),
                                     why=cmd)
            p.startDoc()
            p.feed(kb_text.encode("utf-8"))
            p.endDoc()
            if rules_text.strip():
                p = notation3.SinkParser(pstore, wc,
                                         thisDoc=_data_uri(rules_text),
                                         why=cmd)
                p.startDoc()
                p.feed(rules_text.encode("utf-8"))
                p.endDoc()
            if mode == "think":
                think(wc)
            else:
                applyRules(wc)
            wc.stayOpen = False
            wc = wc.close()
            proof = explainFormula(wc)
            buf = io.StringIO()
            pstore.dumpNested(proof, notation3.ToN3(buf.write, base=base_uri,
                                                    quiet=1, flags="qdr"))
            outcome["proof"] = buf.getvalue()
            outcome["statements"] = len(_triple_keys(wc))
        except Exception as e:
            outcome["error"] = "erreur interne : %s: %s" % (type(e).__name__, e)
        finally:
            _tracking_end(token)

    start = time.monotonic()
    if timeout > 0:
        worker = threading.Thread(target=_gen, daemon=True)
        worker.start()
        worker.join(timeout)
        if worker.is_alive():
            # Le thread abandonné reste bloqué dans sa think() —
            # marquer la génération comme abandonnée et réinitialiser
            # le suivi, sans quoi tout parse ultérieur sans ``why=``
            # échouerait (voir le garde ``_tracking_guard`` en tête
            # de section).
            _tracking_abort(token)
            return _prove_result(
                timeout=True,
                errors=[{
                    "doc": "rules", "line": 0, "column": 0,
                    "message": "timeout après %g s : la clôture ne converge "
                               "pas (règle récursive produisant sans fin ?)"
                               % timeout,
                }],
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )
    else:
        _gen()
    elapsed_ms = int((time.monotonic() - start) * 1000)
    if "proof" not in outcome:
        return _prove_result(errors=[{
            "doc": "rules", "line": 0, "column": 0,
            "message": outcome.get("error", "erreur interne inconnue"),
        }], elapsed_ms=elapsed_ms)
    return _prove_result(proof=outcome["proof"],
                         closure_statements=outcome["statements"],
                         elapsed_ms=elapsed_ms)


#: Code de sortie de ``check`` quand la preuve est **invalide**
#: (``sys.exit(-1)`` → 255 sur POSIX). 0 = valide ; 2 = erreur de
#: ligne de commande ; 1 = autre erreur (preuve non parsable, …).
_CHECK_INVALID_EXIT = 255


def _parse_check_report(stdout):
    """``(étapes, formule_prouvée)`` depuis la sortie de
    ``check --report``.

    La sortie standard contient d'abord les étapes de dérivation
    numérotées (par bloc : ``N: <énoncé>`` + ligne(s)
    ``[by …]``), puis — en cas de succès — le N3 de la formule
    prouvée, écrit par ``check`` en fin de sortie. La première ligne
    non vide qui n'est ni une étape ni une ligne ``[by …]`` marque
    donc le début de la formule prouvée.
    """
    steps, current = [], None
    proved_lines = []
    in_proved = False
    for line in stdout.splitlines():
        if in_proved:
            proved_lines.append(line)
            continue
        m = re.match(r"^(\d+): (.*)$", line)
        if m:
            current = {"no": int(m.group(1)), "statement": m.group(2),
                       "how": ""}
            steps.append(current)
            continue
        if re.match(r"^\s*(\[|with bindings)", line):
            if current is not None and line.strip():
                current["how"] = (current["how"] + " " + line.strip()).strip()
            continue
        if not line.strip():
            continue
        in_proved = True
        proved_lines.append(line)
    proved = "\n".join(proved_lines).strip()
    return steps, (proved or None)


def _check_result(errors=None, valid=None, reason=None, steps=None,
                  proved=None, elapsed_ms=0):
    return {
        "ok": errors is None,
        "errors": errors or [],
        "valid": valid,
        "reason": reason,
        "steps": steps or [],
        "proved": proved,
        "elapsed_ms": elapsed_ms,
    }


def check_proof(proof_text, timeout=30.0):
    """« Vérifier la preuve » — re-vérification d'une preuve (N3) par
    le programme ``check`` de CWM (``python -m swap.check --report``,
    en **subprocess** — risque #4 ROADMAP : ``check`` manipule
    ``sys.argv``/``stdin``, jamais in-process).

    ``check`` rejoue la dérivation : chaque étape ``:Parsing``
    recharge sa source par URI (les sources ``data:`` rendent la
    preuve auto-suffisante), chaque ``:Inference`` ré-applique la
    règle aux étapes qui l'étaient, et la conclusion est comparée à
    celle présentée. Codes de sortie : 0 = valide ; 255 = invalide
    (``Proof invalid: …`` sur stderr) ; 1 = autre erreur — en
    particulier une preuve qui ne se parse plus en N3 (le cas d'une
    preuve altérée à la main).

    L'option ``--report`` fait imprimer les étapes de dérivation
    numérotées, renvoyées en liste de ``{"no", "statement", "how"}`` ;
    en cas de succès, le N3 de la formule prouvée est aussi renvoyé
    (``proved``).

    Le subprocess tourne à la racine du dépôt (même code CWM que le
    moteur) et est interrompu après ``timeout`` secondes (une preuve
    pathologique ne bloque jamais le TP).

    Renvoie un dictionnaire JSON-serialisable :

    - ``ok`` (bool) : le processus ``check`` s'est terminé normalement
      (``False`` si la preuve ne se parse pas, timeout, …) ;
    - ``errors`` (list) : ``{"line", "column", "message"}`` ;
    - ``valid`` (bool ou None) : ``True`` = preuve valide, ``False`` =
      preuve invalide (dérivation non rejouable), ``None`` =
      vérification impossible (preuve non parsable, timeout) ;
    - ``reason`` (str ou None) : la raison du rejet
      (``Proof invalid: …``) ;
    - ``steps`` (list) : étapes de dérivation (``--report``) ;
    - ``proved`` (str ou None) : N3 de la formule prouvée (succès) ;
    - ``elapsed_ms`` (int).
    """
    try:
        timeout = float(timeout)
    except (TypeError, ValueError):
        timeout = 30.0
    if timeout <= 0:
        timeout = 30.0

    if not proof_text.strip():
        return _check_result(errors=[{
            "line": 0, "column": 0,
            "message": "preuve vide : générez d'abord une preuve "
                       "(bouton « Pourquoi ? »)",
        }])

    tmp = tempfile.mkdtemp(prefix="cwm-tp-proof.")
    start = time.monotonic()
    try:
        path = os.path.join(tmp, "proof.n3")
        with open(path, "w", encoding="utf-8") as f:
            f.write(proof_text)
        try:
            r = subprocess.run(
                [sys.executable, "-m", "swap.check", "--report", path],
                capture_output=True, text=True, cwd=REPO_ROOT,
                timeout=timeout)
        except subprocess.TimeoutExpired:
            return _check_result(errors=[{
                "line": 0, "column": 0,
                "message": "timeout après %g s : la vérification de la "
                           "preuve n'a pas terminé (preuve pathologique ?)"
                           % timeout,
            }], elapsed_ms=int((time.monotonic() - start) * 1000))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    elapsed_ms = int((time.monotonic() - start) * 1000)

    steps, proved = _parse_check_report(r.stdout)

    if r.returncode == 0:
        return _check_result(valid=True, steps=steps, proved=proved,
                             elapsed_ms=elapsed_ms)
    if r.returncode == _CHECK_INVALID_EXIT:
        m = re.search(r"^Proof invalid: (.*)$", r.stderr, re.M | re.S)
        reason = " ".join((m.group(1) if m else r.stderr).split())
        if len(reason) > 600:
            reason = reason[:597] + "…"
        return _check_result(valid=False,
                             reason=reason or "preuve invalide",
                             steps=steps, elapsed_ms=elapsed_ms)
    # autres codes : 1 = preuve non parsable / erreur interne,
    # 2 = ligne de commande, …
    first = next((ln.strip() for ln in r.stderr.splitlines() if ln.strip()),
                 "erreur inconnue (exit %d)" % r.returncode)
    if "Failed to parse" in r.stderr:
        message = ("la preuve ne se parse plus comme du N3 "
                   "(preuve altérée ?) : " + first)
    else:
        message = "check a échoué : " + first
    return _check_result(errors=[{"line": 0, "column": 0, "message": message}],
                         valid=None, steps=steps, elapsed_ms=elapsed_ms)


# ----------------------------------------------------------------------
# P7 — rendu Markdown des énoncés (convertisseur minimal, stdlib)
# ----------------------------------------------------------------------

#: Titres de niveau 1 à 3.
_MD_HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)$")
#: Ligne de tableau (cellules séparées par « | »).
_MD_TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
#: Contenu de la ligne de séparation d'un tableau (``---|---`` — la
#: ligne complète est ``|---|---|``, les pipes aux bords étant coupés).
_MD_TABLE_SEP_RE = re.compile(r"^\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*$")
#: Élément de liste à puces (``-`` ou ``*``).
_MD_UL_ITEM_RE = re.compile(r"^(\s*)[-*]\s+(.*)$")
#: Élément de liste numérotée (``1.``).
_MD_OL_ITEM_RE = re.compile(r"^(\s*)\d+\.\s+(.*)$")
#: Code en ligne (``…``).
_MD_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
#: Gras (``**…**``) puis italique (``*…*``).
_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_MD_ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")


def _md_inline(text):
    """Balises inline sur du texte **déjà échappé** : code en ligne,
    gras, italique (le code est protégé en premier)."""
    codes = []

    def _stash_code(m):
        codes.append("<code>%s</code>" % m.group(1))
        return "\x00%d\x00" % (len(codes) - 1)

    text = _MD_INLINE_CODE_RE.sub(_stash_code, text)
    text = _MD_BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = _MD_ITALIC_RE.sub(r"<em>\1</em>", text)
    for i, code in enumerate(codes):
        text = text.replace("\x00%d\x00" % i, code)
    return text


def _md_table(rows):
    """Blocs de tableaux GFM (``| … |``) : la 2e ligne (``|---|``) est
    la séparation — les colonnes de la 1re ligne sont l'en-tête."""
    out = ["<table>"]
    if len(rows) >= 2 and _MD_TABLE_SEP_RE.match(rows[1]):
        out.append("<thead><tr>"
                   + "".join("<th>%s</th>" % _md_inline(c.strip())
                             for c in rows[0].split("|"))
                   + "</tr></thead>")
        body = rows[2:]
    else:
        body = rows
    if body:
        out.append("<tbody>")
        for row in body:
            out.append("<tr>" + "".join("<td>%s</td>" % _md_inline(c.strip())
                                        for c in row.split("|")) + "</tr>")
        out.append("</tbody>")
    out.append("</table>")
    return "\n".join(out)


def _md_list(items):
    """Liste à puces ou numérotée, avec imbrication par retrait :
    ``items`` est une liste de ``(indent, texte, « ul » | « ol »)``.
    Une liste imbriquée reste **dans** le ``<li>`` de son parent
    (laissé ouvert jusqu'au retour à l'indent parent) ; un
    changement de type (puces → numéroté) à indent égal ouvre une
    liste nouvelle, sibling de la précédente."""
    out = []
    stack = []      # (indent, balise) des listes ouvertes
    li_open = False

    def close_deeper(target):
        """Ferme les listes plus profondes que ``target`` — le
        ``<li>`` parent n'est refermé que si l'on revient à son
        indent (sinon il reste ouvert pour la nouvelle imbrication)."""
        nonlocal li_open
        while stack and target < stack[-1][0]:
            if li_open:
                out.append("</li>")
                li_open = False
            out.append("</%s>" % stack[-1][1])
            stack.pop()
            if stack and target == stack[-1][0]:
                out.append("</li>")
                li_open = False

    for indent, text, kind in items:
        tag = "ol" if kind == "ol" else "ul"
        close_deeper(indent)
        if stack and indent == stack[-1][0] and stack[-1][1] != tag:
            # changement de type : on ferme cette liste…
            if li_open:
                out.append("</li>")
                li_open = False
            out.append("</%s>" % stack[-1][1])
            stack.pop()
            close_deeper(indent)
            # …et le ``<li>`` parent (si plus court) reste ouvert
            if stack and indent == stack[-1][0]:
                out.append("</li>")
                li_open = False
        if not stack or indent > stack[-1][0]:
            # liste imbriquée (dans le ``<li>`` courant, resté ouvert)
            out.append("<%s>" % tag)
            stack.append((indent, tag))
        elif li_open:
            out.append("</li>")
            li_open = False
        out.append("<li>%s" % _md_inline(text))
        li_open = True
    # fin de la liste : tout se ferme (chaque liste fermée referme le
    # ``<li>`` parent dans lequel elle était imbriquée)
    while stack:
        if li_open:
            out.append("</li>")
            li_open = False
        out.append("</%s>" % stack[-1][1])
        stack.pop()
        if stack:
            out.append("</li>")
            li_open = False
    return "\n".join(out)


def render_markdown(text):
    """Convertisseur **minimal** du Markdown des énoncés vers HTML
    (P7 — les énoncés restent des ``.md`` dans le dépôt, source de
    vérité ; l'appli les affiche rendus).

    Sous-ensemble supporté (celui des énoncés du pack TP) : titres
    ``#``/``##``/``###``, listes à puces et numérotées (un niveau
    d'imbrication), tableaux (``| … |``), blocs de code ``` ``` ``` ``,
    ``**gras**``, ``*italique*``, ``code en ligne``. Le texte est
    **d'abord échappé** (HTML) : aucun fragment de Markdown ne peut
    injecter de balise. Le reste est rendu tel quel (paragraphes).
    ``quote=False`` : les guillemets ne sont pas échappés (inutiles
    dans du texte, ça évite des ``&#x27;`` dans le rendu).
    """
    text = html_escape(text.replace("\r\n", "\n"), quote=False)
    lines = text.split("\n")
    out = []
    para = []
    codes = []

    def flush_para():
        if para:
            out.append("<p>%s</p>" % " ".join(
                _md_inline(l.strip()) for l in para if l.strip()))
            del para[:]

    i = 0
    while i < len(lines):
        line = lines[i]
        # bloc de code ```
        if line.strip().startswith("```"):
            flush_para()
            block = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            # le texte a été échappé au démarrage (pas de double échappement)
            codes.append("<pre><code>%s</code></pre>"
                         % "\n".join(block))
            out.append("\x00%d\x00" % (len(codes) - 1))
            i += 1
            continue
        stripped = line.strip()
        if not stripped:
            flush_para()
            i += 1
            continue
        # titre
        m = _MD_HEADING_RE.match(stripped)
        if m:
            flush_para()
            level = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (level, _md_inline(m.group(2)), level))
            i += 1
            continue
        # tableau (bloc de lignes « | … | » consécutives)
        if _MD_TABLE_ROW_RE.match(line):
            flush_para()
            rows = []
            while i < len(lines) and _MD_TABLE_ROW_RE.match(lines[i]):
                rows.append(_MD_TABLE_ROW_RE.match(lines[i]).group(1))
                i += 1
            out.append(_md_table(rows))
            continue
        # liste (puces ou numérotée) — bloc d'éléments consécutifs
        ul = _MD_UL_ITEM_RE.match(line)
        ol = _MD_OL_ITEM_RE.match(line)
        if ul or ol:
            flush_para()
            items = []
            while i < len(lines):
                mu = _MD_UL_ITEM_RE.match(lines[i])
                mo = _MD_OL_ITEM_RE.match(lines[i])
                if mu:
                    items.append((len(mu.group(1)), mu.group(2), "ul"))
                    i += 1
                    continue
                if mo:
                    items.append((len(mo.group(1)), mo.group(2), "ol"))
                    i += 1
                    continue
                break
            out.append(_md_list(items))
            continue
        # paragraphe (lignes consécutives sans balise)
        para.append(stripped)
        i += 1
    flush_para()
    html = "\n".join(out)
    for n, block in enumerate(codes):
        html = html.replace("\x00%d\x00" % n, block)
    return html


# ----------------------------------------------------------------------
# P5 — pack TP : exercices
# ----------------------------------------------------------------------

#: Dossier des exercices (``exercises/``). Chaque exercice est un
#: sous-dossier contenant :
#:
#: - ``enonce.md``    : l'énoncé (obligatoire) — son premier titre
#:   ``# …`` sert de libellé ;
#: - ``*.n3``         : les fichiers de données — ``regles.n3`` va dans
#:   l'éditeur « règles », les autres sont concaténés (ordre
#:   alphabétique) dans l'éditeur « données » ;
#: - ``context.json`` : préchargements optionnels des éditeurs
#:   (« requête » / « conclusion ») : ``{"query": …, "conclusion": …,
#:   "base_uri": …}``.
EXERCISES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exercises")


def _exercise_error(message, name=None):
    return {"ok": False, "errors": [{"doc": "exercise", "line": 0,
                                     "column": 0, "message": message}],
            "name": name}


def list_exercises():
    """Liste les exercices disponibles (sous-dossiers de
    :data:`EXERCISES_DIR` portant un ``enonce.md``), par ordre
    alphabétique.

    Renvoie ``{"ok": True, "exercises": [{"name", "title", "files"},
    …]}`` — ``title`` est le premier titre ``# …`` de l'énoncé,
    ``files`` le nombre de fichiers ``.n3``.
    """
    exercises = []
    if os.path.isdir(EXERCISES_DIR):
        for name in sorted(os.listdir(EXERCISES_DIR)):
            d = os.path.join(EXERCISES_DIR, name)
            if name.startswith(".") or not os.path.isdir(d):
                continue
            enonce = os.path.join(d, "enonce.md")
            if not os.path.isfile(enonce):
                continue
            title = name
            try:
                with open(enonce, encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("# "):
                            title = line[2:].strip()
                            break
            except OSError:
                pass
            n3 = [f for f in os.listdir(d) if f.endswith(".n3")]
            exercises.append({"name": name, "title": title, "files": len(n3)})
    return {"ok": True, "exercises": exercises}


def load_exercise(name):
    """Charge un exercice dans les éditeurs (voir la convention de
    :data:`EXERCISES_DIR`).

    ``name`` est validé (pas de séparateur de chemin, pas de ``..``) —
    anti-traversée de dossier, comme le service des statiques. Les
    données et règles de l'exercice sont **validées par parse** avant
    d'être renvoyées : un exercice cassé ne se charge pas dans les
    éditeurs (message d'erreur tagué par document).

    Renvoie un dictionnaire JSON-serialisable : ``ok``, ``errors``
    (``{"doc": "kb" | "rules" | "query" | "concl" | "exercise",
    "line", "column", "message"}``), ``name``, ``title``, ``enonce``
    (texte de l'énoncé), ``kb``, ``rules``, ``query`` (str ou None),
    ``conclusion`` (str ou None), ``base_uri`` (str ou None).
    """
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name or ""):
        return _exercise_error("nom d'exercice invalide : %r" % name)
    d = os.path.realpath(os.path.join(EXERCISES_DIR, name))
    if not d.startswith(os.path.realpath(EXERCISES_DIR) + os.sep) or \
       not os.path.isdir(d):
        return _exercise_error("exercice inconnu : %r" % name, name=name)
    enonce_path = os.path.join(d, "enonce.md")
    if not os.path.isfile(enonce_path):
        return _exercise_error(
            "l'exercice %r n'a pas d'énoncé (enonce.md)" % name, name=name)
    try:
        with open(enonce_path, encoding="utf-8") as f:
            enonce = f.read()
    except OSError as e:
        return _exercise_error("impossible de lire l'énoncé : %s" % e,
                               name=name)

    files = sorted(f for f in os.listdir(d) if f.endswith(".n3"))
    if not files:
        return _exercise_error(
            "l'exercice %r n'a aucun fichier .n3" % name, name=name)
    try:
        kb = "".join(open(os.path.join(d, f), encoding="utf-8").read() + "\n"
                     for f in files if f != "regles.n3")
        rules = "".join(open(os.path.join(d, f), encoding="utf-8").read() + "\n"
                        for f in files if f == "regles.n3")
    except OSError as e:
        return _exercise_error("impossible de lire les fichiers : %s" % e,
                               name=name)

    # préchargements optionnels (context.json)
    query = conclusion = base_uri = None
    ctx_path = os.path.join(d, "context.json")
    if os.path.isfile(ctx_path):
        try:
            with open(ctx_path, encoding="utf-8") as f:
                ctx = json.load(f)
        except (OSError, ValueError) as e:
            return _exercise_error("context.json illisible : %s" % e,
                                   name=name)
        query = ctx.get("query")
        conclusion = ctx.get("conclusion")
        base_uri = ctx.get("base_uri")

    # validation : un exercice cassé ne se charge pas
    for doc, text, language in (("kb", kb, "n3"), ("rules", rules, "n3"),
                                ("query", query, "sparql"),
                                ("concl", conclusion, "n3")):
        if not text or not text.strip():
            continue
        p = parse(text, language=language)
        if not p["ok"]:
            return {"ok": False, "name": name, "errors": [
                dict(e, doc=doc) for e in p["errors"]]}

    title = name
    for line in enonce.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    return {"ok": True, "errors": [], "name": name, "title": title,
            "enonce": enonce,
            "enonce_html": render_markdown(enonce),  # P7 : rendu HTML
            "kb": kb, "rules": rules, "query": query,
            "conclusion": conclusion, "base_uri": base_uri}


# ----------------------------------------------------------------------
# P5 — visualisation du graphe (vis.js)
# ----------------------------------------------------------------------

#: Nombre maximum de triples envoyés au navigateur. vis-network reste
#: fluide en deçà ; au-delà le graphe est tronqué (signalé par
#: ``truncated``) plutôt que de geler l'onglet.
_GRAPH_MAX_TRIPLES = 3000

#: Libellé court de ``rdf:type`` dans le graphe (convention Turtle).
_RDF_TYPE_URI = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


def _short_uri(uri):
    """Libellé court d'une URI : le fragment si présent, sinon le
    dernier segment du chemin, sinon l'URI entière (tronquée à 40
    caractères)."""
    frag = uri.rsplit("#", 1)[-1]
    seg = frag.rsplit("/", 1)[-1]
    label = seg if seg else uri
    return label if len(label) <= 40 else label[:37] + "…"


def _term_kind(term):
    """Nature d'un terme pour la visualisation : ``"resource"``
    (``Symbol``/``Fragment``), ``"literal"`` ou ``"blank"`` (tout le
    reste — nœud vide, et variables s'il en restait après clôture)."""
    if isinstance(term, (Symbol, Fragment)):
        return "resource"
    if isinstance(term, Literal):
        return "literal"
    return "blank"


def _term_label(term, kind):
    """Libellé court d'un terme (plein libellé dans ``title``)."""
    if kind == "resource":
        return _short_uri(term.uriref())
    if kind == "literal":
        # value() peut renvoyer un int/float (littéral numérique)
        value = term.value()
        value = value if isinstance(value, str) else str(term)
        return value if len(value) <= 30 else value[:27] + "…"
    return str(term)


def _term_title(term, kind):
    if kind == "literal":
        value = term.value()
        return value if isinstance(value, str) else str(term)
    return str(term)


def _graph_statements(formula):
    """Énoncés de niveau supérieur de ``formula`` en liste de
    ``(sujet, prédicat, objet)`` — termes, pas chaînes. Les
    énoncés-règles (prédicat ``log:implies``) sont exclus : ils ne
    sont pas des faits."""
    out = []
    for s in formula.statements:
        pred = s[1]
        if isinstance(pred, (Symbol, Fragment)) and \
           pred.uriref() == IMPLIES_URI:
            continue
        out.append((s[2], pred, s[3]))
    return out


def graph(kb_text, rules_text, base_uri=DEFAULT_BASE_URI, reason=False,
          mode="think", timeout=10.0, hide_literals=False):
    """Graphe des triples de la KB — et, si ``reason``, de sa clôture.

    Même parse que :func:`infer` : ``kb_text`` dans une formule,
    ``rules_text`` dans une seconde (même store). Si ``reason`` est
    vrai, les règles sont appliquées (``mode`` ``"think"``/``"once"``,
    timeout en thread démon) et les nœuds/arcs **nouveaux** (absents
    des données d'origine) sont marqués ``inferred``.

    Si ``hide_literals`` est vrai (P7, mode « attributs masqués »),
    les nœuds-littéraux sont **supprimés du rendu** : leurs énoncés
    (``sujet prédicat littéral``) sont regroupés en **attributs** sur
    le sujet — comptés dans ``attrs`` (pastille) et listés dans la
    ``title`` du sujet (bulle contextuelle). Les autres énoncés
    touchant un littéral sont simplement retirés du rendu.

    Renvoie un dictionnaire JSON-serialisable :

    - ``ok`` (bool), ``errors`` (list, format habituel) ;
    - ``nodes`` : ``[{"id", "label", "kind" ("resource" | "literal" |
      "blank"), "inferred", "title"}, …]`` — ``id`` est la chaîne du
      terme (URI absolue / valeur littérale / nom de nœud vide) ;
    - ``edges`` : ``[{"from", "to", "label", "inferred"}, …]`` — un
      arc par paire (sujet, objet) ; les prédicats multiples entre les
      mêmes termes sont fusionnés dans ``label`` ; ``rdf:type`` se lit
      ``a`` ;
    - ``attrs`` : ``{"id du sujet": ["prédicat valeur", …]}`` — les
      attributs masqués (vide si ``hide_literals`` est faux) ;
    - ``statement_count`` (int) : nb d'énoncés représentés ;
    - ``truncated`` (bool) : le graphe a été coupé à
      :data:`_GRAPH_MAX_TRIPLES` énoncés ;
    - ``elapsed_ms`` (int).
    """
    if mode not in ("think", "once"):
        return {"ok": False,
                "errors": [{"doc": "rules", "line": 0, "column": 0,
                            "message": "mode inconnu : %r" % mode}],
                "nodes": [], "edges": [], "attrs": {}, "statement_count": 0,
                "truncated": False, "elapsed_ms": 0}
    try:
        timeout = float(timeout)
    except (TypeError, ValueError):
        timeout = 10.0
    if timeout < 0:
        timeout = 0.0

    setVerbosity(0)
    store = llyn.RDFStore()
    formula = store.newFormula(base_uri + "#_work")
    parser = notation3.SinkParser(store, formula, thisDoc=base_uri)
    try:
        parser.startDoc()
        parser.feed(kb_text.encode("utf-8"))
        parser.endDoc()
        kb_closed = formula.close()
    except BadSyntax as e:
        line, column = _position(e)
        return {"ok": False, "errors": [{"doc": "kb", "line": line,
                                         "column": column,
                                         "message": e._why}],
                "nodes": [], "edges": [], "attrs": {}, "statement_count": 0,
                "truncated": False, "elapsed_ms": 0}
    except Exception as e:  # toute entrée d'étudiant doit rester gérable
        return {"ok": False, "errors": [{"doc": "kb", "line": 0,
                                         "column": 0,
                                         "message": "erreur interne : "
                                                     "%s: %s"
                                                     % (type(e).__name__, e)}],
                "nodes": [], "edges": [], "attrs": {}, "statement_count": 0,
                "truncated": False, "elapsed_ms": 0}

    raw_stmts = _graph_statements(kb_closed)
    raw_pairs = {(_term_str(s), _term_str(o)) for s, _, o in raw_stmts}
    after_stmts = raw_stmts
    if reason:
        from swap.query.query import applyRules, think

        rules_formula = store.newFormula(base_uri + "#_rules")
        parser = notation3.SinkParser(store, rules_formula,
                                       thisDoc=base_uri)
        try:
            parser.startDoc()
            parser.feed(rules_text.encode("utf-8"))
            parser.endDoc()
            rules_closed = rules_formula.close()
        except BadSyntax as e:
            line, column = _position(e)
            return {"ok": False,
                    "errors": [{"doc": "rules", "line": line,
                                "column": column, "message": e._why}],
                    "nodes": [], "edges": [], "attrs": {}, "statement_count": 0,
                    "truncated": False, "elapsed_ms": 0}
        except Exception as e:
            return {"ok": False,
                    "errors": [{"doc": "rules", "line": 0, "column": 0,
                                "message": "erreur interne : %s: %s"
                                           % (type(e).__name__, e)}],
                    "nodes": [], "edges": [], "attrs": {}, "statement_count": 0,
                    "truncated": False, "elapsed_ms": 0}

        open_kb = store.newFormula(base_uri + "#_closure")
        store.copyFormula(kb_closed, open_kb)
        start = time.monotonic()
        if timeout > 0:
            def _run():
                if mode == "think":
                    think(open_kb, rules_closed)
                else:
                    applyRules(open_kb, rules_closed)

            worker = threading.Thread(target=_run, daemon=True)
            worker.start()
            worker.join(timeout)
            if worker.is_alive():
                return {"ok": False, "timeout": True,
                        "errors": [{"doc": "rules", "line": 0,
                                    "column": 0,
                                    "message": "timeout après %g s : la "
                                               "clôture ne converge pas"
                                               % timeout}],
                        "nodes": [], "edges": [], "attrs": {}, "statement_count": 0,
                        "truncated": False,
                        "elapsed_ms": int((time.monotonic() - start) * 1000)}
        else:
            if mode == "think":
                think(open_kb, rules_closed)
            else:
                applyRules(open_kb, rules_closed)
        after_stmts = _graph_statements(open_kb)
    else:
        start = time.monotonic()

    # Nœuds : identifiés par la chaîne du terme. ``inferred`` = le
    # terme n'apparaît dans AUCUN énoncé des données d'origine (il a
    # été créé par les règles) — un nœud existant lié par un arc
    # inféré ne devient PAS inféré lui-même.
    raw_terms = set()
    for s, _, o in raw_stmts:
        raw_terms.add(_term_str(s))
        raw_terms.add(_term_str(o))
    nodes = {}

    def _node(term):
        tstr = _term_str(term)
        node = nodes.get(tstr)
        if node is None:
            kind = _term_kind(term)
            nodes[tstr] = node = {
                "id": tstr,
                "label": _term_label(term, kind),
                "kind": kind,
                "inferred": bool(reason and tstr not in raw_terms),
                "title": _term_title(term, kind),
            }
        return tstr

    # Énoncés (s, p, o) triés pour une troncature déterministe.
    triples = sorted(after_stmts,
                     key=lambda t: (_term_str(t[0]), _term_str(t[2])))
    truncated = len(triples) > _GRAPH_MAX_TRIPLES
    triples = triples[:_GRAPH_MAX_TRIPLES]

    # Un arc par paire (s, o) ; les prédicats multiples entre les
    # mêmes termes sont fusionnés dans le libellé.
    grouped = {}
    order = []
    for s, pred, o in triples:
        so = (_term_str(s), _term_str(o))
        if so not in grouped:
            grouped[so] = {"s": s, "o": o, "preds": []}
            order.append(so)
        grouped[so]["preds"].append(pred)

    def _is_literal(term):
        return _term_kind(term) == "literal"

    edges = []
    attrs = {}  # P7 : attributs masqués — id du sujet → [libellés]
    for so in order:
        g = grouped[so]
        s, o = g["s"], g["o"]
        s_lit, o_lit = _is_literal(s), _is_literal(o)
        if hide_literals and (s_lit or o_lit):
            if o_lit and not s_lit:
                # énoncé « sujet prédicat littéral » : regroupé en
                # attribut (pastille) sur le sujet
                s_id = _node(s)
                value = _term_str(o)
                for pred in g["preds"]:
                    pstr = _term_str(pred)
                    lab = ("type" if pstr == _RDF_TYPE_URI
                           else _short_uri(pstr))
                    item = lab + " " + value
                    if item not in attrs.setdefault(s_id, []):
                        attrs[s_id].append(item)
            continue  # pas d'arc vers/depuis un littéral masqué
        inferred = reason and so not in raw_pairs
        s_id = _node(s)
        o_id = _node(o)
        if s_id == o_id:
            continue  # boucle dégénérée, peu lisible
        labels = []
        for pred in g["preds"]:
            pstr = _term_str(pred)
            lab = "a" if pstr == _RDF_TYPE_URI else _short_uri(pstr)
            if lab not in labels:
                labels.append(lab)
        edges.append({"from": s_id, "to": o_id,
                      "label": " · ".join(labels), "inferred": inferred})

    # P7 : la bulle contextuelle du sujet liste les attributs masqués
    for node_id, items in attrs.items():
        nodes[node_id]["title"] += (
            "\n\n%d attribut%s masqué%s :\n%s"
            % (len(items), "s" if len(items) > 1 else "",
               "s" if len(items) > 1 else "", "\n".join(items)))

    return {
        "ok": True,
        "errors": [],
        "nodes": [nodes[k] for k in sorted(nodes)],
        "edges": edges,
        "attrs": attrs,
        "statement_count": len(triples),
        "truncated": truncated,
        "elapsed_ms": int((time.monotonic() - start) * 1000),
    }
