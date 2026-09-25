// Testa o frete com CEPs reais de São Mateus (busca ruas no ViaCEP e calcula cada uma).
// Uso: node tools/test-frete.mjs   (precisa de internet; roda no GitHub Actions)
import { readFileSync } from 'node:fs';
import { quoteDelivery } from '../lib/frete.js';

const seed = JSON.parse(readFileSync(new URL('../data/seed.json', import.meta.url)));
const neighborhoods = seed.neighborhoods.map(n => ({ name: n.name, fee_cents: Math.round(n.fee * 100), eta: n.eta, active: 1 }));
const mem = new Map();
const cache = { get: async k => mem.get(k) || null, set: async (k, v) => { mem.set(k, v); } };

const picked = new Map();
for (const term of ['Rua', 'Avenida', 'Travessa']) {
  const res = await fetch(`https://viacep.com.br/ws/ES/Sao%20Mateus/${term}/json/`);
  const list = res.ok ? await res.json() : [];
  for (const r of list) if (r.bairro && !picked.has(r.bairro) && picked.size < 24) picked.set(r.bairro, r);
}
console.log(`CEPs de teste: ${picked.size} bairros diferentes\n`);
let ok = 0, byDistance = 0;
for (const r of [{ cep: '29936-050', bairro: 'Centro (loja)', logradouro: 'Av. Dr. Raimundo G. Sobrinho' }, ...picked.values()]) {
  const q = await quoteDelivery({ cep: r.cep, number: '', settings: {}, neighborhoods, cache });
  if (q.ok) { ok++; if (q.method === 'distancia') byDistance++; }
  console.log(`${r.cep}  ${String(r.bairro).padEnd(24).slice(0, 24)}  ${q.ok ? `R$ ${(q.fee_cents / 100).toFixed(2)}  ${q.method.padEnd(9)} ${q.distance_km ?? '-'} km` : 'X  ' + q.error}`);
  await new Promise(r => setTimeout(r, 1100)); // respeita o limite do OpenStreetMap
}
console.log(`\n${ok} com frete calculado (${byDistance} pela distância, ${ok - byDistance} pelo bairro).`);
