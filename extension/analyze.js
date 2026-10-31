// PhotoCut image check: should this image be trimmed?
//   trim       a product on a plain background (the background around it can go)
//   keep whole an image with text / feature callouts, or a photo with a scene or coloured design
// Runs in the background worker on a small copy of the image, so it is fast and needs no
// access to the page. Used by the popup to pre-set each image's Trim / Keep whole badge.

const ANALYZE_SIZE = 480;   // px, longest side of the copy that is analysed
const BG_TOLERANCE = 30;    // same as the crop's default colour tolerance

async function analyzeImage(url) {
  const res = await fetch(url, { credentials: 'include' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const bitmap = await createImageBitmap(await res.blob());
  const scale = Math.min(1, ANALYZE_SIZE / Math.max(bitmap.width, bitmap.height));
  const w = Math.max(1, Math.round(bitmap.width * scale));
  const h = Math.max(1, Math.round(bitmap.height * scale));
  const canvas = new OffscreenCanvas(w, h);
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.fillStyle = '#fff';  // transparent areas count as white, like the saved image
  ctx.fillRect(0, 0, w, h);
  ctx.drawImage(bitmap, 0, 0, w, h);
  bitmap.close();
  return classifyPixels(ctx.getImageData(0, 0, w, h));
}

function classifyPixels({ data, width: w, height: h }) {
  // Background colour: per-channel median of a 2 px border strip (as in the crop).
  const strip = Math.max(1, Math.min(2, Math.floor(Math.min(w, h) / 2)));
  const hist = [new Uint32Array(256), new Uint32Array(256), new Uint32Array(256)];
  let borderCount = 0;
  const forBorder = (fn) => {
    for (let y = 0; y < h; y++) {
      const edgeRow = y < strip || y >= h - strip;
      for (let x = 0; x < w; x++) {
        if (edgeRow || x < strip || x >= w - strip) fn((y * w + x) * 4);
      }
    }
  };
  forBorder((i) => { hist[0][data[i]]++; hist[1][data[i + 1]]++; hist[2][data[i + 2]]++; borderCount++; });
  const bg = hist.map((hc) => {
    let total = 0;
    for (let v = 0; v < 256; v++) { total += hc[v]; if (total >= borderCount / 2) return v; }
    return 255;
  });
  const isFg = (i) => Math.max(Math.abs(data[i] - bg[0]), Math.abs(data[i + 1] - bg[1]), Math.abs(data[i + 2] - bg[2])) > BG_TOLERANCE;

  // 1. Is the border a plain background? If not, it's a scene or a designed graphic.
  let plainBorder = 0;
  forBorder((i) => { if (!isFg(i)) plainBorder++; });
  const borderPlain = plainBorder / borderCount;
  if (borderPlain < 0.8) {
    return { trim: false, kind: 'scene', reason: 'Busy background (a scene or coloured design), so it is kept whole' };
  }

  // 2. Connected areas of non-background pixels.
  const n = w * h;
  const label = new Int32Array(n);
  const comps = [];
  const stack = new Int32Array(n);
  for (let p = 0; p < n; p++) {
    if (label[p] || !isFg(p * 4)) continue;
    const id = comps.length + 1;
    let top = 0, area = 0, x0 = w, y0 = h, x1 = 0, y1 = 0;
    stack[top++] = p;
    label[p] = id;
    while (top) {
      const q = stack[--top];
      const x = q % w, y = (q - x) / w;
      area++;
      if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
      for (const r of [x > 0 ? q - 1 : -1, x < w - 1 ? q + 1 : -1, y > 0 ? q - w : -1, y < h - 1 ? q + w : -1]) {
        if (r >= 0 && !label[r] && isFg(r * 4)) { label[r] = id; stack[top++] = r; }
      }
    }
    comps.push({ area, x0, y0, x1, y1, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, w: x1 - x0 + 1, h: y1 - y0 + 1 });
  }

  // 3. Text: many small, similar-height shapes sitting in rows (letters or words).
  const big = n * 0.015;
  const glyphs = comps.filter((c) => c.area >= 4 && c.area < big && c.h >= 3 && c.h <= h * 0.12 && c.w <= w * 0.5);
  glyphs.sort((a, b) => a.cy - b.cy);
  const lines = [];
  for (const g of glyphs) {
    const line = lines.find((l) => Math.abs(l.cy - g.cy) < Math.max(l.h, g.h) * 0.5 && Math.max(l.h, g.h) / Math.min(l.h, g.h) < 2);
    if (line) { line.items.push(g); line.cy = (line.cy * (line.items.length - 1) + g.cy) / line.items.length; }
    else lines.push({ cy: g.cy, h: g.h, items: [g] });
  }
  let textGlyphs = 0, textLines = 0;
  for (const line of lines) {
    const items = line.items.sort((a, b) => a.x0 - b.x0);
    let run = 1, best = 1;
    for (let i = 1; i < items.length; i++) {
      const gap = items[i].x0 - items[i - 1].x1;
      run = gap >= -1 && gap < line.h * 3 ? run + 1 : 1;
      best = Math.max(best, run);
    }
    if (best >= 3) { textLines++; textGlyphs += best; }
  }
  if (textGlyphs >= 6 && textLines >= 1) {
    return { trim: false, kind: 'text', reason: 'Has text or feature callouts, so it is kept whole' };
  }
  return { trim: true, kind: 'product', reason: 'Product on a plain background, so the background is trimmed' };
}
