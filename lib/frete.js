// Frete automático pelo CEP: CEP -> endereço e localização -> distância em linha reta até a loja
// -> faixa de preço (igual à configuração da Ditos na Brendi). Sem localização, usa o bairro do CEP
// na tabela de bairros. Tudo calculado no servidor; o navegador nunca define o valor do frete.

// Padrões tirados da configuração real da loja na Brendi. A aba Loja do painel pode sobrescrever.
export const DEFAULTS = {
  city: 'São Mateus',
  uf: 'ES',
  store: { lat: -18.719059, lng: -39.859791 },
  ranges: [
    { km: 1, fee_cents: 700, eta: '20 a 30 min' },
    { km: 2, fee_cents: 800, eta: '25 a 35 min' },
    { km: 2.5, fee_cents: 900, eta: '25 a 35 min' },
    { km: 3.5, fee_cents: 1000, eta: '25 a 35 min' },
    { km: 4, fee_cents: 1200, eta: '25 a 35 min' },
    { km: 5, fee_cents: 1300, eta: '25 a 35 min' },
    { km: 6, fee_cents: 1500, eta: '25 a 35 min' }
  ],
  // Áreas onde a loja não entrega (polígonos da Brendi).
  noDelivery: [
    { name: 'Nova Era', polygon: [[-18.757175, -39.8699], [-18.757621, -39.857283], [-18.75055, -39.859171], [-18.749494, -39.865437]] },
    { name: 'Liberdade', polygon: [[-18.73892, -39.810419], [-18.740707, -39.808924], [-18.748102, -39.810848], [-18.746152, -39.816084], [-18.737861, -39.818072], [-18.736607, -39.817376]] },
    { name: 'Litorâneo', polygon: [[-18.697029, -39.872327], [-18.695557, -39.860115], [-18.681008, -39.856124], [-18.672148, -39.858098], [-18.671281, -39.865566], [-18.673135, -39.874273]] }
  ]
};

const UA = 'DitosLanches/1.0 (pedidos online; ditoslanches.vercel.app)';
export const norm = s => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  .replace(/\b(bairro|loteamento|lot|residencial|res|conjunto|cj|condominio)\b/g, ' ')
  .replace(/\b(park|pq)\b/g, 'parque').replace(/\bjd\b/g, 'jardim').replace(/\bvl\b/g, 'vila')
  .replace(/\bsta\b/g, 'santa').replace(/\bsto\b/g, 'santo').replace(/\bbonsucesso\b/g, 'bom sucesso')
  .replace(/\biii\b/g, '3').replace(/\bii\b/g, '2').replace(/\bi\b/g, '1')
  .replace(/[^a-z0-9]+/g, ' ').trim();

async function getJson(url, ms = 4500) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try {
    const res = await fetch(url, { signal: ctrl.signal, headers: { 'user-agent': UA, accept: 'application/json' } });
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; } finally { clearTimeout(t); }
}

const num = v => { const n = Number(v); return Number.isFinite(n) && n !== 0 ? n : null; };

// CEP -> { cep, street, district, city, uf }. Tenta três serviços gratuitos.
// (A localização que alguns devolvem é a do centro da cidade em São Mateus, por isso não é usada.)
export async function lookupCep(cep) {
  const [awesome, via] = await Promise.all([
    getJson(`https://cep.awesomeapi.com.br/json/${cep}`),
    getJson(`https://viacep.com.br/ws/${cep}/json/`)
  ]);
  let out = null;
  if (awesome && !awesome.code && awesome.city) {
    out = { street: awesome.address || '', district: awesome.district || '', city: awesome.city, uf: awesome.state };
  }
  if (via && !via.erro && via.localidade) {
    out = out || {};
    out.street = out.street || via.logradouro || '';
    out.district = out.district || via.bairro || '';
    out.city = out.city || via.localidade;
    out.uf = out.uf || via.uf;
  }
  if (!out) {
    const br = await getJson(`https://brasilapi.com.br/api/cep/v2/${cep}`);
    if (br && br.city) out = { street: br.street || '', district: br.neighborhood || '', city: br.city, uf: br.state };
  }
  return out ? { cep, ...out } : null;
}

// Rua -> trechos com esse nome na cidade, pelo OpenStreetMap (só ruas/imóveis dentro da cidade;
// centro da cidade ou bairro inteiro dariam frete errado). null = serviço fora do ar (não guardar).
const OSM = 'https://nominatim.openstreetmap.org/search?format=jsonv2&limit=6&countrycodes=br&addressdetails=1';
const TRUSTED = new Set(['road', 'house', 'building', 'residential', 'house_number']);
const placeOf = x => x.address?.city || x.address?.town || x.address?.municipality || x.address?.village || '';
const areaOf = x => [x.address?.suburb, x.address?.neighbourhood, x.address?.quarter, x.address?.city_district, x.address?.residential].filter(Boolean);
let lastOsm = 0;
async function osm(url) { // o OpenStreetMap pede no máximo 1 consulta por segundo
  const wait = lastOsm + 1000 - Date.now();
  if (wait > 0) await new Promise(r => setTimeout(r, wait));
  lastOsm = Date.now();
  return getJson(url);
}
export async function searchStreet({ street, city, uf }) {
  if (!street) return [];
  const r = await osm(`${OSM}&street=${encodeURIComponent(street)}&city=${encodeURIComponent(city)}&state=${encodeURIComponent(UF_NAMES[uf] || uf)}`);
  if (!Array.isArray(r)) return null;
  return r.filter(x => (x.category === 'highway' || TRUSTED.has(x.addresstype)) && norm(placeOf(x)) === norm(city) && num(x.lat) && num(x.lon))
    .map(x => ({ lat: num(x.lat), lng: num(x.lon), areas: areaOf(x) }));
}
// Bairro -> ponto central dele no mapa. { miss: true } quando o mapa não conhece o bairro.
export async function searchArea({ district, city, uf }) {
  if (!district) return { miss: true };
  const r = await osm(`${OSM}&q=${encodeURIComponent(`${district}, ${city}, ${UF_NAMES[uf] || uf}`)}`);
  if (!Array.isArray(r)) return null;
  const hit = r.find(x => (x.category === 'place' || x.addresstype === 'residential') && norm(placeOf(x)) === norm(city)
    && norm(x.name) === norm(district) && num(x.lat) && num(x.lon));
  return hit ? { lat: num(hit.lat), lng: num(hit.lon) } : { miss: true };
}
// "Rua G", "Rua Um", "Avenida 10": nomes que se repetem em vários bairros da cidade.
const GENERIC = /^(rua|avenida|av|travessa|tv|beco|alameda|estrada|servidao)\s+([a-z]|\d+|um|dois|tres|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|quatorze|catorze|quinze|dezesseis|dezessete|dezoito|dezenove|vinte)$/;
const sameArea = (a, d) => { const n = norm(a); return !!n && !!d && (n === d || ` ${n} `.includes(` ${d} `) || ` ${d} `.includes(` ${n} `)); };
const UF_NAMES = { ES: 'Espírito Santo', MG: 'Minas Gerais', BA: 'Bahia', RJ: 'Rio de Janeiro', SP: 'São Paulo' };

export function distanceKm(a, b) {
  const R = 6371, rad = x => x * Math.PI / 180;
  const dLat = rad(b.lat - a.lat), dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

export function insidePolygon(p, polygon) {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [yi, xi] = polygon[i], [yj, xj] = polygon[j];
    if ((yi > p.lat) !== (yj > p.lat) && p.lng < (xj - xi) * (p.lat - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

// Faixas no formato do painel: uma por linha, "até km | taxa | tempo", ex.: "1 | 7,00 | 20 a 30 min".
export function parseRanges(text) {
  const out = [];
  for (const line of String(text || '').split('\n')) {
    const [km, fee, eta] = line.split('|').map(s => s.trim());
    const k = Number(String(km).replace(',', '.')), f = Math.round(Number(String(fee || '').replace(/[^\d,.]/g, '').replace(',', '.')) * 100);
    if (k > 0 && f >= 0 && Number.isFinite(f)) out.push({ km: k, fee_cents: f, eta: eta || '30 a 40 min' });
  }
  return out.sort((a, b) => a.km - b.km);
}
export const formatRanges = ranges => ranges.map(r => `${String(r.km).replace('.', ',')} | ${(r.fee_cents / 100).toFixed(2).replace('.', ',')} | ${r.eta}`).join('\n');

// Configuração efetiva (padrões + o que a loja mudou no painel).
export function deliveryConfig(s = {}) {
  let ranges = DEFAULTS.ranges;
  if (s.delivery_ranges) { const r = parseRanges(s.delivery_ranges); if (r.length) ranges = r; }
  const lat = num(s.store_lat), lng = num(s.store_lng);
  return {
    city: s.delivery_city || DEFAULTS.city,
    uf: DEFAULTS.uf,
    store: lat && lng ? { lat, lng } : DEFAULTS.store,
    ranges,
    noDelivery: DEFAULTS.noDelivery
  };
}

/**
 * Calcula o frete. `neighborhoods` é a tabela de bairros (plano B quando não há localização).
 * Retorna { ok, cep, street, district, city, uf, fee_cents, eta, method, distance_km } ou { ok:false, error }.
 */
export async function quoteDelivery({ cep, number, settings, neighborhoods, cache }) {
  cep = String(cep || '').replace(/\D/g, '');
  if (cep.length !== 8) return { ok: false, error: 'Digite o CEP completo, com 8 números.' };
  const cfg = deliveryConfig(settings);

  let addr = await cache.get('cep:' + cep);
  if (!addr) {
    addr = await lookupCep(cep);
    if (!addr) return { ok: false, error: 'Não encontramos esse CEP. Confira os números.' };
    await cache.set('cep:' + cep, addr);
  }
  if (norm(addr.city) !== norm(cfg.city) || String(addr.uf || '').toUpperCase() !== cfg.uf) {
    return { ok: false, ...addr, error: `Esse CEP é de ${addr.city} - ${addr.uf}. Por enquanto só entregamos em ${cfg.city}.` };
  }

  // CEP geral da cidade (sem rua): a localização dele é o centro da cidade e daria frete errado.
  if (!addr.street) return { ok: false, cep, city: addr.city, uf: addr.uf, error: 'Esse é o CEP geral da cidade. Use o CEP da sua rua para calcularmos o frete.' };

  const base = { cep, street: addr.street, district: addr.district, city: addr.city, uf: addr.uf };
  const blockedByName = cfg.noDelivery.find(a => norm(a.name) === norm(addr.district));
  if (blockedByName) return { ok: false, ...base, error: `Ainda não entregamos na região de ${blockedByName.name}. Você pode retirar no balcão.` };

  // Localização. Consultas guardadas por 30 dias (a do bairro vale para todos os CEPs dele);
  // falha de rede não é guardada, para tentar de novo no próximo cliente.
  const cached = async (key, fn) => {
    const hit = await cache.get(key);
    if (hit) return hit;
    const fresh = await fn();
    if (fresh) await cache.set(key, fresh);
    return fresh;
  };
  const d = norm(addr.district);
  const found = await cached(`rua:${cep}`, async () => { const h = await searchStreet(addr); return h && { hits: h }; });
  const streets = found?.hits || [];
  const nb = matchNeighborhood(addr.district, neighborhoods);
  const zone = p => {
    const blocked = cfg.noDelivery.find(a => insidePolygon(p, a.polygon));
    if (blocked) return { blocked };
    const km = distanceKm(cfg.store, p);
    return { km, range: cfg.ranges.find(r => km <= r.km) };
  };
  const priced = (p, method) => {
    const z = zone(p);
    if (z.blocked) return { ok: false, ...base, error: `Ainda não entregamos na região de ${z.blocked.name}. Você pode retirar no balcão.` };
    const km = Math.round(z.km * 10) / 10;
    if (z.range) return { ok: true, ...base, fee_cents: z.range.fee_cents, eta: z.range.eta, method, distance_km: method === 'distancia' ? km : null };
    return { ok: false, ...base, distance_km: km, error: `Esse endereço fica a ${z.km.toFixed(1).replace('.', ',')} km. Entregamos até ${String(cfg.ranges.at(-1).km).replace('.', ',')} km da loja.` };
  };
  const nearest = (to, list) => list.reduce((a, b) => (distanceKm(to, b) < distanceKm(to, a) ? b : a));

  // 1) A rua no mapa fica no bairro do CEP: distância exata.
  const inArea = streets.find(h => h.areas.some(a => sameArea(a, d)));
  if (inArea) {
    const q = priced(inArea, 'distancia');
    // Longe demais, mas o bairro está na tabela: o mapa provavelmente pegou outra rua; vale o bairro.
    if (q.ok || !nb || zone(inArea).blocked) return q;
  }
  // 2) Bairro na tabela da loja.
  if (nb) return { ok: true, ...base, fee_cents: nb.fee_cents, eta: nb.eta, method: 'bairro' };
  // 3) Rua de nome próprio cujos trechos no mapa dão todos o mesmo preço: é essa.
  if (streets.length && !GENERIC.test(norm(addr.street))) {
    const key = p => { const z = zone(p); return z.blocked ? 'x' + z.blocked.name : String(z.range ? z.range.km : 'longe'); };
    if (new Set(streets.map(key)).size === 1) return priced(nearest(cfg.store, streets), 'distancia');
  }
  // 4) Centro do bairro no mapa: o trecho da rua perto dele ou, sem isso, o próprio centro do bairro.
  const area = await cached(`bairro:${d}`, () => searchArea(addr));
  if (area && !area.miss) {
    const near = streets.length ? nearest(area, streets) : null;
    return near && distanceKm(area, near) <= 1.2 ? priced(near, 'distancia') : priced(area, 'bairro-mapa');
  }
  if (!found || !area) return { ok: false, ...base, error: 'O mapa não respondeu agora. Tente de novo em alguns segundos.' };
  return { ok: false, ...base, error: 'Não conseguimos calcular o frete desse endereço. Chame a gente no WhatsApp ou retire no balcão.' };
}

// Bairro do CEP -> bairro da tabela (ignora acento, "Bairro", abreviações e I/II/III).
export function matchNeighborhood(district, neighborhoods) {
  const d = norm(district);
  if (!d) return null;
  const active = neighborhoods.filter(n => n.active !== 0);
  const exact = active.filter(n => norm(n.name) === d);
  if (exact.length === 1) return exact[0];
  const partial = active.filter(n => { const x = norm(n.name); return x.startsWith(d + ' ') || d.startsWith(x + ' '); });
  // Vários parecidos (Bom Sucesso I, II e III): só vale se todos têm o mesmo preço.
  return partial.length && partial.every(n => n.fee_cents === partial[0].fee_cents) ? partial[0] : null;
}
