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

/** A route's reply: a JSON body (200), or a full Response for errors. */
export type RouteReply = unknown

/**
 * Stub fetch by path, for screens that make several calls at once. Each call gets a fresh
 * Response (a body can only be read once). Unknown paths answer 404.
 * Replace a route mid-test by mutating the returned `routes` object.
 */
export function stubApi(initial: Record<string, RouteReply>) {
  const routes: Record<string, RouteReply> = { ...initial }
  const mock = vi.fn((request: Request) => {
    const path = new URL(request.url).pathname
    if (!(path in routes)) return Promise.resolve(jsonResponse({ detail: 'Not Found' }, 404))
    const reply = routes[path]
    return Promise.resolve(reply instanceof Response ? reply.clone() : jsonResponse(reply))
  })
  vi.stubGlobal('fetch', mock)
  return { mock, routes }
}
