import { describe, expect, it } from 'vitest'

import type { Movement } from '../api/types'
import { groupByDay, groupTransfers } from './movements'

let nextId = 0

function movement(fields: Partial<Movement>): Movement {
  nextId += 1
  return {
    id: `m${String(nextId)}`,
    account_id: 'bbva',
    type: 'expense',
    real_amount: '-100.00',
    accounting_amount: '-100.00',
    occurred_on: '2026-11-20',
    description: '',
    category_id: null,
    transfer_group_id: null,
    commitment_id: null,
    created_at: '2026-11-20T12:00:00Z',
    ...fields,
  }
}

function transferLegs(group: string, amount: string, occurredOn = '2026-11-20') {
  const source = movement({
    type: 'transfer',
    account_id: 'bbva',
    real_amount: `-${amount}`,
    accounting_amount: `-${amount}`,
    transfer_group_id: group,
    occurred_on: occurredOn,
  })
  const destination = movement({
    type: 'transfer',
    account_id: 'nu',
    real_amount: amount,
    accounting_amount: amount,
    transfer_group_id: group,
    occurred_on: occurredOn,
  })
  return { source, destination }
}

describe('groupTransfers', () => {
  it('joins both legs of a transfer into one row', () => {
    const { source, destination } = transferLegs('g1', '2000.00')

    // The API may return the destination first
    const rows = groupTransfers([destination, source])

    expect(rows).toEqual([
      {
        kind: 'transfer',
        key: 'g1',
        occurredOn: '2026-11-20',
        type: 'transfer',
        source,
        destination,
      },
    ])
  })

  it('shows a leg alone when its pair was cut by the limit', () => {
    const { source } = transferLegs('g1', '2000.00')

    expect(groupTransfers([source])).toEqual([
      { kind: 'single', key: source.id, occurredOn: '2026-11-20', movement: source },
    ])
  })
})

describe('groupByDay', () => {
  it('puts consecutive rows of the same day under one header', () => {
    const rows = groupTransfers([
      movement({ occurred_on: '2026-11-20' }),
      movement({ occurred_on: '2026-11-20' }),
      movement({ occurred_on: '2026-11-19' }),
    ])

    const days = groupByDay(rows)

    expect(days.map((day) => [day.day, day.rows.length])).toEqual([
      ['2026-11-20', 2],
      ['2026-11-19', 1],
    ])
  })
})
