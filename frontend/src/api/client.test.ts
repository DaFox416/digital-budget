import { describe, expect, it } from 'vitest'

import { jsonResponse, stubFetch } from '../test/query'
import { api, ApiError, unwrap } from './client'

describe('unwrap', () => {
  it('returns the data of a successful call', async () => {
    stubFetch(jsonResponse([{ id: '1', name: 'Comida' }]))

    const categories = await unwrap(api.GET('/api/v1/categories'))

    expect(categories).toEqual([{ id: '1', name: 'Comida' }])
  })

  it("throws an ApiError with FastAPI's detail", async () => {
    stubFetch(jsonResponse({ detail: 'Movement 123 not found' }, 404))

    const call = unwrap(api.GET('/api/v1/movements'))

    await expect(call).rejects.toThrow(ApiError)
    await expect(call).rejects.toMatchObject({
      status: 404,
      message: 'Movement 123 not found',
      detail: 'Movement 123 not found',
    })
  })

  it('joins the messages of a validation error', async () => {
    stubFetch(
      jsonResponse(
        {
          detail: [
            {
              loc: ['body', 'amount'],
              msg: 'Input should be greater than 0',
              type: 'greater_than',
            },
            { loc: ['body', 'type'], msg: 'Field required', type: 'missing' },
          ],
        },
        422,
      ),
    )

    await expect(unwrap(api.GET('/api/v1/movements'))).rejects.toMatchObject({
      status: 422,
      message: 'Input should be greater than 0; Field required',
    })
  })

  it('falls back to the status when there is no detail', async () => {
    stubFetch(new Response('Bad gateway', { status: 502 }))

    await expect(unwrap(api.GET('/api/v1/summary'))).rejects.toMatchObject({
      status: 502,
      message: 'Request failed with status 502',
    })
  })
})
