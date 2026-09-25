// Acompanhamento do pedido: consulta o status a cada poucos segundos e mostra o Pix quando for o caso.
(() => {
  'use strict';
  const $ = s => document.querySelector(s);
  const money = c => (c / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  const time = iso => new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  const code = (location.pathname.match(/\/pedido\/([A-Za-z0-9]+)/) || [])[1] || new URLSearchParams(location.search).get('c');

  const COPY = {
    recebido: ['Pedido recebido.', 'A cozinha já está com ele. Daqui a pouco vai pra chapa.'],
    na_chapa: ['Seu lanche está na chapa.', 'Carne selando, pão tostando. Falta pouco.'],
    saiu: ['Saiu pra entrega.', 'Sacola fechada, motoboy na rua. Fica de olho no interfone.'],
    pronto: ['Pronto pra retirar.', 'Pode vir buscar no balcão. Está quentinho esperando você.'],
    entregue: ['Entregue. Bom apetite!', 'Obrigado por pedir na Ditos.'],
    cancelado: ['Pedido cancelado.', 'Se foi engano, fale com a gente que a gente resolve.']
  };

  function steps(order) {
    const last = order.fulfillment === 'pickup'
      ? [['pronto', 'Pronto pra retirar'], ['entregue', 'Retirado']]
      : [['saiu', 'Saiu pra entrega'], ['entregue', 'Entregue']];
    return [['recebido', 'Recebido'], ['na_chapa', 'Na chapa'], ...last];
  }

  let lastStatus = null, qrDone = false, timer = null;

  function render(o) {
    const [head, sub] = COPY[o.status] || COPY.recebido;
    $('[data-headline]').textContent = head;
    $('[data-subline]').textContent = sub;
    document.title = `${head} | Pedido #${o.number} | Ditos Lanches`;
    $('[data-number]').textContent = `Pedido #${String(o.number).padStart(4, '0')}`;
    $('[data-code]').textContent = `Código ${o.code} · ${new Date(o.created_at).toLocaleDateString('pt-BR')} ${time(o.created_at)}`;

    const stamp = $('[data-stamp]');
    if (o.status !== lastStatus) {
      stamp.hidden = false;
      stamp.className = 'stamp' + (o.status === 'entregue' ? ' is-ok' : o.status === 'cancelado' ? ' is-off' : '');
      stamp.textContent = o.status_label;
      stamp.style.animation = 'none'; void stamp.offsetWidth; stamp.style.animation = '';
      lastStatus = o.status;
    }

    const list = steps(o);
    const reached = new Map(o.history.map(h => [h.status, h.at]));
    const currentIndex = list.findIndex(([k]) => k === o.status);
    const prog = $('[data-progress]');
    prog.replaceChildren(...list.map(([k, label], i) => {
      const li = document.createElement('li');
      const done = o.status !== 'cancelado' && (i < currentIndex || (i === currentIndex && k === 'entregue'));
      const now = o.status !== 'cancelado' && i === currentIndex && k !== 'entregue';
      if (done) li.classList.add('is-done');
      if (now) li.classList.add('is-now');
      const dot = document.createElement('span'); dot.className = 'pdot'; dot.textContent = done ? '✓' : String(i + 1);
      const b = document.createElement('b'); b.textContent = label;
      const small = document.createElement('small'); small.textContent = reached.has(k) ? time(reached.get(k)) : '';
      li.append(dot, b, small);
      if (now) li.setAttribute('aria-current', 'step');
      return li;
    }));

    $('[data-lines]').replaceChildren(...o.items.map(it => {
      const li = document.createElement('li'); li.className = 'line';
      const main = document.createElement('div'); main.className = 'line-main';
      const q = document.createElement('span'); q.className = 'line-qty'; q.textContent = `${it.qty}x`;
      const n = document.createElement('span'); n.className = 'line-name'; n.textContent = it.name;
      const opts = it.options.map(op => `${op.name}${op.qty > 1 ? ' ×' + op.qty : ''}`);
      if (opts.length) { const s = document.createElement('small'); s.textContent = opts.join(', '); n.append(s); }
      if (it.note) { const s = document.createElement('small'); s.textContent = `Obs.: ${it.note}`; n.append(s); }
      const p = document.createElement('span'); p.className = 'line-price'; p.textContent = money(it.unit_cents * it.qty);
      main.append(q, n, p); li.append(main);
      return li;
    }));

    const rows = [['Subtotal', money(o.subtotal_cents)]];
    rows.push(o.fulfillment === 'delivery' ? [`Entrega · ${o.neighborhood}`, money(o.delivery_fee_cents)] : ['Retirada no balcão', 'grátis']);
    const totals = $('[data-totals]');
    totals.replaceChildren(...rows.map(([a, b]) => { const d = document.createElement('div'); const dt = document.createElement('dt'); dt.textContent = a; const dd = document.createElement('dd'); dd.textContent = b; d.append(dt, dd); return d; }));
    const tot = document.createElement('div'); tot.className = 'total';
    const dt = document.createElement('dt'); dt.textContent = 'Total'; const dd = document.createElement('dd'); dd.textContent = money(o.total_cents);
    tot.append(dt, dd); totals.append(tot);
    $('[data-pay]').textContent = `Pagamento: ${o.payment_label}${o.paid ? ' · pago' : ''}`;

    const pix = $('[data-pix]');
    pix.hidden = !o.pix;
    $('[data-paid]').hidden = !(o.payment_method === 'pix' && o.paid);
    if (o.pix) {
      $('[data-pix-code]').value = o.pix;
      $('[data-pix-total]').textContent = `Valor: ${money(o.total_cents)}`;
      if (!qrDone && window.qrcode) {
        const qr = window.qrcode(0, 'M');
        qr.addData(o.pix);
        qr.make();
        $('[data-qr]').innerHTML = qr.createSvgTag({ cellSize: 4, margin: 0, scalable: true });
        qrDone = true;
      }
    }

    const wa = String(o.whatsapp || '').replace(/\D/g, '');
    const whats = $('[data-whats]');
    if (wa) {
      whats.hidden = false;
      whats.href = `https://wa.me/${wa.startsWith('55') ? wa : '55' + wa}?text=${encodeURIComponent(`Oi! Sobre o pedido #${o.number} (${o.code})`)}`;
    }
    $('[data-updated]').textContent = ['entregue', 'cancelado'].includes(o.status) ? 'Pedido finalizado' : `Acompanhando ao vivo · atualizado ${time(new Date().toISOString())}`;
  }

  async function load() {
    try {
      const res = await fetch(`/api/orders/${encodeURIComponent(code || '')}`, { cache: 'no-store' });
      if (res.status === 404) throw new Error('404');
      if (!res.ok) throw new Error('net');
      const order = await res.json();
      render(order);
      if (['entregue', 'cancelado'].includes(order.status)) return;
    } catch (err) {
      if (err.message === '404') {
        $('[data-headline]').textContent = 'Não achamos esse pedido.';
        $('[data-subline]').textContent = 'Confira o link ou fale com a gente pelo Instagram.';
        return;
      }
      $('[data-updated]').textContent = 'Sem conexão. Tentando de novo...';
    }
    timer = setTimeout(load, document.hidden ? 20000 : 8000);
  }

  $('[data-copy]').addEventListener('click', async e => {
    const text = $('[data-pix-code]').value;
    try { await navigator.clipboard.writeText(text); }
    catch { const t = $('[data-pix-code]'); t.select(); document.execCommand('copy'); }
    e.target.textContent = 'Código copiado!';
    setTimeout(() => { e.target.textContent = 'Copiar código Pix'; }, 2400);
  });
  document.addEventListener('visibilitychange', () => { if (!document.hidden && timer) { clearTimeout(timer); load(); } });
  document.addEventListener('DOMContentLoaded', load);
})();
