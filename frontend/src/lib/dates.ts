/**
 * Calendar dates from the API ("2026-11-20") are days, not instants.
 *
 * `new Date('2026-11-20')` reads them as midnight UTC, which in Mexico is 6 pm of the 19th:
 * every date would show one day early. Instead we split the string and format a UTC date
 * in UTC, so the machine's time zone never moves the day.
 */
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/

const dayFormat = new Intl.DateTimeFormat('es-MX', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  timeZone: 'UTC',
})

const shortFormat = new Intl.DateTimeFormat('es-MX', {
  day: 'numeric',
  month: 'short',
  timeZone: 'UTC',
})

function toUtcDate(iso: string): Date {
  const match = ISO_DATE.exec(iso)
  if (!match) throw new Error(`Not an ISO date: ${JSON.stringify(iso)}`)
  const [, year, month, day] = match
  const date = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)))
  // Date.UTC rolls 2026-02-30 over to March 2: reject impossible dates instead
  if (date.getUTCDate() !== Number(day)) throw new Error(`Not a valid date: ${iso}`)
  return date
}

/** "2026-11-20" -> "vie 20 de nov": headers of the movement list. */
export function formatDay(iso: string): string {
  return dayFormat.format(toUtcDate(iso))
}

/** "2026-12-05" -> "5 dic": due dates and cutoffs. */
export function formatShortDate(iso: string): string {
  return shortFormat.format(toUtcDate(iso))
}

const mexicoDate = new Intl.DateTimeFormat('en-CA', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  timeZone: 'America/Mexico_City',
})

/**
 * Today as "2026-11-20" in Mexico City, the same zone the backend uses for "today". Taken
 * from the parts, since the separator of a locale's format isn't guaranteed.
 */
export function todayInMexico(now: Date = new Date()): string {
  const parts = mexicoDate.formatToParts(now)
  const part = (type: Intl.DateTimeFormatPartTypes): string => {
    const found = parts.find((item) => item.type === type)
    if (!found) throw new Error(`Date format has no ${type}`)
    return found.value
  }
  return `${part('year')}-${part('month')}-${part('day')}`
}
