# Prompts IA (génération de données N3)

Les textes du prompt du bouton « Remplir la base (IA) » sont ici,
dans des fichiers `.txt` **pour pouvoir les affiner à la main**
sans toucher au code Python.

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
| `system.txt` | message `system` (rôle du modèle, anti-injection) | `${note_language}` — « Tu réponds en français. » / « You respond in English. » (langue de l'app, pour la note seule) |
| `user.txt` | squelette du message `user` (contraintes 1–5) | `${n_facts}`, `${n_entities}` — taille demandée ; `${max_facts}`, `${max_entities}` — limites strictes (×2) ; + les blocs ci-dessous |
| `rules_constraint.txt` | contrainte 6 — préfixes/propriétés exactes des règles | — (bloquée : présente seulement si l'exercice chargé a des règles) |
| `json_fr.txt` / `json_en.txt` | contrainte 7 — réponse JSON unique (`n3` + `note`) | — (un seul des deux, selon la langue de l'app) |
| `generic_domain.txt` | domaine par défaut (réseau familial) quand aucun exercice n'est chargé | `${base_uri}` — URI de base du document |
| `feedback.txt` | bloc de régénération : les raisons de rejet des tentatives précédentes | `${reasons}` — une raison par ligne, `- contrôle : détail` |

Blocs conditionnels dans `user.txt` :

- `${rules_constraint}` — contenu de `rules_constraint.txt`, seulement
  si l'exercice chargé a des règles ;
- `${json_constraint}` — contenu de `json_fr.txt` ou `json_en.txt` ;
- `${domaine_block}` — `<domaine>…énoncé…</domaine>` (tronqué à 8 000
  caractères, bornes codées dans `ia.py`) ;
- `${regles_block}` — `<regles>…règles…</regles>` (tronqué à 6 000
  caractères) ;
- `${generic_domain}` — contenu de `generic_domain.txt`, seulement si
  ni énoncé ni règles ;
- `${feedback_block}` — contenu de `feedback.txt`, seulement lors des
  tentatives 2+ (régénération).

Les blocs `<domaine>`/`<regles>`/`<rejet_precedent>` sont injectés
par le code (`cwm_lab/ia.py`, `build_messages`) ; les textes des
contenus ne sont PAS dans ces fichiers.

## Règles de retouche

- Gardez les numéros de contraintes (1–7) et les mots-clés que les
  contrôles a posteriori et les tests s'appuient sur
  (« DONNÉES SEULES », « log:implies », « JSON », « familial »,
  « written in English », « You respond in English. », « Tu réponds en
  français. ») — ou mettez à jour `tests/test_ia.py` avec.
- Ne laissez pas de ligne blanche « perdue » entre deux contraintes :
  les lignes vides sont conservées, sauf celles qui ne contiennent
  qu'un placeholder vide.
- La langue du prompt reste **française** (calibrée sur les énoncés
  du TP) ; seule la langue de la *note* suit l'app
  (`${note_language}` + le choix `json_fr` / `json_en`).
- Après une retouche, vérifiez : le bouton IA génère, la réponse se
  parse, les contrôles passent, `make test` (les tests comparent des
  morceaux de prompt).
