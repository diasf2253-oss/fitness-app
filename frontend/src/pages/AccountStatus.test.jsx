// @vitest-environment jsdom
/** The "can't continue" screens: a server error must not blame the connection. */
import { cleanup, render, screen } from '@testing-library/react'
import React from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('../auth/auth', () => ({ useAuth: () => ({ refresh: vi.fn(), logout: vi.fn() }) }))

import AccountStatus from './AccountStatus'

afterEach(cleanup)

describe('AccountStatus', () => {
  it('a server error says the problem is on our side, not the connection', () => {
    render(<AccountStatus kind="server_error" />)
    expect(screen.getByText('Something went wrong on our side')).toBeTruthy()
    expect(screen.getByText(/not your connection/)).toBeTruthy()
  })

  it('a real network failure still asks to check the connection', () => {
    render(<AccountStatus kind="unreachable" />)
    expect(screen.getByText("Can't reach the server")).toBeTruthy()
    expect(screen.getByText(/Check your connection/)).toBeTruthy()
  })
})
