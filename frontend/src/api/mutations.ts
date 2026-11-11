import { useMutation, useQueryClient, type QueryClient, type QueryKey } from '@tanstack/react-query'

import { todayInMexico } from '../lib/dates'
import { api, unwrap } from './client'
import { queryKeys, type MovementFilters } from './queries'
import type { InstallmentPlanCreate, Movement, MovementCreate, TransferCreate } from './types'

/** Ids of rows shown before the API confirms them; the list marks them as "saving". */
export const PENDING_PREFIX = 'pending-'

export function isPendingId(id: string): boolean {
  return id.startsWith(PENDING_PREFIX)
}

function pendingId(): string {
  return `${PENDING_PREFIX}${crypto.randomUUID()}`
}

// Only a sign in front of the typed amount: no arithmetic on money
function negative(amount: string | number): string {
  return `-${String(amount)}`
}

function pendingMovement(fields: Partial<Movement> & Pick<Movement, 'account_id'>): Movement {
  return {
    id: pendingId(),
    type: 'expense',
    real_amount: '0.00',
    accounting_amount: '0.00',
    occurred_on: todayInMexico(),
    description: '',
    category_id: null,
    transfer_group_id: null,
    commitment_id: null,
    created_at: new Date().toISOString(),
    ...fields,
  }
}

type Snapshot = [QueryKey, Movement[] | undefined][]

/**
 * Optimistic update: the new rows show in the movement lists right away, before the API
 * answers. Returns what the lists held, to put it back if saving fails.
 */
async function showPending(client: QueryClient, rows: Movement[]): Promise<Snapshot> {
  // A refetch landing now would overwrite the pending rows
  await client.cancelQueries({ queryKey: ['movements'] })
  const snapshot = client.getQueriesData<Movement[]>({ queryKey: ['movements'] })
  for (const [key, list] of snapshot) {
    if (!list) continue
    const filters = key[1] as MovementFilters | undefined
    // A list filtered by account only gets the rows of that account
    const matching = rows.filter(
      (row) => filters?.account_id === undefined || row.account_id === filters.account_id,
    )
    client.setQueryData<Movement[]>(key, [...matching, ...list])
  }
  return snapshot
}

function restore(client: QueryClient, snapshot: Snapshot | undefined): void {
  for (const [key, list] of snapshot ?? []) client.setQueryData(key, list)
}

/**
 * Saved or not, ask the API again: the real rows replace the pending ones, and balances and
 * the seven figures come from the backend (no money math in the frontend).
 */
function refreshAfterSaving(client: QueryClient): Promise<unknown> {
  return Promise.all(
    [
      // ['movements'] matches every filtered list: ['movements', { limit: 50 }], ...
      ['movements'],
      queryKeys.accounts,
      queryKeys.summary,
      queryKeys.commitments,
      // "available" changed, so do the warnings and suggestions
      ['movement-preview'],
    ].map((queryKey) => client.invalidateQueries({ queryKey })),
  )
}

export function useCreateMovement() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: MovementCreate) => unwrap(api.POST('/api/v1/movements', { body })),
    onMutate: (body) =>
      showPending(client, [
        pendingMovement({
          account_id: body.account_id,
          type: body.type,
          real_amount: body.type === 'expense' ? negative(body.amount) : String(body.amount),
          occurred_on: body.occurred_on ?? todayInMexico(),
          description: body.description,
          category_id: body.category_id ?? null,
        }),
      ]),
    onError: (_error, _body, snapshot) => {
      restore(client, snapshot)
    },
    onSettled: () => refreshAfterSaving(client),
  })
}

export interface TransferVariables {
  body: TransferCreate
  // Known from the tab; the API decides it again from the destination account
  type: 'transfer' | 'card_payment'
}

export function useCreateTransfer() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ body }: TransferVariables) => unwrap(api.POST('/api/v1/transfers', { body })),
    onMutate: ({ body, type }) => {
      const group = pendingId()
      const leg = {
        type,
        occurred_on: body.occurred_on ?? todayInMexico(),
        transfer_group_id: group,
      }
      return showPending(client, [
        pendingMovement({
          ...leg,
          account_id: body.source_account_id,
          real_amount: negative(body.amount),
          description: body.description,
        }),
        pendingMovement({
          ...leg,
          account_id: body.destination_account_id,
          real_amount: String(body.amount),
        }),
      ])
    },
    onError: (_error, _variables, snapshot) => {
      restore(client, snapshot)
    },
    onSettled: () => refreshAfterSaving(client),
  })
}

export function useCreateInstallmentPlan() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: InstallmentPlanCreate) =>
      unwrap(api.POST('/api/v1/installment-plans', { body })),
    onMutate: (body) =>
      showPending(client, [
        pendingMovement({
          account_id: body.account_id,
          real_amount: negative(body.total),
          occurred_on: body.purchased_on ?? todayInMexico(),
          description: body.description,
          category_id: body.category_id ?? null,
        }),
      ]),
    onError: (_error, _body, snapshot) => {
      restore(client, snapshot)
    },
    onSettled: () => refreshAfterSaving(client),
  })
}
