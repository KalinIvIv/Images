import io
import json

import pytest
from PIL import Image, ImageDraw

from photocut import naming, pipeline, rules
from photocut.pipeline import Settings


def png_bytes(img, fmt='PNG', **kw):
    buf = io.BytesIO()
    img.save(buf, format=fmt, **kw)
    return buf.getvalue()


def product(size=1000, box=(300, 300, 700, 700), color=(255, 0, 0), bg=(255, 255, 255)):
    img = Image.new('RGB', (size, size), bg)
    ImageDraw.Draw(img).rectangle(box, fill=color)
    return img


# --- cropping -----------------------------------------------------------------

def test_crops_to_object():
    assert pipeline.content_bbox(product()) == (300, 300, 701, 701)


def test_yellow_on_white_is_detected():
    # Legacy code converted the difference to greyscale and missed this.
    assert pipeline.content_bbox(product(color=(255, 255, 0))) == (300, 300, 701, 701)


def test_single_speck_does_not_block_crop():
    img = product()
    ImageDraw.Draw(img).point((5, 5), fill=(0, 0, 0))
    ImageDraw.Draw(img).line([(0, 990), (999, 990)], fill=(0, 0, 0), width=1)
    assert pipeline.content_bbox(img) == (300, 300, 701, 701)


def test_noisy_background_edge_color():
    img = product(bg=(250, 250, 250))
    for x in range(0, 1000, 7):
        img.putpixel((x, 0), (240 + x % 15, 250, 255))
    assert pipeline.edge_color(img) == (250, 250, 250)


def test_object_touching_edge_keeps_background_color():
    img = product(box=(0, 300, 700, 700))
    assert pipeline.edge_color(img) == (255, 255, 255)


def test_transparent_image_uses_alpha_and_drops_shadow():
    img = Image.new('RGBA', (800, 800), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((100, 600, 700, 700), fill=(0, 0, 0, 80))       # soft shadow
    d.rectangle((200, 200, 600, 620), fill=(0, 128, 255, 255))   # product
    assert pipeline.content_bbox(img) == (200, 200, 601, 621)


def test_blank_image_is_left_alone():
    img = Image.new('RGB', (700, 700), 'white')
    assert pipeline.auto_crop(img).size == (700, 700)


# --- loading ------------------------------------------------------------------

def test_exif_rotation_applied():
    img = Image.new('RGB', (1200, 800), 'white')
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 CW
    data = png_bytes(img, 'JPEG', exif=exif.tobytes())
    assert pipeline.load(data).size == (800, 1200)


def test_modes_normalised():
    assert pipeline.load(png_bytes(Image.new('L', (10, 10)))).mode == 'RGB'
    assert pipeline.load(png_bytes(Image.new('P', (10, 10)))).mode == 'RGB'
    assert pipeline.load(png_bytes(Image.new('CMYK', (10, 10)), 'JPEG')).mode == 'RGB'
    assert pipeline.load(png_bytes(Image.new('LA', (10, 10), (0, 0)))).mode == 'RGBA'
    # alpha channel that is fully opaque is treated as a normal photo
    assert pipeline.load(png_bytes(Image.new('RGBA', (10, 10), (1, 2, 3, 255)))).mode == 'RGB'


# --- sizes --------------------------------------------------------------------

def test_small_image_padded_to_650():
    data, info = pipeline.process(png_bytes(product(size=400, box=(100, 150, 300, 250))))
    out = Image.open(io.BytesIO(data))
    assert out.format == 'PNG'
    assert out.size == (650, 650)
    assert out.getpixel((0, 0)) == (255, 255, 255)


def test_wide_image_padded_in_one_direction():
    img = Image.new('RGB', (2200, 600), 'white')
    ImageDraw.Draw(img).rectangle((100, 200, 2100, 400), fill='blue')
    _, info = pipeline.process(png_bytes(img))
    assert info['final'] == (2001, 650)


def test_large_image_scaled_to_3000():
    img = product(size=4000, box=(10, 10, 3990, 3990))
    _, info = pipeline.process(png_bytes(img, 'JPEG'))
    assert max(info['final']) == 3000


def test_transparent_padding_stays_transparent():
    img = Image.new('RGBA', (300, 300), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((50, 50, 250, 250), fill=(255, 0, 0, 255))
    out = Image.open(io.BytesIO(pipeline.process(png_bytes(img))[0]))
    assert out.mode == 'RGBA' and out.size == (650, 650)
    assert out.getpixel((0, 0))[3] == 0


def test_flatten_option():
    img = Image.new('RGBA', (300, 300), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((50, 50, 250, 250), fill=(255, 0, 0, 255))
    out = Image.open(io.BytesIO(pipeline.process(png_bytes(img), Settings(flatten=True))[0]))
    assert out.mode == 'RGB' and out.getpixel((0, 0)) == (255, 255, 255)


def test_size_limit_scales_down_and_stays_png():
    noise = Image.effect_noise((1500, 1500), 100).convert('RGB')
    data, info = pipeline.process(png_bytes(noise), Settings(max_bytes=1_000_000))
    assert len(data) <= 1_000_000
    assert Image.open(io.BytesIO(data)).format == 'PNG'
    assert min(info['final']) >= 650


# --- naming -------------------------------------------------------------------

@pytest.mark.parametrize('raw,expected', [
    ('Chair X200', 'Chair X200'),
    ('LG 32GS95UV-B: 32" UltraGear', 'LG 32GS95UV-B 32 UltraGear'),
    ('  dots...  ', 'dots'),
    ('CON', 'CON_'),
    ('', 'images'),
    ('a/b\\c?', 'a b c'),
])
def test_sanitize(raw, expected):
    assert naming.sanitize(raw) == expected


def test_folder_status_and_unique(tmp_path):
    st = naming.folder_status(tmp_path, 'Chair')
    assert st == {'name': 'Chair', 'path': str(tmp_path / 'Chair'), 'exists': False, 'count': 0, 'next': 1}
    (tmp_path / 'Chair').mkdir()
    for n in (1, 2, 5):
        (tmp_path / 'Chair' / f'Chair_{n}.png').write_bytes(b'x')
    (tmp_path / 'Chair' / 'other.png').write_bytes(b'x')
    st = naming.folder_status(tmp_path, 'Chair')
    assert st['count'] == 3 and st['next'] == 6
    assert naming.unique_folder(tmp_path, 'Chair') == 'Chair (2)'


def test_write_new_never_overwrites(tmp_path):
    target = tmp_path / 'a' / 'x.png'
    naming.write_new(target, b'one')
    with pytest.raises(FileExistsError):
        naming.write_new(target, b'two')
    assert target.read_bytes() == b'one'
    assert not (tmp_path / 'a' / 'x.png.part').exists()


# --- rules --------------------------------------------------------------------

def test_rules_match_by_domain_and_subdomain():
    data = {'version': 1, 'sites': {'lg.com': {'gallery': '.g'}, 'shop.aoc.com': {'gallery': '.a'}}}
    assert rules.match(data, 'www.lg.com') == ('lg.com', {'gallery': '.g'})
    assert rules.match(data, 'lg.com')[0] == 'lg.com'
    assert rules.match(data, 'shop.aoc.com')[0] == 'shop.aoc.com'
    assert rules.match(data, 'www.aoc.com') == (None, None)


def test_save_site_merges_and_keeps_backup(tmp_path):
    path = tmp_path / 'shared' / 'rules.json'
    rules.save_site(path, 'www.lg.com', {'gallery': '.g', 'exclude': ['b', 'a', 'a', ''], 'junk': 1}, 'Kalin')
    # someone else adds a site in the meantime
    data = json.loads(path.read_text())
    data['sites']['aoc.com'] = {'gallery': '.x'}
    path.write_text(json.dumps(data))

    rules.save_site(path, 'lg.com', {'gallery': '.g2'}, 'Ana')
    data = json.loads(path.read_text())
    assert set(data['sites']) == {'aoc.com', 'lg.com'}
    assert data['sites']['lg.com']['gallery'] == '.g2'
    assert data['sites']['lg.com']['updatedBy'] == 'Ana'
    assert (tmp_path / 'shared' / 'rules.json.bak').exists()

    rules.save_site(path, 'lg.com', None)
    assert set(json.loads(path.read_text())['sites']) == {'aoc.com'}


def test_clean_rule():
    assert rules.clean_rule({'gallery': '.g', 'exclude': ['b', 'a', 'b'], 'include': [], 'x': 1}) == \
        {'gallery': '.g', 'exclude': ['a', 'b']}


def test_bad_rules_file_raises(tmp_path):
    p = tmp_path / 'rules.json'
    p.write_text('[1, 2]')
    with pytest.raises(ValueError):
        rules.load(p)


# --- keep whole (no trim) -------------------------------------------------------

def test_keep_whole_skips_crop_but_applies_limits():
    big = product(size=4000, box=(1000, 1000, 1500, 1500))
    _, info = pipeline.process(png_bytes(big, 'JPEG'), trim=False)
    assert info['trimmed'] is False and info['cropped'] == (4000, 4000) and info['final'] == (3000, 3000)

    small = product(size=400, box=(100, 100, 200, 200))
    data, info = pipeline.process(png_bytes(small), trim=False)
    assert info['final'] == (650, 650)
    out = Image.open(io.BytesIO(data)).convert('RGB')
    assert out.getpixel((125 + 150, 125 + 150)) == (255, 0, 0)  # original layout kept, centred


def test_trim_is_default():
    assert pipeline.process(png_bytes(product()))[1]['trimmed'] is True
