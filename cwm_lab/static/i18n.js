/* i18n.js — internationalisation de l'interface CWM Lab (FR par défaut).
 *
 * - Deux dictionnaires (fr / en) : ajouter une langue = une table ici
 *   + une option dans le sélecteur de l'entête.
 * - Chaînes statiques (index.html) : attribut data-i18n (textContent),
 *   data-i18n-ph (placeholder), data-i18n-title (infobulles),
 *   data-i18n-aria (aria-label). Le texte français du HTML reste le
 *   repli si la clé manque.
 * - Chaînes dynamiques (app.js) : t(key, …args), placeholders {1} {2}
 *   … — l'app re-rend ses résultats à chaque changement de langue
 *   (événement `cwm-tp:lang`, via onLangChange).
 * - Persistance : localStorage (`cwm-tp-lang`) ; `<html lang>` et le
 *   titre de page suivent la langue.
 *
 * Hors périmètre (du CONTENU, pas de l'interface) : les énoncés des
 * exercices, les messages du moteur de parse (anglais, CWM), la note
 * du modèle IA (le prompt est calibré en français).
 */

export const LANGS = ["fr", "en"];
const LANG_KEY = "cwm-tp-lang";

const MESSAGES = {
  fr: {
    // ── entête / barre d'outils ──────────────────────────────────────
    "page.title": "CWM Lab — CWM 2.0",
    "header.subPre": "— cohérence, validité, règles (",
    "header.subPost": ")",
    "header.docLinkText": "CWM 2.0",
    "header.docTitle": "Documentation CWM 2.0 (README français)",
    "header.docLink": "https://gitlab.univ-nantes.fr/desmontils-e/cwm/-/blob/main/README.md",
    "bar.baseUri": "Base URI",
    "bar.parse": "Parse",
    "bar.parseTitle": "Parse maintenant (⌘⏎ / Ctrl⏎)",
    "bar.exercise": "Exercice",
    "bar.exerciseNone": "— aucun —",
    "bar.exerciseTitle": "Charge l'exercice choisi dans les éditeurs (données, règles, requête, conclusion) et affiche son énoncé",
    "bar.load": "Charger",
    "bar.loadTitle": "Remplir les éditeurs avec l'exercice choisi (remplace le contenu actuel) et afficher son énoncé",
    "bar.export": "Export :",
    "bar.exportN3Title": "Exporter en N3 (règles comprises)",
    "bar.exportTurtleTitle": "Exporter en Turtle (RDF pur uniquement)",
    "bar.exportNtTitle": "Exporter en NTriples (RDF pur uniquement)",
    "bar.exportRdfTitle": "Exporter en RDF/XML",
    "bar.lang": "Langue",
    "bar.langTitle": "Langue de l'interface (persistance locale)",
    // ── énoncé / éditeurs ────────────────────────────────────────────
    "enonce.summary": "Énoncé",
    "ed.data": "Document — données (N3 / Turtle)",
    "ia.banner": "⚠ Données générées par IA — à vérifier avant raisonnement / interrogation.",
    "ia.bannerClose": "Masquer la bannière",
    "ed.rules": "Règles (N3)",
    "ed.query": "Requête (SPARQL)",
    // ── barre d'actions ──────────────────────────────────────────────
    "bar.reasoning": "Raisonnement",
    "bar.infer": "Raisonner",
    "bar.inferTitle": "Appliquer les règles aux données (clôture, nouveaux faits, incohérence)",
    "bar.mode": "mode :",
    "bar.modeThink": "convergence (think)",
    "bar.modeOnce": "1 passe (applyRules)",
    "bar.modeTitle": "convergence (think) = point fixe ; 1 passe (applyRules) = une seule application de chaque règle",
    "bar.rulesStored": "règles stockées",
    "bar.rulesStoredTitle": "copier les énoncés-règles dans la clôture (comme cwm --rules)",
    "bar.timeout": "timeout (s) :",
    "bar.timeoutTitle": "délai maximum de raisonnement ; 0 = sans limite",
    "bar.queryGroup": "Interroger",
    "bar.query": "Interroger",
    "bar.queryTitle": "Exécuter la requête SPARQL sur les données (et sur la clôture si « raisonner avant »)",
    "bar.reasonFirst": "raisonner avant d'interroger",
    "bar.reasonFirstTitle": "calculer d'abord la clôture, puis ré-exécuter la même requête : les lignes nouvelles sont surlignées",
    "bar.validate": "Valider",
    "bar.entail": "Entraîne ?",
    "bar.entailTitle": "La clôture (données + règles appliquées) contient-elle la conclusion de l'éditeur « Conclusion » ?",
    "bar.why": "Pourquoi ?",
    "bar.whyTitle": "Générer la preuve de la clôture dans l'onglet « Preuve » — altérez-la ensuite à la main",
    "bar.check": "Vérifier la preuve",
    "bar.checkTitle": "Vérifier la preuve de l'onglet « Preuve » : la dérivation est re-jouée — une preuve altérée est rejetée",
    "bar.generate": "Générer (IA)",
    "bar.generateBtn": "Remplir la base (IA)",
    "bar.generateBtnTitle": "Générer un jeu de données N3 réaliste (domaine de l'exercice chargé, sinon générique) et l'injecter dans l'éditeur « données » — contrôlé (parse, cohérence, plausibilité), à vérifier",
    "bar.facts": "faits ≈",
    "bar.factsTitle": "nombre approximatif de faits à générer",
    "bar.entities": "entités ≈",
    "bar.entitiesTitle": "nombre approximatif d'entités à générer",
    // ── graphe ───────────────────────────────────────────────────────
    "resizerTitle": "Glisser pour ajuster la largeur des colonnes",
    "resizerAria": "Ajuster la largeur des colonnes",
    "graph.title": "Graphe",
    "graph.afterReasoning": "après raisonnement",
    "graph.afterReasoningTitle": "calculer d'abord la clôture (données + règles), puis surligner ce qu'elle ajoute",
    "graph.hideLiterals": "attributs masqués",
    "graph.hideLiteralsTitle": "masquer les nœuds-littéraux : les attributs sont regroupés en pastille (compteur) sur le nœud — survolez la pastille pour les lire",
    "graph.legendResource": "ressource",
    "graph.legendLiteral": "littéral",
    "graph.legendBlank": "nœud vide",
    "graph.legendInferred": "inféré",
    // ── conclusion / preuve ──────────────────────────────────────────
    "proof.title": "Conclusion / Preuve (N3)",
    "tab.concl": "Conclusion",
    "tab.conclTitle": "La conclusion à tester : la KB (données + règles) l'entraîne-t-elle ?",
    "tab.proof": "Preuve",
    "tab.proofTitle": "La preuve (générée par « Pourquoi ? », altérable à la main) — « Vérifier la preuve » rejoue la dérivation",
    // ── résultats (onglets) ──────────────────────────────────────────
    "results.title": "Résultats",
    "tab.parse": "Parse",
    "tab.infer": "Raisonnement",
    "tab.query": "Requête",
    "tab.entail": "Entraînement",
    "tab.proofRes": "Preuve",
    "tab.export": "Export",
    "tab.ia": "Génération (IA)",
    "pane.parseHint": "Le parse est automatique pendant la saisie (⌘⏎ / Ctrl⏎ pour forcer).",
    "export.download": "⬇ Télécharger",
    "export.close": "Fermer",
    "pane.iaHint": "Bouton « Remplir la base (IA) » : génère un jeu de données N3 réaliste (domaine de l'exercice chargé, sinon générique), contrôlé a posteriori (parse, cohérence avec les règles, plausibilité), et l'injecte dans l'éditeur « données ».",
    // ── colophon ─────────────────────────────────────────────────────
    "colophon.copyright": "© 2026 Emmanuel Desmontils — Nantes Université",
    "colophon.version": "CWM Lab, version",
    // ── aide (popup des boutons et cases) ────────────────────────────
    "help.btn": "?",
    "help.btnTitle": "Aide : ce que fait chaque bouton et chaque case",
    "help.title": "Aide — boutons et cases",
    "help.close": "Fermer",
    "help.secHeader": "Barre d'entête",
    "help.baseUri": "Base URI — l'URI de base du document : les IRI courts (:alice) sont complétés avec elle.",
    "help.parse": "Parse — analyse le document « données » et les « règles » (N3/Turtle) ; automatique pendant la saisie, forcé par ce bouton (ou ⌘⏎ / Ctrl⏎). Les erreurs sont localisées ligne/colonne.",
    "help.exercise": "Exercice + Charger — remplit les éditeurs (données, règles, requête, conclusion) avec l'exercice choisi et affiche son énoncé.",
    "help.export": "Export (N3 / Turtle / NTriples / RDF) — écrit le document courant au format choisi dans l'onglet « Export », avec lien de téléchargement.",
    "help.lang": "Langue — change la langue de l'interface (FR/EN) ; le choix est mémorisé localement.",
    "help.secReasoning": "Raisonnement",
    "help.infer": "Raisonner — applique les règles aux données : la clôture (faits nouveaux) est calculée et affichée dans l'onglet « Raisonnement » ; une incohérence (⊥) est signalée.",
    "help.mode": "mode — convergence (think) : les règles s'appliquent jusqu'au point fixe ; 1 passe (applyRules) : chaque règle est appliquée une seule fois.",
    "help.timeout": "timeout (s) — délai maximum de raisonnement ; 0 = sans limite.",
    "help.rulesStored": "règles stockées — copie les énoncés-règles dans la clôture (comme cwm --rules) ; on peut alors les requêter.",
    "help.secQuery": "Interroger",
    "help.query": "Interroger — exécute la requête SPARQL de l'éditeur « Requête » sur la base de connaissances ; les lignes de résultat sont dans l'onglet « Requête ».",
    "help.reasonFirst": "raisonner avant d'interroger — calcule d'abord la clôture, puis ré-exécute la même requête : les lignes nouvelles (apportées par les règles) sont surlignées.",
    "help.secValidate": "Valider",
    "help.entail": "Entraîne ? — vérifie que la conclusion (éditeur « Conclusion ») est bien contenue dans la clôture (données + règles appliquées).",
    "help.why": "Pourquoi ? — génère la preuve de la conclusion dans l'onglet « Preuve » ; on peut ensuite l'altérer à la main.",
    "help.check": "Vérifier la preuve — rejoue la dérivation de la preuve : une preuve valide est acceptée, une preuve altérée est rejetée.",
    "help.secGenerate": "Générer (IA)",
    "help.ia": "Remplir la base (IA) — génère un jeu de données N3 réaliste (domaine de l'exercice chargé, sinon générique), contrôlé a posteriori (parse, cohérence, plausibilité), et l'injecte dans l'éditeur « données » — à vérifier avant usage.",
    "help.iaSize": "faits ≈ / entités ≈ — taille approximative du jeu de données à générer ; le quota de séance est affiché sous le bouton.",
    "help.secGraph": "Graphe",
    "help.graphReason": "après raisonnement — le graphe calcule d'abord la clôture, puis surligne en orange ce qu'elle ajoute (nœuds et arcs inférés).",
    "help.graphHide": "attributs masqués — masque les nœuds-littéraux : les attributs sont regroupés en pastille (compteur) sur le nœud ; survolez la pastille pour les lire.",
    "help.graphFocus": "clic sur un nœud — masque les nœuds qui ne le concernent pas (voisinage direct) ; un clic sur le vide réaffiche tout.",
    // ── libellés des éditeurs / documents ────────────────────────────
    "label.document": "document",
    "label.rules": "règles",
    "label.query": "requête",
    "label.conclusion": "conclusion",
    "label.proof": "preuve",
    "doc.data": "données",
    "doc.rules": "règles",
    "doc.query": "requête",
    "doc.conclusion": "conclusion",
    "doc.proof": "preuve",
    "doc.server": "serveur",
    // ── statut (barre) ───────────────────────────────────────────────
    "status.parsing": "parse en cours…",
    "status.syntaxError": "erreur de syntaxe",
    "status.networkError": "erreur réseau : {1}",
    "status.ok": "OK{1}",
    // ── parse ────────────────────────────────────────────────────────
    "parse.editorError": "Éditeur « {1} » : erreur de syntaxe.",
    "parse.errorLine": "ligne {1}, col. {2} — {3}",
    "parse.editorValid": "Éditeur « {1} » : valide.",
    "parse.editorValidQuery": "Éditeur « {1} » : requête valide.",
    "parse.statements": "énoncé(s)",
    "parse.rules": "règle(s)",
    "parse.blankNodes": "nœud(s) vide(s)",
    "parse.queryType": "type :",
    "parse.queryTypeUnknown": "inconnue",
    "parse.variables": "variables :",
    "parse.noVariables": "— (SELECT * ou ASK)",
    "export.empty": "(document vide)",
    // ── méta communs ─────────────────────────────────────────────────
    "meta.newFacts": "{1} fait(s) nouveau(x)",
    "meta.closure": "{1} énoncé(s) dans la clôture",
    "meta.storedRules": "{1} règle(s) stockée(s)",
    "meta.cache": "cache",
    // ── raisonnement ─────────────────────────────────────────────────
    "infer.timeoutTail": " — le raisonnement a été interrompu, la page reste utilisable.",
    "infer.inconsistent": "⚠ <b>Incohérent</b> : la clôture contient la constante <code>log:false</code> (une règle aboutit à une contradiction).",
    "infer.newFactsTitle": "Nouveaux faits (absents des données d'origine) :",
    "infer.noNewFacts": "Aucun nouveau fait : la clôture est identique aux données (les règles ne s'appliquent pas, ou ont déjà convergé).",
    "infer.busy": "Raisonnement en cours… (une règle non convergente est interrompue au timeout).",
    "btn.reasoning": "raisonnement…",
    // ── requête ──────────────────────────────────────────────────────
    "query.busy": "Requête en cours…",
    "query.busyReason": " (clôture d'abord — une règle non convergente est interrompue au timeout).</p>",
    "query.metaAsk": "ASK : {1}",
    "query.metaAskReasoned": "après raisonnement : {1}",
    "query.rowsRaw": "{1} ligne(s) sur les données brutes",
    "query.rowsReasoned": "{1} ligne(s) après raisonnement, dont {2} nouvelle(s)",
    "query.timeoutTail": " — la clôture a été interrompue ; seuls les résultats bruts sont affichés.",
    "query.askRaw": "ASK sur les données brutes : <b>{1}</b>",
    "query.askReasoned": "ASK après raisonnement : <b>{1}</b>",
    "query.askChanged": " <span class=\"muted\">(le raisonnement a changé la réponse)</span>",
    "query.resultsRaw": "Résultats (données brutes)",
    "query.rawData": "Données brutes",
    "query.afterReasoning": "Après raisonnement",
    "query.newRowsHl": "<span class=\"muted\">(lignes nouvelles surlignées)</span>",
    "query.noRows": "(0 ligne)",
    "query.rowNew": "ligne nouvelle : produite par le raisonnement",
    "ask.true": "vrai",
    "ask.false": "faux",
    "btn.querying": "requête…",
    // ── entraînement / preuve ────────────────────────────────────────
    "entail.timeoutTail": " — le raisonnement a été interrompu ; la conclusion n'a pas pu être testée.",
    "entail.yes": "✔ <b>Oui</b> : la clôture (données + règles appliquées) <b>entraîne</b> la conclusion.",
    "entail.no": "✘ <b>Non</b> : la clôture ne contient pas la conclusion — aucune dérivaison ne la produit.",
    "entail.inconsistent": "⚠ La clôture est <b>incohérente</b> (<code>log:false</code>) : par explosion, <i>toute</i> conclusion y est « entraînée » — le oui ci-dessus n'a pas de valeur.",
    "entail.busy": "Entraînement en cours… (clôture d'abord — une règle non convergente est interrompue au timeout).",
    "btn.testing": "test…",
    "prove.timeoutTail": " — la preuve n'a pas pu être générée.",
    "prove.generated": "✔ Preuve générée : la clôture (données + règles) est la formule prouvée. Elle est dans l'onglet <b>Preuve</b> — <b>altérez-la à la main</b> (un prédicat, une étape, une source…), puis cliquez sur « Vérifier la preuve ».",
    "prove.busy": "Génération de la preuve… (clôture d'abord — une règle non convergente est interrompue au timeout).",
    "btn.generating": "génération…",
    "check.stepsMeta": "{1} étape(s) de dérivation",
    "check.valid": "✔ <b>Preuve valide</b> : la dérivation est re-jouée sans erreur — la formule prouvée suit bien des sources, par les règles.",
    "check.invalid": "✘ <b>Preuve invalide</b> : la dérivation ne se re-joue pas. Raison : <code>{1}</code>",
    "check.invalidReason": "inconnue",
    "check.stepsIntro": "Étapes (déroulées avant l'échec — en cas d'altération, c'est là qu'on voit le point de rupture) :",
    "check.stepsSummary": "Étapes de dérivation ({1})",
    "check.busy": "Vérification en cours… (check rejoue la dérivation dans un processus dédié).",
    "btn.checking": "vérification…",
    "empty": "(vide)",
    // ── exercices ────────────────────────────────────────────────────
    "exercise.emptyEnonce": "(énoncé vide)",
    "exercise.loadError": "Erreur réseau lors du chargement : {1}",
    "exercise.cannotLoad": "Impossible de charger l'exercice : {1}",
    "exercise.unreadable": "exercice illisible",
    "exercise.opt": "{1} ({2} fichier(s) .n3)",
    // ── génération (IA) ──────────────────────────────────────────────
    "ia.bannerPrefix": "⚠ Données générées par IA",
    "ia.bannerSuffix": " — à vérifier avant raisonnement / interrogation.",
    "ia.quota": "quota du jour : {1} requête(s), {2} tokens",
    "ia.unconfigured": "IA non configurée",
    "ia.btnTitle": "Générer des données N3 réalistes (domaine de l'exercice chargé) et les injecter dans l'éditeur « données » — contrôlées, à vérifier",
    "ia.model": "modèle : {1}",
    "ia.attempt": "tentative {1}",
    "ia.tokens": "{1} tokens",
    "ia.elapsed": "{1} s",
    "ia.accepted": "✓ Génération acceptée (tentative {1}) — les données sont dans l'éditeur « données ».",
    "ia.warning": "(avertissement : {1})",
    "ia.parseFacts": "({1} faits)",
    "ia.inferredFacts": "({1} faits inférés)",
    "ia.plausibility": "({1} faits, {2} entités)",
    "ia.ctrlParse": "parse",
    "ia.ctrlCoherence": "cohérence",
    "ia.ctrlPlausibility": "plausibilité",
    "ia.acceptedNote": "Les données générées sont <strong>dans l'éditeur « données »</strong> — lisez-les, corrigez-les, supprimez-les. Elles ne sont pas vérifiées par un humain : contrôlez les valeurs (et les seuils) par rapport à l'énoncé avant de raisonner ou d'interroger.",
    "ia.busyBtn": "génération…",
    "ia.busy": "Génération en cours… (quelques secondes — la réponse est contrôlée : parse, cohérence avec les règles, plausibilité ; en cas d'échec, régénération bornée, 3 tentatives au maximum).",
    // ── graphe (dynamique) ───────────────────────────────────────────
    "graph.statements": "{1} énoncé(s)",
    "graph.nodes": "{1} nœud(s)",
    "graph.edges": "{1} arc(s)",
    "graph.truncated": " (tronqué)",
    "graph.truncatedMsg": "Graphe tronqué (trop d'énoncés pour rester lisible) : {1} affichés.",
    "graph.networkError": "Erreur réseau : {1}",
    "graph.unknownError": "erreur inconnue",
  },

  en: {
    // ── header / toolbar ─────────────────────────────────────────────
    "page.title": "CWM Lab — CWM 2.0",
    "header.subPre": "— consistency, validity, rules (",
    "header.subPost": ")",
    "header.docLinkText": "CWM 2.0",
    "header.docTitle": "CWM 2.0 documentation (English README)",
    "header.docLink": "https://gitlab.univ-nantes.fr/desmontils-e/cwm/-/blob/main/README.en.md",
    "bar.baseUri": "Base URI",
    "bar.parse": "Parse",
    "bar.parseTitle": "Parse now (⌘⏎ / Ctrl⏎)",
    "bar.exercise": "Exercise",
    "bar.exerciseNone": "— none —",
    "bar.exerciseTitle": "Loads the chosen exercise into the editors (data, rules, query, conclusion) and shows its statement",
    "bar.load": "Load",
    "bar.loadTitle": "Fills the editors with the chosen exercise (replaces the current content) and shows its statement",
    "bar.export": "Export:",
    "bar.exportN3Title": "Export as N3 (rules included)",
    "bar.exportTurtleTitle": "Export as Turtle (pure RDF only)",
    "bar.exportNtTitle": "Export as NTriples (pure RDF only)",
    "bar.exportRdfTitle": "Export as RDF/XML",
    "bar.lang": "Language",
    "bar.langTitle": "Interface language (stored locally)",
    // ── statement / editors ──────────────────────────────────────────
    "enonce.summary": "Statement",
    "ed.data": "Document — data (N3 / Turtle)",
    "ia.banner": "⚠ AI-generated data — check before reasoning / querying.",
    "ia.bannerClose": "Dismiss the banner",
    "ed.rules": "Rules (N3)",
    "ed.query": "Query (SPARQL)",
    // ── action bar ───────────────────────────────────────────────────
    "bar.reasoning": "Reasoning",
    "bar.infer": "Reason",
    "bar.inferTitle": "Apply the rules to the data (closure, new facts, inconsistency)",
    "bar.mode": "mode:",
    "bar.modeThink": "convergence (think)",
    "bar.modeOnce": "1 pass (applyRules)",
    "bar.modeTitle": "convergence (think) = fixpoint; 1 pass (applyRules) = each rule applied once",
    "bar.rulesStored": "rules stored",
    "bar.rulesStoredTitle": "copy the rule statements into the closure (like cwm --rules)",
    "bar.timeout": "timeout (s):",
    "bar.timeoutTitle": "maximum reasoning time; 0 = unlimited",
    "bar.queryGroup": "Query",
    "bar.query": "Query",
    "bar.queryTitle": "Run the SPARQL query on the data (and on the closure if 'reason before querying' is set)",
    "bar.reasonFirst": "reason before querying",
    "bar.reasonFirstTitle": "compute the closure first, then re-run the same query: new rows are highlighted",
    "bar.validate": "Validate",
    "bar.entail": "Entails?",
    "bar.entailTitle": "Does the closure (data + applied rules) contain the conclusion from the 'Conclusion' editor?",
    "bar.why": "Why?",
    "bar.whyTitle": "Generate the proof of the closure in the 'Proof' tab — then tamper with it by hand",
    "bar.check": "Check the proof",
    "bar.checkTitle": "Check the proof in the 'Proof' tab: the derivation is replayed — a tampered proof is rejected",
    "bar.generate": "Generate (AI)",
    "bar.generateBtn": "Fill the KB (AI)",
    "bar.generateBtnTitle": "Generate a realistic N3 dataset (domain of the loaded exercise, or generic) and inject it into the 'data' editor — checked (parse, coherence, plausibility), to be verified",
    "bar.facts": "facts ≈",
    "bar.factsTitle": "approximate number of facts to generate",
    "bar.entities": "entities ≈",
    "bar.entitiesTitle": "approximate number of entities to generate",
    // ── graph ────────────────────────────────────────────────────────
    "resizerTitle": "Drag to adjust the column widths",
    "resizerAria": "Adjust the column widths",
    "graph.title": "Graph",
    "graph.afterReasoning": "after reasoning",
    "graph.afterReasoningTitle": "compute the closure first (data + rules), then highlight what it adds",
    "graph.hideLiterals": "hidden attributes",
    "graph.hideLiteralsTitle": "hide the literal nodes: attributes are grouped into a badge (counter) on the node — hover the badge to read them",
    "graph.legendResource": "resource",
    "graph.legendLiteral": "literal",
    "graph.legendBlank": "blank node",
    "graph.legendInferred": "inferred",
    // ── conclusion / proof ───────────────────────────────────────────
    "proof.title": "Conclusion / Proof (N3)",
    "tab.concl": "Conclusion",
    "tab.conclTitle": "The conclusion to test: does the KB (data + rules) entail it?",
    "tab.proof": "Proof",
    "tab.proofTitle": "The proof (generated by 'Why?', tamperable by hand) — 'Check the proof' replays the derivation",
    // ── results (tabs) ───────────────────────────────────────────────
    "results.title": "Results",
    "tab.parse": "Parse",
    "tab.infer": "Reasoning",
    "tab.query": "Query",
    "tab.entail": "Entailment",
    "tab.proofRes": "Proof",
    "tab.export": "Export",
    "tab.ia": "Generation (AI)",
    "pane.parseHint": "Parsing is automatic while typing (⌘⏎ / Ctrl⏎ to force).",
    "export.download": "⬇ Download",
    "export.close": "Close",
    "pane.iaHint": "'Fill the KB (AI)' button: generates a realistic N3 dataset (domain of the loaded exercise, or generic), checked a posteriori (parse, coherence with the rules, plausibility), and injects it into the 'data' editor.",
    // ── colophon ─────────────────────────────────────────────────────
    "colophon.copyright": "© 2026 Emmanuel Desmontils — Nantes University",
    "colophon.version": "CWM Lab, version",
    // ── help (buttons & checkboxes popup) ────────────────────────────
    "help.btn": "?",
    "help.btnTitle": "Help: what each button and checkbox does",
    "help.title": "Help — buttons and checkboxes",
    "help.close": "Close",
    "help.secHeader": "Header bar",
    "help.baseUri": "Base URI — the document's base URI: short IRIs (:alice) are completed with it.",
    "help.parse": "Parse — parses the 'data' and 'rules' documents (N3/Turtle); automatic while typing, forced by this button (or ⌘⏎ / Ctrl⏎). Errors are located line/column.",
    "help.exercise": "Exercise + Load — fills the editors (data, rules, query, conclusion) with the chosen exercise and shows its statement.",
    "help.export": "Export (N3 / Turtle / NTriples / RDF) — writes the current document in the chosen format to the 'Export' tab, with a download link.",
    "help.lang": "Language — changes the interface language (FR/EN); the choice is remembered locally.",
    "help.secReasoning": "Reasoning",
    "help.infer": "Reason — applies the rules to the data: the closure (new facts) is computed and shown in the 'Reasoning' tab; a contradiction (⊥) is reported.",
    "help.mode": "mode — convergence (think): rules are applied to a fixed point; 1 pass (applyRules): each rule is applied once.",
    "help.timeout": "timeout (s) — maximum reasoning time; 0 = no limit.",
    "help.rulesStored": "stored rules — copies the rule statements into the closure (like cwm --rules); they can then be queried.",
    "help.secQuery": "Query",
    "help.query": "Query — runs the SPARQL query from the 'Query' editor over the knowledge base; result rows appear in the 'Query' tab.",
    "help.reasonFirst": "reason before query — computes the closure first, then re-runs the same query: new rows (brought by the rules) are highlighted.",
    "help.secValidate": "Validate",
    "help.entail": "Entails? — checks that the conclusion ('Conclusion' editor) is contained in the closure (data + applied rules).",
    "help.why": "Why? — generates the proof of the conclusion in the 'Proof' tab; you can then tamper with it by hand.",
    "help.check": "Check proof — replays the derivation: a valid proof is accepted, a tampered proof is rejected.",
    "help.secGenerate": "Generate (AI)",
    "help.ia": "Fill the KB (AI) — generates a realistic N3 dataset (domain of the loaded exercise, or generic), checked a posteriori (parse, coherence, plausibility), and injects it into the 'data' editor — to be verified before use.",
    "help.iaSize": "facts ≈ / entities ≈ — approximate size of the dataset to generate; the session quota is shown below the button.",
    "help.secGraph": "Graph",
    "help.graphReason": "after reasoning — the graph computes the closure first, then highlights in orange what it adds (inferred nodes and edges).",
    "help.graphHide": "hidden attributes — masks literal nodes: attributes are grouped in a badge (counter) on the node; hover the badge to read them.",
    "help.graphFocus": "click on a node — masks the nodes that do not concern it (direct neighborhood); a click on empty space shows everything again.",
    // ── editor / document labels ─────────────────────────────────────
    "label.document": "document",
    "label.rules": "rules",
    "label.query": "query",
    "label.conclusion": "conclusion",
    "label.proof": "proof",
    "doc.data": "data",
    "doc.rules": "rules",
    "doc.query": "query",
    "doc.conclusion": "conclusion",
    "doc.proof": "proof",
    "doc.server": "server",
    // ── status bar ───────────────────────────────────────────────────
    "status.parsing": "parsing…",
    "status.syntaxError": "syntax error",
    "status.networkError": "network error: {1}",
    "status.ok": "OK{1}",
    // ── parse ────────────────────────────────────────────────────────
    "parse.editorError": "Editor '{1}': syntax error.",
    "parse.errorLine": "line {1}, col. {2} — {3}",
    "parse.editorValid": "Editor '{1}': valid.",
    "parse.editorValidQuery": "Editor '{1}': valid query.",
    "parse.statements": "statement(s)",
    "parse.rules": "rule(s)",
    "parse.blankNodes": "blank node(s)",
    "parse.queryType": "type:",
    "parse.queryTypeUnknown": "unknown",
    "parse.variables": "variables:",
    "parse.noVariables": "— (SELECT * or ASK)",
    "export.empty": "(empty document)",
    // ── shared meta ──────────────────────────────────────────────────
    "meta.newFacts": "{1} new fact(s)",
    "meta.closure": "{1} statement(s) in the closure",
    "meta.storedRules": "{1} stored rule(s)",
    "meta.cache": "cached",
    // ── reasoning ────────────────────────────────────────────────────
    "infer.timeoutTail": " — reasoning was interrupted; the page stays usable.",
    "infer.inconsistent": "⚠ <b>Inconsistent</b>: the closure contains the constant <code>log:false</code> (a rule leads to a contradiction).",
    "infer.newFactsTitle": "New facts (absent from the original data):",
    "infer.noNewFacts": "No new fact: the closure is identical to the data (the rules do not apply, or already converged).",
    "infer.busy": "Reasoning in progress… (a non-convergent rule is interrupted at the timeout).",
    "btn.reasoning": "reasoning…",
    // ── query ────────────────────────────────────────────────────────
    "query.busy": "Query in progress…",
    "query.busyReason": " (closure first — a non-convergent rule is interrupted at the timeout).</p>",
    "query.metaAsk": "ASK: {1}",
    "query.metaAskReasoned": "after reasoning: {1}",
    "query.rowsRaw": "{1} row(s) on the raw data",
    "query.rowsReasoned": "{1} row(s) after reasoning, {2} new",
    "query.timeoutTail": " — the closure was interrupted; only the raw results are shown.",
    "query.askRaw": "ASK on the raw data: <b>{1}</b>",
    "query.askReasoned": "ASK after reasoning: <b>{1}</b>",
    "query.askChanged": " <span class=\"muted\">(reasoning changed the answer)</span>",
    "query.resultsRaw": "Results (raw data)",
    "query.rawData": "Raw data",
    "query.afterReasoning": "After reasoning",
    "query.newRowsHl": "<span class=\"muted\">(new rows highlighted)</span>",
    "query.noRows": "(0 rows)",
    "query.rowNew": "new row: produced by reasoning",
    "ask.true": "true",
    "ask.false": "false",
    "btn.querying": "querying…",
    // ── entailment / proof ───────────────────────────────────────────
    "entail.timeoutTail": " — reasoning was interrupted; the conclusion could not be tested.",
    "entail.yes": "✔ <b>Yes</b>: the closure (data + applied rules) <b>entails</b> the conclusion.",
    "entail.no": "✘ <b>No</b>: the closure does not contain the conclusion — no derivation produces it.",
    "entail.inconsistent": "⚠ The closure is <b>inconsistent</b> (<code>log:false</code>): by explosion, <i>every</i> conclusion is 'entailed' in it — the yes above is worthless.",
    "entail.busy": "Entailment test in progress… (closure first — a non-convergent rule is interrupted at the timeout).",
    "btn.testing": "testing…",
    "prove.timeoutTail": " — the proof could not be generated.",
    "prove.generated": "✔ Proof generated: the closure (data + rules) is the proved formula. It is in the <b>Proof</b> tab — <b>tamper with it by hand</b> (a predicate, a step, a source…), then click 'Check the proof'.",
    "prove.busy": "Generating the proof… (closure first — a non-convergent rule is interrupted at the timeout).",
    "btn.generating": "generating…",
    "check.stepsMeta": "{1} derivation step(s)",
    "check.valid": "✔ <b>Valid proof</b>: the derivation is replayed without error — the proved formula does follow from the sources, by the rules.",
    "check.invalid": "✘ <b>Invalid proof</b>: the derivation cannot be replayed. Reason: <code>{1}</code>",
    "check.invalidReason": "unknown",
    "check.stepsIntro": "Steps (unrolled before the failure — if tampered, this is where you see the breaking point):",
    "check.stepsSummary": "Derivation steps ({1})",
    "check.busy": "Checking in progress… (check replays the derivation in a dedicated process).",
    "btn.checking": "checking…",
    "empty": "(empty)",
    // ── exercises ────────────────────────────────────────────────────
    "exercise.emptyEnonce": "(empty statement)",
    "exercise.loadError": "Network error while loading: {1}",
    "exercise.cannotLoad": "Cannot load the exercise: {1}",
    "exercise.unreadable": "unreadable exercise",
    "exercise.opt": "{1} ({2} .n3 file(s))",
    // ── AI generation ────────────────────────────────────────────────
    "ia.bannerPrefix": "⚠ AI-generated data",
    "ia.bannerSuffix": " — check before reasoning / querying.",
    "ia.quota": "daily quota: {1} request(s), {2} tokens",
    "ia.unconfigured": "AI not configured",
    "ia.btnTitle": "Generate realistic data (domain of the loaded exercise) and inject them into the 'data' editor — checked, to be verified",
    "ia.model": "model: {1}",
    "ia.attempt": "attempt {1}",
    "ia.tokens": "{1} tokens",
    "ia.elapsed": "{1} s",
    "ia.accepted": "✓ Generation accepted (attempt {1}) — the data are in the 'data' editor.",
    "ia.warning": "(warning: {1})",
    "ia.parseFacts": "({1} facts)",
    "ia.inferredFacts": "({1} inferred facts)",
    "ia.plausibility": "({1} facts, {2} entities)",
    "ia.ctrlParse": "parse",
    "ia.ctrlCoherence": "coherence",
    "ia.ctrlPlausibility": "plausibility",
    "ia.acceptedNote": "The generated data are <strong>in the 'data' editor</strong> — read them, correct them, delete them. They are not human-verified: check the values (and thresholds) against the statement before reasoning or querying.",
    "ia.busyBtn": "generating…",
    "ia.busy": "Generating… (a few seconds — the answer is checked: parse, coherence with the rules, plausibility; on failure, bounded regeneration, at most 3 attempts).",
    // ── graph (dynamic) ──────────────────────────────────────────────
    "graph.statements": "{1} statement(s)",
    "graph.nodes": "{1} node(s)",
    "graph.edges": "{1} edge(s)",
    "graph.truncated": " (truncated)",
    "graph.truncatedMsg": "Graph truncated (too many statements to stay readable): {1} shown.",
    "graph.networkError": "Network error: {1}",
    "graph.unknownError": "unknown error",
  },
};

let current = localStorage.getItem(LANG_KEY);
if (!LANGS.includes(current)) current = "fr";

export function lang() {
  return current;
}

// Traduction de ``key`` dans la langue courante (repli : fr, puis la
// clé elle-même — un trou dans le dictionnaire ne casse jamais la page).
// ``{1}``, ``{2}``, … sont remplacés par les arguments.
export function t(key, ...args) {
  let s = (MESSAGES[current] || {})[key];
  if (s === undefined) s = MESSAGES.fr[key];
  if (s === undefined) return key;
  args.forEach((a, i) => {
    s = s.split("{" + (i + 1) + "}").join(String(a));
  });
  return s;
}

// Applique les attributs data-i18n* de index.html + langue du <html>
// + titre de page.
export function applyStatic() {
  document.documentElement.lang = current;
  document.title = t("page.title");
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPh);
  });
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    el.title = t(el.dataset.i18nTitle);
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((el) => {
    el.setAttribute("aria-label", t(el.dataset.i18nAria));
  });
  // Liens dont la cible suit la langue (ex. le README de CWM 2.0) :
  // chaque dictionnaire porte sa propre valeur de href.
  document.querySelectorAll("[data-i18n-href]").forEach((el) => {
    el.setAttribute("href", t(el.dataset.i18nHref));
  });
}

const listeners = [];
export function onLangChange(fn) {
  listeners.push(fn);
}

export function setLang(l) {
  if (!LANGS.includes(l) || l === current) return;
  current = l;
  localStorage.setItem(LANG_KEY, l);
  applyStatic();
  const sel = document.getElementById("lang-select");
  if (sel) sel.value = current;
  listeners.forEach((fn) => fn());
}

// Initialisation : module exécuté après parsing du DOM (defer).
applyStatic();
const _sel = document.getElementById("lang-select");
if (_sel) {
  _sel.value = current;
  _sel.addEventListener("change", () => setLang(_sel.value));
}
