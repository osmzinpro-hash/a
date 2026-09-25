// Captures reference pages listed in media/reference-urls.txt: visible text,
// JSON API responses, product image URLs and screenshots of the ordering flow.
// Runs inside GitHub Actions with Playwright. A page already captured is skipped.
import { readFile, writeFile, mkdir, access } from 'node:fs/promises';
import { chromium, devices } from 'playwright';

const lines = (await readFile(new URL('./reference-urls.txt', import.meta.url), 'utf8'))
  .split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#'));

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function tryClick(page, locator, label, shots) {
  try {
    const el = locator.first();
    await el.waitFor({ state: 'visible', timeout: 6000 });
    await el.click({ timeout: 6000 });
    await sleep(2500);
    shots.push(label);
    return true;
  } catch (err) {
    console.log(`  step "${label}" skipped: ${err.message.split('\n')[0]}`);
    return false;
  }
}

for (const line of lines) {
  const [url, slugArg] = line.split(/\s+/);
  const slug = slugArg || new URL(url).hostname.replace(/\W+/g, '-');
  const out = `media/reference/${slug}`;
  try { await access(`${out}/done.txt`); console.log(`skip ${slug}`); continue; } catch {}
  await mkdir(`${out}/api`, { recursive: true });
  await mkdir(`${out}/shots`, { recursive: true });
  console.log(`capture ${url} -> ${out}`);

  const browser = await chromium.launch();
  const context = await browser.newContext({ ...devices['iPhone 13'], locale: 'pt-BR' });
  const page = await context.newPage();

  let n = 0;
  page.on('response', async res => {
    try {
      const type = res.headers()['content-type'] || '';
      if (!type.includes('json') || n >= 120) return;
      const body = await res.body();
      if (body.length > 3_000_000) return;
      const name = `${String(++n).padStart(3, '0')}-${new URL(res.url()).pathname.replace(/\W+/g, '_').slice(0, 80)}.json`;
      await writeFile(`${out}/api/${name}`, body);
      await writeFile(`${out}/api/${name}.url.txt`, res.url());
    } catch {}
  });

  await page.goto(url, { waitUntil: 'networkidle', timeout: 90000 }).catch(e => console.log('goto:', e.message));
  await sleep(4000);

  // Walk the whole page so lazy sections load, grabbing viewport shots on the way.
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  let shot = 0;
  for (let y = 0; y < height && shot < 40; y += 700) {
    await page.evaluate(v => window.scrollTo(0, v), y);
    await sleep(700);
    await page.screenshot({ path: `${out}/shots/scroll-${String(++shot).padStart(2, '0')}.jpg`, type: 'jpeg', quality: 70 });
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await sleep(800);

  await writeFile(`${out}/text.txt`, await page.evaluate(() => document.body.innerText));
  await writeFile(`${out}/page.html`, await page.content());
  const images = await page.evaluate(() => [...new Set([...document.querySelectorAll('img')]
    .map(i => ({ src: i.currentSrc || i.src, alt: i.alt || '' }))
    .filter(i => i.src && !i.src.startsWith('data:'))
    .map(i => JSON.stringify(i)))].map(s => JSON.parse(s)));
  await writeFile(`${out}/images.json`, JSON.stringify(images, null, 2));

  // Try the ordering flow: open a product, add it, open the bag, go to checkout.
  const flow = [];
  const snap = async label => page.screenshot({ path: `${out}/shots/flow-${String(flow.length).padStart(2, '0')}-${label}.jpg`, type: 'jpeg', quality: 70 });
  if (await tryClick(page, page.locator('text=/R\\$\\s*\\d/'), 'product', flow)) {
    await snap('product');
    await writeFile(`${out}/flow-product.txt`, await page.evaluate(() => document.body.innerText));
    if (await tryClick(page, page.getByRole('button', { name: /adicionar|incluir/i }), 'added', flow)) await snap('added');
    if (await tryClick(page, page.locator('text=/ver sacola|sacola|carrinho|ver pedido/i'), 'bag', flow)) {
      await snap('bag');
      await writeFile(`${out}/flow-bag.txt`, await page.evaluate(() => document.body.innerText));
    }
    for (let i = 0; i < 4; i++) {
      const ok = await tryClick(page, page.getByRole('button', { name: /finalizar|continuar|avançar|próximo|fechar pedido|confirmar/i }), `checkout${i}`, flow);
      if (!ok) break;
      await snap(`checkout${i}`);
      await writeFile(`${out}/flow-checkout${i}.txt`, await page.evaluate(() => document.body.innerText));
    }
  }

  await browser.close();
  await writeFile(`${out}/done.txt`, `${new Date().toISOString()}\n${url}\njson responses: ${n}\n`);
}
