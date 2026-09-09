/**
 * Audio cue service.
 *
 * A tiny sound layer for the four moments that deserve one: opening the app,
 * tapping a button, finishing a workout, and ranking up. Design goals map to
 * the acceptance criteria:
 *
 *  - iOS PWA safe. Mobile Safari blocks all audio until the first user
 *    gesture, and creating/resuming an AudioContext before that gesture logs
 *    a console warning. So we do NOT touch Web Audio until `unlock()` runs
 *    inside the first interaction (pointerdown/keydown). Before that, every
 *    play() is a graceful no-op — the app-open cue simply doesn't sound on a
 *    cold PWA launch; instead it's remembered and fired on that first tap
 *    (see `pendingAppOpen`), which is the allowed "play on first tap".
 *
 *  - No audible tap lag. `preload()` fetches the clip bytes up front (no
 *    context needed — avoids the pre-gesture warning); `unlock()` decodes
 *    them into AudioBuffers once. Each play then spins up a fresh
 *    BufferSource — the lowest-latency path the browser offers, and it lets
 *    cues overlap.
 *
 *  - Mute persists. A single localStorage flag (`audio_muted`), read
 *    synchronously so the very first cue already respects it, exposed via
 *    isMuted/setMuted with a subscribe() for the settings toggle.
 *
 *  - Never noisy. Missing files, decode failures, or a blocked context all
 *    fail silently (best-effort catch) — no console errors.
 *
 * Volumes are modest by default; `tap` is deliberately the quietest.
 */
import appOpenUrl from './assets/audio/app-open.mp3'
import tapUrl from './assets/audio/tap.mp3'
import workoutCompleteUrl from './assets/audio/workout-complete.mp3'
import rankUpUrl from './assets/audio/rank-up.mp3'

// name -> asset URL (Vite rewrites these to hashed, cacheable paths)
const SOURCES = {
  'app-open': appOpenUrl,
  tap: tapUrl,
  'workout-complete': workoutCompleteUrl,
  'rank-up': rankUpUrl,
}

// Per-cue gain relative to the master. Tap is subtle; the celebrations lean in.
const CUE_GAIN = {
  'app-open': 0.7,
  tap: 0.45,
  'workout-complete': 1.0,
  'rank-up': 1.0,
}

// Modest master volume — present, never startling.
const MASTER_GAIN = 0.6

const MUTE_KEY = 'audio_muted'

let ctx = null                 // AudioContext, created lazily inside unlock()
let masterGain = null
const rawBytes = new Map()     // name -> ArrayBuffer (fetched, pre-decode)
const buffers = new Map()      // name -> decoded AudioBuffer (post-unlock)
let unlocked = false
let pendingAppOpen = false     // app-open requested before unlock → play on unlock
const muteListeners = new Set()

// ---------------------------------------------------------------------------
// Mute state (persisted, read synchronously so the first cue honours it)
// ---------------------------------------------------------------------------

function readMuted() {
  try {
    return localStorage.getItem(MUTE_KEY) === '1'
  } catch {
    return false  // storage blocked (private mode) — default to audible
  }
}

let muted = readMuted()

export function isMuted() {
  return muted
}

export function setMuted(value) {
  muted = !!value
  try {
    localStorage.setItem(MUTE_KEY, muted ? '1' : '0')
  } catch { /* storage blocked — in-memory only for this session */ }
  muteListeners.forEach(fn => {
    try { fn(muted) } catch { /* a bad subscriber must not break the rest */ }
  })
}

/** Subscribe to mute changes (for the settings toggle). Returns an unsubscribe. */
export function subscribeMuted(fn) {
  muteListeners.add(fn)
  return () => muteListeners.delete(fn)
}

// ---------------------------------------------------------------------------
// Loading + unlocking
// ---------------------------------------------------------------------------

function AudioCtx() {
  return (typeof window !== 'undefined' && (window.AudioContext || window.webkitAudioContext)) || null
}

/** Whether Web Audio is even available (older browsers / SSR guards). */
function supported() {
  return !!AudioCtx()
}

/**
 * Fetch every cue's bytes so they're in memory (and warm in the SW cache)
 * before the user unlocks. No AudioContext is created here — decoding waits
 * for the gesture. Fully best-effort: a file that 404s is skipped, not thrown.
 */
export async function preload() {
  if (!supported()) return
  await Promise.all(
    Object.entries(SOURCES).map(async ([name, url]) => {
      if (rawBytes.has(name) || buffers.has(name)) return
      try {
        const res = await fetch(url)
        if (!res.ok) return
        rawBytes.set(name, await res.arrayBuffer())
      } catch { /* skip this cue; the others still load */ }
    })
  )
}

// decodeAudioData has a callback signature on older Safari; wrap both.
// Decode from a copy so the source ArrayBuffer isn't neutered (lets a retry work).
function decodeArrayBuffer(context, data) {
  return new Promise((resolve) => {
    try {
      const p = context.decodeAudioData(data.slice(0), resolve, () => resolve(null))
      if (p && typeof p.then === 'function') p.then(resolve, () => resolve(null))
    } catch {
      resolve(null)
    }
  })
}

async function decodeAll() {
  if (!ctx) return
  await Promise.all(
    Object.keys(SOURCES).map(async (name) => {
      if (buffers.has(name)) return
      const bytes = rawBytes.get(name)
      if (!bytes) return
      const buf = await decodeArrayBuffer(ctx, bytes)
      if (buf) buffers.set(name, buf)
    })
  )
}

/**
 * Turn audio on. MUST run inside a user-gesture handler on iOS. Creates the
 * AudioContext (if needed), resumes it, decodes the cues, and plays a queued
 * app-open cue. Idempotent and best-effort.
 */
export function unlock() {
  if (!supported()) return
  const Ctor = AudioCtx()
  try {
    if (!ctx) {
      ctx = new Ctor()
      masterGain = ctx.createGain()
      masterGain.gain.value = MASTER_GAIN
      masterGain.connect(ctx.destination)
    }
    const finish = async () => {
      await preload()   // idempotent; covers a tap that beats the initial fetch
      await decodeAll()
      unlocked = true
      if (pendingAppOpen) {
        pendingAppOpen = false
        play('app-open')
      }
    }
    if (ctx.state === 'suspended') {
      ctx.resume().then(finish, finish)
    } else {
      finish()
    }
  } catch { /* leave locked; play() stays a no-op */ }
}

/**
 * Attach unlock listeners. We keep listening (not `once`) because the context
 * can be re-suspended (tab backgrounded on iOS); each gesture re-resumes it
 * cheaply. Listens on `window`; the tap handler lives on `document`, which
 * sits earlier in the bubble path — so a first tap unlocks (and fires
 * app-open) without also firing a tap cue. Returns a teardown for tests.
 */
export function installUnlockListeners(target = typeof window !== 'undefined' ? window : null) {
  if (!target) return () => {}
  const handler = () => unlock()
  const events = ['pointerdown', 'touchend', 'keydown']
  events.forEach(e => target.addEventListener(e, handler, { passive: true }))
  return () => events.forEach(e => target.removeEventListener(e, handler))
}

// ---------------------------------------------------------------------------
// Playback
// ---------------------------------------------------------------------------

/**
 * Play a cue by name. No-ops (silently) when muted, unsupported, not yet
 * unlocked, or the buffer isn't loaded. The app-open cue is special: if we're
 * asked to play it before the first interaction, we remember it and let the
 * first unlock fire it ("play on first tap").
 */
export function play(name) {
  if (muted || !supported()) return
  if (!unlocked || !ctx) {
    if (name === 'app-open') pendingAppOpen = true
    return
  }
  const buffer = buffers.get(name)
  if (!buffer) return
  try {
    if (ctx.state === 'suspended') ctx.resume()
    const src = ctx.createBufferSource()
    src.buffer = buffer
    const gain = ctx.createGain()
    gain.gain.value = CUE_GAIN[name] ?? 1.0
    src.connect(gain).connect(masterGain)
    src.start(0)
  } catch { /* a failed cue must never surface to the user */ }
}

// Convenience wrappers — the app calls these, not play() with magic strings.
export const playAppOpen = () => play('app-open')
export const playTap = () => play('tap')
export const playWorkoutComplete = () => play('workout-complete')
export const playRankUp = () => play('rank-up')

// Test-only reset hook (not used in app code).
export function __resetForTests() {
  ctx = null
  masterGain = null
  rawBytes.clear()
  buffers.clear()
  unlocked = false
  pendingAppOpen = false
  muteListeners.clear()
  muted = readMuted()
}
