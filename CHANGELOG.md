# Changelog

Notable changes per release. Full user-facing notes are in
[RELEASE_NOTES.md](RELEASE_NOTES.md) and on the
[Releases page](https://github.com/sajidmahmoodfarooqi-png/SANAD-thRefGuard/releases).
This project uses semantic-ish `vMAJOR.MINOR.PATCH` tags; each tag builds and publishes a Windows
installer via CI.

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
