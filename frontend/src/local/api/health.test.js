/**
 * Sync-status parity — expected values mirror
 * backend/tests/test_health_shortcut.py::TestSyncStatus so the phone and the
 * laptop agree on whether health data is actually arriving.
 */
import { describe, expect, it } from 'vitest'
import { buildSyncStatus, lastRealDate } from './health'

const TODAY = '2026-09-08'
const NONE = { last_date: null, days_stale: null }

describe('lastRealDate', () => {
  it('is null for no rows', () => {
    expect(lastRealDate([])).toBe(null)
  })

  it('picks the newest date regardless of array order', () => {
    expect(lastRealDate([
      { date: '2026-09-01', source: 'manual' },
      { date: '2026-09-07', source: 'apple_health' },
      { date: '2026-09-03', source: 'manual' },
    ])).toBe('2026-09-07')
  })

  it('ignores estimated and sample rows', () => {
    expect(lastRealDate([
      { date: '2026-09-08', source: 'estimated' },
      { date: '2026-09-07', source: 'sample' },
      { date: '2026-09-02', source: 'apple_health' },
    ])).toBe('2026-09-02')
  })

  it('is null when every row is derived', () => {
    expect(lastRealDate([
      { date: '2026-09-08', source: 'estimated' },
      { date: '2026-09-07', source: 'sample' },
    ])).toBe(null)
  })
})

describe('buildSyncStatus', () => {
  it('never-synced shape', () => {
    const s = buildSyncStatus({}, TODAY)
    expect(s.last_ingest).toBe(null)
    expect(s.has_any_data).toBe(false)
    expect(s.stalest_days).toBe(null)
    for (const m of ['weight', 'steps', 'sleep', 'nutrition']) expect(s[m]).toEqual(NONE)
  })

  it('reports today as zero days stale', () => {
    const s = buildSyncStatus({
      weight: [{ date: TODAY, source: 'apple_health' }],
      steps: [{ date: TODAY, source: 'apple_health' }],
    }, TODAY, '2026-09-08T08:01:14')
    expect(s.weight).toEqual({ last_date: TODAY, days_stale: 0 })
    expect(s.steps).toEqual({ last_date: TODAY, days_stale: 0 })
    // Nothing posted sleep or nutrition — unknown, not "fresh"
    expect(s.sleep).toEqual(NONE)
    expect(s.has_any_data).toBe(true)
    expect(s.last_ingest).toBe('2026-09-08T08:01:14')
  })

  it('stalest_days is the worst metric', () => {
    const s = buildSyncStatus({
      weight: [{ date: TODAY, source: 'apple_health' }],
      steps: [{ date: '2026-09-04', source: 'apple_health' }],
    }, TODAY)
    expect(s.weight.days_stale).toBe(0)
    expect(s.steps.days_stale).toBe(4)
    expect(s.stalest_days).toBe(4)
  })

  it('derived rows do not count as fresh', () => {
    const s = buildSyncStatus({
      weight: [{ date: TODAY, source: 'estimated' }],
    }, TODAY)
    expect(s.weight).toEqual(NONE)
    expect(s.has_any_data).toBe(false)
  })

  it('manual entries count as real', () => {
    const s = buildSyncStatus({
      weight: [{ date: TODAY, source: 'manual' }],
    }, TODAY)
    expect(s.weight).toEqual({ last_date: TODAY, days_stale: 0 })
  })

  it('spans a month boundary correctly', () => {
    const s = buildSyncStatus({
      steps: [{ date: '2026-08-30', source: 'apple_health' }],
    }, '2026-09-02')
    expect(s.steps.days_stale).toBe(3)
  })
})
