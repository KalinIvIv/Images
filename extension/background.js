// PhotoCut background service worker.
// Owns the connection to the local app (native messaging) and runs save jobs,
// so a job keeps going even if the popup is closed.

const HOST = 'com.photocut.host';
const DOWNLOAD_CONCURRENCY = 6;
const REFERER_RULE_ID = 1;

let port = null;
let nextId = 1;
const pending = new Map();   // request id -> {resolve, reject}
const jobs = new Map();      // jobId -> {tabId, resolve}

function connect() {
  if (port) return port;
  port = chrome.runtime.connectNative(HOST);
  port.onMessage.addListener(onHostMessage);
  port.onDisconnect.addListener(() => {
    const error = chrome.runtime.lastError?.message || 'PhotoCut app disconnected';
    port = null;
    for (const { reject } of pending.values()) reject(new Error(error));
    pending.clear();
    for (const [jobId, job] of jobs) finishJob(jobId, { error });
  });
  return port;
}

function request(msg) {
  return new Promise((resolve, reject) => {
    const id = nextId++;
    pending.set(id, { resolve, reject });
    try {
      connect().postMessage({ ...msg, id });
    } catch (e) {
      pending.delete(id);
      reject(e);
    }
  });
}

function onHostMessage(msg) {
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    msg.ok ? resolve(msg) : reject(new Error(msg.error || 'Request failed'));
  } else if (msg.type === 'progress') {
    updateJob(msg.jobId, { processed: msg.done, total: msg.total });
  } else if (msg.type === 'job_done') {
    finishJob(msg.jobId, { folder: msg.folder, saved: msg.saved, errors: msg.errors });
  }
}

// --- job state, kept in session storage so a reopened popup can show it --------

async function updateJob(jobId, changes) {
  const job = jobs.get(jobId);
  if (!job) return;
  Object.assign(job.state, changes);
  await chrome.storage.session.set({ [`job:${job.tabId}`]: job.state });
}

async function finishJob(jobId, result) {
  const job = jobs.get(jobId);
  if (!job) return;
  jobs.delete(jobId);
  job.state = { ...job.state, ...result, status: result.error ? 'error' : 'done' };
  await chrome.storage.session.set({ [`job:${job.tabId}`]: job.state });
  await clearReferer();
  const count = result.saved?.length || 0;
  chrome.action.setBadgeBackgroundColor({ color: result.error || result.errors?.length ? '#b45309' : '#15803d' });
  chrome.action.setBadgeText({ tabId: job.tabId, text: result.error ? '!' : String(count) });
}

// Some image servers only answer when the request carries the shop's address as Referer.
async function setReferer(pageUrl) {
  const origin = new URL(pageUrl).origin + '/';
  await chrome.declarativeNetRequest.updateSessionRules({
    removeRuleIds: [REFERER_RULE_ID],
    addRules: [{
      id: REFERER_RULE_ID,
      priority: 1,
      action: { type: 'modifyHeaders', requestHeaders: [{ header: 'Referer', operation: 'set', value: origin }] },
      condition: { tabIds: [chrome.tabs.TAB_ID_NONE], resourceTypes: ['xmlhttprequest', 'other'] },
    }],
  });
}

async function clearReferer() {
  if (jobs.size) return;
  await chrome.declarativeNetRequest.updateSessionRules({ removeRuleIds: [REFERER_RULE_ID] });
}

function toBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}

async function fetchImage(url) {
  const res = await fetch(url, { credentials: 'include' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const type = res.headers.get('content-type') || '';
  if (type.startsWith('text/')) throw new Error(`not an image (${type})`);
  return toBase64(await res.arrayBuffer());
}

async function startJob({ tabId, pageUrl, folder, mode, images }) {
  const jobId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const job = { tabId, state: { status: 'running', folder, downloaded: 0, processed: 0, total: images.length, started: Date.now() } };
  jobs.set(jobId, job);
  await chrome.storage.session.set({ [`job:${tabId}`]: job.state });
  chrome.action.setBadgeText({ tabId, text: '…' });

  try {
    const start = await request({ type: 'job_start', jobId, folder, mode, total: images.length });
    await updateJob(jobId, { folder: start.folder });
    await setReferer(pageUrl);

    let next = 0;
    const worker = async () => {
      while (next < images.length) {
        const index = next++;
        const { url, fallback } = images[index];
        let msg;
        try {
          msg = { data: await fetchImage(url) };
        } catch (e) {
          // The upgraded high-resolution URL failed - fall back to the URL the page displays.
          try {
            if (!fallback || fallback === url) throw e;
            msg = { data: await fetchImage(fallback) };
          } catch {
            msg = { error: e.message };
          }
        }
        connect().postMessage({ type: 'job_image', jobId, index, url, ...msg });
        await updateJob(jobId, { downloaded: (job.state.downloaded || 0) + 1 });
      }
    };
    await Promise.all(Array.from({ length: DOWNLOAD_CONCURRENCY }, worker));
    connect().postMessage({ type: 'job_end', jobId });
  } catch (e) {
    await finishJob(jobId, { error: e.message });
  }
  return { jobId };
}

// --- messages from the popup, options page and picker ---------------------------

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  const reply = (p) => p.then((r) => sendResponse({ ok: true, ...r }), (e) => sendResponse({ ok: false, error: e.message }));

  if (msg.cmd === 'host') {
    reply(request(msg.req));
    return true;
  }
  if (msg.cmd === 'startJob') {
    reply(startJob(msg));
    return true;
  }
  if (msg.cmd === 'picked' && sender.tab) {
    const host = new URL(sender.tab.url).hostname;
    chrome.storage.session
      .set({ [`picked:${sender.tab.id}`]: { selector: msg.selector, host } })
      .then(() => chrome.action.openPopup?.({ windowId: sender.tab.windowId }))
      .catch(() => {});  // if the popup can't open itself, the page toast tells the user to click the icon
    sendResponse({ ok: true });
  }
  return false;
});
