import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import App from './App'
import { jsonResponse, queryWrapper, requestOf, stubFetch } from './test/query'

describe('App', () => {
  it('shows the API as connected when /health responds ok', async () => {
    const fetchMock = stubFetch(jsonResponse({ status: 'ok' }))

    render(<App />, { wrapper: queryWrapper() })

    expect(await screen.findByText('Conectada')).toBeInTheDocument()
    expect(new URL(requestOf(fetchMock).url).pathname).toBe('/api/v1/health')
  })

  it('shows the API as down when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    render(<App />, { wrapper: queryWrapper() })

    expect(await screen.findByText('Sin conexión')).toBeInTheDocument()
  })

  it('shows the API as down when it answers with an error', async () => {
    stubFetch(jsonResponse({ detail: 'Service unavailable' }, 503))

    render(<App />, { wrapper: queryWrapper() })

    expect(await screen.findByText('Sin conexión')).toBeInTheDocument()
  })
})
