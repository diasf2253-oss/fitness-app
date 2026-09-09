// @vitest-environment jsdom
/**
 * Audio service: the guarantees that matter — mute persists and silences,
 * nothing plays before the iOS unlock gesture, and the app-open cue is
 * deferred to that first unlock ("play on first tap").
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  __resetForTests, installUnlockListeners, isMuted, play, playAppOpen,
  preload, setMuted, subscribeMuted, unlock,
} from './audio'

// --- Minimal Web Audio mock (jsdom has no AudioContext) ---------------------
let sourceStarts = 0

class FakeGain {
  constructor() { this.gain = { value: 1 } }
  connect(x) { return x }
}
class FakeSource {
  constructor() { this.buffer = null }
  connect(x) { return x }
  start() { sourceStarts += 1 }
}
class FakeAudioContext {
  constructor() { this.state = 'suspended'; this.destination = {} }
  createGain() { return new FakeGain() }
  createBufferSource() { return new FakeSource() }
  decodeAudioData(_data, onSucc) { onSucc({ duration: 0.1 }); return undefined }
  resume() { this.state = 'running'; return Promise.resolve() }
  close() { this.state = 'closed'; return Promise.resolve() }
}

const tick = () => new Promise(r => setTimeout(r, 0))

beforeEach(() => {
  sourceStarts = 0
  window.AudioContext = FakeAudioContext
  delete window.webkitAudioContext
  global.fetch = vi.fn(async () => ({ ok: true, arrayBuffer: async () => new ArrayBuffer(8) }))
  localStorage.clear()
  __resetForTests()
})

afterEach(() => { vi.restoreAllMocks() })

describe('mute', () => {
  it('defaults to audible and persists across a fresh module init', () => {
    expect(isMuted()).toBe(false)
    setMuted(true)
    expect(isMuted()).toBe(true)
    expect(localStorage.getItem('audio_muted')).toBe('1')
    // A new session re-reads persisted state on init (simulated by reset).
    __resetForTests()
    expect(isMuted()).toBe(true)
  })

  it('notifies subscribers', () => {
    const seen = []
    const unsub = subscribeMuted(m => seen.push(m))
    setMuted(true)
    setMuted(false)
    unsub()
    setMuted(true)  // no longer observed
    expect(seen).toEqual([true, false])
  })
})

describe('gesture gating', () => {
  it('does not play before unlock', async () => {
    await preload()
    play('tap')
    await tick()
    expect(sourceStarts).toBe(0)
  })

  it('plays after unlock', async () => {
    await preload()
    unlock()
    await tick()
    play('tap')
    await tick()
    expect(sourceStarts).toBe(1)
  })

  it('defers app-open to the first unlock ("play on first tap")', async () => {
    await preload()
    playAppOpen()          // requested before any gesture
    await tick()
    expect(sourceStarts).toBe(0)
    unlock()               // first gesture
    await tick()
    expect(sourceStarts).toBe(1)  // the queued app-open fired
  })
})

describe('mute silences playback', () => {
  it('no source is started while muted, even after unlock', async () => {
    await preload()
    unlock()
    await tick()
    setMuted(true)
    play('tap')
    play('workout-complete')
    await tick()
    expect(sourceStarts).toBe(0)
  })
})

describe('unlock listeners', () => {
  it('a pointerdown unlocks, enabling playback', async () => {
    await preload()
    const teardown = installUnlockListeners(window)
    window.dispatchEvent(new Event('pointerdown'))
    await tick()
    play('tap')
    await tick()
    expect(sourceStarts).toBe(1)
    teardown()
  })
})
