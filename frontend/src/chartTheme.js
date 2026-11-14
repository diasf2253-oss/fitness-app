/**
 * Shared chart palette + helpers — mirrors the "Quiet Tracker" CSS tokens in
 * index.css so Recharts (which needs literal colours, not CSS variables)
 * stays in step with the rest of the UI.
 */
export const GRID = 'rgba(241, 234, 217, 0.07)'
export const AXIS = '#93a08c'
export const SAGE = '#9db08f'
export const MOSS = '#809076'
export const BONE = '#f1ead9'
export const KHAKI = '#f8d794'   // Creased Khaki — highlights (e.g. the weight 'now' point)
export const EMERALD = '#284139'
export const TOOLTIP_STYLE = {
  background: '#172320',
  border: '1px solid rgba(241, 234, 217, 0.12)',
  borderRadius: 12,
  color: '#f1ead9',
}

/** "2026-11-14" → "Nov 14" (local date, never shifted by timezone). */
export function fmtDay(iso) {
  return new Date(iso + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
