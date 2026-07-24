"use strict";
// SANAD renderer — talks to the local Core over HTTP. No data is hardcoded;
// every list below reflects what the Core actually holds.

const CORE = (window.sanadShell && window.sanadShell.coreUrl) || "http://127.0.0.1:23890";

async function api(path, opts) {
  const r = await fetch(CORE + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
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
  toastTimer = setTimeout(() => t.classList.remove("show"), 2200);
}

// --- navigation ------------------------------------------------------------ //
function go(id) {
  document.querySelectorAll(".nav").forEach((n) =>
    n.classList.toggle("active", n.getAttribute("data-screen") === id));
  document.querySelectorAll(".screen").forEach((s) => (s.hidden = s.id !== id));
  if (id === "library") loadLibrary();
  if (id === "style") loadStyles();
}
document.querySelectorAll("[data-screen]").forEach((b) =>
  b.addEventListener("click", () => go(b.getAttribute("data-screen"))));
document.querySelectorAll("[data-nav]").forEach((b) =>
  b.addEventListener("click", () => go(b.getAttribute("data-nav"))));

// --- Core health (live status) --------------------------------------------- //
async function pollHealth() {
  try {
    const h = await api("/v1/health");
    $("coreStatus").className = "live on";
    $("coreStatusText").textContent = "Working locally";
    $("coreVersion").textContent = "v" + (h.version || "");
    $("coreCard").className = "corecard on";
    $("coreCardState").textContent = "running · library + integrity engine";
  } catch {
    $("coreStatus").className = "live off";
    $("coreStatusText").textContent = "Core not reachable";
    $("coreCard").className = "corecard";
    $("coreCardState").textContent = "not connected";
  }
}

// --- library --------------------------------------------------------------- //
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
      <p>Import references from RIS or BibTeX to get started. To try it out, import a small sample set from the toolbar above.</p></div>`;
    $("libDetail").style.display = "none";
    return;
  }

  const rows = results.map((r, i) => `
    <tr data-i="${i}"><td class="ti">${esc(r.title)}</td>
    <td class="au">${esc(r.authors || "")}</td>
    <td class="yr">${r.year ?? ""}</td>
    <td><span class="tag">${esc(itemLabel(r.item_type))}</span></td></tr>`).join("");
  wrap.innerHTML = `<table class="lib"><thead><tr><th>Title</th><th>Authors</th><th>Year</th><th>Type</th></tr></thead><tbody>${rows}</tbody></table>`;
  wrap.querySelectorAll("tbody tr").forEach((tr) =>
    tr.addEventListener("click", () => {
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

$("importSampleBtn").addEventListener("click", async () => {
  try {
    const res = await api("/v1/library/import", {
      method: "POST",
      body: JSON.stringify({ format: "ris", text: NEUTRAL_RIS }),
    });
    toast(`Imported ${res.imported} — library now holds ${res.library_size}`);
    loadLibrary();
  } catch (e) {
    toast("Import failed: " + e.message);
  }
});

// --- style profiles -------------------------------------------------------- //
async function loadStyles() {
  let profiles = [];
  try { profiles = (await api("/v1/style-profiles")).profiles; } catch {}
  $("styleCount").textContent = `${profiles.length} profile${profiles.length === 1 ? "" : "s"}`;
  $("navStyleCount").textContent = profiles.length || "";
  $("mStyles").textContent = profiles.length;

  const list = $("profList");
  if (profiles.length === 0) {
    list.innerHTML = `<div style="font-size:13px;color:var(--muted);padding:8px;line-height:1.6">No custom style profiles yet. Create one to capture your university's formatting rules, or apply the built-in APA 7th default.</div>`;
    $("profBody").innerHTML = "";
    return;
  }
  list.innerHTML = profiles.map((p, i) =>
    `<div class="prof${i === 0 ? " sel" : ""}" data-id="${esc(p.id)}"><div class="pn">${esc(p.name)}</div><div class="pm">${esc(p.university || "—")} · based on ${esc(p.based_on_csl)}</div></div>`).join("");
  list.querySelectorAll(".prof").forEach((el) =>
    el.addEventListener("click", () => {
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
      ${ps.font_family ? row("Font", ps.font_family + (ps.font_size_pt ? " " + ps.font_size_pt : "")) : ""}`;
  } catch (e) { $("profBody").innerHTML = `<p style="color:var(--muted)">Couldn't load profile: ${esc(e.message)}</p>`; }
}
function row(label, value) {
  return `<div style="display:flex;justify-content:space-between;padding:11px 0;border-bottom:1px solid var(--hairline)"><span style="font-size:13px">${esc(label)}</span><span style="font-family:var(--mono);font-size:12px;color:var(--accent);font-weight:600">${esc(value)}</span></div>`;
}
$("newProfileBtn").addEventListener("click", async () => {
  try {
    await api("/v1/style-profiles/build", {
      method: "POST",
      body: JSON.stringify({ name: "New profile", hanging_indent_cm: 1.27, font_family: "Times New Roman", et_al_min: 3 }),
    });
    toast("Profile created");
    loadStyles();
  } catch (e) { toast("Couldn't create profile: " + e.message); }
});

// --- helpers --------------------------------------------------------------- //
function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function itemLabel(t) {
  return ({ "article-journal": "Journal", book: "Book", chapter: "Chapter", report: "Report", webpage: "Web" }[t] || t || "—");
}

let searchTimer = null;
$("globalSearch").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { if (!$("library").hidden) loadLibrary(); }, 250);
});

// --- boot ------------------------------------------------------------------ //
pollHealth();
setInterval(pollHealth, 5000);
