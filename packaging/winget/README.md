# Publishing SANAD to winget (Windows Package Manager)

Once SANAD is on winget, anyone can install/upgrade it with:

```powershell
winget install SANAD
winget upgrade SANAD
```

winget also has its own discovery, and — importantly — it establishes publisher trust, which softens
the SmartScreen "unknown publisher" warning that scares non-technical users off an unsigned `.exe`.

## The easy path (recommended): wingetcreate

`wingetcreate` fills in the installer URL, computes the SHA256, and opens the PR for you.

```powershell
winget install Microsoft.WingetCreate

# Point it at the release asset; it downloads, hashes, and drafts the manifests:
wingetcreate new "https://github.com/sajidmahmoodfarooqi-png/SANAD-thRefGuard/releases/download/v0.2.10/SANAD.Setup.0.2.10.exe" ^
  --identifier SajidMahmoodFarooqi.SANAD

# For a later version, update the existing manifest and submit the PR:
wingetcreate update SajidMahmoodFarooqi.SANAD ^
  --version 0.2.11 ^
  --urls "https://github.com/sajidmahmoodfarooqi-png/SANAD-thRefGuard/releases/download/v0.2.11/SANAD.Setup.0.2.11.exe" ^
  --submit
```

That opens a pull request against **microsoft/winget-pkgs**. A maintainer/bot validates and merges;
then `winget install SANAD` works for everyone.

## The manual path

The three YAML files in this folder are ready templates. For each release, replace `<VERSION>`,
`<URL>`, and `<SHA256>`:

```powershell
# compute the installer hash
Get-FileHash .\SANAD.Setup.0.2.10.exe -Algorithm SHA256 | Select-Object -ExpandProperty Hash
```

Then fork **microsoft/winget-pkgs**, drop the three files under
`manifests/s/SajidMahmoodFarooqi/SANAD/<VERSION>/`, validate, and open a PR:

```powershell
winget validate --manifest manifests/s/SajidMahmoodFarooqi/SANAD/0.2.10
winget install --manifest manifests/s/SajidMahmoodFarooqi/SANAD/0.2.10   # local test
```

## Notes

- **Identifier** `SajidMahmoodFarooqi.SANAD` — keep it stable across versions.
- The installer is **electron-builder NSIS**, per-user scope, silent switch `/S` — reflected above.
- **Code signing** is not required for winget, but a signed installer removes the SmartScreen warning
  entirely. Options: an OV/EV code-signing certificate, or building reputation over time. Publishing
  through winget and/or the Microsoft Store both help with trust in the meantime.
