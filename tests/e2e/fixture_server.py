"""
Local fake shops for the end-to-end test.

/products/test-bundle          Shopify-like store (uses /products/<handle>.js and _400x thumbnails)
/za/monitors/32gs95uv-b/       LG-like page: custom gallery with srcset, logo, awards, related products
/shop/item-77                  page whose gallery has meaningless class names (needs the picker)

Images are generated on request: /img/<name>_<w>x<h>.<ext>, coloured by name.
Shopify-style size suffixes (_400x) are ignored so the "original" URL also works.
"""

import hashlib
import io
import json
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image, ImageDraw


def photo(name, w, h, fmt):
    color = tuple(int(hashlib.md5(name.encode()).hexdigest()[i:i + 2], 16) // 2 for i in (0, 2, 4))
    img = Image.new('RGB', (w, h), 'white')
    ImageDraw.Draw(img).rectangle((w // 5, h // 6, w * 4 // 5, h * 5 // 6), fill=color)
    buf = io.BytesIO()
    img.save(buf, {'jpg': 'JPEG', 'png': 'PNG', 'webp': 'WEBP'}[fmt])
    return buf.getvalue(), f'image/{"jpeg" if fmt == "jpg" else fmt}'


SHOPIFY = """<!doctype html><html><head><title>PanzerGlass 2-in-1 Bundle</title>
<link rel="stylesheet" href="/cdn/shop/t/1/assets/base.css">
<script>window.Shopify = {shop: 'test'};</script></head><body>
<header><img src="/img/logo_300x80.png" alt="Store logo" width="300"></header>
<main><h1>PanzerGlass 2-in-1 Essential Bundle</h1>
<media-gallery class="product__media-wrapper"><ul class="product__media-list">
 <li><img src="/cdn/shop/files/bundle-front_400x.jpg" width="400"></li>
 <li><img src="/cdn/shop/files/bundle-back_400x.jpg" width="400"></li>
</ul></media-gallery>
<section class="related-products"><h2>You may also like</h2>
 <img src="/img/other-product_600x600.jpg"></section></main></body></html>"""

SHOPIFY_JS = {
    'title': 'PanzerGlass 2-in-1 Essential Bundle',
    'variants': [{'sku': 'PG-7890'}],
    'media': [{'media_type': 'image', 'src': '/cdn/shop/files/bundle-front.jpg', 'width': 1600},
              {'media_type': 'image', 'src': '/cdn/shop/files/bundle-back.jpg', 'width': 1600},
              {'media_type': 'video', 'src': '/cdn/shop/files/video-poster.jpg'},
              {'media_type': 'image', 'src': '/cdn/shop/files/bundle-box.jpg', 'width': 1600}],
}

LG = """<!doctype html><html><head><title>32GS95UV-B | LG ZA</title>
<meta property="og:image" content="/img/og-32gs95uv_1200x630.jpg"></head><body>
<header><img src="/img/lg-logo_200x60.png" alt="LG"></header>
<nav><img src="/img/menu-promo_800x200.jpg"></nav>
<div class="pdp-top"><h1>32" UltraGear OLED Gaming Monitor</h1>
 <div class="c-gallery">
  <div class="c-gallery__main"><img src="/img/32gs95uv-01_800x800.jpg"
      srcset="/img/32gs95uv-01_800x800.jpg 800w, /img/32gs95uv-01_2000x2000.jpg 2000w"></div>
  <div class="c-gallery__thumbs">
   <img src="/img/32gs95uv-01_100x100.jpg" data-large="/img/32gs95uv-01_2000x2000.jpg">
   <img src="/img/32gs95uv-02_100x100.jpg" data-large="/img/32gs95uv-02_2000x2000.jpg">
   <img src="/img/32gs95uv-03_100x100.jpg" data-large="/img/32gs95uv-03_2000x2000.jpg">
  </div></div></div>
<div style="height:1500px"></div>
<section class="awards"><img src="/awards/red-dot_1000x1000.png"></section>
<div class="feature-banner"><img src="/img/lifestyle-banner_1920x800.jpg" width="1920"></div>
<footer><img src="/img/payment-icons_400x40.png"></footer></body></html>"""

PICKER = """<!doctype html><html><head><title>Item 77</title></head><body>
<div class="hero"><img src="/img/sale-banner_1600x900.jpg" width="1600" height="900" style="width:100%"></div>
<div class="x9 q2" style="margin-top:900px">
 <div class="a1"><img src="/img/item77-a_900x900.jpg" width="300"><img src="/img/item77-b_900x900.jpg" width="300"></div>
</div>
<div class="zz"><img src="/img/unrelated_900x900.jpg" width="300"></div></body></html>"""

def special(kind, w, h):
    """Images for the trim / keep-whole check."""
    from PIL import ImageFont
    img = Image.new('RGB', (w, h), 'white')
    d = ImageDraw.Draw(img)
    if kind == 'infographic':          # product + feature callouts
        d.rectangle((w // 12, h // 4, w * 5 // 12, h * 3 // 4), fill=(30, 60, 120))
        font = ImageFont.load_default(size=max(12, h // 22))
        for i, line in enumerate(['Ultra-clear 9H glass', 'Easy bubble-free install', 'Case friendly fit', 'Works with Face ID']):
            d.text((w // 2, h // 5 + i * h // 7), line, fill=(40, 40, 40), font=font)
    elif kind == 'lifestyle':          # product in a room: wall, floor, texture
        d.rectangle((0, 0, w, h * 3 // 5), fill=(205, 190, 160))
        d.rectangle((0, h * 3 // 5, w, h), fill=(110, 80, 55))
        img = Image.blend(img, Image.effect_noise((w, h), 70).convert('RGB'), 0.25)
        ImageDraw.Draw(img).rectangle((w // 3, h // 3, w * 2 // 3, h * 4 // 5), fill=(200, 30, 30))
    elif kind == 'labelled':           # product with a printed brand name / label on it
        d.rectangle((w // 4, h // 6, w * 3 // 4, h * 5 // 6), fill=(180, 20, 20))
        font = ImageFont.load_default(size=max(12, h // 14))
        d.text((w * 3 // 8, h // 2 - h // 20), 'BRAND', fill='white', font=font)
    else:                              # plain product shot
        d.ellipse((w // 4, h // 6, w * 3 // 4, h * 5 // 6), fill=(20, 120, 60))
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=92)
    return buf.getvalue(), 'image/jpeg'


MIXED = """<!doctype html><html><head><title>Mixed 3</title></head><body>
<div class="product-gallery">
 <img src="/special/product_1200x1200.jpg" width="300"><img src="/special/labelled_1200x1200.jpg" width="300">
 <img src="/special/infographic_1600x1200.jpg" width="300"><img src="/special/lifestyle_1600x1000.jpg" width="300">
</div></body></html>"""

# Gallery with only auto-generated class names (like many big-brand sites).
HASHED = """<!doctype html><html><head><title>Hashed 5</title></head><body>
<div class="css-a8f3k2"><img src="/img/hashed-banner_1600x900.jpg" width="1600" height="900" style="width:100%"></div>
<div class="sc-bdfBwQ" style="margin-top:900px">
 <div><img src="/img/hashed-a_900x900.jpg" width="300"><img src="/img/hashed-b_900x900.jpg" width="300"></div>
</div>
<div class="sc-gsTCUz"><div><img src="/img/hashed-other_900x900.jpg" width="300"></div></div></body></html>"""

# Gallery drawn with CSS background images from a stylesheet.
BACKGROUND = """<!doctype html><html><head><title>Bg 9</title><style>
.ph { display:inline-block; width:300px; height:300px; background-size:cover }
.p1 { background-image:url(/img/bg-a_900x900.jpg) } .p2 { background-image:url(/img/bg-b_900x900.jpg) }
</style></head><body>
<div class="hero"><img src="/img/bg-banner_1600x900.jpg" width="1600" height="900" style="width:100%"></div>
<section class="pdp" style="margin-top:900px"><span class="ph p1"></span><span class="ph p2"></span></section>
</body></html>"""


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, body, ctype, status=200):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the browser closed the page mid-download

    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/products/test-bundle':
            return self.send(SHOPIFY, 'text/html')
        if path == '/products/test-bundle.js':
            return self.send(json.dumps(SHOPIFY_JS), 'application/json')
        if path.startswith('/za/monitors/32gs95uv-b'):
            return self.send(LG, 'text/html')
        if path == '/shop/item-77':
            return self.send(PICKER, 'text/html')
        if path == '/shop/hashed-5':
            return self.send(HASHED, 'text/html')
        if path == '/shop/bg-9':
            return self.send(BACKGROUND, 'text/html')
        if path == '/shop/mixed-3':
            return self.send(MIXED, 'text/html')
        m = re.match(r'^/special/(\w+)_(\d+)x(\d+)\.jpg$', path)
        if m:
            return self.send(*special(m.group(1), int(m.group(2)), int(m.group(3))))
        if path.endswith('.css'):
            return self.send('', 'text/css')
        m = re.match(r'^/cdn/shop/files/([\w-]+?)(?:_\d+x\d*)?\.(jpg|png|webp)$', path)
        if m:
            return self.send(*photo(m.group(1), 1600, 1600, m.group(2)))
        m = re.match(r'^/(?:img|awards)/([\w-]+)_(\d+)x(\d+)\.(jpg|png|webp)$', path)
        if m:
            return self.send(*photo(m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)))
        self.send('not found', 'text/plain', 404)


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
