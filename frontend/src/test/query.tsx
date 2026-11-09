import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { vi } from 'vitest'

/** A fresh cache per test, without retries so failures show up right away. */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

export function queryWrapper(client: QueryClient = createTestQueryClient()) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** Stub fetch with one response and return the mock, to inspect the Request it got. */
export function stubFetch(response: Response) {
  const mock = vi.fn<(request: Request) => Promise<Response>>().mockResolvedValue(response)
  vi.stubGlobal('fetch', mock)
  return mock
}

/** The Request that the stubbed fetch received on its nth call. */
export function requestOf(mock: ReturnType<typeof stubFetch>, call = 0): Request {
  const request = mock.mock.calls.at(call)?.[0]
  if (!request) throw new Error(`fetch wasn't called ${String(call + 1)} time(s)`)
  return request
}
