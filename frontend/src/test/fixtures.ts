import type { Account, CardSummary, Category, Movement, Summary } from '../api/types'

// The example from docs/PLANEACION.md: BBVA, a credit card with a 12 MSI laptop, Nov 20

const cycle = { start: '2026-10-16', cutoff: '2026-11-15', payment_due: '2026-12-05' }

export const bbva: Account = {
  id: 'bbva',
  type: 'debit',
  name: 'BBVA',
  initial_balance: '5000.00',
  balance: '14777.11',
  color: '#1A73E8',
  position: 0,
  credit: null,
}

export const tdcOro: Account = {
  id: 'tdc-oro',
  type: 'credit',
  name: 'TDC Oro',
  initial_balance: '0.00',
  balance: '-12634.00',
  color: null,
  position: 1,
  credit: {
    credit_limit: '20000.00',
    cutoff_day: 15,
    payment_due_rule: 'fixed_day',
    payment_due_value: 5,
    available: '7366.00',
    current_cycle: { start: '2026-11-16', cutoff: '2026-12-15', payment_due: '2027-01-05' },
    last_statement: cycle,
  },
}

export const categories: Category[] = [{ id: 'comida', name: 'Comida', icon: 'utensils' }]

export const tdcOroSummary: CardSummary = {
  account_id: 'tdc-oro',
  name: 'TDC Oro',
  debt: '12634.00',
  installments_pending: '10000.00',
  next_payment: {
    cutoff: '2026-11-15',
    payment_due: '2026-12-05',
    amount: '1634.00',
    is_closed: true,
  },
}

export const summary: Summary = {
  on: '2026-11-20',
  // Adds up: 12,000 + 0 + 12,634 + 0 + 143.11 - 10,000 = 14,777.11
  real_balance: '14777.11',
  available: '12000.00',
  set_aside: '0.00',
  card_debt: '12634.00',
  savings_goals: '0.00',
  leftover: '143.11',
  leftover_releasable: '140.00',
  installments_pending: '10000.00',
  cards: [tdcOroSummary],
}

function movement(fields: Partial<Movement> & Pick<Movement, 'id'>): Movement {
  return {
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

export const movements: Movement[] = [
  movement({
    id: 'cine',
    real_amount: '-387.56',
    accounting_amount: '-387.56',
    description: 'Cine',
    category_id: 'comida',
  }),
  movement({
    id: 'pago-src',
    type: 'card_payment',
    real_amount: '-634.00',
    accounting_amount: '-634.00',
    transfer_group_id: 'pago',
  }),
  movement({
    id: 'pago-dst',
    type: 'card_payment',
    account_id: 'tdc-oro',
    real_amount: '634.00',
    accounting_amount: '634.00',
    transfer_group_id: 'pago',
  }),
  movement({
    id: 'quincena',
    type: 'income',
    real_amount: '10164.67',
    accounting_amount: '10164.67',
    description: 'Quincena',
    occurred_on: '2026-11-19',
  }),
]

export const homeRoutes = {
  '/api/v1/health': { status: 'ok' },
  '/api/v1/summary': summary,
  '/api/v1/accounts': [bbva, tdcOro],
  '/api/v1/categories': categories,
  '/api/v1/movements': movements,
}
