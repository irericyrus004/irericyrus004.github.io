/* PREPFIX service worker: keeps the app working offline.
   UPDATES ARE NEVER AUTOMATIC: the app files a phone is running stay exactly as they are until the teacher
   taps "Update" in the app. Keep the SHELL name below unchanged, so a new sw.js never swaps the app files by itself. */
const SHELL = 'ireri-shell-v44';
const SHELL_FILES = ['/app.css', '/app.js', '/config.js', '/qrcode.js',
  '/icons/icon-192.png', '/icons/icon-512.png', '/brand/prepfix-logo-600.png', '/brand/prepfix-mark.png'];
const APP_FILE = /\/(app\.js|app\.css|qrcode\.js|config\.js)$/;

self.addEventListener('install', event => {
  // no skipWaiting: a new service worker waits quietly; and it only saves files the phone does not have yet
  event.waitUntil(
    caches.open(SHELL).then(c => Promise.all(SHELL_FILES.map(u =>
      c.match(u).then(hit => hit ? null : c.add(new Request(u, { cache: 'reload' })).catch(() => null)))))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k.startsWith('ireri-shell-') && k !== SHELL).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// The app asks for the new service worker only when the teacher taps Update
self.addEventListener('message', event => { if (event.data === 'SKIP_WAITING') self.skipWaiting(); });

function timeout(ms) { return new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), ms)); }

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // Timetable data is always fetched live; the app keeps its own saved copy for offline use.
  if (url.origin === location.origin && /\/(meta|data|schools)\.json$/.test(url.pathname)) return;
  // Update checks always go to the website, never to the saved copy
  if (url.origin === location.origin && (url.searchParams.has('v') || url.searchParams.has('u') || /\/(config\.js|shell\.json)$/.test(url.pathname) && req.cache === 'no-store')) return;

  // Pages: network first (so updates show), fall back to the saved page when offline.
  if (req.mode === 'navigate' && url.origin === location.origin) {
    event.respondWith(
      Promise.race([fetch(req), timeout(5000)])
        .then(res => {
          if (res && res.ok) { const copy = res.clone(); caches.open(SHELL).then(c => c.put('/__page', copy)).catch(() => {}); }
          return res;
        })
        .catch(() => caches.match('/__page').then(r => r || fetch(req)))
    );
    return;
  }

  // PREPFIX app files: always the saved copy (changed only when the teacher taps Update); fetched once if missing.
  if (url.origin === location.origin && APP_FILE.test(url.pathname)) {
    event.respondWith(
      caches.match(url.pathname).then(hit => hit || fetch(new Request(req, { cache: 'reload' })).then(res => {
        if (res && res.ok) { const copy = res.clone(); caches.open(SHELL).then(c => c.put(url.pathname, copy)).catch(() => {}); }
        return res;
      }))
    );
    return;
  }

  // Icons, logos and fonts: saved copy first, refreshed in the background.
  const cacheable = url.origin === location.origin ||
    url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com';
  if (!cacheable) return;
  event.respondWith(
    caches.match(req).then(hit => {
      const net = fetch(req).then(res => {
        if (res && (res.ok || res.type === 'opaque')) { const copy = res.clone(); caches.open(SHELL).then(c => c.put(req, copy)).catch(() => {}); }
        return res;
      }).catch(() => hit);
      return hit || net;
    })
  );
});

// Lesson reminder: tapping the notification opens the app
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
    for (const c of list) { if ('focus' in c) return c.focus(); }
    return clients.openWindow ? clients.openWindow(url) : null;
  }));
});

// Lesson reminder pushed by the PREPFIX reminder service: the phone works out which lesson it is
self.addEventListener('push', event => {
  event.waitUntil((async () => {
    let plan = null;
    try { const c = await caches.open('prepfix-rem'); const r = await c.match('/__reminders'); if (r) plan = await r.json(); } catch (e) { }
    const now = new Date(), wd = now.getDay(), m = now.getHours() * 60 + now.getMinutes();
    const L = plan && (plan.lessons || []).filter(x => x.wd === wd && x.start - m >= 2 && x.start - m <= 17).sort((a, b) => a.start - b.start)[0];
    const fmt = mm => { const h = Math.floor(mm / 60); return `${h > 12 ? h - 12 : h}:${String(mm % 60).padStart(2, '0')}`; };
    const mins = L ? L.start - m : (plan && plan.min) || 10;
    const title = L ? `⏰ Lesson in ${mins} minutes — ${L.label} at ${fmt(L.start)}` : '⏰ Your next lesson starts soon';
    const body = L ? [L.title, L.body].filter(Boolean).join(' · ') : 'Open PREPFIX Timetables to see it.';
    await self.registration.showNotification(title, {
      body, icon: '/icons/icon-192.png', badge: '/icons/badge-96.png', tag: L ? `lesson-${L.wd}-${L.start}` : 'lesson-next',
      renotify: true, requireInteraction: true, vibrate: [400, 150, 400, 150, 800], data: { url: (plan && plan.url) || '/' },
    });
  })());
});
