/* Ireri Timetables service worker: keeps the app working offline. */
const SHELL = 'ireri-shell-v1';
const SHELL_FILES = ['/app.css', '/app.js', '/config.js', '/qrcode.js',
  '/icons/icon-192.png', '/icons/icon-512.png'];

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
  if (url.origin === location.origin && /\/(meta|data)\.json$/.test(url.pathname)) return;

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
