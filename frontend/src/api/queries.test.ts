import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { jsonResponse, queryWrapper, requestOf, stubFetch } from '../test/query'
import { ApiError } from './client'
import { queryKeys, useMovements, useSummary } from './queries'
import type { Summary } from './types'

const summary: Summary = {
  on: '2026-11-20',
  real_balance: '14777.11',
  card_debt: '12634.00',
  installments_pending: '10000.00',
  cards: [],
}

describe('useSummary', () => {
  it('returns the typed summary, amounts as strings', async () => {
    const fetchMock = stubFetch(jsonResponse(summary))

    const { result } = renderHook(() => useSummary(), { wrapper: queryWrapper() })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })
    expect(result.current.data).toEqual(summary)
    expect(result.current.data?.real_balance).toBe('14777.11')
    expect(new URL(requestOf(fetchMock).url).pathname).toBe('/api/v1/summary')
  })

  it('exposes API errors as ApiError', async () => {
    stubFetch(jsonResponse({ detail: 'boom' }, 500))

    const { result } = renderHook(() => useSummary(), { wrapper: queryWrapper() })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })
    expect(result.current.error).toBeInstanceOf(ApiError)
  })
})

describe('useMovements', () => {
  it('sends the filters as query parameters', async () => {
    const fetchMock = stubFetch(jsonResponse([]))

    renderHook(() => useMovements({ account_id: 'abc', limit: 20 }), { wrapper: queryWrapper() })

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled()
    })
    const url = new URL(requestOf(fetchMock).url)
    expect(url.pathname).toBe('/api/v1/movements')
    expect(url.searchParams.get('account_id')).toBe('abc')
    expect(url.searchParams.get('limit')).toBe('20')
  })

  it('caches each set of filters separately', () => {
    expect(queryKeys.movements({ account_id: 'a' })).not.toEqual(
      queryKeys.movements({ account_id: 'b' }),
    )
  })
})
