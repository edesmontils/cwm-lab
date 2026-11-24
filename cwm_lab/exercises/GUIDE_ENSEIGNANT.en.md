# Teacher's guide — CWM Lab (semantic web lab, CWM 2.0)

*English version — the French original is [`GUIDE_ENSEIGNANT.md`](GUIDE_ENSEIGNANT.md).*

> Duration: **2 h** — Audience: Master MIAGE — Prerequisites: none
> (basic Python notions useful, not required). Material: the
> [cwm-lab](https://github.com/edesmontils/cwm-lab) tool (CWM 2.0
> as dependency), a browser, Python ≥ 3.9.

## Setup (before the lab)

```sh
pip install cwm-lab
cwm-lab                              # → http://127.0.0.1:8000
```

Check that the page loads and that the preloaded example (family)
parses (“OK” badge). The exercises are loaded from the **Exercise**
menu of the header: `famille` (warm-up) and `recettes` (main
exercise).

## Run-of-show (2 h)

| Time | Sequence | What the student does |
|---|---|---|
| 00:00–00:10 | Welcome | Start the tool, observe the preloaded example, automatic parse, break a line and observe the error in the gutter |
| 00:10–00:40 | **Exercise 1 — Family** | Load the `famille` exercise, follow the statement's walkthrough: Reason (1 new fact) → Query with/without reasoning (diff 0→1 row) → Entails? (yes/no) → Why? (proof) → **tamper with the proof** → Check (rejection) |
| 00:40–01:40 | **Exercise 2 — Recipes** | Load `recettes` (3 data files + rules). Reason, run the preloaded query **before/after** reasoning (the diff is the key pedagogical point: 0 raw rows, everything is inferred). Then questions 1–3 of the statement (move a threshold, add a disease — model answers in `corriges/` —, add patient Franck + `corriges/exo-totaux.n3`) |
| 01:40–01:55 | Proofs + contamination | Question 4: generate the proof of a contraindication, identify the chain (absolute rule or threshold rule **with the calculation** → patient aggregation), check, then tamper. Question 5: cross-contamination of the “gluten-free” crêpes (“may contain” ≠ “contains”) |
| 01:55–02:00 | Discussion | The statement's “model limits”: sufficient but not necessary condition, aggregation (Franck's total: 1039 mg > 1000 mg but no single ingredient exceeds it), daily thresholds. (Question 6 — SPARQL `SUM` + patch — as an extension) |

Variants:
- **Short (1 h 30)**: skip question 2 of recettes (add a disease)
  and the discussion;
- **Long (3 h)**: add the “To develop” section of the recettes
  statement (new nutritional axis = 1 property + 2 rules + 1
  disease) and/or the implementation of contribution aggregation.

## Watchpoints (classic pitfalls, observed in labs)

1. **Rule variables**: without `@forAll :x , :y , :z .`, a bare
   `:x` is a **constant** — the rule fires only literally
   (symptom: “0 new facts”). This is pitfall no. 1.
2. **`false` vs `log:false`**: the bare keyword `false` is a
   literal silently ignored; the CWM inconsistency is the constant
   `log:false` (the `log:false log:false log:false` triple in the
   closure).
3. **SPARQL ≠ N3**: `PREFIX : <…>` **without** final dot in the
   query; `@prefix : <…> .` in the data. Students mix the two
   syntaxes.
4. **Base URI**: relative terms (`:alice`) resolve against the
   base URI of the header — changing it mid-session changes term
   identity (and breaks the comparisons).
5. **Timeout**: a rule that produces forever (e.g. an existential
   in the conclusion) does not block the tool — the timeout
   returns a clean error. Showing it is a pedagogical goal
   (forward chaining not guaranteed on cyclic rules).
6. **Proofs**: the tampering must be done **outside the `data:`
   sources** (the long encoded lines) — otherwise the proof no
   longer parses (a “not parsable” rejection) instead of the
   “derivation not replayable” rejection. Both rejections are
   instructive: show them.
7. **“1 pass” vs “convergence” mode**: on `recettes`, the threshold
   rules have two levels (contribution → contraindication →
   patient): in “1 pass”, the `nePeutPasManger` do **not** appear —
   an excellent observation subject.
8. **Graph**: the “Graph” button (+ “after reasoning”) renders the
   triple graph; a node is orange (“inferred”) only if it was
   **created** by the rules — an existing node linked by an
   inferred edge keeps its original color (the edge, itself, is
   orange): that is the pedagogical distinction to verbalize.

## Suggested grading (out of 20)

| Assessment | Points |
|---|---|
| Exercise 1 — full walkthrough (parse, reasoning, query diff, entailment, proof, rejected tampering) | 6 |
| Exercise 2 — reasoning + before/after query interpreted | 4 |
| Exercise 2 — questions 1–3 (KB modifications + justified results) | 5 |
| Exercise 2 — question 4 (proof read and commented: rule chain, bindings, calculation) | 3 |
| Questions 5–6 + model limits (argumentation: sufficient not necessary, aggregation, contamination) | 2 |

Minimal success criteria: the student knows (a) to distinguish raw
data from inferred facts, (b) to read a proof (steps, bindings) and
understand why a tampering rejects it.

## Model answers

- **Family**: in the statement (`famille/enonce.md`, “Expected
  results”);
- **Recipes**: in `recettes/enonce.md` — tables of the
  contraindications per recipe and per patient (reproducible
  results: `cwm cwm_lab/exercises/recettes/*.n3 --think`, or the
  tool with “Reason”); the model answers of exercises 2–3 (renal,
  IHD, hypercholesterolemia, totals) are in
  `recettes/corriges/` — to be loaded **with** the base, never
  instead of it.
