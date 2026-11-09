import createClient from 'openapi-fetch'

import type { paths } from './schema'

/**
 * Typed client for the backend: routes, parameters and responses come from the OpenAPI
 * schema (`npm run api:types`), so a wrong path or field fails at compile time.
 */
export const api = createClient<paths>({
  // openapi-fetch builds a Request, which needs an absolute URL. The dev server proxies /api.
  baseUrl: globalThis.location.origin,
  // Look up fetch on every call instead of capturing it once, so tests can stub it.
  fetch: (request) => globalThis.fetch(request),
})

/** An error response from the API, with FastAPI's `detail` turned into a readable message. */
export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, detail: unknown) {
    super(messageFrom(status, detail))
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

function messageFrom(status: number, detail: unknown): string {
  // Domain, 404 and 409 errors: { "detail": "Account named 'Nu' already exists" }
  if (typeof detail === 'string') return detail
  // Pydantic validation errors (422): { "detail": [{ "msg": "...", ... }] }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item: unknown) =>
        typeof item === 'object' && item !== null && 'msg' in item ? String(item.msg) : null,
      )
      .filter((message) => message !== null)
    if (messages.length > 0) return messages.join('; ')
  }
  return `Request failed with status ${String(status)}`
}

// Only FastAPI's JSON `detail`; a non-JSON body (a proxy's HTML page) isn't a useful message
function detailOf(error: unknown): unknown {
  return typeof error === 'object' && error !== null && 'detail' in error ? error.detail : undefined
}

interface ApiResult<T> {
  data?: T
  error?: unknown
  response: Response
}

/**
 * Returns the data of a successful call or throws an ApiError.
 *
 * openapi-fetch returns `{ data, error }` instead of throwing, but TanStack Query only sees
 * a failure when the query function throws: this connects the two.
 */
export async function unwrap<T>(call: Promise<ApiResult<T>>): Promise<T> {
  const { data, error, response } = await call
  if (error !== undefined || !response.ok) {
    throw new ApiError(response.status, detailOf(error))
  }
  return data as T
}
