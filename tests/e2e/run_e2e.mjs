// End-to-end test: real Chromium + the PhotoCut extension + the native host + fake shops.
// Run:  node tests/e2e/run_e2e.mjs   (needs `npm i playwright` somewhere on NODE_PATH)

import { chromium } from 'playwright';
import { spawn, execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const EXT = path.join(ROOT, 'extension');
const PORT = 8765;
const SITE = `http://127.0.0.1:${PORT}`;
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'photocut-e2e-'));
const cfgDir = path.join(tmp, 'cfg');
const userData = path.join(tmp, 'chrome');
const out = path.join(tmp, 'out');
const rulesFile = path.join(tmp, 'drive', 'rules.json');
const env = { ...process.env, PYTHONPATH: path.join(ROOT, 'app'), PHOTOCUT_CONFIG_DIR: cfgDir };

let failures = 0;
function check(cond, what) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${what}`);
  if (!cond) failures++;
}

const py = (args) => execFileSync('python3', args, { env, encoding: 'utf-8' });
py(['-c', `from photocut import install; install.install([r"${path.join(userData, 'NativeMessagingHosts')}"])`]);
py(['-m', 'photocut', 'config', `base_folder=${out}`, `rules_path=${rulesFile}`, 'open_folder=false', 'user_name=E2E']);

const server = spawn('python3', [path.join(ROOT, 'tests/e2e/fixture_server.py'), String(PORT)], { stdio: 'inherit' });
await new Promise((r) => setTimeout(r, 800));

const context = await chromium.launchPersistentContext(userData, {
  channel: 'chromium',
  headless: true,
  env,
  args: [`--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`],
});

try {
  let [worker] = context.serviceWorkers();
  worker = worker || await context.waitForEvent('serviceworker');
  const extId = worker.url().split('/')[2];
  check(extId === 'dhmhjgdnpjnnfpajmflglfajjmofnjmg', `extension has the fixed ID (${extId})`);

  async function openPopup(productPage) {
    const tabId = await worker.evaluate(async (url) => (await chrome.tabs.query({})).find((t) => t.url === url).id, productPage.url());
    const popup = await context.newPage();
    await popup.setViewportSize({ width: 560, height: 600 });
    await popup.goto(`chrome-extension://${extId}/popup.html?tab=${tabId}`);
    await popup.waitForSelector('#main:not([hidden]), .message.error', { timeout: 15000 });
    return popup;
  }

  async function cards(popup) {
    return popup.$$eval('.card', (els) => els.map((c) => ({ on: c.classList.contains('on'), title: c.title, gallery: !!c.closest('#grid-gallery') })));
  }

  async function saveAndWait(popup) {
    const t0 = Date.now();
    await popup.click('#save');
    await popup.waitForFunction(() => /^Saved|wrong/.test(document.querySelector('#job-title')?.textContent || ''), null, { timeout: 60000 });
    return { title: await popup.textContent('#job-title'), detail: await popup.textContent('#job-detail'), secs: (Date.now() - t0) / 1000 };
  }

  const pngs = (folder) => fs.existsSync(folder) ? fs.readdirSync(folder).filter((f) => f.endsWith('.png')).sort() : [];

  // --- 1. Shopify store ---------------------------------------------------------
  {
    const page = await context.newPage();
    await page.goto(`${SITE}/products/test-bundle?variant=1`);
    const popup = await openPopup(page);
    const c = await cards(popup);
    const on = c.filter((x) => x.on).map((x) => x.title.split('\n')[1]);
    check(on.length === 3 && on.every((u) => /bundle-(front|back|box)\.jpg$/.test(u)), `shopify: 3 full-size product images pre-selected (${on.map((u) => u.split('/').pop())})`);
    check(!c.some((x) => /logo/.test(x.title)), 'shopify: logo not offered');
    check(!c.some((x) => x.on && /other-product/.test(x.title)), 'shopify: related product not selected');
    check(await popup.inputValue('#folder') === 'PG-7890', 'shopify: folder name from SKU');
    const r = await saveAndWait(popup);
    check(r.title === 'Saved 3 images', `shopify: saved (${r.title}, ${r.secs.toFixed(1)}s)`);
    const files = pngs(path.join(out, 'PG-7890'));
    check(JSON.stringify(files) === JSON.stringify(['PG-7890_1.png', 'PG-7890_2.png', 'PG-7890_3.png']), `shopify: files ${files}`);
    await popup.close();
    await page.close();
  }

  // --- 2. LG-like custom layout -------------------------------------------------------
  {
    const page = await context.newPage();
    await page.goto(`${SITE}/za/monitors/32gs95uv-b/`);
    const popup = await openPopup(page);
    const c = await cards(popup);
    const on = c.filter((x) => x.on).map((x) => x.title.split('\n')[1].split('/').pop());
    check(JSON.stringify(on) === JSON.stringify(['32gs95uv-01_2000x2000.jpg', '32gs95uv-02_2000x2000.jpg', '32gs95uv-03_2000x2000.jpg']),
      `lg: gallery found, high-res versions, duplicates merged (${on})`);
    check(!c.some((x) => x.on && /(banner|award|og-|logo|payment|menu-promo)/.test(x.title)), 'lg: banners/awards/logos not selected');
    check(!c.some((x) => /lg-logo|payment-icons|red-dot/.test(x.title)), 'lg: logo, payment icons, awards not offered at all');
    check(await popup.inputValue('#folder') === '32GS95UV-B', 'lg: folder name = model code from URL');
    const r = await saveAndWait(popup);
    check(r.title === 'Saved 3 images' && r.secs < 15, `lg: saved in ${r.secs.toFixed(1)}s`);
    // run again: numbering continues, nothing overwritten
    await popup.click('#again');
    await popup.waitForSelector('#main:not([hidden])');
    await popup.waitForFunction(() => /numbered from 4/.test(document.querySelector('#folder-status').textContent));
    check(true, 'lg: popup warns the folder already has 3 images');
    await saveAndWait(popup);
    check(pngs(path.join(out, '32GS95UV-B')).length === 6, 'lg: second save continued numbering to _6');
    await popup.close();
    await page.close();
  }

  // --- 3. Teaching a site with the picker ------------------------------------------------
  {
    const page = await context.newPage();
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto(`${SITE}/shop/item-77`);
    let popup = await openPopup(page);
    let c = await cards(popup);
    const wrong = c.filter((x) => x.on).map((x) => x.title.split('\n')[0]);
    console.log(`      auto-detected before teaching: ${wrong}`);

    // user clicks "Pick gallery area", then clicks the real gallery on the page
    await popup.evaluate(() => { window.close = () => {}; });
    await popup.click('#pick');
    await page.bringToFront();
    await page.waitForFunction(() => document.body.parentElement.innerText.includes('PhotoCut: click the product gallery'));
    await page.locator('.a1').scrollIntoViewIfNeeded();
    const box = await page.locator('.a1').boundingBox();
    await page.mouse.move(box.x + 20, box.y + 20);
    await page.mouse.move(box.x + 30, box.y + 30);
    await page.mouse.wheel(0, -100);  // widen from the <img> to its container
    await page.mouse.click(box.x + 30, box.y + 30);
    await page.waitForTimeout(300);
    await popup.close();

    popup = await openPopup(page);
    c = await cards(popup);
    console.log(`      rule status: ${await popup.textContent('#rule-status')}`);
    const on = c.filter((x) => x.on).map((x) => x.title.split('\n')[0]);
    check(JSON.stringify(on) === JSON.stringify(['item77-a_900x900.jpg', 'item77-b_900x900.jpg']), `picker: picked area used (${on})`);
    check(await popup.isVisible('#remember-wrap'), 'picker: offers to remember the rule');
    const r = await saveAndWait(popup);
    check(r.title === 'Saved 2 images', `picker: saved (${r.title})`);
    const msg = await popup.$eval('#message', (m) => m.hidden ? '' : m.textContent);
    if (msg) console.log(`      popup message: ${msg}`);
    const rules = JSON.parse(fs.readFileSync(rulesFile, 'utf-8'));
    const rule = rules.sites['127.0.0.1'];
    check(!!rule?.gallery && rule.updatedBy === 'E2E', `picker: team rule written to shared file (gallery: ${rule?.gallery})`);
    await popup.close();

    // a fresh look at the page now uses the team rule straight away
    popup = await openPopup(page);
    c = await cards(popup);
    check(JSON.stringify(c.filter((x) => x.on).map((x) => x.title.split('\n')[0])) === JSON.stringify(['item77-a_900x900.jpg', 'item77-b_900x900.jpg']),
      'picker: rule applied on next visit');
    check(/Team rule/.test(await popup.textContent('#rule-status')), 'picker: popup says a team rule is in use');
    await popup.close();
    await page.close();
  }

  // --- 4. Output files are correct -------------------------------------------------------
  {
    const info = py(['-c', `
from PIL import Image; import glob, json
res = []
for f in sorted(glob.glob(r"${out}/*/*.png")):
    im = Image.open(f); res.append([f.split('/')[-1], im.format, im.size])
print(json.dumps(res))`]);
    const files = JSON.parse(info);
    check(files.length === 11 && files.every(([, fmt, [w, h]]) => fmt === 'PNG' && Math.min(w, h) >= 650 && Math.max(w, h) <= 3000),
      `output: ${files.length} real PNGs within 650-3000 px`);
  }
} finally {
  await context.close();
  server.kill();
}

console.log(failures ? `\n${failures} check(s) FAILED` : '\nAll checks passed');
process.exit(failures ? 1 : 0);
