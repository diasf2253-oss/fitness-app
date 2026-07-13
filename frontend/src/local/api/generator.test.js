/**
 * Generator port parity — mirrors backend/tests/test_generator.py, so the
 * phone builds the same program as the laptop.
 */
import { describe, expect, it } from 'vitest'
import { generate, isCompound } from './generator'
import { DEFAULT_VOLUME_TARGETS } from './muscles'

const ex = (i, name) => ({ id: i, name })

const POOLS = {
  Chest: [ex(1, 'Barbell Bench Press'), ex(2, 'Cable Fly'), ex(3, 'Incline Dumbbell Press')],
  Back: [ex(4, 'Barbell Row'), ex(5, 'Lat Pulldown'), ex(6, 'Deadlift')],
  Shoulders: [ex(7, 'Overhead Press'), ex(8, 'Lateral Raise')],
  Biceps: [ex(9, 'Barbell Curl'), ex(10, 'Cable Curl')],
  Triceps: [ex(11, 'Tricep Pushdown'), ex(12, 'Close-Grip Bench Press')],
  Quads: [ex(13, 'Barbell Squat'), ex(14, 'Leg Extension')],
  Hamstrings: [ex(15, 'Romanian Deadlift'), ex(16, 'Leg Curl')],
  Glutes: [ex(17, 'Hip Thrust'), ex(18, 'Cable Pull-Through')],
  Calves: [ex(19, 'Standing Calf Raise'), ex(20, 'Seated Calf Raise')],
  Abs: [ex(21, 'Cable Crunch'), ex(22, 'Hanging Leg Raise')],
}

const gen = (priority, days, split) => generate({
  priority, daysPerWeek: days, splitType: split,
  targets: DEFAULT_VOLUME_TARGETS, exercisesByGroup: POOLS,
})

describe('generator port', () => {
  it('detects compound movements', () => {
    expect(isCompound('Barbell Bench Press')).toBe(true)
    expect(isCompound('Romanian Deadlift')).toBe(true)
    expect(isCompound('Cable Fly')).toBe(false)
    expect(isCompound('Lateral Raise')).toBe(false)
  })

  it('priority tops the range and leads the day', () => {
    const prog = gen(['Chest', 'Back'], 6, 'ppl')
    expect(prog.weekly_sets.Chest).toBe(DEFAULT_VOLUME_TARGETS.Chest[1])   // 20
    expect(prog.weekly_sets.Back).toBe(DEFAULT_VOLUME_TARGETS.Back[1])     // 22
    const push = prog.routines.find(r => r.day_type === 'Push')
    const pull = prog.routines.find(r => r.day_type === 'Pull')
    expect(push.exercises[0].muscle_group).toBe('Chest')
    expect(pull.exercises[0].muscle_group).toBe('Back')
  })

  it('compounds come first with sensible reps', () => {
    const prog = gen(['Chest'], 4, 'ppl')
    const push = prog.routines.find(r => r.day_type === 'Push')
    const chest = push.exercises.filter(e => e.muscle_group === 'Chest')
    expect(chest[0].is_compound).toBe(true)
    expect([chest[0].rep_low, chest[0].rep_high]).toEqual([6, 10])
  })

  it('flags a priority muscle the split cannot reach', () => {
    const prog = gen(['Quads'], 3, 'bro')
    expect(prog.weekly_sets.Quads || 0).toBe(0)
    expect(prog.notes.some(n => n.includes('Quads') && n.includes('priority'))).toBe(true)
  })

  it('weekly sets equal the distributed per-day sets', () => {
    const prog = gen(['Chest'], 6, 'ppl')
    const push = prog.routines.find(r => r.day_type === 'Push')
    const perDay = push.exercises.filter(e => e.muscle_group === 'Chest')
      .reduce((a, e) => a + e.sets, 0)
    const pushDays = prog.arrangement.filter(d => d === 'Push').length
    expect(perDay * pushDays).toBe(prog.weekly_sets.Chest)
  })
})
