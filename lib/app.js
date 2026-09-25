// Ditos Lanches: a API da loja (/api/...). A mesma lógica roda no servidor local (server.js)
// e na Vercel (api/index.js). Preços sempre recalculados aqui, nunca aceitos do navegador.
import { randomBytes, createHmac, timingSafeEqual } from 'node:crypto';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openDb } from './db.js';

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'ditos2002';
const SECRET = process.env.SESSION_SECRET || createHmac('sha256', 'ditos-lanches').update(ADMIN_PASSWORD).digest('hex');
const TZ = 'America/Sao_Paulo';

if (!process.env.ADMIN_PASSWORD) {
  console.warn('[aviso] ADMIN_PASSWORD não definida. Usando a senha padrão "ditos2002". Troque antes de publicar.');
}

// ---------------------------------------------------------------- utilidades
const httpError = (status, message) => Object.assign(new Error(message), { status });
const clean = (v, max = 200) => String(v ?? '').replace(/[\u0000-\u001f]/g, ' ').trim().slice(0, max);

export function send(res, status, body, headers = {}) {
  const isObj = typeof body === 'object' && !Buffer.isBuffer(body);
  res.writeHead(status, {
    'Content-Type': isObj ? 'application/json; charset=utf-8' : 'text/plain; charset=utf-8',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    ...headers
  });
  res.end(isObj ? JSON.stringify(body) : body);
}
const fail = (res, status, message) => send(res, status, { error: message });

async function readJson(req, limit = 64 * 1024) {
  // Na Vercel o corpo já vem lido em req.body; no servidor local lemos o fluxo.
  if (req.body !== undefined && req.body !== null) {
    if (typeof req.body === 'object' && !Buffer.isBuffer(req.body)) return req.body;
    const text = String(req.body);
    if (text.length > limit) throw httpError(413, 'Pedido grande demais.');
    try { return text ? JSON.parse(text) : {}; } catch { throw httpError(400, 'JSON inválido.'); }
  }
  let size = 0;
  const chunks = [];
  for await (const chunk of req) {
    size += chunk.length;
    if (size > limit) throw httpError(413, 'Pedido grande demais.');
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')); }
  catch { throw httpError(400, 'JSON inválido.'); }
}

// Limite simples por IP (pedidos e login), em memória de cada servidor.
const hits = new Map();
function limited(key, max, windowMs) {
  const now = Date.now();
  const list = (hits.get(key) || []).filter(t => now - t < windowMs);
  list.push(now);
  hits.set(key, list);
  if (hits.size > 5000) hits.clear();
  return list.length > max;
}
const clientIp = req => String(req.headers['x-forwarded-for'] || '').split(',')[0].trim() || req.socket?.remoteAddress || '';

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
  try {
    const payload = JSON.parse(Buffer.from(body, 'base64url').toString());
    return payload.exp > Date.now() ? payload : null;
  } catch { return null; }
}
const isAdmin = req => verifyToken(String(req.headers.authorization || '').replace(/^Bearer\s+/i, ''));

// ---------------------------------------------------------------- loja aberta?
function nowParts() {
  const parts = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false }).formatToParts(new Date());
  const get = t => parts.find(p => p.type === t).value;
  return { day: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].indexOf(get('weekday')), minutes: Number(get('hour')) % 24 * 60 + Number(get('minute')) };
}
const toMin = hhmm => { const [h, m] = String(hhmm || '0:0').split(':').map(Number); return h * 60 + (m || 0); };

export function storeStatus(s) {
  if (s.store_mode === 'open') return { open: true, message: 'Aberto agora' };
  if (s.store_mode === 'closed') return { open: false, message: s.closed_message || 'Estamos fechados no momento.' };
  const { day, minutes } = nowParts();
  const openDays = String(s.open_days || '0,1,2,3,4,5,6').split(',').map(Number);
  const o = toMin(s.open_time), c = toMin(s.close_time);
  const open = c > o
    ? openDays.includes(day) && minutes >= o && minutes < c
    : (openDays.includes(day) && minutes >= o) || (openDays.includes((day + 6) % 7) && minutes < c);
  return open
    ? { open: true, message: `Aberto até ${s.close_time}` }
    : { open: false, message: s.closed_message || `Fechado agora. Abrimos às ${s.open_time}.` };
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

export function pixPayload({ key, name, city, amountCents, txid }) {
  if (!key) return null;
  const mai = tlv('00', 'br.gov.bcb.pix') + tlv('01', key.trim());
  let p = tlv('00', '01') + tlv('26', mai) + tlv('52', '0000') + tlv('53', '986');
  if (amountCents > 0) p += tlv('54', (amountCents / 100).toFixed(2));
  p += tlv('58', 'BR') + tlv('59', plain(name, 25) || 'DITOS LANCHES') + tlv('60', plain(city, 15) || 'SAO MATEUS');
  p += tlv('62', tlv('05', (txid || '***').replace(/[^A-Za-z0-9]/g, '').slice(0, 25) || '***'));
  p += '6304';
  return p + crc16(p);
}

// ---------------------------------------------------------------- dados
const PUBLIC_SETTINGS = ['store_name', 'whatsapp', 'phone', 'address', 'address_2', 'hours_label', 'instagram', 'min_order', 'pickup_enabled', 'delivery_enabled', 'avg_prep', 'pickup_eta'];
const EDITABLE_SETTINGS = [...PUBLIC_SETTINGS, 'pix_enabled', 'pix_key', 'pix_name', 'pix_city', 'store_mode', 'open_time', 'close_time', 'open_days', 'closed_message'];
const PAYMENTS = {
  pix: 'Pix pelo site',
  credito: 'Cartão de crédito na entrega',
  debito: 'Cartão de débito na entrega',
  dinheiro: 'Dinheiro',
  vale: 'Vale-refeição na entrega'
};
const STATUS = {
  recebido: 'Pedido recebido',
  na_chapa: 'Na chapa',
  saiu: 'Saiu pra entrega',
  pronto: 'Pronto pra retirar',
  entregue: 'Entregue',
  cancelado: 'Cancelado'
};
const pixReady = s => s.pix_enabled !== '0' && !!String(s.pix_key || '').trim();
const CODE_ALPHABET = '23456789ABCDEFGHJKMNPQRSTUVWXYZ';

function dayStartIso(offsetDays = 0) {
  // Início do dia em São Mateus (UTC-3) em ISO.
  const d = new Date(Date.now() - 3 * 3600e3);
  d.setUTCHours(0, 0, 0, 0);
  return new Date(d.getTime() + 3 * 3600e3 - offsetDays * 86400e3).toISOString();
}

export function createApi({ onCatalogChange = () => {} } = {}) {
  let dbPromise = null;
  const database = () => (dbPromise ||= openDb(ROOT).catch(err => { dbPromise = null; throw err; }));

  async function getSettings(db) {
    const rows = await db.all('SELECT key, value FROM settings');
    return Object.fromEntries(rows.map(r => [r.key, r.value]));
  }

  async function menuPayload(db) {
    const s = await getSettings(db);
    const [links, options, groups, categories, products, neighborhoods] = await Promise.all([
      db.all('SELECT product_id, group_id FROM product_groups ORDER BY product_id, sort'),
      db.all('SELECT id, group_id, title, price_cents, max_qty FROM options WHERE active = 1 ORDER BY group_id, sort, id'),
      db.all('SELECT id, title, type, min_choices, max_choices FROM option_groups'),
      db.all('SELECT id, name, blurb FROM categories WHERE active = 1 ORDER BY sort'),
      db.all('SELECT id, category_id, slug, name, description, price_cents, image, badge FROM products WHERE active = 1 ORDER BY sort, id'),
      db.all('SELECT id, name, fee_cents, eta FROM neighborhoods WHERE active = 1 ORDER BY name')
    ]);
    const groupsOf = {};
    for (const l of links) (groupsOf[l.product_id] ||= []).push(l.group_id);
    return {
      store: {
        ...Object.fromEntries(PUBLIC_SETTINGS.map(k => [k, s[k] ?? ''])),
        ...storeStatus(s),
        payments: Object.entries(PAYMENTS).filter(([k]) => k !== 'pix' || pixReady(s)).map(([id, label]) => ({ id, label }))
      },
      categories,
      products: products.map(p => ({ ...p, groups: groupsOf[p.id] || [] })),
      groups: groups.map(g => ({ ...g, options: options.filter(o => o.group_id === g.id).map(({ group_id, ...o }) => o) })),
      neighborhoods
    };
  }

  async function newCode(db) {
    for (;;) {
      const code = [...randomBytes(8)].map(b => CODE_ALPHABET[b % CODE_ALPHABET.length]).join('');
      if (!(await db.get('SELECT 1 AS x FROM orders WHERE code = ?', [code]))) return code;
    }
  }

  async function createOrder(db, input) {
    const s = await getSettings(db);
    const status = storeStatus(s);
    if (!status.open) throw httpError(409, status.message);

    const name = clean(input.name, 80);
    const phone = clean(input.phone, 30).replace(/[^\d+() -]/g, '');
    if (name.length < 2) throw httpError(400, 'Informe seu nome.');
    if (phone.replace(/\D/g, '').length < 10) throw httpError(400, 'Informe um telefone com DDD.');

    const fulfillment = input.fulfillment === 'pickup' ? 'pickup' : 'delivery';
    if (fulfillment === 'pickup' && s.pickup_enabled === '0') throw httpError(400, 'Retirada indisponível no momento.');
    if (fulfillment === 'delivery' && s.delivery_enabled === '0') throw httpError(400, 'Entrega indisponível no momento.');

    const lines = Array.isArray(input.items) ? input.items.slice(0, 60) : [];
    if (!lines.length) throw httpError(400, 'Seu pedido está vazio.');
    const items = [];
    let subtotal = 0;
    for (const line of lines) {
      const product = await db.get('SELECT id, name, price_cents FROM products WHERE id = ? AND active = 1', [Number(line.id) || 0]);
      if (!product) throw httpError(409, 'Um item do seu pedido saiu do cardápio. Atualize a página.');
      const qty = Math.max(1, Math.min(30, Math.floor(Number(line.qty) || 1)));
      const picked = new Map();
      for (const o of Array.isArray(line.options) ? line.options.slice(0, 40) : []) {
        const id = Number(o.id) || 0;
        picked.set(id, (picked.get(id) || 0) + Math.max(1, Math.floor(Number(o.qty) || 1)));
      }
      const groups = await db.all('SELECT g.id, g.title, g.type, g.min_choices, g.max_choices FROM product_groups pg JOIN option_groups g ON g.id = pg.group_id WHERE pg.product_id = ? ORDER BY pg.sort', [product.id]);
      const optionRows = picked.size
        ? await db.all(`SELECT id, group_id, title, price_cents, max_qty FROM options WHERE active = 1 AND id IN (${[...picked.keys()].map(() => '?').join(',')})`, [...picked.keys()])
        : [];
      const chosen = [];
      for (const g of groups) {
        const inGroup = optionRows.filter(o => o.group_id === g.id).map(o => ({ o, n: picked.get(o.id) }));
        const count = inGroup.reduce((sum, x) => sum + (g.type === 'qty' ? x.n : 1), 0);
        if (count < g.min_choices) throw httpError(400, `${product.name}: escolha ${g.title.toLowerCase()}.`);
        if (count > g.max_choices) throw httpError(400, `${product.name}: no máximo ${g.max_choices} em ${g.title.toLowerCase()}.`);
        for (const { o, n } of inGroup) {
          const q = g.type === 'qty' ? Math.min(n, o.max_qty || g.max_choices) : 1;
          chosen.push({ id: o.id, group: g.title, name: o.title, qty: q, price_cents: o.price_cents });
        }
      }
      const unit = product.price_cents + chosen.reduce((sum, o) => sum + o.price_cents * o.qty, 0);
      if (unit <= 0) throw httpError(400, `${product.name}: escolha uma opção.`);
      subtotal += unit * qty;
      items.push({ id: product.id, name: product.name, qty, unit_cents: unit, options: chosen, note: clean(line.note, 140) });
    }

    const minOrder = Math.round(Number(s.min_order || 0) * 100);
    if (subtotal < minOrder) throw httpError(400, `O pedido mínimo é de R$ ${(minOrder / 100).toFixed(2).replace('.', ',')}.`);

    let address = {}, neighborhood = '', fee = 0;
    if (fulfillment === 'delivery') {
      const nb = await db.get('SELECT id, name, fee_cents FROM neighborhoods WHERE id = ? AND active = 1', [Number(input.address?.neighborhood_id) || 0]);
      if (!nb) throw httpError(400, 'Escolha o bairro da entrega.');
      address = {
        street: clean(input.address?.street, 120), number: clean(input.address?.number, 20),
        complement: clean(input.address?.complement, 80), reference: clean(input.address?.reference, 120)
      };
      if (address.street.length < 3 || !address.number) throw httpError(400, 'Informe rua e número para a entrega.');
      neighborhood = nb.name;
      fee = nb.fee_cents;
    }

    const payment = PAYMENTS[input.payment] ? input.payment : null;
    if (!payment) throw httpError(400, 'Escolha a forma de pagamento.');
    if (payment === 'pix' && !pixReady(s)) throw httpError(400, 'Pix indisponível agora. Escolha outra forma.');
    const total = subtotal + fee;
    const changeFor = payment === 'dinheiro' ? Math.round(Number(String(input.change_for || 0).replace(',', '.')) * 100) || 0 : 0;
    if (changeFor && changeFor < total) throw httpError(400, 'O troco precisa ser para um valor maior que o total.');

    const code = await newCode(db);
    const now = new Date().toISOString();
    await db.run(`INSERT INTO orders (code, created_at, updated_at, status, history, customer_name, customer_phone, fulfillment, address, neighborhood, items, subtotal_cents, delivery_fee_cents, total_cents, payment_method, change_for_cents, notes)
      VALUES (?, ?, ?, 'recebido', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [code, now, now, JSON.stringify([{ status: 'recebido', at: now }]), name, phone, fulfillment,
      JSON.stringify(address), neighborhood, JSON.stringify(items), subtotal, fee, total, payment, changeFor, clean(input.notes, 300)]);
    return code;
  }

  function publicOrder(row, s) {
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
  const adminOrder = (row, s) => ({
    ...publicOrder(row, s), id: row.id, customer_name: row.customer_name, customer_phone: row.customer_phone,
    address: JSON.parse(row.address || '{}'), notes: row.notes, change_for_cents: row.change_for_cents, updated_at: row.updated_at
  });

  // ---------------------------------------------------------------- painel
  async function handleAdmin(db, req, res, path, url) {
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
      const rows = scope === 'open'
        ? await db.all("SELECT * FROM orders WHERE status NOT IN ('entregue', 'cancelado') ORDER BY id DESC LIMIT 200")
        : await db.all('SELECT * FROM orders WHERE created_at >= ? ORDER BY id DESC LIMIT 500', [dayStartIso(scope === 'week' ? 6 : 0)]);
      const stats = await db.get("SELECT COUNT(*) AS orders, COALESCE(SUM(total_cents), 0) AS revenue FROM orders WHERE created_at >= ? AND status != 'cancelado'", [dayStartIso(0)]);
      const s = await getSettings(db);
      return send(res, 200, { orders: rows.map(r => adminOrder(r, s)), stats: { orders: Number(stats.orders), revenue: Number(stats.revenue) }, store: storeStatus(s) });
    }
    const orderMatch = path.match(/^\/api\/admin\/orders\/(\d+)$/);
    if (orderMatch && req.method === 'PATCH') {
      const id = Number(orderMatch[1]);
      const row = await db.get('SELECT * FROM orders WHERE id = ?', [id]);
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
      await db.run('UPDATE orders SET status = ?, history = ?, paid = ?, updated_at = ? WHERE id = ?', [status, JSON.stringify(history), paid, now, id]);
      return send(res, 200, adminOrder(await db.get('SELECT * FROM orders WHERE id = ?', [id]), await getSettings(db)));
    }

    if (path === '/api/admin/catalog' && req.method === 'GET') {
      const [categories, products, groups, options, neighborhoods, s] = await Promise.all([
        db.all('SELECT * FROM categories ORDER BY sort'),
        db.all('SELECT * FROM products ORDER BY category_id, sort, id'),
        db.all('SELECT * FROM option_groups ORDER BY title'),
        db.all('SELECT * FROM options ORDER BY group_id, sort, id'),
        db.all('SELECT * FROM neighborhoods ORDER BY name'),
        getSettings(db)
      ]);
      return send(res, 200, { categories, products, groups, options, neighborhoods, settings: Object.fromEntries(Object.entries(s).filter(([k]) => EDITABLE_SETTINGS.includes(k))) });
    }
    const productMatch = path.match(/^\/api\/admin\/products(?:\/(\d+))?$/);
    if (productMatch && (req.method === 'POST' || req.method === 'PUT')) {
      const b = await readJson(req);
      const fields = [clean(b.category_id, 40), clean(b.name, 80), clean(b.description, 300), Math.max(0, Math.round(Number(b.price_cents) || 0)), clean(b.image, 200), clean(b.badge, 30), b.active === false || b.active === 0 ? 0 : 1];
      if (!fields[1]) return fail(res, 400, 'O nome é obrigatório.');
      if (!(await db.get('SELECT 1 AS x FROM categories WHERE id = ?', [fields[0]]))) return fail(res, 400, 'Categoria inválida.');
      let row;
      if (req.method === 'POST') {
        row = await db.get('INSERT INTO products (category_id, name, description, price_cents, image, badge, active, sort) VALUES (?, ?, ?, ?, ?, ?, ?, 999) RETURNING *', fields);
      } else {
        await db.run('UPDATE products SET category_id = ?, name = ?, description = ?, price_cents = ?, image = ?, badge = ?, active = ? WHERE id = ?', [...fields, Number(productMatch[1])]);
        row = await db.get('SELECT * FROM products WHERE id = ?', [Number(productMatch[1])]);
      }
      onCatalogChange();
      return send(res, req.method === 'POST' ? 201 : 200, row);
    }
    const optionMatch = path.match(/^\/api\/admin\/options\/(\d+)$/);
    if (optionMatch && req.method === 'PUT') {
      const b = await readJson(req);
      const title = clean(b.title, 60), price = Math.max(0, Math.round(Number(b.price_cents) || 0)), active = b.active === false || b.active === 0 ? 0 : 1;
      if (!title) return fail(res, 400, 'Informe o nome da opção.');
      await db.run('UPDATE options SET title = ?, price_cents = ?, active = ? WHERE id = ?', [title, price, active, Number(optionMatch[1])]);
      onCatalogChange();
      return send(res, 200, { ok: true });
    }
    const nbMatch = path.match(/^\/api\/admin\/neighborhoods(?:\/(\d+))?$/);
    if (nbMatch && (req.method === 'POST' || req.method === 'PUT')) {
      const b = await readJson(req);
      const name = clean(b.name, 60), fee = Math.max(0, Math.round(Number(b.fee_cents) || 0)), eta = clean(b.eta, 30) || '35 a 50 min', active = b.active === false || b.active === 0 ? 0 : 1;
      if (!name) return fail(res, 400, 'Informe o nome do bairro.');
      try {
        if (req.method === 'POST') await db.run('INSERT INTO neighborhoods (name, fee_cents, eta, active) VALUES (?, ?, ?, ?)', [name, fee, eta, active]);
        else await db.run('UPDATE neighborhoods SET name = ?, fee_cents = ?, eta = ?, active = ? WHERE id = ?', [name, fee, eta, active, Number(nbMatch[1])]);
      } catch { return fail(res, 409, 'Esse bairro já existe.'); }
      onCatalogChange();
      return send(res, 200, { ok: true });
    }
    if (path === '/api/admin/settings' && req.method === 'PUT') {
      const b = await readJson(req);
      for (const [k, v] of Object.entries(b)) {
        if (EDITABLE_SETTINGS.includes(k)) await db.run('INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value', [k, clean(v, 300)]);
      }
      onCatalogChange();
      return send(res, 200, { ok: true, store: storeStatus(await getSettings(db)) });
    }
    return fail(res, 404, 'Rota não encontrada.');
  }

  // ---------------------------------------------------------------- roteador da API
  async function handle(req, res) {
    const url = new URL(req.url, 'http://localhost');
    let path = url.pathname.replace(/\/+$/, '') || '/';
    // Na Vercel a rota chega reescrita para /api/index?__path=...; recupera o caminho original.
    if (/^\/api\/index(\.js)?$/.test(path) && url.searchParams.get('__path')) path = '/api/' + url.searchParams.get('__path');
    try {
      const db = await database();
      if (path.startsWith('/api/admin/')) return await handleAdmin(db, req, res, path, url);
      if (path === '/api/menu' && req.method === 'GET') return send(res, 200, await menuPayload(db));
      if (path === '/api/orders' && req.method === 'POST') {
        if (limited('order:' + clientIp(req), 12, 15 * 60e3)) return fail(res, 429, 'Muitos pedidos seguidos. Chame a gente no WhatsApp.');
        const code = await createOrder(db, await readJson(req));
        return send(res, 201, publicOrder(await db.get('SELECT * FROM orders WHERE code = ?', [code]), await getSettings(db)));
      }
      const track = path.match(/^\/api\/orders\/([A-Z0-9]{6,12})$/);
      if (track && req.method === 'GET') {
        const row = await db.get('SELECT * FROM orders WHERE code = ?', [track[1]]);
        return row ? send(res, 200, publicOrder(row, await getSettings(db))) : fail(res, 404, 'Pedido não encontrado.');
      }
      if (path === '/api/health') return send(res, 200, { ok: true, db: db.kind });
      return fail(res, 404, 'Rota não encontrada.');
    } catch (err) {
      if (!err.status) console.error(err);
      if (!res.headersSent) fail(res, err.status || 500, err.status ? err.message : 'Algo deu errado. Tente de novo.');
    }
  }

  return { handle, menu: async () => menuPayload(await database()) };
}
