// Ditos Lanches: cardápio, comanda (carrinho) e checkout.
// Lê o cardápio do banco (/api/menu). Sem servidor, usa a cópia estática em assets/data/menu.json
// e manda o pedido pelo WhatsApp ou pela página da Brendi, para o cliente nunca ficar sem saída.
(() => {
  'use strict';

  const BRL = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  const money = cents => BRL.format((cents || 0) / 100);
  const $ = (sel, root = document) => root.querySelector(sel);
  const FALLBACK_ORDER_URL = 'https://pedido.brendi.com.br/ditos-lanches-centro/';

  const store = { menu: null, live: false, byId: new Map(), groups: new Map() };
  const CART_KEY = 'ditos-comanda-v1';
  const CUSTOMER_KEY = 'ditos-cliente-v1';

  // ------------------------------------------------------------------ helpers
  function h(tag, attrs = {}, ...children) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === false || v == null) continue;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else if (k === 'dataset') Object.assign(el.dataset, v);
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const c of children.flat()) if (c != null && c !== false) el.append(c.nodeType ? c : document.createTextNode(c));
    return el;
  }
  const read = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } };
  const write = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch {} };

  // ------------------------------------------------------------------ carregamento
  async function loadMenu() {
    try {
      const res = await fetch('/api/menu', { headers: { accept: 'application/json' } });
      if (!res.ok) throw new Error(res.status);
      store.menu = await res.json();
      store.live = true;
    } catch {
      const res = await fetch('assets/data/menu.json');
      store.menu = await res.json();
      store.live = false;
      store.menu.store.open = true;
      store.menu.store.message = 'Pedidos pelo WhatsApp';
    }
    store.menu.products.forEach(p => store.byId.set(p.id, p));
    store.menu.groups.forEach(g => store.groups.set(g.id, g));
    document.dispatchEvent(new CustomEvent('ditos:menu', { detail: store.menu }));
  }

  // Preço de um item com as opções escolhidas.
  function unitPrice(product, options = []) {
    let total = product.price_cents;
    for (const o of options) {
      const opt = findOption(product, o.id);
      if (opt) total += opt.price_cents * (o.qty || 1);
    }
    return total;
  }
  function findOption(product, optionId) {
    for (const gid of product.groups) {
      const opt = store.groups.get(gid)?.options.find(o => o.id === optionId);
      if (opt) return opt;
    }
    return null;
  }
  function fromPrice(product) {
    if (product.price_cents > 0) return { label: '', cents: product.price_cents };
    const required = product.groups.map(g => store.groups.get(g)).find(g => g && g.min_choices > 0);
    const min = required ? Math.min(...required.options.map(o => o.price_cents)) : 0;
    return { label: 'a partir de', cents: min };
  }

  // ------------------------------------------------------------------ cardápio
  function renderMenu() {
    const { categories, products, store: info } = store.menu;
    const bar = $('[data-cat-bar]');
    const body = $('[data-menu]');
    if (!bar || !body) return;
    bar.replaceChildren();
    body.replaceChildren();

    categories.forEach((cat, i) => {
      const items = products.filter(p => p.category_id === cat.id);
      if (!items.length) return;
      bar.append(h('a', { class: 'cat-chip', href: `#cat-${cat.id}`, dataset: { cat: cat.id } }, cat.name));
      const section = h('section', { class: 'cat', id: `cat-${cat.id}`, 'aria-labelledby': `cat-${cat.id}-t` },
        h('header', { class: 'cat-head' },
          h('span', { class: 'cat-index', 'aria-hidden': 'true' }, String(i + 1).padStart(2, '0')),
          h('h3', { id: `cat-${cat.id}-t` }, cat.name),
          cat.blurb ? h('p', {}, cat.blurb) : null
        ),
        h('ul', { class: 'cards', role: 'list' }, items.map(renderCard))
      );
      body.append(section);
    });

    const status = $('[data-store-status]');
    if (status) {
      status.classList.toggle('is-open', !!info.open);
      status.querySelector('[data-status-text]').textContent = info.open
        ? `${info.message}. Pedido mínimo ${money(Math.round(Number(info.min_order || 0) * 100))}.`
        : info.message;
    }
    setupCategorySpy();
    document.dispatchEvent(new CustomEvent('ditos:menu-rendered'));
  }

  function renderCard(p) {
    const price = fromPrice(p);
    const img = p.image
      ? h('img', { src: p.image, alt: '', loading: 'lazy', decoding: 'async', width: 360, height: 360 })
      : h('span', { class: 'card-noimg', 'aria-hidden': 'true' }, p.name.slice(0, 1));
    return h('li', { class: 'card' },
      h('button', { class: 'card-btn', type: 'button', onclick: () => openProduct(p.id), 'aria-label': `${p.name}, ${price.label} ${money(price.cents)}. Abrir opções` },
        h('span', { class: 'card-img' }, img),
        h('span', { class: 'card-text' },
          h('span', { class: 'card-name' }, p.name),
          p.description ? h('span', { class: 'card-desc' }, p.description) : null,
          h('span', { class: 'card-foot' },
            h('span', { class: 'price' }, price.label ? h('small', {}, price.label + ' ') : null, money(price.cents)),
            h('span', { class: 'card-add', 'aria-hidden': 'true' }, '+')
          )
        )
      )
    );
  }

  function setupCategorySpy() {
    const chips = [...document.querySelectorAll('.cat-chip')];
    if (!('IntersectionObserver' in window) || !chips.length) return;
    let current = '';
    const io = new IntersectionObserver(entries => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        const id = e.target.id.replace('cat-', '');
        if (id === current) continue;
        current = id;
        chips.forEach(c => c.classList.toggle('is-active', c.dataset.cat === id));
        const chip = chips.find(c => c.dataset.cat === id);
        const track = chip?.parentElement;
        if (chip && track) track.scrollTo({ left: chip.offsetLeft - 16, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
      }
    }, { rootMargin: '-45% 0px -50% 0px' });
    document.querySelectorAll('.cat').forEach(s => io.observe(s));
  }

  // ------------------------------------------------------------------ folha do produto
  const sheet = () => $('#product-sheet');
  let lastFocus = null;

  function openLayer(el) {
    lastFocus = document.activeElement;
    el.hidden = false;
    document.documentElement.classList.add('has-layer');
    requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add('is-open')));
    const focusable = el.querySelector('[data-autofocus]') || el.querySelector('button, [href], input, select, textarea');
    setTimeout(() => focusable?.focus({ preventScroll: true }), 60);
  }
  function closeLayer(el) {
    if (!el || el.hidden) return;
    el.classList.remove('is-open');
    const done = () => {
      el.hidden = true;
      if (!document.querySelector('.layer.is-open')) document.documentElement.classList.remove('has-layer');
      lastFocus?.focus?.({ preventScroll: true });
    };
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) done();
    else setTimeout(done, 320);
  }

  function openProduct(id) {
    const p = store.byId.get(id);
    if (!p) return;
    const el = sheet();
    const state = { qty: 1, picks: new Map(), note: '' }; // picks: optionId -> qty
    const groups = p.groups.map(g => store.groups.get(g)).filter(Boolean);

    const addBtn = h('button', { class: 'btn btn-accent btn-block', type: 'button' });
    const hint = h('p', { class: 'sheet-hint', 'aria-live': 'polite' });
    const qtyOut = h('output', { class: 'qty-out', 'aria-live': 'polite' }, '1');

    function groupCount(g) {
      let n = 0;
      for (const o of g.options) if (state.picks.has(o.id)) n += g.type === 'qty' ? state.picks.get(o.id) : 1;
      return n;
    }
    function missing() {
      return groups.find(g => groupCount(g) < g.min_choices);
    }
    function refresh() {
      const options = [...state.picks].map(([oid, qty]) => ({ id: oid, qty }));
      const unit = unitPrice(p, options);
      const miss = missing();
      addBtn.disabled = !!miss || unit <= 0;
      addBtn.textContent = miss ? 'Escolha as opções' : `Adicionar  ${money(unit * state.qty)}`;
      hint.textContent = miss ? `Falta escolher: ${miss.title.toLowerCase()}.` : '';
      qtyOut.textContent = state.qty;
      el.querySelectorAll('[data-group]').forEach(box => {
        const g = store.groups.get(box.dataset.group);
        const count = groupCount(g);
        box.querySelector('.grp-count').textContent = g.type === 'one' ? '' : `${count}/${g.max_choices}`;
        box.classList.toggle('is-done', count >= g.min_choices && g.min_choices > 0);
        if (g.type === 'many') box.querySelectorAll('input').forEach(inp => { inp.disabled = !inp.checked && count >= g.max_choices; });
        if (g.type === 'qty') box.querySelectorAll('[data-plus]').forEach(b => {
          const o = g.options.find(x => x.id === Number(b.dataset.plus));
          b.disabled = count >= g.max_choices || (state.picks.get(o.id) || 0) >= (o.max_qty || g.max_choices);
        });
      });
    }

    const groupEls = groups.map(g => {
      const rule = g.type === 'one' ? (g.min_choices ? 'Escolha 1' : 'Opcional')
        : g.type === 'many' ? `Escolha ${g.min_choices === g.max_choices ? g.max_choices : `até ${g.max_choices}`}`
        : `Até ${g.max_choices}`;
      const box = h('fieldset', { class: 'grp', dataset: { group: g.id } },
        h('legend', {},
          h('span', { class: 'grp-title' }, g.title),
          h('span', { class: 'grp-rule' }, g.min_choices > 0 ? h('b', {}, 'Obrigatório') : null, rule),
          h('span', { class: 'grp-count', 'aria-hidden': 'true' })
        )
      );
      g.options.forEach(o => {
        const price = o.price_cents ? `+ ${money(o.price_cents)}` : '';
        if (g.type === 'qty') {
          const out = h('output', { class: 'step-out' }, '0');
          const set = n => {
            if (n <= 0) state.picks.delete(o.id); else state.picks.set(o.id, n);
            out.textContent = n;
            refresh();
          };
          box.append(h('div', { class: 'opt opt-qty' },
            h('span', { class: 'opt-name' }, o.title, price ? h('small', {}, price) : null),
            h('span', { class: 'stepper' },
              h('button', { type: 'button', class: 'step', 'aria-label': `Menos ${o.title}`, onclick: () => set((state.picks.get(o.id) || 0) - 1) }, '−'),
              out,
              h('button', { type: 'button', class: 'step', 'data-plus': o.id, 'aria-label': `Mais ${o.title}`, onclick: () => set((state.picks.get(o.id) || 0) + 1) }, '+')
            )
          ));
        } else {
          const input = h('input', { type: g.type === 'one' ? 'radio' : 'checkbox', name: `g-${g.id}`, value: o.id });
          input.addEventListener('change', () => {
            if (g.type === 'one') g.options.forEach(x => state.picks.delete(x.id));
            if (input.checked) state.picks.set(o.id, 1); else state.picks.delete(o.id);
            refresh();
          });
          box.append(h('label', { class: 'opt' }, input, h('span', { class: 'opt-mark', 'aria-hidden': 'true' }), h('span', { class: 'opt-name' }, o.title), price ? h('small', {}, price) : null));
        }
      });
      return box;
    });

    const note = h('textarea', { id: 'item-note', rows: 2, maxlength: 140, placeholder: 'Ex.: sem cebola, carne bem passada' });
    note.addEventListener('input', () => { state.note = note.value; });

    addBtn.addEventListener('click', () => {
      if (missing()) return;
      addToCart({ id: p.id, qty: state.qty, options: [...state.picks].map(([oid, qty]) => ({ id: oid, qty })), note: state.note.trim() });
      closeLayer(el);
      pulseFab();
    });

    const body = $('.sheet-body', el);
    body.replaceChildren(
      p.image ? h('figure', { class: 'sheet-img' }, h('img', { src: p.image, alt: p.name })) : null,
      h('div', { class: 'sheet-copy' },
        h('h3', { id: 'sheet-title' }, p.name),
        p.description ? h('p', { class: 'sheet-desc' }, p.description) : null,
        h('p', { class: 'price price-lg' }, fromPrice(p).label ? h('small', {}, fromPrice(p).label + ' ') : null, money(fromPrice(p).cents))
      ),
      ...groupEls,
      h('div', { class: 'field' }, h('label', { for: 'item-note' }, 'Alguma observação?'), note)
    );
    const foot = $('.sheet-foot', el);
    foot.replaceChildren(
      h('div', { class: 'stepper stepper-lg', role: 'group', 'aria-label': 'Quantidade' },
        h('button', { type: 'button', class: 'step', 'aria-label': 'Diminuir quantidade', onclick: () => { state.qty = Math.max(1, state.qty - 1); refresh(); } }, '−'),
        qtyOut,
        h('button', { type: 'button', class: 'step', 'aria-label': 'Aumentar quantidade', onclick: () => { state.qty = Math.min(30, state.qty + 1); refresh(); } }, '+')
      ),
      addBtn, hint
    );
    body.scrollTop = 0;
    refresh();
    openLayer(el);
  }

  // ------------------------------------------------------------------ comanda
  let cart = read(CART_KEY, []);
  const lineKey = l => `${l.id}|${l.options.map(o => `${o.id}x${o.qty}`).sort().join(',')}|${l.note}`;

  function addToCart(line) {
    const key = lineKey(line);
    const same = cart.find(l => lineKey(l) === key);
    if (same) same.qty = Math.min(30, same.qty + line.qty); else cart.push(line);
    saveCart();
  }
  function saveCart() {
    cart = cart.filter(l => store.byId.has(l.id) && l.qty > 0);
    write(CART_KEY, cart);
    renderCart();
  }
  const cartSubtotal = () => cart.reduce((sum, l) => sum + unitPrice(store.byId.get(l.id), l.options) * l.qty, 0);
  const cartCount = () => cart.reduce((n, l) => n + l.qty, 0);

  function pulseFab() {
    const fab = $('.fab');
    if (!fab) return;
    fab.classList.remove('is-pulse');
    void fab.offsetWidth;
    fab.classList.add('is-pulse');
  }

  function renderCart() {
    const fab = $('.fab');
    const count = cartCount();
    if (fab) {
      fab.hidden = count === 0;
      $('[data-cart-count]', fab).textContent = count;
      $('[data-cart-total]', fab).textContent = money(cartSubtotal());
    }
    document.querySelectorAll('[data-cart-badge]').forEach(b => { b.textContent = count || ''; b.hidden = !count; });
    const list = $('[data-cart-lines]');
    if (!list) return;
    list.replaceChildren();
    if (!cart.length) {
      list.append(h('li', { class: 'line-empty' }, 'Sua comanda está vazia. Escolha um lanche no cardápio.'));
    }
    cart.forEach((l, i) => {
      const p = store.byId.get(l.id);
      const unit = unitPrice(p, l.options);
      const opts = l.options.map(o => { const opt = findOption(p, o.id); return opt ? `${opt.title}${o.qty > 1 ? ' ×' + o.qty : ''}` : ''; }).filter(Boolean);
      list.append(h('li', { class: 'line' },
        h('div', { class: 'line-main' },
          h('span', { class: 'line-qty' }, `${l.qty}x`),
          h('span', { class: 'line-name' }, p.name,
            opts.length ? h('small', {}, opts.join(', ')) : null,
            l.note ? h('small', { class: 'line-note' }, `Obs.: ${l.note}`) : null),
          h('span', { class: 'line-price' }, money(unit * l.qty))
        ),
        h('div', { class: 'line-actions' },
          h('button', { type: 'button', class: 'step', 'aria-label': `Menos ${p.name}`, onclick: () => { l.qty -= 1; if (l.qty <= 0) cart.splice(i, 1); saveCart(); } }, '−'),
          h('button', { type: 'button', class: 'step', 'aria-label': `Mais ${p.name}`, onclick: () => { l.qty = Math.min(30, l.qty + 1); saveCart(); } }, '+'),
          h('button', { type: 'button', class: 'link-btn', onclick: () => { cart.splice(i, 1); saveCart(); } }, 'Remover')
        )
      ));
    });
    updateTotals();
  }

  // ------------------------------------------------------------------ checkout
  const drawer = () => $('#comanda');
  const form = () => $('#checkout');

  function feeCents() {
    const f = form();
    if (!f || f.fulfillment.value !== 'delivery') return 0;
    const nb = store.menu.neighborhoods.find(n => String(n.id) === f.neighborhood.value);
    return nb ? nb.fee_cents : 0;
  }
  function updateTotals() {
    const sub = cartSubtotal();
    const fee = feeCents();
    const f = form();
    const delivery = f && f.fulfillment.value === 'delivery';
    const set = (sel, text) => document.querySelectorAll(sel).forEach(el => { el.textContent = text; });
    set('[data-sub]', money(sub));
    set('[data-fee]', delivery ? (f.neighborhood.value ? money(fee) : 'escolha o bairro') : 'grátis, retirada');
    set('[data-total]', money(sub + fee));
    const min = Math.round(Number(store.menu?.store.min_order || 0) * 100);
    const minNote = $('[data-min-note]');
    if (minNote) {
      minNote.hidden = !cart.length || sub >= min;
      minNote.textContent = `Pedido mínimo de ${money(min)}. Faltam ${money(min - sub)}.`;
    }
    const go = $('[data-go-checkout]');
    if (go) go.disabled = !cart.length || sub < min;
    const submit = $('[data-submit]');
    if (submit) submit.textContent = store.live ? `Mandar pra chapa  ${money(sub + fee)}` : 'Enviar pedido pelo WhatsApp';
  }

  function setStep(step) {
    const d = drawer();
    d.dataset.step = step;
    $('[data-step-cart]', d).hidden = step !== 'cart';
    $('[data-step-checkout]', d).hidden = step !== 'checkout';
    $('.drawer-scroll', d).scrollTop = 0;
    const title = $('#comanda-title', d);
    title.textContent = step === 'cart' ? 'Sua comanda' : 'Fechar pedido';
    setTimeout(() => (step === 'checkout' ? form().elements.name : $('[data-close-cart]', d))?.focus({ preventScroll: true }), 60);
  }

  function fillCheckout() {
    const f = form();
    const { neighborhoods, store: info } = store.menu;
    const select = f.neighborhood;
    select.replaceChildren(h('option', { value: '' }, 'Escolha o bairro'),
      ...neighborhoods.map(n => h('option', { value: n.id }, `${n.name}  ·  ${money(n.fee_cents)}  ·  ${n.eta}`)));
    const pay = $('[data-payments]', f);
    pay.replaceChildren(...info.payments.map((p, i) =>
      h('label', { class: 'pay' },
        h('input', { type: 'radio', name: 'payment', value: p.id, required: true, checked: i === 0 && info.payments.length === 1 }),
        h('span', { class: 'pay-mark', 'aria-hidden': 'true' }),
        h('span', {}, p.label))));
    f.querySelector('[data-pickup]').hidden = info.pickup_enabled === '0';
    f.querySelector('[data-delivery]').hidden = info.delivery_enabled === '0';
    if (info.delivery_enabled === '0') f.fulfillment.value = 'pickup';
    const saved = read(CUSTOMER_KEY, {});
    for (const k of ['name', 'phone', 'street', 'number', 'complement', 'reference']) if (saved[k] && !f.elements[k].value) f.elements[k].value = saved[k];
    if (saved.neighborhood && neighborhoods.some(n => String(n.id) === saved.neighborhood)) select.value = saved.neighborhood;
    syncFulfillment();
  }

  function syncFulfillment() {
    const f = form();
    const delivery = f.fulfillment.value === 'delivery';
    $('[data-address]', f).hidden = !delivery;
    ['neighborhood', 'street', 'number'].forEach(n => { f.elements[n].required = delivery; });
    const info = store.menu.store;
    $('[data-eta]', f).textContent = delivery ? `Entrega em ${f.neighborhood.value ? store.menu.neighborhoods.find(n => String(n.id) === f.neighborhood.value)?.eta : info.avg_prep}.` : `Retirada no balcão em ${info.pickup_eta || '15 a 25 min'}. ${info.address}.`;
    const cash = f.payment?.value === 'dinheiro';
    $('[data-change]', f).hidden = !cash;
    updateTotals();
  }

  function showError(message) {
    const box = $('[data-error]');
    box.textContent = message;
    box.hidden = !message;
    if (message) box.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  function orderPayload() {
    const f = form();
    return {
      name: f.elements.name.value.trim(),
      phone: f.elements.phone.value.trim(),
      fulfillment: f.fulfillment.value,
      address: {
        neighborhood_id: Number(f.neighborhood.value) || null,
        street: f.elements.street.value.trim(),
        number: f.elements.number.value.trim(),
        complement: f.elements.complement.value.trim(),
        reference: f.elements.reference.value.trim()
      },
      payment: f.payment.value,
      change_for: f.elements.change_for.value.replace(',', '.'),
      notes: f.elements.notes.value.trim(),
      items: cart.map(l => ({ id: l.id, qty: l.qty, options: l.options, note: l.note }))
    };
  }

  function whatsappText(order) {
    const lines = [`*Pedido Ditos Lanches*`, ''];
    cart.forEach(l => {
      const p = store.byId.get(l.id);
      const opts = l.options.map(o => { const t = findOption(p, o.id)?.title; return t ? `${t}${o.qty > 1 ? ' ×' + o.qty : ''}` : ''; }).filter(Boolean);
      lines.push(`${l.qty}x ${p.name}${opts.length ? ` (${opts.join(', ')})` : ''}${l.note ? ` Obs.: ${l.note}` : ''}  ${money(unitPrice(p, l.options) * l.qty)}`);
    });
    const nb = store.menu.neighborhoods.find(n => n.id === order.address.neighborhood_id);
    lines.push('', `Subtotal: ${money(cartSubtotal())}`);
    if (order.fulfillment === 'delivery') {
      lines.push(`Entrega (${nb?.name || ''}): ${money(nb?.fee_cents || 0)}`, `Total: ${money(cartSubtotal() + (nb?.fee_cents || 0))}`, '',
        `Endereço: ${order.address.street}, ${order.address.number}${order.address.complement ? ', ' + order.address.complement : ''}, ${nb?.name || ''}`,
        order.address.reference ? `Referência: ${order.address.reference}` : '');
    } else lines.push(`Total: ${money(cartSubtotal())}`, '', 'Vou retirar no balcão.');
    lines.push(`Pagamento: ${store.menu.store.payments.find(p => p.id === order.payment)?.label || order.payment}`, `Nome: ${order.name}`, `Telefone: ${order.phone}`);
    if (order.notes) lines.push(`Obs.: ${order.notes}`);
    return lines.filter(l => l !== '').join('\n');
  }

  async function submitOrder(e) {
    e.preventDefault();
    const f = form();
    showError('');
    if (!f.reportValidity()) return;
    const order = orderPayload();
    write(CUSTOMER_KEY, { name: order.name, phone: order.phone, street: order.address.street, number: order.address.number, complement: order.address.complement, reference: order.address.reference, neighborhood: f.neighborhood.value });

    if (!store.live) {
      const wa = String(store.menu.store.whatsapp || '').replace(/\D/g, '');
      window.open(wa ? `https://wa.me/${wa.startsWith('55') ? wa : '55' + wa}?text=${encodeURIComponent(whatsappText(order))}` : FALLBACK_ORDER_URL, '_blank', 'noopener');
      return;
    }
    const btn = $('[data-submit]');
    btn.disabled = true;
    btn.classList.add('is-busy');
    btn.textContent = 'Mandando pra chapa...';
    try {
      const res = await fetch('/api/orders', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(order) });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Não deu para enviar agora. Tente de novo.');
      write('ditos-ultimo-pedido', { code: data.code, at: Date.now() });
      cart = [];
      write(CART_KEY, cart);
      location.href = `/pedido/${data.code}`;
    } catch (err) {
      showError(err.message);
      btn.disabled = false;
      btn.classList.remove('is-busy');
      updateTotals();
    }
  }

  // ------------------------------------------------------------------ ligações
  function wire() {
    document.addEventListener('click', e => {
      const t = e.target.closest('[data-open-cart], [data-close-cart], [data-close-sheet], [data-go-checkout], [data-back-cart], [data-jump-cat]');
      if (!t) return;
      if (t.matches('[data-open-cart]')) { setStep('cart'); openLayer(drawer()); }
      else if (t.matches('[data-close-cart]')) closeLayer(drawer());
      else if (t.matches('[data-close-sheet]')) closeLayer(sheet());
      else if (t.matches('[data-go-checkout]')) setStep('checkout');
      else if (t.matches('[data-back-cart]')) setStep('cart');
      else if (t.matches('[data-jump-cat]')) {
        const target = document.getElementById(`cat-${t.dataset.jumpCat}`);
        if (target) { e.preventDefault(); target.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }); }
      }
    });
    document.addEventListener('keydown', e => {
      if (e.key !== 'Escape') return;
      const open = [...document.querySelectorAll('.layer.is-open')].pop();
      if (open) closeLayer(open);
    });
    document.querySelectorAll('.layer').forEach(layer => {
      layer.addEventListener('click', e => { if (e.target === layer) closeLayer(layer); });
      layer.addEventListener('keydown', e => { // prende o foco dentro da camada aberta
        if (e.key !== 'Tab') return;
        const items = [...layer.querySelectorAll('button:not([disabled]), [href], input:not([disabled]), select, textarea')].filter(el => el.offsetParent !== null);
        if (!items.length) return;
        const first = items[0], last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      });
    });
    const f = form();
    f.addEventListener('change', e => { if (['fulfillment', 'neighborhood', 'payment'].includes(e.target.name)) syncFulfillment(); });
    f.addEventListener('submit', submitOrder);
    f.elements.phone.addEventListener('input', e => {
      const d = e.target.value.replace(/\D/g, '').slice(0, 11);
      e.target.value = d.length > 6 ? `(${d.slice(0, 2)}) ${d.slice(2, d.length - 4)}-${d.slice(-4)}` : d.length > 2 ? `(${d.slice(0, 2)}) ${d.slice(2)}` : d;
    });

    const last = read('ditos-ultimo-pedido', null);
    const track = $('[data-last-order]');
    if (track && last && Date.now() - last.at < 12 * 3600e3) { track.href = `/pedido/${last.code}`; track.hidden = false; }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    if (!$('[data-menu]')) return;
    wire();
    try {
      await loadMenu();
      renderMenu();
      fillCheckout();
      renderCart();
      if (!store.menu.store.open) {
        const submit = $('[data-submit]');
        submit.disabled = true;
        $('[data-closed-note]').hidden = false;
        $('[data-closed-note]').textContent = store.menu.store.message;
      }
    } catch (err) {
      console.error(err);
      $('[data-menu]').append(h('p', { class: 'menu-error' }, 'Não conseguimos carregar o cardápio agora. ', h('a', { href: FALLBACK_ORDER_URL }, 'Peça pela nossa página na Brendi.')));
    }
  });

  window.DitosStore = { openProduct, store };
})();
