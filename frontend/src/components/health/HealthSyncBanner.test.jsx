// @vitest-environment jsdom
/** Daily weigh-in nudge: shows until today's weight is logged; dismiss lasts the day. */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

let status
vi.mock('./HealthSync', () => ({ useSyncStatus: () => ({ status }) }))
vi.mock('../../auth/auth', () => ({ useAuth: () => ({ user: { id: 7 } }) }))
const openQuickLog = vi.fn()
vi.mock('../training/QuickLog', () => ({ openQuickLog: (...a) => openQuickLog(...a) }))

import HealthSyncBanner from './HealthSyncBanner'

const today = (() => {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
})()
const renderAt = (path = '/') => render(<MemoryRouter initialEntries={[path]}><HealthSyncBanner /></MemoryRouter>)

beforeEach(() => { try { localStorage.clear() } catch { /* ignore */ } openQuickLog.mockReset() })
afterEach(cleanup)

describe('weigh-in nudge', () => {
  it('shows when weight is not from today and opens quick-log on weight', () => {
    status = { weight: { last_date: '2026-01-01', days_stale: 3 } }
    renderAt()
    expect(screen.getByText('Weight not logged today.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Log weight' }))
    expect(openQuickLog).toHaveBeenCalledWith('weight')
  })

  it('hides once today’s weight is logged', () => {
    status = { weight: { last_date: today, days_stale: 0 } }
    renderAt()
    expect(screen.queryByText('Weight not logged today.')).toBeNull()
  })

  it('stays dismissed for the rest of the day', () => {
    status = { weight: { last_date: null, days_stale: null } }
    renderAt()
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss for today' }))
    cleanup()
    renderAt()
    expect(screen.queryByText('Weight not logged today.')).toBeNull()
  })

  it('never mentions connecting Apple Health, and is hidden on the full log page', () => {
    status = { weight: { last_date: null } }
    const { container } = renderAt('/log')
    expect(container.textContent).toBe('')
    cleanup()
    renderAt()
    expect(document.body.textContent).not.toMatch(/Apple Health/)
  })
})
