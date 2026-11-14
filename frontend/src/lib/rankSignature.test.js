/**
 * Rank-up detection parity: a promotion (tier/division up, or unranked→ranked)
 * must raise the signature; LP drift within a division must not.
 */
import { describe, expect, it } from 'vitest'
import { rankSignature, detectRankUp } from './rankSignature'

const TIERS = ['Wood', 'Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond', 'Champion', 'Titan', 'Olympian']

const data = (parts) => ({ tiers: TIERS, body_parts: parts })
const bp = (muscle, tier, division, lp, ranked = true) => ({ muscle, tier, division, lp, ranked })

describe('rankSignature', () => {
  it('is zero when nothing is ranked', () => {
    expect(rankSignature(data([bp('Chest', null, null, null, false)]))).toBe(0)
    expect(rankSignature({})).toBe(0)
  })

  it('rises with tier and with division within a tier', () => {
    const woodIII = rankSignature(data([bp('Chest', 'Wood', 'III', 0)]))
    const woodI = rankSignature(data([bp('Chest', 'Wood', 'I', 0)]))
    const bronzeIII = rankSignature(data([bp('Chest', 'Bronze', 'III', 0)]))
    expect(woodI).toBeGreaterThan(woodIII)     // division promotion
    expect(bronzeIII).toBeGreaterThan(woodI)   // tier promotion outranks division
  })

  it('ignores LP changes within the same division', () => {
    const lo = rankSignature(data([bp('Chest', 'Gold', 'II', 10)]))
    const hi = rankSignature(data([bp('Chest', 'Gold', 'II', 95)]))
    expect(hi).toBe(lo)
  })

  it('sums across body parts', () => {
    const one = rankSignature(data([bp('Chest', 'Silver', 'I', 0)]))
    const two = rankSignature(data([bp('Chest', 'Silver', 'I', 0), bp('Back', 'Silver', 'I', 0)]))
    expect(two).toBe(one * 2)
  })
})

describe('detectRankUp', () => {
  const d = data([bp('Chest', 'Silver', 'II', 40)])

  it('never fires on the first load (no previous value)', () => {
    const { rankedUp, signature } = detectRankUp(d, null)
    expect(rankedUp).toBe(false)
    expect(signature).toBeGreaterThan(0)
  })

  it('fires when the signature climbs', () => {
    const prev = rankSignature(data([bp('Chest', 'Silver', 'III', 90)]))
    const { rankedUp } = detectRankUp(d, prev)  // III → II is a promotion
    expect(rankedUp).toBe(true)
  })

  it('does not fire on an LP-only gain', () => {
    const prev = rankSignature(data([bp('Chest', 'Silver', 'II', 10)]))
    const { rankedUp } = detectRankUp(d, prev)  // same division, more LP
    expect(rankedUp).toBe(false)
  })

  it('fires when a previously unranked muscle becomes ranked', () => {
    const prev = rankSignature(data([bp('Chest', null, null, null, false)]))
    const now = data([bp('Chest', 'Wood', 'III', 0)])
    expect(detectRankUp(now, prev).rankedUp).toBe(true)
  })
})
