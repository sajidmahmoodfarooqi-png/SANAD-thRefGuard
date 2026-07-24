# SANAD the RefGuard — Core

**SANAD** (سند — Arabic/Urdu for a *chain of authority*, and for a certificate or proof) is an
open-source, local-first citation companion for MS Word and LibreOffice. It goes beyond formatting
to check whether each citation is *actually right* — the right source, cited in the right place —
and it never touches a word of your prose.

This repository holds the **Core**: the local engine and service the word-processor add-ins talk
to. It runs entirely on your machine; there is no account and no cloud.

## What makes it different

- **Context-integrity checking.** After a citation *looks* right, SANAD checks whether it *is*
  right: wrong in-text year, a book resolved to a review venue, orphaned/duplicate references,
  author-year ambiguity (Tier-A rules R1–R7), and — with a local embedding model — a reference
  cited in the wrong context, with a better-matching source suggested from your own library
  (Tier-B, R8).
- **Handbook-driven formatting.** A university's formatting rules become a shareable *Style
  Profile* (`.sanadstyle.json`) — indent, "et al." threshold, ampersand rule, spacing — layered
  over a real CSL style.
- **The Text Integrity Guarantee.** SANAD only ever writes inside its own citation and
  bibliography fields. The boundary is enforced in code and proven by a fuzz test, not just
  promised.
- **Bilingual by design.** First-class right-to-left / Urdu support.

## Repository layout

| Path | What it is |
|---|---|
| `sanad_core/` | The Core: SQLite library, RIS/BibTeX/typed import, CSL rendering, Style Profiles, the Tier-A/Tier-B integrity engine, the document-model write boundary, and the local HTTP + WebSocket service. |
| `tests/` | The pytest suite. All sample data is small and invented — the suite carries no real bibliography. |
| `CONCEPT.md` | The product vision. |
| `MVP_SPEC.md` | The Phase-1 technical spec (data model, protocol, rules, Style Profile format). |
| `LICENSE` | GNU AGPLv3. |
| `requirements.txt` | Runtime + dev dependencies. |

## Quick start

```bash
pip install -r requirements.txt
python -m pytest            # run the test suite
python -m sanad_core.server # start the local Core service on 127.0.0.1:23890
```

The Tier-B semantic check uses a local sentence-transformers model when installed and degrades to
a deterministic lexical fallback otherwise; the scan reports which backend actually ran.

## License

GNU Affero General Public License v3.0 — see [LICENSE](LICENSE).
