/**
 * Tests for the pure math ported in P3/P4 — expected values mirror the
 * backend implementations (stats.py, trackers.py, insights.py) and the
 * backend test suite where cases exist there.
 */
import { describe, expect, it } from 'vitest'
import { epley1rm, isWorkingSet } from './workout'
import { habitStreak } from './trackers'
import { isoWeekKey, pearson } from './util'

describe('epley1rm (mirrors stats.epley_1rm + test_stats.py)', () => {
  it('returns weight unchanged for singles', () => {
    expect(epley1rm(100, 1)).toBe(100)
    expect(epley1rm(100, 0)).toBe(100)
  })

  it('applies weight × (1 + reps/30)', () => {
    expect(epley1rm(100, 6)).toBeCloseTo(120, 5)     // 100 × 1.2
    expect(epley1rm(80, 10)).toBeCloseTo(80 * (1 + 10 / 30), 5)
  })

  it('caps reps at 12 — a 20-rep set estimates like a 12-rep set', () => {
    expect(epley1rm(60, 20)).toBeCloseTo(epley1rm(60, 12), 5)
    expect(epley1rm(60, 12)).toBeCloseTo(60 * 1.4, 5)
  })
})

describe('isWorkingSet (mirrors the working-set filter in stats.py)', () => {
  const base = { is_completed: true, is_warmup: false, reps: 8, weight_kg: 80 }
  it('accepts completed non-warmup sets with reps and weight', () => {
    expect(isWorkingSet(base)).toBe(true)
  })
  it('rejects warmups, incomplete, zero-rep and zero-weight sets', () => {
    expect(isWorkingSet({ ...base, is_warmup: true })).toBe(false)
    expect(isWorkingSet({ ...base, is_completed: false })).toBe(false)
    expect(isWorkingSet({ ...base, reps: 0 })).toBe(false)
    expect(isWorkingSet({ ...base, weight_kg: 0 })).toBe(false)
  })
})

describe('habitStreak (mirrors trackers.habit_streak)', () => {
  it('counts consecutive done-days ending today', () => {
    const done = new Set(['2026-07-08', '2026-07-09', '2026-07-10'])
    expect(habitStreak(done, '2026-07-10')).toBe(3)
  })

  it('an unlogged today does not break the streak', () => {
    const done = new Set(['2026-07-08', '2026-07-09'])
    expect(habitStreak(done, '2026-07-10')).toBe(2)
  })

  it('a gap resets the count', () => {
    const done = new Set(['2026-07-05', '2026-07-09', '2026-07-10'])
    expect(habitStreak(done, '2026-07-10')).toBe(2)
  })

  it('empty history is a zero streak', () => {
    expect(habitStreak(new Set(), '2026-07-10')).toBe(0)
  })
})

describe('pearson (mirrors insights.pearson)', () => {
  it('perfect positive and negative correlation', () => {
    expect(pearson([1, 2, 3], [2, 4, 6])).toBeCloseTo(1, 5)
    expect(pearson([1, 2, 3], [6, 4, 2])).toBeCloseTo(-1, 5)
  })
  it('constant series and n<2 are undefined (null)', () => {
    expect(pearson([1, 1, 1], [2, 4, 6])).toBeNull()
    expect(pearson([1], [2])).toBeNull()
  })
})

describe('isoWeekKey (mirrors Python isocalendar keying in stats.py)', () => {
  it('matches Python isocalendar for known dates', () => {
    // datetime(2026, 7, 10).isocalendar() → (2026, 28, 5)
    expect(isoWeekKey('2026-07-10T18:00:00')).toBe('2026-W28')
    // Year-boundary: Jan 1 2027 is a Friday → ISO week 53 of 2026
    expect(isoWeekKey('2027-01-01T10:00:00')).toBe('2026-W53')
    // Dec 29 2025 (Monday) → ISO week 1 of 2026
    expect(isoWeekKey('2025-12-29T10:00:00')).toBe('2026-W01')
  })
})
