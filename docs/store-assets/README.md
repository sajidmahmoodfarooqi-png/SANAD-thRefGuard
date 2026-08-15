# Store assets (ready to upload)

Drop-in assets for the Microsoft AppSource / Partner Center submission. Dimensions match Partner
Center's requirements, so they upload without cropping.

| File | Dimensions | Use in Partner Center |
|---|---|---|
| `logo-300.png` | 300×300 | Store logo / app icon |
| `screenshot-1-desktop-1366x768.png` | 1366×768 | Screenshot 1 (the desktop app) |
| `screenshot-2-word-addin-1366x768.png` | 1366×768 | Screenshot 2 (the Word add-in, integrity findings) |

Regenerate from the source screenshots in `../screenshots/` and the medallion in
`../../assets/branding/` if the UI changes. The listing text to pair with these is in
[`../AppSource-listing-copy.md`](../AppSource-listing-copy.md).
