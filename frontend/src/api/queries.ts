import { useQuery } from '@tanstack/react-query'

import { api, unwrap } from './client'
import type { MovementPreviewRequest } from './types'

export interface MovementFilters {
  account_id?: string
  limit?: number
}

/**
 * Cache keys in one place. Mutations (day 11) will invalidate these, so a new movement
 * refreshes movements, accounts and the summary together.
 */
export const queryKeys = {
  health: ['health'] as const,
  accounts: ['accounts'] as const,
  categories: ['categories'] as const,
  movements: (filters: MovementFilters = {}) => ['movements', filters] as const,
  summary: ['summary'] as const,
  preferences: ['preferences'] as const,
  commitments: ['commitments'] as const,
  preview: (body: MovementPreviewRequest) => ['movement-preview', body] as const,
}

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: () => unwrap(api.GET('/api/v1/health')),
  })
}

export function useAccounts() {
  return useQuery({
    queryKey: queryKeys.accounts,
    queryFn: () => unwrap(api.GET('/api/v1/accounts')),
  })
}

export function useCategories() {
  return useQuery({
    queryKey: queryKeys.categories,
    queryFn: () => unwrap(api.GET('/api/v1/categories')),
    // Categories barely change
    staleTime: 5 * 60_000,
  })
}

export function useMovements(filters: MovementFilters = {}) {
  return useQuery({
    queryKey: queryKeys.movements(filters),
    queryFn: () => unwrap(api.GET('/api/v1/movements', { params: { query: filters } })),
  })
}

export function useSummary() {
  return useQuery({
    queryKey: queryKeys.summary,
    queryFn: () => unwrap(api.GET('/api/v1/summary')),
  })
}

export function usePreferences() {
  return useQuery({
    queryKey: queryKeys.preferences,
    queryFn: () => unwrap(api.GET('/api/v1/preferences')),
  })
}

export function useCommitments() {
  return useQuery({
    queryKey: queryKeys.commitments,
    queryFn: () => unwrap(api.GET('/api/v1/commitments')),
  })
}

/** Suggested accounting amount and purchase warning for what's being captured. Stores nothing. */
export function previewQuery(body: MovementPreviewRequest) {
  return {
    queryKey: queryKeys.preview(body),
    queryFn: () => unwrap(api.POST('/api/v1/movements/preview', { body })),
  }
}

export function usePreview(body: MovementPreviewRequest | null) {
  return useQuery({
    // A placeholder key while there's nothing to preview; `enabled` keeps it from running
    ...previewQuery(body ?? { account_id: '', type: 'expense', amount: '0' }),
    enabled: body !== null,
  })
}
