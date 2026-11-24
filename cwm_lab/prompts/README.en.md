# AI prompts (N3 data generation)

*English version — the French original is [`README.md`](README.md).*

The prompt texts of the “Fill the KB (AI)” button live here, in
**Markdown** files (`.md`), **so they can be refined by hand**
without touching the Python code — Markdown is readable for whoever
edits it, and understood by the model.

**Every generation re-reads the files** (no server restart needed);
they are also shipped in the PyPI package. A missing (or renamed)
file makes the prompt fall back to the **hard-coded original texts**
in `cwm_lab/ia.py` — a bad edit never breaks generation.

## Files and placeholders

Placeholder syntax: `${...}` (`string.Template` style).
A line that contains **only** an **empty** placeholder is removed
from the final prompt (the conditional blocks).

| File | Role | Placeholders |
| --- | --- | --- |
| `system.md` | the `system` message (model role, anti-injection) | `${note_language}` — “Tu réponds en français.” / “You respond in English.” (app language, for the note only) |
| `user.md` | skeleton of the `user` message (numbered list of constraints 1–5) | `${n_facts}`, `${n_entities}` — requested size; `${max_facts}`, `${max_entities}` — hard limits (×2); + the blocks below |
| `rules_constraint.md` | constraint 6 — exact prefixes/properties of the rules | — (gated: present only if the loaded exercise has rules) |
| `json_fr.md` / `json_en.md` | constraint 7 — single JSON answer (`n3` + `note`) | — (one of the two, according to the app language) |
| `generic_domain.md` | default domain (family network) when no exercise is loaded | `${base_uri}` — the document's base URI |
| `feedback.md` | regeneration block: rejection reasons of the previous attempts | `${reasons}` — one reason per block, `- control: detail` |

Conditional blocks in `user.md`:

- `${rules_constraint}` — content of `rules_constraint.md`, only if
  the loaded exercise has rules (continues the numbered list);
- `${json_constraint}` — content of `json_fr.md` or `json_en.md`;
- `${domaine_block}` — `<domaine>…statement…</domaine>` (truncated to
  8,000 characters, bounds coded in `ia.py`);
- `${regles_block}` — `<regles>…rules…</regles>` (truncated to 6,000
  characters);
- `${generic_domain}` — content of `generic_domain.md`, only if there
  is neither a statement nor rules;
- `${feedback_block}` — content of `feedback.md`, only on attempts 2+
  (regeneration).

The `<domaine>`/`<regles>`/`<rejet_precedent>` blocks are injected
by the code (`cwm_lab/ia.py`, `build_messages`); the texts of the
contents are **not** in these files.

## How the domain is defined (and how to target it in an edit)

The prompt “domain” is **not a structured field**: it is the
loaded exercise's **Markdown statement** + **its rules**, as they
are in the interface. Three sources, by priority:

1. **The loaded exercise** (folder `cwm_lab/exercises/<name>/`):
   - `enonce.md` (+ `enonce.en.md`) — the text that *describes the
     domain*: vocabulary (classes/properties), files, constraints,
     teaching context; it feeds the `<domaine>` block. It is the
     main lever of realism: refining the statement refines the
     generated domain, without touching these prompts.
   - `regles.n3` — the **exact vocabulary** (prefixes, properties);
     it feeds the `<regles>` block and activates constraint 6
     (`rules_constraint.md`): the new data must apply to these
     rules.
2. **The current “rules” editor**: what is sent is the editor's
   *current* content (not the exercise file) — if the student has
   modified their rules, the generated data follow *their* rules.
   The exercise **data** (`donnees.n3`) is **never** sent: the model
   generates new data, not a copy of the example.
3. **No exercise loaded** (neither statement nor rules) → the
   `generic_domain.md` fallback (generic family network, with the
   document's base URI).

Assembly details coded in `build_messages` (ia.py):

- `<domaine>`: the statement truncated to **8,000** characters
  (`_MAX_ENONCE`); `<regles>`: the rules truncated to **6,000**
  (`_MAX_REGLES`);
- **anti-injection**: the `system.md` message specifies that the
  blocks' content is **contextual DATA** — the statement may
  contain Markdown with instructions intended for the student; the
  model must not follow them.

| To target… | Edit |
| --- | --- |
| the **domain** (theme, realism, plausible values) | the exercise's `enonce.md` — or `user.md` / `generic_domain.md` for the generic domain |
| the **vocabulary** (prefixes/properties used) | the rules (exercise or editor) — constraint 6 already locks exactness; `rules_constraint.md` if you need to nuance it |
| the **size / format** | `user.md` (constraints 5 and 7) — the truncation bounds stay coded in ia.py |
| the **note language** | `${note_language}` + `json_fr.md` / `json_en.md` |

## Editing rules

- Keep **simple Markdown** (`##` headings, numbered list, `**bold**`,
  `` `code` ``) — avoid tables, images, links: the model reads plain
  text.
- Keep the constraint numbers (1–7) and the keywords the a posteriori
  controls and the tests rely on (“DONNÉES SEULES”, “log:implies”,
  “JSON”, “familial”, “written in English”, “You respond in
  English.”, “Tu réponds en français.”) — or update
  `tests/test_ia.py` accordingly.
- Keep each placeholder `${...}` on **its own line**: a line
  containing only an empty placeholder is removed from the prompt
  (if you paste a placeholder in the middle of a line, the line
  stays, with the empty placeholder visible).
- The prompt language stays **French** (calibrated on the lab's
  exercise statements); only the *note* language follows the app
  (`${note_language}` + the `json_fr` / `json_en` choice).
- After an edit, check: the AI button generates, the answer parses,
  the controls pass, `make test` (the tests compare prompt
  snippets).
