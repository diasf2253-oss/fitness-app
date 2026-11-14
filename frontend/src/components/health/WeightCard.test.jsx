// @vitest-environment jsdom
/**
 * WeightCard — the range chip, the headline number (real weigh-ins only,
 * never an interpolated day) and the change figure.
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import WeightCard, { mergeWeight, sliceRange, summarize } from './WeightCard'

// ResponsiveContainer measures its parent; jsdom has no layout.
globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} }

// 90 days ending 2026-11-14, rising 0.1 kg/day from 80.0; the newest day is an
// interpolated estimate (100.0) that must never become the headline, so the
// latest REAL weigh-in is the day before: 88.8 kg.
function makeWeight() {
  const series = []
  const avg = []
  const end = Date.UTC(2026, 10, 14)
  for (let i = 89; i >= 0; i--) {
    const date = new Date(end - i * 86400000).toISOString().slice(0, 10)
    const kg = Math.round((80 + (89 - i) * 0.1) * 10) / 10
    series.push({ date, weight_kg: i === 0 ? 100 : kg, estimated: i === 0 })
    avg.push({ date, avg_kg: kg })
  }
  return { series, moving_avg_7d: avg }
}

const renderCard = weight => render(<MemoryRouter><WeightCard weight={weight} /></MemoryRouter>)

beforeEach(() => { try { localStorage.clear() } catch { /* ignore */ } })
afterEach(cleanup)

describe('weight helpers', () => {
  it('slices by calendar days counted back from the newest point', () => {
    const pts = mergeWeight(makeWeight())
    expect(pts).toHaveLength(90)
    expect(sliceRange(pts, 7)).toHaveLength(7)
    expect(sliceRange(pts, 30)).toHaveLength(30)
    expect(sliceRange(pts, 90)).toHaveLength(90)
    expect(sliceRange([], 30)).toEqual([])
  })

  it('headlines the latest REAL weigh-in, skipping estimated days', () => {
    const s = summarize(sliceRange(mergeWeight(makeWeight()), 7))
    expect(s.latest.weight_kg).toBe(88.8)        // not the 100 kg estimate
    expect(s.latest.estimated).toBe(false)
    expect(s.change).toBe(0.5)                    // 88.8 − 88.3 over the real days in range
  })

  it('returns null when there is no real reading at all', () => {
    expect(summarize([{ date: '2026-11-14', weight_kg: 80, estimated: true, avg_kg: null }])).toBeNull()
  })
})

describe('<WeightCard>', () => {
  it('defaults to 30D and the chip cycles 7D → 30D → 90D', () => {
    renderCard(makeWeight())
    const chip = screen.getByRole('button', { name: /showing 30 days/i })
    expect(chip.textContent).toBe('30D')
    fireEvent.click(chip)
    expect(chip.textContent).toBe('90D')
    fireEvent.click(chip)
    expect(chip.textContent).toBe('7D')
    fireEvent.click(chip)
    expect(chip.textContent).toBe('30D')
  })

  it('shows the real latest weight and the change for the range', () => {
    renderCard(makeWeight())
    expect(screen.getByTestId('weight-latest').textContent).toBe('88.8')
    // 30D: real days run 86.0 → 88.8
    expect(screen.getByTestId('weight-change').textContent).toContain('▲ 2.8 kg')
  })

  it('shows the empty state with no data', () => {
    renderCard({ series: [], moving_avg_7d: [] })
    expect(screen.getByText(/No weight readings yet/i)).toBeTruthy()
    expect(screen.queryByTestId('weight-latest')).toBeNull()
  })
})
