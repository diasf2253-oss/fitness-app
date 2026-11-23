// @vitest-environment jsdom
/**
 * ConfirmSheet — the in-app replacement for window.confirm().
 * Regression: Finish/Discard workout went dead in browsers that suppress
 * window.confirm (it returns false instantly, with no popup). The sheet must
 * resolve true/false from its own buttons and never call window.confirm.
 */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ConfirmHost, confirmAction } from './ConfirmSheet'

// jsdom lacks the Web Animations API that Modal uses
Element.prototype.animate ??= function () { return { cancel() {}, onfinish: null } }

afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('confirmAction with the sheet mounted', () => {
  it('resolves true on the confirm button, without touching window.confirm', async () => {
    const native = vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<ConfirmHost />)
    let p
    act(() => { p = confirmAction({ title: 'Finish this workout?', confirmLabel: 'Finish workout' }) })
    fireEvent.click(await screen.findByRole('button', { name: 'Finish workout' }))
    await expect(p).resolves.toBe(true)
    expect(native).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('resolves false on Cancel', async () => {
    render(<ConfirmHost />)
    let p
    act(() => { p = confirmAction({ title: 'Discard this workout?', confirmLabel: 'Discard', danger: true }) })
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }))
    await expect(p).resolves.toBe(false)
  })
})

describe('confirmAction without the sheet', () => {
  it('falls back to window.confirm', async () => {
    const native = vi.spyOn(window, 'confirm').mockReturnValue(true)
    await expect(confirmAction({ title: 'Delete?', message: 'Gone for good.' })).resolves.toBe(true)
    expect(native).toHaveBeenCalledWith('Delete?\n\nGone for good.')
  })
})
