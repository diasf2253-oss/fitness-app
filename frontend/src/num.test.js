import { describe, expect, it } from 'vitest'
import { parseDecimal } from './num'

describe('parseDecimal', () => {
  it('parses comma decimals (European keyboards)', () => {
    expect(parseDecimal('82,5')).toBe(82.5)
    expect(parseDecimal('7,25')).toBe(7.25)
  })

  it('parses dot decimals and integers', () => {
    expect(parseDecimal('82.5')).toBe(82.5)
    expect(parseDecimal('90')).toBe(90)
    expect(parseDecimal(' 82,5 ')).toBe(82.5)
  })

  it('returns null for empty input', () => {
    expect(parseDecimal('')).toBeNull()
    expect(parseDecimal('   ')).toBeNull()
    expect(parseDecimal(null)).toBeNull()
    expect(parseDecimal(undefined)).toBeNull()
  })

  it('returns null for garbage instead of NaN', () => {
    expect(parseDecimal('abc')).toBeNull()
    expect(parseDecimal('8o')).toBeNull()
    expect(parseDecimal('1,2,3')).toBeNull()
  })
})
