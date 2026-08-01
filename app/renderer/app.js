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
const LIB_PAGE = 200;   // rows rendered per page — the whole library is reachable via paging
let libOffset = 0;
let libLastQuery = null;
let libSort = "year";   // "title"/"title_desc"/"year"/"year_asc" — click a column header to change

async function loadLibrary() {
  const wrap = $("libListWrap");
  const q = $("globalSearch").value.trim();
  if (q !== libLastQuery) { libOffset = 0; libLastQuery = q; }  // new search resets to page 1

  let results = [], total = 0;
  try {
    const data = await api(`/v1/library?q=${encodeURIComponent(q)}&limit=${LIB_PAGE}&offset=${libOffset}&sort=${libSort}`);
    results = data.results; total = data.total ?? results.length;
  } catch {
    wrap.innerHTML = `<div class="empty"><h3>Core not reachable</h3><p>The SANAD Core service isn't responding. It should start automatically with the app.</p></div>`;
    return;
  }

  // header counts always reflect the TRUE total, not just the current page
  const label = q ? `${total.toLocaleString()} match${total === 1 ? "" : "es"}` : `${total.toLocaleString()} source${total === 1 ? "" : "s"}`;
  $("libCount").textContent = label;
  $("navLibCount").textContent = total || "";
  $("mSources").textContent = total;

  if (total === 0) {
    wrap.innerHTML = `<div class="empty">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--faint)" stroke-width="1.4"><path d="M5 4h9a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z"/><path d="M17 7h2v13H8"/></svg>
      <h3>${q ? "No matches" : "Your library is empty"}</h3>
      <p>${q ? "No references match your search." : "Import your existing library file (<b>.ris</b>, <b>.bib</b>, .csv, .xlsx, .docx) — use <b>Add source</b> in the sidebar."}</p></div>`;
    $("libDetail").style.display = "none";
    return;
  }

  const rows = results.map((r, i) => `
    <tr data-i="${i}"><td class="ti">${esc(r.title)}</td>
    <td class="au">${esc(r.authors || "")}</td>
    <td class="yr">${r.year ?? ""}</td>
    <td><span class="tag">${esc(itemLabel(r.item_type))}</span></td></tr>`).join("");

  const from = total ? libOffset + 1 : 0, to = Math.min(libOffset + LIB_PAGE, total);
  const pager = total > LIB_PAGE ? `
    <div class="pager">
      <button class="btn small" id="libPrev" ${libOffset === 0 ? "disabled" : ""}>← Previous</button>
      <span class="pager-info">Showing ${from.toLocaleString()}–${to.toLocaleString()} of ${total.toLocaleString()}</span>
      <button class="btn small" id="libNext" ${to >= total ? "disabled" : ""}>Next →</button>
    </div>` : "";

  const titleArrow = libSort === "title" ? " ▲" : (libSort === "title_desc" ? " ▼" : "");
  const yearArrow = libSort === "year" ? " ▼" : (libSort === "year_asc" ? " ▲" : "");
  wrap.innerHTML = `<table class="lib"><thead><tr>` +
    `<th class="sortable" data-sort="title" title="Click to sort A–Z (clusters duplicates)">Title${titleArrow}</th>` +
    `<th>Authors</th>` +
    `<th class="sortable" data-sort="year" title="Click to sort by year">Year${yearArrow}</th>` +
    `<th>Type</th></tr></thead><tbody>${rows}</tbody></table>${pager}`;
  wrap.querySelectorAll("th.sortable").forEach((th) => th.addEventListener("click", () => {
    const col = th.dataset.sort;
    if (col === "title") libSort = libSort === "title" ? "title_desc" : "title";
    else libSort = libSort === "year" ? "year_asc" : "year";
    libOffset = 0; loadLibrary();
  }));
  wrap.querySelectorAll("tbody tr").forEach((tr) => tr.addEventListener("click", () => {
    wrap.querySelectorAll("tr").forEach((x) => x.classList.remove("sel"));
    tr.classList.add("sel");
    showDetail(results[+tr.dataset.i]);
  }));
  const prev = wrap.querySelector("#libPrev"), next = wrap.querySelector("#libNext");
  if (prev) prev.addEventListener("click", () => { libOffset = Math.max(0, libOffset - LIB_PAGE); loadLibrary(); });
  if (next) next.addEventListener("click", () => { libOffset += LIB_PAGE; loadLibrary(); });
  showDetail(results[0]);
  wrap.querySelector("tbody tr")?.classList.add("sel");
  refreshDedupeButton();
}

async function refreshDedupeButton() {
  const btn = $("libDedupeBtn");
  if (!btn) return;
  try {
    const d = await api("/v1/library/duplicates");
    if (d.duplicate_count > 0) {
      $("libDedupeLbl").textContent = `Remove ${d.duplicate_count} duplicate${d.duplicate_count === 1 ? "" : "s"}`;
      btn.style.display = "";
    } else {
      btn.style.display = "none";
    }
  } catch { btn.style.display = "none"; }
}

function openDedupe() {
  api("/v1/library/duplicates").then((d) => {
    const n = d.duplicate_count;
    if (!n) { toast("No duplicates found"); return; }
    openModal(`
      <div class="modal-h"><h3>Remove duplicates</h3><button class="modal-x" data-close>&times;</button></div>
      <div class="modal-b"><p style="font-size:13.5px;line-height:1.6">Found <b>${n}</b> duplicate reference${n === 1 ? "" : "s"} across ${d.groups} group${d.groups === 1 ? "" : "s"} — copies of works you already have. Matched by DOI, by an exact content match, or by the same title and year (e.g. a full record with a DOI alongside a bare re-entry of the same paper). The most complete copy is kept.</p>
      <p style="font-size:13.5px;line-height:1.6">SANAD keeps one copy of each and removes the extras. Any citations already pointing at a removed copy are repointed to the one that's kept, so nothing breaks. This can't be undone.</p></div>
      <div class="modal-f"><button class="btn" data-close>Cancel</button><button class="btn primary" id="dedupeGo">Remove ${n} duplicate${n === 1 ? "" : "s"}</button></div>`);
    modalEl.querySelector("#dedupeGo").addEventListener("click", async () => {
      try {
        const r = await api("/v1/library/deduplicate", { method: "POST" });
        closeModal();
        toast(`Removed ${r.removed} duplicate${r.removed === 1 ? "" : "s"} — library holds ${r.library_size}`);
        libOffset = 0; libLastQuery = null; loadLibrary();
      } catch (e) { toast("Couldn't remove duplicates: " + e.message); }
    });
  }).catch((e) => toast("Couldn't check for duplicates: " + e.message));
}
$("libDedupeBtn")?.addEventListener("click", openDedupe);

function showDetail(r) {
  const d = $("libDetail");
  if (!r) { d.style.display = "none"; return; }
  d.style.display = "block";
  d.innerHTML = `
    <div class="k" style="margin-top:0">Title</div><div class="dt">${esc(r.title)}</div>
    <div class="dau">${esc(r.authors || "—")}</div>
    <div class="k">Year</div><div class="val">${r.year ?? "—"}</div>
    <div class="k">Type</div><div class="val">${esc(itemLabel(r.item_type))}</div>
    ${r.doi ? `<div class="k">DOI</div><div class="doi">${esc(r.doi)}</div>` : ""}
    <div class="k">Reference id</div><div class="val" style="font-family:var(--mono);font-size:11px;color:var(--faint)">${esc(r.id)}</div>
    <button class="btn danger" id="refDelete" style="margin-top:18px">Delete this reference</button>`;
  d.querySelector("#refDelete").addEventListener("click", () => deleteReference(r));
}

async function deleteReference(r) {
  const title = (r.title || "").slice(0, 80);
  openModal(`
    <div class="modal-h"><h3>Delete reference?</h3><button class="modal-x" data-close>&times;</button></div>
    <div class="modal-b"><p style="font-size:13.5px;line-height:1.6">Remove <b>${esc(title)}</b> from your library? This can't be undone. Any citation pointing at it is unlinked.</p></div>
    <div class="modal-f"><button class="btn" data-close>Cancel</button><button class="btn danger" id="delRefGo">Delete</button></div>`);
  modalEl.querySelector("#delRefGo").addEventListener("click", async () => {
    try {
      const res = await api(`/v1/library/${encodeURIComponent(r.id)}`, { method: "DELETE" });
      closeModal();
      toast(res.deleted ? `Deleted — library holds ${res.library_size}` : "Already gone");
      loadLibrary();
    } catch (e) { toast("Couldn't delete: " + e.message); }
  });
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
    const ds = p.document_structure || {}, hd = ds.headings || {};
    const hspec = (s) => s && (s.font || s.size_pt != null)
      ? [s.font || "(body font)", s.size_pt != null ? s.size_pt + " pt" : ""].filter(Boolean).join(" · ") : "";
    $("profBody").innerHTML = `
      <h3>${esc(p.name)}</h3>
      <p style="font-size:12.5px;color:var(--muted);margin:0 0 16px">${esc(p.university || "—")} · based on ${esc(p.based_on_csl)}</p>
      ${row("Base citation style", p.based_on_csl)}
      ${ov.et_al_min != null ? row("“et al.” from", ov.et_al_min + " authors") : ""}
      ${ov.ampersand_in_text != null ? row("Ampersand in text", ov.ampersand_in_text ? "&" : "and") : ""}
      ${ps.bibliography_hanging_indent_cm != null ? row("Hanging indent", ps.bibliography_hanging_indent_cm + " cm") : ""}
      ${ps.font_family ? row("Reference font", ps.font_family + (ps.font_size_pt ? " " + ps.font_size_pt : "")) : ""}
      ${ds.margin_cm != null ? row("Page margin", ds.margin_cm + " cm") : ""}
      ${ds.binding_margin_cm != null ? row("Binding margin", ds.binding_margin_cm + " cm (" + (ds.binding_side || "left") + ")") : ""}
      ${hspec(hd.title) ? row("Title style", hspec(hd.title)) : ""}
      ${hspec(hd.h1) ? row("Heading 1", hspec(hd.h1)) : ""}
      ${hspec(hd.h2) ? row("Heading 2", hspec(hd.h2)) : ""}
      ${hspec(hd.h3) ? row("Heading 3", hspec(hd.h3)) : ""}
      ${hd.numbered ? row("Heading numbering", "1 / 1.1 / 1.1.1 (automatic)") : ""}
      ${(ds.caption && (ds.caption.font || ds.caption.size_pt != null || ds.caption.italic)) ? row("Caption style", [ds.caption.font, ds.caption.size_pt != null ? ds.caption.size_pt + " pt" : "", ds.caption.italic ? "italic" : ""].filter(Boolean).join(" · ")) : ""}
      <div style="display:flex;gap:8px;margin-top:20px">
        <button class="btn" id="profRename">Rename…</button>
        <button class="btn danger" id="profDelete">Delete</button>
      </div>`;
    $("profRename").addEventListener("click", () => renameProfile(p));
    $("profDelete").addEventListener("click", () => deleteProfile(p));
  } catch (e) { $("profBody").innerHTML = `<p style="color:var(--muted)">Couldn't load profile: ${esc(e.message)}</p>`; }
}

function renameProfile(p) {
  openModal(`
    <div class="modal-h"><h3>Rename style profile</h3><button class="modal-x" data-close>&times;</button></div>
    <div class="modal-b">
      <div class="field-row"><label for="rnName">Profile name</label>
        <input class="inp" id="rnName" value="${esc(p.name)}"/></div>
    </div>
    <div class="modal-f"><button class="btn" data-close>Cancel</button><button class="btn primary" id="rnGo">Save</button></div>`);
  const input = modalEl.querySelector("#rnName");
  input.focus(); input.select();
  modalEl.querySelector("#rnGo").addEventListener("click", async () => {
    const name = input.value.trim();
    if (!name) { toast("Give the profile a name"); return; }
    try {
      await api(`/v1/style-profiles/${p.id}`, { method: "PUT", body: JSON.stringify({ ...p, name }) });
      closeModal(); toast("Renamed"); loadStyles();
    } catch (e) { toast("Rename failed: " + e.message); }
  });
}

function deleteProfile(p) {
  openModal(`
    <div class="modal-h"><h3>Delete style profile?</h3><button class="modal-x" data-close>&times;</button></div>
    <div class="modal-b"><p style="font-size:13.5px;line-height:1.6">Delete <b>${esc(p.name)}</b>? Documents already formatted with it keep their formatting; you just can't apply it to new documents. This can't be undone.</p></div>
    <div class="modal-f"><button class="btn" data-close>Cancel</button><button class="btn danger" id="delGo">Delete</button></div>`);
  modalEl.querySelector("#delGo").addEventListener("click", async () => {
    try {
      await api(`/v1/style-profiles/${p.id}`, { method: "DELETE" });
      closeModal(); toast("Deleted"); loadStyles();
    } catch (e) { toast("Delete failed: " + e.message); }
  });
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
let modalReturnFocus = null;
const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';
function openModal(html) {
  modalReturnFocus = document.activeElement;  // restore focus on close
  modalEl.innerHTML = html;
  overlay.classList.add("show");
  modalEl.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", closeModal));
  // move focus into the dialog (first field, else first control)
  const first = modalEl.querySelector("input,select,textarea") || modalEl.querySelector(FOCUSABLE);
  if (first) first.focus();
}
function closeModal() {
  overlay.classList.remove("show");
  modalEl.innerHTML = "";
  if (modalReturnFocus && modalReturnFocus.focus) modalReturnFocus.focus();
  modalReturnFocus = null;
}
function modalOpen() { return overlay.classList.contains("show"); }
overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });
document.addEventListener("keydown", (e) => {
  if (!modalOpen()) return;
  if (e.key === "Escape") { closeModal(); return; }
  if (e.key !== "Tab") return;
  // trap Tab within the dialog
  const items = [...modalEl.querySelectorAll(FOCUSABLE)].filter((el) => el.offsetParent !== null);
  if (items.length === 0) return;
  const first = items[0], last = items[items.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
});

// --- import dialog --------------------------------------------------------- //
const FMT_BY_EXT = { csv: "csv", xlsx: "xlsx", xls: "xlsx", docx: "docx", ris: "ris", bib: "bibtex", bibtex: "bibtex", txt: "typed" };

function abToB64(ab) {
  const bytes = new Uint8Array(ab);
  let bin = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  return btoa(bin);
}

let importInFlight = false;
async function doImport(body) {
  if (importInFlight) { toast("An import is already running — one moment…"); return; }  // block a rapid double-drop
  importInFlight = true;
  try {
    const r = await api("/v1/library/import", { method: "POST", body: JSON.stringify(body) });
    closeModal();
    const extra = r.resolved ? `, ${r.resolved} enriched online` : "";
    toast(`Imported ${r.imported}${extra} — library holds ${r.library_size}`);
    libOffset = 0; libLastQuery = null;  // show page 1 with the new total
    go("library");
  } catch (e) { toast("Import failed: " + e.message); }
  finally { importInFlight = false; }
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
    <div class="modal-h"><h3>Import your library</h3><button class="modal-x" data-close>&times;</button></div>
    <div class="modal-b">
      <div class="field-row"><label>Import an existing library file</label>
        <div class="import-drop" id="impDrop">
          <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="1.6"><path d="M12 16V4M8 8l4-4 4 4"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/></svg>
          <div><b>Choose a file</b> or drag it here</div>
          <div class="fmts"><span class="fmt">.ris</span><span class="fmt">.bib</span><span class="fmt">.bibtex</span><span class="fmt">.csv</span><span class="fmt">.xlsx</span><span class="fmt">.docx</span></div>
          <span class="hint">Already have a library from Zotero, Mendeley, EndNote or a spreadsheet? Export it as <b>RIS</b> or <b>BibTeX</b> and drop it here — no need to retype anything, and no PDFs required.</span>
        </div>
        <input type="file" id="impFile" accept=".csv,.xlsx,.xls,.docx,.ris,.bib,.bibtex,.txt" style="display:none"/>
      </div>
      <div class="field-row" style="border-top:1px solid var(--hairline); padding-top:16px">
        <label>…or paste references instead</label>
        <div class="seg2" id="impFmt"><button data-fmt="ris" class="on">RIS</button><button data-fmt="bibtex">BibTeX</button><button data-fmt="csv">CSV</button><button data-fmt="typed">Typed list</button></div>
        <textarea class="ta" id="impText" placeholder="Paste RIS, BibTeX, a CSV table, or a plain numbered reference list."></textarea>
        <span class="hint">New to this? <a href="#" id="impSample">Load a small sample set</a>.</span>
      </div>
      <div class="field-row" style="border-top:1px solid var(--hairline); padding-top:16px">
        <label class="check"><input type="checkbox" id="impResolve"/> Look up complete details online for references that carry a DOI</label>
        <span class="hint">Off by default. When on, SANAD queries Crossref (the only time it uses the internet) to fill in and correct titles, authors, year and journal for entries that include a DOI. Everything else stays fully local.</span>
      </div>
    </div>
    <div class="modal-f"><button class="btn" data-close>Cancel</button><button class="btn primary" id="impGo">Import pasted text</button></div>`);
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
  const drop = modalEl.querySelector("#impDrop"), fileInput = modalEl.querySelector("#impFile");
  drop.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", (e) => { const f = e.target.files[0]; if (f) importFile(f); });
  // drag-and-drop a library file straight onto the drop zone. Every dragover must
  // preventDefault or the drop never fires; the global guard below stops a stray
  // drop from navigating the whole window to the file.
  ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); e.stopPropagation(); drop.classList.add("drag"); }));
  drop.addEventListener("dragleave", (e) => { e.preventDefault(); drop.classList.remove("drag"); });
  drop.addEventListener("drop", (e) => {
    e.preventDefault(); e.stopPropagation(); drop.classList.remove("drag");
    const dt = e.dataTransfer;
    const f = (dt.files && dt.files[0]) || (dt.items && dt.items[0] && dt.items[0].getAsFile && dt.items[0].getAsFile());
    if (f) importFile(f);
    else toast("Couldn't read the dropped file — try the “Choose a file” button instead");
  });
}
document.querySelectorAll("[data-action=import]").forEach((b) => b.addEventListener("click", openImport));
// Global guard: in Electron a file dropped anywhere but a handled zone makes the
// window navigate to that file (blanking the app). Swallow drops outside the zone.
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", (e) => e.preventDefault());

// --- style profile builder ------------------------------------------------- //
function openStyleBuilder(prefill) {
  const pf = prefill || {};
  const val = (k, d) => (pf[k] != null ? pf[k] : d);
  const banner = pf._detected ? `
    <div class="detect-banner">
      <b>Read from your manual — please confirm.</b>
      <ul>${pf._detected.map((d) => `<li><b>${esc(d.field)}:</b> ${esc(String(d.value))} <span class="ev">“${esc(d.evidence)}”</span></li>`).join("")}</ul>
      ${(pf._notes && pf._notes.length) ? `<div class="notes">${pf._notes.map((n) => esc(n)).join("<br/>")}</div>` : ""}
    </div>` : "";
  openModal(`
    <div class="modal-h"><h3>${pf._detected ? "Confirm style from manual" : "New style profile"}</h3><button class="modal-x" data-close>&times;</button></div>
    <div class="modal-b">
      ${banner}
      <div class="field-row"><label>Profile name</label><input class="inp" id="spName" value="${esc(val("name", ""))}" placeholder="e.g. Metropolitan University Thesis 2026"/></div>
      <div class="grid2">
        <div class="field-row"><label>University (optional)</label><input class="inp" id="spUni" value="${esc(val("university", ""))}"/></div>
        <div class="field-row"><label>Citation style</label>
          <input class="inp" id="spBaseSearch" placeholder="Search 10,000+ styles — APA, MLA, Vancouver, a journal name…" autocomplete="off"/>
          <select class="sel" id="spBase" size="6" style="margin-top:6px"></select>
        </div>
      </div>
      <div class="grid2">
        <div class="field-row"><label>Body font</label><input class="inp" id="spFont" value="${esc(val("font_family", "Times New Roman"))}"/></div>
        <div class="field-row"><label>Font size (pt)</label><input class="inp" id="spSize" type="number" value="${esc(val("font_size_pt", 12))}"/></div>
      </div>
      <div class="grid2">
        <div class="field-row"><label>Line spacing</label><select class="sel" id="spSpacing">
          <option value="1">Single (1.0)</option><option value="1.5">1.5</option><option value="2">Double (2.0)</option></select></div>
        <div class="field-row"><label>Page margin (cm)</label><input class="inp" id="spMargin" type="number" step="0.01" value="${esc(val("margin_cm", 2.54))}"/></div>
      </div>
      <div class="grid2">
        <div class="field-row"><label>Reference hanging indent (cm)</label><input class="inp" id="spIndent" type="number" step="0.01" value="${esc(val("hanging_indent_cm", 1.27))}"/></div>
        <div class="field-row"><label>“et al.” from (authors)</label><input class="inp" id="spEtal" type="number" min="1" value="3"/></div>
      </div>
      <div class="grid2">
        <div class="field-row"><label>Binding margin (cm) — optional</label><input class="inp" id="spBindMargin" type="number" step="0.01" placeholder="e.g. 3.81 (1.5 in)"/></div>
        <div class="field-row"><label>Binding side (portrait)</label><select class="sel" id="spBindSide"><option value="left">Left</option><option value="right">Right</option><option value="top">Top</option><option value="bottom">Bottom</option></select></div>
      </div>
      <div class="grid2">
        <div class="field-row"><label>Binding side (landscape pages)</label><select class="sel" id="spBindSideLand"><option value="bottom">Bottom</option><option value="top">Top</option><option value="left">Left</option><option value="right">Right</option></select></div>
        <div class="field-row"></div>
      </div>
      <p class="sp-hint">Leave binding margin blank for equal margins all round. Set it (e.g. 3.81 cm = 1.5″) for the bound edge; the other sides keep the page margin above. Landscape pages (wide tables) are bound on a different edge — bottom by default — and are handled automatically.</p>
      <label class="check"><input type="checkbox" id="spAmp"/> Use the word “and” in text instead of “&amp;”</label>
      <div class="sp-section-h">Headings (Word Styles gallery)</div>
      <p class="sp-hint">Fonts &amp; sizes for Title and Heading 1–3, applied when you format a thesis. Your heading text is never changed — only the style.</p>
      <div class="grid2">
        <div class="field-row"><label>Title font</label><input class="inp" id="spTitleFont" value="${esc(val("title_font", ""))}" placeholder="(same as body)"/></div>
        <div class="field-row"><label>Title size (pt)</label><input class="inp" id="spTitleSize" type="number" step="0.5" value="${esc(val("title_size_pt", ""))}" placeholder="e.g. 26"/></div>
      </div>
      <div class="grid2">
        <div class="field-row"><label>Heading 1 font</label><input class="inp" id="spH1Font" value="${esc(val("h1_font", ""))}" placeholder="(same as body)"/></div>
        <div class="field-row"><label>Heading 1 size (pt)</label><input class="inp" id="spH1Size" type="number" step="0.5" value="${esc(val("h1_size_pt", ""))}" placeholder="e.g. 16"/></div>
      </div>
      <div class="grid2">
        <div class="field-row"><label>Heading 2 font</label><input class="inp" id="spH2Font" value="${esc(val("h2_font", ""))}" placeholder="(same as body)"/></div>
        <div class="field-row"><label>Heading 2 size (pt)</label><input class="inp" id="spH2Size" type="number" step="0.5" value="${esc(val("h2_size_pt", ""))}" placeholder="e.g. 14"/></div>
      </div>
      <div class="grid2">
        <div class="field-row"><label>Heading 3 font</label><input class="inp" id="spH3Font" value="${esc(val("h3_font", ""))}" placeholder="(same as body)"/></div>
        <div class="field-row"><label>Heading 3 size (pt)</label><input class="inp" id="spH3Size" type="number" step="0.5" value="${esc(val("h3_size_pt", ""))}" placeholder="e.g. 12"/></div>
      </div>
      <label class="check"><input type="checkbox" id="spNumber"/> Number headings automatically — <b>1</b>, <b>1.1</b>, <b>1.1.1</b> (Word’s standard multilevel scheme)</label>
      <div class="sp-section-h">Captions (figures &amp; tables)</div>
      <p class="sp-hint">Sets how Word’s Caption style looks. Insert captions in Word (References → Insert Caption) — <b>below</b> figures/graphs, <b>above</b> tables; this styles them.</p>
      <div class="grid2">
        <div class="field-row"><label>Caption font</label><input class="inp" id="spCapFont" placeholder="(same as body)"/></div>
        <div class="field-row"><label>Caption size (pt)</label><input class="inp" id="spCapSize" type="number" step="0.5" placeholder="e.g. 10"/></div>
      </div>
      <label class="check"><input type="checkbox" id="spCapItalic"/> Italic captions</label>
    </div>
    <div class="modal-f"><button class="btn" data-close>Cancel</button><button class="btn primary" id="spGo">${pf._detected ? "Save profile" : "Create profile"}</button></div>`);
  // searchable style picker over the full bundled CSL catalog
  const baseSel = modalEl.querySelector("#spBase"), baseSearch = modalEl.querySelector("#spBaseSearch");
  async function loadStyles(q) {
    try {
      const { styles } = await api(`/v1/styles?q=${encodeURIComponent(q || "")}`);
      baseSel.innerHTML = styles.map((s) => `<option value="${esc(s.id)}"${s.id === pf.based_on_csl ? " selected" : ""}>${esc(s.title)}</option>`).join("")
        || `<option value="" disabled>No matching styles</option>`;
    } catch { baseSel.innerHTML = `<option value="apa">APA 7th</option>`; }
  }
  let styleTimer = null;
  baseSearch.addEventListener("input", () => { clearTimeout(styleTimer); styleTimer = setTimeout(() => loadStyles(baseSearch.value), 250); });
  // if the manual named a style, search for it so it's selectable/selected
  loadStyles(pf.based_on_csl || "");
  // preselect detected line spacing
  const sp = modalEl.querySelector("#spSpacing");
  sp.value = String(val("line_spacing", 1) === 2.0 ? 2 : (val("line_spacing", 1) === 1.5 ? 1.5 : val("line_spacing", 1)));
  if (val("number_headings", false)) modalEl.querySelector("#spNumber").checked = true;
  modalEl.querySelector("#spGo").addEventListener("click", async () => {
    const g = (id) => modalEl.querySelector(id);
    const form = {
      name: g("#spName").value.trim() || "New profile",
      university: g("#spUni").value.trim() || null,
      based_on_csl: g("#spBase").value || "apa",
      et_al_min: +g("#spEtal").value || 3,
      hanging_indent_cm: +g("#spIndent").value || 1.27,
      line_spacing: +g("#spSpacing").value || 1,
      margin_cm: +g("#spMargin").value || null,
      font_family: g("#spFont").value.trim(),
      font_size_pt: +g("#spSize").value || 12,
      ampersand_in_text: !g("#spAmp").checked,
      ampersand_in_bibliography: true,
      number_headings: g("#spNumber").checked,
    };
    // headings: send font/size only when the user actually entered one
    const num = (id) => { const v = g(id).value.trim(); return v === "" ? null : (+v || null); };
    const txt = (id) => g(id).value.trim() || null;
    Object.assign(form, {
      title_font: txt("#spTitleFont"), title_size_pt: num("#spTitleSize"),
      h1_font: txt("#spH1Font"), h1_size_pt: num("#spH1Size"),
      h2_font: txt("#spH2Font"), h2_size_pt: num("#spH2Size"),
      h3_font: txt("#spH3Font"), h3_size_pt: num("#spH3Size"),
      binding_margin_cm: num("#spBindMargin"), binding_side: g("#spBindSide").value || "left",
      binding_side_landscape: g("#spBindSideLand").value || "bottom",
      caption_font: txt("#spCapFont"), caption_size_pt: num("#spCapSize"),
      caption_italic: g("#spCapItalic").checked ? true : null,
    });
    try {
      await api("/v1/style-profiles/build", { method: "POST", body: JSON.stringify(form) });
      closeModal(); toast("Profile created"); go("style");
    } catch (e) { toast("Couldn't create: " + e.message); }
  });
}

// --- create a profile from a thesis manual (local detect & confirm) -------- //
const MANUAL_EXT = { docx: "docx", pdf: "pdf", txt: "txt" };
function fromManual() {
  const input = document.createElement("input");
  input.type = "file"; input.accept = ".docx,.pdf,.txt";
  input.addEventListener("change", () => {
    const file = input.files[0]; if (!file) return;
    const ext = (file.name.split(".").pop() || "").toLowerCase();
    const fmt = MANUAL_EXT[ext];
    if (!fmt) { toast("Upload the manual as .docx, .pdf or .txt"); return; }
    toast("Reading your manual on-device…");
    const reader = new FileReader();
    const done = async (body) => {
      try {
        const r = await api("/v1/handbook/parse", { method: "POST", body: JSON.stringify(body) });
        const pf = { ...r.form, _detected: r.detected, _notes: r.notes };
        if (!pf.name) pf.name = file.name.replace(/\.[^.]+$/, "");
        openStyleBuilder(pf);
      } catch (e) { toast("Couldn't read the manual: " + e.message); }
    };
    if (fmt === "txt") { reader.onload = () => done({ format: "txt", text: reader.result }); reader.readAsText(file); }
    else { reader.onload = () => done({ format: fmt, data_b64: abToB64(reader.result) }); reader.readAsArrayBuffer(file); }
  });
  input.click();
}
$("fromManualBtn")?.addEventListener("click", fromManual);

// --- format the researcher's thesis .docx to a profile (local, offline) ---- //
function formatThesis() {
  api("/v1/style-profiles").then(({ profiles }) => {
    if (!profiles.length) { toast("Create a style profile first (or build one from your manual)"); return; }
    openModal(`
      <div class="modal-h"><h3>Format my thesis</h3><button class="modal-x" data-close>&times;</button></div>
      <div class="modal-b">
        <div class="field-row"><label>Apply this style profile</label>
          <select class="sel" id="ftProfile">${profiles.map((p) => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("")}</select></div>
        <div class="field-row" style="border-top:1px solid var(--hairline);padding-top:16px">
          <label>Your thesis document (.docx)</label>
          <div class="import-drop" id="ftDrop">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="1.6"><path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4"/></svg>
            <div><b>Choose your .docx</b> or drag it here</div>
            <span class="hint">SANAD applies the fonts, spacing, margins and reference indent to your document’s styles and hands it back. <b>Your words are never changed, and the file never leaves this computer.</b></span>
          </div>
          <input type="file" id="ftFile" accept=".docx" style="display:none"/>
        </div>
        <div id="ftResult"></div>
      </div>
      <div class="modal-f"><button class="btn" data-close>Close</button></div>`);
    const drop = modalEl.querySelector("#ftDrop"), fileInput = modalEl.querySelector("#ftFile");
    const run = (file) => {
      if (!file) return;
      if (!file.name.toLowerCase().endsWith(".docx")) { toast("Please choose a .docx file"); return; }
      const profileId = modalEl.querySelector("#ftProfile").value;
      modalEl.querySelector("#ftResult").innerHTML = `<p class="hint" style="margin-top:14px">Formatting on-device…</p>`;
      const reader = new FileReader();
      reader.onload = async () => {
        try {
          const r = await api("/v1/documents/format", { method: "POST",
            body: JSON.stringify({ profile_id: profileId, data_b64: abToB64(reader.result) }) });
          const bytes = Uint8Array.from(atob(r.data_b64), (c) => c.charCodeAt(0));
          const blob = new Blob([bytes], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
          const url = URL.createObjectURL(blob);
          const outName = file.name.replace(/\.docx$/i, "") + " (formatted).docx";
          modalEl.querySelector("#ftResult").innerHTML = `
            <div class="detect-banner"><b>Done — your words are unchanged.</b>
              <ul>${r.applied.map((a) => `<li>${esc(a)}</li>`).join("")}</ul>
              <a class="btn primary" id="ftDownload" download="${esc(outName)}" href="${url}">Download formatted thesis</a>
            </div>`;
        } catch (e) { modalEl.querySelector("#ftResult").innerHTML = `<p class="hint" style="color:var(--danger,#c0392b);margin-top:14px">Couldn’t format: ${esc(e.message)}</p>`; }
      };
      reader.readAsArrayBuffer(file);
    };
    drop.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => run(e.target.files[0]));
    ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); e.stopPropagation(); drop.classList.add("drag"); }));
    drop.addEventListener("dragleave", (e) => { e.preventDefault(); drop.classList.remove("drag"); });
    drop.addEventListener("drop", (e) => { e.preventDefault(); e.stopPropagation(); drop.classList.remove("drag"); run(e.dataTransfer.files[0]); });
  }).catch((e) => toast("Couldn't load profiles: " + e.message));
}
$("formatDocBtn")?.addEventListener("click", formatThesis);

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

// open the complete offline guide (shipped with the app) in the system browser
$("openGuideBtn")?.addEventListener("click", async () => {
  try {
    const r = await window.sanadShell?.openGuide?.();
    if (!r) throw new Error("unavailable");
    if (!r.ok) throw new Error(r.error || "couldn't open the guide");
  } catch (e) {
    toast("Couldn't open the guide: " + (e.message || e));
  }
});

// --- boot ------------------------------------------------------------------ //
pollHealth();
setInterval(pollHealth, 5000);
