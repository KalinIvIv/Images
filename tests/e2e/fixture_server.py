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
        self.wfile.write(body)

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
