-- Anonymise a production copy for staging (run by scripts/seed_staging.sh).
-- Destructive by design — never point this at production.
--
-- Keeps the dataset realistic — exercise/routine/session names, dates, sets,
-- reps, streaks and volumes all survive, so ranks, insights and the adaptive
-- calorie engine behave like production. What goes:
--   * every free-text field (journal entries, notes, cues) — the actually
--     personal content;
--   * true body weight — shifted by one random per-run offset (trend intact)
--     plus per-row noise;
--   * steps and nutrition — small per-row jitter;
--   * profile age — reset to a generic value;
--   * every production credential and every friend's identity:
--       - users: non-admin email -> user<id>@example.test, name -> User <id>;
--         EVERY password_hash (admin included) -> one staging-only argon2
--         hash; must_change_password -> false; ingest_token -> fresh random;
--       - auth_session: all rows deleted (no prod session id works here);
--       - invite_codes: code -> fresh random, active -> false,
--         label -> Invite <id>.
--     The admin row keeps its email and name, so the operator logs in with
--     their usual email + the staging password. Ids, roles and statuses stay.
--
-- The staging password arrives as the psql variable `staging_pw_hash` — an
-- argon2 hash, never plaintext. seed_staging.sh computes it from
-- STAGING_USER_PASSWORD with the same hasher as app/auth.py.
--
-- All-or-nothing: one transaction that checks its own work before COMMIT;
-- any failure rolls every change back.
--
-- Plain SQL UPDATEs deliberately bypass the ORM's onupdate, so updated_at
-- keeps its production values and sync/merge behaviour stays realistic.
-- Needs Postgres 13+ (gen_random_uuid() is built in from 13).

\if :{?staging_pw_hash}
\else
  DO $$ BEGIN RAISE EXCEPTION 'psql variable staging_pw_hash is not set — run this via scripts/seed_staging.sh'; END $$;
\endif

BEGIN;

-- One offset for the whole run: the weight *trend* (what the calorie engine
-- and charts read) is preserved; the absolute values are masked.
CREATE TEMP TABLE _anon AS
SELECT (random() * 6 - 3)       AS weight_offset_kg,
       :'staging_pw_hash'::text AS pw_hash;

-- Refuse a plaintext password passed by mistake.
DO $chk$
BEGIN
  IF (SELECT pw_hash FROM _anon) NOT LIKE '$argon2%' THEN
    RAISE EXCEPTION 'staging_pw_hash is not an argon2 hash — pass the hash, never the password';
  END IF;
END
$chk$;

UPDATE weight_log
SET weight_kg = round(
      (weight_kg + (SELECT weight_offset_kg FROM _anon)
       + (random() * 0.2 - 0.1))::numeric, 1);

UPDATE steps_log
SET steps = greatest(0, round(steps * (0.9 + random() * 0.2)))::int;

UPDATE nutrition_day n
SET calories  = round((n.calories  * j.f)::numeric, 0),
    protein_g = round((n.protein_g * j.f)::numeric, 1),
    carbs_g   = round((n.carbs_g   * j.f)::numeric, 1),
    fat_g     = round((n.fat_g     * j.f)::numeric, 1)
FROM (SELECT id, 0.95 + random() * 0.1 AS f FROM nutrition_day) j
WHERE n.id = j.id;

-- Free text: scrub, don't NULL where the column is NOT NULL.
UPDATE session      SET notes = NULL WHERE notes IS NOT NULL;
UPDATE routine      SET notes = NULL WHERE notes IS NOT NULL;
UPDATE exercise     SET notes = NULL WHERE notes IS NOT NULL;
UPDATE activity     SET notes = NULL WHERE notes IS NOT NULL;
UPDATE routine_note SET text  = 'Note scrubbed for staging';
UPDATE tracker_log  SET value_text = 'Entry scrubbed for staging'
                    WHERE value_text IS NOT NULL;

-- Plan items: the title is the personal part ("Study for X exam") — replace
-- with the category, which keeps the calendar/plan UI realistic.
UPDATE plan_item SET title = initcap(category), notes = NULL;

-- Profile
UPDATE settings SET age = 30;

-- Accounts: friends become numbered placeholders. The admin keeps its email
-- (the operator's own) so logging in to staging works the usual way.
UPDATE users
SET email = 'user' || id || '@example.test',
    name  = 'User ' || id
WHERE role <> 'admin';

-- Credentials, admin included. One known staging-only hash; no forced change
-- (a pending prod temp-password reset means nothing once the hash is gone);
-- a fresh ingest token so the prod tokens on friends' phones can't push here.
-- Two gen_random_uuid() (Postgres's strong RNG, volatile → per row) give 64
-- hex chars — exactly the varchar(64) column, and never the 43-char
-- token_urlsafe format prod issues.
UPDATE users
SET password_hash        = (SELECT pw_hash FROM _anon),
    must_change_password = false,
    ingest_token         = replace(gen_random_uuid()::text, '-', '')
                        || replace(gen_random_uuid()::text, '-', '');

-- Supabase login links: staging signs in through its OWN Supabase project,
-- so production's login ids mean nothing here — and while they're set, no
-- staging login can link to these accounts (linking only fills an empty
-- supabase_uid). Clear them; testers create staging logins and link by
-- email. Conditional because a dump taken before the Supabase migration
-- (d3f5a7b9c1e2) has no such column yet — then there's nothing to clear.
DO $uid$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name = 'users' AND column_name = 'supabase_uid') THEN
    UPDATE users SET supabase_uid = NULL;
  END IF;
END
$uid$;

-- Live prod session ids would otherwise log you in on staging.
DELETE FROM auth_session;

-- A prod invite code read off staging could open prod signup; a label may
-- name the friend it was for. New codes are made from staging's /admin.
UPDATE invite_codes
SET code   = replace(gen_random_uuid()::text, '-', ''),
    label  = 'Invite ' || id,
    active = false;

-- Self-check before committing: if any credential or identity slipped
-- through, abort and roll everything back.
DO $chk$
DECLARE
  staging_hash text := (SELECT pw_hash FROM _anon);
BEGIN
  IF EXISTS (SELECT 1 FROM auth_session) THEN
    RAISE EXCEPTION 'scrub check failed: auth_session still has rows';
  END IF;
  IF EXISTS (SELECT 1 FROM users
             WHERE role <> 'admin'
               AND (email <> 'user' || id || '@example.test'
                    OR name <> 'User ' || id)) THEN
    RAISE EXCEPTION 'scrub check failed: a non-admin user kept a real email/name';
  END IF;
  IF EXISTS (SELECT 1 FROM users WHERE password_hash IS DISTINCT FROM staging_hash) THEN
    RAISE EXCEPTION 'scrub check failed: a user kept a production password hash';
  END IF;
  IF EXISTS (SELECT 1 FROM users WHERE ingest_token !~ '^[0-9a-f]{64}$') THEN
    RAISE EXCEPTION 'scrub check failed: a user kept a production ingest token';
  END IF;
  IF EXISTS (SELECT 1 FROM invite_codes
             WHERE active OR code !~ '^[0-9a-f]{32}$') THEN
    RAISE EXCEPTION 'scrub check failed: an invite code is still active or unchanged';
  END IF;
END
$chk$;

COMMIT;
