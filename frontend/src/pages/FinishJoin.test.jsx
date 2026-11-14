// @vitest-environment jsdom
/** Step 2 of joining: redeem an invite code, prefilled from step 1. */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const apiFetch = vi.fn()
const refresh = vi.fn()
vi.mock('../api', () => ({ apiFetch: (...a) => apiFetch(...a) }))
vi.mock('../auth', async () => {
  const stash = { current: null }
  return {
    useAuth: () => ({
      session: { user: { email: 'new@example.com', user_metadata: { full_name: 'Google Name' } } },
      refresh, logout: vi.fn(),
    }),
    readPendingJoin: () => stash.current,
    clearPendingJoin: () => { stash.current = null },
    __stash: stash,
  }
})

import * as auth from '../auth'
import FinishJoin from './FinishJoin'

beforeEach(() => { apiFetch.mockReset(); refresh.mockReset(); auth.__stash.current = null })
afterEach(cleanup)

describe('FinishJoin', () => {
  it('prefills what was typed on the Join screen, then joins', async () => {
    auth.__stash.current = { code: 'welcome', name: 'Ana' }
    apiFetch.mockResolvedValue({ status: 'pending' })
    render(<FinishJoin />)

    expect(screen.getByLabelText('Name').value).toBe('Ana')
    expect(screen.getByLabelText('Invite code').value).toBe('welcome')
    fireEvent.click(screen.getByRole('button', { name: 'Join' }))

    await waitFor(() => expect(refresh).toHaveBeenCalled())
    expect(apiFetch).toHaveBeenCalledWith('/api/auth/join', {
      method: 'POST', body: JSON.stringify({ code: 'welcome', name: 'Ana' }),
    })
    expect(auth.__stash.current).toBeNull()
  })

  it("falls back to the Google profile name and says when a code isn't valid", async () => {
    apiFetch.mockRejectedValue(Object.assign(new Error('Invalid or expired invite code'), { status: 400 }))
    render(<FinishJoin />)

    expect(screen.getByLabelText('Name').value).toBe('Google Name')
    fireEvent.change(screen.getByLabelText('Invite code'), { target: { value: 'guess' } })
    fireEvent.click(screen.getByRole('button', { name: 'Join' }))

    expect(await screen.findByText(/isn't valid/)).toBeTruthy()
    expect(refresh).not.toHaveBeenCalled()
  })
})
