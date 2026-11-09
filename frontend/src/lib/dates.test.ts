import { describe, expect, it } from 'vitest'

import { formatDay, formatShortDate } from './dates'

describe('formatDay', () => {
  it('formats a calendar day in Spanish', () => {
    expect(formatDay('2026-11-20')).toBe('vie 20 de nov')
  })

  it("doesn't move the day back in Mexico's time zone", () => {
    // The trap this avoids: new Date('2026-11-20') in Mexico City is the 19th
    expect(
      new Date('2026-11-20').toLocaleDateString('es-MX', { timeZone: 'America/Mexico_City' }),
    ).toBe('19/11/2026')

    expect(formatDay('2026-11-20')).toContain('20')
  })

  it('handles the change of year', () => {
    expect(formatDay('2027-01-01')).toBe('vie 1 de ene')
  })

  it.each(['2026-11-20T00:00:00', '20/11/2026', '', '2026-02-30'])('rejects %j', (value) => {
    expect(() => formatDay(value)).toThrow()
  })
})

describe('formatShortDate', () => {
  it('formats due dates and cutoffs', () => {
    expect(formatShortDate('2026-12-05')).toBe('5 dic')
    expect(formatShortDate('2028-02-29')).toBe('29 feb')
  })
})
