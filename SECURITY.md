# Security policy

This is a personal project run as a small invite-only beta. It stores health
and training data, so security reports are genuinely appreciated.

## Reporting a vulnerability

Please **don't open a public issue**. Use GitHub's private reporting instead:
the repository's **Security** tab → **Report a vulnerability**. Include what
you found, how to reproduce it, and what an attacker could do with it.

You'll get a reply as soon as I can manage — this is maintained in spare time,
and there is no bug bounty.

## Scope

In scope: this repository's code — authentication and sessions, per-user data
isolation (one account reading or changing another's data), the Apple Health
ingest endpoints, and the backup/restore scripts.

Out of scope: denial-of-service, findings that need a compromised device, and
reports from automated scanners without a demonstrated impact.

## For self-hosters

- Never commit `backend/.env`, database files, or `backups/` — all are
  git-ignored.
- Serve the app over HTTPS and keep `SESSION_COOKIE_SECURE` at its default
  (`true`).
- Change the seeded admin password (`python -m app.set_admin_password`) and
  rotate any ingest token that may have leaked (Settings → Apple Health sync).
