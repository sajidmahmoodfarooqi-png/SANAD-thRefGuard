/* SANAD Word add-in — a thin client of the local SANAD Core.
 *
 * It never writes prose: every citation it inserts is wrapped in a Word content
 * control tagged "sanad-cite", and that tag is the only place it ever writes.
 * The Core (http://127.0.0.1:23890) does all the resolving, rendering, and
 * integrity checking; this task pane just calls it and places the results.
 */
"use strict";

const CORE = "http://127.0.0.1:23890";
const $ = (id) => document.getElementById(id);

// --- reviewer / first-run demo mode ---------------------------------------- //
// When no local Core is reachable (an AppSource reviewer, or a brand-new user who
// hasn't started the desktop app yet), the pane can preview itself with built-in
// SAMPLE data so its features are visible. It is clearly labelled "sample" and
// never claims to be real: Insert writes an obviously-sample citation, and the
// Integrity list shows fixed example findings. Real usage is unaffected — demo
// mode only turns on when the user explicitly clicks "Preview with sample data".
let DEMO = false;
const demoCited = new Set();   // which sample refs the user actually inserted, so the
                               // demo bibliography reflects the document (like the real engine)
const DEMO_REFS = [
  { id: "d1", title: "A framework for resilient urban water networks", authors: "Alvarez, M. & Okonkwo, P.", year: 2019,
    cite: "(Alvarez & Okonkwo, 2019)", entry: "Alvarez, M., & Okonkwo, P. (2019). A framework for resilient urban water networks. Journal of Urban Systems, 11, 44–61." },
  { id: "d2", title: "Spatial equity in urban green infrastructure", authors: "Nakamura, Y.", year: 2020,
    cite: "(Nakamura, 2020)", entry: "Nakamura, Y. (2020). Spatial equity in urban green infrastructure. Landscape & Society, 14, 5–22." },
  { id: "d3", title: "Remote sensing of informal settlement growth", authors: "Costa, L., Fenwick, A. & Reyes, D.", year: 2018,
    cite: "(Costa et al., 2018)", entry: "Costa, L., Fenwick, A., & Reyes, D. (2018). Remote sensing of informal settlement growth. Remote Sensing Letters, 9, 301–314." },
];
const DEMO_SCAN = { flags: [
  { rule_id: "R8_CONTEXT_MISALIGNMENT", severity: "warning",
    message: "The citing sentence seems only weakly related to the source it cites — a closer source may fit better. (sample finding)",
    suggestion: { alternatives: [{ similarity: 0.17, title: "Remote sensing of informal settlement growth" }] } },
  { rule_id: "R1_YEAR_MISMATCH", severity: "error",
    message: "In-text year 2018 does not match the source in your library (2019). Pick the correct year. (sample finding)" },
  { rule_id: "R5_LISTED_NOT_CITED", severity: "info",
    message: "“Participatory mapping methods” sits in your reference list but nothing cites it. (sample finding)" },
] };
function enterDemo() {
  DEMO = true;
  const bar = $("demoBar"); if (bar) bar.hidden = true;
  const el = $("status"); el.className = "status on"; el.innerHTML = `<i></i> Demo · sample data (no engine)`;
  showTab("insert");
  $("results").innerHTML = `<p class="muted">Preview mode with built-in sample data. Type anything, insert a sample citation, then open <b>Integrity</b> or <b>Bibliography</b>. Connect a running SANAD engine to use your own library.</p>`;
}

// The Core requires a per-launch session token. The user pastes it once (from the
// desktop app's Settings, or the sanad.token file next to the library) into the
// add-in's connect field; it is kept in this document's own settings.
function coreToken() {
  // localStorage persists per-user across ALL your documents for this add-in, so
  // the token is pasted once (roamingSettings is Outlook-only — unavailable here).
  // Fall back to a per-document token saved by older versions.
  try {
    const ls = (window.localStorage.getItem("sanadToken") || "").trim();
    if (ls) return ls;
  } catch (_) { /* storage blocked */ }
  return (Office.context.document.settings.get("sanadToken") || "").trim();
}

async function core(path, opts) {
  const headers = { "Content-Type": "application/json" };
  const t = coreToken();
  if (t) headers["Authorization"] = "Bearer " + t;
  const r = await fetch(CORE + path, { headers, ...opts });
  if (r.status === 401) throw new Error("Not connected: paste your SANAD token in the add-in settings.");
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.status === 204 ? null : r.json();
}
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// stable per-document id, persisted in the document's own settings
function docId() {
  let id = Office.context.document.settings.get("sanadDocId");
  if (!id) {
    id = "doc-" + Math.random().toString(36).slice(2, 10);
    Office.context.document.settings.set("sanadDocId", id);
    Office.context.document.settings.saveAsync();
  }
  return id;
}

Office.onReady((info) => {
  if (info.host !== Office.HostType.Word) return;
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => showTab(t.dataset.tab)));
  $("q").addEventListener("input", debounce(search, 250));
  $("scanBtn").addEventListener("click", runIntegrity);
  $("biblioBtn").addEventListener("click", insertBibliography);
  $("saveTokenBtn").addEventListener("click", saveToken);
  document.querySelectorAll(".demo-start").forEach((b) => b.addEventListener("click", enterDemo));
  const tok = coreToken();
  if (tok) $("token").value = tok;
  pollHealth();
  setInterval(pollHealth, 5000);
});

// --- connect: store the Core session token in this document's settings ------ //
function saveToken() {
  const v = ($("token").value || "").trim();
  // localStorage = remembered for every document you open, so this is one-time.
  // Also mirror into document settings as a reliable fallback if storage is wiped.
  try { window.localStorage.setItem("sanadToken", v); } catch (_) {}
  try {
    Office.context.document.settings.set("sanadToken", v);
    Office.context.document.settings.saveAsync();
  } catch (_) {}
  $("connectMsg").innerHTML = v
    ? `<p class="muted">Saved for all your documents. Checking connection…</p>`
    : `<p class="muted">Token cleared.</p>`;
  pollHealth();
}

function showTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("on", t.dataset.tab === name));
  document.querySelectorAll(".tab-body").forEach((b) => (b.hidden = b.id !== name));
}

async function pollHealth() {
  const el = $("status");
  const bar = $("demoBar");
  try {
    const h = await core("/v1/health");
    // A real engine answered — it always wins over preview. This is what lets you
    // LEAVE demo mode: as soon as the desktop app is reachable (or you Connect a
    // token), the next poll switches the pane to the live engine automatically.
    DEMO = false;
    el.className = "status on"; el.innerHTML = `<i></i> working locally · v${esc(h.version)}`;
    if (bar) bar.hidden = true;
  } catch {
    if (DEMO) return;                     // no engine, but the user chose preview — keep it
    el.className = "status off"; el.innerHTML = `<i></i> Core not running`;
    if (bar) bar.hidden = false;          // offer the sample-data preview
  }
}

// --- search + insert ------------------------------------------------------- //
async function search() {
  const q = $("q").value.trim();
  const box = $("results");
  if (!q) { box.innerHTML = `<p class="muted">Type to search your local library, then insert a citation at the cursor.</p>`; return; }
  let results;
  if (DEMO) {
    const ql = q.toLowerCase();
    results = DEMO_REFS.filter((r) => r.title.toLowerCase().includes(ql) || r.authors.toLowerCase().includes(ql));
    if (!results.length) results = DEMO_REFS;
  } else {
    try { results = (await core(`/v1/library/search?q=${encodeURIComponent(q)}&limit=25`)).results; }
    catch (e) { box.innerHTML = `<p class="muted">Can't reach the Core: ${esc(e.message)}</p>`; return; }
  }
  if (!results.length) { box.innerHTML = `<p class="muted">Nothing found for “${esc(q)}”.</p>`; return; }
  box.innerHTML = results.map((r) =>
    `<div class="res" data-id="${esc(r.id)}"><div class="rt">${esc(r.title)}</div><div class="rm">${esc(r.authors || "")}${r.year ? " · " + r.year : ""}</div></div>`).join("");
  box.querySelectorAll(".res").forEach((el) => el.addEventListener("click", () => insertCitation(el.dataset.id)));
}

async function insertCitation(refId) {
  let res;
  if (DEMO) {
    const r = DEMO_REFS.find((x) => x.id === refId) || DEMO_REFS[0];
    demoCited.add(r.id);   // remember it so the demo bibliography lists only what was inserted
    res = { citation_id: "demo-" + refId, rendered_text: r.cite };
  } else {
    try { res = await core("/v1/citations", { method: "POST", body: JSON.stringify({ document_id: docId(), reference_ids: [refId] }) }); }
    catch (e) { return notify("Couldn't create citation: " + e.message); }
  }
  await Word.run(async (ctx) => {
    const cc = ctx.document.getSelection().insertContentControl();
    cc.tag = "sanad-cite";          // the ONLY place this add-in ever writes
    cc.title = res.citation_id;     // stash the stable UUID for re-resolving / scanning
    cc.appearance = "BoundingBox";
    cc.insertText(res.rendered_text, Word.InsertLocation.replace);
    await ctx.sync();
  });
  notify("Inserted — build the list from the Bibliography tab");
}

// --- reference list -------------------------------------------------------- //
// Rebuilds the whole bibliography from the document's citations and writes it
// ONLY inside the single "sanad-bibliography" content control (created if absent,
// updated in place if present). Formatting comes from the active Style Profile.
async function insertBibliography() {
  const msg = $("biblioMsg");
  msg.innerHTML = `<p class="muted">Building reference list…</p>`;
  let data;
  if (DEMO) {
    data = { entries: DEMO_REFS.filter((r) => demoCited.has(r.id)).map((r) => r.entry), paragraph_style: {} };
  } else {
    // Enumerate the citation controls actually present in the document, so the
    // Core drops any citation the user deleted in Word before rebuilding the list.
    // IMPORTANT: only send the present-set if we actually read it — sending an
    // empty set on a failed read would tell the Core to prune every citation.
    let present = [], gathered = false;
    try {
      await Word.run(async (ctx) => {
        const ccs = ctx.document.contentControls;
        ccs.load("items/tag,items/title");
        await ctx.sync();
        present = ccs.items.filter((c) => c.tag === "sanad-cite").map((c) => c.title);
      });
      gathered = true;
    } catch (_) { gathered = false; }   // couldn't read controls -> don't reconcile

    const url = `/v1/documents/${docId()}/bibliography`;
    try {
      data = gathered
        ? await core(url, { method: "POST", body: JSON.stringify({ present_control_ids: present }) })
        : await core(url);
    } catch (e) {
      // older Core without the POST route (405): fall back to the plain GET build
      try { data = await core(url); }
      catch (e2) { return (msg.innerHTML = `<p class="muted">Couldn't build it: ${esc(e2.message)}</p>`); }
    }
  }
  const entries = data.entries || [];
  const ps = data.paragraph_style || {};
  if (!entries.length) { return (msg.innerHTML = `<p class="muted">No SANAD citations in this document yet — insert some first.</p>`); }

  try {
    await Word.run(async (ctx) => {
      // find our own bibliography control (the ONLY place we write here)
      const existing = ctx.document.contentControls.getByTag("sanad-bibliography");
      existing.load("items");
      await ctx.sync();

      let cc;
      if (existing.items.length) {
        cc = existing.items[0];
        cc.clear();                       // safe: it is our tagged control
      } else {
        cc = ctx.document.getSelection().insertContentControl();
        cc.tag = "sanad-bibliography";
        cc.title = "SANAD Reference List";
        cc.appearance = "BoundingBox";
      }
      // first entry replaces the (empty) control content; the rest become paragraphs
      cc.insertText(entries[0], Word.InsertLocation.replace);
      await ctx.sync();
      for (let i = 1; i < entries.length; i++) cc.insertParagraph(entries[i], Word.InsertLocation.end);
      await ctx.sync();

      // apply the profile's paragraph formatting to every line of the list
      const paras = cc.paragraphs;
      paras.load("items");
      await ctx.sync();
      paras.items.forEach((p) => {
        if (ps.fontName) p.font.name = ps.fontName;
        if (ps.fontSizePt != null) p.font.size = ps.fontSizePt;
        if (ps.spaceAfterPt != null) p.spaceAfter = ps.spaceAfterPt;
        if (ps.leftIndentPt != null) p.leftIndent = ps.leftIndentPt;          // hanging indent:
        if (ps.firstLineIndentPt != null) p.firstLineIndent = ps.firstLineIndentPt;  // negative first line
      });
      await ctx.sync();
    });
  } catch (e) { return (msg.innerHTML = `<p class="muted">Couldn't write the list: ${esc(e.message)}</p>`); }
  msg.innerHTML = `<p class="muted">Reference list updated — ${entries.length} entr${entries.length === 1 ? "y" : "ies"}.</p>`;
}

// --- integrity ------------------------------------------------------------- //
async function runIntegrity() {
  const box = $("flags");
  box.innerHTML = `<p class="muted">Checking…</p>`;
  if (DEMO) { renderFlags(DEMO_SCAN); return; }   // sample findings, no engine needed
  // gather each sanad-cite control's surrounding paragraph as its citing context (Tier-B)
  const contexts = {};
  let present = [];
  try {
    await Word.run(async (ctx) => {
      const ccs = ctx.document.contentControls;
      ccs.load("items/tag,items/title");
      await ctx.sync();
      const cites = ccs.items.filter((c) => c.tag === "sanad-cite");
      cites.forEach((c) => { present.push(c.title); c._para = c.paragraphs; c._para.load("items/text"); });
      await ctx.sync();
      for (const c of cites) {
        const txt = (c._para.items[0] && c._para.items[0].text || "").trim();
        if (txt) contexts[c.title] = txt;
      }
    });
  } catch (e) { return (box.innerHTML = `<p class="muted">Couldn't read the document: ${esc(e.message)}</p>`); }

  let scan;
  try { scan = await core(`/v1/documents/${docId()}/scan`, { method: "POST", body: JSON.stringify({ present_control_ids: present, contexts }) }); }
  catch (e) { return (box.innerHTML = `<p class="muted">Scan failed: ${esc(e.message)}</p>`); }
  renderFlags(scan);
}

function renderFlags(scan) {
  const flags = scan.flags || [];
  if (!flags.length) { $("flags").innerHTML = `<p class="muted">All clear — no issues found.</p>`; return; }
  const cls = (s) => (s === "error" ? "error" : s === "warning" ? "warn" : "info");
  $("flags").innerHTML = flags.map((f) => {
    const alts = (f.suggestion && f.suggestion.alternatives) || [];
    const sugg = alts.length ? `<div class="sugg"><span class="pct">${Math.round(alts[0].similarity * 100)}%</span><span class="st">${esc(alts[0].title || "")}</span></div>` : "";
    return `<div class="flag ${cls(f.severity)}"><span class="rl">${esc(f.rule_id)}</span><span class="bdg">${esc(f.severity)}</span><p class="msg">${esc(f.message)}</p>${sugg}</div>`;
  }).join("");
}

// --- helpers --------------------------------------------------------------- //
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
function notify(msg) {
  try { Office.context.document.settings; } catch (_) {}
  const el = $("status"); const prev = el.innerHTML;
  el.innerHTML = `<i></i> ${esc(msg)}`;
  setTimeout(() => { el.innerHTML = prev; }, 1800);
}
