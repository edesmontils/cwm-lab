# cwm-lab — Outil TP Web sémantique (CWM 2.0)

> **Application web locale** pour un TP de Web sémantique (Master MIAGE)
> sur les notions de **cohérence**, **validité** et **règles** —
> tout ce que sait faire [CWM 2.0](https://gitlab.univ-nantes.fr/desmontils-e/cwm) :
> parser N3/Turtle, raisonner (chaînage avant), interroger (SPARQL),
> détecter les incohérences, tester l'inférence, générer et vérifier
> les preuves.
>
> Projet autonome : **CWM 2.0 est la seule dépendance** (publiée sur
> PyPI sous le nom [`cwm`](https://pypi.org/project/cwm/), source :
> [dépôt GitLab public](https://gitlab.univ-nantes.fr/desmontils-e/cwm)).

## Crédits

- **Auteur** : Emmanuel Desmontils
- **Institution** : Nantes Université
- **Copyright** : © 2026 Emmanuel Desmontils — Nantes Université
- **Date** : 2026-11-23 (projet autonome ; livraison P0–P8 + reprise d'ergonomie P7)
- **Version** : `cwm_lab.__version__` (affichée dans le pied de
  page de l'outil, servie par `GET /api/version`)
- **Licence** : Apache-2.0 (code, voir `LICENSE`) ; le moteur
  CWM 2.0 (dépendance) est sous licence W3C Software (code
  d'origine) / Apache-2.0 (modifications du fork) ; CodeMirror 6 et
  vis.js vendus en local (MIT, voir `cwm_lab/static/vendor/`).

## Statut

**P0 livrée** (2026-11-21) : parse N3/Turtle avec erreurs
ligne/colonne et stats, serveur stdlib, page minimale, tests
(`make test`).

**P1 livrée** (2026-11-22) : éditeur CodeMirror 6 (bundle local,
coloration Turtle + surcouche N3), auto-parse au frappage avec
erreurs surlignées dans la gouttière, base URI configurable,
exports N3 / Turtle / NTriples / RDF/XML (Turtle/NTriples refusés
si le graphe n'est pas du RDF pur, comme `cwm --turtle`).

**P2 livrée** (2026-11-22) : second éditeur pour les **règles N3**
(`{ … } log:implies { … } .`, variables déclarées avec `@forAll`),
bouton **Raisonner** → clôture (`think` = convergence, `applyRules`
= 1 passe, règles stockées ou non), **liste des nouveaux faits**,
signal d'**incohérence** (présence de `log:false`, en rouge) et
**timeout** propre sur les règles non convergentes — rien ne bloque
jamais le TP.

**P3 livrée** (2026-11-22) : troisième éditeur pour la **requête
SPARQL** (`PREFIX : <…>` + `SELECT` / `ASK`), case **« raisonner avant
d'interroger »** : la même requête s'exécute sur la KB brute *et* sur
la clôture, les **lignes nouvelles du diff avant/après sont surlignées**
— l'écart pédagogique clé du TP. L'exemple préchargé (grand-parent)
renvoie 0 ligne brute et 1 ligne après raisonnement. ASK s'affiche en
bannière (vrai/faux, avant/après). `POST /api/query`, `engine.query`.

**P4 livrée** (2026-11-22) : éditeur **Conclusion / Preuve**
(onglets, dans la colonne de droite). **« Entraîne ? »** : la clôture
(données + règles) contient-elle la conclusion ? → oui/non
(`testIncludes`, avertissement *ex falso* si la clôture est
incohérente). **« Pourquoi ? »** : génération de la **preuve** N3 de
la clôture, affichée colorée dans l'onglet « Preuve » — la preuve est
**auto-suffisante** (ses sources sont des URI `data:`, le texte des
documents est embarqué) et **altérable à la main**. **« Vérifier la
preuve »** : `check` rejoue la dérivation dans un subprocess →
verdict **valide / invalide** + étapes de dérivation numérotées. Une
preuve altérée (un prédicat de la conclusion, une source…) est
**rejetée**. `engine.entail` / `engine.prove` / `engine.check_proof`,
`POST /api/entail` / `/api/prove` / `/api/check`.

**P5 livrée** (2026-11-22) : **pack TP**. Le menu **Exercice** du
bandeau charge un exercice dans les éditeurs (données, règles,
requête, conclusion) et affiche son **énoncé** :

- `cwm_lab/exercises/famille/` — échauffement (~30 min) : parcourt
  toutes les fonctions de l'outil en miniature ;
- `cwm_lab/exercises/recettes/` — exercice principal (~60–90 min) :
  contre-indications alimentaires calculées par règles N3 (allergènes
  absolus + nutriments à seuil avec calculs `math:`), 9 recettes,
  5 patients, 6 exercices + **corrigés** (`recettes/corriges/`) +
  discussion des limites du modèle ;
- `cwm_lab/exercises/GUIDE_ENSEIGNANT.md` — déroulé 2 h, points de
  vigilance, barème suggéré ;
- convention d'exercice (dossier `enonce.md` + `*.n3` +
  `context.json` optionnel) documentée dans
  `cwm_lab/exercises/README.md` — un nouvel exercice s'ajoute sans
  code. Les exercices sont **dans le paquet** : ils voyagent avec
  `pip install` (source ou PyPI).

`engine.list_exercises` / `engine.load_exercise`,
`GET /api/exercises`, `GET /api/exercise?name=…`.

Le **graphe des triples** (option vis.js de la roadmap, vendue en
local) — ressources (bleu), littéraux (vert), nœuds vides (gris) ;
avec « après raisonnement », les nœuds créés par les règles et les
arcs nouveaux sont surlignés en orange. `engine.graph`,
`POST /api/graph`. (Depuis P7, il est **toujours visible** — voir ci-dessous.)

**P8 livrée** (2026-11-23) : **cache des traitements**. En TP, le
même traitement (parse, raisonnement, requête, preuve,
vérification de preuve, graphe, sérialisation) revient très
probablement : il est servi depuis un cache **à deux niveaux** —
mémoire (LRU, TTL 5 min) et **disque persisté** (TTL 7 jours,
borné 200 Mo) — au lieu d'être recalculé. La seconde occurrence
d'un traitement est quasi instantanée, et le cache **survit aux
redémarrages** : le gain se cumule sur plusieurs séances. Clé =
SHA-256 du payload complet (toute édition force le recalcul) ;
seuls les résultats complets et réussis sont cachés ; la réponse
porte le drapeau `cached`. Configuration facultative
(`config.yaml` non sensible, `.env` sensible/git-ignoré —
exemples commités) ; `cache.py`, 19 tests dont l'intégration
serveur.

**P7 livrée** (2026-11-23) : **reprise d'ergonomie** — l'interface
est repensée pour un étudiant qui découvre l'outil :

- **layout 2 colonnes** : à gauche les éditeurs + une
  **barre d'actions unifiée** groupée par objectif (Raisonnement /
  Interroger / Valider) ; à droite le **graphe, toujours visible**,
  l'**éditeur Conclusion/Preuve** et les **résultats consolidés en
  onglets** (Parse / Raisonnement / Requête / Entraînement /
  Preuve / Export) — fini les N blocs empilés. L'éditeur
  Conclusion/Preuve est à droite : une preuve générée fait des
  dizaines de lignes (URI `data:` de plusieurs milliers de
  caractères), elle ne gonfle plus la colonne des éditeurs ;
- **largeur des colonnes ajustable** : poignée de glissement entre
  les deux colonnes (25–75 %, persistée en localStorage) ; les
  pistes du grid sont `minmax(0, …)` — **un résultat ne change
  jamais la largeur des colonnes** ;
- **graphe systématiquement visible et à jour** : le bouton
  « Graphe » a disparu — le panneau persistant se re-rend à chaque
  action (édition des données/règles, Raisonner, Interroger avec
  raisonnement, chargement d'exercice, changement des options) ;
  les cases « après raisonnement » et « attributs masqués » sont
  dans l'en-tête du panneau ;
- **mode « attributs masqués »** : les nœuds-littéraux sont
  remplacés par une **pastille compteur** sur le nœud (les
  attributs masqués sont listés dans la bulle contextuelle au
  survol) — le graphe devient lisible quand une ressource porte
  beaucoup de littéraux (`recettes`) ;
- **énoncés rendus Markdown → HTML** : convertisseur minimal
  **stdlib** (`engine.render_markdown` : titres, listes imbriquées,
  tableaux, blocs code, gras/italique ; texte échappé d'abord,
  aucune injection possible) ; les `.md` restent la source de
  vérité dans le dépôt.

10 tests ajoutés (110 au total) ; version `0.2.0`.

Décisions actées :

- **Stack** : backend Python **stdlib uniquement** (`http.server` + JSON),
  frontend navigateur avec **CodeMirror 6** (vendu en local, pas de CDN) ;
  zéro dépendance ajoutée au dépôt ;
- **Dépendance** : CWM 2.0 (fork) — unique dépendance, publiée sur
  PyPI sous le nom `cwm` ;
- **Public** : Master MIAGE.

## Lancement

```sh
pip install cwm-lab    # installe l'outil + CWM 2.0 (cwm, dépendance unique)

cwm-lab                # → http://127.0.0.1:8000
cwm-lab --port 8080
```

`pip install cwm-lab` résout automatiquement `cwm>=2.9.3` (CWM 2.0,
fork, sur PyPI) ; en développement : `pip install -e .` depuis ce
dépôt. `make test` exécute les tests unitaires (110) ; `make serve`
démarre le serveur.

## Configuration (P8, facultative)

L'appli démarre **sans aucun fichier de config** (valeurs par
défaut). Deux fichiers optionnels, dans `cwm_lab/` :

- `config.yaml` — paramètres **non sensibles** : rétention du cache
  disque/mémoire (`ttl_disk`, `ttl_memory`), taille max disque,
  nombre d'entrées mémoire. Installer :
  `cp cwm_lab/config.yaml.example cwm_lab/config.yaml && chmod 600 cwm_lab/config.yaml` ;
- `.env` — **données sensibles / locales** (ignoré par git) :
  répertoire du cache (`CACHE_DIR`, défaut `~/.cache/lab_tp`), et
  pour la P9, provider/modèle/clé de l'IA (`IA_*`). Installer :
  `cp cwm_lab/.env.example cwm_lab/.env && chmod 600 cwm_lab/.env`.

## Arborescence

```
cwm-lab/
├── README.md            # ce fichier
├── ROADMAP.md           # feuille de route (phases, critères, risques)
├── pyproject.toml       # paquet cwm-lab (dépendance : cwm>=2.9.3)
├── Makefile             # test / serve
├── cwm_lab/
│   ├── __init__.py      # version
│   ├── server.py        # http.server + endpoints /api/*
│   ├── engine.py        # wrapper stateless sur les API swap (cœur testable)
│   ├── cache.py         # P8 : cache deux niveaux (mémoire + disque)
│   ├── config.yaml.example  # config non sensible (TTL, tailles) — facultatif
│   ├── .env.example         # config sensible (cache dir, IA) — facultatif
│   ├── static/
│   │   ├── index.html   # tableau de bord (2 colonnes — éditeurs + barre
│   │   │                #   d'actions | graphe persistant + onglets)
│   │   ├── app.js       # éditeur CodeMirror + appels API + affichage
│   │   │                #   (onglets de résultats, graphe auto, pastilles)
│   │   ├── style.css    # styles du tableau de bord
│   │   ├── vendor/codemirror/  # CodeMirror 6 en bundle local (esbuild)
│   │   └── vendor/vis/         # vis-network + vis-data (UMD, graphe)
│   └── exercises/       # exercices de TP : .n3 + énoncés .md + corrigés
│                        #   (dans le paquet — voyagent avec pip install)
└── tests/               # tests de cwm_lab (engine, cache, serveur)
```

## Principes

- **Stateless** : chaque requête reconstruit le store depuis le texte des
  éditeurs ; pas d'état serveur à gérer — le **cache** (P8) est une
  **optimisation, pas un état** : seule la réponse JSON déjà calculée
  est mémorisée (mémoire + disque), jamais un store ;
- **API CWM directes** : `think()`, `applyRules()`, `applyQueries()`,
  `applySparqlQueries()`, `testIncludes()`, `why`/`explainFormula`,
  parser `notation3` — pas de passage par les CLI, sauf `check`
  (subprocess `python -m swap.check`, car il manipule `sys.argv`/`stdin`) ;
- **Timeout par requête** : une règle récursive ne doit jamais bloquer
  le TP (chaînage avant non garanti sur des règles cycliques) ;
- **Zéro dépendance propre** : CWM 2.0 est la seule dépendance ;
  CodeMirror et vis.js sont téléchargés une fois dans
  `cwm_lab/static/vendor/` et commités (pas de CDN).
