# exercises/ — lab exercises

*English version — the French original is [`README.md`](README.md).*

An **exercise** is a subfolder of this directory. The tool discovers
it automatically (the header **Exercise** menu) and loads it into
the editors via `GET /api/exercise?name=<folder>`.

## Exercise folder convention

| File | Role |
|---|---|
| `enonce.md` | **required** — the statement in French (shown at the top of the page). The first `# …` heading is the menu label |
| `enonce.en.md` | **optional** — the statement in English, served when the application is in English (fallback: `enonce.md`) |
| `*.n3` | the data — `regles.n3` goes into the “rules” editor, **the other files are concatenated** (alphabetical order) into the “data” editor |
| `context.json` | **optional** — preloads: `{"query": "…", "conclusion": "…", "base_uri": "…"}` |

On load, the documents are **validated by parse**: a broken
exercise does not load (error message per document).

## Bilingual labels (`rdfs:label`)

The exercise ontologies carry **bilingual** `rdfs:label`s (`@fr` /
`@en`) on classes, properties and individuals. The tool shows the
label **in the application's language** (FR/EN switch top right),
with two fallbacks: the unlabeled label, then the first label
present. Resolution happens **in the backend**:

- new query rows, the new facts of “Reason”, and the graph's
  nodes/edges receive the chosen label — the IRIs never change;
- exercise queries therefore select **resources** (`?pat`, `?rec`)
  and not `rdfs:label` — a variable on `rdfs:label` would produce
  **one row per label** (duplicates);
- proper names identical in both languages (Alice, Bob…) carry an
  **unlabeled** label.

## Available exercises

| Folder | Suggested duration | Content |
|---|---|---|
| [`famille/`](famille/enonce.md) | ~30 min | warm-up: a small family graph (5 fact triples + the bilingual ontology) + the grandparent rule — walks through every function of the tool (parse, reasoning, query diff, entailment, proof, tampering) |
| [`recettes/`](recettes/enonce.md) | ~60–90 min | main exercise: food contraindications computed by N3 rules (absolute allergens + threshold nutrients, with `math:` calculations) over 9 recipes and 5 patients; 6 exercises, model answers (`corriges/`) + discussion of the model's limits |

**Teacher's guide** (2 h run-of-show, watchpoints, grading):
[`GUIDE_ENSEIGNANT.md`](GUIDE_ENSEIGNANT.md) (English:
[`GUIDE_ENSEIGNANT.en.md`](GUIDE_ENSEIGNANT.en.md)).

## Checking an exercise without the tool

```sh
# from the repository root: closure of an exercise
cwm <the exercise's .n3 files> --think
```

## Adding a new exercise

1. create the folder with `enonce.md` + the `.n3` files (+
   `context.json` if needed);
2. check that `cwm *.n3 --think` converges (no unbounded rule);
3. reload the tool's page: the new exercise appears in the menu
   (no registration needed);
4. add a row in the “Available exercises” table above.
