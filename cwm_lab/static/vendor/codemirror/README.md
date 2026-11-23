# CodeMirror 6 — bundle local (P1)

Ce dossier contient le bundle **CodeMirror 6** utilisé par l'outil TP
(`cwm_lab/static/app.js`), **vendu en local** : pas de CDN, aucune
dépendance réseau au moment de l'exécution (décision actée dans
`lab/ROADMAP.md`).

- `codemirror.js` — bundle ES module (minifié) : l'API publique utilisée
  par `app.js` (ré-exportée depuis `entry.js`) ;
- `entry.js` — point d'entrée du bundle, conservé pour pouvoir le
  **regénérer** ;
- `LICENSE.md` — licences (tout le bundle est **MIT**).

## Provenance

Bundle généré avec **esbuild** (outillage de build, absent du dépôt) à
partir des paquets npm suivants :

| Paquet | Version | Rôle |
|---|---|---|
| `codemirror` | 6.0.2 | `basicSetup` |
| `@codemirror/state` | 6.7.6 | `EditorState`, `EditorSelection` |
| `@codemirror/view` | 6.43.15 | `EditorView`, `keymap`, `Decoration` (styles par défaut injectés par `StyleModule` dans le JS — pas de CSS séparé) |
| `@codemirror/language` | 6.13.1 | `syntaxHighlighting`, `HighlightStyle` |
| `@codemirror/commands` | 6.11.1 | `defaultKeymap`, `history` |
| `@codemirror/search` | 6.7.2 | `searchKeymap` |
| `@codemirror/autocomplete` | 6.20.4 | `closeBrackets`, `autocompletion` |
| `@codemirror/lint` | 6.9.8 | `linter`, `lintGutter` (erreurs de parse dans la gouttière) |
| `@lezer/highlight` | 1.2.5 | `tags` (balises de coloration) |
| `@lezer/lr` | 1.4.12 | parser LR de Lezer |
| `@lezer/common` | 1.5.6 | (dépendance) |
| `codemirror-lang-turtle` | 0.0.2 | **langage Turtle** (parser Lezer : `turtle()`, `TurtleLanguage`) |
| `crelt`, `style-mod`, `w3c-keyname`, `@marijn/find-cluster-break` | — | dépendances des paquets ci-dessus |

## Regénérer le bundle

```sh
mkdir cm6 && cd cm6 && npm init -y
npm i --no-audit --no-fund esbuild \
  @codemirror/state @codemirror/view @codemirror/language \
  @codemirror/commands @codemirror/search @codemirror/autocomplete \
  @codemirror/lint @lezer/common @lezer/highlight @lezer/lr \
  codemirror codemirror-lang-turtle
cp <ce dossier>/entry.js .
./node_modules/.bin/esbuild entry.js --bundle --format=esm --minify \
  --outfile=codemirror.js
```

## Note sur la coloration N3

Le paquet `codemirror-lang-turtle` colore la syntaxe **Turtle** (IRIs,
préfixes, littéraux, listes, nœuds vides, commentaires). Les extensions
spécifiques à N3 (`@forAll`, `@forSome`, formules `{ … } log:implies { … }`)
sortent de la grammaire Turtle : le parser Lezer les signale comme erreurs
de *tokenisation* sans faire planter l'éditeur, et `app.js` applique un
surlignage complémentaire de ces mots-clés (voir `app.js`).
