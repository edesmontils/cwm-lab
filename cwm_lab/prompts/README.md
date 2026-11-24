# Prompts IA (génération de données N3)

*Version française — l'anglais est dans [`README.en.md`](README.en.md).*

Les textes du prompt du bouton « Remplir la base (IA) » sont ici,
dans des fichiers **Markdown** (`.md`) **pour pouvoir les affiner à
la main** sans toucher au code Python — le Markdown est lisible pour
qui retouche, et compris par le modèle.

**Chaque génération re-lit les fichiers** (pas de redémarrage du
serveur) ; ils sont aussi copiés dans le paquet PyPI.
Un fichier introuvable (ou renommé) fait basculer le prompt sur les
**textes d'origine en dur** dans `cwm_lab/ia.py` — une retouche
ratée ne casse jamais la génération.

## Fichiers et placeholders

Syntaxe des placeholders : `${...}` (style `string.Template`).
Une ligne qui ne contient qu'un placeholder **vide** est retirée
du prompt final (les blocs conditionnels).

| Fichier | Rôle | Placeholders |
| --- | --- | --- |
| `system.md` | message `system` (rôle du modèle, anti-injection) | `${note_language}` — « Tu réponds en français. » / « You respond in English. » (langue de l'app, pour la note seule) |
| `user.md` | squelette du message `user` (liste numérotée des contraintes 1–5) | `${n_facts}`, `${n_entities}` — taille demandée ; `${max_facts}`, `${max_entities}` — limites strictes (×2) ; + les blocs ci-dessous |
| `rules_constraint.md` | contrainte 6 — préfixes/propriétés exactes des règles | — (bloquée : présente seulement si l'exercice chargé a des règles) |
| `json_fr.md` / `json_en.md` | contrainte 7 — réponse JSON unique (`n3` + `note`) | — (un seul des deux, selon la langue de l'app) |
| `generic_domain.md` | domaine par défaut (réseau familial) quand aucun exercice n'est chargé | `${base_uri}` — URI de base du document |
| `feedback.md` | bloc de régénération : les raisons de rejet des tentatives précédentes | `${reasons}` — une raison par bloc, `- contrôle : détail` |

Blocs conditionnels dans `user.md` :

- `${rules_constraint}` — contenu de `rules_constraint.md`, seulement
  si l'exercice chargé a des règles (poursuit la liste numérotée) ;
- `${json_constraint}` — contenu de `json_fr.md` ou `json_en.md` ;
- `${domaine_block}` — `<domaine>…énoncé…</domaine>` (tronqué à 8 000
  caractères, bornes codées dans `ia.py`) ;
- `${regles_block}` — `<regles>…règles…</regles>` (tronqué à 6 000
  caractères) ;
- `${generic_domain}` — contenu de `generic_domain.md`, seulement si
  ni énoncé ni règles ;
- `${feedback_block}` — contenu de `feedback.md`, seulement lors des
  tentatives 2+ (régénération).

Les blocs `<domaine>`/`<regles>`/`<rejet_precedent>` sont injectés
par le code (`cwm_lab/ia.py`, `build_messages`) ; les textes des
contenus ne sont PAS dans ces fichiers.

## Comment le domaine est défini (et le cibler dans sa retouche)

Le « domaine » du prompt n'est **pas un champ structuré** : c'est
l'**énoncé Markdown de l'exercice chargé** + **ses règles** tels
qu'ils sont dans l'interface. Trois sources, par ordre de priorité :

1. **L'exercice chargé** (dossier `cwm_lab/exercises/<nom>/`) :
   - `enonce.md` (+ `enonce.en.md`) — le texte qui *décrit le
     domaine* : vocabulaire (classes/propriétés), fichiers,
     contraintes, contexte pédagogique ; il alimente le bloc
     `<domaine>`. C'est le principal levier de réalisme : affiner
     l'énoncé affine le domaine généré, sans toucher à ces prompts.
   - `regles.n3` — le **vocabulaire exact** (préfixes, propriétés) ;
     il alimente le bloc `<regles>` et active la contrainte 6
     (`rules_constraint.md`) : les nouvelles données doivent
     s'appliquer à ces règles.
2. **L'éditeur « règles » courant** : ce qui est envoyé est le
   contenu *courant* de l'éditeur (pas le fichier de l'exercice) —
   si l'étudiant a modifié ses règles, les données générées suivent
   *ses* règles. Les **données** de l'exercice (`donnees.n3`) ne sont
   **jamais** envoyées : le modèle génère des données nouvelles, pas
   une copie de l'exemple.
3. **Aucun exercice chargé** (ni énoncé ni règles) → le repli
   `generic_domain.md` (réseau familial générique, avec la base URI
   du document).

Détails d'assemblage codés dans `build_messages` (ia.py) :

- `<domaine>` : l'énoncé tronqué à **8 000** caractères
  (`_MAX_ENONCE`) ; `<regles>` : les règles tronquées à **6 000**
  (`_MAX_REGLES`) ;
- **anti-injection** : le message `system.md` précise que le
  contenu des blocs est de la **DONNÉE contextuelle** — l'énoncé
  peut contenir du Markdown avec des instructions destinées à
  l'étudiant, le modèle ne doit pas s'y conformer.

| Pour cibler… | On retouche |
| --- | --- |
| le **domaine** (thème, réalisme, valeurs plausibles) | l'`enonce.md` de l'exercice — ou `user.md` / `generic_domain.md` pour le domaine générique |
| le **vocabulaire** (préfixes/propriétés utilisées) | les règles (exercice ou éditeur) — la contrainte 6 verrouille déjà l'exactitude ; `rules_constraint.md` si besoin de nuancer |
| la **taille / le format** | `user.md` (contraintes 5 et 7) — les bornes de troncature restent codées dans ia.py |
| la **langue de la note** | `${note_language}` + `json_fr.md` / `json_en.md` |

## Règles de retouche

- Restez en **Markdown** simple (titres `##`, liste numérotée,
  gras `**…**`, code `` `…` ``) — évitez les tableaux, images,
  liens : le modèle lit le texte brut.
- Gardez les numéros de contraintes (1–7) et les mots-clés que les
  contrôles a posteriori et les tests s'appuient sur
  (« DONNÉES SEULES », « log:implies », « JSON », « familial »,
  « written in English », « You respond in English. », « Tu réponds en
  français. ») — ou mettez à jour `tests/test_ia.py` avec.
- Gardez chaque placeholder `${...}` sur **sa propre ligne** : une
  ligne ne contenant qu'un placeholder vide est retirée du prompt
  (si vous collez un placeholder au milieu d'une ligne, la ligne
  reste, avec le placeholder vide visible).
- La langue du prompt reste **française** (calibrée sur les énoncés
  du TP) ; seule la langue de la *note* suit l'app
  (`${note_language}` + le choix `json_fr` / `json_en`).
- Après une retouche, vérifiez : le bouton IA génère, la réponse se
  parse, les contrôles passent, `make test` (les tests comparent des
  morceaux de prompt).
