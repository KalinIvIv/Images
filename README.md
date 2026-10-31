# PhotoCut

Click a button in Chrome on a product page and get its product photos downloaded, cropped,
resized and saved as `<Folder>\<Folder>_1.png, _2.png …` on your PC, usually in a few seconds.
When detection gets a site wrong, you teach it once (point at the gallery, untick logos). The
fix goes into a **shared rules file**, so it works for the whole team.

- **Colleagues:** see [docs/HOW_TO_USE.md](docs/HOW_TO_USE.md).
- **History:** the previous folder-based tool is in [`legacy/`](legacy/), with notes on it in [NOTES.md](NOTES.md).

## How it works

```
Chrome extension (extension/)                    Local app (app/photocut/, PhotoCut.exe)
  detect.js   finds product images +              host.py      native messaging (stdin/stdout JSON)
              highest-resolution URLs             pipeline.py  crop → scale ≤3000 → pad ≥650 → PNG ≤5MB
  picker.js   "Pick gallery area" overlay         rules.py     shared rules.json: safe merge + backup
  popup.js    folder name, image grid, save       naming.py    folder names, numbering, no overwrites
  analyze.js  trim / keep-whole suggestion per
              image (text callouts, scenes)
  background  downloads images (with the          config.py    %APPDATA%\PhotoCut\config.json
              browser's cookies) → streams        install.py   registers the host with Chrome (HKCU)
              them to the local app               cli.py       command line (folder / urls / config)
```

**Detection order:**
1. Team rule (gallery CSS selector, exclude/include URL fragments, URL rewrites, min size).
2. Shopify product JSON (`/products/<handle>.js`).
3. Known shop gallery layouts (WooCommerce, Magento, PrestaShop…).
4. The best-scoring gallery-like container near the top of the page.
5. Structured data (JSON-LD `Product.image`).
6. Large images.

Each image is upgraded to its largest version: `srcset`, zoom/large attributes, and Shopify,
WordPress and Magento size suffixes are stripped. Duplicates at different sizes are merged.

**Trim or keep whole:** when the popup opens, `analyze.js` checks a 480 px copy of each image
in the background worker. If the border isn't a plain background, it's a scene or design and is kept
whole. Rows of small, similar-height shapes mean text or feature callouts, so it's also kept whole.
Anything else is a product shot and gets trimmed. Users can switch the badge per image. Kept-whole
images skip the crop and only get resizing, padding and PNG encoding (`pipeline.process(trim=False)`;
`--no-trim` on the command line).

Rules are keyed by domain without `www.`, so a rule for `lg.com` covers every
localisation. Built-in starter rules are in `extension/rules_builtin.json`; the shared file
overrides them per domain.

## Build and release (Windows)

```bat
installer\build.bat
```
This installs the requirements, runs the tests, builds `PhotoCut.exe` (PyInstaller, one folder) and
packages `release\PhotoCut.zip`, containing the app, the extension, `install.bat`,
`uninstall.bat` and `HOW_TO_USE.md`.

The extension has a fixed ID (`dhmhjgdnpjnnfpajmflglfajjmofnjmg`, from the `key` in
`extension/manifest.json`). The app only accepts connections from that ID.

## Develop and test

```bash
pip install -r requirements.txt
python -m pytest                      # engine, rules, naming, native host protocol
cd tests/e2e && npm install && npm test   # Chromium + extension + host against fake shops
```
The end-to-end test starts `tests/e2e/fixture_server.py`, which serves a Shopify-like store, an LG-like page
and a page that needs the picker. It loads the real extension into Chromium, registers the host
and checks detection, saving, numbering, the picker and the shared rule.

Run the app from source without building: `python -m photocut install` (with `PYTHONPATH=app`)
registers a launcher script instead of the EXE.

## Command line

```
PhotoCut install | uninstall
PhotoCut folder <input folder> <name>          crop images already on disk
PhotoCut urls <name> <image url> [...]         download and crop
PhotoCut config [key=value ...]                show or change settings
```
