#!/usr/bin/env python3
"""
Image Auto-Cropper
Automatically crops images by detecting and removing background color from edges.
Constraints:
- Min resolution: 650x650 (adds white padding if needed)
- Max resolution: 3000x3000 (scales down if needed)
- Max file size: 5MB (compresses if needed)
"""

from PIL import Image, ImageChops
try:
    import pillow_avif
except ImportError:
    pass
import os
import sys
import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox


def get_edge_color(img):
    """
    Detect the dominant edge color by sampling corners and edges.
    Returns the most common color from the image borders.
    """
    width, height = img.size

    # Sample pixels from all four edges
    edge_pixels = []

    # Top and bottom edges
    for x in range(0, width, max(1, width // 20)):
        edge_pixels.append(img.getpixel((x, 0)))  # Top
        edge_pixels.append(img.getpixel((x, height - 1)))  # Bottom

    # Left and right edges
    for y in range(0, height, max(1, height // 20)):
        edge_pixels.append(img.getpixel((0, y)))  # Left
        edge_pixels.append(img.getpixel((width - 1, y)))  # Right

    # Find most common color
    color_counts = {}
    for pixel in edge_pixels:
        # Convert to tuple if it's a single value (grayscale)
        if isinstance(pixel, int):
            pixel = (pixel,)
        color_counts[pixel] = color_counts.get(pixel, 0) + 1

    # Return the most common color
    return max(color_counts, key=color_counts.get)


def auto_crop(img, tolerance=30, alpha_threshold=200):
    """
    Automatically crop image by removing background and shadows.
    Focuses on the primary object only.

    Args:
        img: PIL Image object
        tolerance: Color difference tolerance (0-255) for RGB images
        alpha_threshold: Alpha threshold (0-255) for RGBA images.
                        Pixels with alpha below this are treated as background/shadow.
                        Default 200 removes soft shadows. Use 128 for more aggressive cropping.

    Returns:
        Cropped PIL Image object
    """
    # Keep reference to original image
    original_img = img.copy()
    original_mode = img.mode

    # Ensure we have RGB or RGBA
    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGBA')

    # Strategy 1: If image has alpha channel, use it to detect the object
    if img.mode == 'RGBA' or 'transparency' in img.info:
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        # Extract alpha channel
        alpha = img.split()[3]

        # Only use alpha strategy if there's actual transparency to work with.
        # If all pixels are fully opaque, fall through to RGB edge detection instead.
        if min(alpha.getdata()) < alpha_threshold:
            bbox = alpha.point(lambda p: 255 if p > alpha_threshold else 0).getbbox()
            if bbox:
                return original_img.crop(bbox)

    # Strategy 2: For RGB images (no alpha), use enhanced edge detection
    # Convert to RGB for processing
    rgb_img = img
    if img.mode == 'RGBA':
        # Create white background for comparison
        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
        rgb_img.paste(img, mask=img.split()[3])
    elif img.mode != 'RGB':
        rgb_img = img.convert('RGB')

    # Get the edge color
    edge_color = get_edge_color(rgb_img)

    # Create a background image with the detected edge color
    bg = Image.new('RGB', rgb_img.size, edge_color[:3])

    # Calculate difference
    diff = ImageChops.difference(rgb_img, bg)

    # Convert difference to grayscale for better analysis
    diff_gray = diff.convert('L')

    # Apply tolerance - more aggressive to remove shadows
    # Shadows are usually very faint, so we ignore anything below the tolerance
    diff_gray = diff_gray.point(lambda p: 255 if p > tolerance else 0)

    # Get bounding box of significant content
    bbox = diff_gray.getbbox()

    if bbox:
        return original_img.crop(bbox)
    else:
        # No difference found, return original
        return original_img


def add_white_padding(img, min_width=650, min_height=650):
    """
    Add white padding to image if it's smaller than minimum dimensions.
    Centers the image on white background.
    """
    width, height = img.size

    if width >= min_width and height >= min_height:
        return img

    # Calculate new dimensions
    new_width = max(width, min_width)
    new_height = max(height, min_height)

    # Create white background
    if img.mode == 'RGBA':
        new_img = Image.new('RGBA', (new_width, new_height), (255, 255, 255, 255))
    else:
        new_img = Image.new('RGB', (new_width, new_height), (255, 255, 255))

    # Calculate position to center the image
    x = (new_width - width) // 2
    y = (new_height - height) // 2

    # Paste the original image
    new_img.paste(img, (x, y))

    return new_img


def scale_down_if_needed(img, max_width=3000, max_height=3000):
    """
    Scale down image if it exceeds maximum dimensions.
    Maintains aspect ratio.
    """
    width, height = img.size

    if width <= max_width and height <= max_height:
        return img

    # Calculate scaling factor
    scale = min(max_width / width, max_height / height)

    new_width = int(width * scale)
    new_height = int(height * scale)

    return img.resize((new_width, new_height), Image.LANCZOS)


def compress_to_size(img, output_path, max_size_mb=5):
    """
    Save image and compress if file size exceeds max_size_mb.
    Always saves as PNG with optimization.

    Args:
        img: PIL Image object
        output_path: Path to save the image
        max_size_mb: Maximum file size in megabytes
    """
    max_size_bytes = max_size_mb * 1024 * 1024

    # Ensure RGB or RGBA mode for PNG
    if img.mode not in ('RGB', 'RGBA', 'P'):
        img = img.convert('RGB')

    # Try PNG with optimization first
    img.save(output_path, format='PNG', optimize=True)
    file_size = os.path.getsize(output_path)

    if file_size <= max_size_bytes:
        print(f"  Saved as PNG, size={file_size / (1024*1024):.2f}MB")
        return

    # If still too large and has alpha channel, try converting to RGB
    if img.mode == 'RGBA':
        print(f"  PNG too large ({file_size / (1024*1024):.2f}MB), converting RGBA to RGB...")
        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
        rgb_img.paste(img, mask=img.split()[3])
        rgb_img.save(output_path, format='PNG', optimize=True)
        file_size = os.path.getsize(output_path)

        if file_size <= max_size_bytes:
            print(f"  Saved as PNG (RGB), size={file_size / (1024*1024):.2f}MB")
            return
        img = rgb_img

    # If still too large, convert to JPEG as last resort
    print(f"  PNG still too large, converting to JPEG...")
    output_path_jpeg = str(output_path).replace('.png', '.jpg')

    quality = 95
    while quality >= 10:
        img.save(output_path_jpeg, format='JPEG', quality=quality, optimize=True)
        file_size = os.path.getsize(output_path_jpeg)

        if file_size <= max_size_bytes:
            # Remove the original PNG and rename JPEG to PNG
            if os.path.exists(output_path):
                os.remove(output_path)
            os.rename(output_path_jpeg, output_path)
            print(f"  Saved as JPEG (renamed to .png), quality={quality}, size={file_size / (1024*1024):.2f}MB")
            return

        quality -= 5

    # If still too large, keep the smallest version
    if os.path.exists(output_path):
        os.remove(output_path)
    os.rename(output_path_jpeg, output_path)
    print(f"  Warning: Could not compress below {max_size_mb}MB. Saved with quality=10, size={file_size / (1024*1024):.2f}MB")


def process_image(input_path, output_path=None, tolerance=30):
    """
    Process a single image: auto-crop, resize, and compress.
    Output is always saved as PNG.

    Args:
        input_path: Path to input image
        output_path: Path to save processed image (default: input_path with '_cropped.png')
        tolerance: Color tolerance for cropping (0-255)
    """
    print(f"Processing: {input_path}")

    # Load image
    try:
        img = Image.open(input_path)
    except Exception as e:
        print(f"  Error loading image: {e}")
        return False

    print(f"  Original size: {img.size[0]}x{img.size[1]}")

    # Step 1: Auto-crop
    img = auto_crop(img, tolerance=tolerance)
    print(f"  After crop: {img.size[0]}x{img.size[1]}")

    # Step 2: Scale down if too large
    img = scale_down_if_needed(img)
    print(f"  After scaling: {img.size[0]}x{img.size[1]}")

    # Step 3: Add padding if too small
    img = add_white_padding(img)
    print(f"  After padding: {img.size[0]}x{img.size[1]}")

    # Prepare output path (always save as PNG)
    if output_path is None:
        input_file = Path(input_path)
        output_path = input_file.parent / f"{input_file.stem}_cropped.png"
    else:
        # Ensure output has .png extension
        output_path = Path(output_path)
        output_path = output_path.parent / f"{output_path.stem}.png"

    # Step 4: Compress and save
    compress_to_size(img, str(output_path))
    print(f"  Saved to: {output_path}")
    print()
    return True


def process_directory(input_dir, output_dir=None, tolerance=30):
    """
    Process all images in a directory.
    All output images are saved as PNG format.

    Args:
        input_dir: Directory containing images
        output_dir: Directory to save processed images (default: input_dir/output)
        tolerance: Color tolerance for cropping (0-255)

    Returns:
        Dictionary with processing statistics
    """
    input_path = Path(input_dir)

    if output_dir is None:
        output_path = input_path
    else:
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True, parents=True)

    # Supported image formats
    image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.avif'}

    # Find all images
    image_files = [f for f in input_path.iterdir()
                   if f.is_file() and f.suffix.lower() in image_extensions]

    if not image_files:
        print(f"No images found in {input_dir}")
        return {'total': 0, 'processed': 0, 'output_dir': str(output_path)}

    print(f"Found {len(image_files)} images to process\n")

    processed = 0
    skipped = []
    for img_file in image_files:
        # Always save as PNG
        output_file = output_path / f"{img_file.stem}.png"
        try:
            success = process_image(str(img_file), str(output_file), tolerance=tolerance)
            if success:
                processed += 1
                if img_file.suffix.lower() != '.png':
                    img_file.unlink()
                    print(f"  Deleted original: {img_file.name}")
            else:
                skipped.append(img_file.name)
                print(f"  Skipped (could not process): {img_file.name}")
        except Exception as e:
            skipped.append(img_file.name)
            print(f"Error processing {img_file.name}: {e}")

    return {'total': len(image_files), 'processed': processed, 'skipped': skipped, 'output_dir': str(output_path)}


def get_config_path():
    """Get the path to the configuration file."""
    # Store config in the same directory as the script/exe
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        app_dir = Path(sys.executable).parent
    else:
        # Running as script
        app_dir = Path(__file__).parent

    return app_dir / "config.json"


def load_saved_folder():
    """Load the saved folder path from config file."""
    config_path = get_config_path()

    if not config_path.exists():
        return None

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            folder_path = config.get('folder_path')

            # Verify the folder still exists
            if folder_path and Path(folder_path).exists():
                return folder_path
    except Exception as e:
        print(f"Error loading config: {e}")

    return None


def save_folder_path(folder_path):
    """Save the folder path to config file."""
    config_path = get_config_path()

    try:
        config = {'folder_path': folder_path}
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}")


def show_windows_toast(title, message):
    """Show a non-interrupting Windows toast notification (bottom-right corner)."""
    import subprocess
    safe_title = title.replace("'", "''")
    safe_message = message.replace("'", "''").replace('\n', ' ')
    ps_script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null; "
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null; "
        "$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
        "$x = [xml] $t.GetXml(); "
        f"$x.toast.visual.binding.text[0].InnerText = '{safe_title}'; "
        f"$x.toast.visual.binding.text[1].InnerText = '{safe_message}'; "
        "$d = New-Object Windows.Data.Xml.Dom.XmlDocument; "
        "$d.LoadXml($x.OuterXml); "
        "$n = [Windows.UI.Notifications.ToastNotification]::new($d); "
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('ArdesPhotoCut').Show($n)"
    )
    try:
        subprocess.Popen(
            ['powershell', '-WindowStyle', 'Hidden', '-NonInteractive', '-Command', ps_script],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    except Exception:
        pass


def run_gui_mode():
    """
    Run the application in GUI mode with folder selection dialog.
    Automatically uses saved folder from config.json if it exists.
    To change folder: delete or edit config.json
    """
    # Hide the root window
    root = tk.Tk()
    root.withdraw()

    # Check if we have a saved folder path
    saved_folder = load_saved_folder()

    if saved_folder:
        # Use saved folder directly without asking
        folder_path = saved_folder
        print(f"Using saved folder from config.json: {folder_path}")
        print("To change folder, delete or edit config.json\n")
    else:
        # No saved folder, ask user to select one
        messagebox.showinfo("Image Auto-Cropper",
                           "Select the folder containing images to process.\n\n"
                           "Processed images will be saved directly in the selected folder.\n"
                           "This folder will be saved in config.json for future use.")

        folder_path = filedialog.askdirectory(title="Select Folder with Images")

        if not folder_path:
            messagebox.showwarning("Cancelled", "No folder selected. Exiting.")
            return

        # Save the selected folder for next time
        save_folder_path(folder_path)
        print(f"Folder saved to config.json: {folder_path}\n")

    # Process the directory
    print(f"Processing images in: {folder_path}\n")
    tolerance = 30  # Default tolerance

    try:
        result = process_directory(folder_path, tolerance=tolerance)

        if result['total'] == 0:
            messagebox.showwarning("No Images Found",
                                  f"No images found in the selected folder:\n{folder_path}")
        else:
            skipped = result.get('skipped', [])
            success_msg = (f"Processing Complete!\n\n"
                          f"Processed: {result['processed']} out of {result['total']} images\n"
                          f"Output folder: {result['output_dir']}")
            if skipped:
                success_msg += f"\n\nFailed to process ({len(skipped)}):\n" + "\n".join(skipped)
            show_windows_toast("Processing Complete!", success_msg)
            print(f"\n{success_msg}")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{str(e)}")
        print(f"Error: {e}")


if __name__ == "__main__":
    # If no arguments provided, run in GUI mode
    if len(sys.argv) < 2:
        run_gui_mode()
    else:
        # Command-line mode
        input_arg = sys.argv[1]
        output_arg = sys.argv[2] if len(sys.argv) > 2 else None
        tolerance = int(sys.argv[3]) if len(sys.argv) > 3 else 30

        # Check if input is directory or file
        input_path = Path(input_arg)

        if not input_path.exists():
            print(f"Error: {input_arg} does not exist")
            sys.exit(1)

        if input_path.is_dir():
            result = process_directory(input_arg, output_arg, tolerance)
            print(f"\nProcessed {result['processed']} out of {result['total']} images")
            print(f"Output saved to: {result['output_dir']}")
        else:
            process_image(input_arg, output_arg, tolerance)
