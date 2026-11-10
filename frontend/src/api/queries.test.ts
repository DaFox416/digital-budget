import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { jsonResponse, queryWrapper, requestOf, stubFetch } from '../test/query'
import { ApiError } from './client'
import { useMovements, useSummary } from './queries'

describe('useSummary', () => {
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
})
