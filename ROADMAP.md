# Feuille de route — CWM Lab (cwm-lab)

> Outil de TP (Master MIAGE) sur la **cohérence**, la **validité** et
> les **règles**, construit sur CWM 2.0.
>
> **Projet autonome** (2026-11-23) : l'outil a quitté le dépôt CWM
> (où il vivait dans `lab/`) pour son propre dépôt
> [edesmontils/cwm-lab](https://github.com/edesmontils/cwm-lab) —
> CWM 2.0 (fork) est désormais l'unique **dépendance** (PyPI :
> `cwm` ; en attendant, dépôt GitLab public). Les chemins des phases
> ci-dessous (`lab/`, `lab_web/`, `make test-lab`) sont ceux de
> l'emplacement historique ; le projet s'appelle maintenant
> `cwm-lab`, le paquet `cwm_lab`, et les cibles `make test` /
> `make serve`.
>
> Décisions actées (2026-11-21) :
>
> | Décision | Choix |
> |---|---|
> | Architecture | **Web app locale** : backend Python stdlib (`http.server` + JSON) + navigateur |
> | Édition | **CodeMirror 6** (vendu en local, pas de CDN) avec coloration N3/Turtle |
> | Emplacement | `lab/` à la racine du dépôt CWM (→ projet autonome `cwm-lab` le 2026-11-23) |
> | Public | Master MIAGE |
> | Dépendances | **Aucune ajoutée** au dépôt CWM (politique du repo) → CWM 2.0 en dépendance unique du projet autonome |

## 1. Concepts du TP ↔ capacités CWM 2.0

| Concept du TP | Capacité CWM 2.0 | Point d'entrée API |
|---|---|---|
| Syntaxe N3/Turtle | Parser Notation3, erreurs **avec ligne/colonne** | `notation3.SinkParser`, `BadSyntax` |
| Validation / stats | Parse + comptage (triples, règles, requêtes, bnodes) | parser + store |
| Règles | Règles N3 `!{ … } -> { … }` (`log:implies`) | `store.implies` |
| Raisonnement (clôture) | Chaînage avant, 1 passe ou convergence | `think()`, `applyRules()` |
| Nouveaux faits | Diff entre KB et clôture | diff d'ensembles (esprit `delta`) |
| **Cohérence** | Monde fermé : contradiction dans la clôture | `false` / `log:notIncludes` (à valider, P2) |
| **Validité** (inférence) | « La KB entraîne-t-elle la conclusion ? » | `testIncludes(f, g)` |
| Requêtes | SPARQL et N3QL, avec ou sans raisonnement préalable | `applySparqlQueries()`, `applyQueries()` |
| Preuves | Génération de la preuve d'une conclusion | `think(why=…)`, `newTopLevelFormula`, `explainFormula` |
| **Vérifier les raisonnements** | Re-vérifier qu'une preuve est une dérivation valide | `swap.cli.check` (subprocess) |
| Sérialisations | N3, Turtle, RDF/XML, NTriples | `swap.serialize` |

Parcours pédagogique : **parser → raisonner → détecter l'incohérence →
interroger (avec/sans raisonnement) → vérifier la validité → produire et
vérifier la preuve**.

## 2. Layout du tableau de bord

```
┌──────────────────────────────────────────────────────────────────────┐
│ [Parse] [Raisonner] [Interroger] [Pourquoi ?] [Vérifier la preuve]   │
├──────────────────────────────────┬───────────────────────────────────┤
│ Éditeur 1 — Connaissances        │ Résultats (onglets) :             │
│   (N3/Turtle)                    │  • Syntaxe : erreurs par ligne,   │
│ Éditeur 2 — Règles (N3)          │    stats (N triples, M règles)    │
│ Éditeur 3 — Requête              │  • Nouveaux faits (diff clôture)  │
│   SPARQL / N3QL                  │  • Incohérence (signalement)      │
│   ☐ raisonner avant d'interroger │  • Résultats requête             │
│ Éditeur 4 — Conclusion / Preuve  │    (avec/sans raisonnement, diff) │
│   (N3, preuve colorée)           │  • Preuve + verdict de « check »  │
└──────────────────────────────────┴───────────────────────────────────┘
```

## 3. Phases

### P0 — Socle ✅ (livré le 2026-11-21)

- Dossier `lab/`, paquet `lab_web/` ;
- `engine.py` : wrapper stateless sur les API `swap` — fonction `parse`
  (erreurs ligne/colonne + stats) ;
- `server.py` : `http.server` (threadé) + endpoint `/api/parse` +
  service de `static/` (anti-traversée de dossier) + `/api/version` ;
- page minimale avec un éditeur (textarea ; CodeMirror arrive en P1)
  et un bouton **Parse** ;
- `lab/tests/test_engine.py` : 10 tests, cible `make test-lab`.

**Critère d'acceptation** : un document N3 cassé renvoie l'erreur avec
ligne/colonne ; un document valide renvoie les stats du graphe. ✔

**Faits techniques établis en P0** (à réutiliser dans le TP) :

- La syntaxe de règle du parser CWM est
  **`{ … } log:implies { … } .`** — la syntaxe `!{…} -> {…}` n'est
  supportée par **aucun** parser du dépôt : `notation3` (défaut) ne
  connaît que `log:implies` (et le verbe `=>`) ; le parser
  expérimental `n3p` (chemin alternatif `CWM_N3_PARSER=n3p`) a `!`
  comme opérateur de *chemin* et ses règles s'écrivent `{ … } => { … }` ;
- `@forAll :x , :y , :z .` prend une liste **séparée par virgules** ;
- les erreurs de parse remontent en `BadSyntax` avec la position exacte
  (`_str` / `_i`) ; une erreur d'EOF renvoie la position de fin de
  document ;
- hiérarchie des termes : les nœuds vides du document sont exactement
  les `AnonymousExistential` ; variables `@forAll`
  (`AnonymousUniversal`) et corps/tête de règle (`Formula`) héritent
  aussi de `AnonymousNode` mais ne sont pas des bnodes du document ;
- un bnode `[ … ]` ajoute son propre triple au top level du document
  (compter les énoncés en tête de doc le reflète).

### P1 — Syntaxe & sérialisation ✅ (livrée le 2026-11-22)

- CodeMirror 6 dans `static/vendor/codemirror/` : bundle ES module
  (esbuild, ~430 Ko) + README de provenance + licences (tout est MIT) ;
- coloration N3/Turtle : le paquet npm `codemirror-lang-turtle`
  (parser Lezer : IRIs, préfixes, littéraux, nœuds vides, commentaires)
  + **surcouche en décorations** pour la syntaxe propre à N3 hors
  grammaire Turtle (`@forAll`, `@forSome`, `log:implies`, variables
  `?x`) — le parser Lezer résynchronise proprement dans les formules
  `{ … }`, les triples internes restent colorés ;
- auto-parse au frappage (debounce 500 ms) ; erreurs de parse
  **surlignées dans la gouttière** (linter asynchrone) + panneau ;
- base URI configurable (persistée en `localStorage`) ;
- export N3 / Turtle / RDF/XML / NTriples via `engine.serialize`
  (le Turtle et NTriples sont refusés si le graphe n'est pas du
  RDF pur, comme le fait `--turtle`) ; `POST /api/serialize`.

**Critère d'acceptation** : document cassé → erreur surlignée à la bonne
ligne ; valide → stats ; export Turtle garanti valide. ✔

**Faits techniques établis en P1** (à réutiliser) :

- CodeMirror 6 moderne **n'a plus de CSS à importer** : les styles par
  défaut sont un `StyleModule` (`baseTheme`) compilé et injecté à
  l'exécution par `@codemirror/view` — aucun `*.css` dans les paquets npm ;
- les fonctions du facet `EditorView.decorations` reçoivent le **view**
  (pas l'état) ; `doc.lines` est le *nombre* de lignes, `doc.line(n)`
  (clampé) renvoie la ligne ;
- la gouttière de lint s'installe avec l'extension **séparée**
  `lintGutter()` (pas une option de `linter()`), et la source du linter
  peut être asynchrone — elle attend le parse, ce qui évite toute course
  avec le panneau de résultats (un fetch dédupliqué par contenu est
  partagé entre les deux) ;
- `ToN3` : `dumpNested` (pas `dumpBySubject`) est seul à restituer les
  règles ; drapeaux `qr` (quiet + URIs absolues) pour N3/Turtle,
  `uspartnea` pour NTriples ; l'espace de noms *par défaut* dérivé de la
  base reste relatif même avec `r` (comportement `ToN3` originel,
  identique au CLI cwm) ;
- le serveur envoie `Cache-Control: no-cache` sur les statiques (outil
  de dev : rechargements propres sans versionner les noms de fichiers).

### P2 — Règles & raisonnement ✅ (livrée le 2026-11-22)

- Éditeur 2 (règles N3) — même Coloration/linter/gouttière que l'éditeur
  de données (fabrique d'éditeur commune dans `app.js`) ;
- bouton **Raisonner** → clôture + **liste des nouveaux faits**
  (diff KB → clôture), avec l'option « 1 passe » vs « convergence »
  (`applyRules` vs `think`) et « règles stockées ou non » ;
- **timeout par requête** (thread démont + `join(timeout)`) : une règle
  récursive ne bloque jamais le TP ;
- **détection d'incohérence** : sémantique CWM validée empiriquement —
  la clôture est incohérente si elle contient la constante `log:false`
  (triple canonique `log:false log:false log:false`) ; signal rouge.

**Critère d'acceptation** : exemple famille/ancêtre → nouveaux faits
listés ; règle contradictoire → signal « incohérent » ; règle cyclique
→ timeout propre, pas de blocage. ✔ (les trois scénarios vérifiés en
navigateur, en plus de 9 tests unitaires)

**Faits techniques établis en P2** (à réutiliser) :

- **Les variables de règle doivent être déclarées** `@forAll :x , :y .`
  (ou `?x`) : un `:x` nu est parsé comme **constante** — c'est la cause
  du « 0 nouveau fait » apparent si on oublie la déclaration ;
- `@forAll` ne crée **pas** d'énoncé dans la formule (il n'enregistre
  qu'un terme universel) : les seuls énoncés d'un document de règles
  sont les énoncés-règles `… log:implies …` ;
- **Sémantique de l'incohérence** : une formule est incohérente si sa
  clôture contient `log:false` (`http://www.w3.org/2000/10/swap/log#false`),
  ajoutée par une règle qui conclut `{ log:false log:false log:false }`.
  NB : le mot-clé nu `false` du parser est un *littéral booléen Python*
  **silencieusement ignoré** (`{ false }` → formule vide) — il n'est
  PAS la constante N3 (piège classique des étudiants). `log:notIncludes`
  est un *built-in lourd* (monde fermé, requêtes uniquement), pas un
  opérateur de clôture ;
- `think(KB, rules)` = point fixe (`repeat=1`, `runSmart`) — la KB doit
  être une formule **ouverte** ; `applyRules(KB, rules)` = une seule
  passe (`repeat=0`, `runLaborious`). Les deux sont dans
  `swap/query/query/task.py` ;
- « Règles stockées » (équivalent `cwm --rules`) : on copie les
  énoncés-règles dans la formule de travail *avant* le raisonnement
  (`store.copyFormula(rules, kb)`). `--think=foo` / `--apply=foo`
  (équivalent « non stockées ») : les règles restent dans leur document
  source. Les énoncés-règles (prédicat `log:implies`) sont toujours
  **exclus du diff** des nouveaux faits ;
- **Timeout** : thread `daemon` + `join(timeout)` ; à l'échéance la
  réponse revient (`timeout: true`) et le thread orphelin est abandonné
  (il continue de calculer en arrière-plan, sans jamais bloquer le TP).
  NB : les règles à prémisses vides ne se déclenchent qu'**une fois**
  (dé-duplication du binding vide dans `Rule.already`) — une règle
  *vraiment* infinie doit produire un **nouveau binding à chaque passe**
  (ex. un existential en conclusion) ;
- **Piège d'affichage** : `Term.value()` renvoie *self* et `str()` un
  fragment **relatif** à la base URI — pour l'affichage JSON il faut
  l'URI absolue via `uriref()`. NB : dans la hiérarchie de
  `swap/core/term.py`, `Fragment` **n'est pas** un sous-classe de
  `Symbol` (les deux héritent de `LabelledNode`) — les deux cas doivent
  être gérés ;
- le diff « nouveaux faits » est un diff d'ensembles de triples
  (chaînes) sur la *même formule ouverte* : les nœuds vides gardent
  leur identité au sein de la formule, donc le diff est stable.

### P3 — Requêtes avec/sans raisonnement ✅ (livrée le 2026-11-22)

- Éditeur 3 (SPARQL) + case « raisonner avant d'interroger » ;
- tableau de résultats (colonnes = variables de la clause SELECT) ;
- **diff avant/après raisonnement** : exécuter la requête sur la KB brute
  et sur la clôture, surligner les lignes nouvelles — la fonctionnalité
  la plus pédagogique du TP ;
- ASK : bannières « vrai / faux » avant et après raisonnement ;
- `/api/parse` accepte `language: "sparql"` (linter de l'éditeur de
  requête : type de requête + variables) ; `POST /api/query`.

**Critère d'acceptation** : la même requête montre plus de lignes après
raisonnement, la différence est visible d'un coup d'œil. ✔ (exemple
préchargé : 0 ligne brute, 1 ligne après raisonnement, surlignée —
vérifié en navigateur, en plus de 19 tests unitaires)

**Faits techniques établis en P3** (à réutiliser) :

- **SPARQL uniquement** (la roadmap disait « SPARQL ou N3QL ») : aucun
  exemple de référence N3QL dans le corpus de tests du dépôt, l'API
  `applyQueries` existe mais reste non validée — N3QL reporté (à
  documenter si demandé) ;
- chemin de parse SPARQL (string → formule) : même que le CLI
  (`contentType "x-application/sparql"`, `swap/io/webAccess.py`) —
  convertisseur `sparql2cwm.FromSparql(store, F)` +
  `sparql_parser.N3Parser(io.BytesIO(text), sparql_parser.branches,
  convertor)` + `p.parse(sparql_parser.start)` ; `parse()` renvoie
  **None à l'EOF** (document vide) ;
- syntaxe : `PREFIX : <…>` (majuscule, **sans** point final) —
  `@prefix` et le point final sont de la syntaxe N3 et **échouent** en
  SPARQL (piège classique des étudiants, à mettre dans le guide) ;
- exécution : `applySparqlQueries(workingContext, qf, targetContext)`
  (`swap/query/query/task.py`) — même cheminement que le CLI : copie de
  la KB → `canonicalize()` → requête dans une formule neuve
  (`stayOpen=True`) ;
- forme des résultats : chaque ligne SELECT est une formule typée
  `sparqlCwm#Result` dont les énoncés internes sont
  `(VALEUR, bound, "nomVariable")` — la **valeur est en sujet**, le nom
  de variable en objet ; ASK vrai = énoncé
  `_g type sparqlCwm#Success` ; ASK faux / SELECT vide = **0 énoncé** ;
- **l'ordre des variables ne peut pas être lu dans la formule parsée**
  (la clause SELECT y est un *ensemble* d'énoncés, sans ordre) — il est
  extrait du **texte** de la requête (regex `SELECT … WHERE`) ;
  `SELECT *` → union triée des variables du résultat ;
- re-exécuter la même formule de requête est sûr :
  `Formula.substitution` (formula.py) rend une **nouvelle** formule ;
  `gatherSparqlQueries` substitue le stand-in `data` (symbole du chemin
  CWD, `FromSparql.uribase = uripath.base()`) par le contexte de travail
  à chaque exécution ;
- erreurs du parser SPARQL : `Exception("Found (name, word, line) when
  expecting …")` ou `Exception("Found %s; %s expected")` — la ligne du
  token est **0-indexée** (compteur du lexiqueur) → +1 pour l'affichage ;
  token de fin de document `('…#eof', '', -1)` = requête incomplète ;
- CONSTRUCT / DESCRIBE : refusés avec un message clair (le TP couvre
  SELECT + ASK).

### P4 — Validité & preuves ✅ (livrée le 2026-11-22)

- Éditeur 4 **Conclusion / Preuve** (deux onglets, deux éditeurs CM6) ;
- bouton **Entraîne ?** → `engine.entail` + `POST /api/entail` :
  « La KB entraîne-t-elle la conclusion ? » via `testIncludes` sur la
  clôture → bannières oui/non (+ avertissement *ex falso* si la clôture
  est incohérente) ;
- bouton **Pourquoi ?** → `engine.prove` + `POST /api/prove` : génération
  de la preuve (flux `cwm --think --why`), affichée colorée dans l'onglet
  « Preuve » — la preuve est **auto-suffisante** (sources en URI `data:`)
  et **altérable à la main** ;
- bouton **Vérifier la preuve** → `engine.check_proof` + `POST /api/check` :
  subprocess `python -m swap.check --report` (fichier temp, cwd = racine du
  dépôt) → verdict « preuve valide / invalide » + **étapes de dérivation**
  numérotées + formule prouvée ;
- scénario clé livré : l'étudiant **altère la preuve** à la main (un
  prédicat de la conclusion) → `check` rejoue la dérivation et la rejette
  (exit 255, raison affichée) — vérifié en navigateur.

**Critère d'acceptation** : aller-retour complet génération →
vérification, y compris le rejet d'une preuve altérée. ✔ (chaîne
Entraîne ? → Pourquoi ? → Vérifier → altération → Vérifier rejette,
vérifiée en navigateur, en plus de 20 tests unitaires)

**Faits techniques établis en P4** (à réutiliser) :

- **Génération de la preuve** (flux validé in-process) :
  ```
  diag.tracking = 1
  wc = store.newFormula(base + "#_work"); newTopLevelFormula(wc)
  wc.stayOpen = 1; wc.isWorkingContext = True
  SinkParser(store, wc, thisDoc=datauri(text), why=BecauseOfCommandLine(…))
  think(wc) / applyRules(wc)
  wc.stayOpen = False          # OBLIGATOIRE
  wc = wc.close()              # sinon explainFormula échoue (pas canonical)
  proof = explainFormula(wc)   # swap/reasoner/why.py
  store.dumpNested(proof, notation3.ToN3(…, base=base, quiet=1, flags="qdr"))
  ```
  `SinkParser(why=…)` + `diag.tracking` enveloppe automatiquement chaque
  document en `:Parsing` dont `:source` = `thisDoc` — d'où
  `thisDoc = data:text/rdf+n3;charset=utf-8,` + texte URI-encodé
  (preuve auto-suffisante : `check` recharge chaque source par URI,
  les `data:` ne pointent nulle part) ;
- **dump de la preuve : drapeaux `qdr`** (quiet + **no default
  namespace** + absolu) : avec seulement `r`, `ToN3.setDefaultNamespace`
  écrit *toujours* l'espace de noms par défaut **relatif** à la base
  (`@prefix : </…>`) — re-résolu contre l'emplacement du fichier temp,
  la vérification échouait. `d` l'évite ; la base peut alors être
  n'importe quelle URI (la même que le document) ;
- `wc.close()` ne **canonicalise pas** si `stayOpen` est encore 1
  (formula.py) — `explainFormula` exige une formule canonical : c'était
  l'échec silencieux du flux initial ;
- **`check` en subprocess uniquement** (risque #4) ; codes de sortie :
  **0** = valide, **255** (`sys.exit(-1)`) = `InvalidProof`
  (« Proof invalid: … » sur stderr), 1 = autre erreur (preuve non
  parsable, …), 2 = ligne de commande ; `--report` imprime les étapes
  numérotées (`N: <énoncé>` + `[by parsing/erasure/rule from step …
  with bindings/conjoining …]`) puis le N3 de la formule prouvée ;
- **deux bugs CWM corrigés pour P4** (voir `doc/changes.md`) :
  (1) `check --report` levait `IndexError` sur une variable **sans
  fragment** (`@forAll :x` avec base `http://example.org/` donne
  `http://example.org/x` — `str(var).split("#")[1]` → `rsplit("#", 1)[-1]`) ;
  (2) la formule prouvée (écrite en binaire sur `sys.stdout.buffer`)
  sortait **avant** les étapes du rapport (tampon texte non vidé) —
  `sys.stdout.flush()` avant l'écriture binaire ;
- **`testIncludes` est une inclusion pure** : le moteur CWM n'implémente
  PAS l'explosion — `engine.entail` l'applique explicitement (clôture
  incohérente → toute conclusion entraînée, signalé via
  `inconsistent: true`) ;
- **le global `diag.tracking` doit être gardé** : un thread de `prove`
  abandonné au timeout reste bloqué dans sa `think()` non convergente
  (son `finally` ne s'exécute jamais) — le thread principal marque la
  génération comme abandonnée (jeton sous verrou) et réinitialise le
  suivi, sinon tout parse ultérieur sans `why=` lève « Tracking reasons
  but no reason given » ;
- bnodes de la preuve (`_g0`, …) dérivés de la **base du dump**
  (`uripath.join(base, "#_g")`) — un dump relatif aurait rendu ces URIs
  relatives aussi ;
- l'UI ne peut pas accéder à la `EditorView` de ce bundle (aucun
  `cmView` sur le DOM) — pour altérer le contenu d'un éditeur de façon
  programmatique : `focus()` sur `.cm-content` + sélection réelle +
  `document.execCommand("insertText")` (perd les retours à la ligne,
  sans effet sur la validité N3).

### P5 — Pack TP ✅ (livrée le 2026-11-22)

- `lab/exercises/` : **2 exercices** calibrés Master MIAGE —
  `famille/` (échauffement ~30 min : toutes les fonctions de l'outil en
  miniature, corrigé dans l'énoncé) et `recettes/` (exercice principal
  ~60–90 min : contre-indications alimentaires par règles N3 —
  allergènes absolus + nutriments à seuil avec calculs `math:`,
  7 recettes, 3 patients, 5 questions + discussion des limites du
  modèle) ;
- **mode « exercice »** : menu du bandeau (découverte automatique des
  dossiers d'exercice), préchargement dans les éditeurs (données,
  règles, requête, conclusion) + affichage de l'énoncé ;
- guide enseignant : `exercises/GUIDE_ENSEIGNANT.md` (déroulé 2 h,
  points de vigilance, barème suggéré) ;
- convention d'exercice documentée (`exercises/README.md`) — un nouvel
  exercice s'ajoute **sans code** ;
- option « visualisation du graphe » (vis.js) : **livrée** — bouton
  « Graphe » + « après raisonnement » : graphe des triples (ressources
  bleu, littéraux vert, nœuds vides gris ; nœuds/arcs **inférés** en
  orange avec la clôture), `vis-network` 10.1.5 + `vis-data` 7.1.9
  vendus en local (`static/vendor/vis/`, UMD, licence MIT) ;
  `engine.graph`, `POST /api/graph` (nœuds/arcs JSON, troncature à
  3000 énoncés signalée, timeout comme les autres raisonnements).

**Critère d'acceptation** : un TP de 2 h est réalisable de bout en bout
sans autre matériel que le dépôt. ✔ (déroulé 2 h écrit ; les deux
exercices vérifiés de bout en bout : `recettes` reproduit exactement
les tableaux de l'énoncé via le moteur — 154 nouveaux faits, 0
incohérence)

**Faits techniques établis en P5** (à réutiliser) :

- convention d'exercice : sous-dossier de `lab/exercises/` portant
  `enonce.md` (obligatoire, premier titre `# …` = libellé), `*.n3`
  (`regles.n3` → éditeur règles ; les autres concaténés en ordre
  alphabétique → éditeur données), `context.json` optionnel
  (`{"query", "conclusion", "base_uri"}`) ;
- découverte **automatique** : pas d'enregistrement — un dossier
  d'exercice valide apparaît dans le menu au rechargement de la page
  (`GET /api/exercises` liste les sous-dossiers portant `enonce.md`) ;
- validation au chargement : les documents de l'exercice sont parsés
  (N3 + SPARQL) **avant** d'être renvoyés — un exercice cassé ne se
  charge pas (erreur taguée par document `kb`/`rules`/`query`/`concl`) ;
- anti-traversée de dossier double : le nom est validé
  (`[A-Za-z0-9._-]+`, pas de séparateur) puis contrôlé par
  `os.path.realpath` contre la racine des exercices (même pattern que
  le service des statiques) ;
- remplissage des éditeurs par `dispatch` d'un seul bloc
  (`changes: {from: 0, to: doc.length, insert}`) — le `updateListener`
  (docChanged) déclenche les re-parses automatiques, et le parse de la
  KB est forcé immédiatement (`parseNow`) pour un retour visuel rapide
  (le debounce de 500 ms et le parse immédiat sont dédupliqués par
  contenu, mécanisme P3) ;
- graphe : vis.js en **UMD** (pas d'esbuild, contrairement à
  CodeMirror) — deux `<script>` classiques, `vis-data` définit l'objet
  global `vis`, `vis-network` l'étend ; un arc par paire (sujet, objet),
  les prédicats multiples fusionnés dans le libellé (`rdf:type` → `a`) ;
  « inféré » d'un nœud = terme absent de **tous** les énoncés bruts
  (pas seulement des arcs inférés) ; troncature à 3000 énoncés
  (signalée) pour ne pas geler l'onglet ; les énoncés-règles
  (`log:implies`) sont exclus du graphe.

### P6 — Déploiement serveur (à faire, optionnelle)

Le TP est conçu local-une-machine, mais le passage sur un serveur
(salle de TP, département) est **envisageable sans refonte** :
l'architecture y est déjà presque prête.

**Ce qui joue en faveur (état actuel, zéro code) :**

- **Stateless** (décision P0) : pas de session, pas d'état serveur —
  n'importe quelle instance traite n'importe quelle requête, scaling
  horizontal trivial ;
- `ThreadingHTTPServer` : requêtes concurrentes déjà gérées
  (1 thread / connexion) ;
- `--host 0.0.0.0` existe déjà : accessible sur le réseau **aujourd'hui**
  (`cwm-lab --host 0.0.0.0`) ;
- zéro dépendance : déploiement = le dépôt + Python 3 ;
- aucune API d'écriture : pas d'intégrité de données à protéger,
  seuls risques = CPU / mémoire ;
- les builtins `os:` de CWM 2.0 sont en **lecture seule** (`argv`) :
  pas d'exécution de shell via une N3 saisie par un étudiant ;
  `check` tourne déjà en subprocess isolé.

**Niveaux de déploiement :**

1. **Salle de TP / LAN** — zéro code : `--host 0.0.0.0` + IP de la
   machine. ~30 étudiants sur des KB de TP (5–500 énoncés,
   raisonnement < 300 ms) tiennent 2 h sans renfort ;
2. **Serveur de département** — **gunicorn** (workers de production)
   + systemd + **Caddy** (reverse proxy, **déjà en place sur les
   serveurs**) pour TLS et statiques +
   renforts ci-dessous ;
3. **Internet** — en plus : authentification, monitoring, sandbox.

**Travaux à prévoir (le seul vrai changement de code) :**

- **Timeout du raisonnement en subprocess tuable** — actuellement un
  thread abandonné continue de tourner `think()` (CPU/mémoire
  illimités jusqu'à convergence ou OOM) : vector de DoS sur un serveur
  partagé. Pattern à réutiliser : celui de `check_proof`
  (subprocess + kill au timeout) ;
- **Semaphore de concurrence** : plafond de raisonnements simultanés
  (ex. 8), 503 « serveur occupé » au-delà ;
- **`gunicorn` devant le serveur** (mise à disposition sur le net
  plus robuste) : le `ThreadingHTTPServer` de stdlib est un serveur
  de développement — un worker de production (gunicorn, workers
  fork + preload) rend la mise en ligne plus robuste (récupération
  d'un worker mort, supervision, démarrage supervisé sous systemd).
  Deux points à traiter :
  - la handler http.server n'est **pas WSGI** — il faut une couche
    d'adaptation mince (une centaine de lignes stdlib :
    `environ`/`start_response` → appel de la handler existante),
    l'API JSON reste inchangée ;
  - **exception à la politique zéro dépendance** : gunicorn est une
    dépendance **de déploiement uniquement** (jamais importée par
    le code du TP — le mode `python3 -m cwm_lab.server` local
    reste stdlib pur) ; déclarée dans un
    `requirements-deploy.txt` séparé, documenté comme
    optionnel. Gunicorn est MIT, stable, sans transitive
    obligatoire ;
- rate-limit par IP (niveau 2+) ; `ulimit` mémoire du service.

**Critère d'acceptation** : 30 étudiants simultanés en salle de TP,
aucun blocage dû à des règles cycliques soumises de mauvaise foi,
zéro état résiduel entre deux étudiants.

### P7 — Reprise d'ergonomie ✅ (livrée le 2026-11-23)

**Problème constaté** : le tableau de bord a grandi phase par phase
(P0 → P5 + visu) et on le sent — **zones éparpillées** (5 blocs de
résultats empilés verticalement : syntaxe, nouveaux faits, requête,
preuve, graphe) et **boutons aux objectifs différents** (Parse,
Raisonner, Interroger, Pourquoi ?, Vérifier la preuve, Graphe) :
charge cognitive élevée pour un étudiant qui découvre l'outil. Le
**graphe**, qui est la vue la plus parlante de la KB, est en plus
**caché derrière un bouton** : il faut cliquer « Graphe » et gérer la
case « après raisonnement » pour le voir.

**Direction envisagée** :

- **Graphe systématiquement visible** : un panneau de graphe
  **persistant** (colonne dédiée ou zone fixe) qui se re-rend à
  **chaque action** — parse (données brutes), Raisonner (clôture,
  inférés en orange), Interroger, chargement d'exercice — ; le
  bouton « Graphe » disparaît, le graphe devient une vue permanente
  de la KB (le mécanisme de rafraîchissement automatique déjà livré
  avec la visu est la base) ;
- **Graphe — mode « attributs masqués »** : case qui supprime les
  nœuds-littéraux du rendu et les regroupe en une **pastille sur le
  nœud** portant le **nombre d'attributs** (ex. `:alice` + « 3 ») ;
  la **bulle contextuelle** (infobulle au survol, déjà présente)
  liste alors les attributs masqués. Rend le graphe lisible quand
  une ressource porte beaucoup de littéraux (`recettes` :
  ingrédients, doses, contre-indications) ; le rendu complet reste
  disponible en décochant ;
- **Barre d'actions unifiée** : regrouper les boutons par objectif
  (vérifier / raisonner / interroger) ou un seul bouton « Lancer »
  avec sous-options — à arbitrer avec l'enseignant ;
- **Zone de résultats consolidée** : un seul panneau à onglets
  (syntaxe, faits, requête, preuve) au lieu de N blocs empilés ;
- **Énoncés : rendu Markdown → HTML dans l'appli** : les énoncés
  restent des `.md` dans le dépôt (source de vérité, éditable), mais
  l'appli les affiche **rendus en HTML** (titres, listes, tableaux,
  gras/italique, code) au lieu du texte brut. Deux options, à
  arbitrer : (a) convertisseur minimal **stdlib** dans `engine`
  (sous-ensemble Markdown suffisant pour les énoncés — zéro
  dépendance, conforme à la politique du dépôt) ; (b) `marked.js`
  (MIT) **vendu en local** comme vis.js (`static/vendor/`) — plus
  complet, même politique que CodeMirror/vis.js.
- itératif : le layout actuel reste utilisable en attendant (pas de
  refonte blanche).

**Critère d'acceptation** : un étudiant qui ne voit l'outil pour la
première fois termine l'exercice `famille` sans aide en sachant
seul quel bouton sert à quoi, et le graphe est **toujours visible
et toujours à jour** sans qu'il ait à le demander. ✔ (vérifié en
navigateur : parcours `famille` complet — chargement d'exercice
→ énoncé rendu, `Interroger` 0/1 ligne avec ligne nouvelle
surlignée, `Entraîne ?` oui, `Pourquoi ?` → `Vérifier la preuve`
valide, export N3 ; le graphe suit chaque action sans qu'on le
demande, y compris à l'édition d'un énoncé de la KB)

**Faits techniques établis en P7** (à réutiliser) :

- **layout 2 colonnes** : gauche = éditeurs + barre d'actions
  unifiée (groupes « Raisonnement / Interroger / Valider »,
  options de raisonnement **communes** aux 3 groupes) ; droite =
  panneau **graphe persistant**, **éditeur Conclusion/Preuve** et
  panneau **résultats en onglets** (Parse / Raisonnement /
  Requête / Entraînement / Preuve / Export) ; le bouton « Graphe »
  et le bloc de résultats empilés ont disparu ; l'éditeur
  Conclusion/Preuve est à droite : une preuve générée embarque des
  URI `data:` de plusieurs milliers de caractères sur une seule
  ligne (min-content CodeMirror énorme), elle ne gonfle plus la
  colonne des éditeurs ;
- **largeur des colonnes ajustable, indépendante des résultats** :
  les pistes du grid sont `minmax(0, …)` (un `1fr` nu =
  `minmax(auto, 1fr)` : le min-content d'une ligne CodeMirror
  très longue élargissait les colonnes à chaque preuve) ; poignée
  de glissement `#col-resizer` (pointer events, largeur relative
  25–75 % persistée en localStorage — nombre, pas pourcentage,
  pour éviter les `%%` qui invalident la déclaration entière),
  `graphNetwork.redraw()` pendant le glissement (le canvas
  vis-network suit le redimensionnement avec retard) ;
- **graphe toujours visible** : `refreshGraph()` (toujours, plus
  de test de visibilité) sur : édition KB/règles (debounce 800 ms,
  dernier état l'emporte), parse forcé, base URI, `Raisonner`
  (coche « après raisonnement » si succès), `Interroger` avec
  raisonnement, chargement d'exercice, changement des cases du
  panneau graphe ; rendu initial au chargement de la page ;
- **attributs masqués** : côté **serveur** (`engine.graph(...,
  hide_literals=True)`) — littéraux retirés du rendu, `attrs` =
  {id du sujet → [« prédicat valeur »]} (le titre `rdf:type` se
  lit « type »), `title` du sujet enrichi de la liste ; le
  frontend dessine une **pastille compteur** calée au-dessus de
  chaque nœud porte d'attributs (recalculée à chaque `afterDrawing`
  du réseau, masquée hors du canvas) ; survol = infobulle
  (attributs masqués) ; le mode est persisté en localStorage ;
- **onglets de résultats** : le parse met à jour l'onglet « Parse »
  **sans auto-bascule** (pas de nuisance pendant la saisie) ;
  chaque action (`Raisonner`, `Interroger`, `Entraîne ?`,
  `Pourquoi ?`, `Vérifier`, export) bascule sur son onglet ; un
  **point** signale un résultat nouveau dans un onglet masqué
  (effacé au passage) ;
- **barre d'actions unifiée** : regroupement par **objectif**
  (pas de bouton unique « Lancer » — jugé pire pour le critère
  novice), chaque bouton conserve son tooltip explicite ;
- **énoncés Markdown → HTML, option (a)** : convertisseur
  minimal **stdlib** `engine.render_markdown` (titres, listes
  imbriquées par retrait, tableaux GFM, blocs code, gras/italique/
  code en ligne) ; le texte est **d'abord échappé HTML**
  (`quote=False`), aucun fragment de Markdown ne peut injecter de
  balise ; les `.md` restent la source de vérité dans le dépôt
  (`load_exercise` renvoie `enonce` brut + `enonce_html` rendu) ;
  le 1er `<h1>` du rendu est masqué (redondant avec le libellé du
  panneau).

### P8 — Cache des traitements ✅ (livrée le 2026-11-23)

**Constat** : c'est un TP — **le même traitement est très
probablement demandé plusieurs fois** (même requête SPARQL
re-lancée, même raisonnement rejoué après un clic, même preuve
vérifiée deux fois, mêmes données/graphes re-rendus). Chaque
traitement recalcule tout (stateless, par conception) : du CPU
gaspillé, surtout pour les traitements lourds (`think`,
`prove`, `check_proof` en subprocess, `query` sur clôture).

**Objectif** : un système de cache évitant de refaire les calculs —
**accélérer la réponse** (seconde occurrence quasi instantanée) et
**décharger le processeur** (salle de TP / P6).

**Direction envisagée** :

- **Cache deux niveaux, par API** :
  `/api/parse`, `/api/infer`, `/api/query`, `/api/entail`,
  `/api/prove`, `/api/check`, `/api/graph`, `/api/serialize` —
  tous des **fonctions pures** de leur payload, donc cachables sans
  risque sémantique (le stateless est préservé : le cache est une
  optimisation, pas un état) :
  1. **mémoire** (processus) — hot path, réponse immédiate ;
  2. **disque** (**persisté**) — un fichier JSON par clé dans un
     répertoire cache (ex. `.lab-cache/` hors du dépôt servi, ou
     `~/.cache/lab_tp/`) : le cache **survit aux redémarrages du
     serveur** et profite de **plusieurs séances de TP** (les mêmes
     exercices reviennent d'une séance à l'autre — le premier
     étudiant de la séance 2 n'attend plus le raisonnement de
     `recettes`) ;
- **clé de cache** : empreinte (SHA-256) du **payload complet**
  (kb, règles, requête, conclusion, base_uri, options — mode,
  timeout, flags « raisonner avant », « après raisonnement »,
  store_rules) : une variation d'1 caractère du texte invalidation
  naturelle ;
- **politique d'éviction** : LRU borné + TTL **par niveau** —
  mémoire : petit (ex. 64 entrées, TTL court) ; **disque : borné
  en taille totale** (ex. 200 Mo, nettoyage LRU du plus ancien)
  avec **TTL long** (ex. 7 jours) pour couvrir plusieurs séances ;
  **seuls les résultats complets et réussis** sont cachés (jamais
  un timeout partiel, jamais une erreur) ;
- **configuration en deux fichiers** (séparation sensible / non
  sensible) :
  - `lab/lab_web/config.yaml` (**chmod 600**) — paramètres
    **non sensibles** : **durée de rétention** (TTL disque,
    défaut 7 jours ; TTL mémoire 5 min), taille max, LRU,
    plafonds de quota (P9). Format YAML **plat** (`cle: valeur`,
    un niveau) : parseable en stdlib (~20 lignes), aucune
    dépendance ;
  - `lab/lab_web/.env` (**ignoré par git**, **chmod 600**) —
    **données sensibles / locales** : **provider** et **clé API**
    (P9), **répertoire du cache** (chemin local de la machine,
    défaut `~/.cache/lab_tp/`). Chargé par le backend au démarrage
    (parser `CLE=value` stdlib, ~10 lignes) ;
  - `lab/lab_web/.env.example` (**commité**) — modèle commenté
    pour aider l'utilisateur à son installation (copier en `.env`,
    remplir, `chmod 600`) ;
  - absents les fichiers → les valeurs par défaut s'appliquent
    (l'appli démarre sans config) ;
- **priorité** : `check_proof` (subprocess, le plus cher) et
  `infer`/`query` sur clôture (chaînage avant) ;
- **fiabilité** : le serveur est multithreadé (`ThreadingHTTPServer`)
  — LRU maison + `threading.Lock` (stdlib, aucune dépendance) ;
- signalétique discrète : `cached: true` dans la réponse JSON
  (transparence pédagogique possible : « résultat en mémoire »).

**Critère d'acceptation** : relancer deux fois la même requête /
le même raisonnement / la même vérification de preuve renvoie la
seconde fois **sans recalcul** (réponse < 10 ms, drapeau
`cached`), et la moindre édition d'un éditeur force le recalcul
(clé différente) ; **après redémarrage du serveur**, les
traitements de la séance précédente (dans le TTL disque) sont
toujours servis depuis le cache — le gain se cumule sur
**plusieurs séances de TP**. ✔ (vérifié : 2e `/api/infer` identique
servi depuis le cache avec `cached: true`, même résultat ; payload
différent → recalcul ; erreur/timeout jamais cachés)

**Faits techniques établis en P8** (à réutiliser) :

- **cache = optimisation, pas un état** : le serveur reste
  stateless (chaque requête reconstruit son store) ; seule la
  réponse JSON déjà calculée est mémorisée — la sémantique des
  endpoints est inchangée ;
- **clé** = `"<api>-<sha256>"` (plat, sans « / » : un fichier par
  clé dans le répertoire du cache — l'évacuation par taille scanne
  un seul niveau) sur le **payload complet** en JSON canonique
  (clés triées, séparateurs compacts) : l'ordre des clés du body
  n'a pas d'importance, 1 caractère de différence → recalcul ;
- **deux niveaux** : mémoire (LRU par ordre d'insertion, TTL
  court) puis disque (un fichier JSON `{"ts", "data"}` par clé,
  écriture atomique `tmp` + `os.replace`, hit disque **promu en
  mémoire**) ; un verrou `threading.Lock` unique ;
- **évacuation disque** : au `put`, tant que la taille totale
  dépasse la borne, suppression des plus anciens **par mtime**
  (piège corrigé : déduire la taille *avant* l'`unlink` — après,
  `getsize` renvoie 0 et le vide toute la zone) ;
- **robustesse** : fichier disque corrompu = simple miss ;
  répertoire disque non créable = dégradation mémoire seule ; le
  cache ne doit **jamais** bloquer le TP (`main()` l'encadre dans
  un try) ;
- **config** : `config.yaml` (non sensible : TTL, tailles) +
  `.env` (sensible : `CACHE_DIR`, `IA_*` — P9) ; parseurs plats
  stdlib (~20 lignes chacun) ; **absents → valeurs par défaut**,
  l'appli démarre sans config ; `.env` et `config.yaml`
  git-ignorés, `.example` commités ;
- le drapeau `cached` est ajouté **dans le serveur** (jamais dans
  les données cachées) — le client verra `true` seulement si la
  réponse vient du cache.

### P9 — Remplissage de la base par IA générative ✅ (livrée le 2026-11-23)

**Objectif** : un bouton **« Remplir la base (IA) »** qui génère
des données N3 réalistes et les injecte dans l'éditeur
connaissances — utile pour donner des KB de taille variée à chaque
groupe sans distribuer de fichiers, et pour faire varier les
exercices d'une séance à l'autre (deux groupes ne travaillent pas
sur les mêmes données).

**Direction envisagée** :

- **Provider et modèle dans `.env`** (le fichier sensible de la
  P8 : ignoré par git, chmod 600 — `ia.provider` + `ia.model` +
  **clé API**, jamais dans une config versionnée) ; absent la
  config → le bouton est **désactivé** avec un message explicite
  (l'appli fonctionne sans IA). Le provider sera très
  probablement **ProxyIAg** — un proxy institutionnel qui gère les
  **quotas en nombre de requêtes et en volume de tokens** ;
- **appel depuis le backend** : `urllib` (stdlib) vers l'API du
  provider — le navigateur ne voit jamais la clé API ;
- **respect des quotas ProxyIAg côté appli** : les plafonds
  (requêtes / tokens) sont **portés dans `config.yaml`** et
  comptés **côté backend** (compteur de requêtes + usage de
  tokens lu dans la réponse API, persisté avec le cache P8 pour
  couvrir la séance) : quota atteint → bouton désactivé avec un
  message clair (« quota de la séance épuisé ») ; les prompts
  compacts (données seules, taille bornée) limitent le volume de
  tokens — la régénération bornée (3) compte dans le quota ;
- **prompt bien choisi** : le prompt impose — le **format**
  (N3/Turtle, prefixes fixés, **données seules, aucune règle**
  `log:implies`), le **domaine** (celui de l'exercice chargé, ou
  un domaine générique), la **taille** (N faits, M entités —
  paramétrable), et la **réalisme** (valeurs plausibles : prénoms,
  âges, dates, seuils numériques cohérents avec les règles de
  l'exercice) ; le contexte de l'exercice (énoncé + règles) est
  repris dans le prompt pour que les données générées **s'appliquent
  aux règles existantes** ;
- **contrôles a posteriori** (garantir la cohérence — la génération
  n'est jamais fiable à 100 %) :
  1. **parse** — la réponse doit se parser en N3 (erreurs
     ligne/colonne, mécanisme P0) ;
  2. **cohérence** — raisonnement sur KB générée + règles
     existantes : **absence de `log:false`** (incohérence, P2) ;
  3. **plausibilité structurelle** — requête SPARQL de garde
     (ex. « chaque entité porte au moins son `rdf:type` »,
     compte de faits dans la plage demandée) ;
  4. **échec → régénération** bornée (ex. 3 tentatives, le prompt
     est enrichi des erreurs précédentes) puis signalement
     honnête à l'étudiant (« génération refusée : … ») ;
- **transparence pédagogique** : le texte généré arrive dans
  **l'éditeur** (pas en base cachée) — l'étudiant peut tout lire,
  modifier, supprimer ; bannière « généré par IA, à vérifier » ;
- **hors cache** (P8) : la génération est non déterministe et
  coûteuse — jamais cachée ; le raisonnement sur la KB générée,
  lui, se cache normalement (clé = texte, comme les autres).

**Risques spécifiques** : coût et quota de l'API (plafond par
séance dans la config), **confidentialité** (les données des
exercices partent vers le provider — documenter, opt-in),
réseau indisponible (dégénérescence gracieuse : bouton
indisponible), non-déterminisme (même prompt ≠ mêmes données —
annoncer aux étudiants).

**Critère d'acceptation** : sur `recettes`, un clic génère une KB
de recettes/patients réaliste, parsée, **cohérente avec les règles
existantes** (0 `log:false`, les tableaux de l'énoncé se
recalculent), en moins de 30 s, et une génération incohérente est
**rejetée et régénérée** (jamais injectée telle quelle). ✔

**Faits techniques établis en P9** (à réutiliser dans le TP) :

- **le SPARQL de CWM 2.0 ne supporte ni agrégats ni `MINUS`** :
  `COUNT(?x)` → « token inattendu "(" », et `FILTER isIRI(…)` /
  `BIND` échouent de même (vérifié sur le serveur de dev). La
  « garde SPARQL » de la spec n'est pas exprimable → la
  plausibilité structurelle est calculée **en Python sur la
  formule parsée** (parcours des énoncés, comme `engine.graph`) :
  nb de faits, ressources distinctes, sujets sans `rdf:type` ;
- **l'incohérence du contrôle 2 se vérifie par raisonnement**, pas
  par requête : `engine.infer(kb=générée, rules=règles de
  l'éditeur)` → `inconsistent` si `log:false` dans la clôture ;
  le **timeout des règles non convergentes n'est pas un rejet**
  (la KB d'origine de l'exercice aurait le même timeout) mais un
  avertissement « cohérence non vérifiée » ;
- ProxyIAg (API compatible OpenAI) : `POST {base_url}/chat/
  completions`, `Authorization: Bearer sk-…`, usage dans
  `usage.total_tokens` ; 400 avec `response_format: json_object`
  → retente sans (certains modèles n'ont pas le mode JSON) ;
  codes 429/≥500 traduits en messages génériques (les erreurs du
  proxy ne sont jamais montrées à l'étudiant) ;
- calibration `recettes` (référence des tests) : 577 faits,
  74 ressources distinctes, 60 sujets-ressources, **0 sujet sans
  `rdf:type`**.

### P10 — Internationalisation de l'interface ✅ (livrée le 2026-11-23)

**Objectif** : internationaliser l'application (FR par défaut, EN)
avec un **sélecteur de langue dans la barre d'entête** — l'outil est
pensé pour un public français mais doit pouvoir être utilisé en
anglais (salle internationale, lecteur de la documentation
étranger).

**Direction retenue** :

- **un seul module `static/i18n.js`** : deux dictionnaires (fr/en)
  + helper `t(key, …args)` (placeholders `{1}` `{2}` …) +
  application des chaînes **statiques** via les attributs
  `data-i18n` (text), `data-i18n-ph` (placeholder),
  `data-i18n-title` (infobulles), `data-i18n-aria` (aria-label) ;
  le texte français du HTML reste le **repli** si une clé manque
  (un trou dans le dictionnaire ne casse jamais la page) ;
- **persistance** de la langue en `localStorage`
  (`cwm-tp-lang`) ; `<html lang>` et le titre de page suivent la
  langue ;
- **sélecteur** `<select id="lang-select">` dans `#toolbar`
  (Français / English) — même style que le sélecteur d'exercice ;
- **chaînes dynamiques** (résultats, bannières, erreurs) : toutes
  passées en `t()` dans `app.js` ; le dernier état de chaque rendu
  est conservé (`lastRender`) et **re-rendu au changement de langue**
  (événement via `onLangChange`) — sans re-fetch, sans forcer
  l'onglet actif, **sans reconstruire le réseau vis** (seuls le
  méta et le message de troncature sont re-localisés, la vue
  utilisateur — zoom/pan — est préservée) et **sans ré-écrire la
  preuve** (une altération manuelle n'est pas écrasée) ;
- **backend localisé** : `cwm_lab/ia.py` porte une table
  `MESSAGES = {"fr": …, "en": …}` + `_msg(lang, key, …)` — les
  messages d'erreur de la génération (quota, proxy, contrôles,
  statut) sont localisés côté serveur ; le front envoie sa langue
  (`/api/ia/status?lang=`, `lang` dans le body de
  `/api/ia/generate` ; défaut `fr`, toute autre valeur repli `fr`).
  **Le prompt du modèle reste en français** (calibré sur les
  énoncés du TP) ; les messages du moteur de parse CWM (anglais
  technique) sont du **contenu**, non localisés ; la `note` du
  modèle est **localisée en P10.1** (demandée au modèle dans la
  langue de l'app).

**Hors périmètre (contenu, pas interface)** : les énoncés des
exercices et leurs titres (contenu pédagogique — **pris en charge en
P10.1**), la note du modèle IA (**localisée en P10.1**), les erreurs
du parser CWM (anglais technique).

**Critère d'acceptation** : la bascule FR ↔ EN dans l'entête
retourne toute l'interface (statiques + résultats déjà affichés)
dans la nouvelle langue, la préférence persiste au rechargement, et
les messages de l'IA suivent la langue choisie. ✔ (vérifié en
navigateur sur le serveur de test, en plus de 12 tests unitaires
`test_ia` — quota/proxy/contrôles/statut/génération en EN, repli FR
sur langue invalide, prompt inchangé)

**Faits techniques établis en P10** (à réutiliser) :

- **deux natures de texte, deux traitements** : l'**interface**
  (boutons, libellés, résultats, erreurs applicatives) est
  localisée ; le **contenu** (énoncés des exercices, réponse du
  modèle, erreurs du moteur CWM) ne l'est pas — le prompt reste
  français car **calibré** (la qualité de la génération P9 en
  dépend) ;
- **repli à trois niveaux** du côté front : langue courante → `fr`
  → la clé elle-même ; du côté backend : langue courante → `fr` →
  la clé — un trou dans un dictionnaire ne produit jamais un
  `undefined` à l'écran ;
- **liens dont la cible suit la langue** : attribut
  `data-i18n-href` (clé → URL dans chaque dictionnaire) — utilisé
  pour le texte **« CWM 2.0 » de l'entête**, qui link le README du
  dépôt CWM 2 **dans la langue sélectionnée**
  (FR → `README.md`, EN → `README.en.md` sur
  gitlab.univ-nantes.fr, `target="_blank"`). Le titre du lien
  (`data-i18n-title`) est localisé comme les autres infobulles ;
- **re-rendu au changement de langue** : chaque rendu dynamique
  (`renderResults`/`renderInfer`/`renderQuery`/`renderEntail`/
  `renderProve`/`renderCheck`/`renderIa`/méta-graphe) accepte un
  argument `tab` (défaut `true`) — le re-rendu i18n passe `false`
  pour ne ni basculer d'onglet ni (pour la preuve) re-dispatcher le
  texte dans l'éditeur ;
- le sélecteur de langue est un **simple `<select>`** (2 options)
  — pas de framework i18n, zéro dépendance, cohérent avec la
  politique du dépôt (comme CodeMirror/vis.js vendus en local,
  l'i18n est un petit module maison).

### P10.1 — Libellés bilingues des ontologies d'exercices ✅ (livrée le 2026-11-23)

**Objectif** : les **ontologies des exercices** (classes, propriétés,
individus) portent des `rdfs:label` **bilingues** (`@fr` / `@en`) et
l'application affiche les chaînes **dans la langue de l'app** —
l'étudiant en anglais ne lit plus de libellés français. Les **énoncés
d'exercices** sont traduits (`enonce.en.md`).

**Direction retenue** :

- **résolution de labels côté backend** (pas de `FILTER(lang(…))`
  dans les requêtes d'exercice — les lignes doubleraient par label,
  et le langage est dynamique côté front) : `engine._label_index`
  (par URI, liste des `rdfs:label` `(étiquette, valeur)`) +
  `engine._pick_label` — choix en **trois replis** : langue de
  l'app → libellé **sans étiquette** → **premier** libellé présent
  (deterministe : l'ordre des énoncés n'est **pas** fiable après
  `canonicalize()`, qui réordonne le store) ;
- `lang="fr"` (défaut/repli si ∉ `("fr","en")`) ajouté à
  `engine.infer` / `query` / `graph` / `list_exercises` /
  `load_exercise` ; la traduction s'applique aux **nœuds/arcs/
  attributs du graphe**, aux **lignes de requête** (`rows_raw` /
  `rows_reasoned` / `new_rows` — le diff est calculé sur les valeurs
  brutes, puis traduit) et aux **`new_facts`** d'infer (diff sur les
  IRI bruts, puis traduit). **Pas** d'entail/prove/check (contenu
  formel, pas de libellés) ;
- l'index de labels est construit sur la **KB close d'origine** (pas
  la clôture, qui n'en produit pas de nouveaux) ;
- **données bilingues** : `@en` ajouté à chaque label `@fr` existant
  ; **nouveaux labels typés** — `a rdfs:Property` (prédicats) /
  `a rdfs:Class` (classes) — obligatoire : le contrôle de
  plausibilité IA (P9) compte les `untyped_subjects` (sujets sans
  `rdf:type`), le test exige 0 ; unités dans les libellés de
  prédicats (`… (mg/100 g)`, `… (g/portion)`…) ; les **noms propres**
  (Alice–Eve, famille) restent **sans étiquette** (démo du repli —
  identiques dans les deux langues) ; les 3 maladies des corrigés
  (`insuffisanceRenale`, `hyperCholest`, `IIH`) reçoivent des
  libellés FR+EN ;
- **énoncés** : `enonce.en.md` **optionnel** par exercice
  (`enonce.md` = repli) ; le titre du menu = 1er `#` de l'énoncé de
  la langue ;
- **front** : `lang: i18nLang()` dans les bodies POST
  (`/api/infer`, `/api/query`, `/api/graph`) et `?lang=` sur
  `/api/exercises` / `/api/exercise` ; dans `reRenderAll()` :
  re-fetch query/infer (bodies actuels), graphe = re-fetch +
  **mise à jour in place** des labels dans les DataSets vis (pas de
  reconstruction du réseau), énoncé = re-fetch `/api/exercise` et
  MAJ **du panneau seulement** (jamais les éditeurs — le travail de
  l'étudiant n'est pas écrasé) ;
- **requêtes d'exercice** : sélectionnent des **ressources**
  (`?pat`, `?rec`, `?cond`) — plus de `rdfs:label ?libPat` (sinon
  une ligne par libellé) ; l'interface traduit les URI en libellés
  choisis ;
- **cache** : `lang` dans la requête → clé de cache distincte ;
  **mais** le cache disque est **partagé entre instances** et
  survit aux redémarrages (TTL 7 j) : une entrée écrite par une
  ancienne version du code (ex. instance éditée lancée avant le
  changement, engine gelé en mémoire) serait servie à la nouvelle.
  Garde-fou ajouté : **empreinte du code** (`cache.code_signature` —
  hash des `.py` du paquet + `exercises/`, `static/` exclue) incluse
  dans `Cache.make_key` : tout changement de code/données invalide
  automatiquement le cache disque (`server.CODE_SIG`, calculée au
  démarrage) ;
- **IA (P9)** : `entities` = simple comptage ; le prompt reste FR
  (calibré) mais la **`note` du modèle est demandée dans la langue
  de l'app** (`build_messages(lang=…)` : "You respond in English."
  + consigne 7 EN) — c'était la dernière chaîne FR visible en mode
  EN (signalée par l'utilisateur) ; vérifiée en direct (note EN en
  mode EN, note FR en mode FR).

**Faits techniques établis en P10.1** (à réutiliser) :

- `Literal` (CWM 2.0) a un attribut `lang` (`None` / `'fr'` /
  `'en'`) ; `value()` renvoie la chaîne **sans** tag ;
- SPARQL CWM : `?p rdfs:label ?lib` → **une ligne par label** ;
  `FILTER(lang(?lib) = "fr")` fonctionne mais le langage est
  dynamique côté front → la résolution reste côté backend ;
- `close()` garde l'ordre du document ; `canonicalize()` (chemin
  `query()`) **réordonne** → ne jamais compter sur l'ordre pour le
  « premier label » (d'où les deux premiers replis de
  `_pick_label`) ;
- en mode « attributs masqués », un `rdfs:label` est déjà LE
  libellé du nœud : il est **exclu** des attributs masqués
  (sinon « label Alice » apparaissait en pastille/bulle).
- Python ne fait pas de hot-reload : un processus lancé avant un
  changement de code garde l'engine **en mémoire** (fichiers `.py`
  lus au démarrage), tandis que les **statiques sont re-lues à
  chaque requête** — d'où des instances « front nouveau + backend
  ancien » silencieuses ; redémarrer le serveur après un pull ;
- le cache disque (`~/.cache/lab_tp` par défaut) est **partagé
  entre toutes les instances** : d'où l'empreinte de code dans la
  clé (ci-dessus) ; `ia_quota.json` y vit aussi (ne pas vider le
  répertoire sans précaution).

**Critère d'acceptation** : la bascule FR ↔ EN affiche les
libellés d'ontologie (graphe, lignes de requête, nouveaux faits,
titres du menu) et l'énoncé dans la nouvelle langue, sans toucher
les éditeurs ni reconstruire le réseau vis. ✔ (13 tests
`TestLabelsI18n` : replis, infer/query/graph fr/en, exercices
bilingues, repli sans `enonce.en.md`)

## 4. Risques & points de vigilance

| # | Risque | Mitigation |
|---|---|---|
| 1 | `think()` non garanti sur règles cycliques (boucle) | Timeout par requête dès P2 (thread + alarme) |
| 2 | Globales d'état (`diag.chatty_flag`, etc.) | Réinitialisées à chaque requête |
| 3 | Sémantique de l'incohérence dans CWM à documenter précisément | Validation dédiée en P2 ; doc dans le guide enseignant |
| 4 | `check` manipule `sys.argv`/`stdin` | Subprocess uniquement, jamais in-process |
| 5 | Coloration N3 : `@lezer/turtle` ne couvre pas les règles N3 | Extension Lezer maison (P1, itératif) |
| 6 | Politique « zéro dépendance » du dépôt | Backend stdlib ; CodeMirror commité dans `static/vendor/` ; **gunicorn** (P6) = dépendance de **déploiement** uniquement, jamais importée par le code du TP, dans `lab/requirements-deploy.txt` séparé |
| 7 | Performance sur gros graphes | Hors périmètre TP (documents de TP < quelques centaines de triples) ; timeout de garde |
| 8 | Timeout du raisonnement = thread **abandonné** (continue de tourner en fond) : OK en local-une-machine, vector de DoS (CPU/mémoire) sur un serveur partagé | P6 : raisonnement en subprocess tuable (pattern `check_proof`) + semaphore de concurrence |
| 9 | IA générative (P9) : non-déterminisme, **quotas ProxyIAg** (nombre de requêtes + volume de tokens), **confidentialité** (les données des exercices partent vers le provider) | Prompt contraint + contrôles a posteriori obligatoires (parse, `log:false`, garde de plausibilité **en Python sur la formule parsée** — le SPARQL de CWM ne supporte ni agrégats ni `MINUS`), régénération bornée, **compteur de quotas côté backend persisté avec le cache P8** (quota atteint → bouton désactivé), opt-in documenté, clé API dans `.env` (ignoré par git, chmod 600 — jamais en config versionnée) |

## 5. Journal

| Date | Événement |
|---|---|
| 2026-11-21 | Décisions actées (stack web locale stdlib, dossier `lab/`, public Master MIAGE) ; roadmap P0–P5 écrite |
| 2026-11-21 | **P0 livrée** : `engine.parse` (erreurs ligne/colonne + stats), serveur stdlib, page minimale, 10 tests (`make test-lab`) ; faits techniques établis (syntaxe `log:implies`, bnodes, EOF) |
| 2026-11-22 | **P1 livrée** : CodeMirror 6 en bundle local (esbuild, MIT), coloration Turtle (Lezer) + surcouche N3, auto-parse avec linter en gouttière, base URI, exports N3/Turtle/NTriples/RDF-XML (`engine.serialize` + `POST /api/serialize`) ; 20 tests (`make test-lab`) |
| 2026-11-22 | **P2 livrée** : second éditeur (règles N3), bouton **Raisonner** → `engine.infer` + `POST /api/infer` (clôture `think`/`applyRules`, diff nouveaux faits, incohérence `log:false`, timeout par thread), options mode/règles-stockées/timeout ; 9 tests `TestInfer` (29 au total) ; faits établis : `@forAll` obligatoire, sémantique `log:false`, pièges `value()`/`uriref()` et `Fragment`/`Symbol` |
| 2026-11-22 | **P3 livrée** : troisième éditeur (SPARQL) + case « raisonner avant d'interroger », `engine.query` + `POST /api/query` (SELECT/ASK, `language: "sparql"` sur `/api/parse`), diff avant/après raisonnement surligné, ASK en bannières ; 19 tests (48 au total) ; faits établis : SPARQL seul (N3QL reporté), ordre des variables lu dans le texte (pas dans la formule), valeur en sujet / nom en objet, lignes 0-indexées, `PREFIX` sans point final |
| 2026-11-22 | **P4 livrée** : éditeur 4 Conclusion/Preuve (onglets), `engine.entail`/`prove`/`check_proof` + `POST /api/entail` `/api/prove` `/api/check` (testIncludes sur clôture, génération de preuve auto-suffisante en sources `data:` + dump `qdr`, `check --report` en subprocess), bannières oui/non + *ex falso*, verdict valide/invalide + étapes de dérivation ; 20 tests (68 au total) ; 2 bugs CWM corrigés (`check --report` : variable sans fragment, ordre stdout texte/binaire) ; faits établis : `stayOpen` bloque la canonicalisation, `testIncludes` sans explosion, garde du global `diag.tracking` pour les threads abandonnés |
| 2026-11-22 | **P5 livrée** : pack TP — 2 exercices calibrés (`famille` échauffement, `recettes` principal avec calculs `math:`), mode « exercice » (découverte automatique, préchargement des éditeurs, affichage de l'énoncé), guide enseignant (déroulé 2 h, barème), convention d'exercice sans code ; 6 tests (74 au total) ; `recettes` vérifié de bout en bout (154 nouveaux faits, tableaux de l'énoncé reproduits) |
| 2026-11-22 | **Option vis.js livrée** : bouton « Graphe » + « après raisonnement » — graphe des triples (ressources bleu, littéraux vert, nœuds vides gris, **inférés** orange avec la clôture), `engine.graph` + `POST /api/graph` (nœuds/arcs JSON, troncature 3000 signalée, timeout), vis-network 10.1.5 + vis-data 7.1.9 UMD vendus en local (`static/vendor/vis/`, MIT, provenance documentée) ; 6 tests (80 au total) ; vérifié en navigateur (famille : 5 énoncés → 6 après raisonnement, arc `grandparentOf` inféré seul) |
| 2026-11-22 | **P6 écrite** (déploiement serveur, optionnelle) : le TP passe sur un serveur sans refonte (stateless, `--host 0.0.0.0` déjà présent, builtins `os:` en lecture seule) ; seul vrai changement de code = timeout du raisonnement en subprocess tuable (pattern `check_proof`) + semaphore de concurrence ; risque #8 ajouté (thread abandonné = vector de DoS en serveur partagé) |
| 2026-11-22 | **P7 écrite** (reprise d'ergonomie, optionnelle) : zones de résultats éparpillées et boutons aux objectifs différents → direction retenue : **graphe systématiquement visible** (panneau persistant re-rendu à chaque action, le bouton « Graphe » disparaît), barre d'actions unifiée, zone de résultats consolidée en onglets ; critère : un étudiant novice termine `famille` sans aide, graphe toujours visible et à jour ; option graphe « attributs masqués » (pastille + compteur sur le nœud, attributs dans la bulle contextuelle) ; énoncés rendus Markdown → HTML dans l'appli (.md conservé en source dans le dépôt) |
| 2026-11-22 | **P8 écrite** (cache des traitements, optionnelle) : le même traitement est très probablement demandé plusieurs fois en TP → cache **deux niveaux** (mémoire + **disque persisté**, gain sur plusieurs séances de TP — LRU borné + TTL par niveau, stdlib) sur les APIs pures (parse, infer, query, entail, prove, check, graph, serialize), clé = SHA-256 du payload complet, seuls les résultats complets et réussis cachés, priorité à `check_proof` (subprocess) et raisonnement ; critère : 2e occurrence < 10 ms avec `cached: true`, toute édition force le recalcul ; config en deux fichiers : `config.yaml` (chmod 600, non sensible — TTL, tailles, quotas) + `.env` (ignoré par git, chmod 600, sensible — provider, clé API, répertoire du cache) avec `.env.example` commité pour l'installation |
| 2026-11-23 | **P8 livrée** : cache des traitements à deux niveaux (mémoire LRU + **disque persisté** — survit aux redémarrages, gain cumulé sur plusieurs séances) sur les 8 APIs (parse, serialize, infer, query, entail, prove, check, graph) ; clé = SHA-256 du payload complet (JSON canonique), seuls les résultats complets et réussis cachés, drapeau `cached` dans la réponse ; `lab_web/cache.py` (stdlib, `threading.Lock`, écritures atomiques, dégradation mémoire seule si disque indisponible) ; config en deux fichiers : `config.yaml` (chmod 600, non sensible) + `.env` (git-ignoré, chmod 600, sensible — `CACHE_DIR`, `IA_*` pour la P9) avec `.example` commités ; 19 tests (99 au total) dont intégration serveur (2e occurrence servie du cache, erreur jamais cachée) ; vérifié : 2e `/api/infer` identique → `cached: true`, même résultat |
| 2026-11-23 | **P7 livrée** : reprise d'ergonomie — **layout 2 colonnes** (éditeurs + barre d'actions unifiée \| graphe persistant + résultats en onglets) ; **graphe systématiquement visible** (panneau permanent, re-rendu à chaque action : édition KB/règles, raisonnement, requête avec raisonnement, exercice, options, base URI — le bouton « Graphe » a disparu) ; **mode « attributs masqués »** (littéraux → pastille compteur sur le nœud, attributs dans la bulle contextuelle, `engine.graph(hide_literals=True)` + `attrs`) ; **résultats consolidés en onglets** (Parse/Raisonnement/Requête/Entraînement/Preuve/Export, auto-bascule sur les actions, point sur onglet masqué) ; **barre unifiée** groupée par objectif (Raisonnement/Interroger/Valider, options communes) ; **énoncés rendus Markdown → HTML** (convertisseur stdlib `engine.render_markdown`, texte échappé d'abord, `.md` restant source de vérité, `load_exercise` + `enonce_html`) ; version 0.2.0 ; 10 tests ajoutés (110 au total) ; vérifié en navigateur : parcours `famille` complet (graphe toujours à jour sans demande, 0/1 ligne + surlignage, entraînement oui, preuve valide, export), `recettes` avec attributs masqués (pastilles + infobulles) |
| 2026-11-23 | **P7 ajustée** : (1) **éditeur Conclusion/Preuve déplacé dans la colonne de droite** (à côté du graphe et des résultats) — une preuve générée (URI `data:` de plusieurs milliers de caractères sur une seule ligne, min-content CodeMirror énorme) ne gonfle plus la colonne des éditeurs ; (2) **largeur des colonnes ajustable par poignée de glissement** (25–75 %, persistée en localStorage) et **indépendante des résultats** — les pistes du grid passent de `1fr 1fr` (min-content auto : une preuve élargissait toute la page à ~9564 px) à `minmax(0, …)` partout, y compris en mode une colonne ; vérifié en navigateur : largeur identique avant/après Raisonner et Pourquoi ?, zéro overflow, poignée testée (glissement, bornes 25/75, persistance, valeur corrompue auto-guérie) |
| 2026-11-22 | **P9 écrite** (remplissage de la base par IA générative, optionnelle) : bouton « Remplir la base (IA) » — provider et modèle dans `config.yaml` (provider très probablement **ProxyIAg** — quotas en nombre de requêtes et en volume de tokens, comptés côté backend et persistés avec le cache P8, quota atteint → bouton désactivé ; clé API dans `.env` (ignoré par git, chmod 600), bouton désactivé sans config), appel `urllib` côté backend (le navigateur ne voit jamais la clé), prompt contraint (format N3 données seules, domaine de l'exercice, taille paramétrable, valeurs réalistes) ; contrôles a posteriori obligatoires : parse, **absence de `log:false`**, garde SPARQL structurelle, régénération bornée (3 tentatives) avant signalement ; texte généré dans l'éditeur (visible/modifiable, bannière « à vérifier »), hors cache P8 ; risque #9 ajouté (non-déterminisme, coût/quota, confidentialité — opt-in) |
| 2026-11-23 | **Projet autonome** : l'outil quitte le dépôt CWM (où il vivait dans `lab/`) pour le dépôt GitHub **edesmontils/cwm-lab** — CWM 2.0 (fork) devient l'unique dépendance (PyPI : `cwm` 2.9.3, publiée le 2026-11-23 ; dépôt source GitLab public) ; paquet `cwm_lab` (ex `lab.lab_web`), exercices et tests remontés à la racine, `pyproject.toml` (nom `cwm-lab`, commande `cwm-lab`, dépendance `cwm>=2.9.3`), `Makefile` (`make test` / `make serve`), CI GitHub Actions (Python 3.10/3.12, CWM installé depuis GitLab tant que `cwm` n'est pas sur PyPI) ; les chemins des phases ci-dessus restent ceux de l'emplacement historique (note d'en-tête) |
| 2026-11-23 | **Exercice `recettes` v2** (porté du dépôt CWM, où il était en WIP) : 9 recettes (2 ajoutées : poulet au vin blanc, crêpes « sans gluten »), 28 ingrédients à **9 axes de composition** /100 g (5 nouveaux : gras saturés, cholestérol, histamine, alcool, fructane), 11 conditions (5 absolues, 6 à seuil — cirrhose à seuil 0), 5 patients (David, Eve ajoutés), 14 règles ; 6 exercices (dont « le total exact par SPARQL `SUM` + patch ») ; **corrigés** dans `exercises/recettes/corriges/` (rénale, IIH, hypercholestérolémie, totaux) ; énoncé, guide enseignant et docs mis à jour |
| 2026-11-23 | **Fix : exercices invisibles en installation non éditable** — `EXERCISES_DIR` pointait « un niveau au-dessus du paquet » (la racine du dépôt) : `pip install .` (non éditable) copie le paquet dans `site-packages/` sans le reste du dépôt → menu Exercice vide. Les exercices passent **dans le paquet** (`cwm_lab/exercises/`, package-data `exercises/**/*`) : visibles en source, en `-e` et en installation PyPI. Version `0.3.0` |
| 2026-11-23 | **Fix : pastilles « attributs masqués »** (2 commits) — (1) les pastilles étaient positionnées avec `network.getPosition()` brut, qui renvoie les coordonnées **du réseau** (monde de la simulation) alors que la pastille est un élément HTML en coordonnées **écran** : avec le graphe recentré/zoomé (scale ≈ 0,17 sur `recettes`), le culling hors-canvas en coordonnées monde coupait quasiment toutes les pastilles → mode « attributs masqués » sans aucun compteur. Conversion monde → écran par la vue (vis 10.x n'expose pas `canvasToScreen` : `écran = monde × getScale() + (centre − getViewPosition() × getScale())`). (2) à la demande, les pastilles **échelonnent avec le zoom** : taille ET décalage depuis le centre du nœud multipliés par le scale de la vue (`transform: translate(-50%,-100%) scale(s)`), comme les nœuds et arcs du canvas — vérifié : le rapport de largeur des pastilles est égal au rapport de scale, au zoom avant (×1,61) comme au zoom arrière (×0,35) |
| 2026-11-23 | **`cwm-lab` 0.3.0 publiée sur PyPI** — https://pypi.org/project/cwm-lab/0.3.0/ (wheel + sdist, nom `cwm-lab` libre, première publication) : les étudiants s'installent en une commande, `pip install cwm-lab` (résout `cwm>=2.9.3` sur PyPI — les deux paquets du projet y sont désormais). Parcours de validation : build local (wheel 39 fichiers — 4 modules, static/ + vendor vis/CodeMirror, 16 fichiers d'exercices, `.example`), upload TestPyPI, **installation en venv vierge depuis TestPyPI puis depuis PyPI** : serveur démarrable, `/api/version` 0.3.0, menu exercices `famille` + `recettes`, raisonnement vérifié (`log:implies` → fait inféré) |
| 2026-11-23 | **P9 livrée** : remplissage de la base par IA générative — bouton « Remplir la base (IA) » (taille paramétrable ≈ N faits / M entités), prompt contraint (N3 **données seules** — zéro `log:implies`, domaine = énoncé + règles de l'exercice chargé sinon générique, valeurs réalistes qui déclenchent ET ne déclenchent pas les seuils, contexte entre balises `<domaine>`/`<regles>` traité comme donnée — anti-injection), appel **backend** `urllib` vers proxy API compatible OpenAI (défaut ProxyIAg institutionnel, HTTPS exigé — la clé ne transite jamais en clair ; le navigateur ne voit jamais la clé) ; **contrôles a posteriori** : parse (+ zéro règle), cohérence (`engine.infer` KB générée + règles existantes, absence de `log:false` ; timeout → avertissement, pas un rejet), plausibilité structurelle (faits/entités dans la plage ×0,5–×2, chaque entité typée) ; **régénération bornée** (3, prompt enrichi des rejets) puis signalement honnête ; **quotas de séance** (requêtes + tokens, plafonds `config.yaml`, comptés backend, **persistés avec le cache P8** — `ia_quota.json`, réinitialisés chaque jour, dégradation mémoire seule) ; texte généré **dans l'éditeur** + bannière « généré par IA, à vérifier » (masquée par toute édition) ; onglet de résultats « Génération (IA) » (contrôles, tentative, tokens, durée) ; **hors cache P8** ; absent la config → bouton désactivé avec raison explicite ; `cwm_lab/ia.py` (transport injectable), extensions `cache.py` (config `IA_URL` + quotas) et `server.py` (`GET /api/ia/status`, `POST /api/ia/generate` — 429 si quota épuisé) ; 43 tests (153 au total) dont intégration serveur (proxy fictif, réseau jamais touché) ; version 0.4.0. **Fait technique** : le SPARQL de CWM ne supporte ni agrégats (`COUNT` → « token inattendu "(" ») ni `MINUS`/`isIRI`/`BIND` → la garde de plausibilité est calculée en Python sur la formule parsée (la « garde SPARQL » de la spec n'est pas exprimable). **Ajustements de calibration** (vérification navigateur, proxy ProxyIAg réel sur `recettes`) : `max_tokens` réponse 2000 → **4000** (troncature systématique des documents à 2000), timeout proxy 60 → **120 s**, tolérance haute de plausibilité ×2 → **×3** (le modèle « complète » le domaine, ~100 faits sur `recettes` — ×2 rejetait tout) ; génération acceptée à la tentative 2 (94 faits / 22 entités, préfixes `rec:`/`ingr:`/`med:`/`math:` de l'exercice, 42 faits inférés, 0 `log:false`), ~60 s |
| 2026-11-23 | **`cwm-lab` 0.4.0 publiée sur PyPI** — https://pypi.org/project/cwm-lab/0.4.0/ (wheel + sdist) : la P9 (génération de données par IA, bouton « Remplir la base (IA) », quotas de séance) est installable en `pip install cwm-lab`. Validation : wheel 41 entrées (`ia.py` présent, `.env` **absent** — package-data explicites), **installation en venv vierge depuis TestPyPI puis depuis PyPI** : version 0.4.0, `cwm_lab.ia.generate` importable, `GET /api/ia/status` → `enabled: false` + raison explicite (clé/modèle absents) — l'appli démarre sans IA, le reste fonctionne |
| 2026-11-23 | **P10 livrée** : internationalisation de l'interface (FR par défaut, EN) — **sélecteur de langue dans la barre d'entête** (persistance localStorage, `<html lang>` + titre de page suivent) ; module `static/i18n.js` (dictionnaires fr/en, `t(key, …)` avec placeholders, attributs `data-i18n`/`-ph`/`-title`/`-aria` sur le HTML statique, repli trois niveaux) ; `app.js` : ~100 chaînes dynamiques passées en `t()` + **re-rendu au changement de langue** (dernier état de chaque rendu conservé, sans re-fetch, sans forcer l'onglet, sans reconstruire le réseau vis, sans écraser une preuve altérée à la main) ; **backend localisé** : `ia.py` table `MESSAGES` fr/en + `_msg()` — quota, erreurs proxy, contrôles (parse/cohérence/plausibilité), refus de génération, statut ; le front envoie `lang` (`/api/ia/status?lang=`, body `/api/ia/generate`, défaut + repli `fr`) ; **le prompt du modèle reste en français** (calibré), la note du modèle et les erreurs du parser CWM = contenu non localisé ; 12 tests (55 dans `test_ia`, 165 au total) ; version 0.5.0 |
| 2026-11-23 | **P10 — lien doc CWM 2.0 dans l'entête** : le texte « CWM 2.0 » du sous-titre de l'entête **link le README du dépôt CWM 2 (GitLab) dans la langue sélectionnée** — FR → `README.md`, EN → `README.en.md` (`target="_blank"`, infobulle localisée) ; nouveau mécanisme `data-i18n-href` dans `i18n.js` (la cible du lien est localisée comme le reste de l'interface : chaque dictionnaire porte sa propre URL, appliquée à l'init et au changement de langue) ; vérifié en navigateur (bascule FR↔EN : href, texte et infobulle suivent la langue, zéro erreur console) |
| 2026-11-23 | **`cwm-lab` 0.5.0 publiée sur PyPI** — https://pypi.org/project/cwm-lab/0.5.0/ (wheel + sdist) : la P10 complète (i18n FR/EN + sélecteur d'entête + lien doc CWM 2.0 localisé) est installable en `pip install cwm-lab`. Validation : wheel 41 entrées (`i18n.js` présent, `.env` **absent**), **installation en venv vierge depuis PyPI** : version 0.5.0, lien d'entête + cibles FR/EN dans le HTML/i18n installés, `cwm_lab.ia.LANGS` importable. *Nuance TestPyPI* : la 0.5.0 de l'index de test est un build préliminaire (avant le lien d'entête) — non remplaçable (nom de fichier consommé, l'API de suppression TestPyPI n'existe plus) ; seule la PyPI fait foi |
| 2026-11-23 | **P10.1 livrée** : libellés bilingues des ontologies d'exercices — `rdfs:label` `@fr`/`@en` sur les classes/propriétés/individus des deux exercices (prédicats/classes **typés** `rdfs:Property`/`rdfs:Class` — le contrôle de plausibilité IA exige 0 sujet non typé), noms propres **sans étiquette** (démo du repli), 3 maladies des corrigés libellées FR+EN ; **résolution côté backend** (`engine._label_index`/`_pick_label` : langue de l'app → sans étiquette → premier, déterministe après `canonicalize()`) — `lang` sur `infer`/`query`/`graph`/`list_exercises`/`load_exercise`, appliqué aux nouveaux faits, aux lignes de requête (diff sur valeurs brutes puis traduit), aux nœuds/arcs/attributs du graphe ; **énoncés traduits** (`enonce.en.md` optionnel, `enonce.md` = repli, titre du menu = 1er `#` de la langue) ; requêtes d'exercice sur **ressources** (plus de `rdfs:label ?libPat` — doublons) ; front : `lang` dans les bodies + `?lang=`, au changement de langue re-fetch infer/query/énoncé + **mise à jour in place** des DataSets vis (pas de reconstruction du réseau), éditeurs jamais touchés ; `rdfs:label` exclu des attributs masqués (déjà le libellé du nœud) ; recalibrage IA : `recettes` 774 faits / 108 entités (577/74 avant) ; 13 tests `TestLabelsI18n` (178 au total) ; version 0.5.1 |
| 2026-11-24 | **Fix P10.1 — cache disque partagé : empreinte du code dans la clé** : reproduction du signalement « le graphe / l'énoncé ne changent pas à la bascule de langue » — deux causes : (1) les instances lancées avant le code P10.1 (install éditable 8000, dev 8765) gardaient l'engine **en mémoire** (pas de hot-reload Python) alors que les statiques sont re-lues à chaque requête → front nouveau + backend ancien ; (2) le **cache disque est partagé entre instances** (TTL 7 j) et sa clé ne dépendait que du payload : des entrées écrites par l'ancien engine (qui ignorait `lang`) étaient servies au nouveau. Correction : `cache.code_signature()` (hash des `.py` du paquet + `exercises/`, `static/` exclue) incluse dans `Cache.make_key` (`sig`, calculée au démarrage — `server.CODE_SIG`) : tout changement de code ou de données d'exercices invalide automatiquement le cache disque ; 131 entrées obsolètes purgées (`ia_quota.json` préservé) ; instances 8000/8931 redémarrées ; 2 tests (`make_key` sensible à `sig`, `code_signature` stable/sensible/`""` si dossier absent) — 180 tests OK ; vérifié en navigateur sur 8000 : bascule FR↔EN, énoncé + meta + libellés du graphe in place, zéro erreur console ; version inchangée (0.5.1 non publiée) |
| 2026-11-24 | **Fix P10.1 (2) — note du modèle IA dans la langue de l'app** : signalement « encore une phrase en français » en mode EN — la **`note`** du modèle (seul texte naturel de la réponse, affichée dans la bannière) restait FR : le prompt disait « Tu réponds en français ». Correction minimale : `build_messages(lang=…)` — system « You respond in English. » + consigne 7 en EN (« one-sentence summary … written in English ») ; le reste du prompt reste FR (calibré) ; repli `fr` si langue inconnue ; `generate()` transmet `lang` ; 2 tests (prompt fr/en/repli, `generate` → messages du proxy) ; **vérifié en direct** : génération famille EN → note « A family dataset with 8 people… », génération FR → note FR ; 57 tests `test_ia` (182 au total) ; version inchangée (0.5.1 non publiée) |

| 2026-11-24 | **`cwm-lab` 0.5.1 publiée sur PyPI** — https://pypi.org/project/cwm-lab/0.5.1/ (wheel + sdist) : la P10.1 complète (libellés bilingues résolus côté backend, **empreinte du code dans la clé du cache disque**, **note du modèle IA dans la langue de l'app**) est installable en `pip install cwm-lab`. Validation : wheel 43 entrées (`i18n.js`, `enonce.en.md` bilingues, `ia.py` avec consigne « written in English », `cache.py` avec `code_signature`, `.env` **absent**), **installation en venv vierge depuis TestPyPI puis depuis PyPI** : version 0.5.1, serveur démarrable, `/api/version` 0.5.1, titres FR/EN corrects, libellé du graphe « est parent de » (clé de cache avec empreinte de code), `ia status` sans clé → désactivé avec raison explicite localisée |
| 2026-11-24 | **Ergonomie — sélecteur de langue sur la première ligne de l'entête, aligné à droite** : le sélecteur (label + `#lang-select`) quitte la barre d'outils pour la ligne du titre (`#titlebar` en flex : titre à gauche, `margin-left: auto` sur le groupe langue) — visible avant tout autre contrôle, sans toucher au wiring (mêmes ids `lang-select` / `bar.lang`, i18n.js et app.js inchangés) ; vérifié en navigateur : bascule FR↔EN depuis la nouvelle position, zéro erreur console ; **version 0.5.2** (0.5.1 publiée sur PyPI le 24/11 — le code local ne doit plus porter ce numéro) |
| 2026-11-24 | **Graphe — focus de sélection** : un clic sur un nœud masque les nœuds qui ne le concernent pas (restent le nœud, ses voisins directs dans les deux sens, et les arcs qui le relient) ; un clic sur le vide (désélection) réaffiche tout ; multi-sélection (Ctrl/clic) = union des voisinages. Implémentation `graphFocusSelection()` (app.js) par `hidden` sur les DataSets vis — patch, pas suppression : positions et vue de l'utilisateur préservées, la mise à jour des libellés de langue (in place par id) conserve le masque (vérifié : bascule FR↔EN avec focus actif, 10 nœuds / 11 arcs masqués avant et après) ; les pastilles d'attributs masqués suivent (pas de pastille sur nœud masqué). Événements vis `selectNode` / `deselectNode` — vérifiés dans le bundle : émis par `commitAndEmit` sur le chemin tap/clic utilisateur (Hammer, seuil pan 5 px), **pas** sur `selectNodes()` programmatique ; `deselect` n'existe pas dans ce bundle (`deselectNode` couvre le clic sur le vide). Vérifié en navigateur : voisinage exact (test auto-vérifié sur la famille, simple + multi), zéro erreur console. Poignée de debug `window.__cwmLab` (`graph()` / `focus()`) ajoutée — le module étant en scope fermée, elle rend le réseau vis accessible depuis la console et les tests. Version inchangée (0.5.2 non publiée) |
| 2026-11-24 | **Aide** : petit bouton « ? » dans la barre d'état (bas de page, aligné à droite) ouvrant une popup « très large » qui explique **ce que fait chaque bouton et chaque case à cocher** (barre d'entête, raisonnement, interrogation, validation, génération IA, graphe — 19 entrées, 6 sections). Contenu statique en `data-i18n` (index.html) : la popup suit la langue de l'interface via `applyStatic()`, ouverte ou fermée que soit le popup (vérifié bascule FR↔EN). Fermeture : bouton « Fermer », clic sur le fond, touche Échap — le focus revient au bouton « ? » (vérifié en navigateur, zéro erreur console). Version inchangée (0.5.2 non publiée) |
| 2026-11-24 | **Prompts IA externalisés** : les textes du prompt du bouton « Remplir la base (IA) » sont sortis du code Python dans **`cwm_lab/prompts/*.txt`** (7 fichiers : `system.txt`, `user.txt`, `rules_constraint.txt`, `json_fr.txt` / `json_en.txt`, `generic_domain.txt`, `feedback.txt`) pour pouvoir être **affinés à la main** ; contrat, placeholders (`${…}`, style `string.Template`) et règles de retouche documentés dans `prompts/README.md`. `build_messages` (ia.py) assemblage des blocs conditionnels : les bornes de troncature restent codées ; **re-lecture à chaque génération** (cache par mtime/size — une retouche est effective sans redémarrer le serveur) ; **repli sur les textes d'origine en dur** si un fichier est introuvable (une retouche ratée ne casse jamais la génération) ; `prompts/**/*` ajouté au package-data (wheel vérifié : 8 fichiers présents, pas de `.env`). Prompt assemblé identique à l'origine (vérifié sur recettes, avec feedback ; cas générique). 3 tests ajoutés (fichiers présents dans le wheel, retouche effective sans rechargement, repli fichier supprimé) — 185 tests OK. Instances 8000/8931 redémarrées (code Python) ; IA active (27 requêtes restantes). Version inchangée (0.5.2 non publiée) |
| 2026-11-24 | **Prompts IA en Markdown** : les fichiers de prompt passent de ``.txt`` à **``.md``** (rédigés en Markdown — titres ``##``, liste numérotée, gras, code en ligne : lisible pour qui retouche, compris par le modèle ; tableaux/images/liens à éviter, documenté dans ``prompts/README.md``). 7 fichiers renommés (``system.md``, ``user.md``, ``rules_constraint.md``, ``json_fr.md`` / ``json_en.md``, ``generic_domain.md``, ``feedback.md``) ; ``_DEFAULT_PROMPTS`` (repli d'usine) et les appels ``_fill`` de ``build_messages`` suivent ; mots-clés des tests préservés (DONNÉES SEULES, log:implies, JSON, familial, written in English, Tu réponds en français., You respond in English., rejet_precedent) — 185 tests OK. Version inchangée (0.5.2 non publiée) |
| 2026-11-24 | **Prompts — README enrichi** : section « Comment le domaine est défini » dans ``prompts/README.md`` — le domaine du prompt n'est pas un champ structuré mais l'**énoncé Markdown de l'exercice chargé** + **ses règles courantes** (éditables par l'étudiant) ; données de l'exercice jamais envoyées (génération nouvelle, pas copie) ; repli ``generic_domain.md`` sans exercice ; bornes de troncuration (8 000 / 6 000 car.) ; anti-injection (blocs = DONNÉE contextuelle) ; table « pour cibler X, retouche Y » (domaine → enonce.md, vocabulaire → règles / contrainte 6, taille/format → user.md, langue de la note → json_fr/en). Docs seul — 185 tests OK sans changement. Version inchangée (0.5.2 non publiée) |
| 2026-11-24 | **Prompts — README bilingue** : ``prompts/README.en.md`` — traduction anglaise intégrale du README du dossier de prompts (fichiers et placeholders, blocs conditionnels, « How the domain is defined » + table « To target… / Edit », règles de retouche) ; réferences croisées en tête des deux fichiers. Les mots-clés FR du prompt sont conservés tels quels dans la version EN (ils sont des chaînes du prompt, pas de la doc). Docs seul — 185 tests OK sans changement. Version inchangée (0.5.2 non publiée) |
| 2026-11-24 | **Documentation bilingue** : `README.en.md` (traduction intégrale du README général — crédits, statut P0–P10.1 + livraisons 2026-11-24, lancement, configuration, arborescence mise à jour avec `prompts/`, principes) et `cwm_lab/exercises/GUIDE_ENSEIGNANT.en.md` (teacher's guide — déroulé 2 h, points de vigilance, barème, corrigés) ; références croisées en tête des versions FR. Le `ROADMAP.md` reste **FR seul** : c'est un journal de travail interne (historique des livraisons), pas une documentation destinée à l'utilisateur/enseignant — décision confirmée. Le guide EN voyage dans le wheel (package-data `exercises/**/*`, vérifié). Docs seul — 185 tests OK sans changement. Version inchangée (0.5.2 non publiée) |