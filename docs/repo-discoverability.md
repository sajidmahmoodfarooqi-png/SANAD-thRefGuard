# Make the repo findable (2-minute setup)

The repo currently has **no description, no topics, and no website** set — these are the fields
GitHub search, Google, and the sidebar rank on. Set them once.

## Option A — one command (GitHub CLI)

```bash
gh repo edit sajidmahmoodfarooqi-png/SANAD-thRefGuard \
  --description "Local-first citation companion for Microsoft Word — checks that each citation is actually right (right source, right year, right place), and never touches your prose. Free & open source." \
  --homepage "https://sajidmahmoodfarooqi-png.github.io/SANAD-thRefGuard/" \
  --add-topic citation --add-topic references --add-topic bibliography --add-topic apa \
  --add-topic academic-writing --add-topic thesis --add-topic reference-manager \
  --add-topic word-addin --add-topic zotero-alternative --add-topic local-first \
  --add-topic research-tools --add-topic electron --add-topic python --add-topic fastapi
```

(Install the CLI from https://cli.github.com and run `gh auth login` first.)

## Option B — in the web UI

1. Repo home → click the **⚙ gear** next to *About* (top-right).
2. **Description**: paste the sentence above.
3. **Website**: `https://sajidmahmoodfarooqi-png.github.io/SANAD-thRefGuard/`
4. **Topics**: add `citation`, `references`, `bibliography`, `apa`, `academic-writing`, `thesis`,
   `reference-manager`, `word-addin`, `zotero-alternative`, `local-first`, `research-tools`,
   `electron`, `python`, `fastapi`.
5. Tick **Releases** and **Packages** so they show in the sidebar.

## While you're in Settings

- **Enable Discussions** (Settings → Features → Discussions) — a low-barrier place for non-developer
  users to ask questions and leave feedback. The issue templates already link to it.
- Consider turning **Wiki** off (it's empty) to reduce clutter.
- Confirm **GitHub Pages** is serving from the `gh-pages` branch (Settings → Pages).
