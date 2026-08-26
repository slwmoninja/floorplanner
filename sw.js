// Cache-first app shell with a background network refresh, same pattern as
// the other single-file PWAs in this workspace. Everything (segmentation,
// inpainting, compositing) runs on-device with no external requests, so this
// worker only ever needs to own the same-origin app shell.
const CACHE_NAME = 'photodesigner-shell-v1';
const PRECACHE_URLS = [
  './index.html', './manifest.json', './icon-192.png', './icon-512.png'
];

self.addEventListener('install', (e) => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE_URLS)).catch(() => {}));
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin) {
    e.respondWith(fetch(req));
    return;
  }
  if (/\/(manifest\.json|icon-(192|512)\.png)$/.test(url.pathname)) {
    e.respondWith((async () => {
      try {
        const res = await fetch(req);
        if (res && res.ok) { const cache = await caches.open(CACHE_NAME); cache.put(req, res.clone()); }
        return res;
      } catch (err) {
        const cached = await caches.match(req);
        return cached || Response.error();
      }
    })());
    return;
  }
  e.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    const cacheKey = req.mode === 'navigate' ? './index.html' : req;
    const cached = await cache.match(cacheKey);
    const networkFetch = fetch(req).then(res => {
      if (res && res.ok) cache.put(cacheKey, res.clone());
      return res;
    }).catch(() => null);
    if (cached) { e.waitUntil(networkFetch); return cached; }
    return (await networkFetch) || Response.error();
  })());
});
