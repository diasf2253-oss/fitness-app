-- Anonymise a production copy for staging. Run by app.cli.copy_database
-- (--to staging), i.e. ./scripts/move_to_supabase.sh staging or
-- ./scripts/seed_staging.sh. Destructive by design — never point this at production.
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
--         supabase_uid -> NULL (staging has its own Supabase logins; people
--         re-link by email on first staging sign-in); the unused legacy
--         password_hash -> NULL; ingest_token -> fresh random;
--       - auth_session (legacy, unused): all rows deleted;
--       - invite_codes: code -> fresh random, active -> false,
--         label -> Invite <id>.
--     The admin row keeps its email and name, so the operator signs in to
--     staging with their usual email (as a staging Supabase login).
--     Ids, roles and statuses stay.
--
-- All-or-nothing: one transaction that checks its own work before COMMIT;
-- any failure rolls every change back. Plain SQL — no psql meta-commands —
-- so it runs through psql or a driver alike.
--
-- Plain SQL UPDATEs deliberately bypass the ORM's onupdate, so updated_at
-- keeps its production values and sync/merge behaviour stays realistic.
-- Needs Postgres 13+ (gen_random_uuid() is built in from 13) and the schema
-- at migration d3f5a7b9c1e2 or later (supabase_uid, nullable password_hash) —
-- copy_database runs `alembic upgrade head` first.

BEGIN;

-- One offset for the whole run: the weight *trend* (what the calorie engine
-- and charts read) is preserved; the absolute values are masked.
CREATE TEMP TABLE _anon AS
SELECT (random() * 6 - 3) AS weight_offset_kg;

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

-- Credentials, admin included. Staging signs in through its OWN Supabase
-- project, so production's login ids mean nothing here — and while they're
-- set, no staging login can link to these accounts (linking only fills an
-- empty supabase_uid). The legacy password hash is unused since the switch
-- to Supabase Auth; clear it anyway. A fresh ingest token so the prod tokens
-- on friends' phones can't push here. Two gen_random_uuid() (Postgres's
-- strong RNG, volatile → per row) give 64 hex chars — exactly the
-- varchar(64) column, and never the 43-char token_urlsafe format prod issues.
UPDATE users
SET supabase_uid         = NULL,
    password_hash        = NULL,
    must_change_password = false,
    ingest_token         = replace(gen_random_uuid()::text, '-', '')
                        || replace(gen_random_uuid()::text, '-', '');

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
  IF EXISTS (SELECT 1 FROM users
             WHERE password_hash IS NOT NULL OR supabase_uid IS NOT NULL) THEN
    RAISE EXCEPTION 'scrub check failed: a user kept a production login id or password hash';
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
