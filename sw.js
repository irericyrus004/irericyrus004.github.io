/* Ireri Timetables service worker: keeps the app working offline. */
const SHELL = 'ireri-shell-v55';
const SHELL_FILES = ['/app.css', '/app.js', '/config.js', '/qrcode.js',
  '/icons/icon-192.png', '/icons/icon-512.png', '/brand/prepfix-logo-600.png', '/brand/prepfix-mark.png'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(SHELL)
      .then(c => Promise.all(SHELL_FILES.map(u => c.add(new Request(u, { cache: 'reload' })).catch(() => null))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k.startsWith('ireri-shell-') && k !== SHELL).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

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

  // App files and fonts: saved copy first, refreshed in the background.
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

const VIB = Array.from({ length: 20 }, () => [700, 300]).flat();   // 20-second buzz
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
      renotify: true, requireInteraction: true, vibrate: VIB, data: { url: (plan && plan.url) || '/' },
    });
    // not noticed? ring again twice more (every 20 s) while the notification is still on the screen
    const tag = L ? `lesson-${L.wd}-${L.start}` : 'lesson-next';
    for (let i = 0; i < 2; i++) {
      await new Promise(r => setTimeout(r, 20000));
      const open = await self.registration.getNotifications({ tag });
      if (!open.length) break;
      await self.registration.showNotification(title, {
        body, icon: '/icons/icon-192.png', badge: '/icons/badge-96.png', tag,
        renotify: true, requireInteraction: true, vibrate: VIB, data: { url: (plan && plan.url) || '/' },
      });
    }
  })());
});
