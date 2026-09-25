// Banco de dados com duas bases possíveis, mesma interface assíncrona:
// - Postgres quando existe DATABASE_URL (ou POSTGRES_URL): é o que roda na Vercel (Neon).
// - SQLite embutido no Node (node:sqlite) no resto: computador local ou servidor próprio.
// O SQL do app usa "?" como parâmetro; o adaptador do Postgres converte para $1, $2...
import { mkdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';

const TABLES = id => `
  CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, blurb TEXT DEFAULT '', sort INTEGER DEFAULT 0, active INTEGER DEFAULT 1
  );
  CREATE TABLE IF NOT EXISTS products (
    id ${id}, category_id TEXT NOT NULL REFERENCES categories(id), slug TEXT DEFAULT '',
    name TEXT NOT NULL, description TEXT DEFAULT '', price_cents INTEGER NOT NULL DEFAULT 0,
    image TEXT DEFAULT '', badge TEXT DEFAULT '', active INTEGER DEFAULT 1, sort INTEGER DEFAULT 0
  );
  -- Grupos de opções: 'one' (escolha uma), 'many' (escolha N), 'qty' (adicionais com quantidade)
  CREATE TABLE IF NOT EXISTS option_groups (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, type TEXT NOT NULL, min_choices INTEGER DEFAULT 0, max_choices INTEGER DEFAULT 1
  );
  CREATE TABLE IF NOT EXISTS options (
    id ${id}, group_id TEXT NOT NULL REFERENCES option_groups(id), title TEXT NOT NULL,
    price_cents INTEGER NOT NULL DEFAULT 0, max_qty INTEGER DEFAULT 1, active INTEGER DEFAULT 1, sort INTEGER DEFAULT 0
  );
  CREATE TABLE IF NOT EXISTS product_groups (
    product_id INTEGER NOT NULL REFERENCES products(id), group_id TEXT NOT NULL REFERENCES option_groups(id),
    sort INTEGER DEFAULT 0, PRIMARY KEY (product_id, group_id)
  );
  CREATE TABLE IF NOT EXISTS neighborhoods (
    id ${id}, name TEXT NOT NULL UNIQUE, fee_cents INTEGER NOT NULL, eta TEXT DEFAULT '35 a 50 min', active INTEGER DEFAULT 1
  );
  CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
  CREATE TABLE IF NOT EXISTS orders (
    id ${id}, code TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'recebido', history TEXT NOT NULL DEFAULT '[]',
    customer_name TEXT NOT NULL, customer_phone TEXT NOT NULL, fulfillment TEXT NOT NULL,
    address TEXT DEFAULT '{}', neighborhood TEXT DEFAULT '', items TEXT NOT NULL,
    subtotal_cents INTEGER NOT NULL, delivery_fee_cents INTEGER NOT NULL DEFAULT 0, total_cents INTEGER NOT NULL,
    payment_method TEXT NOT NULL, change_for_cents INTEGER DEFAULT 0, paid INTEGER NOT NULL DEFAULT 0, notes TEXT DEFAULT ''
  );
  CREATE INDEX IF NOT EXISTS orders_created ON orders(created_at);
  -- Respostas dos serviços de CEP e mapa guardadas por 30 dias (mais rápido e sem abusar dos serviços grátis)
  CREATE TABLE IF NOT EXISTS lookup_cache (key TEXT PRIMARY KEY, data TEXT NOT NULL, at TEXT NOT NULL);
`;

async function sqliteAdapter(path) {
  const { DatabaseSync } = await import('node:sqlite');
  mkdirSync(dirname(path), { recursive: true });
  const d = new DatabaseSync(path);
  d.exec('PRAGMA journal_mode = WAL; PRAGMA foreign_keys = ON;');
  const cache = new Map();
  const prep = sql => {
    let s = cache.get(sql);
    if (!s) { s = d.prepare(sql); cache.set(sql, s); }
    return s;
  };
  const api = {
    kind: 'sqlite',
    schema: TABLES('INTEGER PRIMARY KEY AUTOINCREMENT'),
    exec: async sql => { d.exec(sql); },
    all: async (sql, p = []) => prep(sql).all(...p),
    get: async (sql, p = []) => prep(sql).get(...p),
    run: async (sql, p = []) => ({ changes: Number(prep(sql).run(...p).changes) }),
    lock: async () => {},
    resetSequence: async () => {},
    tx: async fn => {
      d.exec('BEGIN IMMEDIATE');
      try { const r = await fn(api); d.exec('COMMIT'); return r; }
      catch (err) { d.exec('ROLLBACK'); throw err; }
    }
  };
  return api;
}

async function pgAdapter(url) {
  const { default: pg } = await import('pg');
  pg.types.setTypeParser(20, v => parseInt(v, 10)); // COUNT e SUM voltam como número, não texto
  const pool = new pg.Pool({ connectionString: url, max: 4, idleTimeoutMillis: 10000, connectionTimeoutMillis: 8000 });
  const toPg = sql => { let i = 0; return sql.replace(/\?/g, () => '$' + (++i)); };
  const wrap = client => ({
    kind: 'pg',
    schema: TABLES('SERIAL PRIMARY KEY'),
    exec: async sql => { await client.query(sql); },
    all: async (sql, p = []) => (await client.query(toPg(sql), p)).rows,
    get: async (sql, p = []) => (await client.query(toPg(sql), p)).rows[0],
    run: async (sql, p = []) => ({ changes: (await client.query(toPg(sql), p)).rowCount }),
    lock: async key => { await client.query('SELECT pg_advisory_xact_lock($1)', [key]); },
    resetSequence: async table => {
      await client.query(`SELECT setval(pg_get_serial_sequence('${table}', 'id'), GREATEST((SELECT COALESCE(MAX(id), 0) FROM ${table}), 1))`);
    }
  });
  return {
    ...wrap(pool),
    tx: async fn => {
      const client = await pool.connect();
      try {
        await client.query('BEGIN');
        const r = await fn(wrap(client));
        await client.query('COMMIT');
        return r;
      } catch (err) {
        await client.query('ROLLBACK').catch(() => {});
        throw err;
      } finally {
        client.release();
      }
    }
  };
}

// Cria as tabelas e, se o cardápio estiver vazio, carrega data/seed.json.
// Tudo dentro de uma transação com trava, para dois servidores subindo juntos não duplicarem nada.
async function prepare(db, seedPath) {
  return db.tx(async t => {
    await t.lock(2002);
    await t.exec(t.schema);
    const { n } = await t.get('SELECT COUNT(*) AS n FROM products');
    if (Number(n) > 0) return false;
    const seed = JSON.parse(readFileSync(seedPath, 'utf8'));
    let optionId = 0, productId = 0;
    for (const g of seed.groups) {
      await t.run('INSERT INTO option_groups (id, title, type, min_choices, max_choices) VALUES (?, ?, ?, ?, ?) ON CONFLICT (id) DO NOTHING', [g.id, g.title, g.type, g.min, g.max]);
      for (const [i, o] of g.options.entries()) {
        await t.run('INSERT INTO options (id, group_id, title, price_cents, max_qty, sort) VALUES (?, ?, ?, ?, ?, ?)', [++optionId, g.id, o.title, Math.round(o.price * 100), o.max || 1, i]);
      }
    }
    for (const [i, c] of seed.categories.entries()) {
      await t.run('INSERT INTO categories (id, name, blurb, sort) VALUES (?, ?, ?, ?) ON CONFLICT (id) DO NOTHING', [c.id, c.name, c.blurb || '', i]);
      for (const [j, p] of c.products.entries()) {
        const id = ++productId;
        await t.run('INSERT INTO products (id, category_id, slug, name, description, price_cents, image, badge, sort) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
          [id, c.id, p.slug || '', p.name, p.description || '', Math.round(p.price * 100), p.image || '', p.badge || '', j]);
        for (const [k, g] of (p.groups || []).entries()) await t.run('INSERT INTO product_groups (product_id, group_id, sort) VALUES (?, ?, ?)', [id, g, k]);
      }
    }
    for (const n of seed.neighborhoods) {
      await t.run('INSERT INTO neighborhoods (name, fee_cents, eta) VALUES (?, ?, ?) ON CONFLICT (name) DO NOTHING', [n.name, Math.round(n.fee * 100), n.eta || '35 a 50 min']);
    }
    for (const [k, v] of Object.entries(seed.settings)) {
      await t.run('INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO NOTHING', [k, String(v)]);
    }
    await t.resetSequence('products');
    await t.resetSequence('options');
    return true;
  });
}

export async function openDb(root) {
  const url = process.env.DATABASE_URL || process.env.POSTGRES_URL;
  const preview = process.env.DITOS_PREVIEW === '1';
  if (!url && process.env.VERCEL && !preview) {
    throw Object.assign(new Error('Banco não configurado: ligue um Postgres (Neon) ao projeto na Vercel.'), { status: 503 });
  }
  // Prévia na Vercel sem Postgres: SQLite na pasta temporária da função (os dados não são permanentes).
  const sqlitePath = process.env.DB_PATH || (process.env.VERCEL ? '/tmp/ditos.db' : join(root, 'data', 'ditos.db'));
  const db = url ? await pgAdapter(url) : await sqliteAdapter(sqlitePath);
  const seeded = await prepare(db, join(root, 'data', 'seed.json'));
  if (seeded && preview) {
    // Na prévia a loja fica aberta a qualquer hora, para dar para testar o pedido.
    await db.run("INSERT INTO settings (key, value) VALUES ('store_mode', 'open') ON CONFLICT (key) DO UPDATE SET value = excluded.value");
  }
  if (seeded) console.log(`[banco] cardápio inicial carregado (${db.kind})`);
  return db;
}
