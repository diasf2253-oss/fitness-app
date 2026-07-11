/**
 * Tests for the local rank-engine port — expected values mirror
 * backend/tests/test_ranks.py one-for-one, so the JS ladder computes
 * exactly what the Python backend computes.
 */
import { describe, expect, it } from 'vitest'
import {
  COMMON_ANCHORS, STANDARDS, TIERS, computeRank, exerciseBenchmark,
  isUnilateral, resolveConfig, tierLowers,
} from './ranks'
import { suggestMuscleGroup } from './muscles'

const SQUAT = STANDARDS.squat   // [1.25, 1.50, 1.75, 2.25, 2.75]

describe('tier mapping (mirrors test_ranks.py)', () => {
  it('each tier starts at its mapped boundary in division III, 0 LP', () => {
    const lowers = tierLowers(SQUAT)
    lowers.forEach((low, i) => {
      const r = computeRank(low + 1e-9, SQUAT)
      expect(r.tier).toBe(TIERS[i])
      if (i > 0) {
        expect(r.division).toBe('III')
        expect(r.lp).toBe(0)
      }
    })
  })

  it('below beginner is Wood; the boundary flips to Bronze', () => {
    expect(computeRank(1.0, SQUAT).tier).toBe('Wood')
    expect(computeRank(1.24, SQUAT).tier).toBe('Wood')
    expect(computeRank(1.25, SQUAT).tier).toBe('Bronze')
  })

  it('divisions climb within a tier (Bronze band [1.25, 1.50) in thirds)', () => {
    expect(computeRank(1.25, SQUAT).division).toBe('III')
    expect(computeRank(1.25 + 0.0834, SQUAT).division).toBe('II')
    expect(computeRank(1.25 + 0.1667, SQUAT).division).toBe('I')
  })

  it('LP is percent within the division', () => {
    const sub = (1.50 - 1.25) / 3
    const divILo = 1.25 + 2 * sub
    const mid = computeRank(divILo + sub / 2, SQUAT)
    expect(mid.tier).toBe('Bronze')
    expect(mid.division).toBe('I')
    expect(Math.abs(mid.lp - 50)).toBeLessThanOrEqual(1)
    expect(computeRank(1.4999, SQUAT).lp).toBeGreaterThanOrEqual(99)
  })

  it('Olympian is open-ended', () => {
    expect(computeRank(2.75, SQUAT).tier).toBe('Olympian')
    const top = computeRank(5.0, SQUAT)
    expect(top.tier).toBe('Olympian')
    expect(top.division).toBe('I')
    expect(top.lp).toBe(100)
  })
})

describe('benchmarks (mirrors test_exercise_benchmark_*)', () => {
  const cfg = resolveConfig(null)

  it('tabulated exercises use their own value untouched', () => {
    expect(exerciseBenchmark('Barbell Squat', 'Quads', 'male', cfg, 'barbell')).toBe(1.75)
  })

  it('custom exercises: group fallback × equipment × unilateral', () => {
    const bb = exerciseBenchmark('My Custom Press', 'Chest', 'male', cfg, 'barbell')
    const dumb = exerciseBenchmark('My Custom DB Press', 'Chest', 'male', cfg, 'dumbbell')
    const uni = exerciseBenchmark('Single-Arm DB Press', 'Chest', 'male', cfg, 'dumbbell')
    expect(dumb).toBeCloseTo(bb * 0.42, 10)
    expect(uni).toBeCloseTo(dumb * 0.55, 10)
  })

  it('female multiplier scales the reference down', () => {
    const f = exerciseBenchmark('Barbell Squat', 'Quads', 'female', cfg, 'barbell')
    expect(f).toBeCloseTo(1.75 * cfg.female_multiplier, 10)
  })

  it('config overrides standards per lift, leaving others default', () => {
    const over = resolveConfig({ standards: { squat: [1, 2, 3, 4, 5] }, female_multiplier: 0.7 })
    expect(over.standards.squat).toEqual([1, 2, 3, 4, 5])
    expect(over.female_multiplier).toBe(0.7)
    expect(over.standards.bench).toEqual(STANDARDS.bench)
  })

  it('body-part average example from the endpoint test', () => {
    // Squat 160/80bw vs 1.75 and Leg Extension 52/80 vs 1.30 → mean score
    const mean = (160 / 80 / 1.75 + 52 / 80 / 1.30) / 2
    const r = computeRank(mean, COMMON_ANCHORS)
    expect(computeRank(160 / 80 / 1.75, COMMON_ANCHORS).tier).toBe('Platinum')
    expect(r.tier).toBe(TIERS[r.tier_index])   // internally consistent
  })
})

describe('unilateral hints + auto-tagging', () => {
  it('detects unilateral movements by name', () => {
    expect(isUnilateral('Bulgarian Split Squat')).toBe(true)
    expect(isUnilateral('Single-Arm Row')).toBe(true)
    expect(isUnilateral('Barbell Bench Press')).toBe(false)
  })

  it('suggests groups like the backend (specific rules win)', () => {
    expect(suggestMuscleGroup('Leg Curl (Lying)')).toBe('Hamstrings')  // not Biceps
    expect(suggestMuscleGroup('Barbell Curl')).toBe('Biceps')
    expect(suggestMuscleGroup('Weird Movement', 'core')).toBe('Abs')   // legacy fallback
    expect(suggestMuscleGroup('Mystery Machine')).toBeNull()
  })
})
