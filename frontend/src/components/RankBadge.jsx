/**
 * Per-exercise rank accent + tier badge.
 *
 * Colours are NOT chosen here — they come from the rank engine
 * (backend/app/ranks.py TIER_COLORS / UNRANKED_COLOR, mirrored 1:1 in
 * src/local/api/ranks.js) via GET /api/ranks/exercises, so the body map and the
 * exercise cards can never drift apart. Tune the thresholds in ranks.py
 * (EXERCISE_BENCHMARK / COMMON_ANCHORS), not in this file.
 */
import React, { useEffect, useState } from 'react'
import { apiFetch } from '../api'

/**
 * {exercise_id: {ranked, tier, division, lp, color}} for every visible
 * exercise. Keyed by whatever the API calls `id` (a uuid in local-first mode),
 * so a lookup works in both modes. Failures degrade to "everything unranked"
 * rather than breaking the page.
 */
export function useExerciseRanks() {
  const [ranks, setRanks] = useState({})
  useEffect(() => {
    let alive = true
    apiFetch('/api/ranks/exercises')
      .then(r => { if (alive) setRanks(r || {}) })
      .catch(() => {})
    return () => { alive = false }
  }, [])
  return ranks
}

/** Left-edge accent for an exercise card, tinted by rank (muted when unranked). */
export function rankAccent(rank) {
  return { borderLeft: `4px solid ${rank?.color || 'var(--color-border)'}` }
}

/** "Gold II" pill in the tier colour. Renders nothing for an unranked exercise. */
export function RankBadge({ rank, style }) {
  if (!rank?.ranked) return null
  return (
    <span
      className="badge"
      title={`${rank.tier} ${rank.division} · ${rank.lp} LP`}
      style={{ background: 'transparent', color: rank.color, borderColor: rank.color, ...style }}
    >
      {rank.tier} {rank.division}
    </span>
  )
}
