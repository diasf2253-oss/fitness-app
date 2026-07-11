/**
 * Service worker — versioned offline app shell (P2/P5).
 *
 * Makes the installed PWA open and run with no server reachable: after the
 * first visit, the shell (HTML + hashed JS/CSS assets) is cached here, and
 * in local-first mode the data comes from IndexedDB — so the app is fully
 * standalone. /api/* is never cached: reads either reach a live server or
 * are answered locally by the app itself.
 *
 * Releases: bump VERSION (the "tracker 1.0.x" scheme). A new worker installs
 * in the background on the next online open, old caches are dropped on
 * activate, and the following launch runs the new version.
 */
const VERSION = 'tracker-1.0.2'

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(VERSION).then((cache) => cache.addAll(['/'])).then(() => self.skipWaiting())
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)

  // Data is never served from HTTP cache — the app handles offline itself
  if (event.request.method !== 'GET' || url.pathname.startsWith('/api/')) return

  // App navigation: freshest shell when online, cached shell when not
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then((resp) => {
          const copy = resp.clone()
          caches.open(VERSION).then((cache) => cache.put('/', copy))
          return resp
        })
        .catch(() => caches.match('/'))
    )
    return
  }

  // Same-origin assets: cache-first (hashed filenames make this safe),
  // caching new ones as they're fetched
  if (url.origin === self.location.origin) {
    event.respondWith(
      caches.match(event.request).then(
        (hit) => hit || fetch(event.request).then((resp) => {
          if (resp.ok) {
            const copy = resp.clone()
            caches.open(VERSION).then((cache) => cache.put(event.request, copy))
          }
          return resp
        })
      )
    )
  }
})
