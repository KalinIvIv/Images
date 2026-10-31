// PhotoCut page detector. Injected into the product page; exposes window.__photocutDetect(rule).
// Finds the product images, works out the highest-resolution URL of each, and
// marks the ones that belong to the product gallery.

(() => {
  if (window.__photocutDetect) return;

  const IMAGE_EXT = /\.(jpe?g|png|webp|avif|gif|bmp|tiff?)(\?|#|$)/i;
  const JUNK = /(logo|icon|awards?[-_/]|sprite|badge|payment|flag|avatar|rating|stars?[-_.]|favicon|placeholder|spinner|loader|blank\.|pixel|tracking|qr[-_]?code|social|facebook|twitter|instagram|youtube|pinterest)/i;
  const HIRES_ATTRS = ['data-zoom-image', 'data-zoom', 'data-zoom-src', 'data-large_image', 'data-large', 'data-large-src',
    'data-full', 'data-full-src', 'data-fullsize', 'data-original', 'data-hires', 'data-high-res', 'data-src-large', 'data-big'];
  const LAZY_ATTRS = ['data-src', 'data-lazy-src', 'data-lazy', 'data-original-src', 'data-image', 'data-img'];
  const SIZE_PARAMS = ['w', 'width', 'h', 'height', 'wid', 'hei', 'size', 'resize', 'imwidth', 'imheight', 'fit', 'crop', 'scale'];
  const GALLERY_SELECTORS = [
    // Shopify
    'media-gallery', '.product__media-list', '.product__media-wrapper', '.product-single__media-group', '.product-gallery',
    '[data-product-gallery]', '.product__photos', '.product-images',
    // WooCommerce
    '.woocommerce-product-gallery',
    // Magento
    '.gallery-placeholder', '.fotorama', '.product.media',
    // PrestaShop / OpenCart / BigCommerce
    '.images-container', '#product-images-large', '.product-images-thumbnails', '.productView-images', '.thumbnails',
    // common names
    '.pdp-gallery', '.product-gallery-wrapper', '.product-media', '.product-image-gallery', '#product-gallery',
  ];
  const GENERIC_GALLERY = '[class*="gallery" i], [class*="carousel" i], [class*="slider" i], [class*="swiper" i], ' +
    '[class*="slick" i], [class*="product-image" i], [class*="product-media" i], [class*="visual" i], [id*="gallery" i]';
  const CHROME = 'header, nav, footer, [role="banner"], [role="navigation"], [role="contentinfo"], ' +
    '[class*="related" i], [class*="recommend" i], [class*="upsell" i], [class*="cross-sell" i], [class*="recently" i]';

  const abs = (u) => {
    if (!u || typeof u !== 'string') return null;
    u = u.trim();
    if (!u || u.startsWith('data:') || u.startsWith('blob:')) return null;
    try { return new URL(u, location.href).href; } catch { return null; }
  };

  function parseSrcset(srcset) {
    let best = null;
    for (const part of (srcset || '').split(/,\s+(?=\S)/)) {
      const [url, desc = '1x'] = part.trim().split(/\s+/);
      const n = parseFloat(desc);
      const w = desc.endsWith('w') ? n : desc.endsWith('x') ? n * 1000 : 0;
      if (url && (!best || w > best.w)) best = { url: abs(url), w: desc.endsWith('w') ? n : 0 };
    }
    return best;
  }

  // Turn a resized image URL into the original one, using platform conventions and site rules.
  function upgrade(url, rule) {
    if (!url) return url;
    for (const { find, replace } of rule.rewrite || []) {
      try { url = url.replace(new RegExp(find, 'g'), replace ?? ''); } catch { /* bad regex in rule */ }
    }
    let u;
    try { u = new URL(url); } catch { return url; }
    if (/cdn\.shopify\.com$/.test(u.hostname) || u.pathname.includes('/cdn/shop/')) {
      u.pathname = u.pathname.replace(/_(\d+x\d*|\d*x\d+|pico|icon|thumb|small|compact|medium|large|grande|master)(_crop_\w+)?(@\dx)?(?=\.\w+$)/i, '');
    }
    if (u.pathname.includes('/wp-content/')) {
      u.pathname = u.pathname.replace(/-\d+x\d+(?=\.\w+$)/, '').replace(/-scaled(?=\.\w+$)/, '');
    }
    if (u.pathname.includes('/media/catalog/product/')) {
      u.pathname = u.pathname.replace(/\/cache\/[0-9a-f]{32}\//, '/');
    }
    for (const p of SIZE_PARAMS) u.searchParams.delete(p);
    return u.href;
  }

  // Key used to recognise the same photo at different sizes.
  function keyOf(url) {
    try {
      const u = new URL(url);
      return (u.hostname.replace(/^www\./, '') + u.pathname).toLowerCase()
        .replace(/_(\d+x\d*|\d*x\d+)(?=\.\w+$)/, '').replace(/-\d+x\d+(?=\.\w+$)/, '')
        .replace(/\.(jpe?g|png|webp|avif)$/, '');
    } catch { return url; }
  }

  const basename = (url) => { try { return new URL(url).pathname.split('/').pop(); } catch { return url; } };

  // All URL variants an <img> offers; returns {url, thumb, size}.
  function fromImg(img) {
    let best = null, size = 0;
    for (const a of HIRES_ATTRS) {
      const v = abs(img.getAttribute(a)) || abs(img.parentElement?.getAttribute(a));
      if (v) { best = v; break; }
    }
    const link = img.closest('a[href]');
    if (!best && link && IMAGE_EXT.test(link.getAttribute('href'))) best = abs(link.getAttribute('href'));

    const sets = [img.getAttribute('srcset'), img.getAttribute('data-srcset')];
    const picture = img.closest('picture');
    if (picture) for (const s of picture.querySelectorAll('source')) sets.push(s.getAttribute('srcset'), s.getAttribute('data-srcset'));
    let largest = null;
    for (const s of sets) {
      const c = s && parseSrcset(s);
      if (c?.url && (!largest || c.w > largest.w)) largest = c;
    }
    const lazy = LAZY_ATTRS.map((a) => abs(img.getAttribute(a))).find(Boolean);
    const shown = abs(img.currentSrc) || abs(img.getAttribute('src')) || lazy;
    // Size is only known when we download what the page shows or what srcset describes;
    // a zoom/large attribute is bigger than the thumbnail but its size is unknown (0).
    if (!best && largest?.url) { best = largest.url; size = largest.w; }
    if (!best) {
      best = lazy || shown;
      size = Math.max(img.naturalWidth || 0, parseInt(img.getAttribute('width') || img.getAttribute('data-width') || 0, 10) || 0);
    }
    return best ? { url: best, thumb: shown || best, size, alt: img.alt || '' } : null;
  }

  function fromBackground(el) {
    const m = (el.getAttribute('style') || '').match(/background(?:-image)?\s*:[^;]*url\(\s*['"]?([^'")]+)/i);
    const url = m && abs(m[1]);
    return url ? { url, thumb: url, size: Math.max(el.clientWidth, el.clientHeight), alt: '' } : null;
  }

  function fromComputedBackground(el) {
    const m = getComputedStyle(el).backgroundImage.match(/url\(\s*['"]?([^'")]+)/);
    const url = m && abs(m[1]);
    return url ? { url, thumb: url, size: Math.max(el.clientWidth, el.clientHeight), alt: '' } : null;
  }

  // deep: also read CSS background images set by stylesheets (slower; used for the gallery area).
  function imagesIn(root, deep = false) {
    const out = [];
    if (deep) {
      for (const el of [root, ...root.querySelectorAll('*')].slice(0, 1500)) {
        if (el.tagName === 'IMG') continue;
        const c = fromComputedBackground(el);
        if (c) out.push({ ...c, el });
      }
    }
    // The picked area may be a single image itself.
    for (const img of root.tagName === 'IMG' ? [root] : root.querySelectorAll('img')) {
      const c = fromImg(img);
      if (c) out.push({ ...c, el: img });
    }
    for (const el of root.querySelectorAll('[style*="url("]')) {
      const c = fromBackground(el);
      if (c) out.push({ ...c, el });
    }
    for (const a of root.querySelectorAll('a[href]')) {
      if (IMAGE_EXT.test(a.getAttribute('href')) && !a.querySelector('img')) {
        const url = abs(a.getAttribute('href'));
        if (url) out.push({ url, thumb: url, size: 0, alt: '', el: a });
      }
    }
    return out;
  }

  // --- structured data ---------------------------------------------------------

  function jsonLdProducts() {
    const found = [];
    const walk = (node) => {
      if (!node || typeof node !== 'object') return;
      if (Array.isArray(node)) return node.forEach(walk);
      const type = [].concat(node['@type'] || []).join(' ');
      if (/Product|ProductGroup|IndividualProduct/.test(type)) found.push(node);
      if (node['@graph']) walk(node['@graph']);
      if (node.hasVariant) walk(node.hasVariant);
    };
    for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
      try { walk(JSON.parse(s.textContent)); } catch { /* invalid JSON-LD */ }
    }
    return found;
  }

  function ldImages(products) {
    const urls = [];
    const add = (v) => {
      if (!v) return;
      if (Array.isArray(v)) return v.forEach(add);
      if (typeof v === 'object') return add(v.contentUrl || v.url);
      const u = abs(v);
      if (u) urls.push(u);
    };
    products.forEach((p) => add(p.image));
    return urls;
  }

  async function shopifyImages() {
    const m = location.pathname.match(/^(.*\/products\/[^/?#]+)/);
    if (!m || !(window.Shopify || document.querySelector('link[href*="cdn.shopify.com"], script[src*="cdn.shopify.com"], link[href*="/cdn/shop/"]'))) return null;
    try {
      const res = await fetch(`${m[1]}.js`, { credentials: 'same-origin' });
      if (!res.ok) return null;
      const p = await res.json();
      const media = (p.media || []).filter((x) => x.media_type === 'image').map((x) => ({ url: abs(x.src), size: x.width || 0 }));
      const list = media.length ? media : (p.images || []).map((src) => ({ url: abs(src), size: 0 }));
      return { images: list.filter((x) => x.url), title: p.title, sku: p.variants?.[0]?.sku || '' };
    } catch { return null; }
  }

  // --- gallery container -----------------------------------------------------------

  function pickGallery(rule) {
    if (rule.gallery) {
      try {
        const els = [...document.querySelectorAll(rule.gallery)];
        if (els.length) return { els, how: 'rule' };
      } catch { /* invalid selector */ }
      return { els: [], how: 'rule-missed' };
    }
    const score = (el) => {
      if (el.closest(CHROME)) return -1;
      const rect = el.getBoundingClientRect();
      if (rect.width < 150 || rect.height < 150) return -1;
      const keys = new Set(imagesIn(el).filter((c) => !JUNK.test(c.url)).map((c) => keyOf(upgrade(c.url, rule))));
      if (!keys.size) return -1;
      const top = rect.top + window.scrollY;
      const position = top < window.innerHeight * 1.2 ? 1 : top < window.innerHeight * 2.5 ? 0.5 : 0.1;
      return Math.min(keys.size, 15) * position * (rect.width > window.innerWidth * 0.95 ? 0.5 : 1);
    };
    for (const [how, selector] of [['platform', GALLERY_SELECTORS.join(',')], ['generic', GENERIC_GALLERY]]) {
      let best = null, bestScore = 0;
      for (const el of document.querySelectorAll(selector)) {
        const s = score(el);
        // prefer the outer container when it holds the same images (main image + thumbnails)
        if (s > bestScore || (s === bestScore && best && el.contains(best))) { best = el; bestScore = s; }
      }
      if (best) return { els: [best], how };
    }
    return { els: [], how: 'none' };
  }

  // --- naming ------------------------------------------------------------------------

  function looksLikeModel(s) {
    return s && s.length >= 4 && s.length <= 30 && /\d/.test(s) && /[a-z]/i.test(s) && !/\s/.test(s) && (s.match(/-/g) || []).length <= 3;
  }

  function suggestName(products, shopify) {
    const p = products[0] || {};
    const sku = p.sku || p.mpn || shopify?.sku || document.querySelector('[itemprop="sku"]')?.textContent?.trim() || '';
    const segments = location.pathname.split('/').filter(Boolean);
    const pathModel = [...segments].reverse().find(looksLikeModel) || '';
    const title = p.name || shopify?.title || document.querySelector('meta[property="og:title"]')?.content ||
      document.querySelector('h1')?.textContent || document.title;
    const clean = (s) => String(s || '').replace(/\s+/g, ' ').trim();
    return { sku: clean(sku), model: pathModel.toUpperCase(), title: clean(title) };
  }

  // --- main --------------------------------------------------------------------------

  window.__photocutDetect = async (rule = {}) => {
    const minSize = rule.minSize || 400;
    const exclude = (rule.exclude || []).filter(Boolean);
    const include = (rule.include || []).filter(Boolean);
    const products = jsonLdProducts();
    const shopify = await shopifyImages();
    const gallery = pickGallery(rule);
    const warnings = [];
    if (gallery.how === 'rule-missed') warnings.push('The saved gallery area was not found on this page, so images were auto-detected. Use "Pick gallery area" to fix the rule.');

    const byKey = new Map();
    const order = [];
    const add = (c, extra) => {
      const url = upgrade(c.url, rule);
      if (!url || /\.svg(\?|$)/i.test(url)) return;
      const key = keyOf(url);
      let item = byKey.get(key);
      if (!item) {
        item = { url, fallback: c.url, thumb: c.thumb || c.url, size: 0, alt: c.alt || '', gallery: false, sources: [] };
        byKey.set(key, item);
        order.push(item);
      }
      item.size = Math.max(item.size, c.size || 0);
      item.gallery = item.gallery || !!extra.gallery;
      if (!item.sources.includes(extra.source)) item.sources.push(extra.source);
    };

    if (shopify?.images.length && gallery.how !== 'rule') {
      shopify.images.forEach((c) => add({ ...c, thumb: c.url.replace(/(\.\w+)(\?|$)/, '_400x$1$2') }, { gallery: true, source: 'shopify' }));
    }
    let galleryCount = 0;
    for (const el of gallery.els) {
      for (const c of imagesIn(el, true)) { add(c, { gallery: true, source: 'gallery' }); galleryCount++; }
    }
    if (gallery.how === 'rule' && !galleryCount) {
      warnings.push('The gallery area has no images PhotoCut can read. Use "Pick gallery area" again and widen the box (scroll up) until it says how many images are inside.');
    }
    ldImages(products).forEach((url) => add({ url, thumb: url, size: 0 }, { gallery: false, source: 'structured' }));
    const og = abs(document.querySelector('meta[property="og:image"]')?.content);
    if (og) add({ url: og, thumb: og, size: 0 }, { gallery: false, source: 'og' });
    for (const c of imagesIn(document.body)) {
      if (c.el.closest(CHROME)) continue;
      add(c, { gallery: false, source: 'page' });
    }

    const isJunk = (item) => JUNK.test(item.url) || JUNK.test(item.alt) || exclude.some((s) => item.url.includes(s));
    let items = order.filter((item) => !isJunk(item));
    if (include.length) {
      const kept = items.filter((item) => include.some((s) => item.url.includes(s)));
      if (kept.length) items = kept;
      else warnings.push('No image matched the rule\'s "include" filter; showing all images.');
    }
    // Small non-gallery images (icons, swatches, related products) are dropped.
    items = items.filter((item) => item.gallery || item.sources.includes('structured') || item.size === 0 || item.size >= minSize);
    // Unknown size and not structured: keep only if it came from a high-res attribute or looks like a photo URL.
    items = items.filter((item) => item.gallery || item.size > 0 || item.sources.includes('structured') || item.sources.includes('og') || IMAGE_EXT.test(item.url));

    // What to tick: the gallery; else structured product images; else the biggest photos.
    let selected = items.filter((i) => i.gallery);
    if (!selected.length) selected = items.filter((i) => i.sources.includes('structured'));
    if (!selected.length) {
      const max = Math.max(0, ...items.map((i) => i.size));
      selected = items.filter((i) => i.size >= Math.max(minSize, max * 0.5));
    }
    const picked = new Set(selected);
    const ordered = [...items.filter((i) => picked.has(i)), ...items.filter((i) => !picked.has(i)).sort((a, b) => b.size - a.size)];

    return {
      url: location.href,
      host: location.hostname,
      name: suggestName(products, shopify),
      galleryHow: shopify?.images.length && gallery.how !== 'rule' ? 'shopify' : gallery.how,
      warnings,
      images: ordered.slice(0, 80).map((i) => ({
        url: i.url, fallback: i.fallback, thumb: i.thumb, size: i.size, selected: picked.has(i),
        gallery: i.gallery, sources: i.sources, file: basename(i.url),
      })),
    };
  };
})();
