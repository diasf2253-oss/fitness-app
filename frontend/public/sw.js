/**
 * Minimal service worker — exists so the app is installable (Android
 * requires a fetch handler). Deliberately does NOT cache: the app is
 * useless without its API, and stale-cache bugs cost more than the
 * offline shell is worth. Revisit if real offline support is wanted.
 */
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()))
self.addEventListener('fetch', () => {
  // Intentionally empty: requests fall through to the network.
})
