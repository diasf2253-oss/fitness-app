/**
 * Service worker — versioned offline app shell (P2/P5).
 *
 * Makes the installed PWA open and run with no server reachable. The key is
 * PRE-caching the app's code at install time: we fetch index.html, parse out
 * its hashed JS/CSS URLs, and cache them all up front. (The previous version
 * only cached '/', so with the server off the page loaded but its JavaScript
 * bundle was missing → "load failed".) In local-first mode the data comes
 * from IndexedDB, so with the shell + code cached the app is fully standalone.
 * /api/* is never cached: reads reach a live server or are answered locally.
 *
 * Releases: bump VERSION (the "tracker 1.0.x" scheme). A new worker installs
 * on the next online open, precaches, drops old caches on activate, and takes
 * over.
 */
const VERSION = 'tracker-1.0.4'

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(VERSION)
    try {
      // Precache the shell + every hashed asset it references, so ONE online
      // visit makes the whole app launchable offline.
      const res = await fetch('/', { cache: 'reload' })
      const html = await res.clone().text()
      await cache.put('/', res)
      const urls = new Set(['/manifest.webmanifest'])
      for (const m of html.matchAll(/(?:src|href)="(\/[^"']+\.(?:js|css))"/g)) {
        urls.add(m[1])
      }
      await cache.addAll([...urls])
    } catch (e) {
      // Best-effort: the fetch handler still cache-fills on later online visits.
    }
    await self.skipWaiting()
  })())
})

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys()
    await Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k)))
    await self.clients.claim()
  })())
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
