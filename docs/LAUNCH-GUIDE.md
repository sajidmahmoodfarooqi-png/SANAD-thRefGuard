# SANAD launch guide — your step-by-step to-do list

Everything technical is prepared. This guide is **only the actions you need to take**, in order,
written for a first-timer. Do them top to bottom. Reddit is already done, so it's skipped.

Time: Part 1 ≈ 15 min · Part 2 ≈ 20 min · Part 3 (AppSource) ≈ 1–2 hours + review wait.

**Links you'll reuse:**
- Repo: `https://github.com/sajidmahmoodfarooqi-png/SANAD-thRefGuard`
- Site: `https://sajidmahmoodfarooqi-png.github.io/SANAD-thRefGuard/`
- Privacy: `https://sajidmahmoodfarooqi-png.github.io/SANAD-thRefGuard/privacy.html`
- Terms: `https://sajidmahmoodfarooqi-png.github.io/SANAD-thRefGuard/terms.html`
- Ready-to-paste listing text: `docs/AppSource-listing-copy.md`
- Store images (already sized): `docs/store-assets/`

---

## PART 1 — Five-minute wins (do these first)

### Step 1 — Pin the repository to your profile
So visitors to your GitHub profile see SANAD first.
1. Go to your profile: `https://github.com/sajidmahmoodfarooqi-png`.
2. Under your bio, click **Customize your pins** (or the **Pin** option on the repo's own page ⋯ menu).
3. Tick **SANAD-thRefGuard** → **Save pins**.

### Step 2 — Create the four "starter" issues
These give visiting developers something to grab. Do each one:
1. Go to the repo → **Issues** tab → green **New issue** button.
2. If it shows templates, click **Open a blank issue** (bottom).
3. Copy a **Title** and **Body** from the four blocks below.
4. On the right, under **Labels**, click the gear and choose **good first issue** (and any others listed).
5. Click **Submit new issue**. Repeat for all four.

> If a label like `good first issue` doesn't exist yet: Issues → **Labels** → **New label** → type the
> name → **Create**. `good first issue` and `help wanted` are GitHub defaults and usually already there.

**Issue 1 — Title:** `Add a reviewer/demo screenshot set to the README`
Body:
```
The add-in now has a "Preview with sample data" demo mode. Add a short GIF or 2–3 screenshots of the
demo flow (search → insert → Integrity findings) to the README and the landing page (docs/site/). No
engine needed — open the task pane and click "Preview with sample data". Good first issue: touches
only docs/screenshots.
```
Labels: `good first issue`, `documentation`

**Issue 2 — Title:** `Contribute a Style Profile for a real university handbook`
Body:
```
SANAD formats to a shareable Style Profile (.sanadstyle.json): base CSL style, "et al." threshold,
ampersand rule, spacing, hanging indent, heading styles. We'd love profiles for real university
handbooks (APA/Harvard variants). Build one in the app (Style profiles → New profile) and open a PR
adding it under an examples/style-profiles/ folder with a note on the source handbook. See
MVP_SPEC.md for the format.
```
Labels: `good first issue`, `help wanted`

**Issue 3 — Title:** `Run SANAD against a real thesis and report integrity-check gaps`
Body:
```
The most valuable early contribution: install SANAD, insert citations in a real (or realistic)
chapter, run the Integrity check, and report what it MISSES or OVER-FLAGS (rules R1–R8). Use the
"Integrity check feedback" issue form. Paraphrased/invented examples are fine — please don't paste
private text.
```
Labels: `good first issue`

**Issue 4 — Title:** `macOS / Linux installers via CI`
Body:
```
Today release.yml builds only the Windows installer (PyInstaller + electron-builder NSIS). Extend the
release workflow to also produce a macOS .dmg and a Linux AppImage (the mac/linux electron-builder
targets already exist in app/package.json). Needs runners for each OS in the CI matrix.
```
Labels: `help wanted`, `enhancement`

---

## PART 2 — Bring in testers with a "Show HN" post

Hacker News sends motivated, technical early users. One good post can bring your first real testers.

### Step 3 — Post to Show HN
1. Create/sign in to a Hacker News account: `https://news.ycombinator.com` → **login** (top right) → create one if needed.
2. Go to `https://news.ycombinator.com/submit`.
3. **Title** (paste exactly — the "Show HN:" prefix matters):
   ```
   Show HN: SANAD – a local-first citation checker for Word that verifies citations are right
   ```
4. **URL**:
   ```
   https://github.com/sajidmahmoodfarooqi-png/SANAD-thRefGuard
   ```
5. Leave the text box empty (you have a URL), then click **submit**.
6. **Immediately after**, add a first comment introducing it (this is expected on Show HN). Paste:
   ```
   Author here. I built SANAD because reference managers stop at formatting — they make a citation
   *look* right. SANAD checks whether it *is* right: wrong in-text year, a book resolved to a review
   of the book, orphaned/duplicate references, and citations dropped into an unrelated sentence (with
   a closer source suggested from your own library).

   Two things I cared about: it runs entirely on your machine (no account, no cloud), and it
   physically can't edit your prose — it only writes inside its own citation/bibliography fields,
   enforced by a fuzz test. Python/FastAPI core, Electron app, Office.js task pane. Free, AGPLv3.

   It's early and I'd love people to run it against a real thesis and tell me what the integrity
   checker misses or over-flags. Windows installer + a 2-minute sample pack are in the repo.
   ```
7. **Timing:** post on a **weekday, ~08:00–10:00 US Eastern** for the best odds.
8. **Then stay for ~2 hours** and reply to every comment — engagement keeps it visible. Be humble and
   specific; "great question, here's how it works…" beats defensiveness.

> Etiquette: post it **once**. Don't ask friends to upvote (HN penalises voting rings). Let it stand
> on its own.

---

## PART 3 — Microsoft AppSource (the big reach unlock)

This puts SANAD in Word's own **Insert → Get Add-ins** search. It's the most involved step — take it
slowly; you can save a draft and come back.

### Step 4 — Create a Partner Center account (one-time)
1. Go to `https://partner.microsoft.com` → **Sign in** with a Microsoft account (create one if needed).
2. Enrol in the **Marketplace / Office Store** program (sometimes called "Commercial Marketplace").
   Registration for Office add-ins is free.
3. Fill in your **publisher profile** (name, contact). Verification can take a day or two — start this
   early so it's ready when you submit.

### Step 5 — Pre-flight the manifest (do this before submitting)
The file to submit is `connectors/word/manifest.prod.xml`. Validate it first:
1. Install Node.js if you don't have it (`https://nodejs.org`, LTS version).
2. In a terminal, from the repo folder:
   ```
   npx office-addin-manifest validate connectors/word/manifest.prod.xml
   ```
3. It should report the manifest is valid. Fix anything it flags.

> ✅ **The ribbon button is already built in.** The manifest now adds a **SANAD** button to Word's
> **Home** tab (an "add-in command") that opens the task pane — this is what AppSource expects. The
> manifest passes Microsoft's official validator with no errors.
>
> **Confirm it once before submitting:** sideload `connectors/word/manifest.prod.xml` in Word
> (**Insert → My Add-ins → Upload My Add-in**), then look at the **Home** tab — you should see a
> **SANAD** button. Click it; the task pane opens. If you don't see the button, close and reopen
> Word once (Office caches add-in commands). Once you've seen the button, you're ready to submit.

### Step 6 — Start the add-in submission and fill the listing
1. In Partner Center: **Marketplace offers** → **New offer** → **Office add-in** (or "Word add-in").
2. Give it an internal name (e.g. `SANAD - the RefGuard`).
3. Open **`docs/AppSource-listing-copy.md`** and copy each field into the matching Partner Center box:
   - **Name**, **Short description / subtitle**, **Description** (the long one), **Search keywords**
     (up to 7), **Category** (Productivity), **Languages** (English).
   - Under **Products supported**, tick **Word for Windows** and **Word for Mac**. **Do NOT** tick
     **Word on the web** (the local-engine model can't work in a browser).

### Step 7 — Enter the required URLs
Paste these into the corresponding fields:
- **Support / Help URL:** `https://github.com/sajidmahmoodfarooqi-png/SANAD-thRefGuard/issues`
- **Privacy policy URL:** `https://sajidmahmoodfarooqi-png.github.io/SANAD-thRefGuard/privacy.html`
- **Terms of use URL:** `https://sajidmahmoodfarooqi-png.github.io/SANAD-thRefGuard/terms.html`
- **Website:** `https://sajidmahmoodfarooqi-png.github.io/SANAD-thRefGuard/`

### Step 8 — Upload the package and images
1. **Manifest / package:** upload `connectors/word/manifest.prod.xml`.
2. **Store logo:** upload `docs/store-assets/logo-300.png` (300×300).
3. **Screenshots:** upload both from `docs/store-assets/`:
   - `screenshot-1-desktop-1366x768.png`
   - `screenshot-2-word-addin-1366x768.png`

### Step 9 — Add the reviewer / certification notes (very important)
In the **Notes for certification** box, paste this so the reviewer can actually test it:
```
How to review without installing anything: SANAD's add-in is a client of a free local engine (the
SANAD desktop app). Open the task pane and click "Preview with sample data" — it's the banner under
the tabs when no engine is detected, and a button on the Connect tab. This enters a clearly-labelled
"Demo · sample data" mode where Insert, Bibliography, and Integrity all work with built-in sample
data (findings are marked "sample finding"). There is no account or sign-in anywhere in the product.

To test the real end-to-end flow (optional): install the free desktop app from
https://github.com/sajidmahmoodfarooqi-png/SANAD-thRefGuard/releases/latest — open it, copy the token
from Settings → Connect to Microsoft Word, and paste it into the add-in's Connect tab.

Privacy: the add-in makes no outbound connections; it only calls the local engine on 127.0.0.1. No
user data is collected. Privacy policy: https://sajidmahmoodfarooqi-png.github.io/SANAD-thRefGuard/privacy.html
```

### Step 10 — Submit, then watch for the review
1. **Review** every page, then **Publish / Submit**.
2. Expect automated + human review (a few days, sometimes longer).
3. **Check your Partner Center notifications / email.** If it's rejected, the reason is usually the
   ribbon-button item from Step 5 or a testing question — reply/adjust and resubmit. This is normal;
   don't be discouraged.

---

## Optional — winget (Windows Package Manager)
Lets people run `winget install SANAD` and softens the "unknown publisher" warning. Full instructions
(the easy `wingetcreate` path) are in `packaging/winget/README.md`. Do this any time; it's independent
of the above.

---

## Quick checklist
- [ ] Step 1 — Pin the repo
- [ ] Step 2 — Create 4 starter issues (with labels)
- [ ] Step 3 — Post Show HN + first comment, then engage for ~2h
- [ ] Step 4 — Partner Center account (start early — verification lag)
- [ ] Step 5 — Validate manifest (ask about the ribbon button)
- [ ] Step 6 — Fill listing from AppSource-listing-copy.md
- [ ] Step 7 — Enter the 4 URLs
- [ ] Step 8 — Upload manifest + logo + 2 screenshots
- [ ] Step 9 — Paste reviewer notes
- [ ] Step 10 — Submit and watch for review
- [ ] Optional — winget
