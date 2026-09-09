/**
 * Rank-up detection.
 *
 * The Ranks page shows a tier (Wood…Olympian) + division (III→II→I) per body
 * part. A "rank up" is a *promotion* — a tier or division climbing, or a
 * previously-unranked muscle becoming ranked. It is NOT LP drifting up within
 * a division (that happens constantly and shouldn't fanfare).
 *
 * `rankSignature` collapses the whole ladder into one monotonic integer: the
 * summed ordinal (tierIndex × 3 + divisionRank) over every ranked body part.
 * Any real promotion strictly increases it; LP changes leave it untouched.
 * The caller stores the last value and compares — see `detectRankUp`.
 */

const DIVISION_RANK = { III: 0, II: 1, I: 2 }  // III entry (low) → I top

/** Monotonic promotion score for a /api/ranks payload. Higher = stronger. */
export function rankSignature(data) {
  const tiers = data?.tiers || []
  const parts = data?.body_parts || []
  let score = 0
  for (const bp of parts) {
    if (!bp || !bp.ranked) continue
    const ti = tiers.indexOf(bp.tier)
    if (ti < 0) continue
    const dr = DIVISION_RANK[bp.division] ?? 0
    // +1 baseline per ranked part so the floor (Wood III → 1) still outranks
    // unranked (0): first-time ranking a muscle counts as a promotion.
    score += 1 + ti * 3 + dr
  }
  return score
}

/**
 * Compare the current signature against the last one seen (from storage).
 * Returns { rankedUp, signature }:
 *   - rankedUp is true only when a previous value existed AND the score rose,
 *     so the very first load (or a fresh install) never false-fires.
 * The caller persists `signature` under its own key.
 */
export function detectRankUp(data, previous) {
  const signature = rankSignature(data)
  const rankedUp = previous != null && signature > previous
  return { rankedUp, signature }
}
