import { describe, expect, it } from 'vitest'

import { formatMoney, isMoney } from './money'

describe('formatMoney', () => {
  it.each([
    ['14777.11', '$14,777.11'],
    ['-387.56', '-$387.56'],
  ])('formats %s as %s', (amount, expected) => {
    expect(formatMoney(amount)).toBe(expected)
  })

  it('shows negative zero without a minus sign', () => {
    expect(formatMoney('-0.00')).toBe('$0.00')
  })

  it('keeps cents a float would lose', () => {
    // As a number this value prints .94: floats can't represent it exactly
    expect(formatMoney('90071992547409.93')).toBe('$90,071,992,547,409.93')
  })

  it.each(['abc', '12.345', '1,000.00'])('rejects %j', (amount) => {
    expect(() => formatMoney(amount)).toThrow('Not a money amount')
  })
})

describe('isMoney', () => {
  it('accepts what the API sends', () => {
    expect(isMoney('-387.56')).toBe(true)
    expect(isMoney('10164.67')).toBe(true)
  })

  it('rejects more than 2 decimals', () => {
    expect(isMoney('0.001')).toBe(false)
  })
})
