# Exercice — Recettes, composition et contre-indications alimentaires

Base de connaissances N3 de **recettes** dont la contre-indication est
**calculée par les règles** à partir de la **composition des ingrédients**
et du **profil médical du patient** (allergies, maladies).

## Fichiers

| Fichier            | Espace de nom | Contenu                                                        |
|--------------------|---------------|----------------------------------------------------------------|
| `ingredients.n3`   | `ingr:`       | Ingrédients : allergènes (qualitatif) + composition /100 g    |
| `recettes.n3`      | `rec:`        | Recettes : liste d'ingrédients + quantités en g / portion     |
| `medical.n3`       | `med:`        | Conditions (allergies absolues, maladies à seuil), patients   |
| `regles.n3`        | —             | Les règles N3 (chaînage avant)                                 |

Les trois espaces de nom sont **indépendants** : la sémantique des
recettes (`rec:`), des ingrédients (`ingr:`) et du médical (`med:`)
n'ont de liens qu'aux **arêtes** (`rec:contient`, `med:provoque`,
`med:contreIndication`), pas aux racines des IRI.

## Modèle (résumé)

**Données**

- Un ingrédient : `ingr:contientAllergene <composant>` (qualitatif) et
  `ingr:contientSodium / Purines / Sucre / Potassium <valeur>` (par 100 g).
- Une recette : `rec:contient [ rec:ingredient <i> ; rec:quantite <g> ]`.
- Une condition : `a med:Allergie` (règle **absolue**, `med:type med:absolu`)
  ou `a med:Maladie` (règle **à seuil**, `med:type med:seuil` +
  `med:seuil<Something> <valeur>` **par portion**).
- Un patient : `med:presente <condition>` (0, 1 ou plusieurs).

**Règles** (voir `regles.n3`)

1. **Absolue** (qualitative, une seule règle pour tous les allergènes) :
   un ingrédient qui *porte* un composant X, dont X *provoque* (données
   `med:provoque`) la condition M → la recette est `med:contreIndication M`.
   La quantité est indifférente : la présence suffit.
2. **À seuil** (quantitative, par nutriment) : contribution du nutriment
   d'un ingrédient = `quantite g × teneur / 100 g` (calculées
   `math:product` + `math:quotient`) ; si elle dépasse le seuil déclaré
   dans les données de la maladie (`math:greaterThan`) → contre-indication.
3. **Agrégation patient** : une condition qui frappe une recette interdit
   la recette à chaque patient qui la présente (`rec:nePeutPasManger`).

## Lancer

```sh
# CWM en ligne de commande (depuis la racine du dépôt)
python3 -m swap.cwm lab/exercises/recettes/*.n3 --think

# Outil lab/ : les 3 fichiers de données dans l'éditeur de faits,
# regles.n3 dans l'éditeur de règles, puis « Raisonner ».
# La même requête SPARQL avant/après raisonnement est vide/remplie :
# c'est l'écart pédagogique clé (aucun nePeutPasManger dans les données
# brutes, tout est inféré).
```

Exemple de requête (tableau patient × recette × motif) :

```sparql
PREFIX rec: <http://example.org/recette#>
PREFIX med: <http://example.org/medical#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?pat ?rec ?libPat ?libRec ?libCond WHERE {
  ?pat rec:nePeutPasManger ?rec .
  ?pat rdfs:label ?libPat .
  ?rec rdfs:label ?libRec .
  OPTIONAL { ?rec med:contreIndication ?cond . ?cond rdfs:label ?libCond . }
}
```

## Résultats attendus (après raisonnement)

| Recette                | Contre-indications inférées                              |
|------------------------|----------------------------------------------------------|
| Soupe de tomates       | *(aucune — la recette « universelle »)*                  |
| Gratin de brocoli      | lait (fromage, crème) · **hypertension** (sel 3 g → 1163 mg) |
| Saumon aux lentilles   | poisson (saumon) · **goutte** (saumon 500 mg, lentilles 270 mg) |
| Tiramisu               | lait, œuf, gluten (mascarpone, œuf, biscuit) · **diabète** (sucre 50 g) |
| Soupe de sate          | arachide, poisson (sauce) · **goutte** (poulet 195 mg)   |
| Crêpes arachide        | gluten, œuf, lait, arachide · **diabète** (sucre 40 g)   |
| Salade niçoise         | œuf, poisson (thon) · **goutte** (thon 288 mg) · **hypertension** (olives 1044 mg) |

Ensuite, patient par patient :

| Patient (conditions)                       | Ne peut PAS manger                                  | Peut manger                    |
|--------------------------------------------|-----------------------------------------------------|--------------------------------|
| Alice (arachide, goutte)                   | crêpes · niçoise · saumon · sate                   | soupe · gratin · tiramisu      |
| Bob (cœliaque, hypertension)               | crêpes · gratin · niçoise · tiramisu               | soupe · saumon · sate          |
| Carole (diabète, lait)                     | crêpes · gratin · tiramisu                         | soupe · saumon · sate · niçoise|

## Exercices

1. **Bouger un seuil** : passer `med:seuilPurines` de `150` à `300`.
   Qui gagne quel plat ? (Réponse : le thon de la niçoise tombe à
   288 mg — Alice retrouve la salade niçoise ; le saumon reste interdit.)
2. **Ajouter une maladie** : `med:insuffisanceRenale` avec
   `med:seuilPotassium 600` — la composition potassium est déjà dans
   `ingredients.n3` : il faut 2 règles (contribution + seuil).
   Qu'est-ce qui tombe ? (Gratin : pomme de terre 875 mg, brocoli 700 mg ;
   Saumon : 660 mg.)
3. **Ajouter un patient** : David, allergie à l'œuf. Quels plats perd-il ?
4. **Preuves** : `--why=u` (ou l'onglet « preuves » du lab) sur une
   contre-indication — vérifier la chaîne règle absolue → agrégation,
   ou règle seuil (avec le calcul) → agrégation.
5. **Contre-exemple** : créer `rec:plateau` avec `olives 40 g` +
   `thon 100 g`. Chaque ingrédient seul reste sous le seuil sodium
   (696 mg et 500 mg) mais l'apport total (1196 mg) le dépasse : la règle
   conclut « pas contre-indiquée ». C'est faux — voir ci-dessous.

## Limites du modèle (à faire discuter)

Les règles à seuil testent la contribution de **chaque ingrédient seul** :
condition **suffisante mais pas nécessaire** (pas d'agrégation des
contributions de la recette). En N3, sommer un nombre arbitraire de
contributions demande un travail supplémentaire :

- approches possibles : récursion sur les listes de contributions,
  ou déclarer directement la composition agrégée de la recette en
  données (au prix de la dupliquer), ou passer par une requête
  (SPARQL + `SUM`) qui alimente un patch ;
- le modèle ignore aussi : les seuils **journaliers** (ici par portion),
  l'apport cumulé d'un allergène **sous le seuil de réaction**,
  les interactions (fructose + sorbitol…), les valeurs d'incertitude.

## À développer (composition des ingrédients)

Les axes `contientSodium / Purines / Sucre / Potassium` couvrent déjà
cinq conditions ; on peut en ajouter : **gras saturés** (cardiopathie),
**cholestérol**, **fibres** (constipation/colopathie), **alcool**,
**histamine** (intolérance, qualitative), **fructane** (syndrome de
l'intestin irritable), **sodium ajouté vs sodium naturel**, et les
**contaminations croisées** (allergène incident à l'usure d'une machine).
Chaque nouvel axe = 1 propriété sur les ingrédients + 2 règles + 1 maladie :
la base est construite pour ça.
