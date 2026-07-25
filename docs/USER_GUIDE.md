# SANAD the RefGuard — User Guide

*A local-first citation companion for Microsoft Word and LibreOffice.*

SANAD (سند — Arabic/Urdu for a *chain of authority*, and for a certificate or
proof) does three things other citation tools don't:

1. It checks that each citation is **actually right** — the right source, cited
   in the right place — not just formatted right.
2. It formats to **your university's handbook**, not a generic style.
3. It **never edits a word of your prose** — a guarantee enforced in code.

Everything runs on your own machine. There is no account, no cloud, and no data
leaves your computer.

---

## Contents

1. [Installing SANAD](#1-installing-sanad)
2. [First run](#2-first-run)
3. [A tour of the window](#3-a-tour-of-the-window)
4. [Importing your references](#4-importing-your-references)
5. [Working with the library](#5-working-with-the-library)
6. [Style profiles — matching your handbook](#6-style-profiles)
7. [The integrity check — what SANAD catches](#7-the-integrity-check)
8. [Citing in Word / LibreOffice](#8-citing-in-word--libreoffice)
9. [Your data & privacy](#9-your-data--privacy)
10. [Troubleshooting](#10-troubleshooting)
11. [FAQ](#11-faq)

---

## 1. Installing SANAD

Download the installer for your system and run it:

- **Windows** — `SANAD-Setup.exe`
- **macOS** — `SANAD.dmg` (drag SANAD to Applications)
- **Linux** — `SANAD.AppImage` (mark executable, then run)

SANAD bundles everything it needs, including its own engine — you do **not** need
to install Python or anything else.

> On first launch, Windows SmartScreen or macOS Gatekeeper may warn about a new
> publisher. This is expected for a new app; choose "Run anyway" / open from
> System Settings → Privacy & Security.

## 2. First run

When SANAD opens it quietly starts its **Core** — a small engine that runs only
on your machine (`127.0.0.1`). The status light in the top-right corner turns
green and reads **"Working locally"** when it's ready. The sidebar's **SANAD
Core** card shows the same.

Your library starts empty. Head to **Library → Add source** to bring in your
references (next section).

## 3. A tour of the window

- **Title bar** — the SANAD mark, a global search box, and the live "Working
  locally" status with the version.
- **Sidebar** — navigation:
  - **Home** — an at-a-glance dashboard and getting-started steps.
  - **Library** — all your sources.
  - **Documents** — the Word/LibreOffice files SANAD is tracking.
  - **Integrity check** — the results of checking a document; the red badge shows
    how many items need review.
  - **Style profiles** — your formatting rules.
  - **Settings** — Core status, version, and app info.
  - **Help** — this guide, inside the app.
- **Main area** — changes with the section you pick.

## 4. Importing your references

Click **Add source** (sidebar) or **Import references** (Library). You have two
ways in, and you can mix them:

**A. From a file (no PDFs needed).** Click **"Choose a file…"** and pick a
well-formatted list of your papers as **Excel (.xlsx)**, **CSV**, or **Word
(.docx)** — or a **RIS**/**BibTeX** export from any reference manager. SANAD
reads the list and builds your library from it; that library is what every
citation, style, and integrity check works from afterwards. For a spreadsheet,
give each paper a row and use column headers such as *Title, Authors, Year,
Journal, Volume, Issue, Pages, DOI, Type* (SANAD recognises common variants and
extra columns are ignored). A Word file may just be your reference list, one
entry per paragraph.

**B. By pasting.** Choose a **format** — **RIS**, **BibTeX**, **CSV**, or
**Typed list** (a plain numbered reference list) — paste into the box, and click
**Import pasted**. New to it? Click **"Load a small sample set"** to try the
whole flow with a few example references.

**Optional: online lookup (off by default).** Tick *"Look up complete details
online for references that carry a DOI"* to have SANAD fill in and correct
titles, authors, year and journal from **Crossref** for any entry that includes
a DOI. This is the **only** time SANAD uses the internet, it is **per-import**
and off unless you tick it, it only touches entries that already have a DOI (so
it can never fetch the *wrong* paper from a title guess), and if you're offline
or a lookup fails your reference is kept exactly as you supplied it.

**What happens on import:** SANAD parses each reference, stores it locally, and
de-duplicates safely — if you import the same reference twice (same DOI, or an
exact content match), it collapses to one entry. It never silently merges two
*different* works that happen to share a title; instead it flags likely
duplicates for you to review (rule **R6**, below).

> With online lookup left off, SANAD makes no network calls at all and keeps
> exactly what you import. If a reference is missing details, either tick the
> lookup box (if it has a DOI), correct it in your reference manager and
> re-import, or edit the source.

## 5. Working with the library

The **Library** lists every source with its title, authors, year, and type.

- **Search** — type in the title-bar search or the library search to filter by
  title, author, or DOI.
- **Select a source** — click a row to see its full details on the right: the
  journal/publisher, DOI, and where it's cited.
- **Filter by type** — journal, book, chapter, report, web.

## 6. Style profiles

A **style profile** captures your target format. Instead of a generic "APA", you
build a profile that matches your **university's thesis handbook**.

To create one: **Style profiles → New profile**, then set:

- **Base style** — the citation style everything derives from (APA 7th, Chicago,
  Harvard, MLA, IEEE).
- **"et al." from** — how many authors before a list is shortened.
- **Ampersand in text** — use "and" instead of "&".
- **Hanging indent** — the reference-list indent, in centimetres.
- **Reference font** — family and size for the bibliography.

Save it, and it becomes available to apply to your documents. A profile is a
small, shareable file — a future version lets you publish it so the next student
at your university can use it directly.

## 7. The integrity check

This is what makes SANAD different. After a citation *looks* right, SANAD checks
whether it *is* right. In the app you can press **Run a demo check** on the
Integrity screen to see it work on a sample document; in real use, the checks run
on the document you're writing.

Each finding is a card with a severity, a plain-English explanation, and actions.
Here is what each rule means and how to act:

| Rule | What it catches | What to do |
|---|---|---|
| **R1 — Year mismatch** | The year you typed in the text doesn't match the source in your library (e.g. you wrote 1998, the library says 2001). | Pick the correct year — usually accept the library's, or fix the source. |
| **R2 — Venue looks wrong** | A book resolved to a *review of* the book (e.g. venue "Choice Reviews Online") rather than the book itself. | Re-resolve/replace the source with the actual work. |
| **R3 — Orphaned citation** | A citation points to a source no longer in your library — it would print as an empty marker. | Relink it to the right source, or remove the citation. |
| **R4 — Cited but not listed** | One source inside a grouped citation is missing, so it would drop out of the reference list. | Restore the missing source. |
| **R5 — Listed but not cited** | A reference sits in the list but nothing in the text cites it. | Cite it, or remove it from the list. |
| **R6 — Possible duplicate** | Two library entries look like the same work. | Merge them, or keep both if they're genuinely different. |
| **R7 — Ambiguous author/year** | Two sources share the same author + year with no a/b suffix, so "(Khan, 2019)" is ambiguous. | Add a/b suffixes so each is distinct. |
| **R8 — Cited out of context** | The sentence is about one topic but cites an unrelated source — and a closer source may already be in your library. | Review the suggested source; use it or keep your own. **SANAD suggests, you decide.** |

**R8** is the standout: it reads the *meaning* of your sentence and the source,
not just the words. Its quality is highest when the optional semantic model is
installed; otherwise it uses a lighter word-overlap check (the check tells you
which one ran). It is always **confirm-only** — it never changes a citation on
its own.

Every finding can be **Confirmed** (you accept the fix) or **Dismissed** (you
disagree). A dismissed finding will not nag you again on the next check.

## 8. Citing in Word / LibreOffice

SANAD's editor add-in is a thin companion to the same local Core. From your
document you can:

- **Insert a citation** — search your library, pick a source, and SANAD places a
  correctly-formatted citation as a tracked field.
- **Rebuild the bibliography** — regenerated from the citations actually present.
- **Run the integrity check** — the add-in sends each citation and its
  surrounding sentence to the Core and shows the findings.

**The guarantee:** the add-in only ever writes inside its own citation and
bibliography fields (tagged `sanad-cite` / `sanad-bibliography`). It has no way to
change your sentences. Even if SANAD is closed or uninstalled, your citations
remain as ordinary, readable text — they never turn into broken links.

> The editor add-in is still being finalised for general release. The desktop app
> above works today for building and checking your library and style profiles.

## 9. Your data & privacy

- **Everything is local.** Your library lives in a single file on your machine;
  the Core listens only on `127.0.0.1` and makes no outbound connections.
- **One optional, explicit exception:** if you tick *online lookup* on an import,
  SANAD sends **only the DOIs** of the entries you're importing to Crossref to
  fetch their metadata. Nothing else leaves your machine, and it never happens
  unless you tick the box for that import.
- **No account, no cloud, no telemetry.**
- **Your prose is never read or written** by the Core — it only ever handles
  citation fields and the sentence text you explicitly send for a context check.

## 10. Troubleshooting

**The status light is red / "Core not reachable".**
The engine didn't start. Quit and reopen SANAD. If it persists, another program
may be using port `23890`; close it and retry.

**Import did nothing / imported 0.**
Check the format matches what you pasted (RIS vs BibTeX). A plain numbered list
should use **Typed list**. Typed lists are stored as low-confidence entries
because they lack structured fields.

**A citation shows an integrity flag I disagree with.**
Press **Dismiss** — it won't return on the next check. Integrity findings are
advice, never automatic changes.

**R8 says "semantic check: off" or uses "lexical-hash".**
The optional semantic model isn't installed, so SANAD used the lighter
word-overlap check. It still works but is less sensitive to paraphrased
mismatches.

## 11. FAQ

**Do I need Python or any other software?**
No. The installer bundles everything.

**Does SANAD change my writing?**
Never. It's a hard, code-enforced guarantee — it only touches citation and
bibliography fields.

**Is my data sent anywhere?**
No. SANAD is fully offline and local.

**Can I use it with Zotero/Mendeley/EndNote?**
Yes — export your references as RIS or BibTeX and import them. SANAD works well as
a *verifier* alongside another manager.

**Is it free?**
Yes, and open-source under the AGPLv3.

**Does it support Urdu / right-to-left?**
Urdu and Arabic references render right-to-left, and RTL support is a founding
goal of the project.
