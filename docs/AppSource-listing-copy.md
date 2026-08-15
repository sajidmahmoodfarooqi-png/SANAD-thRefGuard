# AppSource / Partner Center — store listing copy (ready to paste)

Everything below is drafted to paste straight into Partner Center when submitting the SANAD Word
add-in. Pair it with the process in [AppSource-submission-checklist.md](AppSource-submission-checklist.md).

---

## Name
```
SANAD — the RefGuard
```

## Subtitle / short summary (≤ ~100 chars)
```
Check that every citation is actually right — locally, in Word, without touching your prose.
```

## Search keywords (Partner Center allows up to 7)
```
citation
bibliography
references
APA
thesis
citation checker
local-first
```

## Category
```
Primary: Productivity
Secondary: Reference
```

## Supported products / hosts
- **Word on Windows** ✅ and **Word on Mac** ✅ (the add-in pairs with the free SANAD desktop app on the same machine).
- **Word on the web** — *do not claim.* The add-in talks to a local engine on `127.0.0.1`, which a browser-hosted Word cannot reach. (The pane degrades gracefully with a clear message + the sample-data preview.)

## Languages
```
English (also supports right-to-left / Urdu content)
```

---

## Long description (paste into the Description field)

> **Stop worrying about silently-wrong citations.** Most reference tools stop at formatting — they make a citation *look* right. SANAD — the RefGuard goes one step further and checks whether it *is* right: the correct source, the correct year, cited in a sentence that's actually about that source.
>
> SANAD runs **entirely on your own computer**. There is no account, no cloud, and no telemetry — your reference library and your unpublished writing never leave your machine. And it is built so it **physically cannot edit your prose**: it only ever writes inside its own citation and bibliography fields.
>
> **What the integrity check catches**
> - Wrong in-text year vs. the source in your library
> - A book resolved to a *review of* the book, not the book itself
> - Orphaned citations, and references nobody actually cites
> - Duplicate library entries and ambiguous author–year pairs
> - A citation dropped into an unrelated sentence — with a closer source suggested from your own library
>
> **Right inside Word**
> - **Insert** a citation at the cursor
> - Rebuild your **Bibliography** in your chosen style
> - Run an **Integrity** check over the whole document
>
> **Private by design.** The add-in communicates only with the free SANAD desktop engine on your own machine (`127.0.0.1`), authenticated by a local token that never leaves your device.
>
> Free and open-source (AGPL-3.0). Get the desktop app and full guide at the project's GitHub page.
>
> *New to SANAD? Open the task pane and click "Preview with sample data" to see it work with no setup.*

---

## Notes for certification (reviewer instructions — critical)

> **How to review this add-in without installing anything:** SANAD's add-in is a client of a free local engine (the SANAD desktop app). Open the task pane and click **"Preview with sample data"** — it's the banner shown under the tabs when no engine is detected, and also a button on the **Connect** tab. This enters a clearly-labelled **"Demo · sample data (no engine)"** mode where Insert, Bibliography, and Integrity all work with built-in sample data (findings are marked "sample finding"). No account or sign-in exists anywhere in the product.
>
> **To test the real end-to-end flow (optional):** download and install the free SANAD desktop app from the latest GitHub release: https://github.com/sajidmahmoodfarooqi-png/SANAD-thRefGuard/releases/latest — open it, copy the token from **Settings → Connect to Microsoft Word**, then paste it into the add-in's **Connect** tab. Now Insert/Bibliography/Integrity operate on a real local library.
>
> **Privacy:** the add-in makes no outbound connections; it only calls the local engine on 127.0.0.1. No user data is collected. Privacy policy: https://sajidmahmoodfarooqi-png.github.io/SANAD-thRefGuard/privacy.html

---

## Required URLs

| Field | Value |
|---|---|
| **Support URL** | `https://github.com/sajidmahmoodfarooqi-png/SANAD-thRefGuard/issues` |
| **Privacy policy URL** | `https://sajidmahmoodfarooqi-png.github.io/SANAD-thRefGuard/privacy.html` |
| **Website / Help** | `https://sajidmahmoodfarooqi-png.github.io/SANAD-thRefGuard/` |
| **Terms of use / EULA** | AGPL-3.0 — `https://github.com/sajidmahmoodfarooqi-png/SANAD-thRefGuard/blob/main/LICENSE` (or a short EULA page if Partner Center requires standalone terms) |

## Assets to upload

| Asset | Spec | Source |
|---|---|---|
| Store logo | 300×300 PNG | derive from `assets/branding/sanad-medallion-1024.png` |
| Screenshot 1 | 1366×768 | the Word add-in (`docs/screenshots/word-addin.png`) — pad to size |
| Screenshot 2 | 1366×768 | the desktop app (`docs/screenshots/home.png`) |
| Screenshot 3 (optional) | 1366×768 | the demo-mode Integrity findings |
| Video (optional) | — | 30–60s of the real connect + integrity flow |

## Manifest to submit
```
connectors/word/manifest.prod.xml
```
Validate first: `npx office-addin-manifest validate connectors/word/manifest.prod.xml`
(see the checklist for the manifest field requirements — GUID Id, ProviderName, 300×300 icon, HTTPS URLs).
