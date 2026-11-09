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
  it('leaves expenses and income as they are', () => {
    const cine = movement({ description: 'Cine' })
    const quincena = movement({ type: 'income', real_amount: '10000.00' })

    const rows = groupTransfers([cine, quincena])

    expect(rows).toEqual([
      { kind: 'single', key: cine.id, occurredOn: '2026-11-20', movement: cine },
      { kind: 'single', key: quincena.id, occurredOn: '2026-11-20', movement: quincena },
    ])
  })

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

  it('keeps the card payment type', () => {
    const { source, destination } = transferLegs('g1', '634.00')
    const payment = [
      { ...source, type: 'card_payment' as const },
      { ...destination, type: 'card_payment' as const, account_id: 'tdc-oro' },
    ]

    const [row] = groupTransfers(payment)

    expect(row).toMatchObject({ kind: 'transfer', type: 'card_payment' })
  })

  it('keeps the order of the list', () => {
    const cine = movement({ description: 'Cine' })
    const { source, destination } = transferLegs('g1', '2000.00')
    const despensa = movement({ description: 'Despensa' })

    const keys = groupTransfers([cine, source, destination, despensa]).map((row) => row.key)

    expect(keys).toEqual([cine.id, 'g1', despensa.id])
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

  it('returns no days for no rows', () => {
    expect(groupByDay([])).toEqual([])
  })
})
