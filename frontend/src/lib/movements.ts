import type { Movement } from '../api/types'

/** One row of the movement list: an expense or income, or both legs of a transfer. */
export type MovementRow =
  | { kind: 'single'; key: string; occurredOn: string; movement: Movement }
  | {
      kind: 'transfer'
      key: string
      occurredOn: string
      type: Movement['type']
      // Money leaves the source (negative leg) and enters the destination (positive leg)
      source: Movement
      destination: Movement
    }

export interface MovementDay {
  day: string
  rows: MovementRow[]
}

/**
 * Join the two legs of each transfer or card payment into one row, keeping the API's order
 * (newest first). A leg whose pair isn't in the list (cut by the limit) stays on its own.
 */
export function groupTransfers(movements: readonly Movement[]): MovementRow[] {
  const legsByGroup = new Map<string, Movement[]>()
  for (const movement of movements) {
    if (movement.transfer_group_id === null) continue
    const legs = legsByGroup.get(movement.transfer_group_id) ?? []
    legs.push(movement)
    legsByGroup.set(movement.transfer_group_id, legs)
  }

  const rows: MovementRow[] = []
  const done = new Set<string>()
  for (const movement of movements) {
    const group = movement.transfer_group_id
    const legs = group === null ? undefined : legsByGroup.get(group)
    const source = legs?.find((leg) => leg.real_amount.startsWith('-'))
    const destination = legs?.find((leg) => !leg.real_amount.startsWith('-'))

    if (group === null || !source || !destination) {
      rows.push({
        kind: 'single',
        key: movement.id,
        occurredOn: movement.occurred_on,
        movement,
      })
    } else if (!done.has(group)) {
      done.add(group)
      rows.push({
        kind: 'transfer',
        key: group,
        occurredOn: movement.occurred_on,
        type: movement.type,
        source,
        destination,
      })
    }
  }
  return rows
}

/** Consecutive rows with the same date under one day header. */
export function groupByDay(rows: readonly MovementRow[]): MovementDay[] {
  const days: MovementDay[] = []
  for (const row of rows) {
    const last = days.at(-1)
    if (last?.day === row.occurredOn) {
      last.rows.push(row)
    } else {
      days.push({ day: row.occurredOn, rows: [row] })
    }
  }
  return days
}
