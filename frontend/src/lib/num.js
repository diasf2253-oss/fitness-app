/**
 * Numeric input parsing for the whole app.
 *
 * Gym inputs are typed on a phone with a European keyboard, where the
 * decimal key produces a comma ("82,5"). Number("82,5") is NaN, and a
 * type="number" input silently rejects the comma altogether — so decimal
 * fields use type="text" inputMode="decimal" and run through here.
 */

/** "82,5" → 82.5, "82.5" → 82.5, ""/null/garbage → null. */
export function parseDecimal(value) {
  if (value === null || value === undefined) return null
  const s = String(value).trim().replace(',', '.')
  if (s === '') return null
  const n = Number(s)
  return Number.isFinite(n) ? n : null
}
