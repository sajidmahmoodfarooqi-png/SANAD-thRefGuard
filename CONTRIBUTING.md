# Contributing to SANAD

Thanks for looking! SANAD is early and the most valuable contribution right now is simply
**using it and telling us what breaks** — especially where the integrity checker misses a real
problem or flags a false one.

## Ways to help (no code needed)

- **Run it against a real thesis or paper** and report what the Integrity check catches, misses,
  or over-flags. Concrete before/after examples are gold.
- **Try the [sample pack](examples/)** and tell us if anything is confusing.
- **File issues** for bugs, rough edges, or missing formatting rules for your university's handbook.
- **Suggest Style Profiles** for real university handbooks (APA/Harvard variants, "et al."
  thresholds, spacing) — these are shareable JSON and easy to add.

Please use the issue templates — a version number and steps to reproduce help enormously.

## Running from source

```bash
pip install -r requirements.txt
python -m sanad_core.server     # the local engine on 127.0.0.1:23890
pytest                          # the full suite must stay green
```

The desktop app lives in `app/` (Electron: `cd app && npm install && npm start`), and the Word
add-in in `connectors/word/`. See the README's *For developers* section for the repo layout, and
`MVP_SPEC.md` for the data model, protocol, and the integrity rules (R1–R8).

## Pull requests

- **Keep the tests green** and add a test for any behaviour you change — this project verifies by
  driving the real code path, not by trusting it.
- Match the surrounding style; keep changes focused.
- The **write-boundary guarantee is load-bearing**: nothing may ever write outside SANAD's own
  citation/bibliography fields. There's a fuzz test enforcing it — don't weaken it.
- By contributing you agree your work is licensed under the project's **AGPL-3.0**.

## Reporting a security issue

Please **don't** open a public issue for vulnerabilities — see [SECURITY.md](SECURITY.md).
