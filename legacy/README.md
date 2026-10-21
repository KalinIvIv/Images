# Image Auto-Cropper

Automatically crops images by detecting and removing background color from edges.

## Features

- **Smart cropping**: Removes backgrounds AND shadows to isolate the main object
- Auto-detects edge/background color and crops it out
- Maintains aspect ratio (images don't need to be square)
- Adds white padding if cropped image is smaller than 650x650
- Scales down proportionally if larger than 3000x3000
- **All output images saved as PNG** for maximum quality
- Compresses to keep file size under 5MB
- Supports batch processing of entire directories
- **GUI Mode**: Just double-click to select folder and process images!
- **Remembers folder**: Set once in `config.json`, auto-runs every time!
- **Auto-closing dialogs**: Success message auto-closes after 5 seconds

## Quick Start (For Non-Programmers)

### Option 1: Build Executable (Recommended)

1. Install Python 3.7 or higher from https://www.python.org/downloads/
2. Double-click `build_exe.bat`
3. Wait for the build to complete
4. Find `ImageAutoCropper.exe` in the `dist` folder
5. Double-click `ImageAutoCropper.exe` to run!

When you run the EXE:
- **First time**: Select the folder containing your images
  - This folder path will be saved in `config.json`
- **Next times**: Automatically uses the saved folder (instant start!)
  - No dialogs, just processes images immediately
- The program will process all images and save them in an `output` subfolder
- A success message will appear on top of all windows
- **Auto-closes in 5 seconds** (or click "Close Now" to dismiss immediately)

**To change folder**:
- Option 1: Delete `config.json` and run the EXE again to select a new folder
- Option 2: Edit `config.json` manually (see `config.json.example` for format)

**Note**: The `config.json` file is created next to the executable.

### Option 2: Run Python Script Directly

1. Install Python 3.7 or higher
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Double-click `auto_crop.py` (or run `python auto_crop.py`)
4. Select folder with images when prompted
5. Processed images will be in the `output` subfolder

## Usage

### GUI Mode (No arguments):

```bash
python auto_crop.py
```

This will open a folder selection dialog. Select your folder and images will be saved in `output` subfolder.

### Command-Line Mode

#### Process a single image:

```bash
python auto_crop.py input.jpg
```

Output will be saved as `input_cropped.jpg` in the same directory.

#### Specify output path:

```bash
python auto_crop.py input.jpg output.jpg
```

#### Process entire directory:

```bash
python auto_crop.py ./input_folder ./output_folder
```

If output folder is not specified, it will create an `output` subfolder inside the input folder.

### Adjust color tolerance:

```bash
python auto_crop.py input.jpg output.jpg 40
```

Tolerance value (0-255) controls how similar colors need to be to the edge color to be cropped. Higher values = more aggressive cropping. Default is 30.

## Examples

```bash
# Single image with default settings
python auto_crop.py photo.jpg

# Single image with custom output and higher tolerance
python auto_crop.py photo.jpg result.jpg 50

# Batch process all images in a folder
python auto_crop.py ./raw_photos ./processed_photos

# Batch process with higher tolerance
python auto_crop.py ./raw_photos ./processed_photos 45
```

## How It Works

1. **Smart crop**:
   - For PNG images with transparency: Uses alpha channel to detect only the solid object (ignores shadows)
   - For other images: Detects and removes background color
   - Result: Clean crop with only the main object, no shadows or halos
2. **Scale down**: If image exceeds 3000x3000, scales down proportionally
3. **Add padding**: If image is smaller than 650x650, centers it on white background
4. **Save as PNG**: Saves as optimized PNG for maximum quality
5. **Compress if needed**: If file exceeds 5MB, converts to JPEG (still saved with .png extension)

## Supported Input Formats

The script accepts images in these formats:
- JPEG (.jpg, .jpeg)
- PNG (.png)
- WebP (.webp)
- BMP (.bmp)
- TIFF (.tiff)

**Note**: All output images are saved as PNG format regardless of input format.

## Advanced: Fine-tuning Shadow Removal

By default, the script uses an alpha threshold of **200** (out of 255) to distinguish the main object from shadows. This removes most soft shadows and drop shadows.

If you want to adjust this:
1. Open `auto_crop.py` in a text editor
2. Find line ~240: `img = auto_crop(img, tolerance=tolerance)`
3. Change to: `img = auto_crop(img, tolerance=tolerance, alpha_threshold=150)`
   - Lower values (100-150) = More aggressive, removes more shadow but might cut into semi-transparent parts
   - Higher values (220-250) = Less aggressive, keeps more of the image including some shadows
   - Default (200) = Good balance for most product photos
