# SANAD the RefGuard — Concept & Vision

> **سند** (Arabic/Urdu): *attestation; the chain of authority that vouches for a source.*
> **Wordmark:** **سند the RefGuard** — the Arabic/Urdu **سند** (calligraphic) paired with a
> clean Latin **RefGuard**; the mark fuses a *shield / checkmark* ("guard") with the
> *chain-of-attestation* meaning of سند.
> **Tagline:** *Cite what you actually mean.*
> **License:** AGPLv3.

An **open-source, local-install** citation companion for word processors that does what
Zotero, Mendeley, and EndNote do not: it verifies that each citation's source genuinely
supports the claim it is attached to — catching out-of-context and wrong references, and
proposing the correct one — and formats everything to the *specific* rules of the user's own
university, not just a generic public style.

> ## Core guarantees (non-negotiable)
> 1. **SANAD never alters, rewrites, or "corrects" the author's own prose.** It touches only
>    citation markers, reference-list entries, and explicitly-defined structural style elements
>    (per a confirmed Style Profile) — never the argument itself. This is a hard boundary, not
>    a setting, and it exists specifically so that using SANAD can never introduce a similarity-
>    or AI-detection flag into the author's writing.
> 2. **Formatting is scoped to a Style Profile derived from the user's own university handbook**
>    where one is supplied — not a one-size-fits-all guess at "APA" or "Harvard."

---

## 1. The problem

Every existing reference manager assumes the reference you attached is the correct one. They
manage, insert, and format — they never check the *substance*. Real-world failures this leaves
in place (all observed while building this project's workflow):

- A same-surname, same-year **wrong paper** (a paper from an unrelated field cited for a claim
  it has nothing to do with, simply because author surname and year matched).
- Metadata engines binding a **book to its book-review**, or to an unrelated title entirely.
- **Broken/orphaned citations** (dead EndNote `_ENREF_` links) no "Insert Bibliography"
  command can resolve.
- **Cited-but-not-listed** and **listed-but-never-cited** mismatches between text and
  reference list.

And separately, but just as painfully: **formatting itself is a major headache for
researchers.** Generic "APA 7th" or "Harvard" rarely matches a university's actual thesis
handbook exactly — hanging-indent size, DOI display, heading numbering, spacing, margins.
Researchers currently reconcile this by hand, every draft, often catching mismatches only at
submission.

Thousands of researchers hit these, discover them late (or never), and pay for it at
examination or peer review. That is the gap SANAD fills.

## 2. Vision & principles

- **Text Integrity Guarantee.** SANAD never edits, rewrites, paraphrases, or "corrects" prose.
  It only ever modifies citation markers, reference-list entries, and structural formatting
  explicitly defined in a confirmed Style Profile. This is enforced everywhere in the product,
  including the semantic context-checker (§3) — a suggestion is always shown, never
  auto-applied.
- **Local-first & private.** The manuscript never leaves the machine. Only bare identifiers
  (a DOI, a title) are ever sent to a metadata service, and only with consent. Critical for
  unpublished theses and sensitive research.
- **Open source.** A public good for the research community, built on open standards.
- **Word-first, universal by design.** One local core; thin add-ins per word processor. MS
  Word (the market reality) is the flagship; LibreOffice and others share the same engine.
- **Human-in-the-loop.** SANAD *flags and proposes*; it never silently swaps a source or a
  formatting rule.
- **Standards over reinvention.** Citation Style Language (CSL) for formatting → 10,000+
  styles, including RTL/Arabic ones, as the base layer under every Style Profile.

## 3. Differentiator #1: Context Integrity

Two tiers, both in v1.0.

**Tier A — Deterministic integrity checks (high precision, ship day one):**
- Wrong-year / wrong-edition detection (in-text year vs. resolved metadata).
- Metadata sanity: book-vs-review, journal-vs-book, corporate-author reports.
- Orphaned / broken / field-remnant citations (e.g. EndNote `_ENREF_`).
- Cited-not-listed vs. listed-not-cited reconciliation.
- Duplicate and near-duplicate reference detection.
- Author/year disambiguation using the surrounding context.

**Tier B — Semantic context check (the flagship, assistive):**
1. Read the **claim** (the citing sentence + neighbours) — read-only, never modified.
2. Pull the cited source's **fingerprint** (title, abstract, keywords, venue).
3. Score **topical alignment** with a **local, offline, multilingual** embedding model.
4. On misalignment: flag a **possible miscite** with a confidence band, and surface
   **ranked better-matching sources** (from the user's library first, then open literature),
   shown side-by-side with the claim. The user confirms — always. SANAD never replaces a
   citation, or any surrounding text, on its own.

## 4. Differentiator #2: University Handbook Compliance

The second pillar, and — per direct researcher feedback — possibly the bigger everyday relief.
No existing tool formats to a *specific university's* thesis handbook; they only offer generic
public CSL styles.

**Strict scope — what this module is allowed to touch:**
- In-text citation format (ordering, punctuation, `&`/"and", `et al.` threshold).
- Reference-list entry format, ordering, and hanging indents/spacing.
- Opt-in, explicitly-flagged document structure: margins, font/size, line spacing, heading
  numbering, table/figure caption style, TOC style, page numbering.
- **Never** the body prose, argument, or wording — enforced by the Text Integrity Guarantee
  (§2) with no override.

**How it works:**
1. The user supplies their university's thesis/dissertation formatting handbook (PDF/DOCX).
2. SANAD parses it and proposes a candidate **Style Profile**: the nearest base CSL style plus
   the specific deltas that matter (indent size, DOI display, date format, etc.), and — if the
   user opts in — the structural rules above.
3. **Every extracted rule is shown to the user for confirmation or edit before it is ever
   applied** — the same human-in-the-loop principle as the semantic tier. Handbook parsing is
   assistive; the user's confirmation is what makes a rule active.
4. The confirmed Style Profile is saved as a small, portable file (a JSON/YAML layer on top of
   CSL) that can be reused across drafts and chapters — and shared.
5. **Community Style Profile library (open-source hook):** once verified, a Style Profile can
   be published back to a public, open repository — e.g. "Metropolitan University Thesis Format
   2026." The next student at that university imports it directly and skips the whole exercise.
   This turns one person's one-time effort into a standing public good, which is exactly the
   "thousands of researchers, same anxiety" problem this project set out to relieve.

## 5. MVP (v1.0) scope — "the reliable one that also catches mistakes"

**In:**
- Library import (RIS / BibTeX / CSV / XLSX / typed list) → clean, dedupe, normalize.
- Metadata resolver (Crossref / OpenAlex) with confidence + Tier-A sanity checks.
- **MS Word add-in** (Office.js): insert citation, build/refresh bibliography — reliable,
  local, offline-capable.
- CSL formatting engine, **APA 7th** first (correct `&` / `et al.` / alphabetical grouping /
  hanging indents), any CSL style thereafter.
- **Style Profile (manual, v1.0):** a guided form for building a university-specific profile by
  hand (base CSL style + deltas) — the mechanism ships in v1.0, even before automated handbook
  parsing lands.
- **Integrity panel**: all Tier-A checks + Tier-B semantic flags (labelled assistive).
- **Text Integrity Guarantee enforced at the engine level** — the formatter has no code path
  that writes outside citation/reference/style-profile regions.
- Local SQLite library; network only for opt-in metadata lookups.

**Out (later phases):** automated handbook-document parsing, full RTL polish, LibreOffice/other
add-ins, cloud sync.

## 6. Roadmap

- **v1.0 — MVP:** reliable MS Word formatter + Tier-A integrity + Tier-B semantic (assistive) +
  manually-authored Style Profiles + the Text Integrity Guarantee.
- **v1.x — Reach:** **automated handbook-document parsing** into a candidate Style Profile
  (human-confirmed); the **community Style Profile library**; LibreOffice (UNO/Python) add-in;
  full **RTL / Urdu / Arabic** support; My-Library PDF matcher; legal open-access full-text
  finder.
- **v2.0 — Depth:** stronger semantic retrieval & ranked auto-suggestions; collaborative /
  team libraries (still local-first); more processors (Google Docs bridge, LaTeX).

## 7. Architecture

```
┌──────────────────────────┐      localhost (127.0.0.1)     ┌─────────────────────────┐
│  SANAD Core (local app)  │◄───────────────────────────────►│  Word add-in (Office.js)│
│  • SQLite library        │                                 │  LibreOffice add-in     │
│  • resolver + CSL engine │                                 │  (UNO/Python)           │
│  • integrity + context   │                                 │  → insert / check panel │
│  • Style Profile engine  │                                 │  → handbook import UI   │
└──────────────────────────┘                                 └─────────────────────────┘
        ▲ opt-in, user-controlled
        └── metadata APIs: Crossref · OpenAlex · Unpaywall · Semantic Scholar · CORE
```

A background local app owns the library and does the work; thin per-processor add-ins talk to
it over `localhost` (the proven Zotero pattern). Everything works offline except opt-in
metadata lookups.

## 8. Tech stack (grounded in the existing scripts)

- **Core:** Python (already the project's language), packaged as a local service.
- **Store:** SQLite.
- **Formatting:** CSL (citeproc) — open standard, 10k+ styles — as the base layer under every
  Style Profile.
- **Handbook parsing:** structured document extraction (headings/tables in the handbook
  PDF/DOCX) proposing Style Profile deltas — always human-confirmed, never auto-applied.
- **Metadata:** Crossref, OpenAlex, Unpaywall, Semantic Scholar, CORE.
- **Semantic engine:** small **local** multilingual sentence-embedding model (CPU, offline).
- **Word add-in:** Office.js (Windows/Mac/Web, Microsoft's supported path).
- **LibreOffice:** UNO / Python.
- **Packaging:** one-click installers for Windows / macOS / Linux.

A set of earlier standalone prototype scripts (DOI/metadata resolution, PDF matching, and APA
in-text conversion logic) were a working head start on much of the core; that logic now lives,
generalized, inside `sanad_core/`.

## 9. RTL & multilingual

- Full bidirectional handling; correct Urdu/Arabic/Persian citations and reference lists,
  including mixed LTR/RTL lines (an English reference inside an Urdu paragraph).
- RTL-aware CSL styles and reference ordering, and RTL-aware Style Profiles (§4).
- Cross-script author/work matching (transliteration-aware).
- The semantic engine is multilingual, so context-checking works on RTL text too — something
  no incumbent attempts.

## 10. Open-source plan

- **License: AGPLv3** (decided) — keeps the tool *and* any network/derivative improvements
  open, matching the public-good goal; same family Zotero uses.
- **Governance:** public repo, contribution guide, issue templates, semantic versioning.
- **Community hooks:**
  - Context integrity (§3) is a natural rallying point — academics who have been burned by
    miscites are the built-in early adopters.
  - The **community Style Profile library** (§4) is a second, very concrete hook: a public,
    contributable repository of verified university formatting profiles. Low effort to
    contribute (confirm a parsed handbook once), high, compounding value to every future
    student at that institution.
- **Sustainability:** free core; optional institutional support/hosting later — never a
  subscription lock-in on the local tool.

## 11. Competitive position

| Capability | Zotero | Mendeley | EndNote | **SANAD** |
|---|:--:|:--:|:--:|:--:|
| Manage & format citations | ✓ | ✓ | ✓ | ✓ |
| Local-first / offline / private | ✓ | ~ | ✓ | ✓ |
| **Detect out-of-context / wrong citation** | ✗ | ✗ | ✗ | **✓** |
| **Suggest the correct source for the claim** | ✗ | ✗ | ✗ | **✓** |
| Repair broken / orphaned citations | ✗ | ✗ | ~ | ✓ |
| **Format to your specific university handbook** (not just generic public styles) | ✗ | ✗ | ✗ | **✓** |
| **Shared community library of verified university styles** | ✗ | ✗ | ✗ | **✓** |
| First-class RTL / Urdu | ~ | ~ | ~ | ✓ |
| Explicit guarantee it never touches your prose | n/a | n/a | n/a | **✓ (stated, enforced)** |

## 12. Related work & differentiation

Validating whether a citation actually fits its claim is an emerging research direction; SANAD
is distinct as a **local, private, word-processor-native product** rather than a cloud/LLM
research pipeline.

- **CiteGuard** (arXiv:2510.17853, 2025) — retrieval-augmented validation of citation
  attribution for LLM-generated text; can propose alternative citations. Closest in spirit to
  SANAD's semantic tier, but a research system built around large language models and online
  retrieval. SANAD differs on every product axis: runs **locally/offline**, plugs into **MS
  Word / LibreOffice**, pairs the check with **reliable, handbook-aware formatting**, keeps a
  **human in the loop**, guarantees it **never touches prose**, and is **RTL /
  multilingual-first**. (This name proximity is exactly why we are *not* "CiteGuard.")
- **RefChecker** (Russinovich, GitHub) — validates references in AI-generated text for
  hallucination; a different problem (fabricated refs) on a different surface (not a
  word-processor companion).
- **Zotero / Mendeley / EndNote** — manage, insert, and format citations to generic public
  styles; none assess whether a source supports the claim it is attached to, and none adapt to
  a specific university's own handbook.

**SANAD's wedge = citation-context integrity + handbook-faithful formatting + a hard
never-touch-your-prose guarantee + local privacy + RTL,** in one word-processor-native, open
tool.

## 13. Honest challenges

- The **semantic tier is the hard science**: flagging a mismatch is achievable; auto-finding
  the perfect replacement is open-ended retrieval and must stay human-confirmed. Over-promising
  here is the main risk — hence the deterministic Tier-A carries v1.0's reliability.
- **Handbook parsing will be imperfect.** University handbooks vary wildly in structure (prose
  rules, tables, sample pages, inconsistent numbering). Extraction must be treated as a
  first-draft proposal, always confirmed by the user — never trusted blindly, exactly like the
  semantic tier.
- The **Word add-in is the heaviest engineering** — the same surface that's flaky in incumbents.
- **Abstract/full-text coverage** for the semantic check varies by discipline and OA access.
- **Not a weekend build** — but the existing scripts cover a real slice of the core, and the
  key insight is already prototyped by this project's own workflow.

## 14. Naming & brand

- **Name (decided): SANAD the RefGuard.** "SANAD" (سند) carries the meaning — attestation /
  chain of authority — for Arabic/Urdu readers; "the RefGuard" makes the function instantly
  clear in English. The combined mark is more distinctive (and more protectable) than either
  half alone.
- **Wordmark:** سند (calligraphic Arabic/Urdu) + **RefGuard** (clean Latin), a bilingual
  identity that mirrors the tool's RTL-first stance.
- **Trademark note (not legal advice):** a preliminary web search found no existing "RefGuard"
  citation/reference product. Before any public launch or commercial angle, run a proper
  clearance across USPTO, EUIPO, WIPO Global Brand Database, and IPO-Pakistan, and consider
  brief IP counsel. Names are protected by **trademark**, not copyright. Note the unrelated,
  differently-named tool *RefChecker* (AI-reference validation) to keep positioning distinct.

---

*This document is the founding vision. Next artifacts: a Phase-1 MVP technical spec (including
the Style Profile file format), the Word-add-in ↔ core protocol, the semantic-engine design,
and a logo/brand kit for the **سند the RefGuard** wordmark.*
