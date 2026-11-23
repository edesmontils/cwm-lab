# Exercice — Recettes, composition et contre-indications alimentaires

Base de connaissances N3 de **recettes** dont la contre-indication est
**calculée par les règles** à partir de la **composition des ingrédients**
et du **profil médical du patient** (allergies, maladies).

## Fichiers

| Fichier            | Espace de nom | Contenu                                                        |
|--------------------|---------------|----------------------------------------------------------------|
| `ingredients.n3`   | `ingr:`       | 28 ingrédients : allergènes (qualitatif) + 9 axes de composition /100 g |
| `recettes.n3`      | `rec:`        | 9 recettes : ingrédients + quantités en g / portion           |
| `medical.n3`       | `med:`        | 11 conditions (5 absolues, 6 à seuil), 5 patients            |
| `regles.n3`        | —             | 14 règles N3 (chaînage avant)                                 |
| `corriges/`        | —             | Corrigés des exercices (à charger **avec** la base)            |

Les trois espaces de nom sont **indépendants** : la sémantique des
recettes (`rec:`), des ingrédients (`ingr:`) et du médical (`med:`)
n'ont de liens qu'aux **arêtes** (`rec:contient`, `med:provoque`,
`med:contreIndication`), pas aux racines des IRI.

## Modèle

**Données**

- Un ingrédient : `ingr:contientAllergene <composant>` (qualitatif) et 9
  axes de composition **par 100 g** : `contientSodium`,
  `contientPurines`, `contientPotassium`, `contientGrasSature`,
  `contientSucre`, `contientFructane`, `contientCholestrol`,
  `contientHistamine`, `contientAlcool`.
  - **en service dans les règles** : sodium, purines, sucre, gras
    saturés, histamine, alcool ;
  - **réservés aux exercices** (les données sont déjà là) : potassium
    (rénale), fructane (IIH), cholestérol (hypercholestérolémie).
- Une recette : `rec:contient [ rec:ingredient <i> ; rec:quantite <g> ]`.
- Une condition : `a med:Allergie` (règle **absolue**) ou
  `a med:Maladie` (règle **à seuil** + `med:seuil<X> <valeur>` **par
  portion**). Le type est marqué : `med:type med:absolu` / `med:seuil`.
  Particularité : `med:cirrhose` a un seuil à **0** — une règle absolue
  par la porte des seuils (la moindre goutte d'alcool suffit).
- Un patient : `med:presente <condition>` (1 ou plusieurs).

**Règles** (voir `regles.n3`)

1. **(A) Absolue** (qualitative, une seule règle pour tous les allergènes) :
   un ingrédient qui *porte* un composant X, dont X *provoque*
   (`med:provoque`, en données) la condition M →
   `?r med:contreIndication M`. La quantité est indifférente.
   La contamination croisée passe par la même porte : `ingr:farineSF`
   porte le composant gluten sans l'avoir « dans la recette » (ligne
   partagée) — c'est le cas des crêpes « sans gluten ».
2. **(B) À seuil** (quantitative, par nutriment, 6 nutriments × 2 règles) :
   contribution = `quantite g × teneur / 100 g` (`math:product` +
   `math:quotient`) ; si elle dépasse le seuil déclaré dans les données
   (`math:greaterThan`) → contre-indication. Le seuil est **un fait** :
   le bouger ne demande aucune règle modifiée.
3. **(C) Agrégation patient** : une condition qui frappe une recette
   interdit la recette à chaque patient qui la présente
   (`rec:nePeutPasManger`).

## Lancer

```sh
# CWM en ligne de commande (après pip install cwm-lab, qui apporte cwm)
cwm cwm_lab/exercises/recettes/*.n3 --think

# Outil cwm-lab : les 3 fichiers de données dans l'éditeur de faits,
# regles.n3 dans l'éditeur de règles, puis « Raisonner ».
# Avant/après raisonnement : aucun nePeutPasManger dans les données
# brutes, tout est inféré — l'écart pédagogique clé du TP.
```

Tableau patient × recette × motif (SPARQL) :

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

Contre-indications par recette (le nombre entre parenthèses est la
contribution de l'ingrédient responsable, par portion) :

| Recette                | Contre-indications inférées                              |
|------------------------|----------------------------------------------------------|
| Soupe de tomates       | *(aucune — la recette « universelle »)*                  |
| Gratin de brocoli      | lait · **hypertension** (sel 3 g → 1163 mg) · **cardiopathie** (crème 18 g) |
| Saumon aux lentilles   | poisson · **goutte** (saumon 500, lentilles 270 mg) · **histamine** (saumon 600 mg) |
| Tiramisu               | lait, œuf, gluten · **diabète** (sucre 50 g) · **cardiopathie** (mascarpone 36 g) |
| Soupe de sate          | arachide, poisson (sauce) · **goutte** (poulet 195 mg) · **cardiopathie** (coco 34 g) |
| Crêpes arachide        | gluten, œuf, lait, arachide · **diabète** (sucre 40 g) · **cardiopathie** (beurre 15.3 g) |
| Salade niçoise         | œuf, poisson (thon) · **goutte** (thon 288 mg) · **hypertension** (olives 1044 mg) · **histamine** (thon 480 mg) |
| Poulet au vin blanc    | lait (crème, beurre) · **goutte** (poulet 195 mg) · **cardiopathie** (crème 18 g) · **histamine** (vin 120 mg) · **cirrhose** (alcool 18 g) |
| Crêpes « sans gluten » | **gluten de trace** (contamination croisée), œuf, lait · **diabète** (sucre 40 g) · **cardiopathie** (beurre 15.3 g) |

Par patient :

| Patient (conditions)                          | Ne peut PAS manger                                            | Peut manger              |
|-----------------------------------------------|---------------------------------------------------------------|--------------------------|
| Alice (arachide, goutte)                      | crêpes · sate · saumon · niçoise · poulet au vin              | soupe · gratin · tiramisu · crêpes SF |
| Bob (cœliaque, hypertension)                  | crêpes · tiramisu · crêpes SF · gratin · niçoise              | soupe · saumon · sate · poulet au vin |
| Carole (diabète, lait)                        | tiramisu · crêpes · gratin · crêpes SF · poulet au vin        | soupe · saumon · sate · niçoise |
| David (cardiopathie, histamine)               | **tout, sauf la soupe de tomates**                             | soupe                    |
| Eve (cirrhose)                                | poulet au vin blanc seulement                                  | les 8 autres             |

## Exercices

1. **Bouger un seuil** : `med:seuilPurines` de `150` à `300`.
   Qui gagne quel plat ? (Le thon de la niçoise tombe à 288 mg :
   Alice la retrouve — David non, le thon à 480 mg d'histamine
   dépasse toujours son seuil ; le saumon, à 500 mg de purines,
   reste interdit aux deux.)
2. **Ajouter une maladie** — le patron « 1 fait + 2 règles » :
   insuffisance rénale (potassium, seuil 600), IIH (fructane, seuil 2),
   hypercholestérolémie (cholestérol, seuil 200).
   **Corrigés** : `corriges/exo-renal.n3`, `corriges/exo-iib.n3`,
   `corriges/exo-cholesterol.n3` (charger avec la base, vérifier).
3. **Ajouter un patient** : Franck, **hypertension seulement**.
   Peut-il manger les crêpes ? (Le régime de la base dit oui —
   aucun ingrédient seul ne dépasse 1000 mg, max = sel 775 mg —
   alors que le total est 1039 mg. Charger `corriges/exo-totaux.n3` :
   les crêpes et les crêpes SF deviennent contre-indiquées.)
4. **Preuves** : `--why=u` (ou l'onglet « preuves » du lab) sur une
   contre-indication — chaîne règle absolue → agrégation, ou calcul
   de contribution → seuil → agrégation.
5. **Contamination croisée** : pourquoi les crêpes « sans gluten »
   sont-elles interdites à Bob ? Et est-ce « correct » ? (« peut
   contenir » ≠ « contient » : en pratique on distingue trace
   certifiée et contamination possible — que faudrait-il modéliser ?)
6. **(Avancé) Le total exact par SPARQL** : les contributions sont
   dans la clôture — produire le sodium total par recette en
   requête (`SUM`), le réinjecter (patch) et comparer au seuil.
   CWM est « le sed/awk du RDF » : chaîner les outils est idiomatique.

## Limites du modèle (à faire discuter)

Les règles à seuil testent la contribution de **chaque ingrédient
seul** : condition **suffisante mais pas nécessaire** (pas
d'agrégation des contributions de la recette). Conséquences dans la
base :

- Franck (hypertension seul) pourrait manger les crêpes (total
  1039 mg > 1000) — **erreur** ;
- le total histamine du sate (106 mg) dépasse le seuil sans qu'aucun
  ingrédient seul le fasse (max = sauce au poisson 75 mg) ;
- la niçoise (IIH, fructane 3.32) passe sous le seuil par ingrédient.

Paradoxe : dans **cette** base, aucun menu patient n'est faussé par la
simplification (les faux négatifs concernent des plats déjà perdus
pour d'autres motifs) — le contre-exemple devient visible avec Franck.

Pourquoi l'agrégation exacte est-elle difficile **en N3 pur** ?
- pas de **liste construite depuis les faits** (on ne peut pas
  « collecter » les contributions de la recette) ;
- pas de **négation** (un « budget » décrémen par règle, façon
  `seuil - Σ contributions`, diverge : la même contribution est
  soustraite à l'infini — on ne peut pas marquer « déjà comptée ») ;
- pas d'**itération** sur un ensemble.

D'où les approches de contournement, du plus pragmatique au plus
« pipeline » :

1. **totaux déclarés en données** (étiquette nutritionnelle) + règle
   de comparaison — c'est le choix des bases réelles
   (`corriges/exo-totaux.n3`) ;
2. **SPARQL `SUM` + patch** : la requête calcule, le raisonneur
   consomme (exo 6) ;
3. sortir de N3 pour l'agrégation (service de calcul, SPARQL
   property path + aggregation côté moteur complet).

Le modèle ignore aussi : les seuils **journaliers** (ici par portion),
les **interactions** entre composants, l'**incertitude** des valeurs
(« ≈ 500 mg »), et le seuil de **réaction individuelle** aux
allergènes (certains patients réagissent à la trace d'arachide,
d'autres tolèrent le contaminant incident).

## À développer

Ce développement ajoute à la version initiale (7 recettes, 3 maladies à
seuil, 3 patients) : 2 recettes (poulet au vin blanc, crêpes « sans
gluten »), 2 ingrédients (vin blanc, farine « sans gluten »), 5 axes de
composition (gras saturés, cholestérol, histamine, alcool, fructane),
3 conditions à seuil (cardiopathie, intolérance à l'histamine,
cirrhose) et 2 patients (David, Eve). Il reste à explorer :

- le **contenant incident** comme *qualité* du composant
  (`contientAllergene [ :composant ingr:gluten ; :niveau :trace ]`)
  avec des règles à seuil de traçabilité ;
- les seuils **par jour** et l'accumulation des portions ;
- la **valeur d'incertitude** sur les compositions
  (`[ :valeur 500 ; :marge 50 ]`) et règles sur bornes ;
- de nouvelles conditions (diabète : index glycémique ;
  colopathie : sorbitol ; insuffisance rénale : phosphore…).

Chaque nouvel axe = 1 propriété sur les ingrédients + 2 règles +
1 maladie : la base est construite pour ça — et c'est le point
pédagogique central : **la connaissance est en données, le
raisonnement est en règles, les deux se complètent sans se mêler.**
