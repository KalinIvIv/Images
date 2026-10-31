// PhotoCut gallery picker. Hover highlights the area under the mouse; a click locks it and
// shows a bar to make it bigger/smaller (also ↑/↓ or the scroll wheel); "Use this area" saves it
// as the product gallery for this site. Nothing depends on the scroll wheel, which Chrome
// sometimes won't let a page intercept.

(() => {
  if (window.__photocutPicker) { window.__photocutPicker.start(); return; }

  const UNSTABLE_CLASS = /\d{3,}|^(is-|js-|has-)|active|selected|current|hover|focus|open|visible|hidden|loaded|lazy|animate|swiper-slide-|slick-(active|current|cloned)|^ng-|^css-|^sc-|^jsx-|__\w{5,}$/i;

  let overlay, box, label, banner, bar, count, current = null, stack = [], locked = false, lastX = -1, lastY = -1;

  function el(tag, style, text) {
    const e = document.createElement(tag);
    e.style.cssText = style;
    if (text) e.textContent = text;
    return e;
  }

  const BUTTON = 'all:initial;cursor:pointer;font:600 13px/1 system-ui,sans-serif;padding:8px 12px;border-radius:6px;background:#374151;color:#fff';

  function build() {
    overlay = el('div', 'all:initial;position:fixed;inset:0;z-index:2147483647;pointer-events:none;font:13px/1.4 system-ui,sans-serif');
    box = el('div', 'position:fixed;border:3px solid #2563eb;background:rgba(37,99,235,.12);border-radius:4px;transition:all .05s');
    label = el('div', 'position:fixed;background:#1e3a8a;color:#fff;padding:3px 8px;border-radius:4px;white-space:nowrap');
    banner = el('div', 'position:fixed;top:12px;left:50%;transform:translateX(-50%);max-width:90vw;background:#111827;color:#fff;padding:10px 16px;border-radius:8px;box-shadow:0 4px 20px rgba(0,0,0,.3)',
      'PhotoCut: click the product gallery (main photo + thumbnails). Esc to cancel.');
    bar = el('div', 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);display:none;gap:8px;align-items:center;pointer-events:auto;background:#111827;color:#fff;padding:8px;border-radius:10px;box-shadow:0 4px 20px rgba(0,0,0,.35);white-space:nowrap');
    const button = (act, text, bg) => {
      const b = el('button', BUTTON + (bg ? `;background:${bg}` : ''), text);
      b.dataset.act = act;
      return b;
    };
    count = el('span', 'padding:0 8px;min-width:150px;text-align:center');
    bar.append(button('smaller', '− Smaller'), button('bigger', '+ Bigger'), count, button('use', 'Use this area', '#2563eb'), button('cancel', 'Cancel'));
    overlay.append(box, label, banner, bar);
  }

  // Same idea as the detector: <img> tags plus CSS background images.
  function countImages(e) {
    const imgs = e.tagName === 'IMG' ? [e] : [...e.querySelectorAll('img')];
    const urls = new Set(imgs.map((i) => i.currentSrc || i.src).filter(Boolean));
    for (const n of [e, ...e.querySelectorAll('*')].slice(0, 600)) {
      const m = getComputedStyle(n).backgroundImage.match(/url\(["']?([^"')]+)/);
      if (m) urls.add(m[1]);
    }
    return urls.size;
  }

  function show(e) {
    current = e;
    const r = e.getBoundingClientRect();
    Object.assign(box.style, { left: `${r.left}px`, top: `${r.top}px`, width: `${r.width}px`, height: `${r.height}px` });
    const n = countImages(e);
    const text = n ? `${n} image${n > 1 ? 's' : ''} in this area` : 'No images here: make it bigger';
    label.textContent = text;
    label.style.background = n ? '#1e3a8a' : '#b91c1c';
    Object.assign(label.style, { left: `${Math.max(4, r.left)}px`, top: `${r.top > 30 ? r.top - 26 : r.bottom + 4}px` });
    count.textContent = text;
    bar.querySelector('[data-act="use"]').style.opacity = n ? '1' : '.5';
  }

  function lock(e) {
    locked = true;
    if (e !== current) { stack = []; show(e); }
    bar.style.display = 'flex';
    banner.textContent = 'PhotoCut: make the box cover the main photo and its thumbnails, then press "Use this area". Click elsewhere to start again.';
  }

  function part(e) {
    const tag = e.tagName.toLowerCase();
    const classes = [...e.classList].filter((c) => !UNSTABLE_CLASS.test(c)).slice(0, 2);
    const attr = ['data-testid', 'data-component', 'data-section-type', 'data-role']
      .map((a) => e.getAttribute(a) && `[${a}="${CSS.escape(e.getAttribute(a))}"]`).find(Boolean) || '';
    return tag + classes.map((c) => `.${CSS.escape(c)}`).join('') + attr;
  }

  const stableId = (n) => n.id && !/\d{3,}|[:]/.test(n.id) && document.querySelectorAll(`#${CSS.escape(n.id)}`).length === 1;

  function matchesOnly(sel, e) {
    try {
      const found = document.querySelectorAll(sel);
      return found.length === 1 && found[0] === e;
    } catch { return false; }
  }

  function nthStep(n) {
    let i = 1;
    for (let s = n.previousElementSibling; s; s = s.previousElementSibling) if (s.tagName === n.tagName) i++;
    return `${n.tagName.toLowerCase()}:nth-of-type(${i})`;
  }

  // A selector that matches exactly this element and, ideally, the same area on other
  // product pages of the site: stable classes/attributes or an id first; if the page only
  // has auto-generated class names, fall back to the element's position in the page.
  function selectorFor(e) {
    if (stableId(e)) return `#${CSS.escape(e.id)}`;
    let sel = part(e), node = e.parentElement;
    for (let depth = 0; depth < 5 && !matchesOnly(sel, e) && node && node !== document.documentElement; depth++, node = node.parentElement) {
      if (stableId(node)) { sel = `#${CSS.escape(node.id)} ${sel}`; break; }
      const p = part(node);
      if (p.includes('.') || p.includes('[')) sel = `${p} ${sel}`;
    }
    if (matchesOnly(sel, e)) return sel;

    const steps = [];
    for (node = e; node && node !== document.body && !stableId(node); node = node.parentElement) steps.unshift(nthStep(node));
    const anchor = node && node !== document.body ? `#${CSS.escape(node.id)}` : 'body';
    return `${anchor} > ${steps.join(' > ')}`;
  }

  function toast(text) {
    const t = el('div', 'all:initial;position:fixed;bottom:20px;right:20px;z-index:2147483647;background:#15803d;color:#fff;padding:12px 16px;border-radius:8px;font:14px/1.4 system-ui,sans-serif;box-shadow:0 4px 20px rgba(0,0,0,.3)', text);
    document.documentElement.append(t);
    setTimeout(() => t.remove(), 6000);
  }

  function onMove(ev) {
    // Browsers also send mousemove when the page scrolls under a still mouse; only a real
    // move may change the selection, otherwise a scroll would undo a widened selection.
    if (locked || (ev.clientX === lastX && ev.clientY === lastY)) return;
    lastX = ev.clientX;
    lastY = ev.clientY;
    const target = document.elementFromPoint(ev.clientX, ev.clientY);
    // Keep a widened selection while the mouse stays inside it.
    if (!target || target === current || overlay.contains(target) || (stack.length && current?.contains(target))) return;
    stack = [];
    show(target);
  }

  // Keep the box on the selected area if the page scrolls.
  function onScroll() {
    if (current) show(current);
  }

  function widen() {
    if (current?.parentElement && current.parentElement !== document.documentElement) {
      stack.push(current);
      show(current.parentElement);
    }
  }

  function narrow() {
    if (stack.length) show(stack.pop());
  }

  function onWheel(ev) {
    if (!current || bar.contains(ev.target)) return;
    ev.preventDefault();  // has no effect when Chrome marks the event non-cancelable; the box follows the scroll then
    ev.deltaY < 0 ? widen() : narrow();
  }

  function onKey(ev) {
    if (ev.key === 'Escape') stop();
    else if (ev.key === 'ArrowUp') { ev.preventDefault(); widen(); }
    else if (ev.key === 'ArrowDown') { ev.preventDefault(); narrow(); }
    else if (ev.key === 'Enter' && current) { ev.preventDefault(); use(); }
  }

  function onClick(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    const act = ev.target.closest?.('[data-act]')?.dataset.act;
    if (act === 'bigger') return widen();
    if (act === 'smaller') return narrow();
    if (act === 'use') return use();
    if (act === 'cancel') return stop();
    if (bar.contains(ev.target)) return;
    // A click inside the current (possibly widened) box locks it; elsewhere starts again there.
    const target = document.elementFromPoint(ev.clientX, ev.clientY);
    lock(current && target && current.contains(target) ? current : target || current);
  }

  function use() {
    if (!current || !countImages(current)) return;
    const selector = selectorFor(current);
    stop();
    chrome.runtime.sendMessage({ cmd: 'picked', selector });
    toast('Gallery area saved. Click the PhotoCut icon to continue.');
  }

  function swallow(ev) {
    if (bar?.contains(ev.target)) return;
    ev.preventDefault();
    ev.stopPropagation();
  }

  // Listen on window in the capture phase so the page's own scripts can't swallow the events.
  const LISTENERS = [
    ['mousemove', onMove, true],
    ['wheel', onWheel, { capture: true, passive: false }],
    ['keydown', onKey, true],
    ['click', onClick, true],
    ['scroll', onScroll, { capture: true, passive: true }],
    ...['mousedown', 'mouseup', 'pointerdown', 'pointerup', 'auxclick', 'contextmenu'].map((t) => [t, swallow, true]),
  ];

  function start() {
    if (overlay?.isConnected) return;
    build();
    document.documentElement.append(overlay);
    locked = false;
    lastX = lastY = -1;
    for (const [type, fn, opts] of LISTENERS) window.addEventListener(type, fn, opts);
  }

  function stop() {
    overlay?.remove();
    for (const [type, fn, opts] of LISTENERS) window.removeEventListener(type, fn, opts);
    current = null;
    stack = [];
    locked = false;
  }

  window.__photocutPicker = { start, stop, selectorFor };
  start();
})();
