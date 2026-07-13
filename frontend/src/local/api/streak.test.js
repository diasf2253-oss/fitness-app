/**
 * Streak port parity — expected values mirror backend/tests/test_streak.py so
 * the phone and laptop compute the same chain.
 */
import { describe, expect, it } from 'vitest'
import { computeStreak } from './streak'

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
