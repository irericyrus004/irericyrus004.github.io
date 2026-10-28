/* Ireri Timetables — teachers' phone app (FET edition) */
(() => {
  'use strict';

  const CFG = self.IRERI_CONFIG || {};
  // Built in. The same on every school's app and not taken from any setting.
  const LOCKED_BRAND = 'CREATED BY CYRUS IRERI';
  const LOCKED_CONTACT = '0720872582';
  const BRAND_LINE = LOCKED_BRAND + ' · ' + LOCKED_CONTACT;
  // Watermark over every timetable on screen and on every saved image. Built in, cannot be switched off.
  const WATERMARK = '© Cyrus Ireri';
  (function brandSplash() {                      // PREPFIX logo every time the app opens, on every device
    const t0 = Date.now();
    const hide = () => { const el = document.getElementById('brandsplash'); if (!el) return; el.classList.add('out'); setTimeout(() => el.remove(), 600); };
    addEventListener('load', () => setTimeout(hide, Math.max(0, 1700 - (Date.now() - t0))));
    setTimeout(hide, 4000);
  })();
  (function addBrandBar() {                      // frozen footer, always visible
    const add = () => { if (document.getElementById('brandbar')) return; const f = document.createElement('div'); f.id = 'brandbar';
      f.innerHTML = `<span>${LOCKED_BRAND}</span><button type="button" data-act="contact" aria-label="Contact Cyrus Ireri"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1A17 17 0 0 1 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1l-2.3 2.2Z"/></svg>${LOCKED_CONTACT}</button>`; document.body.appendChild(f); };
    if (document.body) add(); else document.addEventListener('DOMContentLoaded', add);
  })();
  (function addWatermarkStyle() {
    const st = document.createElement('style');
    st.textContent = `#tt::after{content:"${WATERMARK}";position:fixed;left:0;right:0;top:50%;transform:translateY(-50%) rotate(-30deg);` +
      `text-align:center;pointer-events:none;z-index:60;white-space:nowrap;font-family:Poppins,"Segoe UI",Arial,sans-serif;` +
      `font-weight:600;font-size:clamp(26px,7.5vw,52px);letter-spacing:.06em;color:rgba(18,40,76,.06)}` +
      `@media (prefers-color-scheme: dark){#tt::after{color:rgba(255,255,255,.06)}}` +
      `@media print{#tt::after{position:absolute}}`;
    (document.head || document.documentElement).appendChild(st);
  })();
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
    rotate: 'M16.48 2.52c3.27 1.55 5.61 4.72 5.97 8.48h1.5C23.44 4.84 18.29 0 12 0l-.66.03 3.81 3.81 1.33-1.32zm-6.25-.77c-.59-.59-1.54-.59-2.12 0L1.75 8.11c-.59.59-.59 1.54 0 2.12l12.02 12.02c.59.59 1.54.59 2.12 0l6.36-6.36c.59-.59.59-1.54 0-2.12L10.23 1.75zm4.6 19.44L2.81 9.17l6.36-6.36 12.02 12.02-6.36 6.36zm-7.31.29C4.25 19.94 1.91 16.76 1.55 13H.05C.56 19.16 5.71 24 12 24l.66-.03-3.81-3.81-1.33 1.32z',
    chart: 'M4 20V10h4v10H4Zm6 0V4h4v16h-4Zm6 0v-7h4v7h-4Z',
    wa: 'M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm5.3 14.2c-.2.6-1.3 1.2-1.8 1.2-.5.1-1 .2-3.3-.7-2.8-1.1-4.6-4-4.7-4.2-.1-.2-1.1-1.5-1.1-2.9 0-1.4.7-2 1-2.3.2-.3.5-.3.7-.3h.5c.2 0 .4 0 .6.5l.8 2c.1.2.1.4 0 .5l-.3.5-.4.4c-.1.2-.3.3-.1.6.2.3.8 1.4 1.8 2.2 1.2 1.1 2.2 1.4 2.5 1.6.3.1.5.1.7-.1l.9-1.1c.2-.3.4-.2.7-.1l1.9.9c.3.1.5.2.5.3.1.2.1.7-.1 1.3Z',
  };
  const icon = (n, cls = '') => `<svg class="ic ${cls}" viewBox="0 0 24 24" aria-hidden="true"><path d="${I[n] || n}"/></svg>`;

  // ------------------------------------------------------------------ schools directory (works with or without a school code)
  // Every school's app reads Cyrus Ireri's list of ALL registered schools (also schools on their own GitHub).
  const DIRECTORY = (self.IRERI_CONFIG && self.IRERI_CONFIG.directory) || 'https://irericyrus004.github.io/schools.json';
  const schoolHref = x => `${x.site && x.site.startsWith('https://') ? x.site.replace(/\/$/, '') : ''}/s/${encodeURIComponent(x.code)}/`;
  async function fetchSchools() {
    try {
      let r;
      try { r = await fetch(DIRECTORY + '?v=' + Date.now(), { cache: 'no-store' }); if (!r.ok) throw 0; }
      catch { r = await fetch('/schools.json?v=' + Date.now(), { cache: 'no-store' }); }
      if (!r.ok) throw new Error('x');
      const j = await r.json();
      try { localStorage.setItem('ireri:schools', JSON.stringify(j)); } catch { }
      return j;
    } catch { try { return JSON.parse(localStorage.getItem('ireri:schools') || 'null'); } catch { return null; } }
  }
  function schoolsListHTML(j, cur, q) {
    const list = ((j && j.schools) || []).filter(x => !q || `${x.name} ${x.institution}`.toLowerCase().includes(q.toLowerCase()));
    if (!j) return '<p class="muted center-t">Could not load the list. Check your connection.</p>';
    if (!list.length) return '<p class="muted center-t">No school matches.</p>';
    return list.map(x => `<div class="school ${x.code === cur ? 'mine' : ''}">
      <span class="av av-classes">${esc(String(x.name).replace(/[^A-Za-z0-9 ]/g, '').split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase() || 'S')}</span>
      <span class="nm"><b>${esc(x.name)}</b>${x.code === cur ? ' <i class="me-tag">Your school</i>' : ''}<small>${esc(x.institution || '')}${x.institution ? ' · ' : ''}${[Number.isFinite(x.teachers) ? x.teachers + ' teachers' : '', Number.isFinite(x.classes) ? x.classes + ' classes' : ''].filter(Boolean).join(' · ')}</small>
      ${x.updated ? `<small>Updated ${esc(fmtDate(x.updated))}</small>` : ''}</span>
      <a class="btn small" href="${esc(schoolHref(x))}">Open</a></div>`).join('');
  }
  function wireSchoolSearch(j, cur) {
    const inp = document.getElementById('sq'), box = document.getElementById('slist');
    if (inp && box) inp.addEventListener('input', () => { box.innerHTML = schoolsListHTML(j, cur, inp.value.trim()); });
  }
  async function renderRootDirectory() {
    const el = document.getElementById('app');
    el.innerHTML = `<div class="splash"><div class="splash-logo"></div><h2>School timetables</h2><p>Loading schools…</p></div>`;
    const j = await fetchSchools();
    const n = j && j.schools ? j.schools.length : 0;
    el.innerHTML = `<header class="top"><div class="brandrow"><div class="logo" aria-hidden="true"></div><div class="titles"><h1>PREPFIX Timetables</h1><p class="sub">${n} school${n === 1 ? '' : 's'} using this app</p></div></div></header>
      <main class="page wide"><p class="hint-box">Tap your school to open its timetables.</p>
      <div class="searchbox">${icon('search')}<input id="sq" type="search" autocomplete="off" placeholder="Search for your school…"></div>
      <div id="slist">${schoolsListHTML(j, null, '')}</div>
      <footer class="foot">${esc(BRAND_LINE)}</footer></main>`;
    wireSchoolSearch(j, null);
  }

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
    renderRootDirectory();
    return;
  }
  try { localStorage.setItem('ireri:last', CODE); } catch { }

  const state = {
    data: null, online: navigator.onLine, syncing: false, lastSync: 0, error: null, installEvt: null,
    layout: 'auto', day: null, slot: null, grade: 'all', query: {}, coverTeacher: null, coverSlot: null,
    coverPick: false, navDepth: 0, force: false, meet: { ids: [], q: '', k: 1, pm: false }, an: { tab: 'teachers', sort: 'name', subj: 'all', q: '', sm: 'form', sub: 'all', gr: 'all' },
  };
  let B = null;           // timetable data
  let IDX = null;         // derived indexes

  // ------------------------------------------------------------------ helpers
  const isStandalone = () => matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  const isIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const platformName = () => isIOS() ? 'ios' : /android/i.test(navigator.userAgent) ? 'android' : 'desktop';
  const linkFor = () => `${location.origin}/s/${encodeURIComponent(CODE)}/`;
  const isLandscape = () => state.force || matchMedia('(orientation: landscape)').matches || innerWidth >= 760;
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
    const grades = [...new Set(B.classes.map(c => gradeOf(c.name)).filter(Boolean))]; // keep the school's own order: 10, 11, 4 …
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
  function teachersText(codes, max = Infinity) {          // every teacher by NAME (code only when FET has no name)
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
  const subjHue = s => { const k = String(s || '').replace(/\s*\d+$/, '').trim().toLowerCase(); let h = 7; for (const ch of k) h = (h * 31 + ch.charCodeAt(0)) % 360; return h; };
  // FET's own subject colours (as exported), else a steady colour per subject
  const fetColour = subj => { const C = (B && B.colours) || {}, k = String(subj || '').trim().toUpperCase();
    return C[k] || C[k.split(/\s*[,+]\s*/)[0]] || C[k.replace(/\s*\d+$/, '')] || null; };
  const hlStyle = c => { if (!(isLesson(c) && c.s)) return ''; const f = fetColour(c.s);
    return f ? ` data-fc style="--hl:${subjHue(c.s)};--fb:${f[0]};--ff:${f[1]}"` : ` style="--hl:${subjHue(c.s)}"`; };
  // longest run of lessons with no class after lunch (3 or 4 in a row = a free afternoon)
  function afternoonFree(t, d) {
    const pm = IDX.lessons.filter(j => IDX.P[j].pm); if (!pm.length) return null;
    let best = [], cur = [];
    for (const j of pm) { const c = cellAt(t, d, j); if (c === '' || c === 'X') { cur.push(j); if (cur.length > best.length) best = cur.slice(); } else cur = []; }
    if (best.length < pm.length) return null;          // free afternoon = the WHOLE afternoon, lunch to end of day
    return { j0: best[0], j1: best[best.length - 1], n: best.length, full: best.length === pm.length };
  }
  const runLabel = r => r.full ? `Whole afternoon · ${IDX.P[r.j0].time.split('-')[0]}–${IDX.P[r.j1].time.split('-')[1] || ''}` : `${IDX.P[r.j0].label}–${IDX.P[r.j1].label} · ${r.n} free`;
  function candidates(item, d, j, c) {
    let span = 1; while ((item.grid[d] || [])[j + span] === '^') span++;
    const slots = Array.from({ length: span }, (_, k) => j + k);
    const subj = (c.s || '').replace(/\s*\d+$/, '').trim();
    let cls = (c.c || '').split(',').map(x => x.trim()).filter(Boolean);
    if (!cls.length && item.kind === 'classes') cls = [item.name];
    const ex = new Set(); if (item.kind === 'teachers') ex.add(item.id);
    String(c.t || '').split(',').map(x => x.trim()).filter(Boolean).forEach(cd => { const t = IDX.tByCode[cd]; if (t) ex.add(t.id); });
    const free = B.teachers.filter(t => !ex.has(t.id) && slots.every(k => cellAt(t, d, k) === ''))
      .map(t => ({ t, same: !!subj && teacherSubjects(t).has(subj), knows: cls.some(x => teacherClasses(t).has(x)), load: lessonsOnDay(t, d), pmfree: afternoonFree(t, d) }))
      .sort((a, b) => (b.same - a.same) || (b.knows - a.knows) || (a.load - b.load) || natural(a.t.code, b.t.code));
    return { span, slots, subj, cls, free };
  }
  function coverRows(free, d) {
    return free.map(x => `<li><button class="row" data-go="view/${esc(x.t.id)}"><span class="av av-teachers">${esc(String(x.t.code).slice(0, 4))}</span>
      <span class="nm"><b>${esc(teacherLabel(x.t))}</b><small>${plural(x.load, 'lesson')} on ${esc(dayLabel(d))}</small>
      <span class="badges">${x.same ? '<i class="bd g">Same subject</i>' : ''}${x.knows ? '<i class="bd b">Teaches this class</i>' : ''}${x.pmfree ? '<i class="bd y">Free afternoon</i>' : ''}</span></span>${icon('chev', 'chev')}</button></li>`).join('') || '<li class="empty">No teacher is free at that time.</li>';
  }
  function openCoverSheet(id, d, j) {
    const item = IDX.byId[id]; if (!item) return;
    const c = cellAt(item, d, j); if (!isLesson(c)) return;
    const r = candidates(item, d, j, c);
    const L = cellLines(item.kind === 'master' ? 'classes' : item.kind, c, item.name) || ['', ''];
    openSheet(`<div class="grab"></div><h3>Who can be there?</h3>
      <div class="cvinfo"><b>${esc(dayLabel(d))} · ${esc(pLabel(j))}${r.span > 1 ? ' · double lesson' : ''}</b><span>${esc(L[0])}${L[1] ? ' — ' + esc(L[1]) : ''}</span></div>
      <p class="muted small"><b>${r.free.length}</b> teacher${r.free.length === 1 ? ' is' : 's are'} free at this time. Best matches first. Tap a name to see their timetable.</p>
      <ul class="list cvlist">${coverRows(r.free, d)}</ul>
      <button class="btn ghost wide" data-act="closeSheet">Close</button>`);
  }
  function teacherSubjects(t) { const s = new Set(); t.grid.forEach(r => r.forEach(c => { if (isLesson(c) && c.s) s.add(c.s.replace(/\s*\d+$/, '').trim()); })); return s; }
  function teacherClasses(t) { const s = new Set(); t.grid.forEach(r => r.forEach(c => { if (isLesson(c) && c.c) c.c.split(',').forEach(x => s.add(x.trim())); })); return s; }

  // ------------------------------------------------------------------ data
  // Each school can have several timetables (e.g. KIANDERI, KIANDERI WEEKDAY, END TERM EXAM).
  const curTT = () => store.get('tt', '') || '';
  const cacheKey = tt => `/__data/${CODE}/${tt || 'main'}.json`;
  async function loadCached(tt = curTT()) {
    try { if ('caches' in self) { const c = await caches.open(DATA_CACHE); const r = await c.match(cacheKey(tt)); if (r) return await r.json(); } } catch { }
    try { const v = localStorage.getItem(`ireri:${CODE}:data3:${tt}`); return v ? JSON.parse(v) : null; } catch { return null; }
  }
  async function saveCached(obj) {
    const tt = obj.tt || '';
    const body = JSON.stringify(obj);
    try { if ('caches' in self) { const c = await caches.open(DATA_CACHE); await c.put(cacheKey(tt), new Response(body, { headers: { 'Content-Type': 'application/json' } })); return; } } catch { }
    try { localStorage.setItem(`ireri:${CODE}:data3:${tt}`, body); } catch { }
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
      const list = Array.isArray(meta.timetables) ? meta.timetables : null;
      state.tts = list || [];
      try { localStorage.setItem(`ireri:${CODE}:tts`, JSON.stringify(state.tts)); } catch { }
      if (list && !list.length) throw new NotFound('none');
      let tt = '', ver = meta.version, path = 'data.json';
      if (list) {
        const want = curTT();
        const t = list.find(x => x.id === want) || list[0];
        tt = t.id; ver = t.version; path = `t/${encodeURIComponent(t.id)}/data.json`;
        if (want !== tt) store.set('tt', tt);
      }
      if (!state.data || state.data.tt !== tt || state.data.version !== ver) {
        const switching = state.data && state.data.tt !== tt;
        const full = await getJson(path, ver);                       // the timetable itself
        setData({ tt, ttName: (full.timetable || {}).name || '', version: full.version || ver, school: { ...(full.school || {}), ...meta, note: (full.school || {}).note || '' }, bundle: full.bundle, savedAt: Date.now() });
        await saveCached(state.data);
        if (had && !switching) toast('Timetable updated to the latest version ✓');
        state.error = null; render();
      } else { state.data.school = { ...state.data.school, ...meta, note: state.data.school.note }; state.data.savedAt = Date.now(); saveCached(state.data); }
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
    if (parts[0] === 'analysis') return { name: 'analysis', id: parts[1] };
    if (parts[0] === 'meet') return { name: 'meet' };
    if (parts[0] === 'schools') return { name: 'schools' };
    return { name: parts[0] };
  }
  const go = h => { location.hash = h; };
  function render() {
    if (POSTER) return renderPoster();
    if ((state.full || state.force) && !['view', 'master'].includes(route().name)) releaseRotate();
    if (state.error === 'locked') return renderMsg('Timetables not available', 'This school\'s timetable service is switched off. Please contact the school office.', false);
    if (!state.data) return renderEmpty();
    const r = route();
    if (r.name === 'list') return renderList(r.kind, r.pick);
    if (r.name === 'view' && IDX.byId[r.id]) return renderViewer(r.id);
    if (r.name === 'analysis') { const k = r.id && IDX.byId[r.id] ? IDX.byId[r.id].kind : ''; return k === 'teachers' ? renderProfile(r.id) : k === 'classes' ? renderClassProfile(r.id) : renderAnalysis(); }
    if (r.name === 'meet') return renderMeet();
    if (r.name === 'schools') return renderSchools();
    if (r.name === 'master') return renderMaster();
    if (r.name === 'free') return renderFree();
    if (r.name === 'cover') return renderCover();
    if (r.name === 'where') return renderWhere();
    return renderHome();
  }
  function topBar(title, sub = '', right = '', html = '') {
    return `<header class="vtop"><button class="icon-btn" data-act="back" aria-label="Back">${icon('back')}</button>
      <div class="vtitles"><h2${html ? ' class="big"' : ''}>${html || esc(title)}</h2>${sub ? `<p>${sub}</p>` : ''}</div>${right || '<span class="icon-btn ghost"></span>'}</header>`;
  }
  function renderStatus() {
    const el = $('#status'); if (!el || !state.data) return;
    let s = `${state.data.ttName ? esc(state.data.ttName) + ' · ' : ''}Updated ${esc(fmtDate(B?.published || state.data.school?.updated))}`;
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
    else when = `${dayLabel(n.d)} · CURRENT: ${pLabel(n.j)}`;
    let mine = '';
    if (me && n.d >= 0) {
      const cur = n.status === 'lesson' ? cellAt(me, n.d, n.j) : null;
      const after = n.status === 'after' ? 999 : n.status === 'before' ? n.j - 1 : n.j;
      const nexts = IDX.lessons.filter(j => j > after && isLesson(cellAt(me, n.d, j)) && !isCont(me, n.d, j)).slice(0, 2);
      const L = cur && isLesson(cur) ? cellLines('teachers', cur) : null;
      const curTxt = cur === null ? '' : L ? `<b>${esc(L[0])}</b> ${esc(L[1])}` : cur === 'X' ? 'Not available' : '<b class="ok">Free</b>';
      const nextHTML = nexts.map((j, i) => { const N = cellLines('teachers', cellAt(me, n.d, j));
        return `<span class="nx"><i>${i + 1}</i><b>${esc(N[0])}</b> ${esc(N[1])} <em>${esc(pLabel(j))}</em></span>`; }).join('');
      mine = `<div class="now-me">
        ${curTxt ? `<div class="nowcur"><small>● CURRENT LESSON</small><span>${curTxt}</span></div>` : ''}
        <div><small>${nexts.length > 1 ? 'NEXT 2 LESSONS' : 'NEXT LESSON'}</small>${nextHTML || '<span>No more lessons today</span>'}</div></div>`;
    } else if (!me) {
      mine = `<button class="now-set" data-act="pickMe">${icon('starO')} Choose “My timetable” to see your lessons here</button>`;
    }
    const rem = me ? `<button class="remrow ${remOn() ? 'on' : ''}" data-act="remToggle" role="switch" aria-checked="${remOn()}"><span>⏰ <b>Lesson reminder</b><small>${REMIND_MIN} minutes before each of your lessons</small></span><i class="sw"><em></em></i></button>` : '';
    return `<section class="now-card"><div class="now-when">${icon('clock', 'tiny')}<span>${esc(when)}</span></div>${mine}${rem}</section>`;
  }

  // ------------------------------------------------------------------ LESSON REMINDER (alarm 10 minutes before a lesson)
  const REMIND_MIN = 10;
  const remOn = () => !!store.get('remind', false);
  const fired = new Set();
  function myLessonsOn(me, d) {           // [{j, start, end, lines}]
    return IDX.lessons.filter(j => isLesson(cellAt(me, d, j)) && !isCont(me, d, j) && IDX.P[j].start != null).map(j => {
      let k = j; while ((me.grid[d] || [])[k + 1] === '^') k++;
      return { j, start: IDX.P[j].start, end: IDX.P[k].end ?? IDX.P[j].end, lines: cellLines('teachers', cellAt(me, d, j)), cell: cellAt(me, d, j) };
    });
  }
  const hm = m => `${Math.floor(m / 60) > 12 ? Math.floor(m / 60) - 12 : Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}`;
  function checkReminders() {
    if (!remOn() || !state.data) return;
    const me = meTeacher(), d = todayIndex(); if (!me || d < 0) return;
    const now = nowMinutes(), day = new Date().toDateString();
    for (const L of myLessonsOn(me, d)) {
      const key = `${day}|${state.data.tt}|${L.j}`;
      if (fired.has(key) || store.get('fired:' + key)) continue;
      if (now >= L.start - REMIND_MIN && now < L.start) { fired.add(key); store.set('fired:' + key, 1); fireReminder(L, L.start - now); }
    }
  }
  function beep() {
    try {
      const A = new (window.AudioContext || window.webkitAudioContext)(); let t = A.currentTime;
      [880, 660, 880, 660, 988].forEach((f, i) => { const o = A.createOscillator(), g = A.createGain(); o.type = 'sine'; o.frequency.value = f;
        g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.35, t + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.32);
        o.connect(g); g.connect(A.destination); o.start(t); o.stop(t + 0.34); t += 0.38; });
    } catch { }
  }
  function fireReminder(L, mins) {
    const title = `⏰ Lesson in ${mins} minute${mins === 1 ? '' : 's'} — ${IDX.P[L.j].label} at ${hm(L.start)}`;
    const body = `${L.lines[0]}${L.lines[1] ? ' · ' + L.lines[1] : ''}${L.cell.r ? ' · ' + L.cell.r : ''}`;
    try { navigator.vibrate && navigator.vibrate([400, 150, 400, 150, 800]); } catch { }
    try {
      if ('Notification' in window && Notification.permission === 'granted' && navigator.serviceWorker) {
        navigator.serviceWorker.ready.then(reg => reg.showNotification(title, { body, icon: '/icons/icon-192.png', badge: '/icons/badge-96.png', tag: 'lesson-' + L.j, renotify: true, requireInteraction: true, vibrate: [400, 150, 400, 150, 800], data: { url: location.href } })).catch(() => { });
      }
    } catch { }
    if (document.visibilityState === 'visible') {
      beep();
      $$('.alarm-bg').forEach(n => n.remove());               // its own layer, above anything else on screen
      const box = document.createElement('div'); box.className = 'alarm-bg';
      box.innerHTML = `<div class="alarm" role="alertdialog"><div class="abell">⏰</div><h3>Lesson in ${mins} minute${mins === 1 ? '' : 's'}</h3>
        <p class="alesson"><b>${esc(L.lines[0])}</b>${L.lines[1] ? `<span>${esc(L.lines[1])}</span>` : ''}</p>
        <p class="awhen">${esc(IDX.P[L.j].label)} · ${esc(IDX.P[L.j].time)}${L.cell.r ? ' · ' + esc(L.cell.r) : ''}</p>
        <button class="btn wide" type="button">OK</button></div>`;
      box.querySelector('button').addEventListener('click', () => box.remove());
      document.body.appendChild(box);
    }
  }
  async function remToggle() {
    if (remOn()) { store.set('remind', false); toast('Lesson reminder OFF'); render(); return; }
    store.set('remind', true);
    let perm = 'default';
    try { if ('Notification' in window) perm = Notification.permission === 'granted' ? 'granted' : await Notification.requestPermission(); } catch { }
    render();
    openSheet(`<div class="grab"></div><h3>⏰ Lesson reminder is ON</h3>
      <p>You will get an alarm <b>${REMIND_MIN} minutes before each of your lessons</b> (${esc(teacherLabel(meTeacher()))}), with sound and vibration.</p>
      ${perm === 'granted' ? '<p class="okline">✓ Notifications allowed</p>' : '<p class="warnline">Notifications are blocked — allow them for this app in your phone settings so the reminder shows on the lock screen.</p>'}
      <p class="muted small">Phones can stop a closed app from running. To be sure you never miss an alarm — even when the app is closed — also add your lessons to your phone's calendar:</p>
      <button class="btn wide" data-act="remCal">📅 Add my lessons to my phone calendar</button>
      <button class="btn ghost wide" data-act="closeSheet">Done</button>`);
    checkReminders();
  }
  function remCalendar() {
    const me = meTeacher(); if (!me) return;
    const pad = n => String(n).padStart(2, '0'), stamp = new Date();
    const dt = (date, m) => `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}T${pad(Math.floor(m / 60))}${pad(m % 60)}00`;
    const escI = t => String(t || '').replace(/\\/g, '\\\\').replace(/[,;]/g, m => '\\' + m).replace(/\n/g, ' ');
    const ev = [];
    IDX.D.forEach((dd, d) => {
      if (dd.wd < 0) return;
      const date = new Date(); date.setHours(0, 0, 0, 0);
      while (date.getDay() !== dd.wd) date.setDate(date.getDate() + 1);
      myLessonsOn(me, d).forEach(L => {
        ev.push(['BEGIN:VEVENT', `UID:prepfix-${state.data.tt}-${me.code}-${d}-${L.j}@prepfix`, `DTSTAMP:${dt(stamp, stamp.getHours() * 60 + stamp.getMinutes())}`,
          `DTSTART:${dt(date, L.start)}`, `DTEND:${dt(date, L.end || L.start + 40)}`, 'RRULE:FREQ=WEEKLY;COUNT=14',
          `SUMMARY:${escI(`${IDX.P[L.j].label} · ${L.lines[0]}${L.lines[1] ? ' ' + L.lines[1] : ''}`)}`,
          L.cell.r ? `LOCATION:${escI(L.cell.r)}` : '', `DESCRIPTION:${escI(`${state.data.school?.name || ''} · ${state.data.ttName || ''} · PREPFIX`)}`,
          'BEGIN:VALARM', 'ACTION:DISPLAY', `DESCRIPTION:${escI('Lesson in ' + REMIND_MIN + ' minutes: ' + L.lines[0])}`, `TRIGGER:-PT${REMIND_MIN}M`, 'END:VALARM', 'END:VEVENT'].filter(Boolean).join('\r\n'));
      });
    });
    const ics = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//PREPFIX//Timetables//EN', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', `X-WR-CALNAME:PREPFIX · ${escI(teacherLabel(me))}`, ...ev, 'END:VCALENDAR'].join('\r\n');
    const blob = new Blob([ics], { type: 'text/calendar' }), a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = `PREPFIX reminders - ${teacherLabel(me).replace(/[\\/:*?"<>|]+/g, ' ').replace(/[.\s]+$/, '')}.ics`;
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    toast(`Calendar file saved — open it to add ${ev.length} weekly lessons with a ${REMIND_MIN}-minute alarm`, 5000);
  }
  function schoolsCount() {
    try { const j = JSON.parse(localStorage.getItem('ireri:schools') || 'null'); const n = j && j.schools ? j.schools.length : 0; if (n) return `${n} school${n === 1 ? '' : 's'}`; } catch { }
    fetchSchools().then(j => { const el = document.querySelector('.t-schools small'); if (el && j && j.schools) el.textContent = `${j.schools.length} school${j.schools.length === 1 ? '' : 's'}`; });
    return 'See all schools';
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
      ['meet', 'classes', 'Meeting finder', 'When are teachers all free', 'meet'],
      ['analysis', 'chart', 'Staff analysis', 'Subjects, classes & load', 'analysis'],
      ['schools', 'grid', 'Schools using this app', schoolsCount(), 'schools'],
    ];
    app.innerHTML = `
      <header class="top"><div class="brandrow">
        <div class="logo" aria-hidden="true"></div>
        <div class="titles"><h1>${esc(name)}</h1><p class="sub" id="status"></p></div>
        <button class="icon-btn" data-act="menu" aria-label="Menu">${icon('more')}</button></div>
      </header>
      <main class="home">
        ${ttSwitcher()}
        ${instBlock()}
        <div id="banners"></div>
        ${nowCard()}
        <nav class="tiles">${tiles.map(([k, ic, t, s, href]) => `
          <button class="tile t-${k}" ${href ? `data-go="${href}"` : 'data-act="pickMe"'}>
            <span class="tic">${icon(ic)}</span><strong>${esc(t)}</strong><small>${esc(s)}</small></button>`).join('')}
        </nav>
        <footer class="foot">${esc(BRAND_LINE)}</footer>
      </main>`;
    renderStatus(); renderBanners();
    const on = $('.ttchip.on'); if (on && on.scrollIntoView) on.scrollIntoView({ inline: 'center', block: 'nearest' });
  }
  // The school's name and term exactly as in FET, e.g. ST. BARBARA KIANDERI SEN. SCHOOL / TERM 1 2027 TIMETABLE
  function instLines() {
    if (B && Array.isArray(B.institution_lines) && B.institution_lines.length > 1) return B.institution_lines;
    const whole = String((B && B.institution) || state.data?.school?.institution || '').replace(/\bSCH\b\.?/g, 'SCHOOL').toUpperCase();
    if (!whole) return [];
    const m = whole.match(/\s(TERM\b.*|END\b.*|\d{4}\b.*TIMETABLE.*)$/);
    return m ? [whole.slice(0, m.index).trim(), m[1].trim()] : [whole];
  }
  function instBlock(extra = '') {
    const L = instLines();
    if (!L.length) return '';
    return `<div class="inst ${extra}"><b>${esc(L[0])}</b>${L.slice(1).map(x => `<span>${esc(x)}</span>`).join('')}</div>`;
  }
  function ttSwitcher() {
    const list = state.tts || [];
    if (list.length < 2) return state.data && state.data.ttName ? `<p class="ttone">${esc(state.data.ttName)}</p>` : '';
    return `<div class="ttlist" role="list" aria-label="Choose timetable"><h3 class="ttl-h">Timetables published · tap one to open</h3>${list.map(t => { const on = t.id === state.data.tt;
      return `<button class="ttrow ${on ? 'on' : ''}" data-tt="${esc(t.id)}" role="listitem"><span class="ttdot">${on ? '✓' : ''}</span><span class="ttn"><b>${esc(t.name)}</b><small>${t.updated ? 'Updated ' + esc(fmtDate(t.updated)) : ''}</small></span>${isNewTT(t) ? '<em class="ttnew">NEW</em>' : ''}${on ? '<em class="ttshow">Showing</em>' : icon('chev', 'chev')}</button>`; }).join('')}</div>`;
  }
  const seenMap = () => store.get('seenTT', {}) || {};
  const isNewTT = t => seenMap()[t.id] !== t.version;
  async function switchTT(id) {
    if (!id || (state.data && state.data.tt === id)) return;
    store.set('tt', id);
    const cached = await loadCached(id);
    if (cached && cached.bundle && cached.bundle.format === 2 && cached.tt === id) { setData(cached); render(); }
    else { toast('Loading timetable…', 1500); }
    await sync('switch');
    render();
  }
  function renderBanners() {
    const box = $('#banners'); if (!box || !state.data) return;
    const out = [];
    const fresh = (state.tts && state.tts.length ? state.tts : [{ id: state.data.tt, version: state.data.version, name: state.data.ttName, updated: B.published, note: state.data.school?.note }]).filter(isNewTT);
    if (fresh.length) {
      const items = fresh.map(t => `<b>${esc(t.name || 'Timetable')}</b> · ${esc(fmtDate(t.updated))}${t.note ? ' — ' + esc(t.note) : ''}`).join('<br>');
      out.push(`<div class="banner new"><div><strong>🆕 ${fresh.length > 1 ? 'New timetables published' : 'New timetable published'}</strong><span>${items}</span></div><button class="txt-btn" data-act="seen">Got it</button></div>`);
    }
    if (!isStandalone() && !store.get('hideInstallTip')) {
      if (state.installEvt) out.push(`<div class="banner tip"><div>${icon('install')}<span><strong>Install this app</strong> for one-tap access, even offline.</span></div><div class="banner-actions"><button class="btn small" data-act="install">Install</button><button class="txt-btn" data-act="getapp">Other devices</button><button class="txt-btn" data-act="hideInstall">Later</button></div></div>`);
      else out.push(`<div class="banner tip"><div>${icon('install')}<span><strong>Get the app</strong> on your Android, iPhone or computer — one tap, works offline.</span></div><div class="banner-actions"><button class="btn small" data-act="getapp">Get the app</button><button class="txt-btn" data-act="hideInstall">Later</button></div></div>`);
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
      let rows = listItems(kind);
      if (kind === 'teachers') {                       // ★ My timetable always comes first
        const mine = rows.find(x => String(x.code) === me);
        if (mine) rows = [mine, ...rows.filter(x => x !== mine)];
      }
      $('#list').innerHTML = rows.length ? rows.map(x => `
        <li${kind === 'teachers' && String(x.code) === me ? ' class="mine"' : ''}><button class="row" data-go="view/${esc(x.id)}">
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
    const titleHTML = kind === 'teachers' ? `<span class="tcode">${esc(item.code)}</span>${esc(title)}` : '';
    if (state.day == null) state.day = Math.max(0, todayIndex());
    const layout = effectiveLayout();
    document.title = title + ' · Timetable';
    app.innerHTML = `
      ${topBar(title, sub, kind === 'teachers' ? `<button class="icon-btn star ${isMe ? 'on' : ''}" data-act="me" aria-label="My timetable">${icon(isMe ? 'star' : 'starO')}</button>` : '', titleHTML)}
      <div class="vbar">
        <div class="seg"><button class="${layout === 'day' ? 'on' : ''}" data-layout="day">Day</button><button class="${layout === 'week' ? 'on' : ''}" data-layout="week">Week</button></div>
        <button class="btn small rot" data-act="rotate" aria-label="Rotate">${icon('rotate')} <span>${state.full ? 'Exit full screen' : 'Rotate'}</span></button>
        ${kind === 'teachers' ? `<button class="btn small ghost" data-go="analysis/${esc(item.id)}">${icon('chart')} Profile</button>` : ''}<button class="btn small ghost" data-act="save">${icon('save')} Save</button>
      </div>
      <main class="tt" id="tt">${instBlock('small')}${layout === 'day' ? dayView(item) : weekGrid(item)}</main>
      <div class="vtools">
        <button class="icon-btn" data-act="prev" ${idx <= 0 ? 'disabled' : ''} aria-label="Previous">${icon('prev')}</button>
        <span class="vcount">${idx > 0 ? sibName(sib[idx - 1]) : ''}</span><span class="vsep">${idx + 1}/${sib.length}</span><span class="vcount r">${idx < sib.length - 1 ? sibName(sib[idx + 1]) : ''}</span>
        <button class="icon-btn" data-act="next" ${idx >= sib.length - 1 ? 'disabled' : ''} aria-label="Next">${icon('next')}</button>
      </div>`;
    if (layout === 'week') fitGrid();
  }
  // ROTATE = full-screen landscape, whatever the phone's auto-rotate setting. The whole week fits on the screen.
  function applyForce() {
    if (!state.full) return;
    const portrait = innerHeight > innerWidth;
    state.force = portrait; document.body.classList.toggle('force-land', portrait);
  }
  function releaseRotate() {
    try { screen.orientation && screen.orientation.unlock && screen.orientation.unlock(); } catch { }
    try { if (document.fullscreenElement && document.exitFullscreen) document.exitFullscreen().catch(() => { }); } catch { }
    state.full = false; state.force = false; document.body.classList.remove('force-land', 'fullv');
  }
  async function toggleRotate() {
    if (state.full) { releaseRotate(); if (route().name === 'view') state.layout = 'day'; render(); return; }
    state.full = true; state.layout = 'week'; document.body.classList.add('fullv');
    try { const el = document.documentElement; if (el.requestFullscreen) await el.requestFullscreen({ navigationUI: 'hide' }); } catch { }
    try { if (screen.orientation && screen.orientation.lock) await screen.orientation.lock('landscape'); } catch { }
    applyForce(); render();
    setTimeout(() => { applyForce(); fitGrid(); }, 350);
  }
  const sibName = x => x.kind === 'teachers' ? `<i class="sc">${esc(x.code)}</i><span>${esc(teacherLabel(x))}</span>` : `<span>${esc(x.name)}</span>`;
  const nameOf = x => x.kind === 'teachers' ? tLabel(x) : x.name;
  function dayTabs(sel, attr = 'day') {
    const today = todayIndex();
    return `<div class="daytabs">${IDX.D.map((d, i) => `<button class="dc${i % 5} ${i === sel ? 'on' : ''}" data-${attr}="${i}">${esc(d.label.slice(0, 3))}${i === today ? '<i></i>' : ''}</button>`).join('')}</div>`;
  }
  function dayView(item) {
    const d = state.day, n = nowSlot();
    const rows = IDX.P.map((p, j) => {
      const isNow = n.d === d && n.j === j && (n.status === 'lesson' || n.status === 'break');
      const isNext = n.d === d && n.j === j && (n.status === 'before' || n.status === 'between');
      const tag = isNow ? '<span class="curtag">● CURRENT</span>' : isNext ? '<span class="nexttag">NEXT</span>' : '';
      if (p.brk) return `<li class="brk${isNow ? ' now' : ''}"><span>${esc(p.label)}${tag}</span><em>${esc(p.time)}</em></li>`;
      const cls = (isNow ? 'now' : isNext ? 'next' : '') + (p.pm ? ' pm' : '');
      if (isCont(item, d, j)) return `<li class="cont ${cls}"><div class="pt"><b>${esc(p.label)}</b><em>${esc(p.time)}</em></div><div class="pc">${tag}<span class="muted">↳ continues (double lesson)</span></div></li>`;
      const c = cellAt(item, d, j), L = cellLines(item.kind, c, item.name);
      return `<li class="${cls}${L ? ' has tap' : ''}"${L ? ` data-cv="${esc(item.id)}|${d}|${j}"` : ''}${hlStyle(c)}><div class="pt"><b>${esc(p.label)}</b><em>${esc(p.time)}</em></div>
        <div class="pc">${tag}${L ? `<strong>${esc(L[0])}</strong>${L[1] ? `<small>${esc(L[1])}</small>` : ''}${isDoubleStart(item, d, j) ? '<span class="dbl">double</span>' : ''}` : c === 'X' ? '<span class="muted">Not available</span>' : '<span class="freec">Free</span>'}</div></li>`;
    }).join('');
    return `${dayTabs(d)}<ul class="dayview dv-${item.kind}">${rows}</ul><p class="swipe-hint"><b>Tap a lesson</b> to see who can be there · swipe for the next ${item.kind === 'teachers' ? 'teacher' : item.kind === 'classes' ? 'class' : 'timetable'} · press <b>Rotate</b> for the whole week</p>`;
  }
  function headCells(d, n) {
    return IDX.P.map((p, j) => `<th class="${p.brk ? 'b' : p.pm ? 'pmh' : 'amh'}${n.d === d && n.j === j ? ' nowcol' : ''}">${n.d === d && n.j === j && !p.brk ? '<span class="curtag sm">CURRENT</span>' : ''}${p.brk ? brkHead(p) : `<b>${esc(p.label)}</b><small>${esc(p.time)}</small>`}</th>`).join('');
  }
  // Breaks: name written downwards, one letter per line, sized to fit the column height
  function stackText(label, nrows, rowH) {
    const words = String(label || 'BREAK').toUpperCase().split(/\s+/).filter(Boolean);
    const units = words.reduce((t, w) => t + w.length, 0) + (words.length - 1) * 0.6;
    const px = Math.max(7, Math.min(13, Math.floor((nrows * rowH - 8) / (units * 1.12))));
    return `<div class="stk" style="font-size:${px}px">${words.map(w => [...w].map(ch => `<i>${esc(ch)}</i>`).join('')).join('<i class="sp"></i>')}</div>`;
  }
  const brkTimes = p => { const t = String(p.time || '').split('-'); return t.length === 2 ? `<span class="bt"><b>${esc(t[0])}</b><i>–</i><b>${esc(t[1])}</b></span>` : ''; };
  function brkHead(p) { return brkTimes(p) || `<span class="bt"><b>—</b></span>`; }
  function rowCells(item, kind, d, n, ri = 0, nrows = 1, rowH = 46) {
    let tds = '';
    for (let j = 0; j < IDX.P.length; j++) {
      if (IDX.P[j].brk) { if (ri === 0) tds += `<td class="b bl" rowspan="${nrows}">${stackText(IDX.P[j].label, nrows, rowH)}</td>`; continue; }
      if (isCont(item, d, j)) continue;
      let span = 1; while ((item.grid[d] || [])[j + span] === '^') span++;
      const c = cellAt(item, d, j), L = cellLines(kind, c, item.name);
      const nowc = n.d === d && n.j >= j && n.j < j + span ? ' now' : '';
      tds += `<td${span > 1 ? ` colspan="${span}"` : ''}${L ? ` data-cv="${esc(item.id)}|${d}|${j}"` : ''}${hlStyle(c)} class="${L ? 'l' : c === 'X' ? 'x' : 'f'}${IDX.P[j].pm ? ' pmc' : ''}${nowc}">${nowc && n.status === 'lesson' ? '<span class="curtag sm">● CURRENT</span>' : ''}${L ? `<b>${esc(L[0])}</b>${L[1] ? `<small>${esc(L[1])}</small>` : ''}` : ''}</td>`;
    }
    return tds;
  }
  function weekGrid(item) {
    const n = nowSlot();
    const body = IDX.D.map((dd, d) => `<tr class="dc${d % 5} ${n.d === d ? 'today' : ''}"><th>${esc(dd.label)}${n.d === d ? '<small>today</small>' : ''}</th>${rowCells(item, item.kind, d, n, d, IDX.D.length, 46)}</tr>`).join('');
    return `<div class="gridwrap" id="gridwrap"><table class="wk" id="wk"><thead><tr><th></th>${headCells(-9, { d: -1 })}</tr></thead><tbody>${body}</tbody></table></div>`;
  }
  function fitGrid() {
    const wrap = $('#gridwrap'), tb = $('#wk'); if (!wrap || !tb) return;
    tb.style.zoom = 1; tb.style.width = '';
    if (state.full) {                                   // whole week on one screen: fill the width, fit the height
      const W = wrap.clientWidth - 2, H = wrap.clientHeight - 2, rows = $$('tbody tr', tb);
      rows.forEach(r => { r.style.height = ''; });
      const at = z => { tb.style.zoom = z; tb.style.width = (W / z) + 'px'; return tb.offsetHeight * z; };
      let lo = 0.2, hi = 1.5;                            // largest size at which the whole week still fits
      for (let i = 0; i < 12; i++) { const mid = (lo + hi) / 2; if (at(mid) <= H) lo = mid; else hi = mid; }
      const MIN = 0.85;                                  // never too small to read: below this, scroll instead
      if (lo < MIN) { tb.style.zoom = MIN; tb.style.width = ''; tb.style.minWidth = (W / MIN) + 'px'; wrap.classList.add('scroll2'); return; }
      wrap.classList.remove('scroll2'); tb.style.minWidth = '';
      const z = lo, h = at(z);
      if (h < H - 4 && rows.length) {                   // spread the rows to use the whole height
        const extra = (H - h) / z / rows.length;
        rows.forEach(r => { r.style.height = (r.offsetHeight + extra) + 'px'; });
      }
      return;
    }
    const z = Math.min(1, (wrap.clientWidth - 2) / tb.scrollWidth);
    if (z < 1) tb.style.zoom = Math.max(isLandscape() ? 0.55 : 0.62, z);
  }

  // ------------------------------------------------------------------ MASTER — day by day
  function renderMaster() {
    if (state.day == null) state.day = Math.max(0, todayIndex());
    const d = state.day, n = nowSlot();
    const list = B.master.filter(m => state.grade === 'all' || gradeOf(m.name) === state.grade);
    const body = list.map((m, i) => `<tr class="${i > 0 && gradeOf(list[i - 1].name) !== gradeOf(m.name) ? 'gstart' : ''}"><th>${esc(m.name)}</th>${rowCells(m, 'master', d, n, i, list.length, 34)}</tr>`).join('');
    document.title = 'Master · ' + dayLabel(d);
    app.innerHTML = `${topBar('Master timetable', esc(dayLabel(d)) + ' · all classes', `<button class="btn small rot" data-act="rotate" aria-label="Rotate">${icon('rotate')} <span>${state.full ? 'Exit' : 'Rotate'}</span></button><button class="icon-btn" data-act="save" aria-label="Save">${icon('save')}</button>`)}
      <div class="mbar">${dayTabs(d)}${gradeChips()}</div>
      <main class="tt"><div class="gridwrap" id="gridwrap"><table class="wk master dc${d % 5}" id="wk"><thead><tr><th>Class</th>${headCells(d, n)}</tr></thead><tbody>${body}</tbody></table></div>
      <p class="swipe-hint">Slide the table sideways · press Rotate to see the whole day on one screen</p></main>`;
    if (state.full) fitGrid();
  }

  // ------------------------------------------------------------------ FREE TEACHERS + FREE AFTERNOON
  function slotPicker(sel) {
    const n = nowSlot(), sd = (state.slot || {}).d;
    const curJ = n.status === 'lesson' && n.d === sd ? n.j : -1;
    return `<div class="chips periods">${IDX.lessons.map(j => `<button class="chip ${sel === j ? 'on' : ''}${curJ === j ? ' cur' : ''}" data-slot="${j}">${curJ === j ? '<em>CURRENT</em>' : ''}${esc(IDX.P[j].label)}<small>${esc(IDX.P[j].time)}</small></button>`).join('')}</div>`;
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
      const me = meTeacher();
      const byDay = IDX.D.map((_, dd) => B.teachers.map(t => ({ t, r: afternoonFree(t, dd) })).filter(x => x.r)
        .sort((x, y) => (y.r.full - x.r.full) || (y.r.n - x.r.n) || natural(x.t.code, y.t.code)));
      const none = B.teachers.filter(t => !IDX.D.some((_, dd) => afternoonFree(t, dd)));
      const myFA = me ? IDX.D.map((_, dd) => dd).filter(dd => afternoonFree(me, dd)) : null;
      const nm = t => esc(t.name || 'Tr ' + t.code);
      inner = `${myFA ? `<div class="hint-box">Your free afternoons: <b>${myFA.length ? myFA.map(dayLabel).join(', ') : 'none this week'}</b></div>` : ''}
        ${IDX.D.map((dd, i) => `<h3 class="sect dsect dc${i % 5}">${esc(dd.label)} afternoon · ${byDay[i].length} free</h3>
          <div class="namegrid">${byDay[i].map(x => `<button data-go="view/${x.t.id}" class="${x.r.full ? 'full' : ''} ${me && me.id === x.t.id ? 'me' : ''}"><b>${nm(x.t)}</b><small>${esc(runLabel(x.r))}</small></button>`).join('') || '<span class="muted">Nobody</span>'}</div>`).join('')}
        ${none.length ? `<h3 class="sect warn">No free afternoon this week · ${none.length}</h3><div class="namegrid">${none.map(t => `<button data-go="view/${t.id}"><b>${nm(t)}</b></button>`).join('')}</div>` : ''}
        <p class="muted small">A free afternoon = no class at all from after lunch to the end of the day (${IDX.lessons.filter(j => IDX.P[j].pm).map(j => esc(IDX.P[j].label)).join(', ')}).</p>`;
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
      const c = cellAt(who, d, sel), r = candidates(who, d, sel, c);
      cands = `<h3 class="sect">2. Free teachers — ${r.free.length} can be there</h3><ul class="list">${coverRows(r.free, d)}</ul>`;
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
        <h3 class="sect">${esc(dayLabel(d))} · ${esc(pLabel(j))}${n.d === d && n.j === j && n.status === 'lesson' ? ' <span class="curtag">● CURRENT LESSON</span>' : ''}</h3>
        <ul class="list" id="list"></ul>
      </main>`;
    const draw = () => {
      const q = (state.query.where || '').toLowerCase();
      $('#list').innerHTML = B.teachers.filter(t => !q || `${t.code} ${t.name}`.toLowerCase().includes(q)).map(t => {
        const c = cellAt(t, d, j), L = cellLines('teachers', c);
        const cls = isLesson(c) ? classesText(c.c) : '', subj = isLesson(c) ? [c.s, c.g].filter(Boolean).join(' ') : '';
        return `<li><button class="row wrow" data-go="view/${t.id}"><span class="av av-teachers">${esc(String(t.code).slice(0, 4))}</span>
          <span class="nm"><b class="wname">${esc(teacherLabel(t))}</b>
          ${isLesson(c) ? `<span class="wh"><i class="wcls">${icon('classes')}${esc(cls || '—')}</i><i class="wsub"${hlStyle(c)}>${esc(subj || 'Lesson')}</i>${c.r ? `<i class="wroom">${esc(c.r)}</i>` : ''}</span>`
            : c === 'X' ? '<span class="wh"><i class="wx">Not available</i></span>' : '<span class="wh"><i class="wfree">Free</i></span>'}</span></button></li>`;
      }).join('') || '<li class="empty">No teacher matches.</li>';
    };
    draw();
    $('#q').addEventListener('input', e => { state.query.where = e.target.value; draw(); });
  }


  // ------------------------------------------------------------------ STAFF ANALYSIS (principal's view)
  const baseSubj = x => String(x || '').replace(/\s*\d+$/, '').trim() || 'Unnamed';
  const classOrder = () => { const m = {}; B.classes.forEach((c, i) => { m[c.name] = i; }); return m; };
  function analyse(t) {
    if (t._an) return t._an;
    const subj = {}, cls = {}, perDay = IDX.D.map(() => 0); let total = 0, doubles = 0;
    IDX.D.forEach((_, d) => IDX.lessons.forEach(j => {
      const c = cellAt(t, d, j); if (!isLesson(c)) return;
      total++; perDay[d]++;
      const sn = baseSubj(c.s);
      const S = subj[sn] || (subj[sn] = { name: sn, periods: 0, doubles: 0, classes: {} });
      S.periods++;
      if (!isCont(t, d, j) && isDoubleStart(t, d, j)) { S.doubles++; doubles++; }
      String(c.c || '').split(',').map(x => x.trim()).filter(Boolean).forEach(x => {
        S.classes[x] = (S.classes[x] || 0) + 1;
        const C = cls[x] || (cls[x] = { name: x, periods: 0, subjects: {} });
        C.periods++; C.subjects[sn] = (C.subjects[sn] || 0) + 1;
      });
    }));
    const ord = classOrder(), rank = n => ord[n] ?? 99999;
    const subjects = Object.values(subj).sort((a, b) => b.periods - a.periods || natural(a.name, b.name));
    subjects.forEach(S => { S.list = Object.entries(S.classes).sort((a, b) => rank(a[0]) - rank(b[0])); });
    const classes = Object.values(cls).sort((a, b) => rank(a.name) - rank(b.name));
    return (t._an = { total, doubles, perDay, subjects, classes });
  }
  const hueStyle = n => ` style="--hl:${subjHue(n)}"`;
  const clsText = list => list.map(([n, k]) => `${esc(n)} <i>(${k})</i>`).join(', ') || '<span class="muted">—</span>';
  function subjectIndex() {
    const m = {};
    B.teachers.forEach(t => analyse(t).subjects.forEach(S => {
      const e = m[S.name] || (m[S.name] = { name: S.name, periods: 0, teachers: [], classes: new Set() });
      e.periods += S.periods; e.teachers.push({ t, S }); S.list.forEach(([n]) => e.classes.add(n));
    }));
    return Object.values(m).sort((a, b) => natural(a.name, b.name));
  }
  function renderAnalysis() {
    const A = state.an, rows = B.teachers.map(t => ({ t, a: analyse(t) }));
    const loads = rows.map(r => r.a.total), max = Math.max(1, ...loads), sum = loads.reduce((x, y) => x + y, 0);
    const avg = rows.length ? Math.round(sum / rows.length * 10) / 10 : 0;
    const subs = subjectIndex();
    document.title = 'Staff analysis';
    app.innerHTML = `${topBar('Staff analysis', 'Subjects, classes and teaching load', `<button class="icon-btn" data-act="csv" aria-label="Download Excel">${icon('save')}</button>`)}
      <main class="page wide">
        <div class="stats"><div><b>${rows.length}</b><small>teachers</small></div><div><b>${sum}</b><small>lessons / week</small></div><div><b>${avg}</b><small>average load</small></div><div><b>${max}</b><small>highest load</small></div></div>
        <div class="seg wide-seg four"><button class="${A.tab === 'teachers' ? 'on' : ''}" data-antab="teachers">Teachers</button><button class="${A.tab === 'subjects' ? 'on' : ''}" data-antab="subjects">Subjects</button><button class="${A.tab === 'sessions' ? 'on' : ''}" data-antab="sessions">Sessions</button><button class="${A.tab === 'classes' ? 'on' : ''}" data-antab="classes">Classes</button></div>
        <div class="anbtns"><button class="btn small" data-act="csv">${icon('save')} Teachers (CSV)</button><button class="btn small ghost" data-act="print">${icon('print')} Print</button></div>
        <div id="anbody"></div>
      </main>`;
    const draw = () => {
      const box = $('#anbody'); if (!box) return;
      if (A.tab === 'sessions') return drawSessions(box);
      if (A.tab === 'classes') return drawClassList(box);
      if (A.tab === 'subjects') {
        box.innerHTML = `<div class="searchbox">${icon('search')}<input id="aq" type="search" placeholder="Search a subject…" value="${esc(A.q)}"></div><div id="alist"></div>`;
        const dr = () => {
          const q = (A.q || '').toLowerCase();
          $('#alist').innerHTML = subs.filter(x => !q || x.name.toLowerCase().includes(q)).map(x => `<section class="subcard"${hueStyle(x.name)}>
            <h3>${esc(x.name)}<span>${x.periods} lessons / week · ${x.teachers.length} teacher${x.teachers.length === 1 ? '' : 's'}</span></h3>
            <table class="atable"><thead><tr><th>Teacher</th><th>Classes (lessons)</th><th>Lessons</th></tr></thead><tbody>${x.teachers.sort((a, b) => b.S.periods - a.S.periods).map(({ t, S }) => `<tr data-go="analysis/${esc(t.id)}"><td><b>${esc(teacherLabel(t))}</b></td><td>${clsText(S.list)}</td><td class="n">${S.periods}</td></tr>`).join('')}</tbody></table></section>`).join('') || '<p class="muted">Nothing matches.</p>';
        };
        dr(); $('#aq').addEventListener('input', e => { A.q = e.target.value; dr(); });
        return;
      }
      box.innerHTML = `<div class="searchbox">${icon('search')}<input id="aq" type="search" placeholder="Search teacher or subject…" value="${esc(A.q)}"></div>
        <div class="chips" id="schips">${['all', ...subs.map(x => x.name)].map(n => `<button class="chip ${A.subj === n ? 'on' : ''}" data-s="${esc(n)}">${n === 'all' ? 'All subjects' : esc(n)}</button>`).join('')}</div>
        <div class="sortrow">Sort by <select id="asort"><option value="name">Teacher number / name</option><option value="high">Load: highest first</option><option value="low">Load: lowest first</option><option value="subj">Main subject</option></select></div>
        <div id="alist"></div>`;
      $('#asort').value = A.sort;
      const dr = () => {
        const q = (A.q || '').toLowerCase();
        let list = rows.filter(r => (A.subj === 'all' || r.a.subjects.some(S => S.name === A.subj)) &&
          (!q || `${r.t.code} ${r.t.name} ${r.a.subjects.map(S => S.name).join(' ')}`.toLowerCase().includes(q)));
        list = list.slice().sort((x, y) => A.sort === 'high' ? y.a.total - x.a.total : A.sort === 'low' ? x.a.total - y.a.total :
          A.sort === 'subj' ? natural(x.a.subjects[0]?.name || 'zzz', y.a.subjects[0]?.name || 'zzz') || natural(x.t.code, y.t.code) : natural(x.t.code, y.t.code));
        $('#alist').innerHTML = list.map(({ t, a }) => `<button class="acard" data-go="analysis/${esc(t.id)}">
          <div class="ahead"><span class="av av-teachers">${esc(String(t.code).slice(0, 4))}</span><span class="nm"><b>${esc(teacherLabel(t))}</b><small>${t.name ? 'No. ' + esc(t.code) + ' · ' : ''}${a.subjects.length} subject${a.subjects.length === 1 ? '' : 's'} · ${a.classes.length} class${a.classes.length === 1 ? '' : 'es'}</small></span>
          <span class="load"><b>${a.total}</b><small>lessons/wk</small></span></div>
          <div class="bar"><i style="width:${Math.round(a.total / max * 100)}%"></i></div>
          <div class="asubj">${a.subjects.map(S => `<em${hueStyle(S.name)}>${esc(S.name)} <b>${S.periods}</b></em>`).join('') || '<span class="muted">No lessons</span>'}</div>
          <div class="acls"><b>Classes:</b> ${a.classes.map(C => esc(C.name)).join(', ') || '—'}</div></button>`).join('') || '<p class="muted">No teacher matches.</p>';
      };
      dr();
      $('#aq').addEventListener('input', e => { A.q = e.target.value; dr(); });
      $('#asort').addEventListener('change', e => { A.sort = e.target.value; dr(); });
      $$('#schips .chip').forEach(b => b.addEventListener('click', () => { A.subj = b.dataset.s; $$('#schips .chip').forEach(x => x.classList.toggle('on', x === b)); dr(); }));
    };
    draw();
    $$('[data-antab]').forEach(b => b.addEventListener('click', () => { A.tab = b.dataset.antab; A.q = ''; renderAnalysis(); }));
  }

  // ------------------------------------------------------------------ SESSIONS per subject, FORM-wise and CLASS-wise + CLASS profiles
  const tShort = cd => { const t = IDX.tByCode[cd]; return t ? (t.name || (/^\d+$/.test(cd) ? 'Tr ' + cd : cd)) : cd; };
  function classModel() {
    if (IDX.cm) return IDX.cm;
    const subjSet = new Set();
    const classes = B.classes.map(c => {
      const subj = {}; let total = 0;
      IDX.D.forEach((_, d) => IDX.lessons.forEach(j => {
        const c0 = cellAt(c, d, j); if (!isLesson(c0)) return;
        total++; const sn = baseSubj(c0.s); subjSet.add(sn);
        const S = subj[sn] || (subj[sn] = { name: sn, periods: 0, teachers: {} }); S.periods++;
        String(c0.t || '').split(',').map(x => x.trim()).filter(Boolean).forEach(cd => { S.teachers[cd] = (S.teachers[cd] || 0) + 1; });
      }));
      return { item: c, id: c.id, name: c.name, grade: gradeOf(c.name), subj, total };
    });
    const grades = [...IDX.grades]; if (classes.some(c => !c.grade)) grades.push('');
    const groups = grades.map(g => ({ g, label: g ? 'Grade ' + g : 'Other', cls: classes.filter(c => c.grade === g) })).filter(x => x.cls.length);
    return (IDX.cm = { classes, groups, subjects: [...subjSet].sort(natural) });
  }
  const sess = (c, sn) => c.subj[sn] ? c.subj[sn].periods : 0;
  const teachersOf = (c, sn, withN) => { const S = c.subj[sn]; if (!S) return '<span class="muted">—</span>'; const e = Object.entries(S.teachers).sort((a, b) => b[1] - a[1]);
    return e.map(([cd, n]) => `<b>${esc(tShort(cd))}</b>${withN && e.length > 1 ? ` <i>(${n})</i>` : ''}`).join(', ') || '<span class="muted">not assigned</span>'; };
  function drawSessions(box) {
    const A = state.an, M = classModel();
    if (A.sub !== 'all' && !M.subjects.includes(A.sub)) A.sub = 'all';
    box.innerHTML = `<div class="seg wide-seg"><button class="${A.sm === 'form' ? 'on' : ''}" data-sm="form">Form-wise</button><button class="${A.sm === 'class' ? 'on' : ''}" data-sm="class">Class-wise</button></div>
      <div class="chips" id="schips">${['all', ...M.subjects].map(n => `<button class="chip ${A.sub === n ? 'on' : ''}" data-sub="${esc(n)}">${n === 'all' ? 'All subjects' : esc(n)}</button>`).join('')}</div>
      <div class="anbtns"><button class="btn small" data-act="csv2">${icon('save')} Sessions per class (CSV)</button></div>
      <div id="sbody" class="gridwrap2"></div>`;
    const body = $('#sbody'), sn = A.sub;
    const head = '<p class="muted small keyline"><b class="redkey">Red</b> = some classes in that form have fewer sessions than the others · numbers are lessons per week (a double counts as 2)</p>';
    if (sn === 'all' && A.sm === 'form') {
      body.innerHTML = `<table class="atable mx"><thead><tr><th>Subject</th>${M.groups.map(x => `<th class="c">${esc(x.label)}<small>${x.cls.length} class${x.cls.length > 1 ? 'es' : ''}</small></th>`).join('')}</tr></thead><tbody>
        ${M.subjects.map(n => `<tr><th class="sj"${hueStyle(n)}>${esc(n)}</th>${M.groups.map(({ cls }) => {
          const v = cls.map(c => sess(c, n)), mx = Math.max(...v), mn = Math.min(...v);
          if (!mx) return '<td class="z">–</td>';
          return `<td class="c ${mn < mx ? 'warn' : ''}" data-asub="${esc(n)}"><b>${mn < mx ? mn + '–' + mx : mx}</b></td>`; }).join('')}</tr>`).join('')}
        <tr class="tot"><td>All lessons / week</td>${M.groups.map(({ cls }) => { const v = cls.map(c => c.total); const mn = Math.min(...v), mx = Math.max(...v); return `<td class="c">${mn < mx ? mn + '–' + mx : mx}</td>`; }).join('')}</tr></tbody></table>${head}<p class="muted small">Tap a number to see that subject class by class.</p>`;
    } else if (sn === 'all') {
      body.innerHTML = `<table class="atable mx"><thead><tr><th rowspan="2">Subject</th>${M.groups.map((x, gi) => `<th class="c gs g${gi % 2}" colspan="${x.cls.length}">${esc(x.label)}</th>`).join('')}<th rowspan="2" class="c">Total</th></tr>
        <tr>${M.groups.map((x, gi) => x.cls.map((c, k) => `<th class="c ${k === 0 ? 'gs' : ''} g${gi % 2}">${esc(c.name)}</th>`).join('')).join('')}</tr></thead><tbody>
        ${M.subjects.map(n => `<tr><th class="sj"${hueStyle(n)}>${esc(n)}</th>${M.groups.map((x, gi) => { const mx = Math.max(...x.cls.map(c => sess(c, n)));
          return x.cls.map((c, k) => { const v = sess(c, n); const w = mx > 0 && v < mx; return `<td class="c ${k === 0 ? 'gs' : ''} g${gi % 2} ${w ? 'warn' : ''}" data-asub="${esc(n)}">${v ? `<b>${v}</b>` : w ? '<b>0</b>' : '–'}</td>`; }).join(''); }).join('')}
          <td class="c tot2"><b>${M.classes.reduce((a, c) => a + sess(c, n), 0)}</b></td></tr>`).join('')}
        <tr class="tot"><td>All lessons</td>${M.groups.map(x => x.cls.map((c, k) => `<td class="c ${k === 0 ? 'gs' : ''}">${c.total}</td>`).join('')).join('')}<td class="c">${M.classes.reduce((a, c) => a + c.total, 0)}</td></tr></tbody></table>${head}`;
    } else if (A.sm === 'form') {
      body.innerHTML = `<h3 class="sect">${esc(sn)} · form by form</h3><table class="atable"><thead><tr><th>Form</th><th>Classes</th><th>Sessions per class</th><th>Total sessions</th><th>Teachers (classes)</th></tr></thead><tbody>
        ${M.groups.map(({ label, cls }) => { const v = cls.map(c => sess(c, sn)), mx = Math.max(...v), mn = Math.min(...v);
          const tm = {}; cls.forEach(c => Object.keys((c.subj[sn] || { teachers: {} }).teachers).forEach(cd => (tm[cd] = tm[cd] || []).push(c.name)));
          const less = cls.filter((c, i) => v[i] < mx).map(c => `${esc(c.name)} (${sess(c, sn)})`);
          return `<tr class="${mn < mx ? 'warnrow' : ''}"><th class="gh">${esc(label)}</th><td>${cls.map(c => esc(c.name)).join(', ')}</td>
          <td class="c"><b>${mx ? (mn < mx ? mn + '–' + mx : mx) : '–'}</b>${less.length && mx ? `<small class="redt">Less: ${less.join(', ')}</small>` : ''}</td><td class="c"><b>${v.reduce((a, b) => a + b, 0)}</b></td>
          <td>${Object.entries(tm).map(([cd, cn]) => `<b>${esc(tShort(cd))}</b> <i>(${cn.map(esc).join(', ')})</i>`).join('<br>') || '<span class="muted">—</span>'}</td></tr>`; }).join('')}</tbody></table>${head}`;
    } else {
      body.innerHTML = `<h3 class="sect">${esc(sn)} · teachers class by class</h3><table class="atable"><thead><tr><th>Form</th><th>Class</th><th>Sessions</th><th>Teacher(s)</th><th>Status</th></tr></thead><tbody>
        ${M.groups.map(({ label, cls }) => { const mx = Math.max(...cls.map(c => sess(c, sn)));
          return cls.map((c, k) => { const v = sess(c, sn), w = mx > 0 && v < mx;
            return `<tr class="${k === 0 ? 'gs' : ''} ${w ? 'warnrow' : ''}">${k === 0 ? `<th class="gh" rowspan="${cls.length}">${esc(label)}</th>` : ''}<td><b>${esc(c.name)}</b></td><td class="c"><b>${v || '–'}</b></td><td>${teachersOf(c, sn, true)}</td>
            <td>${!mx ? '<span class="muted">not taught</span>' : v === mx ? '<span class="okt">✓ full</span>' : `<span class="redt">⚠ ${v ? (mx - v) + ' less than rest of form' : 'not on timetable'}</span>`}</td></tr>`; }).join(''); }).join('')}
        <tr class="tot"><td colspan="2">Total sessions</td><td class="c">${M.classes.reduce((a, c) => a + sess(c, sn), 0)}</td><td colspan="2"></td></tr></tbody></table>${head}`;
    }
    $$('[data-sm]', box).forEach(b => b.addEventListener('click', () => { A.sm = b.dataset.sm; drawSessions(box); }));
    $$('[data-sub]', box).forEach(b => b.addEventListener('click', () => { A.sub = b.dataset.sub; drawSessions(box); }));
    $$('[data-asub]', box).forEach(b => b.addEventListener('click', () => { A.sub = b.dataset.asub; drawSessions(box); window.scrollTo(0, 0); }));
  }
  function drawClassList(box) {
    const A = state.an, M = classModel();
    box.innerHTML = `<div class="chips" id="gchips">${['all', ...IDX.grades].map(g => `<button class="chip ${A.gr === g ? 'on' : ''}" data-g="${esc(g)}">${g === 'all' ? 'All' : 'Grade ' + esc(g)}</button>`).join('')}</div><div id="alist"></div>`;
    const dr = () => {
      const list = M.classes.filter(c => A.gr === 'all' || c.grade === A.gr);
      $('#alist').innerHTML = list.map(c => { const subs = Object.values(c.subj).sort((a, b) => b.periods - a.periods);
        const tset = new Set(); subs.forEach(S => Object.keys(S.teachers).forEach(x => tset.add(x)));
        return `<button class="acard" data-go="analysis/${esc(c.id)}"><div class="ahead"><span class="av av-classes">${esc(String(c.name).replace(/\s+/g, '').slice(0, 4))}</span>
          <span class="nm"><b>Class ${esc(c.name)}</b><small>${subs.length} subjects · ${tset.size} teachers</small></span><span class="load"><b>${c.total}</b><small>lessons/wk</small></span></div>
          <div class="asubj">${subs.map(S => `<em${hueStyle(S.name)}>${esc(S.name)} <b>${S.periods}</b></em>`).join('')}</div></button>`; }).join('') || '<p class="muted">No classes.</p>';
    };
    dr(); $$('#gchips .chip').forEach(b => b.addEventListener('click', () => { A.gr = b.dataset.g; $$('#gchips .chip').forEach(x => x.classList.toggle('on', x === b)); dr(); }));
  }
  function renderClassProfile(id) {
    const M = classModel(), c = M.classes.find(x => x.id === id), grp = M.classes.filter(x => x.grade === c.grade);
    document.title = 'Class ' + c.name;
    const names = [...new Set([...Object.keys(c.subj), ...grp.flatMap(x => Object.keys(x.subj))])];
    const rows = names.map(n => { const v = sess(c, n), mx = Math.max(...grp.map(x => sess(x, n))); return { n, v, mx }; }).sort((a, b) => (b.v - a.v) || natural(a.n, b.n));
    const tm = {}; Object.values(c.subj).forEach(S => Object.entries(S.teachers).forEach(([cd, k]) => { const e = tm[cd] || (tm[cd] = { subs: {}, total: 0 }); e.subs[S.name] = k; e.total += k; }));
    const trs = Object.entries(tm).sort((a, b) => b[1].total - a[1].total);
    const flags = rows.filter(r => r.v < r.mx).length;
    app.innerHTML = `${topBar('Class ' + c.name, 'Teachers and subjects' + (c.grade ? ' · Grade ' + esc(c.grade) : ''), `<button class="icon-btn" data-act="print" aria-label="Print">${icon('print')}</button>`)}
      <main class="page wide">
        <div class="stats big"><div class="hi"><b>${c.total}</b><small>lessons / week</small></div><div><b>${Object.keys(c.subj).length}</b><small>subjects</small></div><div><b>${trs.length}</b><small>teachers</small></div><div class="${flags ? 'bad' : ''}"><b>${flags}</b><small>fewer than form</small></div></div>
        <h3 class="sect">Subjects, teachers and sessions</h3>
        <div class="gridwrap2"><table class="atable"><thead><tr><th>Subject</th><th>Teacher(s)</th><th>Sessions</th><th>Other classes in form</th></tr></thead><tbody>
          ${rows.map(r => `<tr${hueStyle(r.n)} class="sr ${r.v < r.mx ? 'warnrow' : ''}"><td><b>${esc(r.n)}</b></td><td>${teachersOf(c, r.n, true)}</td><td class="n">${r.v}</td>
            <td>${r.v < r.mx ? `<span class="redt">⚠ ${r.v ? (r.mx - r.v) + ' fewer than' : 'missing, others have'} ${r.mx}</span>` : '<span class="okt">✓</span>'}</td></tr>`).join('')}
          <tr class="tot"><td colspan="2">TOTAL</td><td class="n">${c.total}</td><td></td></tr></tbody></table></div>
        <h3 class="sect">All teachers of this class</h3>
        <div class="gridwrap2"><table class="atable"><thead><tr><th>Teacher</th><th>Subjects taught (sessions)</th><th>Sessions</th></tr></thead><tbody>
          ${trs.map(([cd, e]) => { const t = IDX.tByCode[cd]; return `<tr ${t ? `data-go="analysis/${esc(t.id)}"` : ''}><td><b>${esc(tShort(cd))}</b></td><td>${Object.entries(e.subs).map(([n, k]) => `<em class="sx"${hueStyle(n)}>${esc(n)} <b>${k}</b></em>`).join(' ')}</td><td class="n">${e.total}</td></tr>`; }).join('') || '<tr><td colspan="3" class="muted">No teachers found</td></tr>'}</tbody></table></div>
        <div class="anbtns"><button class="btn" data-go="view/${esc(c.id)}">Open class timetable</button><button class="btn ghost" data-go="analysis">Back to analysis</button></div>
      </main>`;
  }
  function downloadSessionsCsv() {
    const M = classModel(), q = v => '"' + String(v ?? '').replace(/"/g, '""') + '"';
    const out = [['Subject', 'Grade', 'Class', 'Sessions per week', 'Most sessions in this grade', 'Teachers'].map(q).join(',')];
    M.subjects.forEach(n => M.groups.forEach(({ g, cls }) => { const mx = Math.max(...cls.map(c => sess(c, n))); if (!mx) return;
      cls.forEach(c => out.push([n, g, c.name, sess(c, n), mx, Object.keys((c.subj[n] || { teachers: {} }).teachers).map(tShort).join(' / ')].map(q).join(','))); }));
    const blob = new Blob(['\ufeff' + out.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `${(state.data.school?.name || 'School').replace(/[^\w\- ]+/g, '').trim()}-sessions-per-class.csv`;
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000); toast('Saved to your Downloads ✓');
  }

  function renderProfile(id) {
    const t = IDX.byId[id], a = analyse(t), max = Math.max(1, ...a.perDay);
    document.title = teacherLabel(t) + ' · Profile';
    const busy = a.perDay.indexOf(Math.max(...a.perDay));
    app.innerHTML = `${topBar(teacherLabel(t), 'Teaching profile' + (t.name ? ' · No. ' + esc(t.code) : ''), `<button class="icon-btn" data-act="print" aria-label="Print">${icon('print')}</button>`)}
      <main class="page wide">
        <div class="stats big"><div class="hi"><b>${a.total}</b><small>total lessons / week</small></div><div><b>${a.subjects.length}</b><small>subjects</small></div><div><b>${a.classes.length}</b><small>classes</small></div><div><b>${a.doubles}</b><small>double lessons</small></div></div>
        <h3 class="sect">Subjects taught · lessons per subject</h3>
        <div class="gridwrap2"><table class="atable"><thead><tr><th>Subject</th><th>Classes (lessons each)</th><th>Lessons</th><th>Doubles</th></tr></thead><tbody>
          ${a.subjects.map(S => `<tr${hueStyle(S.name)} class="sr"><td><b>${esc(S.name)}</b></td><td>${clsText(S.list)}</td><td class="n">${S.periods}</td><td class="n">${S.doubles || '–'}</td></tr>`).join('') || '<tr><td colspan="4" class="muted">No lessons</td></tr>'}
          <tr class="tot"><td colspan="2">TOTAL LOAD</td><td class="n">${a.total}</td><td class="n">${a.doubles || '–'}</td></tr></tbody></table></div>
        <h3 class="sect">Classes taught</h3>
        <div class="gridwrap2"><table class="atable"><thead><tr><th>Class</th><th>Subjects (lessons)</th><th>Lessons</th></tr></thead><tbody>
          ${a.classes.map(C => `<tr><td><b>${esc(C.name)}</b></td><td>${Object.entries(C.subjects).map(([n, k]) => `<em class="sx"${hueStyle(n)}>${esc(n)} <b>${k}</b></em>`).join(' ')}</td><td class="n">${C.periods}</td></tr>`).join('') || '<tr><td colspan="3" class="muted">No classes</td></tr>'}</tbody></table></div>
        <h3 class="sect">Load per day</h3>
        <div class="daybars">${IDX.D.map((dd, i) => `<div class="dc${i % 5}"><span>${esc(dd.label.slice(0, 3))}</span><i style="height:${Math.round(a.perDay[i] / max * 80) + 4}px"></i><b>${a.perDay[i]}</b></div>`).join('')}</div>
        <p class="muted small">Busiest day: <b>${esc(dayLabel(busy))}</b> (${a.perDay[busy]} lessons). Double lessons count as 2 lessons.</p>
        <div class="anbtns"><button class="btn" data-go="view/${esc(t.id)}">Open timetable</button><button class="btn ghost" data-go="analysis">All teachers</button></div>
      </main>`;
  }
  function downloadCsv() {
    const q = v => '"' + String(v ?? '').replace(/"/g, '""') + '"';
    const out = [['Teacher No', 'Teacher Name', 'Subject', 'Class', 'Lessons per week (subject+class)', 'Subject total', 'Teacher total load'].map(q).join(',')];
    B.teachers.forEach(t => { const a = analyse(t);
      if (!a.subjects.length) out.push([t.code, t.name, '', '', 0, 0, 0].map(q).join(','));
      a.subjects.forEach(S => { if (!S.list.length) out.push([t.code, t.name, S.name, '', S.periods, S.periods, a.total].map(q).join(','));
        S.list.forEach(([c, k]) => out.push([t.code, t.name, S.name, c, k, S.periods, a.total].map(q).join(','))); }); });
    const blob = new Blob(['\ufeff' + out.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    const nm = `${(state.data.school?.name || 'School').replace(/[^\w\- ]+/g, '').trim()}-teacher-analysis.csv`;
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = nm; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000); toast('Saved to your Downloads ✓');
  }


  // ------------------------------------------------------------------ SCHOOLS using the app
  async function renderSchools() {
    const cur = CODE;
    document.title = 'Schools using Timetables';
    app.innerHTML = `${topBar('Schools using this app', 'Loading…')}<main class="page wide"><p class="muted center-t">Loading schools…</p></main>`;
    const j = await fetchSchools();
    if (route().name !== 'schools') return;
    const n = j && j.schools ? j.schools.length : 0;
    app.innerHTML = `${topBar('Schools using this app', `${n} school${n === 1 ? '' : 's'}`)}
      <main class="page wide">
        <div class="stats three"><div><b>${n}</b><small>schools</small></div><div><b>${(j?.schools || []).reduce((a, x) => a + (x.teachers || 0), 0)}</b><small>teachers</small></div><div><b>${(j?.schools || []).reduce((a, x) => a + (x.classes || 0), 0)}</b><small>classes</small></div></div>
        <div class="searchbox">${icon('search')}<input id="sq" type="search" autocomplete="off" placeholder="Search a school…"></div>
        <div id="slist">${schoolsListHTML(j, cur, '')}</div>
      </main>`;
    wireSchoolSearch(j, cur);
  }

  // ------------------------------------------------------------------ MEETING FINDER
  function meetBlocks(d, sel, k, pmOnly) {
    // windows of k adjacent lessons (not split by lunch) in which every chosen teacher is free
    const L = IDX.lessons.filter(j => !pmOnly || IDX.P[j].pm), out = [];
    const lunchBetween = (a, b) => { for (let x = a + 1; x < b; x++) if (IDX.P[x].brk && /lunch/i.test(IDX.P[x].label || '')) return true; return false; };
    for (let i = 0; i + k <= L.length; i++) {
      const w = L.slice(i, i + k); let ok = true;
      for (let q = 1; q < w.length; q++) if (lunchBetween(w[q - 1], w[q])) ok = false;
      if (ok && w.every(j => sel.every(t => cellAt(t, d, j) === ''))) out.push(w);
    }
    return out;
  }
  const timeRange = (j0, j1) => { const a = String(IDX.P[j0].time || '').split(/\s*[-–]\s*/)[0], b = String(IDX.P[j1].time || '').split(/\s*[-–]\s*/).pop(); return a && b ? `${a}–${b}` : ''; };
  function renderMeet() {
    const M = state.meet;
    document.title = 'Meeting finder';
    app.innerHTML = `${topBar('Meeting finder', 'Find a time when everyone is free')}
      <main class="page wide">
        <h3 class="sect">1. Who must attend?</h3>
        <div id="mchosen" class="chosen"></div>
        <div class="searchbox">${icon('search')}<input id="mq" type="search" autocomplete="off" placeholder="Search teacher to add…" value="${esc(M.q)}"></div>
        <ul class="list mlist" id="mlist"></ul>
        <h3 class="sect">2. Meeting length</h3>
        <div class="optrow"><div class="seg" id="mk">${[1, 2, 3].map(k => `<button class="${M.k === k ? 'on' : ''}" data-k="${k}">${k} lesson${k > 1 ? 's' : ''}</button>`).join('')}</div>
        <label class="chk"><input type="checkbox" id="mpm" ${M.pm ? 'checked' : ''}> After lunch only</label></div>
        <h3 class="sect">3. Times when all are free</h3>
        <div id="mres"></div>
      </main>`;
    const sel = () => M.ids.map(id => IDX.byId[id]).filter(Boolean);
    const drawChosen = () => {
      const me = meTeacher();
      $('#mchosen').innerHTML = (sel().map(t => `<button class="chosenchip" data-del="${esc(t.id)}">${esc(nameOf(t))} <b>✕</b></button>`).join('') || '<span class="muted">Nobody chosen yet. Search below and tap a name.</span>') +
        (me && !M.ids.includes(me.id) ? `<button class="chip" data-addme="1">+ Add me</button>` : '') + (M.ids.length ? '<button class="txt-btn" data-clear="1">Clear all</button>' : '');
    };
    const drawList = () => {
      const q = (M.q || '').toLowerCase();
      const rows = B.teachers.filter(t => !q || `${t.code} ${t.name}`.toLowerCase().includes(q)).slice(0, q ? 60 : 12);
      $('#mlist').innerHTML = rows.map(t => { const on = M.ids.includes(t.id);
        return `<li><button class="row" data-mt="${esc(t.id)}"><span class="av av-teachers">${esc(String(t.code).slice(0, 4))}</span><span class="nm">${esc(teacherLabel(t))}</span><span class="tick ${on ? 'on' : ''}">${on ? '✓' : '+'}</span></button></li>`; }).join('') +
        (!q && B.teachers.length > 12 ? '<li class="empty">Type a name or number to find more teachers.</li>' : '') || '<li class="empty">No teacher matches.</li>';
    };
    const drawRes = () => {
      const T = sel(), box = $('#mres');
      if (T.length < 2) { box.innerHTML = '<p class="hint-box">Choose at least two teachers to see when they are all free.</p>'; return; }
      const days = IDX.D.map((dd, d) => ({ d, dd, blocks: meetBlocks(d, T, M.k, M.pm) }));
      const total = days.reduce((a, x) => a + x.blocks.length, 0);
      const ps = M.pm ? IDX.lessons.filter(j => IDX.P[j].pm) : IDX.lessons;
      const head = `<div class="bestbox ${total ? 'good' : 'none'}"><b>${total ? `${total} time${total === 1 ? '' : 's'} found` : 'No common time found'}</b><span>${T.length} teachers · ${M.k} lesson${M.k > 1 ? 's' : ''}${M.pm ? ' · after lunch' : ''}</span></div>`;
      const found = days.filter(x => x.blocks.length).map(x => `<div class="mday dc${x.d % 5}"><h4>${esc(x.dd.label)}</h4><div>${x.blocks.map(w => `<span class="slotchip"><b>${esc(IDX.P[w[0]].label)}${w.length > 1 ? '–' + esc(IDX.P[w[w.length - 1]].label) : ''}</b><small>${esc(timeRange(w[0], w[w.length - 1]))}</small></span>`).join('')}</div></div>`).join('');
      const grid = `<div class="gridwrap2"><table class="atable mx"><thead><tr><th></th>${ps.map(j => `<th class="c">${esc(IDX.P[j].label)}<small>${esc(IDX.P[j].time)}</small></th>`).join('')}</tr></thead><tbody>
        ${IDX.D.map((dd, d) => `<tr class="dc${d % 5}"><th class="dh">${esc(dd.label.slice(0, 3))}</th>${ps.map(j => { const busy = T.filter(t => cellAt(t, d, j) !== ''); const all = !busy.length;
          return `<td class="c ${all ? 'allfree' : busy.length === 1 ? 'one' : 'busy'}" data-mb="${d}|${j}">${all ? '✓' : `<small>${busy.length} busy</small>`}</td>`; }).join('')}</tr>`).join('')}</tbody></table></div>
        <p class="muted small"><b class="okt">✓ green</b> = every chosen teacher is free · tap any slot to see who is busy.</p>`;
      box.innerHTML = head + found + '<h3 class="sect">Week at a glance</h3>' + grid;
      $$('[data-mb]', box).forEach(td => td.addEventListener('click', () => { const [d, j] = td.dataset.mb.split('|').map(Number);
        const rows = T.map(t => { const c = cellAt(t, d, j), L = cellLines('teachers', c); return `<li><div class="row nolink"><span class="av av-teachers">${esc(String(t.code).slice(0, 4))}</span><span class="nm">${esc(teacherLabel(t))}</span><span class="where ${L ? 'in' : c === 'X' ? 'x' : 'fr'}">${L ? `<b>${esc(L[0])}</b><small>${esc(L[1])}</small>` : c === 'X' ? 'Not available' : 'Free'}</span></div></li>`; }).join('');
        openSheet(`<div class="grab"></div><h3>${esc(dayLabel(d))} · ${esc(pLabel(j))}</h3><ul class="list">${rows}</ul><button class="btn ghost wide" data-act="closeSheet">Close</button>`); }));
    };
    const all = () => { drawChosen(); drawList(); drawRes(); };
    all();
    $('#mq').addEventListener('input', e => { M.q = e.target.value; drawList(); });
    $('#mpm').addEventListener('change', e => { M.pm = e.target.checked; drawRes(); });
    $$('#mk button').forEach(b => b.addEventListener('click', () => { M.k = +b.dataset.k; $$('#mk button').forEach(x => x.classList.toggle('on', x === b)); drawRes(); }));
    $('#mlist').addEventListener('click', e => { const b = e.target.closest('[data-mt]'); if (!b) return; const id = b.dataset.mt;
      M.ids = M.ids.includes(id) ? M.ids.filter(x => x !== id) : [...M.ids, id]; all(); });
    $('#mchosen').addEventListener('click', e => {
      const del = e.target.closest('[data-del]'), me = e.target.closest('[data-addme]'), clr = e.target.closest('[data-clear]');
      if (del) M.ids = M.ids.filter(x => x !== del.dataset.del);
      else if (me) { const m = meTeacher(); if (m && !M.ids.includes(m.id)) M.ids.push(m.id); }
      else if (clr) M.ids = [];
      else return; all(); });
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
      title = `Master timetable — ${dayLabel(d)}`; fname = `Master timetable ${dayLabel(d)}`;
      rows = B.master.filter(m => state.grade === 'all' || gradeOf(m.name) === state.grade).map(m => ({ head: m.name, item: m, d }));
    } else {
      const item = IDX.byId[r.id]; kind = item.kind;
      title = kind === 'teachers' ? `${teacherLabel(item)}${item.name ? ' (No. ' + item.code + ')' : ''}` : item.name;
      fname = title.replace(/[^\w\- ]+/g, '').trim() || 'timetable';
      rows = IDX.D.map((dd, d) => ({ head: dd.label, item, d }));
    }
    const P = IDX.P, scale = 2;
    const headW = kind === 'master' ? 90 : 70, colW = 130, brkW = 34, top = 96, pad = 20;
    const colWs = P.map(p => p.brk ? brkW : colW);
    // every row as tall as its longest cell, so all teacher names fit
    const mctx = document.createElement('canvas').getContext('2d');
    const cellText = (row, j) => {
      let span = 1; while ((row.item.grid[row.d] || [])[j + span] === '^') span++;
      let cw = 0; for (let k = j; k < j + span; k++) cw += colWs[k];
      const c = cellAt(row.item, row.d, j), L = cellLines(kind, c, row.item.name);
      if (!L) return { cw, L, a: [], b: [] };
      mctx.font = '700 12px Poppins, Arial'; const a = wrapText(mctx, L[0], cw - 10).slice(0, 3);
      mctx.font = '600 11px Poppins, Arial'; const b = wrapText(mctx, L[1] || '', cw - 10);
      return { cw, L, a, b };
    };
    const RH = rows.map(row => {
      let h = 64;
      for (let j = 0; j < P.length; j++) { if (P[j].brk || isCont(row.item, row.d, j)) continue; const t = cellText(row, j); h = Math.max(h, t.a.length * 14 + t.b.length * 13 + 20); }
      return Math.ceil(h);
    });
    const Y = []; RH.reduce((acc, h, i) => { Y[i] = acc; return acc + h; }, 0);
    const bodyH = RH.reduce((a, b) => a + b, 0);
    const width = pad * 2 + headW + colWs.reduce((a, b) => a + b, 0);
    const height = top + 44 + bodyH + 50;
    const cv = document.createElement('canvas'); cv.width = width * scale; cv.height = height * scale;
    const ctx = cv.getContext('2d'); ctx.scale(scale, scale);
    ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = '#12284C'; ctx.fillRect(0, 0, width, 72); ctx.fillStyle = '#C9A227'; ctx.fillRect(0, 72, width, 4);
    const IL = instLines();
    ctx.fillStyle = '#fff'; ctx.font = '700 20px Poppins, Arial'; ctx.fillText((IL[0] || state.data.school?.name || '').toUpperCase(), pad, 30);
    ctx.font = '700 14px Poppins, Arial'; ctx.fillStyle = '#E8D48A';
    ctx.fillText([IL.slice(1).join(' '), String(title).toUpperCase()].filter(Boolean).join('   ·   '), pad, 56);
    let x = pad + headW; const y0 = top; const colX = [];
    P.forEach((p, j) => {
      const w = p.brk ? brkW : colW; colX[j] = [x, w];
      ctx.fillStyle = p.brk ? '#EEE8D8' : '#F3EEDF'; ctx.fillRect(x, y0, w, 44); ctx.strokeStyle = '#5F6B82'; ctx.strokeRect(x, y0, w, 44);
      if (p.brk) { const t = String(p.time || '').split('-'); ctx.textAlign = 'center'; ctx.fillStyle = '#1B2333'; ctx.font = '700 9px Poppins, Arial';
        if (t.length === 2) { ctx.fillText(t[0], x + w / 2, y0 + 13); ctx.fillText('–', x + w / 2, y0 + 24); ctx.fillText(t[1], x + w / 2, y0 + 35); } ctx.textAlign = 'left'; }
      if (!p.brk) { ctx.textAlign = 'center'; ctx.fillStyle = '#12284C'; ctx.font = '800 13px Poppins, Arial'; ctx.fillText(p.label, x + w / 2, y0 + 18); ctx.font = '700 11px Poppins, Arial'; ctx.fillStyle = '#1B2333'; ctx.fillText(p.time, x + w / 2, y0 + 35); ctx.textAlign = 'left'; }
      x += w;
    });
    rows.forEach((row, ri) => {
      const y = y0 + 44 + Y[ri], rowH = RH[ri];
      ctx.fillStyle = '#12284C'; ctx.fillRect(pad, y, headW, rowH); ctx.fillStyle = '#fff'; ctx.font = '600 13px Poppins, Arial';
      wrapText(ctx, row.head, headW - 10).slice(0, 3).forEach((ln, k) => ctx.fillText(ln, pad + 6, y + 22 + k * 15));
      for (let j = 0; j < P.length; j++) {
        const [cx, w] = colX[j];
        if (P[j].brk) {
          if (ri === 0) {
            const H = bodyH; ctx.fillStyle = '#E4DCC2'; ctx.fillRect(cx, y, w, H); ctx.lineWidth = 1.5; ctx.strokeStyle = '#2B3447'; ctx.strokeRect(cx, y, w, H); ctx.lineWidth = 1;
            const words = String(P[j].label || 'BREAK').toUpperCase().split(/\s+/).filter(Boolean);
            const units = words.reduce((t, wd) => t + wd.length, 0) + (words.length - 1) * 0.6;
            const fs = Math.max(8, Math.min(16, Math.floor((H - 12) / (units * 1.15)))), lh = fs * 1.15;
            let ty = y + (H - units * lh) / 2 + fs; ctx.font = `800 ${fs}px Poppins, Arial`; ctx.fillStyle = '#3A3218'; ctx.textAlign = 'center';
            words.forEach((wd, wi) => { [...wd].forEach(ch => { ctx.fillText(ch, cx + w / 2, ty); ty += lh; }); if (wi < words.length - 1) ty += lh * 0.6; });
            ctx.textAlign = 'left';
          }
          continue;
        }
        if (isCont(row.item, row.d, j)) continue;
        let span = 1; while ((row.item.grid[row.d] || [])[j + span] === '^') span++;
        const cw = colX[j + span - 1][0] + colX[j + span - 1][1] - cx;
        const c = cellAt(row.item, row.d, j), T = cellText(row, j), L = T.L;
        const fc = L && isLesson(c) ? fetColour(c.s) : null;
        ctx.fillStyle = fc ? fc[0] : L ? '#ffffff' : c === 'X' ? '#F2F2F2' : '#FBFAF6'; ctx.fillRect(cx, y, cw, rowH);
        ctx.lineWidth = 1.5; ctx.strokeStyle = '#2B3447'; ctx.strokeRect(cx, y, cw, rowH); ctx.lineWidth = 1;
        if (L) {
          ctx.textAlign = 'center';
          const a = T.a, b2 = T.b;
          let ty = y + rowH / 2 - ((a.length * 14 + b2.length * 13) / 2) + 11;
          ctx.fillStyle = fc ? fc[1] : '#1B2333'; ctx.font = '700 12px Poppins, Arial'; a.forEach(ln => { ctx.fillText(ln, cx + cw / 2, ty); ty += 14; });
          ctx.font = '600 11px Poppins, Arial'; ctx.fillStyle = fc ? fc[1] : '#3A4356'; b2.forEach(ln => { ctx.fillText(ln, cx + cw / 2, ty); ty += 13; });
          ctx.textAlign = 'left';
        }
      }
    });
    ctx.save(); const gh = 44 + bodyH, gw = width - pad * 2;
    let fs = Math.min(80, gh * 0.3); ctx.font = `600 ${fs}px Poppins, Arial`;
    while (ctx.measureText(WATERMARK).width > Math.min(gw, gh * 1.6) * 0.75 && fs > 18) { fs -= 2; ctx.font = `600 ${fs}px Poppins, Arial`; }
    ctx.globalAlpha = 0.07; ctx.fillStyle = '#12284C'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.translate(width / 2, top + gh / 2); ctx.rotate(-Math.PI / 6); ctx.fillText(WATERMARK, 0, 0); ctx.restore();
    ctx.fillStyle = '#667085'; ctx.font = '11px Poppins, Arial';
    ctx.fillText(`${WATERMARK} · ${BRAND_LINE} · saved ${new Date().toLocaleString('en-GB')}`, pad, height - 18);
    const blob = await new Promise(res => cv.toBlob(res, 'image/png'));
    const ttn = state.data?.ttName || '';
    const full = [fname, ttn].filter(Boolean).join(' - ').replace(/[\\/:*?"<>|]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 90);
    const file = new File([blob], full + '.png', { type: 'image/png' });
    if (isIOS() && navigator.canShare && navigator.canShare({ files: [file] })) {   // iPhone: the only way into Photos
      try { await navigator.share({ files: [file], title: full }); toast('Tap “Save Image” to put it in Photos'); } catch { }
      return;
    }
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = full + '.png';
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    toast(`Saved: ${full}.png ✓ (Gallery / Downloads)`, 3500);
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
      ${!isStandalone() ? `<button class="mrow" data-act="getapp">${icon('install')}<span>Get the app<small>Android · iPhone · Computer</small></span></button>` : ''}
      <button class="mrow" data-go="schools">${icon('classes')}<span>Schools using this app<small>See the other schools on Timetables</small></span></button>
      ${meTeacher() ? `<button class="mrow" data-act="remToggle">${icon('clock')}<span>Lesson reminder: ${remOn() ? 'ON' : 'OFF'}<small>Alarm ${REMIND_MIN} minutes before each of your lessons · tap to switch ${remOn() ? 'off' : 'on'}</small></span></button>` : ''}
      <button class="mrow" data-act="contact">${icon('wa')}<span>Contact Cyrus Ireri<small>WhatsApp · call · SMS — ${esc(LOCKED_CONTACT)}</small></span></button>
      <button class="mrow" data-act="about">${icon('info')}<span>About<small>${esc(BRAND_LINE)}</small></span></button>
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
  // Contact Cyrus Ireri: WhatsApp chat, call or SMS
  const INTL = '254' + LOCKED_CONTACT.replace(/^0/, '');
  function openContact() {
    const school = state.data?.school?.name || '';
    const msg = `Hello Cyrus, I am a teacher${school ? ' at ' + school : ''}. I am using the timetable app and `;
    openSheet(`<div class="grab"></div><h3>Contact Cyrus Ireri</h3><p class="muted center-t">${esc(LOCKED_BRAND)} · ${esc(LOCKED_CONTACT)}</p>
      <div class="contact-opts">
        <a class="copt cwa" href="https://wa.me/${INTL}?text=${encodeURIComponent(msg)}" target="_blank" rel="noopener">${icon('wa')}<span><b>Chat on WhatsApp</b><small>Opens WhatsApp with a message ready</small></span></a>
        <a class="copt ccall" href="tel:+${INTL}"><svg class="ic" viewBox="0 0 24 24"><path d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1A17 17 0 0 1 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1l-2.3 2.2Z"/></svg><span><b>Call</b><small>${esc(LOCKED_CONTACT)}</small></span></a>
        <a class="copt csms" href="sms:+${INTL}"><svg class="ic" viewBox="0 0 24 24"><path d="M4 4h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H8l-4 4V6a2 2 0 0 1 2-2Zm3 6v2h2v-2H7Zm4 0v2h2v-2h-2Zm4 0v2h2v-2h-2Z"/></svg><span><b>Send SMS</b><small>Text message</small></span></a>
      </div>
      <button class="btn ghost wide" data-act="closeSheet">Close</button>`);
  }
  // Get the app: teachers choose their device
  function openGetApp(focus) {
    const me = focus || platformName();
    const inst = state.installEvt ? `<button class="btn wide" data-act="install">${icon('install')} Install now</button>` : '';
    const card = (key, title, sub, steps) => `<details class="gcard ${key}"${key === me ? ' open' : ''}><summary><span class="gicon gi-${key}"></span><span><b>${title}</b><small>${sub}</small></span>${key === me ? '<i class="me-tag">This device</i>' : ''}</summary>
      <ol class="steps">${steps.map(x => `<li>${x}</li>`).join('')}</ol>${key === me ? inst : ''}</details>`;
    openSheet(`<div class="grab"></div><h3>Get the app</h3><p class="muted center-t">Free · the same timetables on every device · updates itself · works offline</p>
      ${card('android', 'Android phone or tablet', 'Chrome', ['Open this page in <b>Chrome</b>.', 'Tap <b>Install</b> (or menu <b>⋮</b> → <b>Install app</b> / <b>Add to Home screen</b>).', 'The app appears on your home screen and in your apps list.'])}
      ${card('ios', 'iPhone or iPad', 'Safari', ['Open this page in <b>Safari</b>.', 'Tap <b>Share ⬆</b> at the bottom of the screen.', 'Choose <b>Add to Home Screen</b>, then <b>Add</b>.'])}
      ${card('desktop', 'Computer (Windows, Mac, Linux)', 'Chrome or Microsoft Edge', ['Open this page in <b>Chrome</b> or <b>Edge</b>.', 'Click the <b>Install</b> icon at the right end of the address bar (or menu → <b>Install Timetables</b>).', 'It opens in its own window and gets a desktop / Start-menu icon.'])}
      <p class="muted center-t small">Share the link or QR code (menu → Share) so colleagues can get it too.</p>
      <button class="btn ghost wide" data-act="closeSheet">Close</button>`);
  }
  function openAbout() {
    openSheet(`<div class="grab"></div><img class="about-logo" src="/brand/prepfix-logo-600.png" alt="PREPFIX — Prepare. Perfect. Present."><h3>About</h3><p>${esc(state.data?.school?.name || '')} timetables. This app shows the latest version published by the school and updates itself when you open it, and keeps a copy for offline use.</p>
      <p class="muted">${esc(state.data?.school?.institution || '')}<br>${esc(LOCKED_BRAND)}<br>${esc(LOCKED_CONTACT)}<br>App version ${esc(CFG.build || '')}</p>
      <button class="btn ghost wide" data-act="closeSheet">Close</button>`);
  }
  async function renderPoster() {
    const link = linkFor(), name = state.data?.school?.name || '';
    document.body.classList.add('poster-mode');
    app.innerHTML = `<div class="poster"><img class="plogo" src="/brand/prepfix-logo-600.png" alt="PREPFIX — Prepare. Perfect. Present."><div class="ptop"><div class="logo big"></div><div><h1>${esc(name || 'School')} Timetables</h1><p>On your phone · Always up to date · Works offline</p></div></div>
      <div class="pmain"><div class="pqr" id="pqr"></div><ol>
        <li><b>Scan</b> this QR code with your phone camera.</li>
        <li><b>Get the app</b> — Android (Chrome): tap <b>Install</b>. iPhone (Safari): Share ⬆ → <b>Add to Home Screen</b>. Computer (Chrome/Edge): click <b>Install</b> in the address bar.</li>
        <li>Tap <b>My timetable</b>, find your name and tap <b>☆</b> to make it <b>My timetable</b>.</li></ol></div>
      <p class="plink">${esc(link)}</p><p class="pfoot">${esc(BRAND_LINE)}</p>
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
    const g = e.target.closest('[data-go]'); if (g) { closeSheet(); go(g.dataset.go); return; }
    const ttb = e.target.closest('[data-tt]'); if (ttb) { switchTT(ttb.dataset.tt); return; }
    const cv = e.target.closest('[data-cv]'); if (cv) { const [id, d, j] = cv.dataset.cv.split('|'); openCoverSheet(id, +d, +j); return; }
    const b = e.target.closest('[data-act],[data-layout],[data-day],[data-sday],[data-slot],[data-grade],[data-freetab],[data-coverslot],[data-covert]');
    if (!b) return;
    const ds = b.dataset;
    if (ds.layout) { if (ds.layout === 'day' && state.full) releaseRotate(); state.layout = ds.layout; render(); return; }
    if (ds.day != null) { state.day = +ds.day; state.coverSlot = null; render(); return; }
    if (ds.sday != null) { state.slot = { ...(state.slot || defaultSlot()), d: +ds.sday }; render(); return; }
    if (ds.slot != null) { state.slot = { ...(state.slot || defaultSlot()), j: +ds.slot }; render(); return; }
    if (ds.grade != null && route().name === 'master') { state.grade = ds.grade; render(); return; }
    if (ds.freetab) { store.set('freeTab', ds.freetab); render(); return; }
    if (ds.coverslot != null) { state.coverSlot = +ds.coverslot; render(); return; }
    if (ds.covert) { state.coverTeacher = ds.covert; state.coverPick = false; state.coverSlot = null; render(); return; }
    switch (ds.act) {
      case 'back': if (state.navDepth > 0) history.back(); else location.hash = ''; break;
      case 'rotate': toggleRotate(); break;
      case 'csv': downloadCsv(); break;
      case 'csv2': downloadSessionsCsv(); break;
      case 'print': window.print(); break;
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
      case 'seen': { const m = seenMap(); (state.tts && state.tts.length ? state.tts : [{ id: state.data.tt, version: state.data.version }]).forEach(t => { m[t.id] = t.version; }); store.set('seenTT', m); render(); break; }
      case 'hideInstall': store.set('hideInstallTip', true); renderBanners(); break;
      case 'install':
        closeSheet();
        if (state.installEvt) { state.installEvt.prompt(); const r = await state.installEvt.userChoice.catch(() => null); state.installEvt = null; if (r?.outcome === 'accepted') toast('Installed ✓'); renderBanners(); }
        else if (isIOS()) openSheet(`<div class="grab"></div><h3>Add to Home Screen</h3><ol class="steps"><li>Tap <b>Share ⬆</b> at the bottom of Safari.</li><li>Choose <b>Add to Home Screen</b>.</li><li>Tap <b>Add</b>.</li></ol><button class="btn wide" data-act="closeSheet">OK</button>`);
        break;
      case 'menu': openMenu(); break;
      case 'remToggle': await remToggle(); break;
      case 'remCal': remCalendar(); break;
      case 'refresh': closeSheet(); toast('Checking…', 1200); await sync('manual'); if (state.online) toast('You have the latest timetable ✓'); break;
      case 'share': openShare(); break;
      case 'copy': try { await navigator.clipboard.writeText(linkFor()); toast('Link copied'); } catch { toast(linkFor(), 6000); } break;
      case 'nativeShare': try { await navigator.share({ title: 'School timetables', url: linkFor() }); } catch { } break;
      case 'about': openAbout(); break;
      case 'contact': openContact(); break;
      case 'getapp': openGetApp(); break;
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
  const onRotate = () => { releaseRotate(); if (state.data && route().name === 'view') { state.layout = 'auto'; render(); } };
  if (mq.addEventListener) mq.addEventListener('change', onRotate); else if (mq.addListener) mq.addListener(onRotate);
  addEventListener('resize', () => { applyForce(); if (state.data && (route().name === 'master' || (route().name === 'view' && effectiveLayout() === 'week'))) setTimeout(fitGrid, 60); });
  addEventListener('hashchange', () => { if (state.full && !['view', 'master'].includes(route().name)) releaseRotate(); });
  addEventListener('online', () => { state.online = true; sync('online'); });
  addEventListener('offline', () => { state.online = false; renderStatus(); });
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState !== 'visible') return;
    if (Date.now() - state.lastSync > 60000) sync('visible');
    if (state.data && route().name === 'home') render();
  });
  setInterval(() => { if (document.visibilityState === 'visible' && state.data && route().name === 'home') { const c = $('.now-card'); if (c) c.outerHTML = nowCard(); } }, 60000);
  setInterval(checkReminders, 15000);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') checkReminders(); });
  addEventListener('beforeinstallprompt', e => { e.preventDefault(); state.installEvt = e; if (state.data && route().name === 'home') renderBanners(); });
  addEventListener('appinstalled', () => { state.installEvt = null; toast('Installed ✓'); });
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(err => console.warn('SW', err));
  }

  // ------------------------------------------------------------------ start
  (async () => {
    try { state.tts = JSON.parse(localStorage.getItem(`ireri:${CODE}:tts`) || '[]'); } catch { state.tts = []; }
    const cached = await loadCached();
    if (cached && cached.bundle && cached.bundle.format === 2) setData(cached);
    if (state.data || POSTER) render();
    await sync('start');
    if (POSTER) renderPoster();
  })();
  self.__ireri = { state, sync, render, nowSlot: () => nowSlot() };
})();
