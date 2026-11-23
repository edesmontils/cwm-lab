# Exercise — Recipes, composition and dietary contraindications

An N3 knowledge base of **recipes** whose contraindications are
**computed by rules** from the **composition of the ingredients** and
the **medical profile of the patient** (allergies, diseases).

## Files

| File             | Namespace | Content                                                    |
|------------------|-----------|------------------------------------------------------------|
| `ingredients.n3` | `ingr:`   | 28 ingredients: allergens (qualitative) + 9 composition axes /100 g |
| `recettes.n3`    | `rec:`    | 9 recipes: ingredients + quantities in g / portion         |
| `medical.n3`     | `med:`    | 11 conditions (5 absolute, 6 threshold), 5 patients        |
| `regles.n3`      | —         | 14 N3 rules (forward chaining)                             |
| `corriges/`      | —         | Solutions to the exercises (to load **with** the base)     |

> **Bilingual labels**: the ontologies carry `rdfs:label`s
> (`@fr` / `@en`). The tool displays the label of **its own language**
> (toggle at the top right): fallback is the untagged label, then the
> first label present. The preloaded query therefore selects
> **resources** (`?pat`, `?rec`, `?cond`) — the backend displays them
> under the chosen label; a variable over `rdfs:label` would produce
> **one row per label** (2 per recipe here), which the query avoids.
> The IRIs never change.

The three namespaces are **independent**: the semantics of the
recipes (`rec:`), the ingredients (`ingr:`) and the medical (`med:`)
are only linked at the **edges** (`rec:contient`, `med:provoque`,
`med:contreIndication`), not at the IRI roots.

## Model

**Data**

- An ingredient: `ingr:contientAllergene <component>` (qualitative)
  and 9 composition axes **per 100 g**: `contientSodium`,
  `contientPurines`, `contientPotassium`, `contientGrasSature`,
  `contientSucre`, `contientFructane`, `contientCholestrol`,
  `contientHistamine`, `contientAlcool`.
  - **in use in the rules**: sodium, purines, sugar, saturated fat,
    histamine, alcohol;
  - **reserved for the exercises** (the data is already there):
    potassium (renal), fructan (IBS), cholesterol (hypercholesterolemia).
- A recipe: `rec:contient [ rec:ingredient <i> ; rec:quantite <g> ]`.
- A condition: `a med:Allergie` (**absolute** rule) or
  `a med:Maladie` (**threshold** rule + `med:seuil<X> <value>` **per
  portion**). The type is marked: `med:type med:absolu` / `med:seuil`.
  Peculiarity: `med:cirrhose` has a threshold of **0** — an absolute
  rule through the threshold door (the smallest drop of alcohol
  suffices).
- A patient: `med:presente <condition>` (1 or more).

**Rules** (see `regles.n3`)

1. **(A) Absolute** (qualitative, one single rule for all allergens):
   an ingredient that *bears* component X, where X *triggers*
   (`med:provoque`, in the data) condition M →
   `?r med:contreIndication M`. The quantity is irrelevant.
   Cross-contamination passes through the same door: `ingr:farineSF`
   bears the gluten component without having it « in the recipe »
   (shared line) — that is the case of the « gluten-free » crêpes.
2. **(B) Threshold** (quantitative, per nutrient, 6 nutrients × 2
   rules): contribution = `quantity g × content / 100 g`
   (`math:product` + `math:quotient`); if it exceeds the threshold
   declared in the data (`math:greaterThan`) → contraindication. The
   threshold is **a fact**: moving it requires no modified rule.
3. **(C) Patient aggregation**: a condition that hits a recipe
   forbids the recipe to every patient who has it
   (`rec:nePeutPasManger`).

## Running

```sh
# CWM from the command line (after pip install cwm-lab, which ships cwm)
cwm cwm_lab/exercises/recettes/*.n3 --think

# cwm-lab tool: the 3 data files in the facts editor,
# regles.n3 in the rules editor, then « Infer ».
# Before/after reasoning: no nePeutPasManger in the raw data,
# everything is inferred — the key pedagogical gap of the practical.
```

Patient × recipe × reason table (SPARQL):

```sparql
PREFIX rec: <http://example.org/recette#>
PREFIX med: <http://example.org/medical#>
SELECT ?pat ?rec ?cond WHERE {
  ?pat rec:nePeutPasManger ?rec .
  OPTIONAL { ?rec med:contreIndication ?cond . }
}
```

Here the `?cond` column is always filled (every
`nePeutPasManger` is derived from a `contreIndication`) — the
`OPTIONAL` keeps the table stable if a recipe were forbidden without
a named condition. **To try**: add a labelled column
(`?pat rdfs:label ?libPat`) and observe — with bilingual labels,
each row is **doubled** (one row per label): that is why the table
selects resources, not labels.

## Expected results (after reasoning)

Contraindications per recipe (the number in parentheses is the
contribution of the responsible ingredient, per portion):

| Recipe               | Inferred contraindications                                |
|----------------------|-----------------------------------------------------------|
| Tomato soup with basil | *(none — the « universal » recipe)*                       |
| Broccoli cheese gratin | milk · **hypertension** (salt 3 g → 1163 mg) · **heart disease** (cream 18 g) |
| Roast salmon with lentils | fish · **gout** (salmon 500, lentils 270 mg) · **histamine** (salmon 600 mg) |
| Tiramisu             | milk, egg, gluten · **diabetes** (sugar 50 g) · **heart disease** (mascarpone 36 g) |
| Satay soup           | peanut, fish (sauce) · **gout** (chicken 195 mg) · **heart disease** (coconut 34 g) |
| Peanut butter crêpes | gluten, egg, milk, peanut · **diabetes** (sugar 40 g) · **heart disease** (butter 15.3 g) |
| Niçoise salad        | egg, fish (tuna) · **gout** (tuna 288 mg) · **hypertension** (olives 1044 mg) · **histamine** (tuna 480 mg) |
| Chicken in white wine  | milk (cream, butter) · **gout** (chicken 195 mg) · **heart disease** (cream 18 g) · **histamine** (wine 120 mg) · **cirrhosis** (alcohol 18 g) |
| 'Gluten-free' crêpes | **trace gluten** (cross-contamination), egg, milk · **diabetes** (sugar 40 g) · **heart disease** (butter 15.3 g) |

Per patient:

| Patient (conditions)                    | Can NOT eat                                              | Can eat                 |
|-----------------------------------------|----------------------------------------------------------|-------------------------|
| Alice (peanut, gout)                    | crêpes · satay · salmon · Niçoise · chicken in wine      | soup · gratin · tiramisu · SF crêpes |
| Bob (coeliac, hypertension)             | crêpes · tiramisu · SF crêpes · gratin · Niçoise         | soup · salmon · satay · chicken in wine |
| Carole (diabetes, milk)                 | tiramisu · crêpes · gratin · SF crêpes · chicken in wine | soup · salmon · satay · Niçoise |
| David (heart disease, histamine)        | **everything, except the tomato soup**                    | soup                    |
| Eve (cirrhosis)                         | chicken in white wine only                                | the other 8             |

## Exercises

1. **Move a threshold**: `med:seuilPurines` from `150` to `300`.
   Who wins which dish? (The tuna of the Niçoise drops to 288 mg:
   Alice wins it back — David does not, the tuna at 480 mg of
   histamine still exceeds his threshold; the salmon, at 500 mg of
   purines, stays forbidden for both.)
2. **Add a disease** — the « 1 fact + 2 rules » pattern:
   renal insufficiency (potassium, threshold 600), IBS (fructan,
   threshold 2), hypercholesterolemia (cholesterol, threshold 200).
   **Solutions**: `corriges/exo-renal.n3`, `corriges/exo-iib.n3`,
   `corriges/exo-cholesterol.n3` (load with the base, check).
3. **Add a patient**: Franck, **hypertension only**.
   Can he eat the crêpes? (The base's diet says yes — no single
   ingredient exceeds 1000 mg, max = salt 775 mg — while the total
   is 1039 mg. Load `corriges/exo-totaux.n3`: the crêpes and the SF
   crêpes become contraindicated.)
4. **Proofs**: `--why=u` (or the « proofs » tab of the lab) on a
   contraindication — absolute rule → aggregation chain, or
   contribution computation → threshold → aggregation.
5. **Cross-contamination**: why are the « gluten-free » crêpes
   forbidden to Bob? And is that « correct »? (« may contain » ≠
   « contains »: in practice one distinguishes certified trace from
   possible contamination — what would need to be modelled?)
6. **(Advanced) The exact total by SPARQL**: the contributions are
   in the closure — produce the total sodium per recipe by query
   (`SUM`), reinject it (patch) and compare to the threshold.
   CWM is « the sed/awk of RDF »: chaining the tools is idiomatic.

## Limits of the model (to be discussed)

The threshold rules test the contribution of **each ingredient
alone**: a **sufficient but not necessary** condition (no
aggregation of the recipe's contributions). Consequences in the
base:

- Franck (hypertension only) could eat the crêpes (total
  1039 mg > 1000) — **error**;
- the total histamine of the satay (106 mg) exceeds the threshold
  without any single ingredient doing so (max = fish sauce 75 mg);
- the Niçoise (IBS, fructan 3.32) stays under the threshold per
  ingredient.

Paradox: in **this** base, no patient menu is skewed by the
simplification (the false negatives concern dishes already lost for
other reasons) — the counter-example becomes visible with Franck.

Why is exact aggregation hard **in pure N3**?
- no **list built from the facts** (one cannot « collect » the
  recipe's contributions);
- no **negation** (a « budget » decremented by rule, like
  `threshold - Σ contributions`, diverges: the same contribution is
  subtracted forever — one cannot mark « already counted »);
- no **iteration** over a set.

Hence the workarounds, from the most pragmatic to the most
« pipeline »:

1. **totals declared in the data** (nutrition label) + comparison
   rule — that is the choice of real-world bases
   (`corriges/exo-totaux.n3`);
2. **SPARQL `SUM` + patch**: the query computes, the reasoner
   consumes (exercise 6);
3. leaving N3 for the aggregation (computation service, SPARQL
   property path + full-engine aggregation).

The model also ignores: **daily** thresholds (here per portion),
**interactions** between components, the **uncertainty** of the
values (« ≈ 500 mg »), and the **individual reaction threshold** to
allergens (some patients react to a trace of peanut, others tolerate
incidental contamination).

## To develop

This development adds to the initial version (7 recipes, 3 threshold
diseases, 3 patients): 2 recipes (chicken in white wine,
« gluten-free » crêpes), 2 ingredients (white wine, « gluten-free »
flour), 5 composition axes (saturated fat, cholesterol, histamine,
alcohol, fructan), 3 threshold conditions (heart disease, histamine
intolerance, cirrhosis) and 2 patients (David, Eve). Still to
explore:

- the **incidental carrier** as a *quality* of the component
  (`contientAllergene [ :composant ingr:gluten ; :niveau :trace ]`)
  with traceability threshold rules;
- **per-day** thresholds and the accumulation of portions;
- the **value of uncertainty** on the compositions
  (`[ :valeur 500 ; :marge 50 ]`) and rules on bounds;
- new conditions (diabetes: glycemic index; colopathy: sorbitol;
  renal insufficiency: phosphorus…).

Each new axis = 1 property on the ingredients + 2 rules +
1 disease: the base is built for that — and that is the central
pedagogical point: **the knowledge is in the data, the
reasoning is in the rules, the two complement each other without
mixing.**
