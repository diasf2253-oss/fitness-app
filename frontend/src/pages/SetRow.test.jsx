// @vitest-environment jsdom
/**
 * Workout SetRow — the in-gym set logger.
 * Comma-decimal weights must persist as numbers, garbage must never
 * become NaN, and completing a set with blank fields must inherit the
 * previous session's values (the placeholder the lifter is matching).
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api', () => ({ apiFetch: vi.fn(() => Promise.resolve({})) }))

import { apiFetch } from '../api'
import { SetRow } from './Workout'

const SET = {
  id: 3, set_number: 1, weight_kg: 0, reps: 0, rpe: null, rir: null,
  is_completed: false, is_warmup: false,
}
const PATCH_URL = '/api/sessions/1/exercises/2/sets/3'

function renderRow(props = {}) {
  render(
    <SetRow
      sessionId={1} seId={2} set={SET} prev={null}
      onChanged={() => {}} onCompleted={() => {}} onDelete={() => {}}
      setError={() => {}}
      {...props}
    />
  )
}

const lastPatchBody = () => {
  const patches = apiFetch.mock.calls.filter(([, opts]) => opts?.method === 'PATCH')
  return JSON.parse(patches[patches.length - 1][1].body)
}

beforeEach(() => vi.clearAllMocks())
afterEach(cleanup)

describe('SetRow input handling', () => {
  it('saves a comma-decimal weight on blur', async () => {
    renderRow()
    const weight = screen.getByLabelText('Weight (kg)')
    fireEvent.change(weight, { target: { value: '82,5' } })
    fireEvent.blur(weight)

    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith(PATCH_URL, expect.anything()))
    expect(lastPatchBody()).toEqual({ weight_kg: 82.5, reps: 0, rir: null })
  })

  it('never saves NaN — garbage falls back to 0', async () => {
    renderRow()
    const weight = screen.getByLabelText('Weight (kg)')
    fireEvent.change(weight, { target: { value: '8o' } })
    fireEvent.blur(weight)

    await waitFor(() => expect(apiFetch).toHaveBeenCalled())
    expect(lastPatchBody().weight_kg).toBe(0)
  })

  it('completing with empty fields inherits the previous session values', async () => {
    renderRow({ prev: { weight_kg: 100, reps: 5 } })
    fireEvent.click(screen.getByLabelText('Mark set complete'))

    await waitFor(() => expect(apiFetch).toHaveBeenCalled())
    expect(lastPatchBody()).toMatchObject({
      weight_kg: 100, reps: 5, is_completed: true,
    })
    // The inherited values are now shown in the inputs, not just implied
    expect(screen.getByLabelText('Weight (kg)').value).toBe('100')
  })
})
