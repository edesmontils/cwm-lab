# Exercise 1 — Family (warm-up, ~30 min)

A small family graph and a grandparent rule. The goal: run through
**every** feature of the tool, in miniature, before the « recipes »
exercise.

## Files

| File | Content |
|---|---|
| `donnees.n3` | 3 people, 2 `:parentOf` links + the ontology (class, 2 properties) |
| `regles.n3` | the grandparent rule (`log:implies`) |

> **Labels**: the ontology carries bilingual `rdfs:label`s
> (`@fr` / `@en`). The tool displays the label of **its own language**
> (toggle at the top right): fallback is the untagged label, then the
> first label present. The IRIs themselves never change.

## Walkthrough

1. **Parse**: load the exercise, parsing happens automatically on
   load. Check the stats (17 statements, 5 fact triples, 1 rule).
   Break a line on purpose (a missing period): watch the error in the
   **gutter** (line/column) and in the panel. Fix it.
2. **Infer**: « Infer » → how many **new facts**? (one — displayed
   with its labels: *Alice is grandparent of Carl* — the rule
   produces nothing else.) Switch to « 1 pass » mode: does the result
   change here? (No — one pass is enough. The difference only shows
   up with multi-level rules, cf. exercise 2.)
3. **Query**: the preloaded query selects the grandparents. Run it
   **without** reasoning: how many rows? (0 — the fact is not in the
   raw data.) Check « reason before querying »: 1 row, **highlighted**
   (before/after diff). The row shows the labels chosen in the tool's
   language — switch language to check.
4. **Entail?**: the preloaded conclusion is
   `:alice :grandparentOf :carl .` — the button answers **yes**.
   Change it to `:carl :grandparentOf :alice .`: **no**.
   What about `:alice :parentOf :carl .`? (No — direct parenthood is
   not derived; only grandparentage is.)
5. **Why?**: generate the proof. Observe its structure: `:Parsing`
   steps (the sources, embedded as `data:` URIs), `:Inference` steps
   (the rule applied with its **bindings**), and the proven formula.
   « Check the proof » → **valid**, with the derivation steps
   numbered.
6. **Tamper**: in the proof, replace `grandparentOf` with
   `siblingOf` (outside the long `data:` sources) then « Check the
   proof » → **invalid**, with the reason. This is the point of the
   practical: a proof is a *derivation* that can be replayed, not a
   certificate.

## Questions

- Q1. Why is `@forAll :x , :y , :z .` needed? What would happen
  without it (hint: how many new facts would « Infer » find, and
  which ones)?
- Q2. Does the rule produce `:alice :grandparentOf :alice .`? (Look
  for the fact in the closure.) Can you write a rule that would
  produce an infinite loop? (Hint: « 1 pass » vs « convergence » +
  the timeout.)

## Expected results

- Closure: 17 data statements + 1 new fact = 18 statements, 0
  inconsistency;
- Query: 0 raw row, 1 row after reasoning;
- Entail: yes for `:alice :grandparentOf :carl`, no for the other
  two;
- Proof: valid, then invalid after tampering.
