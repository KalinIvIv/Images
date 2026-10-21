// PhotoCut gallery picker: highlight the element under the mouse, click to choose it
// as the product gallery for this site. Scroll / arrow keys widen or narrow the selection.

(() => {
  if (window.__photocutPicker) { window.__photocutPicker.start(); return; }

  const UNSTABLE_CLASS = /\d{3,}|^(is-|js-|has-)|active|selected|current|hover|focus|open|visible|hidden|loaded|lazy|animate|swiper-slide-|slick-(active|current|cloned)|^ng-|^css-|^sc-|^jsx-|__\w{5,}$/i;

  let overlay, box, label, banner, current = null, stack = [];

  function el(tag, style, text) {
    const e = document.createElement(tag);
    e.style.cssText = style;
    if (text) e.textContent = text;
    return e;
  }

  function build() {
    overlay = el('div', 'all:initial;position:fixed;inset:0;z-index:2147483647;pointer-events:none;font:13px/1.4 system-ui,sans-serif');
    box = el('div', 'position:fixed;border:3px solid #2563eb;background:rgba(37,99,235,.12);border-radius:4px;transition:all .05s');
    label = el('div', 'position:fixed;background:#1e3a8a;color:#fff;padding:3px 8px;border-radius:4px;white-space:nowrap;max-width:60vw;overflow:hidden;text-overflow:ellipsis');
    banner = el('div', 'position:fixed;top:12px;left:50%;transform:translateX(-50%);background:#111827;color:#fff;padding:10px 16px;border-radius:8px;box-shadow:0 4px 20px rgba(0,0,0,.3)',
      'PhotoCut: click the product gallery (main image + thumbnails).  Scroll or ↑/↓ to widen/narrow.  Esc to cancel.');
    overlay.append(box, label, banner);
  }

  const countImages = (e) => new Set([...e.querySelectorAll('img')].map((i) => i.currentSrc || i.src)).size +
    e.querySelectorAll('[style*="url("]').length;

  function show(e) {
    current = e;
    const r = e.getBoundingClientRect();
    Object.assign(box.style, { left: `${r.left}px`, top: `${r.top}px`, width: `${r.width}px`, height: `${r.height}px` });
    label.textContent = `${countImages(e)} images  ·  ${selectorFor(e)}`;
    Object.assign(label.style, { left: `${Math.max(4, r.left)}px`, top: `${r.top > 30 ? r.top - 26 : r.bottom + 4}px` });
  }

  function part(e) {
    const tag = e.tagName.toLowerCase();
    const classes = [...e.classList].filter((c) => !UNSTABLE_CLASS.test(c)).slice(0, 2);
    const attr = ['data-testid', 'data-component', 'data-section-type', 'data-role']
      .map((a) => e.getAttribute(a) && `[${a}="${CSS.escape(e.getAttribute(a))}"]`).find(Boolean) || '';
    return tag + classes.map((c) => `.${CSS.escape(c)}`).join('') + attr;
  }

  // A selector that finds this element on other product pages of the same site:
  // stable classes/attributes, anchored on an id when there is a sensible one.
  function selectorFor(e) {
    if (e.id && !/\d{3,}|[:]/.test(e.id)) return `#${CSS.escape(e.id)}`;
    let sel = part(e), node = e.parentElement;
    for (let depth = 0; depth < 4 && node && node !== document.body; depth++) {
      if (document.querySelectorAll(sel).length === 1) break;
      if (node.id && !/\d{3,}|[:]/.test(node.id)) { sel = `#${CSS.escape(node.id)} ${sel}`; break; }
      const p = part(node);
      if (p.includes('.') || p.includes('[')) sel = `${p} ${sel}`;
      node = node.parentElement;
    }
    return sel;
  }

  function toast(text) {
    const t = el('div', 'all:initial;position:fixed;bottom:20px;right:20px;z-index:2147483647;background:#15803d;color:#fff;padding:12px 16px;border-radius:8px;font:14px/1.4 system-ui,sans-serif;box-shadow:0 4px 20px rgba(0,0,0,.3)', text);
    document.documentElement.append(t);
    setTimeout(() => t.remove(), 6000);
  }

  function onMove(ev) {
    const target = document.elementFromPoint(ev.clientX, ev.clientY);
    // Keep a widened selection while the mouse stays inside it.
    if (!target || target === current || overlay.contains(target) || (stack.length && current?.contains(target))) return;
    stack = [];
    show(target);
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
    ev.preventDefault();
    ev.deltaY < 0 ? widen() : narrow();
  }

  function onKey(ev) {
    if (ev.key === 'Escape') stop();
    else if (ev.key === 'ArrowUp') { ev.preventDefault(); widen(); }
    else if (ev.key === 'ArrowDown') { ev.preventDefault(); narrow(); }
    else if (ev.key === 'Enter' && current) choose(ev);
  }

  function choose(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    const selector = selectorFor(current);
    stop();
    chrome.runtime.sendMessage({ cmd: 'picked', selector });
    toast('Gallery area saved. Click the PhotoCut icon to continue.');
  }

  function swallow(ev) {
    ev.preventDefault();
    ev.stopPropagation();
  }

  function start() {
    if (overlay?.isConnected) return;
    build();
    document.documentElement.append(overlay);
    document.addEventListener('mousemove', onMove, true);
    document.addEventListener('wheel', onWheel, { capture: true, passive: false });
    document.addEventListener('keydown', onKey, true);
    document.addEventListener('click', choose, true);
    for (const t of ['mousedown', 'mouseup', 'pointerdown', 'pointerup']) document.addEventListener(t, swallow, true);
  }

  function stop() {
    overlay?.remove();
    document.removeEventListener('mousemove', onMove, true);
    document.removeEventListener('wheel', onWheel, { capture: true });
    document.removeEventListener('keydown', onKey, true);
    document.removeEventListener('click', choose, true);
    for (const t of ['mousedown', 'mouseup', 'pointerdown', 'pointerup']) document.removeEventListener(t, swallow, true);
    current = null;
    stack = [];
  }

  window.__photocutPicker = { start, stop, selectorFor };
  start();
})();
