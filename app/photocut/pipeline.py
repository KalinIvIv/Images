"""
Image editing pipeline: crop away the background, fit the size limits, encode as PNG.

Reworked from legacy/auto_crop.py. Differences (see NOTES.md):
- works on in-memory images, never touches the source file
- applies EXIF rotation and normalises the colour mode up front
- background distance is the per-channel maximum (yellow on white is detected)
- edge colour is the per-channel median of the whole border
- isolated specks are ignored when finding the object's bounding box
- output is always a real PNG; if it is over the size limit it is scaled down
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageFilter, ImageOps

Image.MAX_IMAGE_PIXELS = 200_000_000


@dataclass
class Settings:
    tolerance: int = 30          # 0-255, colour distance from the background
    alpha_threshold: int = 200   # 0-255, alpha below this is background/shadow
    min_size: int = 650          # pad up to this many pixels per side
    max_size: int = 3000         # scale down to fit inside this box
    max_bytes: int = 5 * 1024 * 1024
    flatten: bool = False        # put transparent images on white


def load(source):
    """Open bytes or a path, apply EXIF rotation and convert to RGB or RGBA."""
    img = Image.open(io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else source)
    img.load()
    img = ImageOps.exif_transpose(img)

    has_alpha = img.mode in ('RGBA', 'LA', 'PA') or 'transparency' in img.info
    img = img.convert('RGBA' if has_alpha else 'RGB')
    if has_alpha and img.getextrema()[3][0] == 255:
        # Alpha channel present but fully opaque - treat as a normal photo.
        img = img.convert('RGB')
    return img


def _channel_medians(hist, channels):
    medians = []
    for c in range(channels):
        h = hist[c * 256:(c + 1) * 256]
        half, total = sum(h) / 2, 0
        for value, count in enumerate(h):
            total += count
            if total >= half:
                medians.append(value)
                break
    return tuple(medians)


def edge_color(rgb, strip=2):
    """Per-channel median of a thin strip around the whole border."""
    w, h = rgb.size
    s = max(1, min(strip, w // 2, h // 2))
    boxes = [(0, 0, w, s), (0, h - s, w, h), (0, 0, s, h), (w - s, 0, w, h)]
    hist = [0] * 768
    for box in boxes:
        for i, count in enumerate(rgb.crop(box).histogram()):
            hist[i] += count
    return _channel_medians(hist, 3)


def _despeckle(mask):
    """Morphological opening: removes specks and hairlines, keeps solid areas."""
    size = 3 if max(mask.size) < 1500 else 5
    return mask.filter(ImageFilter.MinFilter(size)).filter(ImageFilter.MaxFilter(size))


def content_bbox(img, settings=Settings()):
    """Bounding box of the main object, or None if nothing stands out."""
    if img.mode == 'RGBA':
        alpha = img.getchannel('A')
        if alpha.getextrema()[0] < settings.alpha_threshold:
            mask = alpha.point(lambda p: 255 if p > settings.alpha_threshold else 0)
            return _despeckle(mask).getbbox() or mask.getbbox()
        rgb = Image.new('RGB', img.size, (255, 255, 255))
        rgb.paste(img, mask=alpha)
    else:
        rgb = img

    bg = Image.new('RGB', rgb.size, edge_color(rgb))
    r, g, b = ImageChops.difference(rgb, bg).split()
    distance = ImageChops.lighter(ImageChops.lighter(r, g), b)
    mask = distance.point(lambda p: 255 if p > settings.tolerance else 0)
    return _despeckle(mask).getbbox() or mask.getbbox()


def auto_crop(img, settings=Settings()):
    bbox = content_bbox(img, settings)
    return img.crop(bbox) if bbox else img


def scale_down_if_needed(img, max_size=3000):
    w, h = img.size
    if w <= max_size and h <= max_size:
        return img
    scale = min(max_size / w, max_size / h)
    return img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)


def add_padding(img, min_size=650):
    """Centre on a canvas at least min_size per side (white, or transparent for RGBA)."""
    w, h = img.size
    if w >= min_size and h >= min_size:
        return img
    fill = (255, 255, 255, 0) if img.mode == 'RGBA' else (255, 255, 255)
    canvas = Image.new(img.mode, (max(w, min_size), max(h, min_size)), fill)
    canvas.paste(img, ((canvas.width - w) // 2, (canvas.height - h) // 2))
    return canvas


def flatten(img):
    if img.mode != 'RGBA':
        return img
    out = Image.new('RGB', img.size, (255, 255, 255))
    out.paste(img, mask=img.getchannel('A'))
    return out


def encode_png(img, settings=Settings()):
    """PNG bytes under max_bytes, scaling down (never below min_size) if needed."""
    while True:
        buf = io.BytesIO()
        img.save(buf, format='PNG', compress_level=6)
        data = buf.getvalue()
        if len(data) <= settings.max_bytes:
            return data, img
        w, h = img.size
        if min(w, h) * 0.85 >= settings.min_size:
            img = img.resize((round(w * 0.85), round(h * 0.85)), Image.LANCZOS)
        elif img.mode == 'RGBA':
            img = flatten(img)
        else:
            return data, img  # best effort; caller reports the size


def process(source, settings=Settings(), trim=True):
    """
    Full pipeline. Returns (png_bytes, info).
    trim=False keeps the whole image (infographics, lifestyle photos): only the size
    limits and PNG encoding are applied.
    """
    img = load(source)
    info = {'original': img.size, 'trimmed': trim}
    if trim:
        img = auto_crop(img, settings)
    info['cropped'] = img.size
    img = scale_down_if_needed(img, settings.max_size)
    img = add_padding(img, settings.min_size)
    if settings.flatten:
        img = flatten(img)
    data, img = encode_png(img, settings)
    info['final'] = img.size
    info['bytes'] = len(data)
    info['over_limit'] = len(data) > settings.max_bytes
    return data, info
