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

// The Core requires a per-launch session token. The user pastes it once (from the
// desktop app's Settings, or the sanad.token file next to the library) into the
// add-in's connect field; it is kept in this document's own settings.
function coreToken() {
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
  pollHealth();
  setInterval(pollHealth, 5000);
});

function showTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("on", t.dataset.tab === name));
  document.querySelectorAll(".tab-body").forEach((b) => (b.hidden = b.id !== name));
}

async function pollHealth() {
  const el = $("status");
  try { const h = await core("/v1/health"); el.className = "status on"; el.innerHTML = `<i></i> working locally · v${esc(h.version)}`; }
  catch { el.className = "status off"; el.innerHTML = `<i></i> Core not running`; }
}

// --- search + insert ------------------------------------------------------- //
async function search() {
  const q = $("q").value.trim();
  const box = $("results");
  if (!q) { box.innerHTML = `<p class="muted">Type to search your local library, then insert a citation at the cursor.</p>`; return; }
  let results;
  try { results = (await core(`/v1/library/search?q=${encodeURIComponent(q)}&limit=25`)).results; }
  catch (e) { box.innerHTML = `<p class="muted">Can't reach the Core: ${esc(e.message)}</p>`; return; }
  if (!results.length) { box.innerHTML = `<p class="muted">Nothing found for “${esc(q)}”.</p>`; return; }
  box.innerHTML = results.map((r) =>
    `<div class="res" data-id="${esc(r.id)}"><div class="rt">${esc(r.title)}</div><div class="rm">${esc(r.authors || "")}${r.year ? " · " + r.year : ""}</div></div>`).join("");
  box.querySelectorAll(".res").forEach((el) => el.addEventListener("click", () => insertCitation(el.dataset.id)));
}

async function insertCitation(refId) {
  let res;
  try { res = await core("/v1/citations", { method: "POST", body: JSON.stringify({ document_id: docId(), reference_ids: [refId] }) }); }
  catch (e) { return notify("Couldn't create citation: " + e.message); }
  await Word.run(async (ctx) => {
    const cc = ctx.document.getSelection().insertContentControl();
    cc.tag = "sanad-cite";          // the ONLY place this add-in ever writes
    cc.title = res.citation_id;     // stash the stable UUID for re-resolving / scanning
    cc.appearance = "BoundingBox";
    cc.insertText(res.rendered_text, Word.InsertLocation.replace);
    await ctx.sync();
  });
  notify("Citation inserted");
}

// --- integrity ------------------------------------------------------------- //
async function runIntegrity() {
  const box = $("flags");
  box.innerHTML = `<p class="muted">Checking…</p>`;
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
