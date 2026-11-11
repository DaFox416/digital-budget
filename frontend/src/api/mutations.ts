import { useMutation, useQueryClient, type QueryClient } from '@tanstack/react-query'

import { api, unwrap } from './client'
import { queryKeys } from './queries'
import type { MovementCreate, TransferCreate } from './types'

/**
 * A new movement changes the list, the account balances and the seven figures. The frontend
 * doesn't recompute balances (no money math here): it asks the API again.
 */
function refreshAfterSaving(client: QueryClient): Promise<unknown> {
  return Promise.all([
    // ['movements'] matches every filtered list: ['movements', { limit: 50 }], ...
    client.invalidateQueries({ queryKey: ['movements'] }),
    client.invalidateQueries({ queryKey: queryKeys.accounts }),
    client.invalidateQueries({ queryKey: queryKeys.summary }),
  ])
}

export function useCreateMovement() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: MovementCreate) => unwrap(api.POST('/api/v1/movements', { body })),
    onSettled: () => refreshAfterSaving(client),
  })
}

export function useCreateTransfer() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: TransferCreate) => unwrap(api.POST('/api/v1/transfers', { body })),
    onSettled: () => refreshAfterSaving(client),
  })
}
