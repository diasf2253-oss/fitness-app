// @vitest-environment jsdom
/**
 * The small rules src/auth/auth.jsx and src/lib/supabase.js lean on: which screen an
 * account status maps to, the offline copy of the account (never holding the
 * ingest token, never handed to a different person), the invite-code stash
 * that survives the email-confirmation round trip, Supabase errors in plain
 * words, and reading a reset-link visit from the URL fragment.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../lib/supabase', async (importOriginal) => {
  const real = await importOriginal()
  return { ...real, supabase: null, landing: { recovery: false, error: null } }
})

import {
  clearCachedAccount, clearPendingJoin, friendlyAuthError, readCachedAccount,
  readPendingJoin, saveCachedAccount, stashPendingJoin, statusFromAccount,
} from './auth'
import { readLandingFragment } from '../lib/supabase'

beforeEach(() => { localStorage.clear() })

describe('statusFromAccount', () => {
  it('maps account statuses to screens', () => {
    expect(statusFromAccount({ status: 'active' })).toBe('ready')
    expect(statusFromAccount({ status: 'pending' })).toBe('pending')
    expect(statusFromAccount({ status: 'disabled' })).toBe('disabled')
    expect(statusFromAccount({ status: 'something-new' })).toBe('disabled')   // fail closed
  })
})

describe('offline copy of the account', () => {
  const me = { id: 3, email: 'a@example.com', name: 'A', role: 'user', status: 'active', ingest_token: 'secret' }

  it('round-trips without the ingest token', () => {
    saveCachedAccount(me, 'uid-a')
    const cached = readCachedAccount('uid-a')
    expect(cached).toMatchObject({ id: 3, status: 'active' })
    expect(cached.ingest_token).toBeUndefined()
    expect(localStorage.getItem('auth_me_v1')).not.toContain('secret')
  })

  it("is never handed to a different Supabase user", () => {
    saveCachedAccount(me, 'uid-a')
    expect(readCachedAccount('uid-b')).toBeNull()
  })

  it('is gone after clearing (log out)', () => {
    saveCachedAccount(me, 'uid-a')
    clearCachedAccount()
    expect(readCachedAccount()).toBeNull()
  })

  it('shrugs off junk in storage', () => {
    localStorage.setItem('auth_me_v1', '{not json')
    expect(readCachedAccount()).toBeNull()
  })
})

describe('invite stash', () => {
  it('keeps code + name across the confirmation round trip', () => {
    stashPendingJoin({ code: 'abc', name: 'Ana' })
    expect(readPendingJoin()).toEqual({ code: 'abc', name: 'Ana' })
    clearPendingJoin()
    expect(readPendingJoin()).toBeNull()
  })
})

describe('friendlyAuthError', () => {
  it('translates the common Supabase codes', () => {
    expect(friendlyAuthError({ code: 'invalid_credentials' })).toBe('Incorrect email or password.')
    expect(friendlyAuthError({ code: 'email_not_confirmed' })).toMatch(/Confirm your email/)
    expect(friendlyAuthError({ code: 'over_email_send_rate_limit' })).toMatch(/Too many attempts/)
    expect(friendlyAuthError({ status: 429 })).toMatch(/Too many attempts/)
    expect(friendlyAuthError({ name: 'AuthRetryableFetchError', message: 'Failed to fetch' }))
      .toMatch(/Couldn't reach the login service/)
    expect(friendlyAuthError({ message: 'Something odd' })).toBe('Something odd')
  })
})

describe('readLandingFragment', () => {
  it('spots a password-reset visit', () => {
    expect(readLandingFragment('#access_token=x&type=recovery')).toEqual({ recovery: true, error: null })
    expect(readLandingFragment('#access_token=x&type=signup').recovery).toBe(false)
  })

  it('surfaces an expired-link error', () => {
    const r = readLandingFragment('#error=access_denied&error_description=Email+link+is+invalid+or+has+expired')
    expect(r.error).toBe('Email link is invalid or has expired')
  })

  it('handles no fragment at all', () => {
    expect(readLandingFragment('')).toEqual({ recovery: false, error: null })
  })
})
