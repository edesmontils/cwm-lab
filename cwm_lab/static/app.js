/* app.js — front de CWM Lab (P1 → P7).

Cinq éditeurs CodeMirror 6 (bundle local, voir
static/vendor/codemirror/README.md) — données, règles, requête,
conclusion/preuve (cet éditeur a deux onglets) — avec :

- coloration Turtle (parser Lezer du paquet `codemirror-lang-turtle`)
  + surcouche pour la syntaxe propre à N3 (`@forAll`, `@forSome`,
  `log:implies`, variables `?x`) ;
- auto-parse au frappage (debounce ~500 ms) → /api/parse (N3/Turtle
  pour les deux premiers éditeurs, SPARQL pour l'éditeur de requête) ;
- erreurs de parse affichées dans la gouttière (linter) et dans
  l'onglet « Parse » des résultats (ligne/colonne) ;
- base URI configurable (persistée dans localStorage) ;
- export N3 / Turtle / NTriples / RDF/XML → /api/serialize ;
- bouton **Raisonner** → /api/infer : clôture (convergence ou 1 passe),
  liste des nouveaux faits, signal d'incohérence (log:false),
  timeout sur les règles non convergentes ;
- bouton **Interroger** → /api/query : exécution SPARQL (SELECT/ASK),
  avec ou sans raisonnement préalable — dans le second cas, la même
  requête est ré-exécutée sur la clôture et les lignes nouvelles du
  diff avant/après sont surlignées ;
- bouton **Entraîne ?** → /api/entail : la clôture contient-elle la
  conclusion (test d'entraînement, « oui / non ») ;
- bouton **Pourquoi ?** → /api/prove : génération de la preuve dans
  l'onglet « Preuve » (la preuve est auto-suffisante : sources en
  URI data:, altérable à la main) ;
- bouton **Vérifier la preuve** → /api/check : re-vérification par
  check (subprocess) — verdict « valide / invalide » + étapes de
  dérivation ; une preuve altérée est rejetée.

P7 — ergonomie :

- **deux colonnes à largeur ajustable** : poignée de glissement entre
  les colonnes (largeur relative 25–75 %, persistée en
  localStorage) ; les pistes du grid sont `minmax(0, …)` — un
  résultat (preuve, tableau, …) ne change JAMAIS la largeur des
  colonnes ;
- **éditeur Conclusion/Preuve dans la colonne de droite** (à côté du
  graphe et des résultats) : une preuve générée fait des dizaines de
  lignes, elle ne gonfle plus la colonne des éditeurs ;
- **graphe systématiquement visible** : panneau persistant dans la
  colonne de droite, re-rendu à chaque action (édition des
  données/règles, raisonnement, requête, chargement d'exercice) —
  plus de bouton « Graphe » ;
- **mode « attributs masqués »** : les nœuds-littéraux sont masqués,
  leurs attributs regroupés en pastille (compteur) sur le nœud ;
  survol de la pastille = liste des attributs ;
- **résultats consolidés en onglets** (Parse / Raisonnement /
  Requête / Entraînement / Preuve / Export) — l'onglet correspondant
  s'ouvre à chaque action ; un point signale un nouvel résultat
  dans un onglet masqué ;
- **barre d'actions unifiée** : boutons groupés par objectif
  (Raisonnement / Interroger / Valider) ;
- **énoncés rendus en HTML** (Markdown, converti côté serveur —
  les `.md` restent la source de vérité dans le dépôt).

Rappel (voir lab/ROADMAP.md) : la syntaxe de règle du parser CWM est
`{ … } log:implies { … } .` (pas `!{…} -> {…}`), et les variables se
déclarent avec `@forAll :x , :y .` (un `:x` nu est une constante).
La requête SPARQL s'écrit `PREFIX : <…>` + `SELECT ?x WHERE { … }` :
mot-clé `PREFIX` (pas `@prefix`) et pas de point final après la
déclaration de préfixe — autre grammaire que les deux premiers
éditeurs.
*/
"use strict";

import {
  EditorView, keymap, Decoration,
  syntaxHighlighting, HighlightStyle,
  linter, lintGutter, forceLinting,
  tags, turtle, basicSetup,
} from "/static/vendor/codemirror/codemirror.js";
import { t, onLangChange, lang as i18nLang } from "/static/i18n.js";

// URI de base par défaut — identique à engine.DEFAULT_BASE_URI.
const DEFAULT_BASE_URI = "http://example.org/document.n3";

// Exemple préchargé (éditeur « données ») : un petit graphe familial.
const EXAMPLE_KB = `@prefix : <http://example.org/> .

:alice a :Person .
:bob   a :Person .
:carl  a :Person .
:alice :parentOf :bob .
:bob   :parentOf :carl .
`;

// Exemple préchargé (éditeur « règles ») : la règle de grand-parent.
const EXAMPLE_RULES = `@prefix : <http://example.org/> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

@forAll :x , :y , :z .
{ :x :parentOf :y . :y :parentOf :z . } log:implies { :x :grandparentOf :z } .
`;

// Exemple préchargé (éditeur « requête ») : SELECT grand-parent —
// 0 ligne sur les données brutes, 1 ligne après raisonnement
// (le diff avant/après est visible immédiatement).
const EXAMPLE_QUERY = `PREFIX : <http://example.org/>
SELECT ?s ?o
WHERE { ?s :grandparentOf ?o . }
`;

// Exemple préchargé (éditeur « conclusion ») : le fait du grand-parent —
// absent des données brutes, entraîné par les règles après raisonnement
// (le bouton « Entraîne ? » répond donc oui).
const EXAMPLE_CONCL = `@prefix : <http://example.org/> .

:alice :grandparentOf :carl .
`;

// Contenu préchargé (éditeur « preuve ») : des commentaires (N3 valide,
// formule vide) — une vraie preuve apparaît ici après « Pourquoi ? ».
const EXAMPLE_PROOF = `# La preuve générée (bouton « Pourquoi ? ») apparaîtra ici.
# Altérez-la à la main (un prédicat, une étape, une source…) puis
# cliquez sur « Vérifier la preuve » : la dérivation est re-jouée
# par check, qui rejette toute preuve altérée.
`;

// ----------------------------------------------------------------------
// Coloration
// ----------------------------------------------------------------------

// Thème de coloration des balises Lezer du langage Turtle
// (IRIs, préfixes, littéraux, nœuds vides, commentaires, …).
const n3Theme = HighlightStyle.define([
  { tag: tags.keyword,       color: "#7c3aed", fontWeight: "bold" },
  { tag: tags.namespace,     color: "#0e7490" },
  { tag: tags.url,           color: "#155e75" },
  { tag: tags.propertyName,  color: "#1d4ed8" },
  { tag: tags.string,        color: "#15803d" },
  { tag: tags.annotation,    color: "#be185d" },
  { tag: tags.typeName,      color: "#7c3aed" },
  { tag: tags.integer,       color: "#b45309" },
  { tag: tags.float,         color: "#b45309" },
  { tag: tags.bool,          color: "#b45309", fontWeight: "bold" },
  { tag: tags.comment,       color: "#94a3b8", fontStyle: "italic" },
  { tag: tags.separator,     color: "#64748b" },
  { tag: tags.squareBracket, color: "#64748b" },
]);

// Mots-clés N3 absents de la grammaire Turtle : le parser Lezer ne les
// balance pas, on ajoute une décoration par expression régulière (les
// documents de TP sont petits : le scan ligne à ligne est négligeable).
const N3_RE = /(@forAll|@forSome)|(log:implies|:implies)|(\?[\w]+)/g;
const N3_CLASS = ["cm-n3-directive", "cm-n3-rule", "cm-n3-var"];

// NB : les fonctions du facet `decorations` reçoivent le *view*
// (EditorView), pas l'état — d'où `view.state.doc`.
// (`doc.lines` est le *nombre* de lignes ; `doc.line(n)` renvoie la
// ligne n.)
const n3Overlay = EditorView.decorations.of((view) => {
  const doc = view.state.doc;
  const specs = [];
  for (let i = 1; i <= doc.lines; i++) {
    const line = doc.line(i);
    let m;
    N3_RE.lastIndex = 0;
    while ((m = N3_RE.exec(line.text)) !== null) {
      const group = m[1] !== undefined ? 0 : m[2] !== undefined ? 1 : 2;
      specs.push(
        Decoration.mark({ class: N3_CLASS[group] }).range(
          line.from + m.index, line.from + m.index + m[0].length));
    }
  }
  return Decoration.set(specs);
});

// ----------------------------------------------------------------------
// Onglets de résultats (P7) : un seul panneau à onglets au lieu de
// N blocs empilés — l'onglet correspondant s'ouvre à chaque action ;
// un point signale un résultat nouveau dans un onglet masqué.
// ----------------------------------------------------------------------

const TABS = ["parse", "infer", "query", "entail", "proof", "export", "ia"];
const tabButtons = {};
const tabPanes = {};
for (const name of TABS) {
  tabButtons[name] = document.querySelector(
    `.res-tab[data-tab="${name}"]`);
  tabPanes[name] = document.getElementById("pane-" + name);
}
let activeTab = "parse";

function switchTab(name) {
  activeTab = name;
  for (const t of TABS) {
    tabButtons[t].classList.toggle("active", t === name);
    tabPanes[t].classList.toggle("active", t === name);
    if (t === name) tabButtons[t].classList.remove("dot");
  }
}

// Signale un résultat nouveau dans l'onglet ``name`` (point sur le
// libellé) — seulement s'il n'est pas celui affiché.
function markTab(name) {
  if (name !== activeTab) tabButtons[name].classList.add("dot");
}

for (const name of TABS) {
  tabButtons[name].addEventListener("click", () => switchTab(name));
}

// ----------------------------------------------------------------------
// Parse (auto, debounce ~500 ms)
// ----------------------------------------------------------------------

const results = document.getElementById("results");
const status = document.getElementById("status");
const baseUriInput = document.getElementById("base-uri");

let parseSeq = 0;         // contre les réponses en retard
let parseTimer = null;

// Parse dédupliqué : un seul fetch par (langage, contenu, base). Le
// linter et le panneau de résultats partagent la même requête
// in-flight. ``language`` : "n3" (données, règles) ou "sparql"
// (éditeur de requête).
let inflight = null;
function runParse(text, base_uri, language = "n3") {
  const key = language + "\u0000" + text + "\u0000" + base_uri;
  if (inflight && inflight.key === key) return inflight.promise;
  inflight = {
    key,
    promise: fetch("/api/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, base_uri, language }),
    }).then((r) => r.json()),
  };
  return inflight.promise;
}

// Les erreurs de parse deviennent des diagnostics CodeMirror (marqueurs
// dans la gouttière + infobulle au survol). La source est asynchrone :
// elle attend le parse dédupliqué, toujours à jour du document courant.
function toDiagnostics(view, data) {
  if (!data || data.ok) return [];
  const doc = view.state.doc;
  const diags = [];
  for (const e of data.errors || []) {
    if (!e.line || e.line < 1) continue;
    // `doc.line(n)` lève si n est hors plage : on clamp d'abord.
    const line = doc.line(Math.max(1, Math.min(e.line, doc.lines)));
    const col = Math.max(0, (e.column || 1) - 1);
    const from = line.from + Math.min(col, line.text.length);
    diags.push({
      from,
      to: Math.min(line.to, from + 1),
      severity: "error",
      message: e.message,
    });
  }
  return diags;
}

// Fabrique de linter : un linter par langage (le linter de l'éditeur de
// requête valide du SPARQL, pas du N3).
function makeLinter(language) {
  return linter(async (view) => {
    const base_uri = baseUriInput.value.trim() || DEFAULT_BASE_URI;
    try {
      const data = await runParse(view.state.doc.toString(), base_uri, language);
      return toDiagnostics(view, data);
    } catch {
      return [];                            // serveur injoignable : pas de faux marqueurs
    }
  }, { delay: 250 });
}

// Fabrique d'éditeur : mêmes extensions pour les trois éditeurs
// (données, règles, requête) — coloration, surcouche N3, linter
// (par langage), auto-parse.
function makeEditor(parentId, doc, language, onDocChanged) {
  return new EditorView({
    parent: document.getElementById(parentId),
    doc,
    extensions: [
      basicSetup,
      turtle(),                            // langage Turtle (Lezer)
      syntaxHighlighting(n3Theme),         // avant le thème de secours de basicSetup
      n3Overlay,                           // surcouche (variables ?x, …)
      makeLinter(language),
      lintGutter(),                        // gouttière des diagnostics
      EditorView.updateListener.of((u) => {
        if (u.docChanged) onDocChanged();
      }),
      keymap.of([{
        key: "Mod-Enter",
        run: () => { onDocChanged(0); return true; },
      }]),
    ],
  });
}

// P7 : l'édition des données / des règles change le graphe →
// rafraîchissement planifié (debounce, dernier état l'emporte).
let graphTimer = null;
function scheduleGraphRefresh(delay = 800) {
  clearTimeout(graphTimer);
  graphTimer = setTimeout(() => refreshGraph(), delay);
}

const editorView = makeEditor("editor", EXAMPLE_KB, "n3", (delay) => {
  scheduleParse("kb", delay);
  scheduleGraphRefresh();
  hideIaBanner();   // P9 : toute édition (manuelle ou chargement)
                    // masque la bannière « généré par IA »
});
const rulesView = makeEditor("editor-rules", EXAMPLE_RULES, "n3", (delay) => {
  scheduleParse("rules", delay);
  scheduleGraphRefresh();
});
const queryView = makeEditor("editor-query", EXAMPLE_QUERY, "sparql", (delay) => scheduleParse("query", delay));
const conclView = makeEditor("editor-concl", EXAMPLE_CONCL, "n3", (delay) => scheduleParse("concl", delay));
const proofView = makeEditor("editor-proof", EXAMPLE_PROOF, "n3", (delay) => scheduleParse("proof", delay));

const editorViews = { kb: editorView, rules: rulesView, query: queryView,
                      concl: conclView, proof: proofView };
const editorLangs = { kb: "n3", rules: "n3", query: "sparql",
                      concl: "n3", proof: "n3" };
// Libellés des éditeurs (localisés — i18n.js).
const LABEL_KEY = { kb: "label.document", rules: "label.rules",
                    query: "label.query", concl: "label.conclusion",
                    proof: "label.proof" };
const labelOf = (which) => t(LABEL_KEY[which] || which);
// Libellés des documents taguant les erreurs (kb / rules / query /
// concl / proof / server — P6 : « serveur occupé ») — localisés.
const DOC_KEY = { kb: "doc.data", rules: "doc.rules", query: "doc.query",
                  concl: "doc.conclusion", proof: "doc.proof",
                  server: "doc.server" };
const docLabel = (which) => t(DOC_KEY[which] || which);

// i18n : dernier état de chaque rendu — un changement de langue
// re-rend les résultats dans la nouvelle langue (sans re-fetch, sans
// re-réclamer l'onglet actif, sans écraser les éditions manuelles).
const lastRender = { parse: null, infer: null, query: null, entail: null,
                     prove: null, check: null, ia: null, graph: null,
                     exportFormat: null };

// Onglets « Conclusion / Preuve » (éditeur 4) : deux CodeMirror, un
// seul visible. Le passage d'onglet réveille le view caché (mesure).
function showProofTab(which) {
  const isConcl = which === "concl";
  document.getElementById("editor-concl").hidden = !isConcl;
  document.getElementById("editor-proof").hidden = isConcl;
  document.getElementById("tab-concl").classList.toggle("active", isConcl);
  document.getElementById("tab-proof").classList.toggle("active", !isConcl);
  (isConcl ? conclView : proofView).requestMeasure();
}
document.getElementById("tab-concl").addEventListener("click", () => showProofTab("concl"));
document.getElementById("tab-proof").addEventListener("click", () => showProofTab("proof"));

function setStatus(text, cls) {
  status.textContent = text;
  status.className = "status" + (cls ? " " + cls : "");
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// Le panneau « Parse » (premier onglet) affiche le parse du dernier
// éditeur modifié.
let activeEditor = "kb";

function scheduleParse(which, delay = 500) {
  activeEditor = which;
  clearTimeout(parseTimer);
  parseTimer = setTimeout(() => parseNow(which), delay);
}

async function parseNow(which) {
  activeEditor = which || activeEditor;
  const seq = ++parseSeq;
  const view = editorViews[activeEditor];
  const language = editorLangs[activeEditor];
  setStatus(t("status.parsing"));
  const text = view.state.doc.toString();
  const base_uri = baseUriInput.value.trim() || DEFAULT_BASE_URI;
  try {
    const data = await runParse(text, base_uri, language);
    if (seq !== parseSeq) return;        // réponse devenue obsolète
    renderResults(data, activeEditor);
    forceLinting(view);
    // P7 : un parse des données change le graphe (debounce plus long :
    // le parse du linter vient de tout faire, ici c'est du bonus).
    if (activeEditor === "kb") scheduleGraphRefresh(600);
  } catch (e) {
    if (seq !== parseSeq) return;
    setStatus(t("status.networkError", e), "error");
  }
}

function renderResults(data, which, tab = true) {
  which = which || activeEditor;
  lastRender.parse = { data, which };
  const label = labelOf(which);
  if (!data.ok) {
    setStatus(t("status.syntaxError"), "error");
    const items = (data.errors || []).map((er) =>
      `<li class="error">${t("parse.errorLine", er.line, er.column, esc(er.message))}</li>`
    ).join("");
    results.innerHTML = `<p class="error">${t("parse.editorError", esc(label))}</p>
      <ul class="errors">${items}</ul>`;
    if (tab) markTab("parse");
    return;
  }
  const st = data.stats;
  setStatus(t("status.ok", data.cached ? " (" + t("meta.cache") + ")" : ""));
  if (which === "query") {
    // Stats SPARQL : type de requête + variables de la clause SELECT.
    results.innerHTML = `
    <p class="ok">${t("parse.editorValidQuery", esc(label))}</p>
    <ul class="stats">
      <li>${t("parse.queryType")} <b>${esc(st.queryType || t("parse.queryTypeUnknown"))}</b></li>
      <li>${t("parse.variables")} ${st.variables.length
        ? st.variables.map((v) => `<code>?${esc(v)}</code>`).join(" ")
        : t("parse.noVariables")}</li>
    </ul>`;
    return;
  }
  results.innerHTML = `
    <p class="ok">${t("parse.editorValid", esc(label))}</p>
    <ul class="stats">
      <li><b>${st.statements}</b> ${t("parse.statements")}</li>
      <li><b>${st.rules}</b> ${t("parse.rules")} <code>log:implies</code></li>
      <li><b>${st.blankNodes}</b> ${t("parse.blankNodes")}</li>
    </ul>`;
  if (tab) markTab("parse");
}

document.getElementById("btn-parse").addEventListener("click", () => parseNow(activeEditor));

// Base URI : persistée, re-parse au changement.
baseUriInput.value = localStorage.getItem("cwm-tp-base-uri") || DEFAULT_BASE_URI;
baseUriInput.addEventListener("change", () => {
  localStorage.setItem("cwm-tp-base-uri", baseUriInput.value.trim());
  parseNow();
  scheduleGraphRefresh(100);   // P7 : la base URI change les IRI complets
});

// ----------------------------------------------------------------------
// Export (N3 / Turtle / NTriples / RDF/XML) — onglet « Export » (P7)
// ----------------------------------------------------------------------

const exportFormat = document.getElementById("export-format");
const exportOutput = document.getElementById("export-output");
const exportDownload = document.getElementById("export-download");

const EXPORT_LABEL = { n3: "N3", turtle: "Turtle", ntriples: "NTriples", rdf: "RDF/XML" };
const EXPORT_EXT = { n3: ".n3", turtle: ".ttl", ntriples: ".nt", rdf: ".rdf" };

let exportBlobUrl = null;

async function doExport(format) {
  lastRender.exportFormat = format;
  const text = editorView.state.doc.toString();
  const base_uri = baseUriInput.value.trim() || DEFAULT_BASE_URI;
  switchTab("export");
  exportFormat.textContent = "→ " + EXPORT_LABEL[format];
  exportOutput.classList.remove("error");
  try {
    const resp = await fetch("/api/serialize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, base_uri, format }),
    });
    const data = await resp.json();
    if (data.ok) {
      exportOutput.textContent = data.output || t("export.empty");
      const blob = new Blob([data.output], { type: "text/plain;charset=utf-8" });
      if (exportBlobUrl) URL.revokeObjectURL(exportBlobUrl);
      exportBlobUrl = URL.createObjectURL(blob);
      exportDownload.href = exportBlobUrl;
      exportDownload.download = "document" + EXPORT_EXT[format];
      exportDownload.hidden = false;
    } else {
      exportOutput.classList.add("error");
      exportOutput.textContent = (data.errors || []).map((e) => e.message).join("\n");
      exportDownload.hidden = true;
    }
  } catch (e) {
    exportOutput.classList.add("error");
    exportOutput.textContent = t("status.networkError", e);
    exportDownload.hidden = true;
  }
}

document.querySelectorAll(".export-btn").forEach((btn) => {
  btn.addEventListener("click", () => doExport(btn.dataset.format));
});
document.getElementById("export-close").addEventListener("click", () => {
  switchTab("parse");
});

// ----------------------------------------------------------------------
// Raisonnement (P2) : clôture, nouveaux faits, incohérence, timeout
// ----------------------------------------------------------------------

const inferMeta = document.getElementById("infer-meta");
const inferOutput = document.getElementById("infer-output");

function fmtTriple([s, p, o]) {
  return `<code>${esc(s)} ${esc(p)} ${esc(o)} .</code>`;
}

function renderInfer(data, tab = true) {
  lastRender.infer = data;
  const parts = [];

  if (!data.ok && !data.timeout) {
    // erreurs de parse (taguées par éditeur)
    const items = (data.errors || []).map((er) =>
      `<li class="error">${docLabel(er.doc)} — ` +
      `${t("parse.errorLine", er.line, er.column, esc(er.message))}</li>`
    ).join("");
    parts.push(`<ul class="errors">${items}</ul>`);
    inferMeta.textContent = "";
  } else {
    const bits = [];
    bits.push(t("meta.newFacts", data.new_facts.length));
    bits.push(t("meta.closure", data.closure_statements));
    if (data.rules_in_closure) bits.push(t("meta.storedRules", data.rules_in_closure));
    bits.push(data.elapsed_ms + " ms");
    if (data.cached) bits.push(t("meta.cache"));
    inferMeta.textContent = bits.join(" · ");

    if (data.timeout) {
      parts.push(`<p class="banner banner-timeout">⏱ ${
        esc((data.errors || [])[0] && (data.errors[0].message) || "timeout")
      }${t("infer.timeoutTail")}</p>`);
    }
    if (data.inconsistent) {
      parts.push(`<p class="banner banner-error">${t("infer.inconsistent")}</p>`);
    }
    if (data.new_facts.length) {
      parts.push(`<p class="muted">${t("infer.newFactsTitle")}</p>` +
        `<ul class="new-facts">` +
        data.new_facts.map((f) => `<li>${fmtTriple(f)}</li>`).join("") +
        `</ul>`);
    } else if (!data.timeout) {
      parts.push(`<p class="muted">${t("infer.noNewFacts")}</p>`);
    }
  }
  inferOutput.innerHTML = parts.join("") || `<p class="muted">${t("empty")}</p>`;
  if (tab) switchTab("infer");
}

let inferBusy = false;

// Corps de la requête /api/infer — partagé avec le re-fetch de
// changement de langue (i18n P10.1 : les nouveaux faits libellés
// rdfs:label sont choisis dans la langue de l'application).
function inferBody() {
  return {
    kb: editorView.state.doc.toString(),
    rules: rulesView.state.doc.toString(),
    base_uri: baseUriInput.value.trim() || DEFAULT_BASE_URI,
    mode: document.getElementById("infer-mode").value,
    store_rules: document.getElementById("infer-store-rules").checked,
    timeout: parseFloat(document.getElementById("infer-timeout").value) || 0,
    lang: i18nLang(),
  };
}

async function doInfer() {
  if (inferBusy) return;
  inferBusy = true;
  const btn = document.getElementById("btn-infer");
  btn.disabled = true;
  btn.textContent = t("btn.reasoning");
  inferOutput.innerHTML = `<p class="muted">${t("infer.busy")}</p>`;
  const body = inferBody();
  try {
    const resp = await fetch("/api/infer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    renderInfer(data);
    // P7 : le graphe est toujours visible — la clôture change ce qu'il
    // doit montrer : on le rafraîchit, et si le raisonnement a réussi
    // on coche « après raisonnement » (le graphe passe sur la clôture,
    // inférés en orange) — décocher revient aux données brutes.
    if (data.ok && !data.timeout &&
        !document.getElementById("graph-reason").checked) {
      document.getElementById("graph-reason").checked = true;
    }
    refreshGraph();
  } catch (e) {
    inferOutput.innerHTML = `<p class="error">${t("status.networkError", esc(String(e)))}</p>`;
  } finally {
    inferBusy = false;
    btn.disabled = false;
    btn.textContent = t("bar.infer");
  }
}

document.getElementById("btn-infer").addEventListener("click", doInfer);

// ----------------------------------------------------------------------
// Requête SPARQL (P3) : exécution + diff avant/après raisonnement
// ----------------------------------------------------------------------

const queryMeta = document.getElementById("query-meta");
const queryOutput = document.getElementById("query-output");

// Tableau de résultats : colonnes = variables SELECT ; si ``newRows``
// est fourni, les lignes qui y figurent sont surlignées (diff
// avant/après raisonnement).
function queryTable(variables, rows, newRows) {
  if (!rows.length) return `<p class="muted">${t("query.noRows")}</p>`;
  const head = "<tr>" + variables.map((v) => `<th>?${esc(v)}</th>`).join("") + "</tr>";
  const newSet = new Set((newRows || []).map((r) => r.join("\u0000")));
  const body = rows.map((r) => {
    const isNew = newSet.has(r.join("\u0000"));
    return `<tr class="${isNew ? "row-new" : ""}"` +
      (isNew ? ` title="${esc(t("query.rowNew"))}"` : "") +
      `>` + r.map((c) => `<td>${esc(c)}</td>`).join("") + "</tr>";
  }).join("");
  return `<table class="query-table"><thead>${head}</thead><tbody>${body}</tbody></table>`;
}

const askText = (v) => t(v ? "ask.true" : "ask.false");

function renderQuery(data, tab = true) {
  lastRender.query = data;
  const parts = [];

  if (!data.ok && !data.timeout) {
    // erreurs (taguées par éditeur : kb / rules / query)
    const items = (data.errors || []).map((er) =>
      `<li class="error">${docLabel(er.doc)} — ` +
      `${t("parse.errorLine", er.line, er.column, esc(er.message))}</li>`
    ).join("");
    parts.push(`<ul class="errors">${items}</ul>`);
    queryMeta.textContent = "";
  } else {
    const bits = [];
    if (data.query_type === "AskQuery") {
      bits.push(t("query.metaAsk", askText(data.ask_raw)));
      if (data.rows_reasoned) bits.push(t("query.metaAskReasoned", askText(data.ask_reasoned)));
    } else {
      bits.push(t("query.rowsRaw", data.rows_raw.length));
      if (data.rows_reasoned) bits.push(
        t("query.rowsReasoned", data.rows_reasoned.length, data.new_rows.length));
    }
    if (data.closure_statements != null) bits.push(t("meta.closure", data.closure_statements));
    bits.push(data.elapsed_ms + " ms");
    if (data.cached) bits.push(t("meta.cache"));
    queryMeta.textContent = bits.join(" · ");

    if (data.timeout) {
      parts.push(`<p class="banner banner-timeout">⏱ ${
        esc((data.errors || [])[0] && (data.errors[0].message) || "timeout")
      }${t("query.timeoutTail")}</p>`);
    }
    if (data.query_type === "AskQuery") {
      parts.push(`<p class="banner ${data.ask_raw ? "banner-ok" : "banner-muted"}">` +
        t("query.askRaw", askText(data.ask_raw)) + `</p>`);
      if (data.rows_reasoned) {
        parts.push(`<p class="banner ${data.ask_reasoned ? "banner-ok" : "banner-muted"}">` +
          t("query.askReasoned", askText(data.ask_reasoned)) +
          (data.ask_reasoned !== data.ask_raw
            ? t("query.askChanged") : "") +
          `</p>`);
      }
    } else if (!data.rows_reasoned) {
      parts.push(`<h3>${t("query.resultsRaw")}</h3>` +
        queryTable(data.variables, data.rows_raw));
    } else {
      parts.push(`<h3>${t("query.rawData")}</h3>` +
        queryTable(data.variables, data.rows_raw));
      parts.push(`<h3>${t("query.afterReasoning")} ${t("query.newRowsHl")}</h3>` +
        queryTable(data.variables, data.rows_reasoned, data.new_rows));
    }
  }
  queryOutput.innerHTML = parts.join("") || `<p class="muted">${t("empty")}</p>`;
  if (tab) switchTab("query");
}

let queryBusy = false;

// Corps de la requête /api/query — partagé avec le re-fetch de
// changement de langue.
function queryBody(reason) {
  return {
    kb: editorView.state.doc.toString(),
    rules: rulesView.state.doc.toString(),
    query: queryView.state.doc.toString(),
    base_uri: baseUriInput.value.trim() || DEFAULT_BASE_URI,
    reason,
    mode: document.getElementById("infer-mode").value,
    store_rules: document.getElementById("infer-store-rules").checked,
    timeout: parseFloat(document.getElementById("infer-timeout").value) || 0,
    lang: i18nLang(),
  };
}

async function doQuery() {
  if (queryBusy) return;
  queryBusy = true;
  const btn = document.getElementById("btn-query");
  btn.disabled = true;
  btn.textContent = t("btn.querying");
  const reason = document.getElementById("query-reason").checked;
  queryOutput.innerHTML = `<p class="muted">${t("query.busy")}` +
    (reason ? t("query.busyReason") : `</p>`);
  // Les options de raisonnement (mode, règles stockées, timeout) sont
  // celles de la barre commune — identiques pour « Raisonner » et pour
  // « Interroger » avec raisonnement. lang : les IRI des résultats
  // porteurs d'un rdfs:label sont choisis dans la langue courante
  // (i18n P10.1).
  const body = queryBody(reason);
  try {
    const resp = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    renderQuery(data);
    // P7 : une requête « avec raisonnement » a calculé la clôture —
    // le graphe y passe (même règle qu'après « Raisonner »).
    if (data.ok && !data.timeout && reason) {
      if (!document.getElementById("graph-reason").checked) {
        document.getElementById("graph-reason").checked = true;
      }
      refreshGraph();
    }
  } catch (e) {
    queryOutput.innerHTML = `<p class="error">${t("status.networkError", esc(String(e)))}</p>`;
  } finally {
    queryBusy = false;
    btn.disabled = false;
    btn.textContent = t("bar.query");
  }
}

document.getElementById("btn-query").addEventListener("click", doQuery);

// ----------------------------------------------------------------------
// Validité & preuves (P4) : Entraîne ? / Pourquoi ? / Vérifier la preuve
// ----------------------------------------------------------------------

const entailMeta = document.getElementById("entail-meta");
const entailOutput = document.getElementById("entail-output");
const proofMeta = document.getElementById("proof-meta");
const proofOutput = document.getElementById("proof-output");

// Les options de raisonnement (mode, timeout) sont celles de la barre
// commune — identiques pour « Raisonner », « Interroger » et les tests
// d'entraînement / génération de preuve.
function reasoningOptions() {
  return {
    mode: document.getElementById("infer-mode").value,
    timeout: parseFloat(document.getElementById("infer-timeout").value) || 0,
  };
}

// Étape de dérivation (sortie de check --report) : numéro, énoncé,
// justification (« [by …] »).
function stepsList(steps) {
  if (!steps.length) return "";
  return `<details class="proof-steps"><summary>${t("check.stepsSummary", steps.length)}</summary>
    <ol class="proof-steps-list">` +
    steps.map((s) =>
      `<li><code>${esc(s.statement || "…")}</code>` +
      (s.how ? `<div class="step-how">${esc(s.how)}</div>` : "") +
      `</li>`).join("") +
    `</ol></details>`;
}

function renderEntail(data, tab = true) {
  lastRender.entail = data;
  const parts = [];
  if (!data.ok && !data.timeout) {
    const items = (data.errors || []).map((er) =>
      `<li class="error">${docLabel(er.doc)} — ` +
      `${t("parse.errorLine", er.line, er.column, esc(er.message))}</li>`).join("");
    parts.push(`<ul class="errors">${items}</ul>`);
    entailMeta.textContent = "";
  } else {
    const bits = [];
    bits.push(t("meta.closure", data.closure_statements));
    bits.push(data.elapsed_ms + " ms");
    if (data.cached) bits.push(t("meta.cache"));
    entailMeta.textContent = bits.join(" · ");
    if (data.timeout) {
      parts.push(`<p class="banner banner-timeout">⏱ ${
        esc((data.errors || [])[0] && data.errors[0].message || "timeout")
      }${t("entail.timeoutTail")}</p>`);
    } else if (data.entails) {
      parts.push(`<p class="banner banner-ok">${t("entail.yes")}</p>`);
    } else {
      parts.push(`<p class="banner banner-muted">${t("entail.no")}</p>`);
    }
    if (data.inconsistent && data.entails) {
      parts.push(`<p class="banner banner-error">${t("entail.inconsistent")}</p>`);
    }
  }
  entailOutput.innerHTML = parts.join("") || `<p class="muted">${t("empty")}</p>`;
  if (tab) switchTab("entail");
}

let entailBusy = false;

async function doEntail() {
  if (entailBusy) return;
  entailBusy = true;
  const btn = document.getElementById("btn-entail");
  btn.disabled = true;
  btn.textContent = t("btn.testing");
  entailOutput.innerHTML = `<p class="muted">${t("entail.busy")}</p>`;
  const opts = reasoningOptions();
  try {
    const resp = await fetch("/api/entail", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kb: editorView.state.doc.toString(),
        rules: rulesView.state.doc.toString(),
        conclusion: conclView.state.doc.toString(),
        base_uri: baseUriInput.value.trim() || DEFAULT_BASE_URI,
        ...opts,
      }),
    });
    renderEntail(await resp.json());
  } catch (e) {
    entailOutput.innerHTML = `<p class="error">${t("status.networkError", esc(String(e)))}</p>`;
  } finally {
    entailBusy = false;
    btn.disabled = false;
    btn.textContent = t("bar.entail");
  }
}

document.getElementById("btn-entail").addEventListener("click", doEntail);

function renderProve(data, tab = true) {
  lastRender.prove = data;
  const parts = [];
  if (!data.ok && !data.timeout) {
    const items = (data.errors || []).map((er) =>
      `<li class="error">${docLabel(er.doc)} — ` +
      `${t("parse.errorLine", er.line, er.column, esc(er.message))}</li>`).join("");
    parts.push(`<ul class="errors">${items}</ul>`);
    proofMeta.textContent = "";
  } else if (data.timeout) {
    parts.push(`<p class="banner banner-timeout">⏱ ${
      esc((data.errors || [])[0] && data.errors[0].message || "timeout")
    }${t("prove.timeoutTail")}</p>`);
    proofMeta.textContent = "";
  } else {
    const bits = [t("meta.closure", data.closure_statements),
                  data.elapsed_ms + " ms"];
    if (data.cached) bits.push(t("meta.cache"));
    proofMeta.textContent = bits.join(" · ");
    parts.push(`<p class="banner banner-ok">${t("prove.generated")}</p>`);
    // La preuve est mise dans l'éditeur (uniquement au rendu « frais » :
    // un re-rendu à changement de langue n'écrase PAS une preuve
    // altérée à la main).
    if (tab) {
      showProofTab("proof");
      proofView.dispatch({
        changes: { from: 0, to: proofView.state.doc.length, insert: data.proof },
      });
    }
  }
  proofOutput.innerHTML = parts.join("") || `<p class="muted">${t("empty")}</p>`;
  if (tab) switchTab("proof");
}

let whyBusy = false;

async function doWhy() {
  if (whyBusy) return;
  whyBusy = true;
  const btn = document.getElementById("btn-why");
  btn.disabled = true;
  btn.textContent = t("btn.generating");
  proofOutput.innerHTML = `<p class="muted">${t("prove.busy")}</p>`;
  const opts = reasoningOptions();
  try {
    const resp = await fetch("/api/prove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kb: editorView.state.doc.toString(),
        rules: rulesView.state.doc.toString(),
        base_uri: baseUriInput.value.trim() || DEFAULT_BASE_URI,
        ...opts,
      }),
    });
    renderProve(await resp.json());
  } catch (e) {
    proofOutput.innerHTML = `<p class="error">${t("status.networkError", esc(String(e)))}</p>`;
  } finally {
    whyBusy = false;
    btn.disabled = false;
    btn.textContent = t("bar.why");
  }
}

document.getElementById("btn-why").addEventListener("click", doWhy);

function renderCheck(data, tab = true) {
  lastRender.check = data;
  const parts = [];
  if (!data.ok) {
    const items = (data.errors || []).map((er) =>
      `<li class="error">${esc(er.message)}</li>`).join("");
    parts.push(`<ul class="errors">${items}</ul>`);
    proofMeta.textContent = "";
  } else {
    const bits = [];
    bits.push(t("check.stepsMeta", data.steps.length));
    bits.push(data.elapsed_ms + " ms");
    if (data.cached) bits.push(t("meta.cache"));
    proofMeta.textContent = bits.join(" · ");
    if (data.valid) {
      parts.push(`<p class="banner banner-ok">${t("check.valid")}</p>`);
    } else if (data.valid === false) {
      parts.push(`<p class="banner banner-error">${
        t("check.invalid", esc(data.reason || t("check.invalidReason")))}</p>`);
    }
    if (data.valid === false && data.steps.length) {
      parts.push(`<p class="muted">${t("check.stepsIntro")}</p>`);
    }
  }
  parts.push(stepsList(data.steps));
  proofOutput.innerHTML = parts.join("") || `<p class="muted">${t("empty")}</p>`;
  if (tab) switchTab("proof");
}

let checkBusy = false;

async function doCheck() {
  if (checkBusy) return;
  checkBusy = true;
  const btn = document.getElementById("btn-check");
  btn.disabled = true;
  btn.textContent = t("btn.checking");
  proofOutput.innerHTML = `<p class="muted">${t("check.busy")}</p>`;
  try {
    const resp = await fetch("/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ proof: proofView.state.doc.toString() }),
    });
    renderCheck(await resp.json());
  } catch (e) {
    proofOutput.innerHTML = `<p class="error">${t("status.networkError", esc(String(e)))}</p>`;
  } finally {
    checkBusy = false;
    btn.disabled = false;
    btn.textContent = t("bar.check");
  }
}

document.getElementById("btn-check").addEventListener("click", doCheck);

// ----------------------------------------------------------------------
// Exercices (P5) : charger un exercice dans les éditeurs + afficher
// son énoncé. GET /api/exercises (liste) + GET /api/exercise?name=…
// ----------------------------------------------------------------------

const exerciseSelect = document.getElementById("exercise-select");
const enoncePanel = document.getElementById("enonce-panel");
const enonceTitle = document.getElementById("enonce-title");
const enonceText = document.getElementById("enonce-text");

// Écrir le texte dans un éditeur CodeMirror (dispatch d'un seul bloc).
function setEditorText(view, text) {
  view.dispatch({
    changes: { from: 0, to: view.state.doc.length, insert: text },
  });
}

async function loadExercisesList() {
  try {
    // i18n P10.1 : les titres des énoncés sont lus dans la langue
    // courante (le re-rendu de changement de langue rappelle cette
    // fonction — la sélection est conservée).
    const selected = exerciseSelect.value;
    const resp = await fetch("/api/exercises?lang=" + encodeURIComponent(i18nLang()));
    const data = await resp.json();
    if (!data.ok || !Array.isArray(data.exercises)) return;
    exerciseSelect.innerHTML = "";
    for (const ex of data.exercises) {
      const opt = document.createElement("option");
      opt.value = ex.name;
      opt.textContent = ex.title;
      opt.title = t("exercise.opt", ex.title, ex.files);
      exerciseSelect.appendChild(opt);
    }
    exerciseSelect.value = selected;
  } catch {
    // serveur injoignable : pas de liste, pas de faux message
  }
}

let exerciseBusy = false;

async function doLoadExercise() {
  const name = exerciseSelect.value;
  if (!name || exerciseBusy) return;
  exerciseBusy = true;
  const btn = document.getElementById("btn-load-exercise");
  btn.disabled = true;
  try {
    // i18n P10.1 : l'énoncé est servi dans la langue courante
    // (enonce.en.md s'il existe, sinon enonce.md).
    const resp = await fetch("/api/exercise?name=" + encodeURIComponent(name) +
      "&lang=" + encodeURIComponent(i18nLang()));
    const data = await resp.json();
    if (!data.ok) {
      const msg = (data.errors || [{}])[0].message || t("exercise.unreadable");
      window.alert(t("exercise.cannotLoad", msg));
      return;
    }
    // P9 : contexte de l'exercice pour le prompt de génération
    // (domaine = énoncé ; cohérence = règles) ; un nouvel exercice
    // remplace le contexte précédent, y compris « aucun ».
    loadedExercise = data.name;
    lastRender.exercise = data.name;   // re-fetch de l'énoncé au changement de langue
    currentEnonce = data.enonce || "";
    // Préchargement optionnel de la base URI.
    if (data.base_uri) baseUriInput.value = data.base_uri;
    // Remplir les éditeurs (dispatch → le linter re-parse tout seul).
    if (data.kb) setEditorText(editorView, data.kb);
    if (data.rules !== undefined) setEditorText(rulesView, data.rules);
    if (data.query) setEditorText(queryView, data.query);
    if (data.conclusion) {
      showProofTab("concl");
      setEditorText(conclView, data.conclusion);
    }
    // Afficher l'énoncé — P7 : rendu Markdown → HTML (converti côté
    // serveur ; le .md reste la source de vérité dans le dépôt).
    enonceTitle.textContent = data.title;
    if (data.enonce_html) {
      enonceText.innerHTML = data.enonce_html;
    } else {
      enonceText.textContent = data.enonce || t("exercise.emptyEnonce");
    }
    enoncePanel.hidden = false;
    enoncePanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    // Parse immédiat de la KB pour un retour visuel rapide.
    parseNow("kb");
    // Le graphe affiché montre l'ancien exercice : rafraîchir.
    refreshGraph();
  } catch (e) {
    window.alert(t("exercise.loadError", String(e)));
  } finally {
    exerciseBusy = false;
    btn.disabled = false;
    btn.textContent = t("bar.load");
  }
}

document.getElementById("btn-load-exercise").addEventListener("click", doLoadExercise);
loadExercisesList();

// ----------------------------------------------------------------------
// P9 — Génération de données par IA générative (proxy institutionnel)
// ----------------------------------------------------------------------
// Le texte généré arrive **dans l'éditeur** (visible, modifiable,
// supprimable) — jamais en base cachée ; une bannière « généré par
// IA, à vérifier » reste visible jusqu'à une édition manuelle. Le
// prompt est bâti sur l'exercice chargé (énoncé + règles) pour que
// les données générées s'appliquent aux règles existantes ; les
// contrôles a posteriori (parse, cohérence, plausibilité) et la
// régénération bornée se font côté serveur (ia.py) ; le quota de
// séance est compté côté backend (persisté avec le cache).

const iaBanner = document.getElementById("ia-banner");
const iaBannerText = document.getElementById("ia-banner-text");
const iaQuota = document.getElementById("ia-quota");
const iaMeta = document.getElementById("ia-meta");
const iaOutput = document.getElementById("ia-output");
let iaBusy = false;
let loadedExercise = null;   // nom de l'exercice chargé (contexte du prompt)
let currentEnonce = "";      // énoncé brut (Markdown) de l'exercice chargé
let iaBannerNote = null;     // note du modèle (re-localisable à changement
                             // de langue sans refaire la génération)

function showIaBanner(note) {
  iaBannerNote = note || null;
  iaBannerText.textContent = t("ia.bannerPrefix") +
    (note ? " — " + note : "") +
    t("ia.bannerSuffix");
  iaBanner.hidden = false;
}

function hideIaBanner() {
  iaBanner.hidden = true;
}

document.getElementById("ia-banner-close").addEventListener("click", hideIaBanner);

// Le quota de séance (backend) pilote l'état du bouton. Les messages
// du serveur (`reason`) sont localisés : le front envoie la langue
// courante (le backend les génère dans cette langue).
function setIaButton(s) {
  const btn = document.getElementById("btn-ia");
  const q = s.quota || {};
  const quotaText = t("ia.quota",
    q.requests_left != null ? q.requests_left : "?",
    q.tokens_left != null ? q.tokens_left : "?");
  if (!s.enabled || s.reason) {
    btn.disabled = true;
    btn.title = s.reason || t("ia.unconfigured");
    iaQuota.textContent = s.reason ? quotaText + " — " + s.reason : "";
    iaQuota.className = s.reason ? "ia-quota error" : "ia-quota";
    return;
  }
  btn.disabled = false;
  btn.title = t("ia.btnTitle");
  iaQuota.textContent = quotaText;
  iaQuota.className = "ia-quota";
}

async function loadIaStatus() {
  try {
    const resp = await fetch("/api/ia/status?lang=" + i18nLang());
    const s = await resp.json();
    setIaButton(s);
  } catch {
    // serveur injoignable : l'état du bouton reste tel quel
  }
}

// Libellés des contrôles (c.name : clés stables du backend).
const CTRL_KEY = { parse: "ia.ctrlParse",
                   coherence: "ia.ctrlCoherence",
                   plausibility: "ia.ctrlPlausibility",
                   // noms historiques (français) — robustesse
                   "cohérence": "ia.ctrlCoherence",
                   "plausibilité": "ia.ctrlPlausibility" };

function renderIa(data, tab = true) {
  lastRender.ia = data;
  iaMeta.textContent = [
    data.model ? t("ia.model", data.model) : "",
    data.attempts ? t("ia.attempt", data.attempts) : "",
    data.tokens ? t("ia.tokens", data.tokens) : "",
    data.elapsed_ms ? t("ia.elapsed", Math.round(data.elapsed_ms / 100) / 10) : "",
  ].filter(Boolean).join(" · ");
  const parts = [];
  if (data.ok) {
    parts.push(`<p class="ok">${t("ia.accepted", data.attempts)}</p>`);
    if (data.note) parts.push(`<p class="muted">${esc(data.note)}</p>`);
    const rows = (data.controls || []).map((c) => {
      let detail = "";
      if (c.warning) detail = " " + t("ia.warning", esc(c.warning));
      else if (c.name === "parse" && c.statements != null) detail = " " + t("ia.parseFacts", c.statements);
      else if ((c.name === "coherence" || c.name === "cohérence") && c.new_facts != null) detail = " " + t("ia.inferredFacts", c.new_facts);
      else if (c.name === "plausibility" || c.name === "plausibilité") detail = " " + t("ia.plausibility", c.facts, c.entities);
      else if (c.skipped) detail = " (" + esc(c.skipped) + ")";
      return `<li class="${c.ok ? "ok" : "error"}">${t(CTRL_KEY[c.name] || c.name)} : ${c.ok ? "✓" : "✗"}${detail}</li>`;
    }).join("");
    parts.push(`<ul>${rows}</ul>`);
    parts.push(`<p class="muted">${t("ia.acceptedNote")}</p>`);
  } else {
    parts.push(`<p class="error">✗ ${esc(data.error)}</p>`);
    const rows = (data.controls || []).filter((c) => !c.ok).map((c) =>
      `<li class="error">${t(CTRL_KEY[c.name] || c.name)} : ${esc(c.error || "")}</li>`).join("");
    if (rows) parts.push(`<ul>${rows}</ul>`);
  }
  iaOutput.innerHTML = parts.join("") || `<p class="muted">${t("empty")}</p>`;
  if (tab) switchTab("ia");
}

async function doIaGenerate() {
  if (iaBusy) return;
  iaBusy = true;
  const btn = document.getElementById("btn-ia");
  btn.disabled = true;
  const prevLabel = btn.textContent;
  btn.textContent = t("ia.busyBtn");
  iaOutput.innerHTML = `<p class="muted">${t("ia.busy")}</p>`;
  switchTab("ia");
  const body = {
    enonce: currentEnonce,
    rules: rulesView.state.doc.toString(),
    base_uri: baseUriInput.value.trim() || DEFAULT_BASE_URI,
    facts: parseInt(document.getElementById("ia-facts").value, 10) || 40,
    entities: parseInt(document.getElementById("ia-entities").value, 10) || 10,
    exercise: loadedExercise,
    timeout: 120,
    lang: i18nLang(),   // messages de l'IA (erreurs, contrôles) localisés
  };
  try {
    const resp = await fetch("/api/ia/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    renderIa(data);
    if (data.ok) {
      // Le texte généré arrive dans l'éditeur (dispatch → le linter
      // re-parse et le graphe se rafraîchit tout seul) ; la bannière
      // apparaît APRÈS (l'édition automatique la masquerait sinon).
      setEditorText(editorView, data.n3);
      showIaBanner(data.note);
    }
  } catch (e) {
    iaOutput.innerHTML = `<p class="error">${t("status.networkError", esc(String(e)))}</p>`;
  } finally {
    iaBusy = false;
    btn.textContent = prevLabel;
    // Le quota a changé (ou l'échec a un message à afficher) :
    // l'état du bouton vient du serveur.
    loadIaStatus();
  }
}

document.getElementById("btn-ia").addEventListener("click", doIaGenerate);

// ----------------------------------------------------------------------
// Graphe (P5, option vis.js vendue en local ; P7 : panneau persistant)
// ----------------------------------------------------------------------
// Le graphe des triples de la KB est **toujours visible** (colonne de
// droite) et se met à jour à chaque action : édition des données /
// règles, raisonnement, requête avec raisonnement, changement de la
// base URI, chargement d'exercice. Mode « attributs masqués » (P7) :
// les nœuds-littéraux sont remplacés par une pastille compteur sur le
// nœud (les attributs masqués sont listés dans la bulle contextuelle).

const graphMeta = document.getElementById("graph-meta");
const graphOutput = document.getElementById("graph-output");
const graphCanvas = document.getElementById("graph-canvas");
const graphBadges = document.getElementById("graph-badges");

let graphNetwork = null;
let graphBusy = false;
let graphRefreshPending = false;
let graphAttrs = {};      // P7 : id du nœud → [attributs masqués]

// Poignée de debug (console navigateur / tests automatisés) : le
// module est en scope fermée, sans quoi le réseau vis serait
// inatteignable.
window.__cwmLab = {
  graph: () => graphNetwork,
  focus: () => graphFocusSelection(),
};

// Couleurs par nature de nœud (légende identique dans le HTML) ;
// « inféré » = orange, commun aux trois natures.
const GRAPH_COLORS = {
  resource: { background: "#3b82f6", border: "#1d4ed8" },
  literal: { background: "#16a34a", border: "#166534" },
  blank: { background: "#94a3b8", border: "#475569" },
};
const GRAPH_INFERRED = { background: "#f59e0b", border: "#b45309" };

function destroyGraph() {
  if (graphNetwork) {
    graphNetwork.destroy();
    graphNetwork = null;
  }
  graphAttrs = {};
  graphBadges.innerHTML = "";
}

// Pastilles des attributs masqués (P7) : positionnées au-dessus de
// chaque nœud qui en porte — recalculées à chaque dessin du réseau
// (pan, zoom, physique), les pastilles suivent les nœuds ET leur
// échelle (elles grandissent au zoom, comme les nœuds du canvas).
function positionBadges() {
  graphBadges.innerHTML = "";
  if (!graphNetwork || !Object.keys(graphAttrs).length) return;
  const w = graphCanvas.clientWidth, h = graphCanvas.clientHeight;
  // getPosition renvoie les coordonnées **du réseau** (monde) ; la
  // pastille est un élément HTML positionné en coordonnées **écran**
  // (relatives au canvas). vis 10.x n'expose pas de canvasToScreen :
  // la vue est une homothétie + translation,
  //   écran = monde × scale + translation,
  // et getViewPosition() renvoie le point du monde situé au **centre**
  // du canvas — d'où translation = centre − position × scale.
  // Sans cette conversion, la pastille est décalée du nœud dès que
  // le graphe est recentré, zoomé ou pané.
  //
  // La pastille est traitée comme un élément dessiné **dans le monde**
  // du graphe : sa taille ET son décalage depuis le centre du nœud
  // sont multipliés par `scale` (comme le font les nœuds et les arcs
  // du canvas), elle grandit donc au zoom et reste collée au coin du
  // nœud à tout niveau de zoom.
  const scale = graphNetwork.getScale();
  const vp = graphNetwork.getViewPosition();
  const tx = w / 2 - vp.x * scale;
  const ty = h / 2 - vp.y * scale;
  for (const [id, items] of Object.entries(graphAttrs)) {
    // nœud masqué par le focus de sélection : pas de pastille flottante
    const nd = graphNetwork.body.data.nodes.get(id);
    if (nd && nd.hidden) continue;
    const pos = graphNetwork.getPosition(id);
    if (!pos) continue;
    const sx = pos.x * scale + tx;
    const sy = pos.y * scale + ty;
    // nœud détruit ou hors du canvas : pas de pastille flottante
    if (sx < 0 || sx > w || sy < 0 || sy > h) continue;
    const b = document.createElement("span");
    b.className = "attr-badge";
    b.textContent = items.length;
    b.title = items.join("\n");
    b.style.left = (sx + 12 * scale) + "px";
    b.style.top = (sy - 16 * scale) + "px";
    b.style.transform = "translate(-50%, -100%) scale(" + scale + ")";
    graphBadges.appendChild(b);
  }
}

// Texte du méta-graphe + message de troncature (re-localisables au
// changement de langue sans reconstruire le réseau vis — la vue de
// l'utilisateur, zoom/pan, est préservée).
function updateGraphMeta(data) {
  lastRender.graph = data;
  if (!data.ok) return;
  graphMeta.textContent = "— " + t("graph.statements", data.statement_count) +
    " · " + t("graph.nodes", data.nodes.length) +
    " · " + t("graph.edges", data.edges.length) +
    (data.truncated ? t("graph.truncated") : "") +
    ` · ${data.elapsed_ms} ms` +
    (data.cached ? " · " + t("meta.cache") : "");
  graphOutput.innerHTML = data.truncated
    ? `<p class="muted">${t("graph.truncatedMsg", data.statement_count)}</p>`
    : "";
}

// Facteurs vis.js — partagés avec le rafraîchissement des libellés
// (changement de langue : mêmes ids, seules les étiquettes changent,
// la vue de l'utilisateur est préservée).
function visNodeData(n) {
  const c = n.inferred ? GRAPH_INFERRED : GRAPH_COLORS[n.kind];
  return {
    id: n.id,
    label: n.label,
    title: n.title || n.id,
    shape: n.kind === "literal" ? "box" : "dot",
    size: n.kind === "resource" ? 14 : 11,
    color: { background: c.background, border: c.border,
             highlight: { background: "#fde68a", border: "#b45309" } },
    font: { color: "#1a2332", size: n.kind === "literal" ? 11 : 12 },
  };
}

function visEdgeData(e, i) {
  return {
    id: i,
    from: e.from,
    to: e.to,
    label: e.label,
    arrows: "to",
    color: { color: e.inferred ? "#f59e0b" : "#94a3b8",
             highlight: "#2563eb",
             hover: "#64748b" },
    font: { size: 10, color: "#475569", strokeWidth: 4, strokeColor: "#fff" },
  };
}

// Focus de sélection : un nœud sélectionné masque les nœuds qui ne le
// concernent pas — restent visibles le nœud, ses voisins directs
// (arcs dans les deux sens) et les arcs qui le relient. La
// désélection (clic sur le vide) réaffiche tout. Implémenté par
// `hidden` (patch du DataSet, pas suppression) : positions et vue de
// l'utilisateur sont préservées, et la mise à jour des libellés de
// langue (in place, par id) ne dé masque pas (le merge conserve
// `hidden`).
function graphFocusSelection() {
  if (!graphNetwork) return;
  const nodesDS = graphNetwork.body.data.nodes;
  const edgesDS = graphNetwork.body.data.edges;
  const selected = new Set(graphNetwork.getSelectedNodes());
  const visibleNodes = new Set(selected);
  const visibleEdges = new Set();
  if (selected.size) {
    edgesDS.get().forEach((e) => {
      if (selected.has(e.from) || selected.has(e.to)) {
        visibleNodes.add(e.from);
        visibleNodes.add(e.to);
        visibleEdges.add(e.id);
      }
    });
  }
  const on = selected.size > 0;
  nodesDS.update(nodesDS.get().map((n) =>
    ({ id: n.id, hidden: on && !visibleNodes.has(n.id) })));
  edgesDS.update(edgesDS.get().map((e) =>
    ({ id: e.id, hidden: on && !visibleEdges.has(e.id) })));
}

function renderGraph(data) {
  destroyGraph();
  graphAttrs = (data.ok && data.attrs) || {};
  if (!data.ok) {
    lastRender.graph = data;
    graphCanvas.hidden = true;
    graphMeta.textContent = "";
    const msg = (data.errors || [{}])
      .map((e) => e.message).filter(Boolean).join(" ; ") || t("graph.unknownError");
    graphOutput.innerHTML = `<p class="error">${esc(msg)}</p>`;
    return;
  }
  graphCanvas.hidden = false;
  const nodes = new vis.DataSet(data.nodes.map(visNodeData));
  const edges = new vis.DataSet(data.edges.map(visEdgeData));
  graphNetwork = new vis.Network(graphCanvas, { nodes, edges }, {
    physics: {
      solver: "forceAtlas2Based",
      forceAtlas2Based: { gravitationalConstant: -60, springLength: 120 },
    },
    interaction: { hover: true, tooltipDelay: 200 },
    nodes: { borderWidth: 2 },
    edges: { smooth: { type: "continuous" } },
  });
  // À chaque dessin du canvas, les pastilles suivent les nœuds
  // (le wrapper évite de transmettre la référence du contexte
  // d'événement à une fonction qui ne l'utilise pas).
  graphNetwork.on("afterDrawing", () => positionBadges());
  // Focus de sélection : sélection → masque les nœuds sans rapport ;
  // désélection (dont clic sur le vide) → tout redevient visible
  // (cf. graphFocusSelection). Ces événements ne firent que sur
  // interaction utilisateur (pas sur selectNodes() programmatique).
  graphNetwork.on("selectNode", () => graphFocusSelection());
  graphNetwork.on("deselectNode", () => graphFocusSelection());
  updateGraphMeta(data);
}

// Récupère le graphe (POST /api/graph) — le panneau est persistant
// (P7), d'où le rafraîchissement automatique à chaque action.
async function fetchGraphData(reason, hide) {
  // Les options de raisonnement (mode, timeout) sont celles de la
  // barre commune — identiques pour « Raisonner » et « Interroger ».
  const body = {
    kb: editorView.state.doc.toString(),
    rules: rulesView.state.doc.toString(),
    base_uri: baseUriInput.value.trim() || DEFAULT_BASE_URI,
    reason,
    mode: document.getElementById("infer-mode").value,
    timeout: parseFloat(document.getElementById("infer-timeout").value) || 0,
    hide_literals: hide,
    lang: i18nLang(),   // i18n P10.1 : libellés d'ontologie dans la langue courante
  };
  const resp = await fetch("/api/graph", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return resp.json();
}

// Rafraîchit le graphe (panneau persistant — toujours visible). Si un
// rendu est déjà en cours, un nouveau rafraîchissement est planifié
// (le dernier état l'emporte).
async function refreshGraph() {
  if (graphBusy) {
    graphRefreshPending = true;
    return;
  }
  graphBusy = true;
  try {
    const reason = document.getElementById("graph-reason").checked;
    const hide = document.getElementById("graph-hide-literals").checked;
    const data = await fetchGraphData(reason, hide);
    renderGraph(data);
  } catch (e) {
    // le graphe reste affiché tel quel ; l'erreur réseau est signalée
    graphOutput.innerHTML = `<p class="error">${t("graph.networkError", esc(String(e)))}</p>`;
  } finally {
    graphBusy = false;
    if (graphRefreshPending) {
      graphRefreshPending = false;
      refreshGraph();
    }
  }
}

document.getElementById("graph-reason").addEventListener("change",
  refreshGraph);
document.getElementById("graph-hide-literals").addEventListener("change",
  refreshGraph);

// i18n P10.1 : au changement de langue, les libellés d'ontologie du
// graphe (nœuds-ressources, prédicats d'arcs, attributs masqués) sont
// choisis dans la nouvelle langue — re-fetch, puis mise à jour EN
// PLACE des DataSets vis (mêmes ids : la vue de l'utilisateur,
// positions comprises, est préservée).
async function refreshGraphLabels() {
  if (!graphNetwork) return;
  const reason = document.getElementById("graph-reason").checked;
  const hide = document.getElementById("graph-hide-literals").checked;
  let data;
  try {
    data = await fetchGraphData(reason, hide);
  } catch (e) {
    return;   // le graphe reste affiché tel quel
  }
  lastRender.graph = data;
  if (!data.ok) {
    updateGraphMeta(data);
    return;
  }
  graphAttrs = data.attrs || {};
  // vis.js garde les DataSets dans `body.data` : on met à jour EN
  // PLACE par id — les positions (x/y) des nœuds existants sont
  // préservées, seules les étiquettes changent. Au changement de
  // langue l'ensemble des nœuds/arcs est identique (même KB), donc
  // `update` suffit (ajoute les ids nouveaux, ne supprime rien).
  graphNetwork.body.data.nodes.update(data.nodes.map(visNodeData));
  graphNetwork.body.data.edges.update(data.edges.map(visEdgeData));
  updateGraphMeta(data);
  positionBadges();
}

// ----------------------------------------------------------------------
// P7.1 : poignée de redimensionnement des colonnes
// ----------------------------------------------------------------------
// Les pistes du grid sont `minmax(0, …)` : le contenu (une preuve de
// 50 lignes, un long tableau) ne peut PAS élargir sa colonne — la
// largeur des colonnes ne change que par glissement de la poignée.
// La largeur relative choisie (25–75 %) est persistée (localStorage)
// et se retrouve à la séance suivante.
const layout = document.getElementById("layout");
const resizer = document.getElementById("col-resizer");
const LEFT_COL_KEY = "cwm-tp-left-col";

function applyLeftCol(pct) {
  layout.style.setProperty("--left-col", pct + "%");
}
// la valeur stockée est un nombre (sans « % ») — applyLeftCol l'ajoute
const savedLeft = parseFloat(localStorage.getItem(LEFT_COL_KEY));
if (Number.isFinite(savedLeft)) applyLeftCol(savedLeft);

let resizing = false;
resizer.addEventListener("pointerdown", (e) => {
  resizing = true;
  resizer.classList.add("dragging");
  document.body.classList.add("col-resizing");   // user-select off,
  resizer.setPointerCapture(e.pointerId);        // pas d'événement
  e.preventDefault();                            // volés par les éditeurs
});
resizer.addEventListener("pointermove", (e) => {
  if (!resizing) return;
  const rect = layout.getBoundingClientRect();
  let pct = ((e.clientX - rect.left) / rect.width) * 100;
  applyLeftCol(Math.max(25, Math.min(75, pct)).toFixed(1));
  // le canvas vis-network suit le redimensionnement avec retard ;
  // redraw() est coalescé côté vis (1 par frame) : le graphe ne
  // déborde pas de sa colonne pendant le glissement
  if (graphNetwork) graphNetwork.redraw();
});
resizer.addEventListener("pointerup", () => {
  if (!resizing) return;
  resizing = false;
  resizer.classList.remove("dragging");
  document.body.classList.remove("col-resizing");
  const cur = layout.style.getPropertyValue("--left-col").match(/[\d.]+/);
  if (cur) localStorage.setItem(LEFT_COL_KEY, cur[0]);
  if (graphNetwork) graphNetwork.redraw();   // recadre le canvas
});

// Colophon : la version vient du serveur (source unique :
// lab.lab_web.__version__), le reste est statique dans le HTML.
fetch("/api/version")
  .then((r) => r.json())
  .then((d) => {
    const el = document.getElementById("version");
    if (el && d.version) el.textContent = d.version;
  })
  .catch(() => {});

// Aide : popup des boutons et cases (bouton « ? » de la barre
// d'état). Contenu statique en data-i18n — i18n.js le (re)traduit
// à chaque changement de langue, ouvert ou fermé que soit le popup.
const helpOverlay = document.getElementById("help-overlay");
const btnHelp = document.getElementById("btn-help");
const helpClose = document.getElementById("help-close");
function closeHelp() {
  if (helpOverlay.hidden) return;
  helpOverlay.hidden = true;
  btnHelp.focus();
}
btnHelp.addEventListener("click", () => {
  helpOverlay.hidden = false;
  helpClose.focus();
});
helpClose.addEventListener("click", closeHelp);
helpOverlay.addEventListener("click", (e) => {
  if (e.target === helpOverlay) closeHelp();   // clic sur le fond
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeHelp();
});

// ----------------------------------------------------------------------
// i18n : changement de langue → re-rendu des résultats existants
// ----------------------------------------------------------------------
// Les chaînes statiques (entête, onglets, bannière par défaut…) sont
// traitées par i18n.js (attributs data-i18n). Ici, on re-rend les
// contenus DYNAMIQUES (dernier état de chaque action) dans la nouvelle
// langue — sans forcer d'onglet, sans reconstruire le graphe (la vue
// de l'utilisateur est préservée), sans ré-écrire la preuve (une
// altération manuelle n'est pas écrasée), sans toucher les éditeurs.
//
// i18n P10.1 — les contenus dont les LIBELLÉS d'ontologie dépendent
// de la langue (nouveaux faits, lignes de requête, nœuds/arcs du
// graphe, énoncés, titres du menu) sont choisis côté backend : ils
// sont re-fetchés dans la nouvelle langue, puis re-rendus à la même
// place (sans forcer d'onglet). Un échec réseau garde le rendu
// précédent.
async function refreshInferResults() {
  try {
    const resp = await fetch("/api/infer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(inferBody()),
    });
    renderInfer(await resp.json(), false);
  } catch (e) { /* le rendu précédent reste affiché */ }
}

async function refreshQueryResults() {
  // La requête d'origine était-elle « avec raisonnement » ?
  // (rows_reasoned n'est absent que dans ce cas.)
  const reason = lastRender.query.rows_reasoned != null;
  try {
    const resp = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(queryBody(reason)),
    });
    renderQuery(await resp.json(), false);
  } catch (e) { /* le rendu précédent reste affiché */ }
}

async function refreshEnonce() {
  const name = lastRender.exercise;
  try {
    const resp = await fetch("/api/exercise?name=" + encodeURIComponent(name) +
      "&lang=" + encodeURIComponent(i18nLang()));
    const data = await resp.json();
    if (!data.ok) return;
    // Énoncé du prompt IA (P9) et panneau — sans toucher les éditeurs
    // (le travail de l'étudiant n'est jamais écrasé).
    currentEnonce = data.enonce || "";
    enonceTitle.textContent = data.title;
    if (data.enonce_html) enonceText.innerHTML = data.enonce_html;
    else enonceText.textContent = data.enonce || t("exercise.emptyEnonce");
  } catch (e) { /* le panneau garde l'énoncé précédent */ }
}

function reRenderAll() {
  if (lastRender.parse) renderResults(lastRender.parse.data, lastRender.parse.which, false);
  // Libellés d'ontologie dans la langue : re-fetch (pas de re-rendu
  // local — les chaînes de données ont changé de langue).
  if (lastRender.infer) refreshInferResults();
  if (lastRender.query) refreshQueryResults();
  if (lastRender.entail) renderEntail(lastRender.entail, false);
  if (lastRender.prove) renderProve(lastRender.prove, false);
  if (lastRender.check) renderCheck(lastRender.check, false);
  if (lastRender.ia) renderIa(lastRender.ia, false);
  if (lastRender.graph && graphNetwork) refreshGraphLabels();
  else if (lastRender.graph) updateGraphMeta(lastRender.graph);
  // Énoncés + titres du menu : servis dans la nouvelle langue.
  if (lastRender.exercise) refreshEnonce();
  loadExercisesList();
  if (lastRender.exportFormat) {
    exportFormat.textContent = "→ " + EXPORT_LABEL[lastRender.exportFormat];
  }
  if (!iaBanner.hidden) showIaBanner(iaBannerNote);
  // Boutons pilotés par JS : libellé localisé par défaut (seulement
  // si l'action n'est pas en cours — un libellé « … » est en place).
  for (const [id, key] of [
    ["btn-infer", "bar.infer"], ["btn-query", "bar.query"],
    ["btn-entail", "bar.entail"], ["btn-why", "bar.why"],
    ["btn-check", "bar.check"], ["btn-load-exercise", "bar.load"],
  ]) {
    const btn = document.getElementById(id);
    if (btn && !btn.disabled) btn.textContent = t(key);
  }
  // État du bouton IA : la raison du serveur est localisée (le front
  // renvoie la langue courante).
  loadIaStatus();
}
onLangChange(reRenderAll);

// Premier parse à l'ouverture + premier rendu du graphe (P7 : il est
// visible d'emblée, sur les données préchargées) + état du bouton
// IA (P9 : activé / désactivé selon la config, quota restant).
parseNow("kb");
refreshGraph();
loadIaStatus();
