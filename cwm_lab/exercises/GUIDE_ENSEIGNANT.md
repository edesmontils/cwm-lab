# Guide enseignant — CWM Lab (TP Web sémantique, CWM 2.0)

> Durée : **2 h** — Public : Master MIAGE — Prérequis : aucun
> (notions de base en Python utiles, non exigées). Matériel : l'outil
> [cwm-lab](https://github.com/edesmontils/cwm-lab) (CWM 2.0 en
> dépendance), un navigateur, Python ≥ 3.9.

## Mise en place (avant le TP)

```sh
pip install cwm-lab
cwm-lab                              # → http://127.0.0.1:8000
```

Vérifier que la page charge et que l'exemple préchargé (famille) se
parse (badge « OK »). Les exercices se chargent depuis le menu
**Exercice** du bandeau supérieur : `famille` (échauffement) et
`recettes` (exercice principal).

## Déroulé (2 h)

| Temps | Séquence | Ce que l'étudiant fait |
|---|---|---|
| 00:00–00:10 | Accueil | Lancer l'outil, observer l'exemple préchargé, parse automatique, casser une ligne et observer l'erreur dans la gouttière |
| 00:10–00:40 | **Exercice 1 — Famille** | Charger l'exercice `famille`, suivre le parcours de l'énoncé : Raisonner (1 nouveau fait) → Interroger avec/sans raisonnement (diff 0→1 ligne) → Entraîne ? (oui/non) → Pourquoi ? (preuve) → **altérer la preuve** → Vérifier (rejet) |
| 00:40–01:40 | **Exercice 2 — Recettes** | Charger `recettes` (3 fichiers de données + règles). Raisonner, exécuter la requête préchargée **avant/après** raisonnement (le diff est l'écart pédagogique clé : 0 ligne brute, tout est inféré). Puis les questions 1–3 de l'énoncé (bouger un seuil, ajouter une maladie — corrigés dans `corriges/` —, ajouter un patient Franck + `corriges/exo-totaux.n3`) |
| 01:40–01:55 | Preuves + contamination | Question 4 : générer la preuve d'une contre-indication, identifier la chaîne (règle absolue ou règle à seuil **avec le calcul** → agrégation patient), vérifier, puis altérer. Question 5 : contamination croisée des crêpes « sans gluten » (« peut contenir » ≠ « contient ») |
| 01:55–02:00 | Discussion | « Limites du modèle » de l'énoncé : condition suffisante mais pas nécessaire, agrégation (le total de Franck : 1039 mg > 1000 mg mais aucun ingrédient seul ne dépasse), seuils journaliers. (Question 6 — SPARQL `SUM` + patch — en prolongement) |

Variantes :
- **Court (1 h 30)** : sauter la question 2 de recettes (ajouter une
  maladie) et la discussion ;
- **Long (3 h)** : ajouter la section « À développer » de l'énoncé
  recettes (nouvel axe nutritionnel = 1 propriété + 2 règles + 1
  maladie) et/ou l'implémentation de l'agrégation des contributions.

## Points de vigilance (pièges classiques, observés en TP)

1. **Variables de règle** : sans `@forAll :x , :y , :z .`, un `:x` nu
   est une **constante** — la règle ne se déclenche que littéralement
   (symptôme : « 0 nouveau fait »). C'est le piège n° 1.
2. **`false` vs `log:false`** : le mot-clé nu `false` est un littéral
   ignoré silencieusement ; l'incohérence CWM est la constante
   `log:false` (triple `log:false log:false log:false` dans la clôture).
3. **SPARQL ≠ N3** : `PREFIX : <…>` **sans** point final dans la
   requête ; `@prefix : <…> .` dans les données. Les étudiants
   mélangent les deux syntaxes.
4. **Base URI** : les termes relatifs (`:alice`) se résolvent contre la
   base URI du bandeau — la changer en cours de route change l'identité
   des termes (et casse les comparaisons).
5. **Timeout** : une règle qui produit sans fin (ex. un existential en
   conclusion) ne bloque pas l'outil — le timeout renvoie une erreur
   propre. Montrer-le est un objectif pédagogique (chaînage avant non
   garanti sur règles cycliques).
6. **Preuves** : l'altération doit se faire **hors des sources
   `data:`** (les longues lignes encodées) — sinon la preuve ne se
   parse plus (rejet « non parsable ») au lieu du rejet « dérivation
   non rejouable ». Les deux rejets sont instructifs : les montrer.
7. **Mode « 1 passe » vs « convergence »** : sur `recettes`, les règles
   à seuil ont deux niveaux (contribution → contre-indication →
   patient) : en « 1 passe », les `nePeutPasManger` n'apparaissent
   **pas** — excellent sujet d'observation.
8. **Graphe** : le bouton « Graphe » (+ « après raisonnement ») rend le
   graphe des triples ; un nœud n'est orange (« inféré ») que s'il a été
   **créé** par les règles — un nœud existant relié par un arc inféré
   reste de sa couleur d'origine (l'arc, lui, est orange) : c'est la
   distinction pédagogique à faire verbaliser.

## Barème suggéré (sur 20)

| Épreuve | Points |
|---|---|
| Exercice 1 — parcours complet (parse, raisonnement, diff requête, entraînement, preuve, altération rejetée) | 6 |
| Exercice 2 — raisonnement + requête avant/après interprétée | 4 |
| Exercice 2 — questions 1–3 (modifications de la KB + résultats justifiés) | 5 |
| Exercice 2 — question 4 (preuve lue et commentée : chaîne de règles, bindings, calcul) | 3 |
| Questions 5–6 + limites du modèle (argumentation : suffisant pas nécessaire, agrégation, contamination) | 2 |

Critères de réussite minimaux : l'étudiant sait (a) distinguer données
brutes et faits inférés, (b) lire une preuve (étapes, bindings) et
comprendre pourquoi une altération la rejette.

## Corrigés

- **Famille** : dans l'énoncé (`famille/enonce.md`, « Résultats
  attendus ») ;
- **Recettes** : dans `recettes/enonce.md` — tableaux des
  contre-indications par recette et des patients (résultats
  reproductibles : `cwm cwm_lab/exercises/recettes/*.n3 --think`,
  ou l'outil
  avec « Raisonner ») ; les corrigés des exercices 2–3 (rénale, IIH,
  hypercholestérolémie, totaux) sont dans `recettes/corriges/` — à
  charger **avec** la base, jamais à la place.
