/**
 * The Supabase client — the app's login service.
 *
 * Supabase handles everything about *signing in*: email + password, the
 * Google button, "forgot password" emails, keeping you signed in (it saves
 * the session in this device's localStorage and quietly renews the
 * short-lived access token). The app's own backend still decides who is
 * *allowed in* — invite code, admin approval — see src/auth.jsx.
 *
 * Every API request carries the current access token as
 * `Authorization: Bearer <token>` (src/api.js, src/local/sync.js); the
 * backend verifies it (backend/app/supabase_auth.py).
 *
 * Configured at build time with two Vite env vars — both public by design
 * (the publishable key only identifies the project; it unlocks nothing):
 *   VITE_SUPABASE_URL              https://<project-ref>.supabase.co
 *   VITE_SUPABASE_PUBLISHABLE_KEY  the project's publishable (or legacy anon) key
 * Missing ⇒ `supabase` is null and the app shows a "login isn't set up" screen.
 */
import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = (import.meta.env.VITE_SUPABASE_URL || '').replace(/\/+$/, '')
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || ''

export const supabaseConfigured = Boolean(SUPABASE_URL && SUPABASE_KEY)

/**
 * Email links (confirm address, reset password) and Google sign-ins come
 * back to the app with the outcome in the URL fragment
 * (`#access_token=…&type=recovery`, or `#error_description=…`). supabase-js
 * reads and then clears that fragment while it starts up, so capture the two
 * things the UI needs first: "this is a password-reset visit" and any error.
 */
export function readLandingFragment(hash) {
  try {
    const params = new URLSearchParams(String(hash || '').replace(/^#/, ''))
    return {
      recovery: params.get('type') === 'recovery',
      error: params.get('error_description') || params.get('error') || null,
    }
  } catch {
    return { recovery: false, error: null }
  }
}

export const landing = readLandingFragment(
  typeof window === 'undefined' ? '' : window.location.hash,
)

export const supabase = supabaseConfigured
  ? createClient(SUPABASE_URL, SUPABASE_KEY, {
      auth: {
        persistSession: true,      // stay signed in across launches of the phone app
        autoRefreshToken: true,    // renew the ~1-hour access token before it lapses
        detectSessionInUrl: true,  // finish Google / email-link sign-ins that land here
        // The default today, pinned on purpose: the admin's password-reset
        // links (made server-side) only work with the implicit flow.
        flowType: 'implicit',
      },
    })
  : null

/** The current access token, or null when nobody is signed in. Renews an
 *  expired one first when it can; never throws. */
export async function getAccessToken() {
  if (!supabase) return null
  try {
    const { data } = await supabase.auth.getSession()
    return data?.session?.access_token ?? null
  } catch {
    return null
  }
}

/** Where Supabase sends people back to after an email link or Google.
 *  Must be listed under Authentication → URL Configuration → Redirect URLs. */
export function appRedirectUrl() {
  return `${window.location.origin}/`
}
