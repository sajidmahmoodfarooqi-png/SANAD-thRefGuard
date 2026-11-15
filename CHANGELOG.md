# Changelog

Notable changes per release. Full user-facing notes are in
[RELEASE_NOTES.md](RELEASE_NOTES.md) and on the
[Releases page](https://github.com/sajidmahmoodfarooqi-png/SANAD-thRefGuard/releases).
This project uses semantic-ish `vMAJOR.MINOR.PATCH` tags; each tag builds and publishes a Windows
installer via CI.

## [0.2.13] — diagnostic audit: crash, data-loss and import fixes
Full findings: [docs/AUDIT.md §9](docs/AUDIT.md). 43 new regression tests (suite 218 → 261).
- **Fixed failures:** the integrity check on a document with an unrecorded citation control;
  "Update reference list" after deleting a flagged citation in Word; deleting a style profile a
  document uses; imports stopped by one odd row (year "n.d.", missing title); unreadable `.xls` files.
- **No more lost references:** different Urdu titles, and different works sharing a generic title
  ("Introduction", "Editorial"), are no longer auto-merged as duplicates; re-importing a sparse row no
  longer blanks a complete record; the demo check leaves nothing behind in the library.
- **Imports read more:** RIS with a byte-order mark and `A1`/`JO`/`JF` tags; BibTeX `@string`,
  "and others", `--` page ranges; `1)` / `[1]` / un-numbered typed lists; Excel-saved and
  `;`-separated CSV; reference-list-style author cells; Windows-1252 / UTF-16 text files.
- **Style & Urdu:** the "use 'and' instead of '&'" option now works; the context check reads Urdu
  text instead of flagging every Urdu citation, and stays silent where it cannot judge.
- **Word add-in:** inserting a citation can no longer replace highlighted text; the profile's line
  spacing is applied to the reference list.
- **Desktop app:** the window opens at once and says the engine is starting (the packaged Core takes
  ~50 s to answer; the app used to wait 25 s with no window, then show "Core not reachable").
- **API:** `DELETE /v1/documents/{id}`; `POST /v1/library/import` also returns the `ids` it created.

## [0.2.10] — the seal is the icon now, and you can see it
- The ornate SANAD seal (set into a solid gold-rimmed medallion so it stays visible on any
  background and at small sizes) is now the Desktop/Taskbar icon and the in-app identity.

## [0.2.9] — visible icon, working author search, findable bibliography
- Author search matches each word across title, journal, author and year (handles "et al." + year).
- The Word add-in's reference-list tab is renamed **Bibliography** and is easier to find.

## [0.2.8] — the Word add-in connects to the Core again
- Fixed CORS + Private Network Access so the add-in (hosted on GitHub Pages) can reach the local Core
  instead of falsely reporting "Core not running".

## [0.2.7] — connect-to-Word on the Home screen; import surfaces duplicates
## [0.2.6] — build a library from a plain list of titles (never auto-picks)
## [0.2.5] — Library Health, boot-stats fix, malformed-import guard, manifest fix
## [0.2.4] — one-step, persistent Word connection
## [0.2.0] — thesis formatting, the Word add-in, and integrity fixes

[0.2.10]: https://github.com/sajidmahmoodfarooqi-png/SANAD-thRefGuard/releases/tag/v0.2.10
[0.2.9]: https://github.com/sajidmahmoodfarooqi-png/SANAD-thRefGuard/releases/tag/v0.2.9
[0.2.8]: https://github.com/sajidmahmoodfarooqi-png/SANAD-thRefGuard/releases/tag/v0.2.8
