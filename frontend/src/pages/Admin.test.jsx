// @vitest-environment jsdom
/** Admin → Invite codes: list, create (with limit validation), copy link. */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const apiFetch = vi.fn()
vi.mock('../lib/api', () => ({ apiFetch: (...a) => apiFetch(...a) }))
vi.mock('../components/ui/ConfirmSheet', () => ({ confirmAction: async () => true }))

import Admin, { inviteLink, usageText } from './Admin'

const CODE = { id: 7, code: 'spEp zN', label: 'gym friends', active: true, max_uses: 3, uses: 1,
  created_at: '2026-11-14T10:00:00' }

function serve(codes) {
  apiFetch.mockImplementation(async (path, opts) => {
    if (path === '/api/admin/invite-codes' && !opts) return codes
    if (path === '/api/admin/pending' || path === '/api/admin/users') return []
    return {}
  })
}

beforeEach(() => apiFetch.mockReset())
afterEach(cleanup)

describe('invite code helpers', () => {
  it('describes usage with and without a limit', () => {
    expect(usageText(CODE)).toBe('1 of 3 used')
    expect(usageText({ ...CODE, max_uses: null })).toBe('1 used · no limit')
  })
  it('builds a sign-up link the Join screen prefills from', () => {
    expect(inviteLink(CODE, 'http://x.test')).toBe('http://x.test/join?code=spEp%20zN')
  })
})

describe('Admin invite codes card', () => {
  it('lists codes and creates a new one with a label and limit', async () => {
    serve([CODE])
    render(<Admin />)
    expect(await screen.findByText('spEp zN')).toBeTruthy()
    expect(screen.getByText(/gym friends · 1 of 3 used/)).toBeTruthy()

    fireEvent.change(screen.getByLabelText('Label (optional)'), { target: { value: ' Ana ' } })
    fireEvent.change(screen.getByLabelText('Max uses'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create code' }))

    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith('/api/admin/invite-codes', {
      method: 'POST', body: JSON.stringify({ label: 'Ana', max_uses: 2 }),
    }))
  })

  it('refuses a max-uses value that is not a whole number', async () => {
    serve([])
    render(<Admin />)
    await screen.findByText(/No codes yet/)
    fireEvent.change(screen.getByLabelText('Max uses'), { target: { value: '1,5' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create code' }))
    expect(await screen.findByText(/whole number/)).toBeTruthy()
    expect(apiFetch).not.toHaveBeenCalledWith('/api/admin/invite-codes', expect.objectContaining({ method: 'POST' }))
  })

  it('switches a code off', async () => {
    serve([CODE])
    render(<Admin />)
    fireEvent.click(await screen.findByRole('button', { name: 'Switch off' }))
    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith('/api/admin/invite-codes/7', {
      method: 'PATCH', body: JSON.stringify({ active: false }),
    }))
  })
})
