// Ditos Lanches: servidor para rodar no computador ou num servidor próprio.
// Serve o site (public/), a API (/api) e o painel (/admin). Sem DATABASE_URL usa SQLite em data/ditos.db.
// Na Vercel quem responde a API é api/index.js; este arquivo não é usado lá.
import { createServer } from 'node:http';
import { stat, readFile, writeFile, mkdir } from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import { join, normalize, extname } from 'node:path';
import { createApi, send, ROOT } from './lib/app.js';

const PUBLIC = join(ROOT, 'public');
const PORT = Number(process.env.PORT) || 3000;

// Cópia estática do cardápio para quando o site estiver sem servidor (o pedido vai por WhatsApp).
async function writeFallbackMenu() {
  try {
    const menu = await api.menu();
    menu.store = { ...menu.store, open: true, message: 'Pedidos pelo WhatsApp', payments: menu.store.payments.filter(p => p.id !== 'pix') };
    await mkdir(join(PUBLIC, 'assets', 'data'), { recursive: true });
    await writeFile(join(PUBLIC, 'assets', 'data', 'menu.json'), JSON.stringify(menu));
  } catch (err) { console.warn('[aviso] não consegui salvar a cópia estática do cardápio:', err.message); }
}
const api = createApi({ onCatalogChange: writeFallbackMenu });

const MIME = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.avif': 'image/avif', '.mp4': 'video/mp4', '.webm': 'video/webm',
  '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.txt': 'text/plain; charset=utf-8', '.webmanifest': 'application/manifest+json'
};

async function serveStatic(req, res, pathname) {
  let rel = decodeURIComponent(pathname);
  if (rel.endsWith('/')) rel += 'index.html';
  const file = normalize(join(PUBLIC, rel));
  if (!file.startsWith(PUBLIC)) { send(res, 403, 'Proibido'); return true; }
  let info;
  try { info = await stat(file); } catch { return false; }
  if (info.isDirectory()) return serveStatic(req, res, rel + '/');
  const type = MIME[extname(file).toLowerCase()] || 'application/octet-stream';
  const headers = {
    'Content-Type': type,
    'Cache-Control': type.startsWith('text/html') ? 'no-cache' : 'public, max-age=604800',
    'Accept-Ranges': 'bytes',
    'X-Content-Type-Options': 'nosniff'
  };
  const range = req.headers.range && /bytes=(\d*)-(\d*)/.exec(req.headers.range);
  if (range) {
    const start = range[1] ? Number(range[1]) : info.size - Number(range[2]);
    const end = range[1] && range[2] ? Math.min(Number(range[2]), info.size - 1) : info.size - 1;
    if (start >= info.size || start < 0 || end < start) {
      res.writeHead(416, { 'Content-Range': `bytes */${info.size}` });
      res.end();
      return true;
    }
    res.writeHead(206, { ...headers, 'Content-Range': `bytes ${start}-${end}/${info.size}`, 'Content-Length': end - start + 1 });
    if (req.method === 'HEAD') res.end(); else createReadStream(file, { start, end }).pipe(res);
    return true;
  }
  res.writeHead(200, { ...headers, 'Content-Length': info.size });
  if (req.method === 'HEAD') res.end(); else createReadStream(file).pipe(res);
  return true;
}

const server = createServer(async (req, res) => {
  const path = new URL(req.url, 'http://localhost').pathname;
  if (path.startsWith('/api/')) return api.handle(req, res);
  try {
    if (req.method !== 'GET' && req.method !== 'HEAD') return send(res, 405, 'Método não permitido.');
    if (/^\/pedido\/[A-Za-z0-9]+\/?$/.test(path)) return await serveStatic(req, res, '/pedido.html');
    if (path === '/admin' || path === '/admin/') return await serveStatic(req, res, '/admin.html');
    if (await serveStatic(req, res, path)) return;
    const notFound = await readFile(join(PUBLIC, '404.html')).catch(() => null);
    send(res, 404, notFound || 'Página não encontrada.', notFound ? { 'Content-Type': 'text/html; charset=utf-8' } : {});
  } catch (err) {
    console.error(err);
    if (!res.headersSent) send(res, 500, 'Algo deu errado.');
  }
});

server.listen(PORT, async () => {
  console.log(`Ditos Lanches no ar em http://localhost:${PORT}  (painel: /admin)`);
  await writeFallbackMenu();
});
