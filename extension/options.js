const $ = (id) => document.getElementById(id);
const TEXT = ['base_folder', 'rules_path', 'user_name'];
const CHECKS = ['open_folder', 'flatten'];

function host(req) {
  return chrome.runtime.sendMessage({ cmd: 'host', req }).then((r) => {
    if (!r?.ok) throw new Error(r?.error || 'No response');
    return r;
  });
}

function fill(cfg) {
  TEXT.forEach((k) => { $(k).value = cfg[k] || ''; });
  CHECKS.forEach((k) => { $(k).checked = !!cfg[k]; });
  $('tolerance').value = cfg.tolerance;
}

async function init() {
  try {
    fill((await host({ type: 'get_config' })).config);
  } catch (e) {
    const c = $('conn');
    c.hidden = false;
    c.className = 'message error';
    c.textContent = `The PhotoCut app is not reachable (${e.message}). Run install.bat, then reload this page.`;
    $('save').disabled = true;
  }
}

$('save').onclick = async () => {
  const config = {};
  TEXT.forEach((k) => { config[k] = $(k).value.trim(); });
  CHECKS.forEach((k) => { config[k] = $(k).checked; });
  config.tolerance = Math.max(1, Math.min(120, parseInt($('tolerance').value, 10) || 30));
  if (/^https?:\/\//i.test(config.rules_path)) {
    $('status').textContent = 'The rules file must be a path on this PC (e.g. a Google Drive for desktop folder), not a web link.';
    return;
  }
  try {
    fill((await host({ type: 'set_config', config })).config);
    $('status').textContent = 'Saved.';
  } catch (e) {
    $('status').textContent = `Not saved: ${e.message}`;
  }
};

for (const b of document.querySelectorAll('[data-browse]')) {
  b.onclick = async () => {
    const field = $(b.dataset.browse);
    const { path } = await host({ type: 'pick_path', kind: b.dataset.kind, initial: field.value });
    if (path) field.value = path.replace(/\//g, '\\');
  };
}

init();
