"use strict";
// SANAD renderer — talks to the local Core over HTTP. No data is hardcoded;
// every list below reflects what the Core actually holds.

const CORE = (window.sanadShell && window.sanadShell.coreUrl) || "http://127.0.0.1:23890";
const TOKEN = (window.sanadShell && window.sanadShell.token) || "";

async function api(path, opts) {
  const headers = { "Content-Type": "application/json" };
  if (TOKEN) headers["Authorization"] = "Bearer " + TOKEN;
  const r = await fetch(CORE + path, { headers, ...opts });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.status === 204 ? null : r.json();
}

const $ = (id) => document.getElementById(id);
let toastTimer = null;
function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2400);
}
function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function itemLabel(t) { return ({ "article-journal": "Journal", book: "Book", chapter: "Chapter", report: "Report", webpage: "Web" }[t] || t || "—"); }

const NEUTRAL_RIS = `TY  - BOOK
AU  - Fisher, R. K.
TI  - The Art of Memory
PY  - 2001
PB  - Chandler Press
ER  -
TY  - JOUR
AU  - Nguyen, Linh
AU  - Ortega, Pablo M.
TI  - A framework for distributed caching
T2  - Journal of Systems Engineering
PY  - 2016
VL  - 262
SP  - 101
EP  - 111
DO  - 10.1234/jse.2016.014
ER  -
TY  - JOUR
AU  - Reed, Sarah
AU  - Shaw, Thomas
AU  - Patel, Rina
AU  - Osei, Kwame
AU  - Lindqvist, Mika
AU  - Ibarra, Jose
AU  - Tanaka, Hiro
TI  - A survey of distributed ledger systems
PY  - 2020
ER  -
`;

// --- navigation ------------------------------------------------------------ //
function go(id) {
  document.querySelectorAll(".nav").forEach((n) => n.classList.toggle("active", n.getAttribute("data-screen") === id));
  document.querySelectorAll(".screen").forEach((s) => (s.hidden = s.id !== id));
  if (id === "library") loadLibrary();
  if (id === "style") loadStyles();
}
document.querySelectorAll("[data-screen]").forEach((b) => b.addEventListener("click", () => go(b.getAttribute("data-screen"))));

// --- Core health (live status) --------------------------------------------- //
async function pollHealth() {
  try {
    const h = await api("/v1/health");
    $("coreStatus").className = "live on";
    $("coreStatusText").textContent = "Working locally";
    $("coreVersion").textContent = "v" + (h.version || "");
    $("coreCard").className = "corecard on";
    $("coreCardState").textContent = "running · library + integrity engine";
    $("aboutVer").textContent = h.version || "—";
    $("setCoreState").textContent = "running";
  } catch {
    $("coreStatus").className = "live off";
    $("coreStatusText").textContent = "Core not reachable";
    $("coreCard").className = "corecard";
    $("coreCardState").textContent = "not connected";
    $("setCoreState").textContent = "not connected";
  }
}

// --- library --------------------------------------------------------------- //
async function loadLibrary() {
  const wrap = $("libListWrap");
  let results = [];
  try {
    const q = $("globalSearch").value.trim();
    results = (await api(`/v1/library/search?q=${encodeURIComponent(q)}&limit=100`)).results;
  } catch {
    wrap.innerHTML = `<div class="empty"><h3>Core not reachable</h3><p>The SANAD Core service isn't responding. It should start automatically with the app.</p></div>`;
    return;
  }
  $("libCount").textContent = `${results.length} source${results.length === 1 ? "" : "s"}`;
  $("navLibCount").textContent = results.length || "";
  $("mSources").textContent = results.length;

  if (results.length === 0) {
    wrap.innerHTML = `<div class="empty">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--faint)" stroke-width="1.4"><path d="M5 4h9a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z"/><path d="M17 7h2v13H8"/></svg>
      <h3>Your library is empty</h3>
      <p>Import references from RIS or BibTeX to get started — use <b>Add source</b> in the sidebar.</p></div>`;
    $("libDetail").style.display = "none";
    return;
  }

  const rows = results.map((r, i) => `
    <tr data-i="${i}"><td class="ti">${esc(r.title)}</td>
    <td class="au">${esc(r.authors || "")}</td>
    <td class="yr">${r.year ?? ""}</td>
    <td><span class="tag">${esc(itemLabel(r.item_type))}</span></td></tr>`).join("");
  wrap.innerHTML = `<table class="lib"><thead><tr><th>Title</th><th>Authors</th><th>Year</th><th>Type</th></tr></thead><tbody>${rows}</tbody></table>`;
  wrap.querySelectorAll("tbody tr").forEach((tr) => tr.addEventListener("click", () => {
    wrap.querySelectorAll("tr").forEach((x) => x.classList.remove("sel"));
    tr.classList.add("sel");
    showDetail(results[+tr.dataset.i]);
  }));
  showDetail(results[0]);
  wrap.querySelector("tbody tr")?.classList.add("sel");
}

function showDetail(r) {
  const d = $("libDetail");
  d.style.display = "block";
  d.innerHTML = `
    <div class="k" style="margin-top:0">Title</div><div class="dt">${esc(r.title)}</div>
    <div class="dau">${esc(r.authors || "—")}</div>
    <div class="k">Year</div><div class="val">${r.year ?? "—"}</div>
    <div class="k">Type</div><div class="val">${esc(itemLabel(r.item_type))}</div>
    ${r.doi ? `<div class="k">DOI</div><div class="doi">${esc(r.doi)}</div>` : ""}
    <div class="k">Reference id</div><div class="val" style="font-family:var(--mono);font-size:11px;color:var(--faint)">${esc(r.id)}</div>`;
}

// --- style profiles -------------------------------------------------------- //
async function loadStyles() {
  let profiles = [];
  try { profiles = (await api("/v1/style-profiles")).profiles; } catch {}
  $("styleCount").textContent = `${profiles.length} profile${profiles.length === 1 ? "" : "s"}`;
  $("navStyleCount").textContent = profiles.length || "";
  $("mStyles").textContent = profiles.length;

  const list = $("profList");
  if (profiles.length === 0) {
    list.innerHTML = `<div style="font-size:13px;color:var(--muted);padding:8px;line-height:1.6">No style profiles yet. Create one to capture your university's formatting rules — indent, "et al." threshold, ampersand, fonts — layered over a real citation style.</div>`;
    $("profBody").innerHTML = "";
    return;
  }
  list.innerHTML = profiles.map((p, i) =>
    `<div class="prof${i === 0 ? " sel" : ""}" data-id="${esc(p.id)}"><div class="pn">${esc(p.name)}</div><div class="pm">${esc(p.university || "—")} · based on ${esc(p.based_on_csl)}</div></div>`).join("");
  list.querySelectorAll(".prof").forEach((el) => el.addEventListener("click", () => {
    list.querySelectorAll(".prof").forEach((x) => x.classList.remove("sel"));
    el.classList.add("sel");
    showProfile(el.dataset.id);
  }));
  showProfile(profiles[0].id);
}

async function showProfile(id) {
  try {
    const p = await api(`/v1/style-profiles/${id}`);
    const ov = p.csl_overrides || {}, ps = p.paragraph_style || {};
    $("profBody").innerHTML = `
      <h3>${esc(p.name)}</h3>
      <p style="font-size:12.5px;color:var(--muted);margin:0 0 16px">${esc(p.university || "—")} · based on ${esc(p.based_on_csl)}</p>
      ${row("Base citation style", p.based_on_csl)}
      ${ov.et_al_min != null ? row("“et al.” from", ov.et_al_min + " authors") : ""}
      ${ov.ampersand_in_text != null ? row("Ampersand in text", ov.ampersand_in_text ? "&" : "and") : ""}
      ${ps.bibliography_hanging_indent_cm != null ? row("Hanging indent", ps.bibliography_hanging_indent_cm + " cm") : ""}
      ${ps.font_family ? row("Reference font", ps.font_family + (ps.font_size_pt ? " " + ps.font_size_pt : "")) : ""}`;
  } catch (e) { $("profBody").innerHTML = `<p style="color:var(--muted)">Couldn't load profile: ${esc(e.message)}</p>`; }
}
function row(label, value) {
  return `<div style="display:flex;justify-content:space-between;padding:11px 0;border-bottom:1px solid var(--hairline)"><span style="font-size:13px">${esc(label)}</span><span style="font-family:var(--mono);font-size:12px;color:var(--accent);font-weight:600">${esc(value)}</span></div>`;
}
$("newProfileBtn").addEventListener("click", openStyleBuilder);

// --- global search --------------------------------------------------------- //
let searchTimer = null;
$("globalSearch").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { if (!$("library").hidden) loadLibrary(); else go("library"); }, 280);
});

// --- modal system ---------------------------------------------------------- //
const overlay = $("overlay"), modalEl = $("modal");
function openModal(html) {
  modalEl.innerHTML = html;
  overlay.classList.add("show");
  modalEl.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", closeModal));
}
function closeModal() { overlay.classList.remove("show"); modalEl.innerHTML = ""; }
overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

// --- import dialog --------------------------------------------------------- //
const FMT_BY_EXT = { csv: "csv", xlsx: "xlsx", xls: "xlsx", docx: "docx", ris: "ris", bib: "bibtex", bibtex: "bibtex", txt: "typed" };

function abToB64(ab) {
  const bytes = new Uint8Array(ab);
  let bin = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  return btoa(bin);
}

async function doImport(body) {
  try {
    const r = await api("/v1/library/import", { method: "POST", body: JSON.stringify(body) });
    closeModal();
    const extra = r.resolved ? `, ${r.resolved} enriched online` : "";
    toast(`Imported ${r.imported}${extra} — library holds ${r.library_size}`);
    go("library");
  } catch (e) { toast("Import failed: " + e.message); }
}

function wantsResolve() {
  return !!(modalEl && modalEl.querySelector("#impResolve")?.checked);
}

function importFile(file) {
  const ext = (file.name.split(".").pop() || "").toLowerCase();
  const format = FMT_BY_EXT[ext];
  if (!format) { toast("Unsupported file type — use CSV, Excel, Word, RIS, or BibTeX"); return; }
  const resolve = wantsResolve();
  const reader = new FileReader();
  if (format === "xlsx" || format === "docx") {
    reader.onload = () => doImport({ format, resolve, data_b64: abToB64(reader.result) });
    reader.readAsArrayBuffer(file);
  } else {
    reader.onload = () => doImport({ format, resolve, text: reader.result });
    reader.readAsText(file);
  }
}

function openImport() {
  openModal(`
    <div class="modal-h"><h3>Import references</h3><button class="modal-x" data-close>&times;</button></div>
    <div class="modal-b">
      <div class="field-row"><label>Import a list from a file</label>
        <button class="btn" id="impFileBtn">Choose a file…</button>
        <input type="file" id="impFile" accept=".csv,.xlsx,.xls,.docx,.ris,.bib,.bibtex,.txt" style="display:none"/>
        <span class="hint">A well-formatted <b>Excel</b>, <b>CSV</b> or <b>Word</b> list of papers — or a <b>RIS</b>/<b>BibTeX</b> export. No PDFs needed.</span>
      </div>
      <div class="field-row" style="border-top:1px solid var(--hairline); padding-top:16px">
        <label>…or paste references</label>
        <div class="seg2" id="impFmt"><button data-fmt="ris" class="on">RIS</button><button data-fmt="bibtex">BibTeX</button><button data-fmt="csv">CSV</button><button data-fmt="typed">Typed list</button></div>
        <textarea class="ta" id="impText" placeholder="Paste RIS, BibTeX, a CSV table, or a plain numbered reference list."></textarea>
        <span class="hint">New to this? <a href="#" id="impSample">Load a small sample set</a>.</span>
      </div>
      <div class="field-row" style="border-top:1px solid var(--hairline); padding-top:16px">
        <label class="check"><input type="checkbox" id="impResolve"/> Look up complete details online for references that carry a DOI</label>
        <span class="hint">Off by default. When on, SANAD queries Crossref (the only time it uses the internet) to fill in and correct titles, authors, year and journal for entries that include a DOI. Everything else stays fully local.</span>
      </div>
    </div>
    <div class="modal-f"><button class="btn" data-close>Cancel</button><button class="btn primary" id="impGo">Import pasted</button></div>`);
  let fmt = "ris";
  modalEl.querySelectorAll("#impFmt button").forEach((b) => b.addEventListener("click", () => {
    modalEl.querySelectorAll("#impFmt button").forEach((x) => x.classList.remove("on")); b.classList.add("on"); fmt = b.dataset.fmt;
  }));
  modalEl.querySelector("#impSample").addEventListener("click", (e) => {
    e.preventDefault();
    modalEl.querySelectorAll("#impFmt button").forEach((x) => x.classList.toggle("on", x.dataset.fmt === "ris"));
    fmt = "ris";
    modalEl.querySelector("#impText").value = NEUTRAL_RIS;
  });
  modalEl.querySelector("#impGo").addEventListener("click", () => {
    const text = modalEl.querySelector("#impText").value.trim();
    if (!text) { toast("Paste some references, or choose a file above"); return; }
    doImport({ format: fmt, text, resolve: wantsResolve() });
  });
  modalEl.querySelector("#impFileBtn").addEventListener("click", () => modalEl.querySelector("#impFile").click());
  modalEl.querySelector("#impFile").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) importFile(file);
  });
}
document.querySelectorAll("[data-action=import]").forEach((b) => b.addEventListener("click", openImport));

// --- style profile builder ------------------------------------------------- //
function openStyleBuilder() {
  openModal(`
    <div class="modal-h"><h3>New style profile</h3><button class="modal-x" data-close>&times;</button></div>
    <div class="modal-b">
      <div class="field-row"><label>Profile name</label><input class="inp" id="spName" placeholder="e.g. Metropolitan University Thesis 2026"/></div>
      <div class="grid2">
        <div class="field-row"><label>University (optional)</label><input class="inp" id="spUni"/></div>
        <div class="field-row"><label>Base style</label><select class="sel" id="spBase">
          <option value="apa">APA 7th</option><option value="chicago-author-date">Chicago (author–date)</option>
          <option value="harvard-cite-them-right">Harvard</option><option value="modern-language-association">MLA</option><option value="ieee">IEEE</option></select></div>
      </div>
      <div class="grid2">
        <div class="field-row"><label>“et al.” from (authors)</label><input class="inp" id="spEtal" type="number" min="1" value="3"/></div>
        <div class="field-row"><label>Hanging indent (cm)</label><input class="inp" id="spIndent" type="number" step="0.01" value="1.27"/></div>
      </div>
      <div class="grid2">
        <div class="field-row"><label>Reference font</label><input class="inp" id="spFont" value="Times New Roman"/></div>
        <div class="field-row"><label>Font size (pt)</label><input class="inp" id="spSize" type="number" value="12"/></div>
      </div>
      <label class="check"><input type="checkbox" id="spAmp"/> Use the word “and” in text instead of “&amp;”</label>
    </div>
    <div class="modal-f"><button class="btn" data-close>Cancel</button><button class="btn primary" id="spGo">Create profile</button></div>`);
  modalEl.querySelector("#spGo").addEventListener("click", async () => {
    const g = (id) => modalEl.querySelector(id);
    const form = {
      name: g("#spName").value.trim() || "New profile",
      university: g("#spUni").value.trim() || null,
      based_on_csl: g("#spBase").value,
      et_al_min: +g("#spEtal").value || 3,
      hanging_indent_cm: +g("#spIndent").value || 1.27,
      font_family: g("#spFont").value.trim(),
      font_size_pt: +g("#spSize").value || 12,
      ampersand_in_text: !g("#spAmp").checked,
      ampersand_in_bibliography: true,
    };
    try {
      await api("/v1/style-profiles/build", { method: "POST", body: JSON.stringify(form) });
      closeModal(); toast("Profile created"); go("style");
    } catch (e) { toast("Couldn't create: " + e.message); }
  });
}

// --- live integrity demo --------------------------------------------------- //
const DEMO_RIS = `TY  - BOOK
AU  - Fisher, R. K.
TI  - The Art of Memory
PY  - 2001
ER  -
TY  - JOUR
AU  - Marsh, E.
TI  - Tides and the lunar cycle
AB  - Coastal water levels rise and fall with the moon's gravitational pull across the lunar month.
PY  - 2015
ER  -
TY  - JOUR
AU  - Frost, D.
TI  - Consumer credit and interest rates
AB  - Central bank interest rate decisions affect inflation and lending in the commercial banking sector.
PY  - 2018
ER  -
`;
async function runDemoScan() {
  const body = $("intgBody");
  body.innerHTML = `<div style="color:var(--muted);font-size:13px;padding:8px">Building a sample document and checking it…</div>`;
  try {
    await api("/v1/library/import", { method: "POST", body: JSON.stringify({ format: "ris", text: DEMO_RIS }) });
    const rid = async (q) => (await api(`/v1/library/search?q=${encodeURIComponent(q)}`)).results[0].id;
    const fisher = await rid("Art of Memory"), frost = await rid("Consumer credit");
    const doc = "demo-" + Date.now();
    await api("/v1/citations", { method: "POST", body: JSON.stringify({ document_id: doc, reference_ids: [fisher], raw_original_text: "(Fisher, 1998)" }) });
    const c2 = (await api("/v1/citations", { method: "POST", body: JSON.stringify({ document_id: doc, reference_ids: [frost], raw_original_text: "(Frost, 2018)" }) })).citation_id;
    const scan = await api(`/v1/documents/${doc}/scan`, { method: "POST", body: JSON.stringify({
      contexts: { [c2]: "The rise and fall of coastal water levels follows the moon's gravitational pull across the month." } }) });
    renderFlags(scan);
  } catch (e) { body.innerHTML = `<div class="empty"><h3>Demo couldn't run</h3><p>${esc(e.message)}</p></div>`; }
}
function renderFlags(scan) {
  const flags = scan.flags || [], tb = scan.tier_b || {};
  const map = (s) => (s === "error" ? "error" : s === "warning" ? "warn" : "info");
  const count = (s) => flags.filter((f) => f.severity === s).length;
  const cards = flags.map((f) => {
    const s = map(f.severity);
    const alts = (f.suggestion && f.suggestion.alternatives) || [];
    const alt = alts.length ? `<div style="border:1px dashed color-mix(in srgb,var(--sev-info) 45%,var(--hairline));border-radius:8px;padding:10px 12px;background:color-mix(in srgb,var(--sev-info) 8%,transparent);margin:0 0 10px"><div style="display:flex;justify-content:space-between;gap:10px"><span style="font-family:var(--serif);font-size:13px">${esc(alts[0].title || "")}</span><span style="font-family:var(--mono);color:var(--sev-info);font-weight:700">${Math.round(alts[0].similarity * 100)}%</span></div><div style="font-size:11.5px;color:var(--muted);margin-top:2px">A closer match already in your library</div></div>` : "";
    return `<div class="flag ${s}"><div class="top"><span class="bdg ${s}">${esc(f.severity)}</span><span class="rl">${esc(f.rule_id)}</span></div><p class="msg">${esc(f.message)}</p>${alt}<div class="acts2"><button class="btn small primary" data-flag="${esc(f.id)}" data-st="confirmed">Confirm fix</button><button class="btn small" data-flag="${esc(f.id)}" data-st="dismissed">Dismiss</button></div></div>`;
  }).join("");
  const summary = `<div class="sumrow"><span class="sev"><span class="c" style="background:var(--sev-error)"></span> ${count("error")} error</span><span class="sev"><span class="c" style="background:var(--sev-warn)"></span> ${count("warning")} to check</span><span class="sev"><span class="c" style="background:var(--sev-info)"></span> ${count("info")} suggestion</span><span style="margin-left:auto;font-size:12px;color:var(--muted)">Semantic check: ${tb.ran ? "on · " + esc(tb.backend) : "off"}</span></div>`;
  $("intgBody").innerHTML = summary + (cards || `<div class="empty"><h3>All clear</h3><p>No issues found.</p></div>`);
  $("intgBody").querySelectorAll("[data-flag]").forEach((b) => b.addEventListener("click", async () => {
    try {
      await api(`/v1/flags/${b.dataset.flag}`, { method: "PUT", body: JSON.stringify({ status: b.dataset.st }) });
      toast(b.dataset.st === "dismissed" ? "Dismissed" : "Confirmed"); b.closest(".flag").style.opacity = 0.45;
    } catch (e) { toast(e.message); }
  }));
  const open = flags.filter((f) => f.status === "open").length;
  const badge = $("navFlagBadge"); badge.textContent = open; badge.classList.toggle("show", open > 0);
  $("mFlags").textContent = open;
}
$("demoScanBtn").addEventListener("click", runDemoScan);

// --- boot ------------------------------------------------------------------ //
pollHealth();
setInterval(pollHealth, 5000);
