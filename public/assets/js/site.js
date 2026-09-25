// Ditos Lanches: o vídeo que anda com a rolagem, a faixa de banners, o "segure para selar"
// e as entradas da página. Tudo em transform e opacity, tudo pausa quando ninguém está olhando.
(() => {
  'use strict';

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  const smoothstep = (p, e0, e1) => { const t = clamp((p - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t); };
  const reduceMQ = matchMedia('(prefers-reduced-motion: reduce)');

  // ================================================================ herói
  const hero = $('.hero');
  const stage = $('[data-stage]');
  const video = $('[data-video]');
  const posterLayer = $('[data-poster]');
  const loader = $('[data-loader]');
  const bands = $$('[data-band]').map(el => {
    const [a, b] = el.dataset.range.split(',').map(Number);
    return { el, a, b, ramp: Number(el.dataset.ramp) || 0, op: -1, k: -1, live: null };
  });

  // WebM (VP9) é 3x mais leve e roda em Chrome, Edge, Firefox e Android; Safari fica com o MP4 (H.264).
  const appleOnly = /^((?!chrome|android|crios|fxios|edg).)*safari/i.test(navigator.userAgent);
  const useWebm = !appleOnly && video.canPlayType('video/webm; codecs="vp9"') !== '';
  // Tela em pé (celular): vídeo vertical recortado no lanche, bem mais leve.
  const portrait = matchMedia('(max-aspect-ratio: 4/5)').matches;
  const VIDEO_URL = `assets/video/hero-scrub${portrait ? '-m' : ''}.${useWebm ? 'webm' : 'mp4'}`;
  const VIDEO_BYTES = portrait ? (useWebm ? 774272 : 1425160) : (useWebm ? 2189989 : 6843617);
  const POSTER_URL = portrait ? 'assets/img/hero-poster-m.jpg' : 'assets/img/hero-poster.jpg';

  // Divide os títulos em palavras (e cópias suave/nítida para o "clarear"), uma vez, com sorteio fixo.
  function rng(seed) { let s = seed >>> 0; return () => (s = (s * 1664525 + 1013904223) >>> 0) / 4294967296; }
  bands.forEach((band, bi) => {
    const title = $('[data-split]', band.el);
    if (!title) return;
    const text = title.textContent.trim();
    const entrance = band.el.dataset.entrance;
    const rand = rng(2002 + bi * 97);
    title.textContent = '';
    title.append(Object.assign(document.createElement('span'), { className: 'visually-hidden', textContent: text }));
    if (entrance === 'clear') {
      for (const cls of ['soft', 'sharp']) {
        const s = document.createElement('span');
        s.className = cls;
        s.setAttribute('aria-hidden', 'true');
        s.textContent = text;
        title.append(s);
      }
      return;
    }
    const visual = document.createElement('span');
    visual.className = 'split';
    visual.setAttribute('aria-hidden', 'true');
    const words = text.split(' ');
    words.forEach((word, i) => {
      const w = document.createElement('span');
      w.className = 'w' + (entrance === 'punch' && /quente/i.test(word) ? ' em' : '');
      const spread = entrance === 'settle' ? 0.5 : 0.42;
      w.style.setProperty('--th', (i / words.length * spread + rand() * 0.05).toFixed(3));
      w.textContent = word;
      visual.append(w, i < words.length - 1 ? ' ' : '');
    });
    title.append(visual);
  });

  const heroProgress = () => {
    const range = hero.offsetHeight - innerHeight;
    return range > 0 ? clamp(-hero.getBoundingClientRect().top / range, 0, 1) : 0;
  };

  // Faixas de legenda: opacidade em rampas suaves, montagem (--k) nos primeiros ~20vh da faixa.
  let loadK = 0;
  function updateCaptions(p) {
    const last = bands.length - 1;
    bands.forEach((band, i) => {
      const { a, b } = band;
      const f = Math.min(0.035, (b - a) / 3);
      const inE = i === 0 ? 1 : smoothstep(p, a, a + f);
      const outE = i === last ? 0 : smoothstep(p, b - f, b);
      const op = Math.round(inE * (1 - outE) * 1000) / 1000;
      const ramp = band.ramp || Math.min(0.05, (b - a) * 0.35);
      let k = clamp((p - a) / ramp, 0, 1);
      if (i === 0) k = Math.max(k, loadK);
      if (op !== band.op) {
        band.op = op;
        band.el.style.opacity = op;
        const live = op > 0.5;
        if (live !== band.live) { band.live = live; band.el.classList.toggle('is-live', live); }
      }
      if (Math.abs(k - band.k) > 0.008 || (k === 1 && band.k !== 1) || (k === 0 && band.k !== 0)) {
        band.k = k;
        band.el.style.setProperty('--k', k.toFixed(3));
      }
    });
  }

  // Seeks com trava: nunca dois ao mesmo tempo, sempre o mais novo.
  let seekBusy = false, pendingTime = null;
  function requestSeek(t) {
    if (!video.duration || !isFinite(video.duration)) return;
    t = clamp(t, 0, video.duration - 0.04);
    if (seekBusy) { pendingTime = t; return; }
    if (Math.abs(video.currentTime - t) < 0.01) return;
    seekBusy = true;
    video.currentTime = t;
  }
  video.addEventListener('seeked', () => {
    seekBusy = false;
    if (pendingTime !== null) { const t = pendingTime; pendingTime = null; requestSeek(t); }
  });
  video.addEventListener('error', () => { seekBusy = false; pendingTime = null; failVideo(); });

  // Laço que descansa: suaviza o tempo mostrado e para quando converge ou quando o herói sai da tela.
  let target = 0, shown = 0, rafId = null, lastTick = 0, heroOnScreen = true, scrolledFlag = false;
  function tick(now) {
    const dt = Math.min(100, now - (lastTick || now));
    lastTick = now;
    shown += (target - shown) * (1 - Math.pow(1 - 0.16, dt / 16.667));
    if (Math.abs(target - shown) < 0.0005) { shown = target; rafId = null; lastTick = 0; }
    else rafId = requestAnimationFrame(tick);
    requestSeek(shown * (video.duration || 0));
    updateCaptions(shown);
  }
  function onScroll() {
    target = heroProgress();
    const scrolled = target > 0.015;
    if (scrolled !== scrolledFlag) { scrolledFlag = scrolled; stage.classList.toggle('is-scrolled', scrolled); }
    if (rafId === null && heroOnScreen) rafId = requestAnimationFrame(tick);
  }
  new IntersectionObserver(([e]) => {
    heroOnScreen = e.isIntersecting;
    if (heroOnScreen && scrubOn) onScroll();
  }).observe(hero);

  // Carrega o vídeo como Blob (funciona mesmo em hospedagem sem Range), com anel de progresso honesto.
  let heroStarted = false;
  function initHeroOnce() {
    if (heroStarted) return;
    heroStarted = true;
    posterLayer.style.backgroundImage = `url('${POSTER_URL}')`;
    let started = false;
    const startBlob = () => { if (started) return; started = true; loadHeroBlob().catch(failVideo); };
    const img = new Image();
    img.onload = startBlob;
    img.onerror = startBlob;
    img.src = POSTER_URL;
    setTimeout(startBlob, 4000);
  }
  async function loadHeroBlob() {
    const ring = $('.ring', loader);
    const ctrl = new AbortController();
    let watchdog = setTimeout(() => ctrl.abort(), 20000);
    const res = await fetch(VIDEO_URL, { priority: 'low', signal: ctrl.signal });
    if (!res.ok || !res.body) throw new Error('video ' + res.status);
    const total = Number(res.headers.get('Content-Length')) || VIDEO_BYTES;
    const reader = res.body.getReader();
    const chunks = [];
    let got = 0, lastRing = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      clearTimeout(watchdog);
      watchdog = setTimeout(() => ctrl.abort(), 20000);
      chunks.push(value);
      got += value.length;
      const frac = Math.min(1, got / total);
      const now = performance.now();
      if (now - lastRing > 100 || frac === 1) { lastRing = now; ring.style.setProperty('--ld', Math.round(126 * (1 - frac))); }
    }
    clearTimeout(watchdog);
    ring.style.setProperty('--ld', 0);
    video.src = URL.createObjectURL(new Blob(chunks, { type: useWebm ? 'video/webm' : 'video/mp4' }));
    video.load();
    video.addEventListener('loadeddata', () => {
      requestSeek(heroProgress() * video.duration);
      stage.classList.add('video-ready');
      ring.replaceWith(chevron());
    }, { once: true });
  }
  function chevron() {
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('class', 'chevron');
    svg.innerHTML = '<path d="M5 9l7 7 7-7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>';
    return svg;
  }
  function failVideo() {
    const ring = $('.ring', loader);
    if (ring) ring.replaceWith(chevron());
    stage.classList.add('video-failed');
  }

  // Herói estático só com movimento reduzido (igual ao site.css), decidido ao vivo.
  const GATES = ['(prefers-reduced-motion: reduce)'];
  let scrubOn = false;
  function enableScrub() {
    if (scrubOn) return;
    scrubOn = true;
    initHeroOnce();
    addEventListener('scroll', onScroll, { passive: true });
    addEventListener('resize', onScroll, { passive: true });
    bands.forEach(b => { b.op = -1; b.k = -1; b.live = null; });
    unpinFinalStates();
    const start = performance.now();
    const ramp = now => { loadK = clamp((now - start) / 1100, 0, 1); loadK = 1 - Math.pow(1 - loadK, 3); updateCaptions(shown); if (loadK < 1 && scrubOn) requestAnimationFrame(ramp); };
    if (loadK < 1) requestAnimationFrame(ramp);
    updateCaptions(heroProgress());
    onScroll();
  }
  function disableScrub() {
    if (!scrubOn) return;
    scrubOn = false;
    removeEventListener('scroll', onScroll);
    removeEventListener('resize', onScroll);
    if (rafId !== null) { cancelAnimationFrame(rafId); rafId = null; }
  }
  function applyHeroMode() {
    if (GATES.some(q => matchMedia(q).matches)) disableScrub(); else enableScrub();
  }
  const MQLS = GATES.map(q => matchMedia(q));
  MQLS.forEach(m => m.addEventListener('change', applyHeroMode));

  // ================================================================ navegação
  const nav = $('[data-nav]');
  let navSolid = null;
  function updateNav() {
    const threshold = scrubOn ? hero.offsetHeight - innerHeight * 1.05 : 40;
    const solid = scrollY > threshold;
    if (solid !== navSolid) { navSolid = solid; nav.classList.toggle('is-solid', solid); }
  }

  // ================================================================ linhas de calor que se desenham
  const lines = $$('[data-draw]').map(el => ({ el, v: -1 }));
  function updateLines() {
    for (const l of lines) {
      const r = l.el.getBoundingClientRect();
      const v = Math.round(clamp((innerHeight - r.top) / (innerHeight * 0.7), 0, 1) * 100) / 100;
      if (v !== l.v) { l.v = v; l.el.style.setProperty('--draw', v); }
    }
  }

  let pageTick = null;
  addEventListener('scroll', () => {
    if (pageTick) return;
    pageTick = requestAnimationFrame(() => { pageTick = null; updateNav(); if (!reduceMQ.matches) updateLines(); });
  }, { passive: true });

  // ================================================================ entradas
  const revealIO = new IntersectionObserver(entries => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      e.target.classList.add('in');
      revealIO.unobserve(e.target);
      if (e.target.matches('[data-steps]')) setTimeout(() => e.target.classList.add('settled'), 1200);
    }
  }, { rootMargin: '0px 0px -12% 0px', threshold: 0.08 });
  $$('.reveal, [data-steps]').forEach(el => revealIO.observe(el));
  document.addEventListener('ditos:menu-rendered', () => $$('.cards').forEach(el => revealIO.observe(el)));

  // ================================================================ faixa de banners rolando para a direita
  const marquee = $('[data-marquee]');
  const track = $('[data-marquee-track]');
  const saveData = navigator.connection && navigator.connection.saveData;
  let setWidth = 0, x = 0, mqRaf = null, mqLast = 0, mqVisible = false, mqHover = false;

  // Duplica os banners até cobrir telas bem largas; as cópias ficam fora do leitor de tela e do Tab.
  const originals = $$('[data-deal]', track);
  function buildClones() {
    $$('[data-clone]', track).forEach(c => c.remove());
    setWidth = track.scrollWidth + parseFloat(getComputedStyle(marquee).getPropertyValue('--gap') || 22);
    let copies = Math.max(1, Math.ceil((innerWidth * 2) / setWidth));
    for (let i = 0; i < copies; i++) {
      originals.forEach(o => {
        const c = o.cloneNode(true);
        c.dataset.clone = '';
        c.setAttribute('aria-hidden', 'true');
        c.inert = true;
        $$('a, button', c).forEach(b => b.setAttribute('tabindex', '-1'));
        track.append(c);
      });
    }
    x = -setWidth;
    track.style.transform = `translate3d(${x}px,0,0)`;
    observeDeals();
  }
  function mqStep(now) {
    const dt = Math.min(64, now - (mqLast || now));
    mqLast = now;
    if (!mqHover) {
      x += dt * (innerWidth < 720 ? 0.045 : 0.06);      // px por ms: devagar, para dar tempo de ler
      if (x >= 0) x -= setWidth;
      track.style.transform = `translate3d(${x.toFixed(1)}px,0,0)`;
    }
    mqRaf = requestAnimationFrame(mqStep);
  }
  function mqPlay() { if (mqRaf === null && mqVisible && !reduceMQ.matches && !document.hidden) { mqLast = 0; mqRaf = requestAnimationFrame(mqStep); } }
  function mqStop() { if (mqRaf !== null) { cancelAnimationFrame(mqRaf); mqRaf = null; } }

  // Os vídeos dos banners só tocam enquanto aparecem na tela.
  let dealIO = null;
  function observeDeals() {
    dealIO?.disconnect();
    dealIO = new IntersectionObserver(entries => {
      for (const e of entries) {
        const v = $('video', e.target);
        if (!v || saveData) continue;
        if (e.isIntersecting && mqVisible) {
          if (!v.src) { v.src = v.dataset.src; }
          v.play().catch(() => {});
        } else if (!v.paused) v.pause();
      }
    }, { root: marquee, threshold: 0.1 });
    $$('[data-deal]', track).forEach(d => dealIO.observe(d));
  }
  if (marquee && track) {
    new IntersectionObserver(([e]) => {
      mqVisible = e.isIntersecting;
      if (mqVisible) mqPlay(); else { mqStop(); $$('video', track).forEach(v => v.pause()); }
    }, { rootMargin: '200px 0px' }).observe(marquee);
    marquee.addEventListener('pointerenter', e => { if (e.pointerType === 'mouse') mqHover = true; });
    marquee.addEventListener('pointerleave', () => { mqHover = false; });
    marquee.addEventListener('focusin', () => { mqHover = true; });
    marquee.addEventListener('focusout', () => { mqHover = false; });
    if (!reduceMQ.matches) buildClones(); else observeDeals();
    let rw = innerWidth;
    addEventListener('resize', () => { if (Math.abs(innerWidth - rw) > 40 && !reduceMQ.matches) { rw = innerWidth; buildClones(); } });
  }

  // Botões dos banners abrem o lanche direto.
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-product-slug]');
    if (!b) return;
    const s = window.DitosStore?.store;
    const p = s?.menu?.products.find(x => x.slug === b.dataset.productSlug);
    if (p) window.DitosStore.openProduct(p.id);
    else $('#cardapio')?.scrollIntoView({ behavior: reduceMQ.matches ? 'auto' : 'smooth' });
  });

  // ================================================================ segure para selar a carne
  const sear = $('[data-sear]');
  const searBtn = $('[data-sear-btn]');
  const steps = $$('[data-steps] .pstep');
  let sp = 0, holding = false, searRaf = null, searLast = 0, seared = false;
  function setSear(v) { sp = v; sear.style.setProperty('--sp', v.toFixed(3)); }
  function finishSear(instant) {
    seared = true;
    holding = false;
    setSear(1);
    sear.classList.add('is-done');
    $('[data-sear-label]').textContent = 'Selado!';
    $('[data-sear-help]').textContent = 'Assim com cada lanche: selado na hora que o pedido chega.';
    steps.forEach((s, i) => (instant ? s.classList.add('is-lit') : setTimeout(() => s.classList.add('is-lit'), 180 + i * 260)));
  }
  function searLoop(now) {
    const dt = Math.min(64, now - (searLast || now));
    searLast = now;
    if (holding) setSear(Math.min(1, sp + dt / 1500));
    else setSear(Math.max(0, sp - dt / 900));
    if (sp >= 1 && holding) { finishSear(false); searRaf = null; return; }
    if (sp <= 0 && !holding) { searRaf = null; searLast = 0; return; }
    searRaf = requestAnimationFrame(searLoop);
  }
  function searStart(e) {
    if (seared) return;
    if (reduceMQ.matches) { finishSear(true); return; }
    e.preventDefault();
    holding = true;
    if (searRaf === null) { searLast = 0; searRaf = requestAnimationFrame(searLoop); }
  }
  function searStop() {
    holding = false;
    if (!seared && searRaf === null && sp > 0) { searLast = 0; searRaf = requestAnimationFrame(searLoop); }
  }
  if (searBtn) {
    searBtn.addEventListener('pointerdown', e => { searBtn.setPointerCapture?.(e.pointerId); searStart(e); });
    ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(t => searBtn.addEventListener(t, searStop));
    searBtn.addEventListener('keydown', e => { if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) searStart(e); });
    searBtn.addEventListener('keyup', e => { if (e.key === ' ' || e.key === 'Enter') searStop(); });
    searBtn.addEventListener('contextmenu', e => e.preventDefault());
  }

  // ================================================================ dados da loja na página
  document.addEventListener('ditos:menu', ({ detail }) => {
    const info = detail.store;
    $$('[data-store-address]').forEach(el => { el.textContent = info.address; });
    $$('[data-store-hours]').forEach(el => { el.textContent = info.hours_label; });
    const wa = String(info.whatsapp || '').replace(/\D/g, '');
    if (wa) { const p = $('[data-store-whats]'); p.hidden = false; $('a', p).href = `https://wa.me/${wa.startsWith('55') ? wa : '55' + wa}`; }
    if (info.phone) { const p = $('[data-store-phone]'); p.hidden = false; p.textContent = `Telefone ${info.phone}`; }

    const list = $('[data-hoods]');
    const empty = $('[data-hoods-empty]');
    const money = c => (c / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    const norm = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
    const rows = detail.neighborhoods.map(n => {
      const li = document.createElement('li');
      li.dataset.name = norm(n.name);
      const a = document.createElement('span'); a.textContent = n.name;
      const b = document.createElement('span'); b.textContent = n.eta;
      const c = document.createElement('b'); c.textContent = money(n.fee_cents);
      li.append(a, b, c);
      return li;
    });
    list.replaceChildren(...rows);
    $('[data-hood-search]').addEventListener('input', e => {
      const q = norm(e.target.value.trim());
      let shown = 0;
      rows.forEach(li => { const ok = !q || li.dataset.name.includes(q); li.hidden = !ok; if (ok) shown++; });
      empty.hidden = shown > 0;
    });
  });

  // ================================================================ movimento reduzido ao vivo, aba escondida
  function pinToFinalStates() {
    lines.forEach(l => { l.v = 1; l.el.style.setProperty('--draw', 1); });
    if (!seared && searBtn) finishSear(true);
    $$('.reveal, [data-steps], .cards').forEach(el => el.classList.add('in'));
    mqStop();
    track.style.transform = '';
    $$('[data-clone]', track).forEach(c => c.remove());
  }
  function unpinFinalStates() {
    lines.forEach(l => { l.v = -1; l.el.style.removeProperty('--draw'); });
    if (!reduceMQ.matches) updateLines();
  }
  reduceMQ.addEventListener('change', e => {
    if (e.matches) pinToFinalStates();
    else { applyHeroMode(); unpinFinalStates(); if (marquee) { buildClones(); mqPlay(); } }
  });

  document.addEventListener('visibilitychange', () => {
    document.body.classList.toggle('paused', document.hidden);
    if (document.hidden) { mqStop(); $$('video', track).forEach(v => v.pause()); }
    else { mqPlay(); observeDeals(); }
  });

  // ================================================================ partida
  applyHeroMode();
  updateNav();
  if (reduceMQ.matches) pinToFinalStates(); else updateLines();
})();
