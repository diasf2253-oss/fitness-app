/**
 * Streak port parity — expected values mirror backend/tests/test_streak.py so
 * the phone and laptop compute the same chain.
 */
import { describe, expect, it } from 'vitest'
import { computeStreak, mergeActiveDays } from './streak'

const D = (...days) => days.map(d => `2026-06-${String(d).padStart(2, '0')}`)

describe('computeStreak', () => {
  it('empty history', () => {
    const r = computeStreak([], 1, '2026-06-26')
    expect(r.current).toBe(0)
    expect(r.longest).toBe(0)
    expect(r.last_workout_date).toBe(null)
  })

  it('a rest day keeps the streak (gap 1)', () => {
    const r = computeStreak(D(20, 22, 24, 26), 1, '2026-06-26')
    expect(r.current).toBe(4)
    expect(r.longest).toBe(4)
    expect(r.alive).toBe(true)
    expect(r.at_risk).toBe(false)
  })

  it('two rest days break the chain', () => {
    const r = computeStreak(D(20, 23, 24), 1, '2026-06-25')
    expect(r.longest).toBe(2)
    expect(r.current).toBe(2)
    expect(r.alive).toBe(true)
  })

  it('broken when the gap is exceeded since the last workout', () => {
    const r = computeStreak(D(21, 22, 23), 1, '2026-06-26')
    expect(r.alive).toBe(false)
    expect(r.current).toBe(0)
    expect(r.longest).toBe(3)
  })

  it('at risk on the last allowed day', () => {
    const r = computeStreak(D(22, 24), 1, '2026-06-26')
    expect(r.alive).toBe(true)
    expect(r.at_risk).toBe(true)
    expect(r.current).toBe(2)
  })

  it('a configurable gap allows more rest', () => {
    expect(computeStreak(D(20, 23, 26), 1, '2026-06-26').longest).toBe(1)
    expect(computeStreak(D(20, 23, 26), 2, '2026-06-26').current).toBe(3)
  })
})

// Mirrors the T6a endpoint tests in backend/tests/test_streak.py
describe('mergeActiveDays (T6a: any active day)', () => {
  it('sport sessions bridge workout gaps', () => {
    const days = mergeActiveDays(
      new Set(D(26, 22)),
      [
        { date: '2026-06-24', type: 'football', source: 'manual' },
        { date: '2026-06-23', type: 'judo', source: 'manual' },
      ],
      [],
    )
    expect(computeStreak([...days], 1, '2026-06-26').current).toBe(4)
  })

  it('10k-step days count, fewer steps do not', () => {
    const days = mergeActiveDays(
      new Set(D(26, 22)),
      [],
      [
        { date: '2026-06-24', steps: 11500, source: 'apple_health' },
        { date: '2026-06-23', steps: 4000, source: 'apple_health' },
      ],
    )
    expect(days.has('2026-06-24')).toBe(true)
    expect(days.has('2026-06-23')).toBe(false)
    expect(computeStreak([...days], 1, '2026-06-26').current).toBe(3)
  })

  it('sample rows never count', () => {
    const days = mergeActiveDays(
      new Set(D(26)),
      [{ date: '2026-06-24', type: 'padel', source: 'sample' }],
      [{ date: '2026-06-23', steps: 20000, source: 'sample' }],
    )
    expect(computeStreak([...days], 1, '2026-06-26').current).toBe(1)
  })
})
