# exercises/ — exercices du TP

Un **exercice** est un sous-dossier de ce répertoire. L'outil le
découvre automatiquement (menu **Exercice** du bandeau) et le charge
dans les éditeurs via `GET /api/exercise?name=<dossier>`.

## Convention d'un dossier d'exercice

| Fichier | Rôle |
|---|---|
| `enonce.md` | **obligatoire** — l'énoncé en français (affiché en haut de page). Le premier titre `# …` sert de libellé dans le menu |
| `enonce.en.md` | **optionnel** — l'énoncé en anglais, servi quand l'application est en anglais (repli : `enonce.md`) |
| `*.n3` | les données — `regles.n3` va dans l'éditeur « règles », **les autres fichiers sont concaténés** (ordre alphabétique) dans l'éditeur « données » |
| `context.json` | **optionnel** — préchargements : `{"query": "…", "conclusion": "…", "base_uri": "…"}` |

Au chargement, les documents sont **validés par parse** : un exercice
cassé ne se charge pas (message d'erreur par document).

## Libellés bilingues (`rdfs:label`)

Les ontologies des exercices portent des `rdfs:label` **bilingues**
(`@fr` / `@en`) sur les classes, les propriétés et les individus.
L'outil affiche le libellé **de la langue de l'application** (bascule
FR/EN en haut à droite), avec deux replis : libellé sans étiquette,
puis premier libellé présent. La résolution se fait **côté backend** :

- les nouvelles lignes de requête, les nouveaux faits de
  « Raisonner » et les nœuds/arcs du graphe reçoivent le libellé
  choisi — les IRI ne changent jamais ;
- les requêtes d'exercice sélectionnent donc des **ressources**
  (`?pat`, `?rec`) et non des `rdfs:label` — une variable sur
  `rdfs:label` produirait **une ligne par libellé** (doublons) ;
- les noms propres identiques dans les deux langues (Alice, Bob…)
  portent un libellé **sans étiquette**.

## Exercices disponibles

| Dossier | Durée conseillée | Contenu |
|---|---|---|
| [`famille/`](famille/enonce.md) | ~30 min | échauffement : un petit graphe familial (5 triples de faits + l'ontologie bilingue) + la règle du grand-parent — parcourt toutes les fonctions de l'outil (parse, raisonnement, diff de requête, entraînement, preuve, altération) |
| [`recettes/`](recettes/enonce.md) | ~60–90 min | exercice principal : contre-indications alimentaires calculées par règles N3 (allergènes absolus + nutriments à seuil, avec calculs `math:`) sur 9 recettes et 5 patients ; 6 exercices, corrigés (`corriges/`) + discussion des limites du modèle |

**Guide enseignant** (déroulé 2 h, points de vigilance, barème) :
[`GUIDE_ENSEIGNANT.md`](GUIDE_ENSEIGNANT.md).

## Vérifier un exercice sans l'outil

```sh
# depuis la racine du dépôt : clôture d'un exercice
cwm <fichiers .n3 de l'exercice> --think
```

## Ajouter un nouvel exercice

1. créer le dossier avec `enonce.md` + les `.n3` (+ `context.json` si
   besoin) ;
2. vérifier que `cwm *.n3 --think` converge (pas de
   règle non bornée) ;
3. recharger la page de l'outil : le nouvel exercice apparaît dans le
   menu (pas d'enregistrement à faire) ;
4. ajouter une ligne dans le tableau « Exercices disponibles » ci-dessus.
