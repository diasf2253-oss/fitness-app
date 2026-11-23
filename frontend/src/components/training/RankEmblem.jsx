/**
 * RankEmblem — an original SVG emblem per tier, in the spirit of competitive
 * game rank icons: the silhouette grows more elaborate as you climb, and small
 * pips underneath show the division (III = 1 pip … I = 3 pips).
 *
 *   Wood      rounded plaque        Platinum  faceted rhombus
 *   Bronze    shield                Diamond   cut gem
 *   Silver    double-rim shield     Champion  gem with wings
 *   Gold      faceted hexagon       Titan     spiked crest
 *                                   Olympian  radiant star
 *
 * Colours are NOT chosen here — they come from the rank engine
 * (backend/app/services/training/ranks.py TIER_COLORS, mirrored in src/local/api/ranks.js) and
 * are passed in, so the emblem, body map and badges always agree.
 */
import React, { useId } from 'react'

// Mirrors backend/app/services/training/ranks.py TIERS (ascending).
export const TIERS = ['Wood', 'Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond', 'Champion', 'Titan', 'Olympian']
const DIVISION_PIPS = { III: 1, II: 2, I: 3 }
const DIVISIONS = ['III', 'II', 'I']

/** Lighten (amt > 0) or darken (amt < 0) a #rrggbb colour. */
export function shade(hex, amt) {
  const n = parseInt(hex.replace('#', ''), 16)
  const ch = s => {
    const v = (n >> s) & 255
    return Math.max(0, Math.min(255, Math.round(amt > 0 ? v + (255 - v) * amt : v * (1 + amt))))
  }
  return `#${[16, 8, 0].map(s => ch(s).toString(16).padStart(2, '0')).join('')}`
}

/**
 * One headline rank for the whole body: the average ladder position
 * (tierIndex × 3 + division step) across every ranked body part, rounded.
 * Returns null when nothing is ranked yet.
 */
export function overallRank(data) {
  const tiers = data?.tiers?.length ? data.tiers : TIERS
  const ranked = (data?.body_parts || []).filter(b => b?.ranked && tiers.includes(b.tier))
  if (!ranked.length) return null
  const steps = ranked.map(b => tiers.indexOf(b.tier) * 3 + Math.max(0, DIVISIONS.indexOf(b.division)))
  const avg = Math.round(steps.reduce((a, b) => a + b, 0) / steps.length)
  const tier = tiers[Math.floor(avg / 3)]
  return {
    tier,
    division: DIVISIONS[avg % 3],
    color: data?.tier_colors?.[tier] || '#93a08c',
    n: ranked.length,
  }
}

// Each body is drawn in a 64×64 box (emblem in y≈4–54, pips below).
function Body({ ti, fill, rim, hi }) {
  const common = { fill, stroke: rim, strokeWidth: 1.6, strokeLinejoin: 'round' }
  const facet = { fill: 'none', stroke: hi, strokeWidth: 1.1, strokeOpacity: 0.55, strokeLinejoin: 'round' }
  const SHIELD = 'M32 6 L52 13 V30 C52 43 43 50 32 55 C21 50 12 43 12 30 V13 Z'
  switch (ti) {
    case 0: return (
      <g>
        <rect x="14" y="12" width="36" height="36" rx="9" {...common} />
        <path d="M21 24 H43 M21 31 H43 M21 38 H37" {...facet} />
      </g>
    )
    case 1: return (
      <g>
        <path d={SHIELD} {...common} />
        <path d="M32 18 V44" {...facet} />
      </g>
    )
    case 2: return (
      <g>
        <path d={SHIELD} {...common} />
        <path d="M32 12 L46 17 V30 C46 39 40 44 32 48 C24 44 18 39 18 30 V17 Z" {...facet} />
        <path d="M24 30 L32 24 L40 30" {...facet} strokeOpacity={0.8} />
      </g>
    )
    case 3: return (
      <g>
        <polygon points="32,5 54,17.5 54,42.5 32,55 10,42.5 10,17.5" {...common} />
        <polygon points="32,16 44,23 44,37 32,44 20,37 20,23" {...facet} />
        <path d="M32 5 V16 M54 17.5 L44 23 M54 42.5 L44 37 M32 55 V44 M10 42.5 L20 37 M10 17.5 L20 23" {...facet} strokeOpacity={0.35} />
      </g>
    )
    case 4: return (
      <g>
        <polygon points="32,4 56,30 32,56 8,30" {...common} />
        <path d="M32 4 L32 56 M8 30 L56 30" {...facet} strokeOpacity={0.35} />
        <polygon points="32,16 44,30 32,44 20,30" {...facet} />
      </g>
    )
    case 5: return (
      <g>
        <polygon points="20,9 44,9 57,23 32,56 7,23" {...common} />
        <path d="M7 23 H57 M20 9 L26 23 L32 56 L38 23 L44 9 M26 23 L32 9 L38 23" {...facet} />
      </g>
    )
    case 6: return (
      <g>
        <path d="M22 22 C14 18 7 20 3 26 C9 26 12 29 13 33 C16 30 19 30 22 32 Z" {...common} />
        <path d="M42 22 C50 18 57 20 61 26 C55 26 52 29 51 33 C48 30 45 30 42 32 Z" {...common} />
        <polygon points="24,8 40,8 50,20 32,54 14,20" {...common} />
        <path d="M14 20 H50 M24 8 L28 20 L32 54 L36 20 L40 8" {...facet} />
      </g>
    )
    case 7: return (
      <g>
        <path d="M10 22 L18 7 L25 17 L32 3 L39 17 L46 7 L54 22 L50 41 L32 55 L14 41 Z" {...common} />
        <path d="M17 26 H47 L44 39 L32 48 L20 39 Z" {...facet} />
        <circle cx="32" cy="34" r="4" fill={hi} fillOpacity={0.6} />
      </g>
    )
    default: {
      // Olympian: 8-point radiant star around a gem
      const pts = []
      for (let i = 0; i < 16; i++) {
        const r = i % 2 === 0 ? 27 : 13
        const a = (Math.PI * 2 * i) / 16 - Math.PI / 2
        pts.push(`${(32 + r * Math.cos(a)).toFixed(1)},${(30 + r * Math.sin(a)).toFixed(1)}`)
      }
      return (
        <g>
          <polygon points={pts.join(' ')} {...common} />
          <circle cx="32" cy="30" r="9" fill={rim} stroke={hi} strokeWidth="1.2" />
          <polygon points="32,23 38,30 32,37 26,30" fill={hi} fillOpacity={0.75} />
        </g>
      )
    }
  }
}

/**
 * <RankEmblem tier="Gold" division="II" color="#e3b341" size={48} />
 * Unranked (no tier) renders a muted outline plaque.
 */
export default function RankEmblem({ tier, division, color, size = 40, title }) {
  const gid = useId().replace(/:/g, '')
  const ti = TIERS.indexOf(tier)
  const label = title ?? (ti >= 0 ? `${tier} ${division || ''}`.trim() : 'Unranked')

  if (ti < 0) {
    return (
      <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label={label}>
        <rect x="14" y="12" width="36" height="36" rx="9" fill="none"
          stroke="rgba(241, 234, 217,0.28)" strokeWidth="1.6" strokeDasharray="4 4" />
      </svg>
    )
  }

  const base = color || '#93a08c'
  const top = shade(base, 0.35)
  const bottom = shade(base, -0.45)
  const rim = shade(base, 0.55)
  const hi = shade(base, 0.8)
  const pips = DIVISION_PIPS[division] || 0

  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label={label}>
      <defs>
        <linearGradient id={`g${gid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={top} />
          <stop offset="100%" stopColor={bottom} />
        </linearGradient>
      </defs>
      <Body ti={ti} fill={`url(#g${gid})`} rim={rim} hi={hi} />
      {pips > 0 && (
        <g transform={`translate(${32 - (pips - 1) * 4.5} 60)`}>
          {Array.from({ length: pips }, (_, i) => (
            <polygon key={i} points={`${i * 9},-2.6 ${i * 9 + 2.6},0 ${i * 9},2.6 ${i * 9 - 2.6},0`} fill={rim} />
          ))}
        </g>
      )}
    </svg>
  )
}
