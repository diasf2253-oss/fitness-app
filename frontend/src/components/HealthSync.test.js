/**
 * The iOS-only half of the health sync UX. These paths can't be exercised in
 * the desktop browser preview, so they're pinned here instead.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { FORCE_RESYNC_KEY, freshnessLabel, isIOS, runHealthShortcut, shortcutRunUrl } from './HealthSync'

function withNavigator(props) {
  vi.stubGlobal('navigator', { userAgent: '', platform: '', maxTouchPoints: 0, ...props })
}

afterEach(() => vi.unstubAllGlobals())

describe('isIOS', () => {
  it('detects iPhone', () => {
    withNavigator({ userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)' })
    expect(isIOS()).toBe(true)
  })

  it('detects iPadOS, which claims to be a Mac', () => {
    // Modern iPadOS reports platform MacIntel; the touch points give it away.
    withNavigator({
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
      platform: 'MacIntel',
      maxTouchPoints: 5,
    })
    expect(isIOS()).toBe(true)
  })

  it('is false on a real Mac', () => {
    withNavigator({
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
      platform: 'MacIntel',
      maxTouchPoints: 0,
    })
    expect(isIOS()).toBe(false)
  })

  it('is false on Android and Windows', () => {
    withNavigator({ userAgent: 'Mozilla/5.0 (Linux; Android 14)' })
    expect(isIOS()).toBe(false)
    withNavigator({ userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' })
    expect(isIOS()).toBe(false)
  })
})

describe('shortcutRunUrl', () => {
  it('builds an x-callback-url that returns to the app', () => {
    expect(shortcutRunUrl('https://app.example.com/settings', 'Tracker Health Sync')).toBe(
      'shortcuts://x-callback-url/run-shortcut'
      + '?name=Tracker%20Health%20Sync'
      + '&x-success=https%3A%2F%2Fapp.example.com%2Fsettings',
    )
  })

  it('escapes a return URL carrying a query string', () => {
    const url = shortcutRunUrl('https://a.test/?x=1&y=2', 'S')
    // The inner & must not terminate the outer x-success parameter
    expect(url).toContain('x-success=https%3A%2F%2Fa.test%2F%3Fx%3D1%26y%3D2')
    expect(url.split('&').length).toBe(2)  // only name & x-success
  })
})

describe('freshnessLabel', () => {
  it('words each case the way a person would', () => {
    expect(freshnessLabel(null)).toBe('no data')
    expect(freshnessLabel(undefined)).toBe('no data')
    expect(freshnessLabel(0)).toBe('today')
    expect(freshnessLabel(1)).toBe('yesterday')
    expect(freshnessLabel(4)).toBe('4 days ago')
  })
})


describe('runHealthShortcut', () => {
  it('sets the force-resync flag before navigating, so main.jsx\'s resync '
    + 'throttle does not swallow the visibilitychange fired when iOS bounces '
    + 'back via x-success', () => {
    const location = { href: 'https://app.example.com/' }
    const store = new Map()
    vi.stubGlobal('window', { location })
    vi.stubGlobal('sessionStorage', {
      getItem: k => (store.has(k) ? store.get(k) : null),
      setItem: (k, v) => store.set(k, v),
      removeItem: k => store.delete(k),
    })

    runHealthShortcut()

    expect(store.get(FORCE_RESYNC_KEY)).toBe('1')
    expect(location.href).toContain('shortcuts://x-callback-url/run-shortcut')
  })
})
