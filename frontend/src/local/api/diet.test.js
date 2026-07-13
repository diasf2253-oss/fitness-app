/**
 * Diet-engine port parity — mirrors backend/tests/test_calorie_adapt.py and
 * test_nutrition_rda.py, so the phone adapts calories + classifies micros
 * identically to the laptop.
 */
import { describe, expect, it } from 'vitest'
import { adaptTarget, buildBreakdown, carbsFromTarget } from './diet'

const JUN8 = '2026-06-08', JUN15 = '2026-06-15', JUN1 = '2026-06-01'
const TODAY = '2026-06-23'

function wk(monday, ...weights) {
  const out = {}
  const base = Date.parse(monday + 'T00:00:00Z')
  weights.forEach((w, i) => {
    out[new Date(base + i * 86400000).toISOString().slice(0, 10)] = w
  })
  return out
}

const run = (weightByDate, opts = {}) => adaptTarget({
  currentTarget: opts.current ?? 2300, targetLossKgPerWeek: opts.targetLoss ?? 0.5,
  stepKcal: opts.step ?? 100, toleranceKg: opts.tol ?? 0.15,
  floor: opts.floor ?? 1800, ceiling: opts.ceiling ?? null,
  weightByDate, today: opts.today ?? TODAY, lastAdaptedWeek: opts.lastWeek ?? null,
})

describe('adaptTarget', () => {
  it('losing faster than target → increase', () => {
    const w = { ...wk(JUN8, 79.9, 80.0, 80.1), ...wk(JUN15, 79.1, 79.2, 79.3) }
    const r = run(w)
    expect(r.due).toBe(true)
    expect(r.reason).toBe('increase')
    expect(r.target).toBe(2400)
    expect(r.changed).toBe(true)
    expect(r.actual_change_kg).toBe(-0.8)
  })

  it('losing slower than target → decrease', () => {
    const w = { ...wk(JUN8, 79.9, 80.0, 80.1), ...wk(JUN15, 79.7, 79.8, 79.9) }
    const r = run(w)
    expect(r.reason).toBe('decrease')
    expect(r.target).toBe(2200)
  })

  it('within tolerance → hold', () => {
    const w = { ...wk(JUN8, 79.9, 80.0, 80.1), ...wk(JUN15, 79.4, 79.5, 79.6) }
    const r = run(w)
    expect(r.reason).toBe('hold')
    expect(r.target).toBe(2300)
    expect(r.changed).toBe(false)
  })

  it('fewer than three entries → holds (insufficient data)', () => {
    const w = { ...wk(JUN8, 79.9, 80.0, 80.1), ...wk(JUN15, 79.0, 79.1) }
    const r = run(w)
    expect(r.reason).toBe('insufficient_data')
    expect(r.changed).toBe(false)
    expect(r.entries_completed_week).toBe(2)
  })

  it('needs two consecutive completed weeks', () => {
    expect(run({ ...wk(JUN15, 79.1, 79.2, 79.3) }).reason).toBe('insufficient_data')
    const w = { ...wk(JUN1, 80.4, 80.5, 80.6), ...wk(JUN15, 79.1, 79.2, 79.3) }
    expect(run(w).reason).toBe('insufficient_data')
  })

  it('respects the floor', () => {
    const w = { ...wk(JUN8, 79.9, 80.0, 80.1), ...wk(JUN15, 79.7, 79.8, 79.9) }
    expect(run(w, { current: 1850, floor: 1800 }).target).toBe(1800)
  })
})

describe('carbsFromTarget', () => {
  it('fills the remaining calories after protein + fat', () => {
    // (2300 − 180*4 − 100*9) / 4 = (2300 − 720 − 900)/4 = 170
    expect(carbsFromTarget(2300, 180, 100)).toBe(170)
  })
})

describe('buildBreakdown', () => {
  it('classifies against sex-specific RDA', () => {
    // Iron male RDA 8 mg; 8 mg intake = 100% → meets
    const rows = buildBreakdown({ iron_mg: 8 }, 'male')
    const iron = rows.find(r => r.name === 'iron')
    expect(iron.pct).toBe(100)
    expect(iron.status).toBe('meets')
    // Same intake for female (RDA 18) → ~44% → low
    const rowsF = buildBreakdown({ iron_mg: 8 }, 'female')
    expect(rowsF.find(r => r.name === 'iron').status).toBe('low')
  })
})
