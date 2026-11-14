// @vitest-environment jsdom
/**
 * Quick-log sheet — the fast manual path for weight / steps / sleep while
 * Apple Health sync is paused. Checks the numbers that actually get posted.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api', () => ({ apiFetch: vi.fn() }))

import { apiFetch } from '../api'
import { HEALTH_DATA_CHANGED, QuickLogForm } from './QuickLog'

function localIso(offset = 0) {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

let estimate
beforeEach(() => {
  estimate = { weight_kg: 81.4, estimated: false }
  apiFetch.mockReset()
  apiFetch.mockImplementation(path =>
    path.startsWith('/api/health/weight/estimate') ? Promise.resolve(estimate) : Promise.resolve({}))
})
afterEach(cleanup)

const renderForm = (props = {}) =>
  render(<MemoryRouter><QuickLogForm onDone={() => {}} {...props} /></MemoryRouter>)

const posts = () => apiFetch.mock.calls
  .filter(([, opts]) => opts?.method === 'POST')
  .map(([path, opts]) => [path, JSON.parse(opts.body)])

describe('QuickLogForm', () => {
  it('opens on the requested tab', () => {
    renderForm({ initialMetric: 'sleep' })
    expect(screen.getByRole('tab', { name: 'Sleep' }).getAttribute('aria-selected')).toBe('true')
    expect(screen.getByLabelText('Hours asleep')).toBeTruthy()
  })

  it('prefills the latest weight; one + tap and Save posts it +0.1 kg', async () => {
    renderForm()
    await waitFor(() => expect(screen.getByLabelText('Weight in kg').value).toBe('81.4'))
    fireEvent.click(screen.getByLabelText(/Increase weight/))
    fireEvent.click(screen.getByRole('button', { name: 'Save weight' }))
    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0]).toEqual(['/api/health/weight', { date: localIso(0), weight_kg: 81.5, source: 'manual' }])
  })

  it('accepts a comma decimal ("82,5" → 82.5)', async () => {
    renderForm()
    await waitFor(() => expect(screen.getByLabelText('Weight in kg').value).toBe('81.4'))
    fireEvent.change(screen.getByLabelText('Weight in kg'), { target: { value: '82,5' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save weight' }))
    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0][1].weight_kg).toBe(82.5)
  })

  it('an untouched interpolated estimate is saved as an estimate, never as real', async () => {
    estimate = { weight_kg: 80.9, estimated: true }
    renderForm()
    await waitFor(() => expect(screen.getByLabelText('Weight in kg').value).toBe('80.9'))
    fireEvent.click(screen.getByRole('button', { name: 'Save weight' }))
    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0][1].source).toBe('estimated')
  })

  it('Yesterday sends yesterday’s date', async () => {
    renderForm({ initialMetric: 'steps' })
    fireEvent.click(screen.getByRole('button', { name: 'Yesterday' }))
    fireEvent.change(screen.getByLabelText('Steps'), { target: { value: '10432' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save steps' }))
    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0]).toEqual(['/api/health/steps', { date: localIso(-1), steps: 10432 }])
  })

  it('sleep 7 h 30 m posts 450 minutes', async () => {
    renderForm({ initialMetric: 'sleep' })
    fireEvent.click(screen.getByRole('button', { name: 'Save sleep' }))   // defaults 7h 30m
    await waitFor(() => expect(posts()).toHaveLength(1))
    expect(posts()[0]).toEqual(['/api/health/sleep', { date: localIso(0), asleep_minutes: 450, in_bed_minutes: 450 }])
  })

  it('a save announces health-data-changed so screens refresh', async () => {
    const heard = vi.fn()
    window.addEventListener(HEALTH_DATA_CHANGED, heard)
    renderForm({ initialMetric: 'steps' })
    fireEvent.change(screen.getByLabelText('Steps'), { target: { value: '9000' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save steps' }))
    await waitFor(() => expect(heard).toHaveBeenCalledTimes(1))
    window.removeEventListener(HEALTH_DATA_CHANGED, heard)
  })

  it('an API error shows inline and does not close the sheet', async () => {
    const onDone = vi.fn()
    apiFetch.mockImplementation((path, opts) =>
      opts?.method === 'POST' ? Promise.reject(new Error('Server unreachable')) : Promise.resolve(estimate))
    renderForm({ initialMetric: 'steps', onDone })
    fireEvent.change(screen.getByLabelText('Steps'), { target: { value: '9000' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save steps' }))
    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(screen.getByRole('alert').textContent).toContain('Server unreachable')
    await new Promise(r => setTimeout(r, 800))
    expect(onDone).not.toHaveBeenCalled()
  })

  it('refuses to post an empty step count', async () => {
    renderForm({ initialMetric: 'steps' })
    fireEvent.click(screen.getByRole('button', { name: 'Save steps' }))
    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(posts()).toHaveLength(0)
  })
})
