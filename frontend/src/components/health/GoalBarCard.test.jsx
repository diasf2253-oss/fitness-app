// @vitest-environment jsdom
/** GoalBarCard — day slicing, averages (missing ≠ zero), goal hits, range chip. */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import GoalBarCard, { buildDays, summarizeDays } from './GoalBarCard'

beforeEach(() => { try { localStorage.clear() } catch { /* ignore */ } })
afterEach(cleanup)

const END = '2026-11-14'

describe('buildDays', () => {
  it('returns one entry per calendar day ending today, gaps as null', () => {
    const days = buildDays([{ date: '2026-11-14', value: 10000 }, { date: '2026-11-12', value: 5000 }], 3, END)
    expect(days).toEqual([
      { date: '2026-11-12', value: 5000 },
      { date: '2026-11-13', value: null },
      { date: '2026-11-14', value: 10000 },
    ])
  })
})

describe('summarizeDays', () => {
  it('averages only days with a reading and counts goal hits', () => {
    const s = summarizeDays([
      { date: 'a', value: 12000 }, { date: 'b', value: null }, { date: 'c', value: 6000 }, { date: 'd', value: 9000 },
    ], 9000)
    expect(s).toEqual({ avg: 9000, logged: 3, hits: 2 })   // 9000 exactly counts as a hit
  })

  it('is null when nothing was logged', () => {
    expect(summarizeDays([{ date: 'a', value: null }], 9000)).toBeNull()
  })
})

describe('<GoalBarCard>', () => {
  // A reading every day for 90 days ending today: 8000 on even offsets, 11000 on odd.
  function points() {
    const out = []
    const now = new Date()
    const today = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
    for (let i = 0; i < 90; i++) {
      const d = new Date(Date.parse(today + 'T00:00:00Z') - i * 86400000).toISOString().slice(0, 10)
      out.push({ date: d, value: i % 2 ? 11000 : 8000 })
    }
    return out
  }

  const renderCard = pts => render(
    <GoalBarCard label="Steps" points={pts} goal={9000} goalLabel="9k" unit="steps"
      formatValue={v => Math.round(v).toLocaleString('en-US')} storageKey="t_range"
      empty={<p>No step data yet.</p>} />,
  )

  it('defaults to 30D, shows the average and goal hits, and cycles 30 → 60 → 90', () => {
    renderCard(points())
    const chip = screen.getByRole('button', { name: /showing 30 days/i })
    expect(screen.getByTestId('goal-avg').textContent).toBe('9,500')
    expect(screen.getByTestId('goal-hits').textContent).toContain('15 of 30 days ≥ 9k')
    fireEvent.click(chip)
    expect(chip.textContent).toBe('60D')
    expect(screen.getByTestId('goal-hits').textContent).toContain('30 of 60 days')
    fireEvent.click(chip)
    expect(chip.textContent).toBe('90D')
    fireEvent.click(chip)
    expect(chip.textContent).toBe('30D')
  })

  it('draws an overflow segment only for days over the goal', () => {
    const { container } = renderCard(points())
    // 30 days: every day has a fill; the 15 days at 11000 also get an overflow rect
    expect(container.querySelectorAll('.goal-bar-grow')).toHaveLength(30)
    expect(container.querySelectorAll('.goal-bar-grow rect[fill="#c2d69a"]')).toHaveLength(15)
  })

  it('shows the empty state with no readings', () => {
    renderCard([])
    expect(screen.getByText('No step data yet.')).toBeTruthy()
  })
})
