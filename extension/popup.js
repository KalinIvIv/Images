// PhotoCut popup: detect images on the current tab, let the user adjust, save.

const $ = (id) => document.getElementById(id);
const state = {
  tab: null,
  domain: '',
  rule: {},          // rule used for detection (built-in or shared, plus a fresh pick)
  ruleSource: '',    // 'shared' | 'builtin' | ''
  sharedRule: null,
  picked: null,      // selector picked just now
  result: null,      // detector output
  initialSelected: new Set(),
  folderInfo: null,
  config: null,
};

function host(req) {
  return chrome.runtime.sendMessage({ cmd: 'host', req }).then((r) => {
    if (!r?.ok) throw new Error(r?.error || 'No response');
    return r;
  });
}

function message(html, kind = '') {
  const m = $('message');
  m.className = `message ${kind}`;
  m.innerHTML = html;
  m.hidden = !html;
}

const normalizeDomain = (h) => h.toLowerCase().replace(/^www\./, '');

function matchRule(sites, hostname) {
  const parts = normalizeDomain(hostname).split('.');
  for (let i = 0; i < Math.max(1, parts.length - 1); i++) {
    const d = parts.slice(i).join('.');
    if (sites?.[d]) return [d, sites[d]];
  }
  return [null, null];
}

async function activeTab() {
  const forced = new URLSearchParams(location.search).get('tab');  // used by tests
  if (forced) return chrome.tabs.get(Number(forced));
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

// --- startup ---------------------------------------------------------------------

async function init() {
  $('options').onclick = (e) => { e.preventDefault(); chrome.runtime.openOptionsPage(); };
  state.tab = await activeTab();
  if (!state.tab?.url?.startsWith('http')) {
    message('Open a product page first, then click PhotoCut.');
    return;
  }
  const url = new URL(state.tab.url);
  state.domain = normalizeDomain(url.hostname);
  $('site').textContent = state.domain;

  // A job for this tab still running or just finished? Show it.
  const jobKey = `job:${state.tab.id}`;
  const stored = (await chrome.storage.session.get(jobKey))[jobKey];
  if (stored && (stored.status === 'running' || Date.now() - stored.started < 60_000)) {
    showJob(stored);
  }
  chrome.storage.session.onChanged.addListener((changes) => {
    if (changes[jobKey]?.newValue) showJob(changes[jobKey].newValue);
  });
  if (stored?.status === 'running') return;

  let shared = { rules: { sites: {} } };
  try {
    const ping = await host({ type: 'ping' });
    state.config = ping.config;
    shared = await host({ type: 'get_rules' });
    if (shared.warning) message(`Shared rules file problem: ${escapeHtml(shared.warning)}`);
  } catch (e) {
    message(`<b>The PhotoCut app is not installed or not registered.</b><br>
      Run <code>install.bat</code> from the PhotoCut folder, then reopen this window.<br>
      <span class="small">(${escapeHtml(e.message)})</span>`, 'error');
    return;
  }

  const builtin = await fetch(chrome.runtime.getURL('rules_builtin.json')).then((r) => r.json()).catch(() => ({ sites: {} }));
  const [sharedDomain, sharedRule] = matchRule(shared.rules.sites, url.hostname);
  const [builtinDomain, builtinRule] = matchRule(builtin.sites, url.hostname);
  state.sharedRule = sharedRule;
  if (sharedRule) Object.assign(state, { rule: { ...sharedRule }, ruleSource: 'shared', ruleDomain: sharedDomain });
  else if (builtinRule) Object.assign(state, { rule: { ...builtinRule }, ruleSource: 'builtin', ruleDomain: builtinDomain });

  const pickKey = `picked:${state.tab.id}`;
  const picked = (await chrome.storage.session.get(pickKey))[pickKey];
  if (picked && normalizeDomain(picked.host) === state.domain) {
    // Kept until the user saves, so it survives the popup closing and reopening.
    state.picked = picked.selector;
    state.rule.gallery = picked.selector;
  }

  await detect();
}

async function detect() {
  message('');
  try {
    await chrome.scripting.executeScript({ target: { tabId: state.tab.id }, files: ['content/detect.js'] });
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: state.tab.id },
      func: (rule) => window.__photocutDetect(rule),
      args: [state.rule],
    });
    state.result = result;
  } catch (e) {
    message(`Could not read this page: ${escapeHtml(e.message)}`, 'error');
    return;
  }
  state.initialSelected = new Set(state.result.images.filter((i) => i.selected).map((i) => i.url));
  render();
}

// --- rendering ---------------------------------------------------------------------

function render() {
  const r = state.result;
  $('main').hidden = false;

  const names = [r.name.sku, r.name.model, r.name.title].filter(Boolean);
  const folder = $('folder');
  if (!folder.value) folder.value = sanitize(names[0] || 'images');
  $('name-hints').replaceChildren(...[...new Set(names.map(sanitize))].map((n) => {
    const b = document.createElement('button');
    b.textContent = n.length > 40 ? `${n.slice(0, 40)}…` : n;
    b.title = n;
    b.onclick = () => { folder.value = n; checkFolder(); };
    return b;
  }));

  const how = { rule: 'saved gallery area', shopify: 'Shopify product data', platform: 'shop layout', generic: 'auto-detected gallery', none: 'largest images', 'rule-missed': 'auto-detection' }[r.galleryHow] || r.galleryHow;
  let status = '';
  if (state.picked) status = `Using the gallery area you just picked (<code>${escapeHtml(state.picked)}</code>).`;
  else if (state.ruleSource === 'shared') {
    const by = state.sharedRule.updatedBy ? ` by ${escapeHtml(state.sharedRule.updatedBy)}` : '';
    const when = state.sharedRule.updatedAt ? `, ${state.sharedRule.updatedAt.slice(0, 10)}` : '';
    status = `Team rule for <b>${escapeHtml(state.ruleDomain)}</b>${by}${when} · found via ${how}.`;
  } else if (state.ruleSource === 'builtin') status = `Built-in rule for <b>${escapeHtml(state.ruleDomain)}</b> · found via ${how}.`;
  else status = `No rule for this site yet · found via ${how}.`;
  $('rule-status').innerHTML = status;

  $('warnings').replaceChildren(...r.warnings.map((w) => {
    const d = document.createElement('div');
    d.className = 'warning small';
    d.textContent = w;
    return d;
  }));

  const gallery = r.images.filter((i) => state.initialSelected.has(i.url));
  const others = r.images.filter((i) => !state.initialSelected.has(i.url));
  $('grid-gallery').replaceChildren(...gallery.map(card));
  $('grid-others').replaceChildren(...others.map(card));
  $('others-title').hidden = !others.length;
  if (!r.images.length) message('No product images found on this page. Try "Pick gallery area".');

  update();
  checkFolder();
  folder.focus();
  folder.select();
}

function card(img) {
  const c = document.createElement('div');
  c.className = `card${img.selected ? ' on' : ''}`;
  c.title = `${img.file}\n${img.url}\nfound via: ${img.sources.join(', ')}`;
  const pic = document.createElement('img');
  pic.src = img.thumb;
  pic.loading = 'lazy';
  pic.referrerPolicy = 'no-referrer';
  pic.onerror = () => { if (pic.src !== img.url) pic.src = img.url; };
  const size = document.createElement('div');
  size.className = 'size';
  size.textContent = `${img.size ? `${img.size}px` : 'full size'} · ${img.file}`;
  const tick = document.createElement('div');
  tick.className = 'tick';
  c.append(pic, size, tick);
  c.onclick = () => {
    img.selected = !img.selected;
    c.classList.toggle('on', img.selected);
    update();
  };
  return c;
}

function selectedImages() {
  return state.result.images.filter((i) => i.selected);
}

function changedSelection() {
  return state.result.images.some((i) => i.selected !== state.initialSelected.has(i.url));
}

function update() {
  const n = selectedImages().length;
  $('save').textContent = n ? `Save ${n} image${n > 1 ? 's' : ''}` : 'Save';
  $('save').disabled = !n || !$('folder').value.trim();
  $('count').textContent = `${n} of ${state.result.images.length} selected`;
  const learnable = !!state.picked || changedSelection();
  $('remember-wrap').hidden = !learnable;
  $('remember-domain').textContent = state.ruleDomain || state.domain;
}

let folderTimer = null;
function checkFolder() {
  clearTimeout(folderTimer);
  update();
  folderTimer = setTimeout(async () => {
    const name = $('folder').value.trim();
    if (!name) return;
    try {
      const st = await host({ type: 'folder_status', folder: name });
      state.folderInfo = st;
      $('folder-status').textContent = st.count
        ? `${st.path} already has ${st.count} image${st.count > 1 ? 's' : ''}; new ones will be numbered from ${st.next}.`
        : `Saves to ${st.path}${st.path.includes('\\') ? '\\' : '/'}${st.name}_1.png …`;
      $('new-folder-wrap').hidden = !st.count;
    } catch (e) {
      $('folder-status').textContent = e.message;
    }
  }, 200);
}

// --- actions -------------------------------------------------------------------------

async function saveRule() {
  const base = state.sharedRule ? { ...state.sharedRule } : { ...(state.ruleSource === 'builtin' ? state.rule : {}) };
  delete base.updatedBy;
  delete base.updatedAt;
  if (state.picked) base.gallery = state.picked;
  // Images that were pre-selected but the user rejected: skip them (by file name) next time.
  // This learns site-wide images such as logos, badges and banners.
  const rejected = state.result.images
    .filter((i) => state.initialSelected.has(i.url) && !i.selected)
    .map((i) => i.file)
    .filter((f) => f && f.length > 3);
  base.exclude = [...new Set([...(base.exclude || []), ...rejected])].slice(-200);
  const domain = state.ruleDomain || state.domain;
  await host({ type: 'save_rule', domain, rule: base });
}

async function save() {
  const images = selectedImages();
  if (!images.length) return;
  $('save').disabled = true;

  if (!$('remember-wrap').hidden && $('remember').checked) {
    try {
      await saveRule();
    } catch (e) {
      message(`The images will be saved, but the site rule was not: ${escapeHtml(e.message)}`);
    }
  }

  await chrome.storage.session.remove(`picked:${state.tab.id}`);
  const folder = sanitize($('folder').value);
  const res = await chrome.runtime.sendMessage({
    cmd: 'startJob',
    tabId: state.tab.id,
    pageUrl: state.tab.url,
    folder,
    mode: $('new-folder').checked ? 'new' : 'add',
    images: images.map((i) => ({ url: i.url, fallback: i.fallback })),
  });
  if (!res?.ok) message(`Could not start: ${escapeHtml(res?.error || 'unknown error')}`, 'error');
}

function showJob(job) {
  $('main').hidden = true;
  $('job').hidden = false;
  const total = job.total || 1;
  const done = job.status !== 'running';
  $('job-progress').max = total * 2;
  $('job-progress').value = done ? total * 2 : (job.downloaded || 0) + (job.processed || 0);
  if (job.status === 'running') {
    $('job-title').textContent = `Saving ${job.total} image${job.total > 1 ? 's' : ''}…`;
    $('job-detail').textContent = `Downloaded ${job.downloaded || 0}, edited ${job.processed || 0} of ${job.total}`;
  } else if (job.status === 'error') {
    $('job-title').textContent = 'Something went wrong';
    $('job-detail').textContent = job.error;
  } else {
    const n = job.saved?.length || 0;
    const secs = ((Date.now() - job.started) / 1000).toFixed(1);
    $('job-title').textContent = `Saved ${n} image${n === 1 ? '' : 's'}`;
    $('job-detail').textContent = `${job.folder}  ·  ${secs}s`;
    $('job-errors').replaceChildren(...(job.errors || []).map((e) => {
      const li = document.createElement('li');
      li.textContent = e;
      return li;
    }));
  }
  $('open-folder').hidden = !job.saved?.length;
  $('open-folder').onclick = () => host({ type: 'open_folder', path: job.folder });
  $('again').hidden = !done;
  $('again').onclick = async () => {
    await chrome.storage.session.remove(`job:${state.tab.id}`);
    location.reload();
  };
}

// --- helpers -----------------------------------------------------------------------------

function sanitize(name) {
  return String(name).replace(/[<>:"/\\|?*\x00-\x1f]/g, ' ').replace(/\s+/g, ' ').trim().replace(/[. ]+$/, '').slice(0, 80);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

$('folder').addEventListener('input', checkFolder);
$('folder').addEventListener('keydown', (e) => { if (e.key === 'Enter' && !$('save').disabled) save(); });
$('save').onclick = save;
$('all').onclick = () => { state.result.images.forEach((i) => { i.selected = true; }); render(); };
$('none').onclick = () => { state.result.images.forEach((i) => { i.selected = false; }); render(); };
$('pick').onclick = async () => {
  await chrome.scripting.executeScript({ target: { tabId: state.tab.id }, files: ['content/picker.js'] });
  window.close();
};

init().catch((e) => message(escapeHtml(e.message), 'error'));
