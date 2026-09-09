/**
 * Tests for the local-first weight logic (P2). The expected values mirror
 * backend/tests/test_weight_estimate.py one-for-one — if these pass, the
 * JS port computes exactly what the Python backend computes.
 */
import { describe, expect, it } from 'vitest'
import {
  buildWeightSeries, estimateWeightFor, movingAverage7d,
  realWeightPoints, resolvedWeightFor, writeBlocked,
} from './weights'

const w = (date, weight_kg, source = 'manual') => ({ date, weight_kg, source })

describe('estimateWeightFor', () => {
  it('midpoint is linear interpolation (mirrors test_midpoint)', () => {
    const points = realWeightPoints([w('2026-06-01', 84.0), w('2026-06-11', 82.0)])
    const r = estimateWeightFor('2026-06-06', points)
    expect(r.method).toBe('interpolated')
    expect(r.kg).toBeCloseTo(83.0, 1)
  })

  it('is distance-weighted (mirrors test_distance_weighted)', () => {
    const points = realWeightPoints([w('2026-06-01', 90.0), w('2026-06-11', 80.0)])
    expect(estimateWeightFor('2026-06-03', points).kg).toBeCloseTo(88.0, 1)
  })

  it('carries forward after the last reading', () => {
    const points = realWeightPoints([w('2026-06-01', 84.0), w('2026-06-05', 83.4)])
    const r = estimateWeightFor('2026-06-20', points)
    expect(r.method).toBe('carried_forward')
    expect(r.kg).toBeCloseTo(83.4, 1)
  })

  it('carries back before the first reading', () => {
    const points = realWeightPoints([w('2026-06-10', 81.0)])
    const r = estimateWeightFor('2026-06-05', points)
    expect(r.method).toBe('carried_back')
    expect(r.kg).toBeCloseTo(81.0, 1)
  })

  it('returns null with no data', () => {
    expect(estimateWeightFor('2026-06-01', [])).toBeNull()
  })

  it('never compounds on derived rows (mirrors test_estimates_never_compound)', () => {
    const rows = [
      w('2026-06-01', 84.0), w('2026-06-11', 82.0),
      w('2026-06-06', 99.0, 'estimated'),   // pollution must be ignored
    ]
    const r = estimateWeightFor('2026-06-07', realWeightPoints(rows))
    expect(r.kg).toBeCloseTo(82.8, 1)       // on the 84→82 line, not near 99
  })
})

describe('writeBlocked (source precedence)', () => {
  it('manual is only overwritten by manual', () => {
    expect(writeBlocked(w('d', 83, 'manual'), 'apple_health')).toBe(true)
    expect(writeBlocked(w('d', 83, 'manual'), 'estimated')).toBe(true)
    expect(writeBlocked(w('d', 83, 'manual'), 'manual')).toBe(false)
  })

  it('derived never buries a real reading, real overwrites derived', () => {
    expect(writeBlocked(w('d', 83, 'apple_health'), 'estimated')).toBe(true)
    expect(writeBlocked(w('d', 83, 'apple_health'), 'sample')).toBe(true)
    expect(writeBlocked(w('d', 83, 'estimated'), 'apple_health')).toBe(false)
    expect(writeBlocked(w('d', 83, 'sample'), 'manual')).toBe(false)
  })

  it('no row blocks nothing', () => {
    expect(writeBlocked(null, 'estimated')).toBe(false)
  })
})

describe('resolvedWeightFor', () => {
  it('sample day shows interpolation, not its own value (mirrors sample tests)', () => {
    const rows = [
      w('2026-06-01', 78.0, 'apple_health'), w('2026-06-11', 77.0, 'apple_health'),
      w('2026-06-06', 84.0, 'sample'),
    ]
    const r = resolvedWeightFor('2026-06-06', rows[2], realWeightPoints(rows))
    expect(r.estimated).toBe(true)
    expect(r.kg).toBeCloseTo(77.5, 1)
  })

  it('pure demo database still shows the stored value', () => {
    const row = w('2026-06-01', 84.0, 'sample')
    const r = resolvedWeightFor('2026-06-01', row, realWeightPoints([row]))
    expect(r.estimated).toBe(false)
    expect(r.kg).toBe(84.0)
  })
})

describe('buildWeightSeries', () => {
  it('fills gaps with flagged estimates (mirrors test_dashboard_fills_gaps)', () => {
    const today = '2026-07-10'
    const rows = [w('2026-07-06', 84.0), w(today, 83.0)]
    const { series } = buildWeightSeries(rows, today)
    const byDate = Object.fromEntries(series.map(p => [p.date, p]))
    expect(byDate[today].estimated).toBe(false)
    expect(byDate['2026-07-08'].estimated).toBe(true)
    expect(byDate['2026-07-08'].weight_kg).toBeCloseTo(83.5, 1)
    expect(series).toHaveLength(5)          // continuous 6th → 10th
  })

  it('moving average runs over real readings only', () => {
    const today = '2026-07-10'
    const rows = [w('2026-07-08', 84.0), w('2026-07-09', 83.0), w(today, 82.0)]
    const { moving_avg_7d } = buildWeightSeries(rows, today)
    expect(moving_avg_7d).toHaveLength(3)
    expect(moving_avg_7d[2].avg_kg).toBeCloseTo(83.0, 2)
  })
})

describe('movingAverage7d', () => {
  it('averages the trailing 7-day window including gaps', () => {
    const series = [
      { date: '2026-07-01', weight_kg: 84 },
      { date: '2026-07-05', weight_kg: 82 },   // 4-day gap contributes nothing
      { date: '2026-07-10', weight_kg: 80 },   // 01 falls out of its window
    ]
    const avg = movingAverage7d(series)
    expect(avg[0].avg_kg).toBeCloseTo(84, 2)
    expect(avg[1].avg_kg).toBeCloseTo(83, 2)
    expect(avg[2].avg_kg).toBeCloseTo(81, 2)   // (82+80)/2 — 84 aged out
  })
})
