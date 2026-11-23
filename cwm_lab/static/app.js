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

const TABS = ["parse", "infer", "query", "entail", "proof", "export"];
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
const editorLabels = { kb: "document", rules: "règles", query: "requête",
                       concl: "conclusion", proof: "preuve" };

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
  setStatus("parse en cours…");
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
    setStatus("erreur réseau : " + e, "error");
  }
}

function renderResults(data, which) {
  which = which || activeEditor;
  const label = editorLabels[which];
  if (!data.ok) {
    setStatus("erreur de syntaxe", "error");
    const items = (data.errors || []).map((er) =>
      `<li class="error">ligne ${er.line}, col. ${er.column} — ${esc(er.message)}</li>`
    ).join("");
    results.innerHTML = `<p class="error">Éditeur « ${label} » : erreur de syntaxe.</p>
      <ul class="errors">${items}</ul>`;
    markTab("parse");
    return;
  }
  const st = data.stats;
  setStatus("OK" + (data.cached ? " (cache)" : ""));
  if (which === "query") {
    // Stats SPARQL : type de requête + variables de la clause SELECT.
    results.innerHTML = `
    <p class="ok">Éditeur « ${label} » : requête valide.</p>
    <ul class="stats">
      <li>type : <b>${esc(st.queryType || "inconnue")}</b></li>
      <li>variables : ${st.variables.length
        ? st.variables.map((v) => `<code>?${esc(v)}</code>`).join(" ")
        : "— (SELECT * ou ASK)"}</li>
    </ul>`;
    return;
  }
  results.innerHTML = `
    <p class="ok">Éditeur « ${label} » : valide.</p>
    <ul class="stats">
      <li><b>${st.statements}</b> énoncé(s)</li>
      <li><b>${st.rules}</b> règle(s) <code>log:implies</code></li>
      <li><b>${st.blankNodes}</b> nœud(s) vide(s)</li>
    </ul>`;
  markTab("parse");
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
      exportOutput.textContent = data.output || "(document vide)";
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
    exportOutput.textContent = "erreur réseau : " + e;
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

function renderInfer(data) {
  const parts = [];

  if (!data.ok && !data.timeout) {
    // erreurs de parse (taguées par éditeur)
    const items = (data.errors || []).map((er) =>
      `<li class="error">${er.doc === "rules" ? "règles" : "données"} — ` +
      `ligne ${er.line}, col. ${er.column} : ${esc(er.message)}</li>`
    ).join("");
    parts.push(`<ul class="errors">${items}</ul>`);
    inferMeta.textContent = "";
  } else {
    const bits = [];
    bits.push(data.new_facts.length + " fait(s) nouveau(x)");
    bits.push(data.closure_statements + " énoncé(s) dans la clôture");
    if (data.rules_in_closure) bits.push(data.rules_in_closure + " règle(s) stockée(s)");
    bits.push(data.elapsed_ms + " ms");
    if (data.cached) bits.push("cache");
    inferMeta.textContent = bits.join(" · ");

    if (data.timeout) {
      parts.push(`<p class="banner banner-timeout">⏱ ${
        esc((data.errors || [])[0] && (data.errors[0].message) || "timeout")
      } — le raisonnement a été interrompu, la page reste utilisable.</p>`);
    }
    if (data.inconsistent) {
      parts.push(`<p class="banner banner-error">⚠ <b>Incohérent</b> : la clôture ` +
        `contient la constante <code>log:false</code> (une règle aboutit à une ` +
        `contradiction).</p>`);
    }
    if (data.new_facts.length) {
      parts.push(`<p class="muted">Nouveaux faits (absents des données d'origine) :</p>` +
        `<ul class="new-facts">` +
        data.new_facts.map((t) => `<li>${fmtTriple(t)}</li>`).join("") +
        `</ul>`);
    } else if (!data.timeout) {
      parts.push(`<p class="muted">Aucun nouveau fait : la clôture est identique ` +
        `aux données (les règles ne s'appliquent pas, ou ont déjà convergé).</p>`);
    }
  }
  inferOutput.innerHTML = parts.join("") || `<p class="muted">(vide)</p>`;
  switchTab("infer");
}

let inferBusy = false;

async function doInfer() {
  if (inferBusy) return;
  inferBusy = true;
  const btn = document.getElementById("btn-infer");
  btn.disabled = true;
  btn.textContent = "raisonnement…";
  inferOutput.innerHTML = `<p class="muted">Raisonnement en cours… ` +
    `(une règle non convergente est interrompue au timeout).</p>`;
  const body = {
    kb: editorView.state.doc.toString(),
    rules: rulesView.state.doc.toString(),
    base_uri: baseUriInput.value.trim() || DEFAULT_BASE_URI,
    mode: document.getElementById("infer-mode").value,
    store_rules: document.getElementById("infer-store-rules").checked,
    timeout: parseFloat(document.getElementById("infer-timeout").value) || 0,
  };
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
    inferOutput.innerHTML = `<p class="error">erreur réseau : ${esc(String(e))}</p>`;
  } finally {
    inferBusy = false;
    btn.disabled = false;
    btn.textContent = "Raisonner";
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
  if (!rows.length) return `<p class="muted">(0 ligne)</p>`;
  const head = "<tr>" + variables.map((v) => `<th>?${esc(v)}</th>`).join("") + "</tr>";
  const newSet = new Set((newRows || []).map((r) => r.join("\u0000")));
  const body = rows.map((r) => {
    const isNew = newSet.has(r.join("\u0000"));
    return `<tr class="${isNew ? "row-new" : ""}"` +
      (isNew ? ` title="ligne nouvelle : produite par le raisonnement"` : "") +
      `>` + r.map((c) => `<td>${esc(c)}</td>`).join("") + "</tr>";
  }).join("");
  return `<table class="query-table"><thead>${head}</thead><tbody>${body}</tbody></table>`;
}

const askText = (v) => (v ? "vrai" : "faux");

function renderQuery(data) {
  const parts = [];

  if (!data.ok && !data.timeout) {
    // erreurs (taguées par éditeur : kb / rules / query)
    const label = { kb: "données", rules: "règles", query: "requête" };
    const items = (data.errors || []).map((er) =>
      `<li class="error">${label[er.doc] || er.doc} — ligne ${er.line}, ` +
      `col. ${er.column} : ${esc(er.message)}</li>`
    ).join("");
    parts.push(`<ul class="errors">${items}</ul>`);
    queryMeta.textContent = "";
  } else {
    const bits = [];
    if (data.query_type === "AskQuery") {
      bits.push("ASK : " + askText(data.ask_raw));
      if (data.rows_reasoned) bits.push("après raisonnement : " + askText(data.ask_reasoned));
    } else {
      bits.push(data.rows_raw.length + " ligne(s) sur les données brutes");
      if (data.rows_reasoned) bits.push(
        data.rows_reasoned.length + " ligne(s) après raisonnement, dont " +
        data.new_rows.length + " nouvelle(s)");
    }
    if (data.closure_statements != null) bits.push(data.closure_statements + " énoncé(s) dans la clôture");
    bits.push(data.elapsed_ms + " ms");
    if (data.cached) bits.push("cache");
    queryMeta.textContent = bits.join(" · ");

    if (data.timeout) {
      parts.push(`<p class="banner banner-timeout">⏱ ${
        esc((data.errors || [])[0] && (data.errors[0].message) || "timeout")
      } — la clôture a été interrompue ; seuls les résultats bruts sont affichés.</p>`);
    }
    if (data.query_type === "AskQuery") {
      parts.push(`<p class="banner ${data.ask_raw ? "banner-ok" : "banner-muted"}">` +
        `ASK sur les données brutes : <b>${askText(data.ask_raw)}</b></p>`);
      if (data.rows_reasoned) {
        parts.push(`<p class="banner ${data.ask_reasoned ? "banner-ok" : "banner-muted"}">` +
          `ASK après raisonnement : <b>${askText(data.ask_reasoned)}</b>` +
          (data.ask_reasoned !== data.ask_raw
            ? ` <span class="muted">(le raisonnement a changé la réponse)</span>` : "") +
          `</p>`);
      }
    } else if (!data.rows_reasoned) {
      parts.push(`<h3>Résultats (données brutes)</h3>` +
        queryTable(data.variables, data.rows_raw));
    } else {
      parts.push(`<h3>Données brutes</h3>` +
        queryTable(data.variables, data.rows_raw));
      parts.push(`<h3>Après raisonnement <span class="muted">(lignes nouvelles surlignées)</span></h3>` +
        queryTable(data.variables, data.rows_reasoned, data.new_rows));
    }
  }
  queryOutput.innerHTML = parts.join("") || `<p class="muted">(vide)</p>`;
  switchTab("query");
}

let queryBusy = false;

async function doQuery() {
  if (queryBusy) return;
  queryBusy = true;
  const btn = document.getElementById("btn-query");
  btn.disabled = true;
  btn.textContent = "requête…";
  const reason = document.getElementById("query-reason").checked;
  queryOutput.innerHTML = `<p class="muted">Requête en cours…` +
    (reason
      ? ` (clôture d'abord — une règle non convergente est interrompue au timeout).</p>`
      : `.</p>`);
  // Les options de raisonnement (mode, règles stockées, timeout) sont
  // celles de la barre commune — identiques pour « Raisonner » et pour
  // « Interroger » avec raisonnement.
  const body = {
    kb: editorView.state.doc.toString(),
    rules: rulesView.state.doc.toString(),
    query: queryView.state.doc.toString(),
    base_uri: baseUriInput.value.trim() || DEFAULT_BASE_URI,
    reason,
    mode: document.getElementById("infer-mode").value,
    store_rules: document.getElementById("infer-store-rules").checked,
    timeout: parseFloat(document.getElementById("infer-timeout").value) || 0,
  };
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
    queryOutput.innerHTML = `<p class="error">erreur réseau : ${esc(String(e))}</p>`;
  } finally {
    queryBusy = false;
    btn.disabled = false;
    btn.textContent = "Interroger";
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

// Libellés des éditeurs taguant les erreurs (kb / rules / query /
// concl / proof).
const DOC_LABEL = { kb: "données", rules: "règles", query: "requête",
                    concl: "conclusion", proof: "preuve" };

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
  return `<details class="proof-steps"><summary>Étapes de dérivation (${steps.length})</summary>
    <ol class="proof-steps-list">` +
    steps.map((s) =>
      `<li><code>${esc(s.statement || "…")}</code>` +
      (s.how ? `<div class="step-how">${esc(s.how)}</div>` : "") +
      `</li>`).join("") +
    `</ol></details>`;
}

function renderEntail(data) {
  const parts = [];
  if (!data.ok && !data.timeout) {
    const items = (data.errors || []).map((er) =>
      `<li class="error">${DOC_LABEL[er.doc] || er.doc} — ligne ${er.line}, ` +
      `col. ${er.column} : ${esc(er.message)}</li>`).join("");
    parts.push(`<ul class="errors">${items}</ul>`);
    entailMeta.textContent = "";
  } else {
    const bits = [];
    bits.push(data.closure_statements + " énoncé(s) dans la clôture");
    bits.push(data.elapsed_ms + " ms");
    if (data.cached) bits.push("cache");
    entailMeta.textContent = bits.join(" · ");
    if (data.timeout) {
      parts.push(`<p class="banner banner-timeout">⏱ ${
        esc((data.errors || [])[0] && data.errors[0].message || "timeout")
      } — le raisonnement a été interrompu ; la conclusion n'a pas pu être testée.</p>`);
    } else if (data.entails) {
      parts.push(`<p class="banner banner-ok">✔ <b>Oui</b> : la clôture ` +
        `(données + règles appliquées) <b>entraîne</b> la conclusion.</p>`);
    } else {
      parts.push(`<p class="banner banner-muted">✘ <b>Non</b> : la clôture ne ` +
        `contient pas la conclusion — aucune dérivaison ne la produit.</p>`);
    }
    if (data.inconsistent && data.entails) {
      parts.push(`<p class="banner banner-error">⚠ La clôture est <b>incohérente</b> ` +
        `(<code>log:false</code>) : par explosion, <i>toute</i> conclusion y est ` +
        `« entraînée » — le oui ci-dessus n'a pas de valeur.</p>`);
    }
  }
  entailOutput.innerHTML = parts.join("") || `<p class="muted">(vide)</p>`;
  switchTab("entail");
}

let entailBusy = false;

async function doEntail() {
  if (entailBusy) return;
  entailBusy = true;
  const btn = document.getElementById("btn-entail");
  btn.disabled = true;
  btn.textContent = "test…";
  entailOutput.innerHTML = `<p class="muted">Entraînement en cours… ` +
    `(clôture d'abord — une règle non convergente est interrompue au timeout).</p>`;
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
    entailOutput.innerHTML = `<p class="error">erreur réseau : ${esc(String(e))}</p>`;
  } finally {
    entailBusy = false;
    btn.disabled = false;
    btn.textContent = "Entraîne ?";
  }
}

document.getElementById("btn-entail").addEventListener("click", doEntail);

function renderProve(data) {
  const parts = [];
  if (!data.ok && !data.timeout) {
    const items = (data.errors || []).map((er) =>
      `<li class="error">${DOC_LABEL[er.doc] || er.doc} — ligne ${er.line}, ` +
      `col. ${er.column} : ${esc(er.message)}</li>`).join("");
    parts.push(`<ul class="errors">${items}</ul>`);
    proofMeta.textContent = "";
  } else if (data.timeout) {
    parts.push(`<p class="banner banner-timeout">⏱ ${
      esc((data.errors || [])[0] && data.errors[0].message || "timeout")
    } — la preuve n'a pas pu être générée.</p>`);
    proofMeta.textContent = "";
  } else {
    const bits = [data.closure_statements + " énoncé(s) dans la clôture",
                  data.elapsed_ms + " ms"];
    if (data.cached) bits.push("cache");
    proofMeta.textContent = bits.join(" · ");
    parts.push(`<p class="banner banner-ok">✔ Preuve générée : la clôture ` +
      `(données + règles) est la formule prouvée. Elle est dans l'onglet ` +
      `<b>Preuve</b> — <b>altérez-la à la main</b> (un prédicat, une étape, ` +
      `une source…), puis cliquez sur « Vérifier la preuve ».</p>`);
    showProofTab("proof");
    proofView.dispatch({
      changes: { from: 0, to: proofView.state.doc.length, insert: data.proof },
    });
  }
  proofOutput.innerHTML = parts.join("") || `<p class="muted">(vide)</p>`;
  switchTab("proof");
}

let whyBusy = false;

async function doWhy() {
  if (whyBusy) return;
  whyBusy = true;
  const btn = document.getElementById("btn-why");
  btn.disabled = true;
  btn.textContent = "génération…";
  proofOutput.innerHTML = `<p class="muted">Génération de la preuve… ` +
    `(clôture d'abord — une règle non convergente est interrompue au timeout).</p>`;
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
    proofOutput.innerHTML = `<p class="error">erreur réseau : ${esc(String(e))}</p>`;
  } finally {
    whyBusy = false;
    btn.disabled = false;
    btn.textContent = "Pourquoi ?";
  }
}

document.getElementById("btn-why").addEventListener("click", doWhy);

function renderCheck(data) {
  const parts = [];
  if (!data.ok) {
    const items = (data.errors || []).map((er) =>
      `<li class="error">${esc(er.message)}</li>`).join("");
    parts.push(`<ul class="errors">${items}</ul>`);
    proofMeta.textContent = "";
  } else {
    const bits = [];
    bits.push(data.steps.length + " étape(s) de dérivation");
    bits.push(data.elapsed_ms + " ms");
    if (data.cached) bits.push("cache");
    proofMeta.textContent = bits.join(" · ");
    if (data.valid) {
      parts.push(`<p class="banner banner-ok">✔ <b>Preuve valide</b> : la ` +
        `dérivation est re-jouée sans erreur — la formule prouvée suit bien ` +
        `des sources, par les règles.</p>`);
    } else if (data.valid === false) {
      parts.push(`<p class="banner banner-error">✘ <b>Preuve invalide</b> : ` +
        `la dérivation ne se re-joue pas. Raison : ` +
        `<code>${esc(data.reason || "inconnue")}</code></p>`);
    }
    if (data.valid === false && data.steps.length) {
      parts.push(`<p class="muted">Étapes (déroulées avant l'échec — en cas ` +
        `d'altération, c'est là qu'on voit le point de rupture) :</p>`);
    }
  }
  parts.push(stepsList(data.steps));
  proofOutput.innerHTML = parts.join("") || `<p class="muted">(vide)</p>`;
  switchTab("proof");
}

let checkBusy = false;

async function doCheck() {
  if (checkBusy) return;
  checkBusy = true;
  const btn = document.getElementById("btn-check");
  btn.disabled = true;
  btn.textContent = "vérification…";
  proofOutput.innerHTML = `<p class="muted">Vérification en cours… ` +
    `(check rejoue la dérivation dans un processus dédié).</p>`;
  try {
    const resp = await fetch("/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ proof: proofView.state.doc.toString() }),
    });
    renderCheck(await resp.json());
  } catch (e) {
    proofOutput.innerHTML = `<p class="error">erreur réseau : ${esc(String(e))}</p>`;
  } finally {
    checkBusy = false;
    btn.disabled = false;
    btn.textContent = "Vérifier la preuve";
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
    const resp = await fetch("/api/exercises");
    const data = await resp.json();
    if (!data.ok || !Array.isArray(data.exercises)) return;
    for (const ex of data.exercises) {
      const opt = document.createElement("option");
      opt.value = ex.name;
      opt.textContent = ex.title;
      opt.title = ex.title + " (" + ex.files + " fichier(s) .n3)";
      exerciseSelect.appendChild(opt);
    }
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
    const resp = await fetch("/api/exercise?name=" + encodeURIComponent(name));
    const data = await resp.json();
    if (!data.ok) {
      const msg = (data.errors || [{}])[0].message || "exercice illisible";
      window.alert("Impossible de charger l'exercice : " + msg);
      return;
    }
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
      enonceText.textContent = data.enonce || "(énoncé vide)";
    }
    enoncePanel.hidden = false;
    enoncePanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    // Parse immédiat de la KB pour un retour visuel rapide.
    parseNow("kb");
    // Le graphe affiché montre l'ancien exercice : rafraîchir.
    refreshGraph();
  } catch (e) {
    window.alert("Erreur réseau lors du chargement : " + String(e));
  } finally {
    exerciseBusy = false;
    btn.disabled = false;
  }
}

document.getElementById("btn-load-exercise").addEventListener("click", doLoadExercise);
loadExercisesList();

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
// (pan, zoom, physique), les pastilles suivent les nœuds.
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
  const scale = graphNetwork.getScale();
  const vp = graphNetwork.getViewPosition();
  const tx = w / 2 - vp.x * scale;
  const ty = h / 2 - vp.y * scale;
  for (const [id, items] of Object.entries(graphAttrs)) {
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
    b.style.left = (sx + 12) + "px";
    b.style.top = (sy - 16) + "px";
    graphBadges.appendChild(b);
  }
}

function renderGraph(data) {
  destroyGraph();
  graphAttrs = (data.ok && data.attrs) || {};
  if (!data.ok) {
    graphCanvas.hidden = true;
    graphMeta.textContent = "";
    const msg = (data.errors || [{}])
      .map((e) => e.message).filter(Boolean).join(" ; ") || "erreur inconnue";
    graphOutput.innerHTML = `<p class="error">${esc(msg)}</p>`;
    return;
  }
  graphCanvas.hidden = false;
  const nodes = new vis.DataSet(data.nodes.map((n) => {
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
  }));
  const edges = new vis.DataSet(data.edges.map((e, i) => ({
    id: i,
    from: e.from,
    to: e.to,
    label: e.label,
    arrows: "to",
    color: { color: e.inferred ? "#f59e0b" : "#94a3b8",
             highlight: "#2563eb",
             hover: "#64748b" },
    font: { size: 10, color: "#475569", strokeWidth: 4, strokeColor: "#fff" },
  })));
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
  graphMeta.textContent = `— ${data.statement_count} énoncé(s) · ` +
    `${data.nodes.length} nœud(s) · ${data.edges.length} arc(s)` +
    (data.truncated ? " (tronqué)" : "") + ` · ${data.elapsed_ms} ms` +
    (data.cached ? " · cache" : "");
  graphOutput.innerHTML = data.truncated
    ? `<p class="muted">Graphe tronqué (trop d'énoncés pour rester lisible) : ${data.statement_count} affichés.</p>`
    : "";
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
    graphOutput.innerHTML = `<p class="error">Erreur réseau : ${esc(String(e))}</p>`;
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

// Premier parse à l'ouverture + premier rendu du graphe (P7 : il est
// visible d'emblée, sur les données préchargées).
parseNow("kb");
refreshGraph();
