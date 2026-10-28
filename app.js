/* Ireri Timetables — teachers' phone app (FET edition) */
(() => {
  'use strict';

  const CFG = self.IRERI_CONFIG || {};
  const DATA_CACHE = 'ireri-data-v2';

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const I = {
    back: 'M15.5 4.5 8 12l7.5 7.5-1.4 1.4L5.2 12l8.9-8.9 1.4 1.4Z',
    more: 'M12 7a2 2 0 1 1 0-4 2 2 0 0 1 0 4Zm0 7a2 2 0 1 1 0-4 2 2 0 0 1 0 4Zm0 7a2 2 0 1 1 0-4 2 2 0 0 1 0 4Z',
    bell: 'M12 22a2.5 2.5 0 0 0 2.4-2h-4.8a2.5 2.5 0 0 0 2.4 2Zm7-6V11a7 7 0 0 0-5.5-6.8V3a1.5 1.5 0 0 0-3 0v1.2A7 7 0 0 0 5 11v5l-2 2v1h18v-1l-2-2Z',
    star: 'm12 17.3 6.2 3.7-1.6-7 5.4-4.7-7.2-.6L12 2 9.2 8.7 2 9.3l5.4 4.7-1.6 7L12 17.3Z',
    starO: 'm12 15.4-3.8 2.3 1-4.3-3.3-2.9 4.4-.4L12 6.1l1.7 4 4.4.4-3.3 2.9 1 4.3L12 15.4ZM22 9.2l-7.2-.6L12 2 9.2 8.6 2 9.2l5.5 4.7L5.8 21 12 17.3l6.2 3.7-1.6-7.1L22 9.2Z',
    search: 'M10 2a8 8 0 0 1 6.3 12.9l5.4 5.4-1.4 1.4-5.4-5.4A8 8 0 1 1 10 2Zm0 2a6 6 0 1 0 0 12 6 6 0 0 0 0-12Z',
    refresh: 'M17.7 6.3A8 8 0 1 0 20 12h-2a6 6 0 1 1-1.8-4.3L13 11h7V4l-2.3 2.3Z',
    clock: 'M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20Zm-1 5v6l5 3 1-1.6-4-2.4V7h-2Z',
    share: 'M18 16a3 3 0 0 0-2.4 1.2l-6.7-3.4a3 3 0 0 0 0-1.6l6.7-3.4A3 3 0 1 0 15 7l-6.7 3.4a3 3 0 1 0 0 3.2L15 17a3 3 0 1 0 3-1Z',
    install: 'M11 3h2v9.2l3.3-3.3 1.4 1.4L12 16l-5.7-5.7 1.4-1.4 3.3 3.3V3ZM4 18h16v2H4v-2Z',
    info: 'M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20Zm-1 8v7h2v-7h-2Zm0-3v2h2V7h-2Z',
    chev: 'm9 6 6 6-6 6-1.4-1.4 4.6-4.6-4.6-4.6L9 6Z',
    prev: 'M15.4 7.4 14 6l-6 6 6 6 1.4-1.4-4.6-4.6 4.6-4.6Z',
    next: 'M8.6 16.6 10 18l6-6-6-6-1.4 1.4 4.6 4.6-4.6 4.6Z',
    save: 'M5 3h11l3 3v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm2 2v4h8V5H7Zm5 7a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z',
    print: 'M7 3h10v4H7V3Zm-2 5h14a2 2 0 0 1 2 2v6h-4v4H7v-4H3v-6a2 2 0 0 1 2-2Zm4 7v3h6v-3H9Z',
    teacher: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm0 2c-4.4 0-8 2.2-8 5v1h16v-1c0-2.8-3.6-5-8-5Z',
    classes: 'M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm8 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM8 13c-3 0-6 1.5-6 4v2h12v-2c0-2.5-3-4-6-4Zm8 0c-.5 0-1 0-1.5.1 1 .8 1.5 1.8 1.5 2.9v3h6v-2c0-2.5-3-4-6-4Z',
    lab: 'M9 3h6v2h-1v4.3l5.6 9.3A2 2 0 0 1 17.9 21H6.1a2 2 0 0 1-1.7-3.4L10 9.3V5H9V3Zm3 8.2L8.6 17h6.8L12 11.2Z',
    grid: 'M3 4h18v16H3V4Zm2 2v3h4V6H5Zm6 0v3h4V6h-4Zm6 0v3h2V6h-2ZM5 11v3h4v-3H5Zm6 0v3h4v-3h-4Zm6 0v3h2v-3h-2ZM5 16v2h4v-2H5Zm6 0v2h4v-2h-4Zm6 0v2h2v-2h-2Z',
    free: 'M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20Zm-1.2 13.6 6.4-6.4-1.4-1.4-5 5-2.4-2.4L7 11.8l3.8 3.8Z',
    cover: 'M16 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm-8 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm0 2c-2.7 0-6 1.3-6 3.5V19h7.5v-2.5c0-1 .4-2 1.2-2.8A9 9 0 0 0 8 13Zm8 0c-2.7 0-6 1.3-6 3.5V19h12v-2.5c0-2.2-3.3-3.5-6-3.5Z',
    pin: 'M12 2a7 7 0 0 1 7 7c0 5.2-7 13-7 13S5 14.2 5 9a7 7 0 0 1 7-7Zm0 4.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5Z',
    wa: 'M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm5.3 14.2c-.2.6-1.3 1.2-1.8 1.2-.5.1-1 .2-3.3-.7-2.8-1.1-4.6-4-4.7-4.2-.1-.2-1.1-1.5-1.1-2.9 0-1.4.7-2 1-2.3.2-.3.5-.3.7-.3h.5c.2 0 .4 0 .6.5l.8 2c.1.2.1.4 0 .5l-.3.5-.4.4c-.1.2-.3.3-.1.6.2.3.8 1.4 1.8 2.2 1.2 1.1 2.2 1.4 2.5 1.6.3.1.5.1.7-.1l.9-1.1c.2-.3.4-.2.7-.1l1.9.9c.3.1.5.2.5.3.1.2.1.7-.1 1.3Z',
  };
  const icon = (n, cls = '') => `<svg class="ic ${cls}" viewBox="0 0 24 24" aria-hidden="true"><path d="${I[n] || n}"/></svg>`;

  // ------------------------------------------------------------------ routing / storage
  const pathMatch = location.pathname.match(/^\/s\/([^\/]+)\/?/);
  if (pathMatch && !location.pathname.endsWith('/')) { location.replace(location.pathname + '/' + location.search + location.hash); return; }
  const CODE = pathMatch ? decodeURIComponent(pathMatch[1]) : null;
  const POSTER = new URLSearchParams(location.search).has('poster');
  const store = {
    get(k, d = null) { try { const v = localStorage.getItem(`ireri:${CODE}:${k}`); return v === null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem(`ireri:${CODE}:${k}`, JSON.stringify(v)); } catch { } },
    del(k) { try { localStorage.removeItem(`ireri:${CODE}:${k}`); } catch { } },
  };
  if (!CODE) {
    let last = null; try { last = localStorage.getItem('ireri:last'); } catch { }
    if (last) { location.replace(`/s/${encodeURIComponent(last)}/`); return; }
    document.getElementById('app').innerHTML = `<div class="splash"><div class="splash-logo"></div><h2>School timetables</h2><p>Open the link or scan the QR code your school shared with you.</p></div>`;
    return;
  }
  try { localStorage.setItem('ireri:last', CODE); } catch { }

  const state = {
    data: null, online: navigator.onLine, syncing: false, lastSync: 0, error: null, installEvt: null,
    layout: 'auto', day: null, slot: null, grade: 'all', query: {}, coverTeacher: null, coverSlot: null,
    coverPick: false, navDepth: 0,
  };
  let B = null;           // timetable data
  let IDX = null;         // derived indexes

  // ------------------------------------------------------------------ helpers
  const isStandalone = () => matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  const isIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const platformName = () => isIOS() ? 'ios' : /android/i.test(navigator.userAgent) ? 'android' : 'desktop';
  const linkFor = () => `${location.origin}/s/${encodeURIComponent(CODE)}/`;
  const isLandscape = () => matchMedia('(orientation: landscape)').matches || innerWidth >= 760;
  function fmtDate(iso) {
    if (!iso) return '';
    const d = new Date(iso); if (isNaN(d)) return iso;
    return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }) + ', ' +
      d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }).toLowerCase();
  }
  const ago = ms => { const s = Math.round((Date.now() - ms) / 1000); return s < 60 ? 'just now' : s < 3600 ? `${Math.round(s / 60)} min ago` : s < 86400 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} days ago`; };
  const natural = (a, b) => String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: 'base' });
  async function sha256hex(s) {
    if (crypto.subtle) { const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)); return Array.from(new Uint8Array(b)).map(x => x.toString(16).padStart(2, '0')).join(''); }
    let h = 0; for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0; return 'h' + (h >>> 0).toString(16) + s.length;
  }
  let toastTimer;
  function toast(msg, ms = 3000) { const t = $('#toast'); t.innerHTML = esc(msg); t.classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), ms); }

  // ------------------------------------------------------------------ timetable logic
  function gradeOf(name) { const m = String(name).trim().match(/^(?:form|grade|f|g)?\s*(\d{1,2})/i); return m ? m[1] : ''; }
  function buildIndex() {
    const P = B.periods, D = B.days;
    const lessons = P.map((p, i) => i).filter(i => !P[i].brk);
    const tByCode = {};
    B.teachers.forEach(t => { tByCode[t.code] = t; });
    const byId = {};
    for (const k of ['teachers', 'classes', 'rooms', 'master']) (B[k] || []).forEach(x => { x.kind = k; byId[x.id] = x; });
    const grades = [...new Set(B.classes.map(c => gradeOf(c.name)).filter(Boolean))].sort(natural);
    IDX = { P, D, lessons, tByCode, byId, grades };
  }
  function cellAt(item, d, j) {
    const row = item.grid[d] || [];
    let k = j; while (k > 0 && row[k] === '^') k--;
    const c = row[k];
    return c === undefined ? '' : c;
  }
  const isLesson = c => c && typeof c === 'object';
  const isDoubleStart = (item, d, j) => (item.grid[d] || [])[j + 1] === '^';
  const isCont = (item, d, j) => (item.grid[d] || [])[j] === '^';
  function teacherLabel(t) {
    if (!t) return '';
    if (t.name) return t.name;
    return /^\d+$/.test(t.code) ? `Teacher ${t.code}` : t.code;
  }
  const tLabel = t => t ? (t.name ? `${t.code} · ${t.name}` : teacherLabel(t)) : '';
  function teachersText(codes, max = 2) {
    if (!codes) return '';
    const list = String(codes).split(',').map(s => s.trim()).filter(Boolean);
    if (list.length > max) return `${list.length} teachers`;
    return list.map(c => { const t = IDX.tByCode[c]; return t ? (t.name || (/^\d+$/.test(c) ? `Tr ${c}` : c)) : c; }).join(', ');
  }
  function classesText(c, max = 3) {
    if (!c) return '';
    const list = String(c).split(',').map(s => s.trim()).filter(Boolean);
    if (list.length > max) { const g = [...new Set(list.map(gradeOf))]; return g.length === 1 && g[0] ? `All ${g[0]}s (${list.length} classes)` : `${list.length} classes`; }
    return list.join(', ');
  }
  // Text for a lesson cell in each kind of timetable: [main line, small line]
  function cellLines(kind, c, ownName) {
    if (!isLesson(c)) return null;
    const tag = c.g ? ` ${c.g}` : '';
    if (kind === 'teachers') return [classesText(c.c) || c.s || '', [c.c ? c.s : '', tag.trim(), c.r].filter(Boolean).join(' · ')];
    if (kind === 'classes' || kind === 'master') {
      const others = c.c ? c.c.split(',').map(s => s.trim()).filter(x => x !== ownName) : [];
      return [(c.s || '') + tag, [teachersText(c.t), c.r, others.length && others.length < 3 ? 'with ' + others.join(', ') : ''].filter(Boolean).join(' · ')];
    }
    return [[classesText(c.c), c.s].filter(Boolean).join(' · '), teachersText(c.t)];
  }
  const nowMinutes = () => { const d = new Date(); return d.getHours() * 60 + d.getMinutes(); };
  function todayIndex() { const wd = new Date().getDay(); return IDX.D.findIndex(d => d.wd === wd); }
  function nowSlot() {
    const d = todayIndex();
    if (d < 0) return { d: -1, j: -1, status: 'noday' };
    const m = nowMinutes(), P = IDX.P;
    for (let j = 0; j < P.length; j++) if (P[j].start != null && m >= P[j].start && m < P[j].end) return { d, j, status: P[j].brk ? 'break' : 'lesson' };
    const first = P.find(p => p.start != null), last = [...P].reverse().find(p => p.end != null);
    if (first && m < first.start) return { d, j: IDX.lessons[0], status: 'before' };
    if (last && m >= last.end) return { d, j: -1, status: 'after' };
    return { d, j: P.findIndex(p => p.start != null && p.start > m), status: 'between' };
  }
  function defaultSlot() {
    const n = nowSlot();
    if (n.d < 0) return { d: 0, j: IDX.lessons[0] };
    if (n.status === 'after') return { d: n.d, j: IDX.lessons[IDX.lessons.length - 1] };
    let j = n.j;
    if (j < 0 || IDX.P[j].brk) j = IDX.lessons.find(x => x > (j < 0 ? -1 : j)) ?? IDX.lessons[0];
    return { d: n.d, j };
  }
  const pLabel = j => { const p = IDX.P[j]; return p ? `${p.label}${p.time ? ' · ' + p.time : ''}` : ''; };
  const dayLabel = d => IDX.D[d] ? IDX.D[d].label : '';
  const freeAt = (d, j) => B.teachers.filter(t => cellAt(t, d, j) === '');
  const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
  const lessonsOnDay = (t, d) => (t.grid[d] || []).filter(c => isLesson(c) || c === '^').length;
  function freeAfternoons(t) {
    const pm = IDX.lessons.filter(j => IDX.P[j].pm);
    if (!pm.length) return [];
    return IDX.D.map((_, d) => d).filter(d => pm.every(j => { const c = cellAt(t, d, j); return c === '' || c === 'X'; }));
  }
  function teacherSubjects(t) { const s = new Set(); t.grid.forEach(r => r.forEach(c => { if (isLesson(c) && c.s) s.add(c.s.replace(/\s*\d+$/, '').trim()); })); return s; }
  function teacherClasses(t) { const s = new Set(); t.grid.forEach(r => r.forEach(c => { if (isLesson(c) && c.c) c.c.split(',').forEach(x => s.add(x.trim())); })); return s; }

  // ------------------------------------------------------------------ data
  async function loadCached() {
    try { if ('caches' in self) { const c = await caches.open(DATA_CACHE); const r = await c.match(`/__data/${CODE}.json`); if (r) return await r.json(); } } catch { }
    try { const v = localStorage.getItem(`ireri:${CODE}:data2`); return v ? JSON.parse(v) : null; } catch { return null; }
  }
  async function saveCached(obj) {
    const body = JSON.stringify(obj);
    try { if ('caches' in self) { const c = await caches.open(DATA_CACHE); await c.put(`/__data/${CODE}.json`, new Response(body, { headers: { 'Content-Type': 'application/json' } })); return; } } catch { }
    try { localStorage.setItem(`ireri:${CODE}:data2`, body); } catch { }
  }
  class NotFound extends Error { }
  class Locked extends Error { }
  const BASE = `/s/${encodeURIComponent(CODE)}/`;
  async function getJson(name, bust) {
    const r = await fetch(`${BASE}${name}?v=${encodeURIComponent(bust)}`, { cache: 'no-store' });
    if (r.status === 404) throw new NotFound(name);
    if (!r.ok) throw new Error(`Server said ${r.status}`);
    return r.json();
  }
  function setData(d) { state.data = d; B = d.bundle; buildIndex(); }
  async function sync(reason = '') {
    if (state.syncing) return;
    state.syncing = true; renderStatus();
    const had = !!state.data;
    try {
      const meta = await getJson('meta.json', Date.now());          // tiny file: has anything changed?
      if (!state.data || state.data.version !== meta.version) {
        const full = await getJson('data.json', meta.version);       // the timetables themselves
        setData({ version: full.version || meta.version, school: full.school || meta, bundle: full.bundle, savedAt: Date.now() });
        await saveCached(state.data);
        if (had) toast('Timetable updated to the latest version ✓');
        state.error = null; render();
      } else { state.data.school = { ...state.data.school, ...meta }; state.data.savedAt = Date.now(); saveCached(state.data); }
      state.online = true; state.lastSync = Date.now(); state.error = null;
    } catch (e) {
      state.online = navigator.onLine && !(e instanceof TypeError);
      if (e instanceof NotFound) state.error = 'notfound';
      else if (!state.data) state.error = state.online ? 'failed' : 'offline';
      if (!state.data) render();
      if (reason === 'manual') toast(navigator.onLine ? 'Could not reach the server. Showing saved copy.' : 'You are offline. Showing saved copy.');
    } finally { state.syncing = false; renderStatus(); if (state.data && route().name === 'home') renderBanners(); }
  }

  // ------------------------------------------------------------------ shell
  const app = $('#app');
  function route() {
    const h = location.hash.replace(/^#\/?/, '');
    if (!h) return { name: 'home' };
    const parts = h.split('/').map(decodeURIComponent);
    if (parts[0] === 'list') return { name: 'list', kind: parts[1] || 'teachers', pick: parts[2] === 'pick' };
    if (parts[0] === 'view') return { name: 'view', id: parts[1] };
    return { name: parts[0] };
  }
  const go = h => { location.hash = h; };
  function render() {
    if (POSTER) return renderPoster();
    if (state.error === 'locked') return renderMsg('Timetables not available', 'This school\'s timetable service is switched off. Please contact the school office.', false);
    if (!state.data) return renderEmpty();
    const r = route();
    if (r.name === 'list') return renderList(r.kind, r.pick);
    if (r.name === 'view' && IDX.byId[r.id]) return renderViewer(r.id);
    if (r.name === 'master') return renderMaster();
    if (r.name === 'free') return renderFree();
    if (r.name === 'cover') return renderCover();
    if (r.name === 'where') return renderWhere();
    return renderHome();
  }
  function topBar(title, sub = '', right = '') {
    return `<header class="vtop"><button class="icon-btn" data-act="back" aria-label="Back">${icon('back')}</button>
      <div class="vtitles"><h2>${esc(title)}</h2>${sub ? `<p>${sub}</p>` : ''}</div>${right || '<span class="icon-btn ghost"></span>'}</header>`;
  }
  function renderStatus() {
    const el = $('#status'); if (!el || !state.data) return;
    let s = `Updated ${esc(fmtDate(state.data.school?.updated || B?.published))}`;
    if (state.syncing) s += ` · <span class="pill">checking…</span>`;
    else if (!state.online) s += ` · <span class="pill off">offline · saved copy</span>`;
    else s += ` · <span class="pill ok">✓ latest</span>`;
    el.innerHTML = s;
  }
  function renderEmpty() {
    const msgs = {
      notfound: ['School not found', 'This link does not match any school, or the timetable has not been published yet. Ask your school office for the correct link.'],
      offline: ['You are offline', 'Connect to the internet once to download the timetables. After that they work offline too.'],
      failed: ['Could not load timetables', 'Please check your connection and try again.'],
    };
    const [t, m] = msgs[state.error] || ['Loading timetables…', 'Please wait a moment.'];
    renderMsg(t, m, !!state.error);
  }
  function renderMsg(t, m, retry) {
    app.innerHTML = `<div class="splash"><div class="splash-logo"></div><h2>${esc(t)}</h2><p>${esc(m)}</p>${retry ? '<button class="btn" data-act="retry">Try again</button>' : ''}</div>`;
  }

  // ------------------------------------------------------------------ HOME dashboard
  function meTeacher() { const code = store.get('me'); return code != null ? IDX.tByCode[code] || null : null; }
  function nowCard() {
    const n = nowSlot(), me = meTeacher();
    let when;
    if (n.status === 'noday') when = 'No lessons today';
    else if (n.status === 'after') when = `${dayLabel(n.d)} · lessons are over for today`;
    else if (n.status === 'before') when = `${dayLabel(n.d)} · first lesson at ${(IDX.P[n.j]?.time || '').split('-')[0]}`;
    else if (n.status === 'break') when = `${dayLabel(n.d)} · ${IDX.P[n.j].label} (${IDX.P[n.j].time})`;
    else if (n.status === 'between') when = `${dayLabel(n.d)} · next ${pLabel(n.j)}`;
    else when = `${dayLabel(n.d)} · now ${pLabel(n.j)}`;
    let mine = '';
    if (me && n.d >= 0) {
      const cur = n.status === 'lesson' ? cellAt(me, n.d, n.j) : null;
      const after = n.status === 'after' ? 999 : n.status === 'before' ? n.j - 1 : n.j;
      const nextJ = IDX.lessons.find(j => j > after && isLesson(cellAt(me, n.d, j)) && !isCont(me, n.d, j));
      const L = cur && isLesson(cur) ? cellLines('teachers', cur) : null;
      const curTxt = cur === null ? '' : L ? `<b>${esc(L[0])}</b> ${esc(L[1])}` : cur === 'X' ? 'Not available' : '<b class="ok">Free</b>';
      const N = nextJ != null ? cellLines('teachers', cellAt(me, n.d, nextJ)) : null;
      mine = `<div class="now-me">
        ${curTxt ? `<div><small>You now</small><span>${curTxt}</span></div>` : ''}
        <div><small>Your next lesson</small><span>${N ? `<b>${esc(N[0])}</b> ${esc(N[1])} <em>${esc(pLabel(nextJ))}</em>` : 'No more lessons today'}</span></div></div>`;
    } else if (!me) {
      mine = `<button class="now-set" data-act="pickMe">${icon('starO')} Choose “My timetable” to see your lessons here</button>`;
    }
    return `<section class="now-card"><div class="now-when">${icon('clock', 'tiny')}<span>${esc(when)}</span></div>${mine}</section>`;
  }
  function renderHome() {
    const sch = state.data.school || {};
    const name = sch.name || B.school || 'School';
    const me = meTeacher();
    document.title = name + ' · Timetables';
    const tiles = [
      ['me', 'star', 'My timetable', me ? teacherLabel(me) : 'Tap to choose', me ? `view/${me.id}` : ''],
      ['teachers', 'teacher', 'Teachers', `${B.teachers.length} timetables`, 'list/teachers'],
      ['classes', 'classes', 'Classes', `${B.classes.length} timetables`, 'list/classes'],
      ['master', 'grid', 'Master', 'Day by day', 'master'],
      ['rooms', 'lab', 'Labs & Fields', `${B.rooms.length} timetables`, 'list/rooms'],
      ['free', 'free', 'Free teachers', 'Now & free afternoon', 'free'],
      ['cover', 'cover', 'Find cover', 'Who can stand in', 'cover'],
      ['where', 'pin', 'Where is…?', 'Find a teacher', 'where'],
    ];
    app.innerHTML = `
      <header class="top"><div class="brandrow">
        <div class="logo" aria-hidden="true"></div>
        <div class="titles"><h1>${esc(name)}</h1><p class="sub" id="status"></p></div>
        <button class="icon-btn" data-act="menu" aria-label="Menu">${icon('more')}</button></div>
      </header>
      <main class="home">
        ${sch.institution ? `<p class="term">${esc(sch.institution)}</p>` : ''}
        <div id="banners"></div>
        ${nowCard()}
        <nav class="tiles">${tiles.map(([k, ic, t, s, href]) => `
          <button class="tile t-${k}" ${href ? `data-go="${href}"` : 'data-act="pickMe"'}>
            <span class="tic">${icon(ic)}</span><strong>${esc(t)}</strong><small>${esc(s)}</small></button>`).join('')}
        </nav>
        <footer class="foot">${esc(sch.footer || CFG.brand || 'Timetables by Ireri Venture')}${(sch.contact || CFG.contact) ? ' · ' + esc(sch.contact || CFG.contact) : ''}</footer>
      </main>`;
    renderStatus(); renderBanners();
  }
  function renderBanners() {
    const box = $('#banners'); if (!box || !state.data) return;
    const out = [];
    if (store.get('seen') !== state.data.version) {
      const note = state.data.school?.note || B.note;
      out.push(`<div class="banner new"><div><strong>🆕 New timetable published</strong><span>${esc(fmtDate(state.data.school?.updated || B.published))}${note ? ' — ' + esc(note) : ''}</span></div><button class="txt-btn" data-act="seen">Got it</button></div>`);
    }
    if (!isStandalone() && !store.get('hideInstallTip')) {
      if (state.installEvt) out.push(`<div class="banner tip"><div>${icon('install')}<span><strong>Install this app</strong> for one-tap access, even offline.</span></div><div class="banner-actions"><button class="btn small" data-act="install">Install</button><button class="txt-btn" data-act="hideInstall">Later</button></div></div>`);
      else if (isIOS()) out.push(`<div class="banner tip"><div>${icon('install')}<span><strong>Add to Home Screen:</strong> tap Share <b>⬆</b> in Safari, then <b>Add to Home Screen</b>.</span></div><div class="banner-actions"><button class="txt-btn" data-act="hideInstall">OK</button></div></div>`);
    }
    box.innerHTML = out.join('');
  }

  // ------------------------------------------------------------------ LISTS with filters
  const KIND = {
    teachers: { title: 'Teachers', ph: 'Search by number or name…' },
    classes: { title: 'Classes', ph: 'Search a class…' },
    rooms: { title: 'Labs & Fields', ph: 'Search a lab or field…' },
  };
  function listItems(kind) {
    const q = (state.query[kind] || '').trim().toLowerCase();
    let list = B[kind] || [];
    if (kind === 'classes' && state.grade !== 'all') list = list.filter(c => gradeOf(c.name) === state.grade);
    if (q) list = list.filter(x => (kind === 'teachers' ? `${x.code} ${x.name}` : x.name).toLowerCase().includes(q));
    return list;
  }
  function gradeChips() {
    return IDX.grades.length > 1 ? `<div class="chips" id="chips">${['all', ...IDX.grades].map(g => `<button class="chip ${state.grade === g ? 'on' : ''}" data-grade="${esc(g)}">${g === 'all' ? 'All' : esc(g)}</button>`).join('')}</div>` : '';
  }
  function renderList(kind, pick) {
    const k = KIND[kind] || KIND.teachers;
    app.innerHTML = `${topBar(pick ? 'Choose your timetable' : k.title, `${(B[kind] || []).length} timetables`)}
      <main class="page">
        ${pick ? '<p class="hint-box">Tap your name, then tap ☆ at the top of your timetable.</p>' : ''}
        <div class="searchbox">${icon('search')}<input id="q" type="search" autocomplete="off" placeholder="${esc(k.ph)}" value="${esc(state.query[kind] || '')}"></div>
        ${kind === 'classes' ? gradeChips() : ''}
        <ul class="list" id="list"></ul>
      </main>`;
    const draw = () => {
      const me = String(store.get('me'));
      const rows = listItems(kind);
      $('#list').innerHTML = rows.length ? rows.map(x => `
        <li><button class="row" data-go="view/${esc(x.id)}">
          <span class="av av-${kind}">${kind === 'teachers' ? esc(String(x.code).slice(0, 4)) : kind === 'rooms' ? icon('lab') : esc(String(x.name).replace(/\s+/g, '').slice(0, 4))}</span>
          <span class="nm">${esc(kind === 'teachers' ? teacherLabel(x) : x.name)}${kind === 'teachers' ? `<small>${x.name ? 'No. ' + esc(x.code) + ' · ' : ''}${plural(x.load || 0, 'lesson')} a week</small>` : ''}</span>
          ${kind === 'teachers' && String(x.code) === me ? '<span class="me-tag">★ Me</span>' : ''}
          ${icon('chev', 'chev')}</button></li>`).join('') : `<li class="empty">Nothing matches.</li>`;
    };
    draw();
    $('#q').addEventListener('input', e => { state.query[kind] = e.target.value; draw(); });
    $$('#chips .chip').forEach(b => b.addEventListener('click', () => { state.grade = b.dataset.grade; $$('#chips .chip').forEach(x => x.classList.toggle('on', x === b)); draw(); }));
  }

  // ------------------------------------------------------------------ VIEWER — one timetable at a time
  function siblings(item) {
    const list = ['classes', 'teachers', 'rooms'].includes(item.kind) ? listItems(item.kind) : B[item.kind];
    return list.some(x => x.id === item.id) ? list : B[item.kind];
  }
  const effectiveLayout = () => state.layout === 'auto' ? (isLandscape() ? 'week' : 'day') : state.layout;
  function renderViewer(id) {
    const item = IDX.byId[id], kind = item.kind;
    const sib = siblings(item), idx = sib.findIndex(x => x.id === id);
    const isMe = kind === 'teachers' && String(store.get('me')) === String(item.code);
    const title = kind === 'teachers' ? teacherLabel(item) : item.name;
    const sub = `${KIND[kind]?.title || 'Master'} · ${idx + 1} of ${sib.length}${kind === 'teachers' && item.name ? ' · No. ' + esc(item.code) : ''}`;
    if (state.day == null) state.day = Math.max(0, todayIndex());
    const layout = effectiveLayout();
    document.title = title + ' · Timetable';
    app.innerHTML = `
      ${topBar(title, sub, kind === 'teachers' ? `<button class="icon-btn star ${isMe ? 'on' : ''}" data-act="me" aria-label="My timetable">${icon(isMe ? 'star' : 'starO')}</button>` : '')}
      <div class="vbar">
        <div class="seg"><button class="${layout === 'day' ? 'on' : ''}" data-layout="day">Day</button><button class="${layout === 'week' ? 'on' : ''}" data-layout="week">Week</button></div>
        <button class="btn small ghost" data-act="save">${icon('save')} Save</button>
      </div>
      <main class="tt" id="tt">${layout === 'day' ? dayView(item) : weekGrid(item)}</main>
      <div class="vtools">
        <button class="icon-btn" data-act="prev" ${idx <= 0 ? 'disabled' : ''} aria-label="Previous">${icon('prev')}</button>
        <span class="vcount">${idx > 0 ? esc(nameOf(sib[idx - 1])) + ' ‹' : ''}</span><span class="vsep">${idx + 1}/${sib.length}</span><span class="vcount r">${idx < sib.length - 1 ? '› ' + esc(nameOf(sib[idx + 1])) : ''}</span>
        <button class="icon-btn" data-act="next" ${idx >= sib.length - 1 ? 'disabled' : ''} aria-label="Next">${icon('next')}</button>
      </div>`;
    if (layout === 'week') fitGrid();
  }
  const nameOf = x => x.kind === 'teachers' ? (x.name ? x.name : 'Tr ' + x.code) : x.name;
  function dayTabs(sel, attr = 'day') {
    const today = todayIndex();
    return `<div class="daytabs">${IDX.D.map((d, i) => `<button class="${i === sel ? 'on' : ''}" data-${attr}="${i}">${esc(d.label.slice(0, 3))}${i === today ? '<i></i>' : ''}</button>`).join('')}</div>`;
  }
  function dayView(item) {
    const d = state.day, n = nowSlot();
    const rows = IDX.P.map((p, j) => {
      if (p.brk) return `<li class="brk"><span>${esc(p.label)}</span><em>${esc(p.time)}</em></li>`;
      const cls = n.d === d && n.j === j ? 'now' : '';
      if (isCont(item, d, j)) return `<li class="cont ${cls}"><div class="pt"><b>${esc(p.label)}</b><em>${esc(p.time)}</em></div><div class="pc"><span class="muted">↳ continues (double lesson)</span></div></li>`;
      const c = cellAt(item, d, j), L = cellLines(item.kind, c, item.name);
      return `<li class="${cls}"><div class="pt"><b>${esc(p.label)}</b><em>${esc(p.time)}</em></div>
        <div class="pc">${L ? `<strong>${esc(L[0])}</strong>${L[1] ? `<small>${esc(L[1])}</small>` : ''}${isDoubleStart(item, d, j) ? '<span class="dbl">double</span>' : ''}` : c === 'X' ? '<span class="muted">Not available</span>' : '<span class="freec">Free</span>'}</div></li>`;
    }).join('');
    return `${dayTabs(d)}<ul class="dayview">${rows}</ul><p class="swipe-hint">Swipe left or right for the next ${item.kind === 'teachers' ? 'teacher' : item.kind === 'classes' ? 'class' : 'timetable'} · turn the phone to see the whole week</p>`;
  }
  function headCells(d, n) {
    return IDX.P.map((p, j) => `<th class="${p.brk ? 'b' : ''}${n.d === d && n.j === j ? ' nowcol' : ''}">${p.brk ? `<span class="vt">${esc(p.label)}</span>` : `<b>${esc(p.label)}</b><small>${esc(p.time)}</small>`}</th>`).join('');
  }
  function rowCells(item, kind, d, n) {
    let tds = '';
    for (let j = 0; j < IDX.P.length; j++) {
      if (IDX.P[j].brk) { tds += `<td class="b"></td>`; continue; }
      if (isCont(item, d, j)) continue;
      let span = 1; while ((item.grid[d] || [])[j + span] === '^') span++;
      const c = cellAt(item, d, j), L = cellLines(kind, c, item.name);
      const nowc = n.d === d && n.j >= j && n.j < j + span ? ' now' : '';
      tds += `<td${span > 1 ? ` colspan="${span}"` : ''} class="${L ? 'l' : c === 'X' ? 'x' : 'f'}${nowc}">${L ? `<b>${esc(L[0])}</b>${L[1] ? `<small>${esc(L[1])}</small>` : ''}` : ''}</td>`;
    }
    return tds;
  }
  function weekGrid(item) {
    const n = nowSlot();
    const body = IDX.D.map((dd, d) => `<tr class="${n.d === d ? 'today' : ''}"><th>${esc(dd.label)}</th>${rowCells(item, item.kind, d, n)}</tr>`).join('');
    return `<div class="gridwrap" id="gridwrap"><table class="wk" id="wk"><thead><tr><th></th>${headCells(-9, { d: -1 })}</tr></thead><tbody>${body}</tbody></table></div>`;
  }
  function fitGrid() {
    const wrap = $('#gridwrap'), tb = $('#wk'); if (!wrap || !tb) return;
    tb.style.zoom = 1;
    const z = Math.min(1, (wrap.clientWidth - 2) / tb.scrollWidth);
    if (z < 1) tb.style.zoom = Math.max(isLandscape() ? 0.55 : 0.62, z);
  }

  // ------------------------------------------------------------------ MASTER — day by day
  function renderMaster() {
    if (state.day == null) state.day = Math.max(0, todayIndex());
    const d = state.day, n = nowSlot();
    const list = B.master.filter(m => state.grade === 'all' || gradeOf(m.name) === state.grade);
    const body = list.map(m => `<tr><th>${esc(m.name)}</th>${rowCells(m, 'master', d, n)}</tr>`).join('');
    document.title = 'Master · ' + dayLabel(d);
    app.innerHTML = `${topBar('Master timetable', esc(dayLabel(d)) + ' · all classes', `<button class="icon-btn" data-act="save" aria-label="Save">${icon('save')}</button>`)}
      <div class="mbar">${dayTabs(d)}${gradeChips()}</div>
      <main class="tt"><div class="gridwrap" id="gridwrap"><table class="wk master" id="wk"><thead><tr><th>Class</th>${headCells(d, n)}</tr></thead><tbody>${body}</tbody></table></div>
      <p class="swipe-hint">Slide the table sideways · turn the phone for a wider view</p></main>`;
  }

  // ------------------------------------------------------------------ FREE TEACHERS + FREE AFTERNOON
  function slotPicker(sel) {
    return `<div class="chips periods">${IDX.lessons.map(j => `<button class="chip ${sel === j ? 'on' : ''}" data-slot="${j}">${esc(IDX.P[j].label)}<small>${esc(IDX.P[j].time)}</small></button>`).join('')}</div>`;
  }
  function renderFree() {
    if (!state.slot) state.slot = defaultSlot();
    const { d, j } = state.slot;
    const tab = store.get('freeTab', 'now');
    let inner;
    if (tab === 'now') {
      const free = freeAt(d, j).sort((a, b) => lessonsOnDay(a, d) - lessonsOnDay(b, d) || natural(a.code, b.code));
      inner = `${dayTabs(d, 'sday')}${slotPicker(j)}
        <h3 class="sect">${free.length} free · ${esc(dayLabel(d))} · ${esc(pLabel(j))}</h3>
        <ul class="list">${free.map(t => `<li><button class="row" data-go="view/${t.id}"><span class="av av-teachers">${esc(String(t.code).slice(0, 4))}</span>
          <span class="nm">${esc(teacherLabel(t))}<small>${plural(lessonsOnDay(t, d), 'lesson')} on ${esc(dayLabel(d))}</small></span>${icon('chev', 'chev')}</button></li>`).join('') || '<li class="empty">No teacher is free at this lesson.</li>'}</ul>`;
    } else {
      const fa = B.teachers.map(t => ({ t, days: freeAfternoons(t) }));
      const byDay = IDX.D.map((_, dd) => fa.filter(x => x.days.includes(dd)).map(x => x.t).sort((a, b) => natural(a.code, b.code)));
      const none = fa.filter(x => !x.days.length).map(x => x.t);
      const me = meTeacher(), myFA = me ? freeAfternoons(me) : null;
      const nm = t => esc(t.name || 'Tr ' + t.code);
      inner = `${myFA ? `<div class="hint-box">Your free afternoon: <b>${myFA.length ? myFA.map(dayLabel).join(', ') : 'none this week'}</b></div>` : ''}
        ${IDX.D.map((dd, i) => `<h3 class="sect">${esc(dd.label)} afternoon · ${byDay[i].length} free</h3>
          <div class="namegrid">${byDay[i].map(t => `<button data-go="view/${t.id}" class="${me && me.id === t.id ? 'me' : ''}">${nm(t)}</button>`).join('') || '<span class="muted">Nobody</span>'}</div>`).join('')}
        ${none.length ? `<h3 class="sect warn">No free afternoon this week · ${none.length}</h3><div class="namegrid">${none.map(t => `<button data-go="view/${t.id}">${nm(t)}</button>`).join('')}</div>` : ''}
        <p class="muted small">A free afternoon means no lessons after lunch on that day.</p>`;
    }
    app.innerHTML = `${topBar('Free teachers', 'At any lesson, and free afternoons')}
      <div class="seg wide-seg"><button class="${tab === 'now' ? 'on' : ''}" data-freetab="now">Free at a lesson</button><button class="${tab === 'pm' ? 'on' : ''}" data-freetab="pm">Free afternoon</button></div>
      <main class="page">${inner}</main>`;
  }

  // ------------------------------------------------------------------ FIND COVER
  function renderCover() {
    const me = meTeacher();
    const who = state.coverPick ? null : (state.coverTeacher ? IDX.byId[state.coverTeacher] : me);
    if (state.day == null) state.day = Math.max(0, todayIndex());
    const d = state.day;
    if (!who) {
      app.innerHTML = `${topBar('Find cover', 'Who can stand in for a lesson')}
        <main class="page"><p class="hint-box">Who needs someone to stand in? Choose the teacher.</p>
        <div class="searchbox">${icon('search')}<input id="q" type="search" placeholder="Search by number or name…"></div>
        <ul class="list" id="list"></ul></main>`;
      const draw = () => { const q = ($('#q').value || '').toLowerCase(); $('#list').innerHTML = B.teachers.filter(t => `${t.code} ${t.name}`.toLowerCase().includes(q)).map(t => `<li><button class="row" data-covert="${t.id}"><span class="av av-teachers">${esc(String(t.code).slice(0, 4))}</span><span class="nm">${esc(teacherLabel(t))}</span>${icon('chev', 'chev')}</button></li>`).join(''); };
      draw(); $('#q').addEventListener('input', draw); return;
    }
    const mine = IDX.lessons.filter(j => isLesson(cellAt(who, d, j)) && !isCont(who, d, j));
    const sel = state.coverSlot != null && mine.includes(state.coverSlot) ? state.coverSlot : null;
    let cands = '';
    if (sel != null) {
      const c = cellAt(who, d, sel);
      let span = 1; while ((who.grid[d] || [])[sel + span] === '^') span++;
      const slots = Array.from({ length: span }, (_, k) => sel + k);
      const subj = (c.s || '').replace(/\s*\d+$/, '').trim();
      const cls = (c.c || '').split(',').map(x => x.trim()).filter(Boolean);
      const free = B.teachers.filter(t => t.id !== who.id && slots.every(j => cellAt(t, d, j) === ''))
        .map(t => ({ t, same: teacherSubjects(t).has(subj), knows: cls.some(x => teacherClasses(t).has(x)), load: lessonsOnDay(t, d) }))
        .sort((a, b) => (b.same - a.same) || (b.knows - a.knows) || (a.load - b.load) || natural(a.t.code, b.t.code));
      const msg = t => `Hello ${t.name || 'Tr ' + t.code}, could you please stand in for ${who.name || 'Tr ' + who.code} with ${classesText(c.c)} (${c.s || ''}) on ${dayLabel(d)}, ${pLabel(sel)}${span > 1 ? ' (double lesson)' : ''}? Thank you.`;
      cands = `<h3 class="sect">2. Ask someone who is free — ${free.length} available</h3>
        <ul class="list">${free.map(x => `<li><div class="row nolink"><span class="av av-teachers">${esc(String(x.t.code).slice(0, 4))}</span>
          <span class="nm">${esc(teacherLabel(x.t))}<small>${plural(x.load, 'lesson')} on ${esc(dayLabel(d))}</small>
          <span class="badges">${x.same ? '<i class="bd g">Same subject</i>' : ''}${x.knows ? '<i class="bd b">Teaches this class</i>' : ''}</span></span>
          <a class="wa" href="https://wa.me/?text=${encodeURIComponent(msg(x.t))}" target="_blank" rel="noopener" aria-label="Ask on WhatsApp">${icon('wa')}</a></div></li>`).join('') || '<li class="empty">No teacher is free at that time.</li>'}</ul>`;
    }
    app.innerHTML = `${topBar('Find cover', esc(tLabel(who)), `<button class="txt-btn light" data-act="coverWho">Change</button>`)}
      <main class="page">
        ${dayTabs(d)}
        <h3 class="sect">1. Tap the lesson that needs someone</h3>
        <div class="lessonpick">${mine.map(j => { const L = cellLines('teachers', cellAt(who, d, j)); return `<button class="${sel === j ? 'on' : ''}" data-coverslot="${j}"><b>${esc(IDX.P[j].label)}</b><small>${esc(IDX.P[j].time)}</small><span>${esc(L[0])}</span><em>${esc(L[1])}</em></button>`; }).join('') || `<p class="muted">No lessons on ${esc(dayLabel(d))}.</p>`}</div>
        ${cands}
      </main>`;
  }

  // ------------------------------------------------------------------ WHERE IS…
  function renderWhere() {
    if (!state.slot) state.slot = defaultSlot();
    const { d, j } = state.slot;
    const n = nowSlot();
    app.innerHTML = `${topBar('Where is…?', 'Which class a teacher is in')}
      <main class="page">
        <div class="searchbox">${icon('search')}<input id="q" type="search" autocomplete="off" placeholder="Teacher number or name…" value="${esc(state.query.where || '')}"></div>
        ${dayTabs(d, 'sday')}${slotPicker(j)}
        <h3 class="sect">${esc(dayLabel(d))} · ${esc(pLabel(j))}${n.d === d && n.j === j ? ' · <span class="ok">now</span>' : ''}</h3>
        <ul class="list" id="list"></ul>
      </main>`;
    const draw = () => {
      const q = (state.query.where || '').toLowerCase();
      $('#list').innerHTML = B.teachers.filter(t => !q || `${t.code} ${t.name}`.toLowerCase().includes(q)).map(t => {
        const c = cellAt(t, d, j), L = cellLines('teachers', c);
        return `<li><button class="row" data-go="view/${t.id}"><span class="av av-teachers">${esc(String(t.code).slice(0, 4))}</span>
          <span class="nm">${esc(teacherLabel(t))}</span>
          <span class="where ${L ? 'in' : c === 'X' ? 'x' : 'fr'}">${L ? `<b>${esc(L[0])}</b><small>${esc(L[1])}</small>` : c === 'X' ? 'Not available' : 'Free'}</span></button></li>`;
      }).join('') || '<li class="empty">No teacher matches.</li>';
    };
    draw();
    $('#q').addEventListener('input', e => { state.query.where = e.target.value; draw(); });
  }

  // ------------------------------------------------------------------ SAVE as picture
  function wrapText(ctx, text, maxW) {
    const words = String(text).split(/\s+/); const lines = []; let cur = '';
    for (const w of words) { const t = cur ? cur + ' ' + w : w; if (ctx.measureText(t).width > maxW && cur) { lines.push(cur); cur = w; } else cur = t; }
    if (cur) lines.push(cur); return lines;
  }
  async function saveImage() {
    const r = route();
    let title, rows, kind, fname;
    if (r.name === 'master') {
      const d = state.day; kind = 'master';
      title = `Master timetable — ${dayLabel(d)}`; fname = `Master-${dayLabel(d)}`;
      rows = B.master.filter(m => state.grade === 'all' || gradeOf(m.name) === state.grade).map(m => ({ head: m.name, item: m, d }));
    } else {
      const item = IDX.byId[r.id]; kind = item.kind;
      title = kind === 'teachers' ? `${teacherLabel(item)}${item.name ? ' (No. ' + item.code + ')' : ''}` : item.name;
      fname = title.replace(/[^\w\- ]+/g, '').trim() || 'timetable';
      rows = IDX.D.map((dd, d) => ({ head: dd.label, item, d }));
    }
    const P = IDX.P, scale = 2;
    const headW = kind === 'master' ? 90 : 70, colW = 118, brkW = 22, rowH = 64, top = 96, pad = 20;
    const width = pad * 2 + headW + P.reduce((s, p) => s + (p.brk ? brkW : colW), 0);
    const height = top + 44 + rows.length * rowH + 50;
    const cv = document.createElement('canvas'); cv.width = width * scale; cv.height = height * scale;
    const ctx = cv.getContext('2d'); ctx.scale(scale, scale);
    ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = '#12284C'; ctx.fillRect(0, 0, width, 72); ctx.fillStyle = '#C9A227'; ctx.fillRect(0, 72, width, 4);
    ctx.fillStyle = '#fff'; ctx.font = '600 22px Poppins, Arial'; ctx.fillText(title, pad, 34);
    ctx.font = '13px Poppins, Arial'; ctx.fillStyle = '#E8D48A';
    ctx.fillText(`${state.data.school?.name || ''}${state.data.school?.institution ? ' · ' + state.data.school.institution : ''}`, pad, 56);
    let x = pad + headW; const y0 = top; const colX = [];
    P.forEach((p, j) => {
      const w = p.brk ? brkW : colW; colX[j] = [x, w];
      ctx.fillStyle = p.brk ? '#EEE8D8' : '#F3EEDF'; ctx.fillRect(x, y0, w, 44); ctx.strokeStyle = '#C9BFA4'; ctx.strokeRect(x, y0, w, 44);
      if (!p.brk) { ctx.fillStyle = '#12284C'; ctx.font = '600 12px Poppins, Arial'; ctx.fillText(p.label, x + 6, y0 + 18); ctx.font = '11px Poppins, Arial'; ctx.fillStyle = '#555'; ctx.fillText(p.time, x + 6, y0 + 34); }
      x += w;
    });
    rows.forEach((row, ri) => {
      const y = y0 + 44 + ri * rowH;
      ctx.fillStyle = '#12284C'; ctx.fillRect(pad, y, headW, rowH); ctx.fillStyle = '#fff'; ctx.font = '600 13px Poppins, Arial';
      wrapText(ctx, row.head, headW - 10).slice(0, 3).forEach((ln, k) => ctx.fillText(ln, pad + 6, y + 22 + k * 15));
      for (let j = 0; j < P.length; j++) {
        const [cx, w] = colX[j];
        if (P[j].brk) { ctx.fillStyle = '#EEE8D8'; ctx.fillRect(cx, y, w, rowH); ctx.strokeStyle = '#C9BFA4'; ctx.strokeRect(cx, y, w, rowH); continue; }
        if (isCont(row.item, row.d, j)) continue;
        let span = 1; while ((row.item.grid[row.d] || [])[j + span] === '^') span++;
        const cw = colX[j + span - 1][0] + colX[j + span - 1][1] - cx;
        const c = cellAt(row.item, row.d, j), L = cellLines(kind, c, row.item.name);
        ctx.fillStyle = L ? '#ffffff' : c === 'X' ? '#F2F2F2' : '#FBFAF6'; ctx.fillRect(cx, y, cw, rowH);
        ctx.strokeStyle = '#C9BFA4'; ctx.strokeRect(cx, y, cw, rowH);
        if (L) {
          ctx.fillStyle = '#1B2333'; ctx.font = '600 12px Poppins, Arial';
          const a = wrapText(ctx, L[0], cw - 10).slice(0, 2); a.forEach((ln, k) => ctx.fillText(ln, cx + 5, y + 18 + k * 14));
          ctx.font = '11px Poppins, Arial'; ctx.fillStyle = '#5B6475';
          wrapText(ctx, L[1] || '', cw - 10).slice(0, 2).forEach((ln, k) => ctx.fillText(ln, cx + 5, y + 18 + a.length * 14 + k * 13));
        }
      }
    });
    ctx.fillStyle = '#667085'; ctx.font = '11px Poppins, Arial';
    ctx.fillText(`${state.data.school?.footer || CFG.brand || 'Timetables by Ireri Venture'} · saved ${new Date().toLocaleString('en-GB')}`, pad, height - 18);
    const blob = await new Promise(res => cv.toBlob(res, 'image/png'));
    const file = new File([blob], fname + '.png', { type: 'image/png' });
    try { if (navigator.canShare && navigator.canShare({ files: [file] })) { await navigator.share({ files: [file], title: fname }); return; } }
    catch (e) { if (e && e.name === 'AbortError') return; }
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = fname + '.png';
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    toast('Saved to your Downloads ✓');
  }

  // ------------------------------------------------------------------ sheets: menu, share, poster
  function openSheet(html) {
    closeSheet(); const d = document.createElement('div'); d.className = 'sheet-bg'; d.innerHTML = `<div class="sheet" role="dialog" aria-modal="true">${html}</div>`;
    d.addEventListener('click', e => { if (e.target === d || e.target.closest('[data-act="closeSheet"]')) closeSheet(); }); document.body.appendChild(d); requestAnimationFrame(() => d.classList.add('show'));
  }
  function closeSheet() { $$('.sheet-bg').forEach(n => n.remove()); }
  function openMenu() {
    openSheet(`<div class="grab"></div>
      <button class="mrow" data-act="refresh">${icon('refresh')}<span>Check for new timetable<small>${state.lastSync ? 'Last checked ' + ago(state.lastSync) : ''}</small></span></button>
      <button class="mrow" data-act="share">${icon('share')}<span>Share with colleagues<small>QR code, WhatsApp or copy link</small></span></button>
      ${!isStandalone() && (state.installEvt || isIOS()) ? `<button class="mrow" data-act="install">${icon('install')}<span>Install app<small>Add to your home screen</small></span></button>` : ''}
      <button class="mrow" data-act="about">${icon('info')}<span>About<small>${esc(CFG.brand || 'Timetables by Ireri Venture')}</small></span></button>
      <button class="btn ghost wide" data-act="closeSheet">Close</button>`);
  }
  function loadQR() { if (self.qrcode) return Promise.resolve(); return new Promise((res, rej) => { const s = document.createElement('script'); s.src = '/qrcode.js'; s.onload = res; s.onerror = rej; document.head.appendChild(s); }); }
  async function qrSvg(text) { try { await loadQR(); const qr = self.qrcode(0, 'M'); qr.addData(text); qr.make(); return qr.createSvgTag(6, 2); } catch { return ''; } }
  async function openShare() {
    const link = linkFor(), name = state.data?.school?.name || 'our school';
    const msg = `${name} timetables — open on your phone, it updates automatically: ${link}`;
    openSheet(`<div class="grab"></div><h3>Share with colleagues</h3><div class="qr" id="qrBox"><span class="muted">Loading QR code…</span></div>
      <p class="linktext">${esc(link)}</p>
      <div class="sharebtns"><a class="btn" href="https://wa.me/?text=${encodeURIComponent(msg)}" target="_blank" rel="noopener">WhatsApp</a>
      <button class="btn ghost" data-act="copy">Copy link</button>${navigator.share ? '<button class="btn ghost" data-act="nativeShare">More…</button>' : ''}</div>
      <a class="txt-btn center" href="${esc(link)}?poster=1" target="_blank" rel="noopener">${icon('print')} Printable poster for the staffroom</a>
      <button class="btn ghost wide" data-act="closeSheet">Close</button>`);
    const svg = await qrSvg(link); const box = $('#qrBox'); if (box) box.innerHTML = svg || '<span class="muted">QR code could not be drawn.</span>';
  }
  function openAbout() {
    openSheet(`<div class="grab"></div><h3>About</h3><p>${esc(state.data?.school?.name || '')} timetables. This app shows the latest version published by the school and updates itself when you open it, and keeps a copy for offline use.</p>
      <p class="muted">${esc(state.data?.school?.institution || '')}<br>${esc(CFG.brand || 'Timetables by Ireri Venture')}${CFG.contact ? '<br>' + esc(CFG.contact) : ''}<br>App version ${esc(CFG.build || '')}</p>
      <button class="btn ghost wide" data-act="closeSheet">Close</button>`);
  }
  async function renderPoster() {
    const link = linkFor(), name = state.data?.school?.name || '';
    document.body.classList.add('poster-mode');
    app.innerHTML = `<div class="poster"><div class="ptop"><div class="logo big"></div><div><h1>${esc(name || 'School')} Timetables</h1><p>On your phone · Always up to date · Works offline</p></div></div>
      <div class="pmain"><div class="pqr" id="pqr"></div><ol>
        <li><b>Scan</b> this QR code with your phone camera.</li>
        <li><b>Add to Home Screen</b> — Android: tap <b>Install</b>. iPhone: Share ⬆ → <b>Add to Home Screen</b>.</li>
        <li>Tap <b>My timetable</b>, find your name and tap <b>☆</b> to make it <b>My timetable</b>.</li></ol></div>
      <p class="plink">${esc(link)}</p><p class="pfoot">${esc(state.data?.school?.footer || CFG.brand || 'Timetables by Ireri Venture')}${CFG.contact ? ' · ' + esc(CFG.contact) : ''}</p>
      <button class="btn noprint" onclick="window.print()">Print poster</button></div>`;
    $('#pqr').innerHTML = await qrSvg(link);
  }

  // ------------------------------------------------------------------ events
  function stepItem(dir) {
    const r = route(); if (r.name !== 'view') return;
    const item = IDX.byId[r.id], sib = siblings(item), i = sib.findIndex(x => x.id === item.id) + dir;
    if (sib[i]) location.replace('#view/' + encodeURIComponent(sib[i].id));
  }
  document.addEventListener('click', async e => {
    const g = e.target.closest('[data-go]'); if (g) { go(g.dataset.go); return; }
    const b = e.target.closest('[data-act],[data-layout],[data-day],[data-sday],[data-slot],[data-grade],[data-freetab],[data-coverslot],[data-covert]');
    if (!b) return;
    const ds = b.dataset;
    if (ds.layout) { state.layout = ds.layout; render(); return; }
    if (ds.day != null) { state.day = +ds.day; state.coverSlot = null; render(); return; }
    if (ds.sday != null) { state.slot = { ...(state.slot || defaultSlot()), d: +ds.sday }; render(); return; }
    if (ds.slot != null) { state.slot = { ...(state.slot || defaultSlot()), j: +ds.slot }; render(); return; }
    if (ds.grade != null && route().name === 'master') { state.grade = ds.grade; render(); return; }
    if (ds.freetab) { store.set('freeTab', ds.freetab); render(); return; }
    if (ds.coverslot != null) { state.coverSlot = +ds.coverslot; render(); return; }
    if (ds.covert) { state.coverTeacher = ds.covert; state.coverPick = false; state.coverSlot = null; render(); return; }
    switch (ds.act) {
      case 'back': if (state.navDepth > 0) history.back(); else location.hash = ''; break;
      case 'prev': stepItem(-1); break;
      case 'next': stepItem(1); break;
      case 'save': toast('Preparing picture…', 1500); saveImage().catch(err => toast('Could not save: ' + err.message)); break;
      case 'me': {
        const item = IDX.byId[route().id];
        if (String(store.get('me')) === String(item.code)) { store.del('me'); toast('Removed from My timetable'); }
        else { store.set('me', item.code); toast('★ Saved as My timetable'); }
        render(); break;
      }
      case 'pickMe': state.query.teachers = ''; go('list/teachers/pick'); break;
      case 'coverWho': state.coverPick = true; state.coverSlot = null; render(); break;
      case 'seen': store.set('seen', state.data.version); renderBanners(); break;
      case 'hideInstall': store.set('hideInstallTip', true); renderBanners(); break;
      case 'install':
        closeSheet();
        if (state.installEvt) { state.installEvt.prompt(); const r = await state.installEvt.userChoice.catch(() => null); state.installEvt = null; if (r?.outcome === 'accepted') toast('Installed ✓'); renderBanners(); }
        else if (isIOS()) openSheet(`<div class="grab"></div><h3>Add to Home Screen</h3><ol class="steps"><li>Tap <b>Share ⬆</b> at the bottom of Safari.</li><li>Choose <b>Add to Home Screen</b>.</li><li>Tap <b>Add</b>.</li></ol><button class="btn wide" data-act="closeSheet">OK</button>`);
        break;
      case 'menu': openMenu(); break;
      case 'refresh': closeSheet(); toast('Checking…', 1200); await sync('manual'); if (state.online) toast('You have the latest timetable ✓'); break;
      case 'share': openShare(); break;
      case 'copy': try { await navigator.clipboard.writeText(linkFor()); toast('Link copied'); } catch { toast(linkFor(), 6000); } break;
      case 'nativeShare': try { await navigator.share({ title: 'School timetables', url: linkFor() }); } catch { } break;
      case 'about': openAbout(); break;
      case 'retry': state.error = null; renderEmpty(); sync('manual'); break;
    }
  });

  // swipe left/right in Day view = next / previous timetable
  let tx = 0, ty = 0, tt = 0;
  document.addEventListener('touchstart', e => { const t = e.touches[0]; tx = t.clientX; ty = t.clientY; tt = Date.now(); }, { passive: true });
  document.addEventListener('touchend', e => {
    if (!state.data || route().name !== 'view' || effectiveLayout() !== 'day' || e.target.closest('.daytabs')) return;
    const t = e.changedTouches[0], dx = t.clientX - tx, dy = t.clientY - ty;
    if (Date.now() - tt < 700 && Math.abs(dx) > 70 && Math.abs(dx) > Math.abs(dy) * 1.8) stepItem(dx < 0 ? 1 : -1);
  }, { passive: true });

  addEventListener('hashchange', () => {
    const r = route();
    state.navDepth = r.name === 'home' ? 0 : state.navDepth + 1;
    if (r.name !== 'cover') state.coverPick = false;
    if (state.data) render(); window.scrollTo(0, 0);
  });
  const mq = matchMedia('(orientation: landscape)');
  const onRotate = () => { if (state.data && route().name === 'view') { state.layout = 'auto'; render(); } };
  if (mq.addEventListener) mq.addEventListener('change', onRotate); else if (mq.addListener) mq.addListener(onRotate);
  addEventListener('resize', () => { if (state.data && route().name === 'view' && effectiveLayout() === 'week') fitGrid(); });
  addEventListener('online', () => { state.online = true; sync('online'); });
  addEventListener('offline', () => { state.online = false; renderStatus(); });
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState !== 'visible') return;
    if (Date.now() - state.lastSync > 60000) sync('visible');
    if (state.data && route().name === 'home') render();
  });
  setInterval(() => { if (document.visibilityState === 'visible' && state.data && route().name === 'home') { const c = $('.now-card'); if (c) c.outerHTML = nowCard(); } }, 60000);
  addEventListener('beforeinstallprompt', e => { e.preventDefault(); state.installEvt = e; if (state.data && route().name === 'home') renderBanners(); });
  addEventListener('appinstalled', () => { state.installEvt = null; toast('Installed ✓'); });
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(err => console.warn('SW', err));
  }

  // ------------------------------------------------------------------ start
  (async () => {
    const cached = await loadCached();
    if (cached && cached.bundle && cached.bundle.format === 2) setData(cached);
    if (state.data || POSTER) render();
    await sync('start');
    if (POSTER) renderPoster();
  })();
  self.__ireri = { state, sync, render, nowSlot: () => nowSlot() };
})();
