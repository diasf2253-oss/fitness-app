// @vitest-environment jsdom
/**
 * Log page — the manual weight-entry card.
 * The trickiest input handling: comma decimals ("82,5" from a European
 * phone keyboard) must save as 82.5, and an empty field must show an
 * error instead of posting garbage.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api', () => ({
  apiFetch: vi.fn(path => {
    if (path.startsWith('/api/health/weight/estimate')) {
      return Promise.resolve({ weight_kg: null, estimated: false })
    }
    return Promise.resolve({})
  }),
}))

import { apiFetch } from '../api'
import Log from './Log'

function renderLog() {
  render(<MemoryRouter><Log /></MemoryRouter>)
}

const weightPosts = () =>
  apiFetch.mock.calls.filter(([path, opts]) =>
    path === '/api/health/weight' && opts?.method === 'POST')

beforeEach(() => vi.clearAllMocks())
afterEach(cleanup)

describe('Log — weight card', () => {
  it('saves a comma-decimal weight as a number', async () => {
    renderLog()
    // Let the prefill (estimate) fetch settle first
    await waitFor(() => expect(apiFetch).toHaveBeenCalled())

    fireEvent.change(screen.getByPlaceholderText('84.0'), { target: { value: '82,5' } })
    fireEvent.click(screen.getAllByText('Save')[0])   // Weight is the first card

    await waitFor(() => expect(weightPosts()).toHaveLength(1))
    const body = JSON.parse(weightPosts()[0][1].body)
    expect(body.weight_kg).toBe(82.5)
    expect(body.source).toBe('manual')
  })

  it('shows an error and posts nothing when the field is empty', async () => {
    renderLog()
    await waitFor(() => expect(apiFetch).toHaveBeenCalled())

    fireEvent.click(screen.getAllByText('Save')[0])

    await screen.findByText('Enter a weight first')
    expect(weightPosts()).toHaveLength(0)
  })
})
