// Precaches the app shell and serves it cache-first with a background network
// refresh (stale-while-revalidate) -- fast, offline-capable loads instead of
// re-downloading the whole app every open. Everything (segmentation,
// inpainting, compositing) runs on-device with no external requests, so this
// worker only ever needs to own the same-origin app shell.
//
// This does NOT fight index.html's own checkForUpdate() (a HEAD request with
// cache:'no-store' + a cache-busting query string, comparing etag/last-
// modified, and force-reloading on a mismatch) -- that request is excluded
// below (method!=='GET') and always goes straight to the network untouched.
//
// manifest.json and the icon files are served network-first instead (fall
// back to cache only if offline). Android/Chrome's installed-PWA (WebAPK)
// icon-update check reads the manifest client-side and only re-fetches an
// icon when its URL changes -- and uninstalling a WebAPK on Android does NOT
// clear this service worker/cache. See scripts/sync_pwa_version.py, which
// stamps manifest.json's icon src URLs (and index.html's apple-touch-icon
// href) with a content hash whenever the icon files change, so a real icon
// update always gets a new URL for this check to notice.
const CACHE_NAME = 'floorplanner-shell-7507af0773a7';
const PRECACHE_URLS = [
  './index.html', './manifest.json', './icon-192.png', './icon-512.png'
];

// Every network trip this worker makes needs to go all the way to the
// network, not just to the browser's own HTTP cache -- GitHub Pages serves
// this app with Cache-Control: max-age=600, so a plain fetch() can silently
// resolve from a same-URL response the browser already cached moments ago
// instead of a genuinely fresh round-trip. That would defeat "network-first"
// for manifest/icons below, and worse, defeat the background revalidation
// that's supposed to fix a stale shell for next time: checkForUpdate() in
// index.html purges this worker's own Cache Storage entry and reloads on a
// detected update, but if the reload's navigation fetch then gets served out
// of the browser's still-fresh (<10min) HTTP cache, the "purged" shell comes
// right back and the reload looks like it did nothing.
function freshFetch(req){
  return fetch(req, { cache:'no-store' });
}

self.addEventListener('install', (e) => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE_URLS.map(u => new Request(u, { cache:'no-store' })))).catch(() => {}));
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
        const res = await freshFetch(req);
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
    const networkFetch = freshFetch(req).then(res => {
      if (res && res.ok) cache.put(cacheKey, res.clone());
      return res;
    }).catch(() => null);
    if (cached) { e.waitUntil(networkFetch); return cached; }
    return (await networkFetch) || Response.error();
  })());
});
