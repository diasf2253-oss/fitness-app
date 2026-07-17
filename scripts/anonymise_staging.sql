-- Anonymise a production copy for staging (run by scripts/seed_staging.sh).
--
-- Keeps the dataset realistic — exercise/routine/session names, dates, sets,
-- reps, streaks and volumes all survive, so ranks, insights and the adaptive
-- calorie engine behave like production. What goes:
--   * every free-text field (journal entries, notes, cues) — the actually
--     personal content;
--   * true body weight — shifted by one random per-run offset (trend intact)
--     plus per-row noise;
--   * steps and nutrition — small per-row jitter;
--   * profile age — reset to a generic value.
--
-- Plain SQL UPDATEs deliberately bypass the ORM's onupdate, so updated_at
-- keeps its production values and sync/merge behaviour stays realistic.

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

COMMIT;
