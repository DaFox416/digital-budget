import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import App from './App'

describe('App', () => {
  it('shows the API as connected when /health responds ok', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"status":"ok"}')))

    render(<App />)

    expect(await screen.findByText('Conectada')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('/api/v1/health', expect.anything())
  })

  it('shows the API as down when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    render(<App />)

    expect(await screen.findByText('Sin conexión')).toBeInTheDocument()
  })
})
