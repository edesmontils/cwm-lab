# CWM Lab — outil de TP Web sémantique (CWM 2.0)

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
- **Date** : 2026-11-23 (projet autonome ; livraison P0–P9 + reprise d'ergonomie P7)
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

**P9 livrée** (2026-11-23) : **remplissage de la base par IA
générative** — le bouton **« Remplir la base (IA) »** (barre
d'actions, taille paramétrable : ≈ N faits / M entités) génère un
jeu de données N3 réaliste et l'injecte **dans l'éditeur « données
»** (visible, modifiable, supprimable — jamais une base cachée),
avec une bannière « généré par IA, à vérifier » masquée par toute
édition manuelle. Le prompt est contraint (N3 **données seules**,
aucune règle `log:implies` ; domaine = énoncé + règles de
l'exercice chargé, sinon domaine générique ; valeurs réalistes qui
déclenchent **et ne déclenchent pas** les seuils des règles
existantes). L'appel part **du backend** vers un proxy API
compatible OpenAI (défaut : ProxyIAg institutionnel) : le
navigateur ne voit jamais la clé. **Contrôles a posteriori
obligatoires** — 1 parse (et zéro règle détectée), 2 cohérence
(raisonnement KB générée + règles existantes, absence de
`log:false` ; timeout des règles non convergentes → avertissement,
pas un rejet), 3 plausibilité structurelle (faits/entités dans la
plage demandée, chaque entité typée) — et **régénération bornée**
(3 tentatives, le prompt est enrichi des rejets précédents) puis
signalement honnête. **Quotas de séance** (requêtes + tokens,
plafonds `config.yaml`, comptés côté backend, **persistés avec le
cache P8**, réinitialisés chaque jour) : épuisé → bouton
désactivé. Hors cache P8 (non déterministe, coûteux). Absente la
config (`.env`) → bouton désactivé avec message explicite, l'appli
fonctionne sans IA. `ia.py` (+ extensions de `cache.py` et de
`server.py`), 43 tests dont l'intégration serveur (proxy fictif,
réseau jamais touché).

**Confidentialité (opt-in)** : quand l'étudiant clique sur le
bouton, l'énoncé et les règles de l'exercice chargé partent vers le
provider pour construire le prompt (contexte de domaine). Rien
n'est envoyé sans ce clic ; la taille et le contenu du prompt sont
bornés (énoncé ≤ 8 k caractères, règles ≤ 6 k).

**P10 livrée** (2026-11-23) : **internationalisation de
l'interface** — l'application est disponible en **français (par
défaut) et en anglais**, avec un **sélecteur de langue dans la
barre d'entête** (préférence persistée en localStorage ; `<html
lang>` et le titre de page suivent la langue). Le texte
**« CWM 2.0 »** du sous-titre de l'entête pointe vers le **README
du dépôt CWM 2 dans la langue sélectionnée** (FR → `README.md`,
EN → `README.en.md`, `target="_blank"` — attribut
`data-i18n-href`). Le module
`static/i18n.js` (zéro dépendance) porte les deux dictionnaires et
applique les chaînes statiques via des attributs `data-i18n`
(texte, placeholder, infobulles, aria) ; les chaînes dynamiques
(résultats, bannières, erreurs) passent par `t(key, …)` dans
`app.js` et sont **re-rendues au changement de langue** — sans
re-fetch, sans forcer l'onglet actif, sans reconstruire le graphe
(la vue utilisateur est préservée) et sans écraser une preuve
altérée à la main. Côté backend, les messages de l'IA (quota,
erreurs proxy, contrôles, refus de génération, statut) sont
localisés dans `ia.py` (table `MESSAGES` fr/en) : le front envoie
sa langue (`/api/ia/status?lang=`, `lang` dans le body de
`/api/ia/generate` ; défaut et repli `fr`). **Hors périmètre
(contenu, pas interface)** : les énoncés des exercices, la note du
modèle, les erreurs du moteur de parse CWM (anglais technique) — et
le **prompt du modèle reste en français** (calibré sur les
énoncés du TP). 12 tests ; version `0.5.0`.

**P10.1 livrée** (2026-11-23) : **libellés bilingues des
ontologies d'exercices** — les `rdfs:label` des données
(`@fr` / `@en` sur classes, propriétés et individus) sont
**résolus côté backend** dans la langue de l'application :
l'interface n'affiche que des chaînes prêtes à l'emploi, les IRI ne
changent jamais. Choix en trois replis : libellé de la langue →
libellé sans étiquette → premier libellé présent (deterministe,
indépendant de l'ordre des énoncés après `canonicalize()`).
Appliqué aux **nouvelles lignes de requête** (raw / raisonné /
diff), aux **nouveaux faits** de « Raisonner » (diff calculé sur
les IRI bruts, puis traduit), aux **nœuds-ressources, arcs et
attributs masqués** du graphe, et aux **titres du menu** des
exercices. Au changement de langue, ces contenus sont **re-fetchés**
dans la nouvelle langue (re-rendu à la même place ; le graphe est
mis à jour **in place** dans les DataSets vis, sans reconstruire le
réseau — la vue de l'utilisateur est préservée) ; les éditeurs ne
sont **jamais** touchés. Les ontologies des deux exercices sont
bilingues (prédicats/classes typés `rdfs:Property`/`rdfs:Class` —
le contrôle de plausibilité IA exige 0 sujet non typé), les noms
propres restent **sans étiquette** (démo du repli), et les
**énoncés sont traduits** (`enonce.en.md` optionnel par exercice,
`enonce.md` = repli). Les requêtes d'exercice sélectionnent des
**ressources** (une variable sur `rdfs:label` doublerait les
lignes). Le paramètre `lang` entre dans la clé de cache ; et comme
le cache disque est **partagé entre instances** et survit aux
redémarrages (TTL 7 j), la clé porte aussi une **empreinte du code
et des données d'exercices** (`cache.code_signature`, calculée au
démarrage) : un changement de code invalide automatiquement tout le
cache — jamais une entrée écrite par une version antérieure de
l'engine. 13 tests + 2 tests de l'empreinte de cache ;
version `0.5.1`.

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
dépôt. `make test` exécute les tests unitaires (153) ; `make serve`
démarre le serveur.

## Configuration (P8/P9, facultative)

L'appli démarre **sans aucun fichier de config** (valeurs par
défaut ; l'IA est alors désactivée — le reste de l'outil
fonctionne). Deux fichiers optionnels, dans `cwm_lab/` :

- `config.yaml` — paramètres **non sensibles** : rétention du cache
  disque/mémoire (`ttl_disk`, `ttl_memory`), taille max disque,
  nombre d'entrées mémoire, et pour la P9 les plafonds de **quota
  de séance de l'IA** (`ia_max_requests`, `ia_max_tokens`,
  `ia_max_attempts`, `ia_timeout`, `ia_max_tokens_response`).
  Installer :
  `cp cwm_lab/config.yaml.example cwm_lab/config.yaml && chmod 600 cwm_lab/config.yaml` ;
- `.env` — **données sensibles / locales** (ignoré par git) :
  répertoire du cache (`CACHE_DIR`, défaut `~/.cache/lab_tp`), et
  pour la P9 l'IA : `IA_URL` (défaut : le proxy institutionnel),
  `IA_MODEL` (alias du modèle, ex. `proxyiag/mistral-small-24b`),
  `IA_API_KEY` (clé `sk-…`, révoquable — **jamais** dans une config
  versionnée). Installer :
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
│   ├── cache.py         # P8 : cache deux niveaux (mémoire + disque) + config
│   ├── ia.py            # P9 : remplissage de la base par IA (proxy, contrôles)
│   ├── config.yaml.example  # config non sensible (TTL, tailles, quotas IA)
│   ├── .env.example         # config sensible (cache dir, IA) — facultatif
│   ├── static/
│   │   ├── index.html   # tableau de bord (2 colonnes — éditeurs + barre
│   │   │                #   d'actions | graphe persistant + onglets)
│   │   ├── app.js       # éditeur CodeMirror + appels API + affichage
│   │   │                #   (onglets de résultats, graphe auto, pastilles)
│   │   ├── i18n.js      # P10 : dictionnaires FR/EN + t() + sélecteur
│   │   │                #   de langue (persistance, re-rendu i18n)
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
