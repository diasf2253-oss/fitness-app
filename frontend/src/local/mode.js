/**
 * Local-first mode flag (P2 transition switch).
 *
 * Off (default): the app is the classic thin client — every read/write
 * goes to the laptop backend. The laptop experience is unchanged.
 *
 * On: weight reads/writes use the on-device IndexedDB and the app syncs
 * with the laptop opportunistically on open. This is the phone build.
 *
 * Enable per-device without rebuilding:  localStorage.local_first = '1'
 * or bake it into a build with:          VITE_LOCAL_FIRST=1 npm run build
 */
export function isLocalFirst() {
  try {
    if (localStorage.getItem('local_first') === '1') return true
  } catch { /* storage unavailable (private mode) — fall through */ }
  return import.meta.env.VITE_LOCAL_FIRST === '1'
}
