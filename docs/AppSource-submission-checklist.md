# Getting the SANAD Word add-in into Microsoft AppSource

**Why it's worth it:** once listed, users click **Insert → Get Add-ins → search "SANAD"** *inside
Word* and install with one click — no manifest sideloading. AppSource is also a real discovery
channel for an Office add-in (far better than GitHub for reaching researchers), and it lends
legitimacy.

This is the add-in only (the Office.js task pane in `connectors/word/`). The desktop app / Core is
distributed separately (GitHub Releases, and ideally winget — see `packaging/winget/`).

---

## 0. The one real hurdle — read this first

SANAD's add-in is a **thin client of a local engine**: it only works when the SANAD desktop app is
running on the same machine and the user has pasted a session token. Microsoft's validation team
tests add-ins on their own environment, where the Core is **not** installed — so out of the box the
pane will show "Core not running" and they cannot exercise the features.

**✅ A reviewer demo mode is already built in** (`connectors/word/taskpane.js`). When no local Core
is reachable, a **"No SANAD engine detected — Preview with sample data →"** banner appears under the
tabs, and there's a matching button on the **Connect** tab. Clicking it enters a clearly-labelled
**"Demo · sample data (no engine)"** mode: search returns sample references, Insert writes a sample
citation into the document, Bibliography builds a sample list, and Integrity shows example findings
(each marked *"sample finding"*). It never claims to be real data, and real usage is unaffected —
demo mode only turns on when explicitly clicked.

**In the submission's *Notes for certification*, tell the reviewer exactly this:**

> SANAD's add-in is a client of a free local engine (the SANAD desktop app). To review the add-in's
> UI and features **without installing anything**, open the task pane and click **"Preview with
> sample data"** (the banner under the tabs, or the button on the Connect tab). To test the real
> end-to-end flow, install the desktop app from `<GitHub release link>`, copy the token from
> Settings → Connect to Microsoft Word, and paste it into the add-in's Connect tab.

A short **demo video** of the real flow is still a nice-to-have to attach. A hosted demo Core is not
needed given the built-in demo mode.

## 1. Accounts & legal (one-time)

- [ ] **Microsoft Partner Center** account with the *Office Store / Marketplace* program enrolled
      (https://partner.microsoft.com). Individual publishers are allowed.
- [ ] **Privacy policy URL** (required). SANAD is local-first — a short page on the GitHub Pages site
      stating "no data leaves the device, no account, no telemetry" satisfies this.
- [ ] **EULA / terms** (AGPL-3.0 can back it; you still need a URL).
- [ ] **Support URL** — the repo Issues page.

## 2. Manifest readiness (`connectors/word/manifest.prod.xml`)

- [ ] Unique **`<Id>`** GUID (stable forever for this add-in).
- [ ] **`<ProviderName>`**, **`<DisplayName>`**, **`<Description>`** all present and non-generic.
- [ ] **HTTPS everywhere** — `SourceLocation`, `IconUrl`, `HighResolutionIconUrl`, `SupportUrl`
      (all already on the GitHub Pages origin ✔).
- [ ] **`<AppDomains>`** lists every origin the pane navigates to. (It talks to `http://127.0.0.1`
      via fetch, not navigation, so that's allowed by the add-in's own CORS story — but double-check
      validation doesn't object; be ready to explain the loopback call in the notes.)
- [ ] **Icons**: 32/64/80 px (have) **plus** a 300×300 store logo.
- [ ] **`<VersionOverrides>`** and requirement sets valid; the manifest passes the validator
      (see step 3).
- [ ] Bump the manifest **`<Version>`** for each store update.

## 3. Validate before you submit

- [ ] Run Microsoft's **[Office Add-in Manifest validator](https://learn.microsoft.com/office/dev/add-ins/testing/troubleshoot-manifest)**:
      `npx office-addin-manifest validate connectors/word/manifest.prod.xml`
- [ ] Sideload the **prod** manifest and confirm it loads, connects to a running Core, and that
      Insert / Bibliography / Integrity all work with no console errors.
- [ ] Test on **Word on Windows**, **Word on Mac**, and **Word on the web** if you claim them (the
      loopback-to-127.0.0.1 model does **not** work in Word on the web — either don't claim web, or
      handle it gracefully with a message).

## 4. Store listing assets

- [ ] **Name**: SANAD — the RefGuard
- [ ] **Short + long description** (reuse the README's "Why" and "What makes it different").
- [ ] **At least 1–5 screenshots** (1366×768). Use `docs/screenshots/word-addin.png` and a shot of
      the desktop app.
- [ ] **Logo** 300×300 (derive from `assets/branding/sanad-medallion-1024.png`).
- [ ] **Category**: Productivity / Reference.
- [ ] **Search keywords**: citation, references, bibliography, APA, thesis, integrity, local-first.

## 5. Submit & iterate

- [ ] Submit in Partner Center; expect automated + human review (days, sometimes longer).
- [ ] Watch for rejection reasons — usually the *reviewer-can't-test* hurdle from step 0. Respond
      with the script/video or ship the demo mode, and resubmit.

---

### Realistic sequencing

Ship **GitHub Releases + winget** first (fast, no gatekeeper). Add the **reviewer demo mode** to the
task pane, then pursue **AppSource** — that's the step that unlocks in-Word discovery, but it needs
the testing story sorted first.
