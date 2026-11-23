# exercises/ — exercices du TP

Un **exercice** est un sous-dossier de ce répertoire. L'outil le
découvre automatiquement (menu **Exercice** du bandeau) et le charge
dans les éditeurs via `GET /api/exercise?name=<dossier>`.

## Convention d'un dossier d'exercice

| Fichier | Rôle |
|---|---|
| `enonce.md` | **obligatoire** — l'énoncé (affiché en haut de page). Le premier titre `# …` sert de libellé dans le menu |
| `*.n3` | les données — `regles.n3` va dans l'éditeur « règles », **les autres fichiers sont concaténés** (ordre alphabétique) dans l'éditeur « données » |
| `context.json` | **optionnel** — préchargements : `{"query": "…", "conclusion": "…", "base_uri": "…"}` |

Au chargement, les documents sont **validés par parse** : un exercice
cassé ne se charge pas (message d'erreur par document).

## Exercices disponibles

| Dossier | Durée conseillée | Contenu |
|---|---|---|
| [`famille/`](famille/enonce.md) | ~30 min | échauffement : un graphe de 5 triples + la règle du grand-parent — parcourt toutes les fonctions de l'outil (parse, raisonnement, diff de requête, entraînement, preuve, altération) |
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
