/**
 * Local API dispatcher (P3/P4) — the on-device twin of the FastAPI backend.
 *
 * In local-first mode, apiFetch() offers every request here first. If a
 * route matches, it's served from IndexedDB and never touches the network,
 * so the whole app works with no server reachable. Unmatched routes fall
 * through to the network — deliberately, for the features that *need* the
 * laptop: the AI Coach (Anthropic key lives there), Apple Health ingest,
 * export backfill, /api/sync itself, and dev utilities.
 *
 * Handlers receive (regexMatch, URLSearchParams, parsedBody) and return
 * the same JSON shapes the backend's Pydantic schemas produce — in local
 * mode, `id` fields simply carry uuids, opaque to the components.
 */
import { healthRoutes } from './health'
import { overviewRoutes } from './overview'
import { planRoutes } from './plan'
import { trackerRoutes } from './trackers'
import { workoutRoutes } from './workout'

export { LocalApiError } from './util'

const ROUTES = [
  ...healthRoutes,
  ...workoutRoutes,
  ...trackerRoutes,
  ...planRoutes,
  ...overviewRoutes,
]

/**
 * Serve a request locally if a route matches.
 * Returns { handled: true, result } or { handled: false }.
 */
export async function dispatchLocal(path, options = {}) {
  const url = new URL(path, window.location.origin)
  const method = (options.method || 'GET').toUpperCase()

  for (const route of ROUTES) {
    if (route.method !== method) continue
    const m = url.pathname.match(route.pattern)
    if (!m) continue
    const body = options.body ? JSON.parse(options.body) : undefined
    return { handled: true, result: await route.handler(m, url.searchParams, body) }
  }
  return { handled: false }
}
