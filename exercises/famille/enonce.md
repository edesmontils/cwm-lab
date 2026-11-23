# Exercice 1 — Famille (échauffement, ~30 min)

Un petit graphe familial et une règle de grand-parent. L'objectif :
parcourir **toutes** les fonctions de l'outil, en miniature, avant
l'exercice « recettes ».

## Fichiers

| Fichier | Contenu |
|---|---|
| `donnees.n3` | 3 personnes, 2 liens `:parentOf` |
| `regles.n3` | la règle du grand-parent (`log:implies`) |

## Parcours

1. **Parse** : chargez l'exercice, le parse se fait tout seul au
   chargement. Vérifiez les stats (5 triples, 1 règle). Cassez une
   ligne volontairement (un point manquant) : observez l'erreur dans la
   **gouttière** (ligne/colonne) et le panneau. Remettez-la.
2. **Raisonner** : « Raisonner » → combien de **nouveaux faits** ?
   (`:alice :grandparentOf :carl` — un seul : la règle ne produit
   rien d'autre.) Changez en mode « 1 passe » : le résultat change-t-il
   ici ? (Non — une passe suffit. La différence n'apparaîtra que sur
   les règles à plusieurs niveaux, cf. exercice 2.)
3. **Interroger** : la requête préchargée sélectionne les
   grands-parents. Exécutez **sans** raisonnement : combien de lignes ?
   (0 — le fait n'est pas dans les données brutes.) Cochez « raisonner
   avant d'interroger » : 1 ligne, **surlignée** (diff avant/après).
4. **Entraîne ?** : la conclusion préchargée est
   `:alice :grandparentOf :carl .` — le bouton répond **oui**.
   Changez-la en `:carl :grandparentOf :alice .` : **non**.
   Et `:alice :parentOf :carl .` ? (Non — la parenté directe
   n'est pas dérivée ; seul le grand-parentage l'est.)
5. **Pourquoi ?** : générez la preuve. Observez sa structure : des
   étapes `:Parsing` (les sources, embarquées en URI `data:`), des
   étapes `:Inference` (la règle appliquée avec ses **bindings**), et
   la formule prouvée. « Vérifier la preuve » → **valide**, avec les
   étapes de dérivation numérotées.
6. **Altérer** : dans la preuve, remplacez `grandparentOf` par
   `siblingOf` (hors des longues sources `data:`) puis « Vérifier la
   preuve » → **invalide**, avec la raison. C'est l'essentiel du TP :
   une preuve est une *dérivation* qui se re-joue, pas un certificat.

## Questions

- Q1. Pourquoi faut-il `@forAll :x , :y , :z .` ? Que se passerait-il
  sans (indice : combien de nouveaux faits « Raisonner » trouverait-il,
  et lesquels) ?
- Q2. La règle produit-elle `:alice :grandparentOf :alice .` ?
  (Cherchez le fait dans la clôture.) Peut-on écrire une règle qui
  produirait une boucle sans fin ? (Indice : « 1 passe » vs
  « convergence » + le timeout.)

## Résultats attendus

- Clôture : 5 données + 1 nouveau fait = 6 énoncés, 0 incohérence ;
- Requête : 0 ligne brute, 1 ligne après raisonnement ;
- Entraînement : oui pour `:alice :grandparentOf :carl`, non pour les
  deux autres ;
- Preuve : valide, puis invalide après altération.
