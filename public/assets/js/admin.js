// Painel da cozinha: pedidos ao vivo, cardápio, bairros e dados da loja.
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const money = c => ((c || 0) / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  const cents = v => Math.round(Number(String(v).replace(/[^\d,.-]/g, '').replace(/\.(?=\d{3}(\D|$))/g, '').replace(',', '.')) * 100) || 0;
  const time = iso => new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  const TOKEN_KEY = 'ditos-painel';

  let token = null;
  try { token = sessionStorage.getItem(TOKEN_KEY); } catch {}

  function h(tag, attrs = {}, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const c of kids.flat()) if (c != null && c !== false) el.append(c.nodeType ? c : String(c));
    return el;
  }

  async function api(method, path, body) {
    const res = await fetch(path, {
      method,
      headers: { 'content-type': 'application/json', authorization: `Bearer ${token || ''}` },
      body: body ? JSON.stringify(body) : undefined
    });
    const data = await res.json().catch(() => ({}));
    if (res.status === 401 && path !== '/api/admin/login') { logout(); throw new Error(data.error || 'Sessão expirada'); }
    if (!res.ok) throw new Error(data.error || 'Erro');
    return data;
  }

  // ------------------------------------------------------------ login
  $('[data-login-form]').addEventListener('submit', async e => {
    e.preventDefault();
    const err = $('[data-login-error]');
    err.hidden = true;
    try {
      const { token: t } = await api('POST', '/api/admin/login', { password: e.target.password.value });
      token = t;
      try { sessionStorage.setItem(TOKEN_KEY, t); } catch {}
      start();
    } catch (ex) { err.textContent = ex.message; err.hidden = false; }
  });
  function logout() {
    token = null;
    try { sessionStorage.removeItem(TOKEN_KEY); } catch {}
    clearTimeout(pollTimer);
    $('[data-app]').hidden = true;
    $('[data-login]').hidden = false;
  }
  $('[data-logout]').addEventListener('click', logout);

  // ------------------------------------------------------------ abas
  $$('[data-tab]').forEach(tab => tab.addEventListener('click', () => {
    $$('[data-tab]').forEach(t => t.setAttribute('aria-selected', String(t === tab)));
    $$('[data-pane]').forEach(p => { p.hidden = p.dataset.pane !== tab.dataset.tab; });
    if (tab.dataset.tab === 'cardapio' || tab.dataset.tab === 'bairros' || tab.dataset.tab === 'loja') loadCatalog();
  }));

  // ------------------------------------------------------------ pedidos
  const NEXT = {
    recebido: [['na_chapa', 'Mandar pra chapa']],
    na_chapa: [['saiu', 'Saiu pra entrega', 'delivery'], ['pronto', 'Pronto pra retirar', 'pickup']],
    saiu: [['entregue', 'Entregue']],
    pronto: [['entregue', 'Retirado']]
  };
  const PAY = { pix: 'Pix', credito: 'Crédito na entrega', debito: 'Débito na entrega', dinheiro: 'Dinheiro', vale: 'Vale-refeição' };
  let known = null, pollTimer = null, soundOn = false, unseen = 0, audioCtx = null;

  function beep() {
    if (!soundOn) return;
    try {
      audioCtx ||= new (window.AudioContext || window.webkitAudioContext)();
      [0, 0.22, 0.44].forEach(t => {
        const o = audioCtx.createOscillator(), g = audioCtx.createGain();
        o.frequency.value = 880; o.type = 'triangle';
        g.gain.setValueAtTime(0.0001, audioCtx.currentTime + t);
        g.gain.exponentialRampToValueAtTime(0.3, audioCtx.currentTime + t + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + t + 0.18);
        o.connect(g).connect(audioCtx.destination);
        o.start(audioCtx.currentTime + t); o.stop(audioCtx.currentTime + t + 0.2);
      });
    } catch {}
  }
  $('[data-sound]').addEventListener('click', e => {
    soundOn = !soundOn;
    e.target.textContent = soundOn ? '🔔 Som ligado' : '🔔 Ativar som de novo pedido';
    if (soundOn) beep();
  });

  function orderCard(o, isNew) {
    const addr = o.fulfillment === 'delivery'
      ? `${o.address.street}, ${o.address.number}${o.address.complement ? ', ' + o.address.complement : ''} · ${o.neighborhood}${o.address.cep ? ' · CEP ' + o.address.cep : ''}${o.address.distance_km != null ? ` · ${String(o.address.distance_km).replace('.', ',')} km` : ''}${o.address.reference ? ' · Ref.: ' + o.address.reference : ''}`
      : 'Retirada no balcão';
    const phone = o.customer_phone.replace(/\D/g, '');
    const track = `${location.origin}/pedido/${o.code}`;
    const wa = `https://wa.me/55${phone.replace(/^55/, '')}?text=${encodeURIComponent(`Oi, ${o.customer_first_name}! Aqui é da Ditos Lanches. Acompanhe seu pedido #${o.number}: ${track}`)}`;
    const card = h('article', { class: 'order' + (isNew ? ' is-new' : ''), 'data-id': o.id },
      h('div', { class: 'order-head' }, h('b', {}, `#${String(o.number).padStart(4, '0')}`), h('span', {}, `${time(o.created_at)} · ${o.code}`)),
      h('div', { class: 'order-meta' },
        h('span', { class: 'chip chip-status' }, o.status_label),
        h('span', { class: 'chip' }, o.fulfillment === 'delivery' ? 'Entrega' : 'Retirada'),
        h('span', { class: 'chip ' + (o.paid ? 'chip-paid' : 'chip-unpaid') }, `${PAY[o.payment_method] || o.payment_method}${o.paid ? ' · pago' : ''}`)
      ),
      h('p', { class: 'order-who' }, h('b', {}, o.customer_name), ' · ', h('a', { href: `tel:${phone}` }, o.customer_phone), h('br'), addr,
        o.change_for_cents ? h('span', {}, h('br'), `Troco para ${money(o.change_for_cents)} (levar ${money(o.change_for_cents - o.total_cents)})`) : null),
      h('ul', { class: 'lines', role: 'list' }, o.items.map(it => h('li', { class: 'line' },
        h('div', { class: 'line-main' },
          h('span', { class: 'line-qty' }, `${it.qty}x`),
          h('span', { class: 'line-name' }, it.name,
            it.options.length ? h('small', {}, it.options.map(op => `${op.name}${op.qty > 1 ? ' ×' + op.qty : ''}`).join(', ')) : null,
            it.note ? h('small', {}, `Obs.: ${it.note}`) : null),
          h('span', { class: 'line-price' }, money(it.unit_cents * it.qty)))))),
      o.notes ? h('p', { class: 'order-notes' }, `Obs. do pedido: ${o.notes}`) : null,
      h('dl', { class: 'totals' },
        h('div', {}, h('dt', {}, 'Subtotal'), h('dd', {}, money(o.subtotal_cents))),
        h('div', {}, h('dt', {}, 'Entrega'), h('dd', {}, money(o.delivery_fee_cents))),
        h('div', { class: 'total' }, h('dt', {}, 'Total'), h('dd', {}, money(o.total_cents)))),
      h('div', { class: 'order-actions' },
        ...(NEXT[o.status] || []).filter(([, , only]) => !only || only === o.fulfillment)
          .map(([st, label]) => h('button', { class: 'btn btn-accent', type: 'button', onclick: () => setStatus(o.id, { status: st }) }, label)),
        !['entregue', 'cancelado'].includes(o.status) || !o.paid
          ? h('button', { class: 'btn btn-line', type: 'button', onclick: () => setStatus(o.id, { paid: !o.paid }) }, o.paid ? 'Desmarcar pago' : 'Marcar pago') : null,
        h('a', { class: 'btn btn-line', href: wa, target: '_blank', rel: 'noopener' }, 'WhatsApp'),
        h('button', { class: 'btn btn-line', type: 'button', onclick: e => printOrder(e.target.closest('.order')) }, 'Imprimir'),
        !['entregue', 'cancelado'].includes(o.status)
          ? h('button', { class: 'btn btn-line', type: 'button', onclick: () => { if (confirm(`Cancelar o pedido #${o.number}?`)) setStatus(o.id, { status: 'cancelado' }); } }, 'Cancelar') : null
      )
    );
    return card;
  }
  function printOrder(card) {
    card.classList.add('print');
    window.print();
    setTimeout(() => card.classList.remove('print'), 500);
  }
  async function setStatus(id, patch) {
    try { await api('PATCH', `/api/admin/orders/${id}`, patch); loadOrders(); }
    catch (e) { alert(e.message); }
  }

  async function loadOrders() {
    clearTimeout(pollTimer);
    const scope = $('input[name="scope"]:checked').value;
    try {
      const data = await api('GET', `/api/admin/orders?scope=${scope}`);
      const ids = new Set(data.orders.map(o => o.id));
      const fresh = known ? data.orders.filter(o => !known.has(o.id)) : [];
      if (fresh.length) { unseen += fresh.length; beep(); }
      if (known) data.orders.forEach(o => known.add(o.id)); else known = ids;
      const box = $('[data-orders]');
      box.replaceChildren(...data.orders.map(o => orderCard(o, fresh.some(f => f.id === o.id))));
      $('[data-orders-empty]').hidden = data.orders.length > 0;
      $('[data-stat-orders]').textContent = data.stats.orders;
      $('[data-stat-revenue]').textContent = money(data.stats.revenue);
      const pill = $('[data-store-pill]');
      pill.textContent = data.store.open ? 'Loja aberta' : 'Loja fechada';
      pill.classList.toggle('is-open', data.store.open);
      const badge = $('[data-new]');
      badge.hidden = !unseen;
      badge.textContent = unseen;
      document.title = unseen ? `(${unseen}) Novo pedido | Ditos` : 'Painel da cozinha | Ditos Lanches';
    } catch (e) { console.warn(e); }
    if (token) pollTimer = setTimeout(loadOrders, 6000);
  }
  $$('input[name="scope"]').forEach(r => r.addEventListener('change', loadOrders));
  document.addEventListener('visibilitychange', () => { if (!document.hidden) { unseen = 0; if (token) loadOrders(); } });
  document.addEventListener('pointerdown', () => { if (unseen) { unseen = 0; $('[data-new]').hidden = true; document.title = 'Painel da cozinha | Ditos Lanches'; } });

  // ------------------------------------------------------------ cardápio, bairros e loja
  async function loadCatalog() {
    const data = await api('GET', '/api/admin/catalog');
    renderProducts(data);
    renderHoods(data.neighborhoods);
    fillSettings(data.settings);
  }
  function saveBtn(onSave) {
    return h('button', { class: 'btn btn-ghost', type: 'button', onclick: async e => {
      const b = e.target;
      try { await onSave(); b.textContent = 'Salvo'; setTimeout(() => { b.textContent = 'Salvar'; }, 1500); }
      catch (ex) { alert(ex.message); }
    } }, 'Salvar');
  }
  function renderProducts({ categories, products, groups, options }) {
    const root = $('[data-catalog]');
    root.replaceChildren();
    for (const c of categories) {
      const items = products.filter(p => p.category_id === c.id);
      root.append(h('section', { class: 'cat-admin' }, h('h3', {}, c.name), items.map(p => {
        const price = h('input', { inputmode: 'decimal', value: (p.price_cents / 100).toFixed(2).replace('.', ','), 'aria-label': `Preço de ${p.name}` });
        const active = h('input', { type: 'checkbox', checked: !!p.active, 'aria-label': `${p.name} no ar` });
        const row = h('div', { class: 'row' + (p.active ? '' : ' is-off') },
          h('span', { class: 'row-name' }, p.name, h('small', {}, p.price_cents ? '' : 'Preço vem da opção escolhida')),
          price, h('label', { class: 'check' }, active, 'No ar'),
          saveBtn(async () => {
            await api('PUT', `/api/admin/products/${p.id}`, { ...p, price_cents: cents(price.value), active: active.checked });
            row.classList.toggle('is-off', !active.checked);
          }));
        return row;
      })));
    }
    root.append(h('section', { class: 'cat-admin' }, h('h3', {}, 'Opções e adicionais'), groups.flatMap(g => options.filter(o => o.group_id === g.id).map(o => {
      const price = h('input', { inputmode: 'decimal', value: (o.price_cents / 100).toFixed(2).replace('.', ','), 'aria-label': `Preço de ${o.title}` });
      const active = h('input', { type: 'checkbox', checked: !!o.active, 'aria-label': `${o.title} disponível` });
      const row = h('div', { class: 'row' + (o.active ? '' : ' is-off') },
        h('span', { class: 'row-name' }, o.title, h('small', {}, g.title)),
        price, h('label', { class: 'check' }, active, 'No ar'),
        saveBtn(async () => { await api('PUT', `/api/admin/options/${o.id}`, { title: o.title, price_cents: cents(price.value), active: active.checked }); row.classList.toggle('is-off', !active.checked); }));
      return row;
    }))));
  }
  function renderHoods(list) {
    const root = $('[data-hoods-admin]');
    root.replaceChildren(h('section', { class: 'cat-admin' }, list.map(n => {
      const fee = h('input', { inputmode: 'decimal', value: (n.fee_cents / 100).toFixed(2).replace('.', ','), 'aria-label': `Taxa de ${n.name}` });
      const eta = h('input', { value: n.eta, 'aria-label': `Tempo de ${n.name}` });
      const active = h('input', { type: 'checkbox', checked: !!n.active, 'aria-label': `Entregar em ${n.name}` });
      const row = h('div', { class: 'row' + (n.active ? '' : ' is-off') },
        h('span', { class: 'row-name' }, n.name, eta), fee, h('label', { class: 'check' }, active, 'Entrega'),
        saveBtn(async () => { await api('PUT', `/api/admin/neighborhoods/${n.id}`, { name: n.name, fee_cents: cents(fee.value), eta: eta.value, active: active.checked }); row.classList.toggle('is-off', !active.checked); }));
      return row;
    })));
  }
  $('[data-new-hood]').addEventListener('submit', async e => {
    e.preventDefault();
    const f = e.target;
    try {
      await api('POST', '/api/admin/neighborhoods', { name: f.name.value, fee_cents: cents(f.fee.value), eta: f.eta.value });
      f.reset();
      loadCatalog();
    } catch (ex) { alert(ex.message); }
  });
  function fillSettings(s) {
    const f = $('[data-settings]');
    for (const el of f.elements) {
      if (!el.name || !(el.name in s)) continue;
      if (el.type === 'checkbox') el.checked = s[el.name] !== '0';
      else if (el.type === 'radio') el.checked = el.value === s[el.name];
      else el.value = s[el.name];
    }
  }
  $('[data-settings]').addEventListener('submit', async e => {
    e.preventDefault();
    const f = e.target, body = {};
    for (const el of f.elements) {
      if (!el.name) continue;
      if (el.type === 'checkbox') body[el.name] = el.checked ? '1' : '0';
      else if (el.type === 'radio') { if (el.checked) body[el.name] = el.value; }
      else body[el.name] = el.name === 'min_order' ? String(cents(el.value) / 100) : el.value;
    }
    try {
      await api('PUT', '/api/admin/settings', body);
      const ok = $('[data-saved]'); ok.hidden = false; setTimeout(() => { ok.hidden = true; }, 2000);
      loadOrders();
    } catch (ex) { alert(ex.message); }
  });

  // ------------------------------------------------------------ partida
  function start() {
    $('[data-login]').hidden = true;
    $('[data-app]').hidden = false;
    known = null;
    loadOrders();
  }
  if (token) start();
})();
