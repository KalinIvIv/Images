# Image Auto-Cropper — Code Notes

Notes on the 9 project files: what each one does, how they work together, and where the code and the docs disagree.

## 1. The big picture

A Windows desktop tool for non-technical colleagues. It takes a folder of product photos and, for each one:
- crops away the background,
- fits the result between 650×650 and 3000×3000 px,
- saves it as a PNG under 5 MB.

The Python script does the work. PyInstaller turns it into a single `ImageAutoCropper.exe`. The batch files build the EXE and zip it up to send to colleagues.

```
                developer machine                              colleague's machine
 ┌──────────────────────────────────────────────┐        ┌───────────────────────────┐
 │ requirements.txt ──pip──► Python env         │        │ ImageAutoCropper.exe      │
 │                                              │        │   │ first run: pick folder│
 │ auto_crop.py ──► build_exe.bat ──┐           │        │   ▼                       │
 │                  clean_and_build.bat ──┐     │  ZIP   │ config.json (next to exe) │
 │                                  ▼     ▼     │ ─────► │   │ later runs: reuse     │
 │            PyInstaller (+ .spec) ──► dist/   │        │   ▼                       │
 │                              ImageAutoCropper│        │ crop every image in folder│
 │                                    .exe      │        │   ▼                       │
 │ package_for_distribution.bat ──► Distribution│        │ Windows toast "Complete"  │
 │   (exe + INSTRUCTIONS + config.json.example) │        └───────────────────────────┘
 └──────────────────────────────────────────────┘
```

## 2. File by file

| File | Role |
|---|---|
| `auto_crop.py` | All the logic. Image processing, GUI flow, config handling, CLI mode. |
| `requirements.txt` | Python dependencies: `Pillow>=10`, `pyinstaller>=5`. |
| `build_exe.bat` | Installs PyInstaller if it's missing, then builds a one-file, no-console EXE named `ImageAutoCropper` with `pillow_avif` as a hidden import. |
| `clean_and_build.bat` | Deletes `dist/`, `build/`, `ImageAutoCropper.spec` and `__pycache__/`, then runs the same PyInstaller build. Doesn't check that PyInstaller is installed. |
| `ImageAutoCropper.spec` | The PyInstaller spec that the build commands above generate. It's a **generated file**: `clean_and_build.bat` deletes it and writes a new one, so edits to it are lost. |
| `package_for_distribution.bat` | Checks that `dist\ImageAutoCropper.exe` exists, then copies the EXE, `INSTRUCTIONS_FOR_USERS.txt` and `config.json.example` into a fresh `ImageAutoCropper_Distribution/` folder for zipping. |
| `config.json.example` | Template showing the `{"folder_path": ...}` format. The program never reads it; it only reads `config.json`. |
| `INSTRUCTIONS_FOR_USERS.txt` | End-user guide that ships with the EXE. |
| `README.md` | Developer/user docs: build steps, CLI usage, how the crop works, how to tune shadow removal. |

## 3. How `auto_crop.py` works

### 3.1 Entry point
- **No arguments** (double-clicking the EXE or the script) → `run_gui_mode()`.
- **With arguments** → CLI: `auto_crop.py <input> [output] [tolerance]`. If `<input>` is a folder it calls `process_directory`; if it's a file it calls `process_image`.

### 3.2 GUI flow (`run_gui_mode`)
1. Creates a hidden Tk root window, used only for the dialogs.
2. `load_saved_folder()` reads `config.json`. It looks for the file next to the EXE when frozen (`sys.frozen`) or next to the script otherwise. The saved path is used only if that folder still exists.
3. **If there's no usable saved folder:** shows an info box, opens a folder picker and saves the choice to `config.json`. Cancelling shows a warning and exits.
4. **If there is one:** starts processing straight away, with no dialogs.
5. Runs `process_directory(folder)` with tolerance 30.
6. When done, `show_windows_toast()` starts a hidden PowerShell process that shows a WinRT toast notification (AppID `ArdesPhotoCut`). If nothing was found it shows a "No Images Found" message box; unexpected errors show an error box.

### 3.3 Batch processing (`process_directory`)
- Scans **only the top level** of the folder for `.jpg .jpeg .png .webp .bmp .tiff .avif`. The extension check ignores case.
- With no output folder (which is always the case in GUI mode), **output goes into the input folder itself**.
- Each image is written as `<stem>.png`.
- **After a successful save, any original that isn't a PNG is deleted** (`img_file.unlink()`). This also happens in CLI mode when you give a separate output folder.
- Returns `{total, processed, skipped, output_dir}`.

### 3.4 Per-image pipeline (`process_image`)
```
open ─► auto_crop ─► scale_down_if_needed ─► add_white_padding ─► compress_to_size
```

**Step 1: `auto_crop(img, tolerance=30, alpha_threshold=200)`** uses one of two strategies:

- **A. Transparency.** Used when the image is RGBA, or has `transparency` info, *and* at least one pixel has alpha below 200.
  - Makes a mask of pixels with alpha > 200 and crops to its bounding box.
  - Soft shadows are semi-transparent, so they fall outside the mask and get cropped off.
- **B. Background colour.** Used otherwise.
  - Flattens the image onto white.
  - `get_edge_color()` samples about 20 points along each of the 4 edges and takes the most frequent *exact* RGB value as the background colour.
  - Takes `|image − background|`, converts that to greyscale and thresholds it at `tolerance`.
  - Crops to the bounding box of everything above the threshold.
- Both strategies crop the **original** image, so its colour mode is kept.

**Step 2: `scale_down_if_needed`.** If either side is over 3000 px, shrinks the image in proportion with LANCZOS resampling. It never enlarges.

**Step 3: `add_white_padding`.** If either side is under 650 px, centres the image on a white canvas of `max(w,650) × max(h,650)`. Small images are padded, not enlarged. RGBA images get an *opaque* white canvas.

**Step 4: `compress_to_size` (5 MB limit).** Tries each of these in turn:
1. Optimised PNG. Done if it's ≤ 5 MB.
2. If the image is RGBA: flatten onto white and save as an RGB PNG.
3. JPEG at quality 95, 90, … 10, keeping the first one under 5 MB. **The JPEG is then renamed to `.png`**, so the file is really a JPEG with the wrong extension.
4. If even quality 10 is too big, keeps it anyway and prints a warning.

### 3.5 Config
- `config.json` = `{"folder_path": "..."}`, stored next to the EXE.
- To change folders, delete or edit it. A path that no longer exists sends the user back to the folder picker.

## 4. Docs vs. code: what's out of date

The README and INSTRUCTIONS describe an older version. A colleague following them would be misled on these points:

| Docs say | Code actually does |
|---|---|
| Output goes into an **`output` subfolder** | Output goes **into the same folder**. The GUI's own first-run dialog says so too. |
| "Original images are **NOT modified**" | Non-PNG originals are **deleted**, and PNG originals are **overwritten** in place. |
| Success **dialog auto-closes after 5 s**, has a "Close Now" button, stays on top | It's a **Windows toast notification**. That code isn't there any more. |
| Single file → `input_cropped.jpg` | → `input_cropped.png`. Every output is `.png`. |
| Folder CLI without an output argument → creates `output/` | Writes into the input folder. |
| Supported formats: jpg, png, webp, bmp, tiff | Also **.avif**. `.tif` (one f), `.gif`, `.heic` and `.jfif` are *not* picked up. |
| "Find line ~240" to change `alpha_threshold` | The call is now at line ~264, and the setting can't be changed without editing code. |
| Python **3.7** or higher | `Pillow>=10` needs Python **3.8+**. |
| INSTRUCTIONS: "Contact IT admin to adjust alpha_threshold" | There's no setting for it. Someone has to edit the code and rebuild. |

## 5. Problems and risks (most serious first)

I confirmed items marked ✅ by running the code with test images.

1. ✅ **Data loss from name collisions.** `photo.jpg` and `photo.webp` both become `photo.png`. The second overwrites the first, and **both originals are deleted**. One product photo is lost for good.
   - Same with `photo.jpg` next to an existing `photo.png`: the PNG is overwritten, then processed again.
2. **Originals are destroyed by design.** There's no backup, and it happens even when an output folder is given in CLI mode. Combined with the docs promising "originals are NOT modified", this is the most likely thing to cause a real incident.
3. **Every run processes everything again.** Outputs sit next to the inputs as PNGs, so the next run crops them again. That's mostly harmless for clean PNGs, but files that took the JPEG fallback lose quality on every run.
4. ✅ **Colours the background check can't see.** The colour difference is reduced to greyscale brightness, which counts blue at only ~11%. A yellow object (255,255,0) on white differs only in the blue channel, giving a value of ~29, which is under the tolerance of 30. Result: **yellow, pale-cyan and other light products on white aren't cropped at all.**
5. ✅ **One stray pixel ruins the crop.** The bounding box takes in *any* pixel above the threshold. A single dust speck, watermark, border line or vignette near the edge stops the crop. In my test, one dark pixel turned a 401 px crop into 696 px.
6. **Edge colour = most frequent exact value.** It's fragile on noisy JPEG backgrounds and gradients, where almost every sample is unique, so the "background" may be one random sample.
7. **JPEG saved with a `.png` extension.** Some upload portals, marketplaces and tools check the file contents or reject the mismatch.
8. **The toast may never appear.** On Windows 10/11, toasts from an AppID that isn't registered (`ArdesPhotoCut` has no Start-menu shortcut) are often dropped silently. The EXE is built `--noconsole`, so the user may get **no feedback at all**. Errors on individual images are only `print`ed, and those prints go nowhere in a no-console EXE.
9. **No progress indication.** A big batch runs with nothing on screen. Users may double-click again and start a second process on the same folder, and the two will race on overwrites and deletes.
10. **Photo rotation (EXIF) is ignored** (no `ImageOps.exif_transpose`). Phone photos can come out sideways. EXIF data and ICC colour profiles are also dropped.
11. **Mixed transparent/white output.** A transparent image that gets padded ends up as a transparent object on an opaque white canvas.
12. **Colour modes aren't normalised.** The crop keeps the original mode, so palette (`P`), `LA` and `CMYK` images go down unusual paths. For example, a `P`-mode image can't be saved as JPEG if it ever reached the fallback, and `LA` loses its alpha when converted to RGB.
13. **`config.json` must sit somewhere writable.** If the EXE is put in `Program Files`, saving fails silently and the folder picker appears every time.
14. **Very large images (> ~179 MP)** trigger Pillow's decompression-bomb protection and are skipped.
15. **No subfolders.** Only the top level of the chosen folder is processed.

## 6. Build and packaging notes

- **`requirements.txt` is missing `pillow-avif-plugin`**, which the code and both build scripts reference.
  - If it isn't installed, PyInstaller only warns about the hidden import, and the code's `try/except ImportError` hides the problem.
  - Note: recent Pillow (I checked 12.3) **supports AVIF natively** (`features.check('avif') == True`). On a current Pillow the plugin and the hidden import can probably be dropped.
- `build_exe.bat` installs PyInstaller only. It doesn't run `pip install -r requirements.txt`, so a fresh machine can end up with no Pillow.
- `clean_and_build.bat` deletes the `.spec` file and builds a new one. Treat the spec as generated, or switch the scripts to build *from* the spec if custom settings are ever needed.
- `upx=True` in the spec: if UPX is installed, the compressed one-file no-console EXE is more likely to be flagged by antivirus. That's worth knowing when sending it to colleagues.
- `--icon=NONE` / `icon='NONE'` means "no icon". It isn't a missing file.
- The package contains `config.json.example` but not `config.json`, which is correct: each user's first run creates their own.

## 7. Suggested fixes (if you want to take this further)

1. Write outputs to an `output/` subfolder (matching the docs) and **stop deleting originals**, or move them to an `originals/` folder instead.
2. Name outputs from the full filename (`photo.jpg` → `photo_jpg.png`) or detect collisions and add a number.
3. Skip files that were already processed, which comes free once outputs live in their own folder.
4. Compare background distance per channel (`max` of the R/G/B differences) instead of greyscale brightness, and ignore small specks before taking the bounding box, e.g. with a small `ImageFilter.MinFilter` or by requiring a minimum area.
5. Apply `ImageOps.exif_transpose` on load, and convert to RGB/RGBA up front.
6. Replace the toast with a small Tk window that shows progress and closes itself, as the docs already describe. Write a log file next to the EXE.
7. Make `tolerance` and `alpha_threshold` optional keys in `config.json`.
8. Update `requirements.txt` and the build scripts (`pip install -r requirements.txt`). Bring README and INSTRUCTIONS up to date with the behaviour above.
