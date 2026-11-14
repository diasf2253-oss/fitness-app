// @vitest-environment jsdom
/** RankEmblem — overall-rank averaging, colour shading, and rendering. */
import { cleanup, render, screen } from '@testing-library/react'
import React from 'react'
import { afterEach, describe, expect, it } from 'vitest'

import RankEmblem, { TIERS, overallRank, shade } from './RankEmblem'

afterEach(cleanup)

const COLORS = Object.fromEntries(TIERS.map(t => [t, '#e3b341']))
const payload = parts => ({ tiers: TIERS, tier_colors: COLORS, body_parts: parts })

describe('overallRank', () => {
  it('returns null when nothing is ranked', () => {
    expect(overallRank(payload([{ muscle: 'Chest', ranked: false }]))).toBeNull()
    expect(overallRank(null)).toBeNull()
  })

  it('averages ladder positions across ranked muscles only', () => {
    // Gold III (step 9) + Gold I (step 11) → step 10 = Gold II; unranked ignored
    const r = overallRank(payload([
      { muscle: 'Chest', ranked: true, tier: 'Gold', division: 'III' },
      { muscle: 'Back', ranked: true, tier: 'Gold', division: 'I' },
      { muscle: 'Calves', ranked: false },
    ]))
    expect(r).toMatchObject({ tier: 'Gold', division: 'II', n: 2 })
  })

  it('crosses tier boundaries correctly', () => {
    // Silver I (8) + Platinum III (12) → 10 = Gold II
    const r = overallRank(payload([
      { muscle: 'A', ranked: true, tier: 'Silver', division: 'I' },
      { muscle: 'B', ranked: true, tier: 'Platinum', division: 'III' },
    ]))
    expect(`${r.tier} ${r.division}`).toBe('Gold II')
  })
})

describe('shade', () => {
  it('lightens toward white and darkens toward black', () => {
    expect(shade('#808080', 1)).toBe('#ffffff')
    expect(shade('#808080', -1)).toBe('#000000')
    expect(shade('#808080', 0)).toBe('#808080')
  })
})

describe('<RankEmblem>', () => {
  it('renders every tier with an accessible label and division pips', () => {
    for (const t of TIERS) {
      const { container } = render(<RankEmblem tier={t} division="I" color="#45c2b1" />)
      expect(screen.getByRole('img', { name: `${t} I` })).toBeTruthy()
      // division I = 3 pips (the last <g> group of polygons)
      expect(container.querySelectorAll('g[transform] polygon')).toHaveLength(3)
      cleanup()
    }
  })

  it('renders a muted placeholder when unranked', () => {
    render(<RankEmblem />)
    expect(screen.getByRole('img', { name: 'Unranked' })).toBeTruthy()
  })
})
