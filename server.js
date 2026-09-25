// Ditos Lanches: servidor de pedidos.
// Zero dependências: Node 22.5+ com o SQLite embutido (node:sqlite).
// Serve o site em public/, a API da loja em /api e o painel da cozinha em /admin.
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { createReadStream, existsSync, mkdirSync, readFileSync } from 'node:fs';
import { join, normalize, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomBytes, createHmac, timingSafeEqual } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';

const ROOT = dirname(fileURLToPath(import.meta.url));
const PUBLIC = join(ROOT, 'public');
const PORT = Number(process.env.PORT) || 3000;
const DB_PATH = process.env.DB_PATH || join(ROOT, 'data', 'ditos.db');
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'ditos2002';
const SECRET = process.env.SESSION_SECRET || createHmac('sha256', 'ditos').update(ADMIN_PASSWORD + DB_PATH).digest('hex');
const TZ = 'America/Sao_Paulo';

if (!process.env.ADMIN_PASSWORD) {
  console.warn('[aviso] ADMIN_PASSWORD não definida. Usando a senha padrão "ditos2002". Troque antes de publicar.');
}

// ---------------------------------------------------------------- banco de dados
mkdirSync(dirname(DB_PATH), { recursive: true });
const db = new DatabaseSync(DB_PATH);
db.exec(`
  PRAGMA journal_mode = WAL;
  PRAGMA foreign_keys = ON;
  CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, blurb TEXT DEFAULT '', sort INTEGER DEFAULT 0, active INTEGER DEFAULT 1
  );
  CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id TEXT NOT NULL REFERENCES categories(id),
    slug TEXT DEFAULT '',
    name TEXT NOT NULL, description TEXT DEFAULT '', price_cents INTEGER NOT NULL DEFAULT 0,
    image TEXT DEFAULT '', badge TEXT DEFAULT '',
    active INTEGER DEFAULT 1, sort INTEGER DEFAULT 0
  );
  -- Grupos de opções: 'one' (escolha uma), 'many' (escolha N), 'qty' (adicionais com quantidade)
  CREATE TABLE IF NOT EXISTS option_groups (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, type TEXT NOT NULL,
    min_choices INTEGER DEFAULT 0, max_choices INTEGER DEFAULT 1
  );
  CREATE TABLE IF NOT EXISTS options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id TEXT NOT NULL REFERENCES option_groups(id),
    title TEXT NOT NULL, price_cents INTEGER NOT NULL DEFAULT 0, max_qty INTEGER DEFAULT 1,
    active INTEGER DEFAULT 1, sort INTEGER DEFAULT 0
  );
  CREATE TABLE IF NOT EXISTS product_groups (
    product_id INTEGER NOT NULL REFERENCES products(id),
    group_id TEXT NOT NULL REFERENCES option_groups(id),
    sort INTEGER DEFAULT 0,
    PRIMARY KEY (product_id, group_id)
  );
  CREATE TABLE IF NOT EXISTS neighborhoods (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, fee_cents INTEGER NOT NULL,
    eta TEXT DEFAULT '35 a 50 min', active INTEGER DEFAULT 1
  );
  CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
  CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'recebido',
    history TEXT NOT NULL DEFAULT '[]',
    customer_name TEXT NOT NULL,
    customer_phone TEXT NOT NULL,
    fulfillment TEXT NOT NULL,
    address TEXT DEFAULT '{}',
    neighborhood TEXT DEFAULT '',
    items TEXT NOT NULL,
    subtotal_cents INTEGER NOT NULL,
    delivery_fee_cents INTEGER NOT NULL DEFAULT 0,
    total_cents INTEGER NOT NULL,
    payment_method TEXT NOT NULL,
    change_for_cents INTEGER DEFAULT 0,
    paid INTEGER NOT NULL DEFAULT 0,
    notes TEXT DEFAULT ''
  );
  CREATE INDEX IF NOT EXISTS orders_created ON orders(created_at);
`);

function seedIfEmpty() {
  const count = db.prepare('SELECT COUNT(*) AS n FROM products').get().n;
  if (count > 0) return;
  const seed = JSON.parse(readFileSync(join(ROOT, 'data', 'seed.json'), 'utf8'));
  db.exec('BEGIN');
  try {
    const grp = db.prepare('INSERT OR REPLACE INTO option_groups (id, title, type, min_choices, max_choices) VALUES (?, ?, ?, ?, ?)');
    const opt = db.prepare('INSERT INTO options (group_id, title, price_cents, max_qty, sort) VALUES (?, ?, ?, ?, ?)');
    seed.groups.forEach(g => {
      grp.run(g.id, g.title, g.type, g.min, g.max);
      g.options.forEach((o, i) => opt.run(g.id, o.title, Math.round(o.price * 100), o.max || 1, i));
    });
    const cat = db.prepare('INSERT OR REPLACE INTO categories (id, name, blurb, sort) VALUES (?, ?, ?, ?)');
    const prod = db.prepare('INSERT INTO products (category_id, slug, name, description, price_cents, image, badge, sort) VALUES (?, ?, ?, ?, ?, ?, ?, ?)');
    const link = db.prepare('INSERT INTO product_groups (product_id, group_id, sort) VALUES (?, ?, ?)');
    seed.categories.forEach((c, i) => {
      cat.run(c.id, c.name, c.blurb || '', i);
      c.products.forEach((p, j) => {
        const id = Number(prod.run(c.id, p.slug || '', p.name, p.description || '', Math.round(p.price * 100), p.image || '', p.badge || '', j).lastInsertRowid);
        (p.groups || []).forEach((g, k) => link.run(id, g, k));
      });
    });
    const nb = db.prepare('INSERT OR IGNORE INTO neighborhoods (name, fee_cents, eta) VALUES (?, ?, ?)');
    seed.neighborhoods.forEach(n => nb.run(n.name, Math.round(n.fee * 100), n.eta || '35 a 50 min'));
    const st = db.prepare('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)');
    Object.entries(seed.settings).forEach(([k, v]) => st.run(k, String(v)));
    db.exec('COMMIT');
    console.log('[banco] cardápio inicial carregado de data/seed.json');
  } catch (err) {
    db.exec('ROLLBACK');
    throw err;
  }
}
seedIfEmpty();

const getSettings = () => Object.fromEntries(db.prepare('SELECT key, value FROM settings').all().map(r => [r.key, r.value]));
const setSetting = db.prepare('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)');

// ---------------------------------------------------------------- loja aberta?
function nowParts() {
  const parts = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false }).formatToParts(new Date());
  const get = t => parts.find(p => p.type === t).value;
  return { day: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].indexOf(get('weekday')), minutes: Number(get('hour')) % 24 * 60 + Number(get('minute')) };
}
const toMin = hhmm => { const [h, m] = String(hhmm || '0:0').split(':').map(Number); return h * 60 + (m || 0); };

function storeStatus(s = getSettings()) {
  if (s.store_mode === 'open') return { open: true, message: 'Aberto agora' };
  if (s.store_mode === 'closed') return { open: false, message: s.closed_message || 'Estamos fechados no momento.' };
  const { day, minutes } = nowParts();
  const openDays = String(s.open_days || '0,1,2,3,4,5,6').split(',').map(Number);
  const o = toMin(s.open_time), c = toMin(s.close_time);
  const overnight = c <= o;
  let open;
  if (!overnight) open = openDays.includes(day) && minutes >= o && minutes < c;
  else open = (openDays.includes(day) && minutes >= o) || (openDays.includes((day + 6) % 7) && minutes < c);
  return open
    ? { open: true, message: `Aberto até ${s.close_time}` }
    : { open: false, message: `Fechado agora. Abrimos às ${s.open_time}.` };
}

// ---------------------------------------------------------------- Pix (BR Code estático)
function crc16(str) {
  let crc = 0xffff;
  for (const byte of Buffer.from(str, 'utf8')) {
    crc ^= byte << 8;
    for (let i = 0; i < 8; i++) crc = crc & 0x8000 ? ((crc << 1) ^ 0x1021) & 0xffff : (crc << 1) & 0xffff;
  }
  return crc.toString(16).toUpperCase().padStart(4, '0');
}
const tlv = (id, value) => id + String(value.length).padStart(2, '0') + value;
const plain = (s, max) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^A-Za-z0-9 ]/g, '').trim().slice(0, max).toUpperCase();

function pixPayload({ key, name, city, amountCents, txid }) {
  if (!key) return null;
  const mai = tlv('00', 'br.gov.bcb.pix') + tlv('01', key.trim());
  let p = tlv('00', '01') + tlv('26', mai) + tlv('52', '0000') + tlv('53', '986');
  if (amountCents > 0) p += tlv('54', (amountCents / 100).toFixed(2));
  p += tlv('58', 'BR') + tlv('59', plain(name, 25) || 'DITOS LANCHES') + tlv('60', plain(city, 15) || 'SAO MATEUS');
  p += tlv('62', tlv('05', (txid || '***').replace(/[^A-Za-z0-9]/g, '').slice(0, 25) || '***'));
  p += '6304';
  return p + crc16(p);
}

// ---------------------------------------------------------------- utilidades HTTP
const MIME = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.avif': 'image/avif', '.mp4': 'video/mp4', '.webm': 'video/webm',
  '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.txt': 'text/plain; charset=utf-8', '.webmanifest': 'application/manifest+json'
};

function send(res, status, body, headers = {}) {
  const data = typeof body === 'string' || Buffer.isBuffer(body) ? body : JSON.stringify(body);
  res.writeHead(status, {
    'Content-Type': typeof body === 'object' && !Buffer.isBuffer(body) ? 'application/json; charset=utf-8' : 'text/plain; charset=utf-8',
    'Cache-Control': 'no-store',
    ...headers
  });
  res.end(data);
}
const fail = (res, status, message) => send(res, status, { error: message });

async function readJson(req, limit = 64 * 1024) {
  let size = 0;
  const chunks = [];
  for await (const chunk of req) {
    size += chunk.length;
    if (size > limit) throw Object.assign(new Error('Pedido grande demais.'), { status: 413 });
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')); }
  catch { throw Object.assign(new Error('JSON inválido.'), { status: 400 }); }
}

async function serveStatic(req, res, pathname) {
  let rel = decodeURIComponent(pathname);
  if (rel.endsWith('/')) rel += 'index.html';
  const file = normalize(join(PUBLIC, rel));
  if (!file.startsWith(PUBLIC)) return fail(res, 403, 'Proibido');
  let info;
  try { info = await stat(file); } catch { return false; }
  if (info.isDirectory()) return serveStatic(req, res, rel + '/');
  const type = MIME[extname(file).toLowerCase()] || 'application/octet-stream';
  const isHtml = type.startsWith('text/html');
  const headers = {
    'Content-Type': type,
    'Cache-Control': isHtml ? 'no-cache' : 'public, max-age=604800',
    'Accept-Ranges': 'bytes',
    'X-Content-Type-Options': 'nosniff'
  };
  const range = req.headers.range && /bytes=(\d*)-(\d*)/.exec(req.headers.range);
  if (range) {
    const start = range[1] ? Number(range[1]) : info.size - Number(range[2]);
    const end = range[1] && range[2] ? Math.min(Number(range[2]), info.size - 1) : info.size - 1;
    if (start >= info.size || start < 0 || end < start) {
      res.writeHead(416, { 'Content-Range': `bytes */${info.size}` });
      return res.end();
    }
    res.writeHead(206, { ...headers, 'Content-Range': `bytes ${start}-${end}/${info.size}`, 'Content-Length': end - start + 1 });
    if (req.method === 'HEAD') return res.end();
    return createReadStream(file, { start, end }).pipe(res);
  }
  res.writeHead(200, { ...headers, 'Content-Length': info.size });
  if (req.method === 'HEAD') return res.end();
  createReadStream(file).pipe(res);
  return true;
}

// Limite simples por IP (pedidos e login), guardado em memória.
const hits = new Map();
function limited(key, max, windowMs) {
  const now = Date.now();
  const list = (hits.get(key) || []).filter(t => now - t < windowMs);
  list.push(now);
  hits.set(key, list);
  return list.length > max;
}
const clientIp = req => (req.headers['x-forwarded-for'] || '').split(',')[0].trim() || req.socket.remoteAddress || '';

// ---------------------------------------------------------------- sessão do painel
function signToken(payload) {
  const body = Buffer.from(JSON.stringify(payload)).toString('base64url');
  return body + '.' + createHmac('sha256', SECRET).update(body).digest('base64url');
}
function verifyToken(token) {
  const [body, sig] = String(token || '').split('.');
  if (!body || !sig) return null;
  const expected = createHmac('sha256', SECRET).update(body).digest('base64url');
  const a = Buffer.from(sig), b = Buffer.from(expected);
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;
  const payload = JSON.parse(Buffer.from(body, 'base64url').toString());
  return payload.exp > Date.now() ? payload : null;
}
const isAdmin = req => verifyToken((req.headers.authorization || '').replace(/^Bearer\s+/i, ''));

// ---------------------------------------------------------------- loja
const PUBLIC_SETTINGS = ['store_name', 'whatsapp', 'phone', 'address', 'address_2', 'hours_label', 'instagram', 'min_order', 'pickup_enabled', 'delivery_enabled', 'avg_prep', 'pickup_eta'];
const PAYMENTS = {
  pix: 'Pix pelo site',
  credito: 'Cartão de crédito na entrega',
  debito: 'Cartão de débito na entrega',
  dinheiro: 'Dinheiro',
  vale: 'Vale-refeição na entrega'
};
const pixReady = s => s.pix_enabled !== '0' && !!String(s.pix_key || '').trim();

function menuPayload() {
  const s = getSettings();
  const links = db.prepare('SELECT product_id, group_id FROM product_groups ORDER BY product_id, sort').all();
  const groupsOf = {};
  for (const l of links) (groupsOf[l.product_id] ||= []).push(l.group_id);
  const options = db.prepare('SELECT id, group_id, title, price_cents, max_qty FROM options WHERE active = 1 ORDER BY group_id, sort, id').all();
  const groups = db.prepare('SELECT id, title, type, min_choices, max_choices FROM option_groups').all()
    .map(g => ({ ...g, options: options.filter(o => o.group_id === g.id).map(({ group_id, ...o }) => o) }));
  return {
    store: {
      ...Object.fromEntries(PUBLIC_SETTINGS.map(k => [k, s[k] ?? ''])),
      ...storeStatus(s),
      payments: Object.entries(PAYMENTS).filter(([k]) => k !== 'pix' || pixReady(s)).map(([id, label]) => ({ id, label }))
    },
    categories: db.prepare('SELECT id, name, blurb FROM categories WHERE active = 1 ORDER BY sort').all(),
    products: db.prepare('SELECT id, category_id, slug, name, description, price_cents, image, badge FROM products WHERE active = 1 ORDER BY sort, id').all()
      .map(p => ({ ...p, groups: groupsOf[p.id] || [] })),
    groups,
    neighborhoods: db.prepare('SELECT id, name, fee_cents, eta FROM neighborhoods WHERE active = 1 ORDER BY name').all()
  };
}

const CODE_ALPHABET = '23456789ABCDEFGHJKMNPQRSTUVWXYZ';
function newCode() {
  for (;;) {
    const code = [...randomBytes(8)].map(b => CODE_ALPHABET[b % CODE_ALPHABET.length]).join('');
    if (!db.prepare('SELECT 1 FROM orders WHERE code = ?').get(code)) return code;
  }
}

const STATUS = {
  recebido: 'Pedido recebido',
  na_chapa: 'Na chapa',
  saiu: 'Saiu pra entrega',
  pronto: 'Pronto pra retirar',
  entregue: 'Entregue',
  cancelado: 'Cancelado'
};

const clean = (v, max = 200) => String(v ?? '').replace(/[\u0000-\u001f]/g, ' ').trim().slice(0, max);

function createOrder(input) {
  const s = getSettings();
  const status = storeStatus(s);
  if (!status.open) throw Object.assign(new Error(status.message), { status: 409 });

  const name = clean(input.name, 80);
  const phone = clean(input.phone, 30).replace(/[^\d+() -]/g, '');
  if (name.length < 2) throw Object.assign(new Error('Informe seu nome.'), { status: 400 });
  if (phone.replace(/\D/g, '').length < 10) throw Object.assign(new Error('Informe um telefone com DDD.'), { status: 400 });

  const fulfillment = input.fulfillment === 'pickup' ? 'pickup' : 'delivery';
  if (fulfillment === 'pickup' && s.pickup_enabled === '0') throw Object.assign(new Error('Retirada indisponível no momento.'), { status: 400 });
  if (fulfillment === 'delivery' && s.delivery_enabled === '0') throw Object.assign(new Error('Entrega indisponível no momento.'), { status: 400 });

  // Preços sempre recalculados pelo servidor, nunca aceitos do navegador.
  const productStmt = db.prepare('SELECT id, name, price_cents FROM products WHERE id = ? AND active = 1');
  const groupsStmt = db.prepare('SELECT g.id, g.title, g.type, g.min_choices, g.max_choices FROM product_groups pg JOIN option_groups g ON g.id = pg.group_id WHERE pg.product_id = ? ORDER BY pg.sort');
  const optionStmt = db.prepare('SELECT id, group_id, title, price_cents, max_qty FROM options WHERE id = ? AND active = 1');
  const bad = message => Object.assign(new Error(message), { status: 400 });
  const lines = Array.isArray(input.items) ? input.items.slice(0, 60) : [];
  if (!lines.length) throw bad('Seu pedido está vazio.');
  const items = [];
  let subtotal = 0;
  for (const line of lines) {
    const product = productStmt.get(Number(line.id));
    if (!product) throw Object.assign(new Error('Um item do seu pedido saiu do cardápio. Atualize a página.'), { status: 409 });
    const qty = Math.max(1, Math.min(30, Math.floor(Number(line.qty) || 1)));
    const picked = new Map();
    for (const o of Array.isArray(line.options) ? line.options.slice(0, 40) : []) {
      const id = Number(o.id);
      picked.set(id, (picked.get(id) || 0) + Math.max(1, Math.floor(Number(o.qty) || 1)));
    }
    const groups = groupsStmt.all(product.id);
    const chosen = [];
    for (const g of groups) {
      const inGroup = [...picked].map(([id, n]) => ({ o: optionStmt.get(id), n })).filter(x => x.o && x.o.group_id === g.id);
      const count = inGroup.reduce((sum, x) => sum + (g.type === 'qty' ? x.n : 1), 0);
      if (count < g.min_choices) throw bad(`${product.name}: escolha ${g.title.toLowerCase()}.`);
      if (count > g.max_choices) throw bad(`${product.name}: no máximo ${g.max_choices} em ${g.title.toLowerCase()}.`);
      for (const { o, n } of inGroup) {
        const q = g.type === 'qty' ? Math.min(n, o.max_qty || g.max_choices) : 1;
        chosen.push({ id: o.id, group: g.title, name: o.title, qty: q, price_cents: o.price_cents });
      }
    }
    const unit = product.price_cents + chosen.reduce((sum, o) => sum + o.price_cents * o.qty, 0);
    if (unit <= 0) throw bad(`${product.name}: escolha uma opção.`);
    subtotal += unit * qty;
    items.push({ id: product.id, name: product.name, qty, unit_cents: unit, options: chosen, note: clean(line.note, 140) });
  }

  const minOrder = Math.round(Number(s.min_order || 0) * 100);
  if (subtotal < minOrder) throw Object.assign(new Error(`O pedido mínimo é de R$ ${(minOrder / 100).toFixed(2).replace('.', ',')}.`), { status: 400 });

  let address = {}, neighborhood = '', fee = 0;
  if (fulfillment === 'delivery') {
    const nb = db.prepare('SELECT id, name, fee_cents FROM neighborhoods WHERE id = ? AND active = 1').get(Number(input.address?.neighborhood_id));
    if (!nb) throw Object.assign(new Error('Escolha o bairro da entrega.'), { status: 400 });
    address = {
      street: clean(input.address?.street, 120), number: clean(input.address?.number, 20),
      complement: clean(input.address?.complement, 80), reference: clean(input.address?.reference, 120)
    };
    if (address.street.length < 3 || !address.number) throw Object.assign(new Error('Informe rua e número para a entrega.'), { status: 400 });
    neighborhood = nb.name;
    fee = nb.fee_cents;
  }

  const payment = PAYMENTS[input.payment] ? input.payment : null;
  if (!payment) throw bad('Escolha a forma de pagamento.');
  if (payment === 'pix' && !pixReady(s)) throw bad('Pix indisponível agora. Escolha outra forma.');
  const total = subtotal + fee;
  const changeFor = payment === 'dinheiro' ? Math.round(Number(input.change_for || 0) * 100) : 0;
  if (changeFor && changeFor < total) throw Object.assign(new Error('O troco precisa ser para um valor maior que o total.'), { status: 400 });

  const code = newCode();
  const now = new Date().toISOString();
  const info = db.prepare(`INSERT INTO orders (code, created_at, updated_at, status, history, customer_name, customer_phone, fulfillment, address, neighborhood, items, subtotal_cents, delivery_fee_cents, total_cents, payment_method, change_for_cents, notes)
    VALUES (?, ?, ?, 'recebido', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`).run(
    code, now, now, JSON.stringify([{ status: 'recebido', at: now }]), name, phone, fulfillment,
    JSON.stringify(address), neighborhood, JSON.stringify(items), subtotal, fee, total, payment, changeFor, clean(input.notes, 300)
  );
  return { id: Number(info.lastInsertRowid), code };
}

function publicOrder(row, s = getSettings()) {
  const order = {
    number: row.id,
    code: row.code,
    created_at: row.created_at,
    status: row.status,
    status_label: STATUS[row.status] || row.status,
    history: JSON.parse(row.history),
    fulfillment: row.fulfillment,
    neighborhood: row.neighborhood,
    items: JSON.parse(row.items),
    subtotal_cents: row.subtotal_cents,
    delivery_fee_cents: row.delivery_fee_cents,
    total_cents: row.total_cents,
    payment_method: row.payment_method,
    payment_label: PAYMENTS[row.payment_method] || row.payment_method,
    paid: !!row.paid,
    customer_first_name: row.customer_name.split(' ')[0],
    whatsapp: s.whatsapp || ''
  };
  if (row.payment_method === 'pix' && !row.paid && row.status !== 'cancelado' && pixReady(s)) {
    order.pix = pixPayload({ key: s.pix_key, name: s.pix_name || s.store_name, city: s.pix_city, amountCents: row.total_cents, txid: 'DITOS' + row.code });
  }
  return order;
}

// ---------------------------------------------------------------- painel (admin)
const adminOrder = row => ({ ...publicOrder(row), customer_name: row.customer_name, customer_phone: row.customer_phone, address: JSON.parse(row.address || '{}'), notes: row.notes, change_for_cents: row.change_for_cents, updated_at: row.updated_at });

const EDITABLE_SETTINGS = ['store_name', 'whatsapp', 'phone', 'address', 'address_2', 'hours_label', 'instagram', 'min_order', 'pickup_enabled', 'delivery_enabled', 'pix_enabled', 'pix_key', 'pix_name', 'pix_city', 'store_mode', 'open_time', 'close_time', 'open_days', 'closed_message', 'avg_prep', 'pickup_eta'];

function dayStartIso(offsetDays = 0) {
  // Início do dia em São Mateus (UTC-3) convertido para ISO.
  const d = new Date(Date.now() - 3 * 3600e3);
  d.setUTCHours(0, 0, 0, 0);
  return new Date(d.getTime() + 3 * 3600e3 - offsetDays * 86400e3).toISOString();
}

async function handleAdmin(req, res, path, url) {
  if (path === '/api/admin/login' && req.method === 'POST') {
    if (limited('login:' + clientIp(req), 8, 10 * 60e3)) return fail(res, 429, 'Muitas tentativas. Espere alguns minutos.');
    const { password } = await readJson(req);
    const a = Buffer.from(String(password || '')), b = Buffer.from(ADMIN_PASSWORD);
    if (a.length !== b.length || !timingSafeEqual(a, b)) return fail(res, 401, 'Senha incorreta.');
    return send(res, 200, { token: signToken({ role: 'admin', exp: Date.now() + 14 * 3600e3 }) });
  }
  if (!isAdmin(req)) return fail(res, 401, 'Entre com a senha do painel.');

  if (path === '/api/admin/orders' && req.method === 'GET') {
    const scope = url.searchParams.get('scope') || 'today';
    const since = scope === 'week' ? dayStartIso(6) : dayStartIso(0);
    const rows = scope === 'open'
      ? db.prepare("SELECT * FROM orders WHERE status NOT IN ('entregue','cancelado') ORDER BY id DESC LIMIT 200").all()
      : db.prepare('SELECT * FROM orders WHERE created_at >= ? ORDER BY id DESC LIMIT 500').all(since);
    const stats = db.prepare("SELECT COUNT(*) AS orders, COALESCE(SUM(total_cents),0) AS revenue FROM orders WHERE created_at >= ? AND status != 'cancelado'").get(dayStartIso(0));
    return send(res, 200, { orders: rows.map(adminOrder), stats, store: storeStatus() });
  }
  const orderMatch = path.match(/^\/api\/admin\/orders\/(\d+)$/);
  if (orderMatch && req.method === 'PATCH') {
    const row = db.prepare('SELECT * FROM orders WHERE id = ?').get(Number(orderMatch[1]));
    if (!row) return fail(res, 404, 'Pedido não encontrado.');
    const body = await readJson(req);
    const now = new Date().toISOString();
    const history = JSON.parse(row.history);
    let status = row.status;
    if (body.status && body.status !== row.status) {
      if (!STATUS[body.status]) return fail(res, 400, 'Status inválido.');
      status = body.status;
      history.push({ status, at: now });
    }
    const paid = body.paid === undefined ? row.paid : body.paid ? 1 : 0;
    db.prepare('UPDATE orders SET status = ?, history = ?, paid = ?, updated_at = ? WHERE id = ?').run(status, JSON.stringify(history), paid, now, row.id);
    return send(res, 200, adminOrder(db.prepare('SELECT * FROM orders WHERE id = ?').get(row.id)));
  }

  if (path === '/api/admin/catalog' && req.method === 'GET') {
    return send(res, 200, {
      categories: db.prepare('SELECT * FROM categories ORDER BY sort').all(),
      products: db.prepare('SELECT * FROM products ORDER BY category_id, sort, id').all(),
      groups: db.prepare('SELECT * FROM option_groups ORDER BY title').all(),
      options: db.prepare('SELECT * FROM options ORDER BY group_id, sort, id').all(),
      neighborhoods: db.prepare('SELECT * FROM neighborhoods ORDER BY name').all(),
      settings: Object.fromEntries(Object.entries(getSettings()).filter(([k]) => EDITABLE_SETTINGS.includes(k)))
    });
  }
  const productMatch = path.match(/^\/api\/admin\/products(?:\/(\d+))?$/);
  if (productMatch && (req.method === 'POST' || req.method === 'PUT')) {
    const b = await readJson(req);
    const fields = [clean(b.category_id, 40), clean(b.name, 80), clean(b.description, 300), Math.max(0, Math.round(Number(b.price_cents) || 0)), clean(b.image, 200), clean(b.badge, 30), b.active === false || b.active === 0 ? 0 : 1];
    if (!fields[1]) return fail(res, 400, 'O nome é obrigatório.');
    if (!db.prepare('SELECT 1 FROM categories WHERE id = ?').get(fields[0])) return fail(res, 400, 'Categoria inválida.');
    if (req.method === 'POST') {
      const info = db.prepare('INSERT INTO products (category_id, name, description, price_cents, image, badge, active, sort) VALUES (?, ?, ?, ?, ?, ?, ?, 999)').run(...fields);
      return send(res, 201, db.prepare('SELECT * FROM products WHERE id = ?').get(Number(info.lastInsertRowid)));
    }
    db.prepare('UPDATE products SET category_id = ?, name = ?, description = ?, price_cents = ?, image = ?, badge = ?, active = ? WHERE id = ?').run(...fields, Number(productMatch[1]));
    return send(res, 200, db.prepare('SELECT * FROM products WHERE id = ?').get(Number(productMatch[1])));
  }
  const nbMatch = path.match(/^\/api\/admin\/neighborhoods(?:\/(\d+))?$/);
  if (nbMatch && (req.method === 'POST' || req.method === 'PUT')) {
    const b = await readJson(req);
    const name = clean(b.name, 60), fee = Math.max(0, Math.round(Number(b.fee_cents) || 0)), eta = clean(b.eta, 30) || '35 a 50 min', active = b.active === false || b.active === 0 ? 0 : 1;
    if (!name) return fail(res, 400, 'Informe o nome do bairro.');
    try {
      if (req.method === 'POST') db.prepare('INSERT INTO neighborhoods (name, fee_cents, eta, active) VALUES (?, ?, ?, ?)').run(name, fee, eta, active);
      else db.prepare('UPDATE neighborhoods SET name = ?, fee_cents = ?, eta = ?, active = ? WHERE id = ?').run(name, fee, eta, active, Number(nbMatch[1]));
    } catch { return fail(res, 409, 'Esse bairro já existe.'); }
    return send(res, 200, { ok: true });
  }
  const optionMatch = path.match(/^\/api\/admin\/options\/(\d+)$/);
  if (optionMatch && req.method === 'PUT') {
    const b = await readJson(req);
    const title = clean(b.title, 60), price = Math.max(0, Math.round(Number(b.price_cents) || 0)), active = b.active === false || b.active === 0 ? 0 : 1;
    if (!title) return fail(res, 400, 'Informe o nome da opção.');
    db.prepare('UPDATE options SET title = ?, price_cents = ?, active = ? WHERE id = ?').run(title, price, active, Number(optionMatch[1]));
    return send(res, 200, { ok: true });
  }
  if (path === '/api/admin/settings' && req.method === 'PUT') {
    const b = await readJson(req);
    for (const [k, v] of Object.entries(b)) if (EDITABLE_SETTINGS.includes(k)) setSetting.run(k, clean(v, 300));
    return send(res, 200, { ok: true, store: storeStatus() });
  }
  return fail(res, 404, 'Rota não encontrada.');
}

// ---------------------------------------------------------------- roteador
const server = createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const path = url.pathname;
  try {
    if (path.startsWith('/api/admin/')) return await handleAdmin(req, res, path, url);

    if (path === '/api/menu' && req.method === 'GET') return send(res, 200, menuPayload());

    if (path === '/api/orders' && req.method === 'POST') {
      if (limited('order:' + clientIp(req), 12, 15 * 60e3)) return fail(res, 429, 'Muitos pedidos seguidos. Chame a gente no WhatsApp.');
      const { code } = createOrder(await readJson(req));
      return send(res, 201, publicOrder(db.prepare('SELECT * FROM orders WHERE code = ?').get(code)));
    }
    const track = path.match(/^\/api\/orders\/([A-Z0-9]{6,12})$/);
    if (track && req.method === 'GET') {
      const row = db.prepare('SELECT * FROM orders WHERE code = ?').get(track[1]);
      return row ? send(res, 200, publicOrder(row)) : fail(res, 404, 'Pedido não encontrado.');
    }
    if (path.startsWith('/api/')) return fail(res, 404, 'Rota não encontrada.');

    if (req.method !== 'GET' && req.method !== 'HEAD') return fail(res, 405, 'Método não permitido.');
    if (/^\/pedido\/[A-Za-z0-9]+\/?$/.test(path)) return serveStatic(req, res, '/pedido.html');
    if (path === '/admin' || path === '/admin/') return serveStatic(req, res, '/admin.html');
    const served = await serveStatic(req, res, path);
    if (served === false) {
      const notFound = join(PUBLIC, '404.html');
      if (existsSync(notFound)) return send(res, 404, await readFile(notFound), { 'Content-Type': 'text/html; charset=utf-8' });
      return fail(res, 404, 'Página não encontrada.');
    }
  } catch (err) {
    if (!err.status) console.error(err);
    if (!res.headersSent) fail(res, err.status || 500, err.status ? err.message : 'Algo deu errado. Tente de novo.');
  }
});

server.listen(PORT, () => console.log(`Ditos Lanches no ar em http://localhost:${PORT}  (painel: /admin)`));
