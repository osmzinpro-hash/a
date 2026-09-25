// Testa o frete com CEPs reais de São Mateus (busca ruas no ViaCEP e calcula cada uma).
// Uso: node tools/test-frete.mjs   (precisa de internet; roda no GitHub Actions)
import { readFileSync } from 'node:fs';
import { quoteDelivery, lookupCep, distanceKm, DEFAULTS } from '../lib/frete.js';

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
  const q = await quoteDelivery({ cep: r.cep, number: '100', settings: {}, neighborhoods, cache });
  if (q.ok) { ok++; if (q.method === 'distancia') byDistance++; }
  console.log(`${r.cep}  ${String(r.bairro).padEnd(26).slice(0, 26)} ${String(r.logradouro || '').padEnd(34).slice(0, 34)} ${q.ok ? `R$ ${(q.fee_cents / 100).toFixed(2)}  ${q.method.padEnd(9)} ${q.distance_km ?? '-'} km` : 'X  ' + q.error}`);
  await new Promise(r => setTimeout(r, 1100)); // respeita o limite do OpenStreetMap
  if (process.env.FRETE_DEBUG && q.method !== 'distancia') await debug(r.cep);
}
console.log(`\n${ok} com frete calculado (${byDistance} pela distância, ${ok - byDistance} pelo bairro).`);

// FRETE_DEBUG=1: mostra o que o CEP e o OpenStreetMap devolveram quando não saiu pela distância.
async function debug(cep) {
  const a = await lookupCep(cep.replace(/\D/g, ''));
  console.log(`    cep -> rua "${a?.street}" bairro "${a?.district}"`);
  const show = async (label, url) => {
    const res = await fetch(url, { headers: { 'user-agent': 'DitosLanches/1.0 (teste de frete)' } });
    const list = res.ok ? await res.json() : [];
    console.log(`    ${label}: ${list.length} resultado(s)`);
    for (const x of list) {
      const ad = x.address || {};
      const km = distanceKm(DEFAULTS.store, { lat: +x.lat, lng: +x.lon }).toFixed(1);
      console.log(`      ${x.category}/${x.addresstype} "${x.name}" · ${[ad.suburb, ad.neighbourhood, ad.quarter, ad.city_district, ad.residential].filter(Boolean).join(' / ') || '(sem bairro)'} · ${ad.city || ad.town || ad.municipality || ad.village} · ${km} km`);
    }
    await new Promise(r => setTimeout(r, 1100));
  };
  const base = 'https://nominatim.openstreetmap.org/search?format=jsonv2&limit=6&countrycodes=br&addressdetails=1';
  await show('rua', `${base}&street=${encodeURIComponent(a?.street || '')}&city=S%C3%A3o%20Mateus&state=Esp%C3%ADrito%20Santo`);
  await show('texto', `${base}&q=${encodeURIComponent(`${a?.street}, ${a?.district}, São Mateus, ES`)}`);
  await show('bairro', `${base}&q=${encodeURIComponent(`${a?.district}, São Mateus, Espírito Santo`)}`);
}
