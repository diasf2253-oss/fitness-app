/**
 * Muscle-group taxonomy + name-based auto-tagging, local-first — mirrors
 * backend/app/muscles.py. Only PRIMARY muscle groups count anywhere.
 */

export const MUSCLE_GROUPS = [
  'Chest', 'Back', 'Shoulders', 'Biceps', 'Triceps',
  'Quads', 'Hamstrings', 'Glutes', 'Calves', 'Abs', 'Adductors',
]

// Per-muscle weekly working-set target ranges [low, high] — mirrors
// muscles.DEFAULT_VOLUME_TARGETS. Read by the generator + sets-per-week.
export const DEFAULT_VOLUME_TARGETS = {
  Chest: [10, 20], Back: [10, 22], Shoulders: [8, 20],
  Biceps: [8, 20], Triceps: [8, 18], Quads: [8, 18],
  Hamstrings: [6, 16], Glutes: [8, 16], Calves: [8, 16], Abs: [6, 20],
  Adductors: [6, 16],
}

/** Default ranges with per-user overrides merged on top — mirrors
 * muscles.resolved_volume_targets. Unknown/malformed entries are ignored. */
export function resolvedVolumeTargets(overrides) {
  const out = { ...DEFAULT_VOLUME_TARGETS }
  if (overrides) {
    for (const [muscle, rng] of Object.entries(overrides)) {
      if (muscle in out && Array.isArray(rng) && rng.length === 2) {
        const lo = parseInt(rng[0], 10)
        const hi = parseInt(rng[1], 10)
        if (Number.isFinite(lo) && Number.isFinite(hi)) out[muscle] = [lo, hi]
      }
    }
  }
  return out
}

// Ordered (specific → general): first matching rule wins, so "leg curl"
// hits Hamstrings before "curl" hits Biceps.
const NAME_RULES = [
  // Keep ahead of the leg rules; deliberately not keyed on 'sumo'.
  [['adductor', 'adduction', 'copenhagen'], 'Adductors'],
  [['calf', 'calve'], 'Calves'],
  [['hamstring', 'leg curl', 'lying curl', 'romanian', 'rdl', 'good morning', 'nordic'], 'Hamstrings'],
  [['glute', 'hip thrust', 'pull-through', 'pull through', 'kickback'], 'Glutes'],
  [['quad', 'squat', 'leg press', 'leg extension', 'lunge', 'split squat', 'hack', 'sissy', 'step-up', 'step up'], 'Quads'],
  [['tricep', 'pushdown', 'push-down', 'skull', 'close-grip', 'close grip', 'jm press', 'overhead extension', 'dip'], 'Triceps'],
  [['bicep', 'curl', 'chin-up', 'chin up', 'chinup', 'preacher'], 'Biceps'],
  [['lateral raise', 'side raise', 'rear delt', 'reverse fly', 'reverse flye', 'face pull', 'overhead press', 'shoulder press', 'military press', 'arnold', 'upright row', 'delt'], 'Shoulders'],
  [['row', 'pulldown', 'pull-down', 'pull-up', 'pull up', 'pullup', 'pullover', 'deadlift', 'lat ', 'back extension', 'shrug'], 'Back'],
  [['bench', 'chest', 'fly', 'flye', 'pec', 'push-up', 'push up', 'pushup', 'incline', 'decline'], 'Chest'],
  [['abs', 'ab ', 'crunch', 'plank', 'leg raise', 'knee raise', 'sit-up', 'sit up', 'rollout', 'hollow', 'russian twist', 'core', 'oblique'], 'Abs'],
]

const LEGACY_MAP = {
  chest: 'Chest', back: 'Back', shoulders: 'Shoulders',
  biceps: 'Biceps', triceps: 'Triceps', quads: 'Quads',
  hamstrings: 'Hamstrings', glutes: 'Glutes', calves: 'Calves',
  core: 'Abs', abs: 'Abs',
}

/** Best-guess primary muscle group from an exercise name — mirrors
 * muscles.suggest_muscle_group. Returns null when nothing matches. */
export function suggestMuscleGroup(name, legacyPrimary = null) {
  const n = (name || '').toLowerCase()
  for (const [keywords, group] of NAME_RULES) {
    if (keywords.some(k => n.includes(k))) return group
  }
  if (legacyPrimary) return LEGACY_MAP[legacyPrimary.trim().toLowerCase()] || null
  return null
}
