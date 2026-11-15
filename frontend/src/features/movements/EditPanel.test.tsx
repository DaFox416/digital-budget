import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import App from '../../App'
import { homeRoutes, movements } from '../../test/fixtures'
import { jsonResponse, queryWrapper, stubApi } from '../../test/query'

const cine = movements[0]

function renderApp() {
  render(<App />, { wrapper: queryWrapper() })
}

async function openRow(name: RegExp) {
  await userEvent.click(await screen.findByRole('button', { name }))
  return screen.getByRole('dialog')
}

function requestsTo(mock: ReturnType<typeof stubApi>['mock'], method: string, path: string) {
  return mock.mock.calls
    .map(([request]) => request)
    .filter((request) => request.method === method && new URL(request.url).pathname === path)
}

/** The list without Cine once it's deleted, and with it again once restored. */
function deletableCine() {
  const api = stubApi({
    ...homeRoutes,
    'DELETE /api/v1/movements/cine': () => {
      api.routes['/api/v1/movements'] = movements.slice(1)
      return Promise.resolve(new Response(null, { status: 204 }))
    },
  })
  return api
}

describe('Edit panel', () => {
  it('edits an expense, sending only what changed, and closes', async () => {
    const { mock } = stubApi({ ...homeRoutes, 'PATCH /api/v1/movements/cine': cine })
    renderApp()

    const panel = await openRow(/Cine/)
    expect(within(panel).getByText('Gasto · BBVA')).toBeInTheDocument()
    const amount = within(panel).getByLabelText('Monto')
    expect(amount).toHaveValue('387.56')
    await userEvent.clear(amount)
    await userEvent.type(amount, '400{Control>}{Enter}{/Control}')

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
    const [patch] = requestsTo(mock, 'PATCH', '/api/v1/movements/cine')
    expect(await patch.json()).toEqual({ amount: '400' })
  })

  it('in savings mode, a new amount sends the suggested accounting amount', async () => {
    const { mock } = stubApi({
      ...homeRoutes,
      '/api/v1/preferences': { mode: 'savings', rounding_multiple: 10 },
      'POST /api/v1/movements/preview': {
        ...homeRoutes['POST /api/v1/movements/preview'],
        suggested_accounting_amount: '400.00',
      },
      'PATCH /api/v1/movements/cine': cine,
    })
    renderApp()

    const panel = await openRow(/Cine/)
    const accounting = within(panel).getByLabelText(/Contable/)
    // The stored one until the amount changes
    expect(accounting).toHaveValue('387.56')
    const amount = within(panel).getByLabelText('Monto')
    await userEvent.clear(amount)
    await userEvent.type(amount, '395{Enter}')
    await waitFor(() => {
      expect(accounting).toHaveValue('400.00')
    })
    await userEvent.click(within(panel).getByRole('button', { name: /Guardar cambios/ }))

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
    const [patch] = requestsTo(mock, 'PATCH', '/api/v1/movements/cine')
    expect(await patch.json()).toEqual({ amount: '395', accounting_amount: '400.00' })
  })

  it('deletes at once and undoes from the notice', async () => {
    const { mock, routes } = deletableCine()
    routes['POST /api/v1/movements/cine/restore'] = () => {
      routes['/api/v1/movements'] = movements
      return Promise.resolve(jsonResponse(cine))
    }
    renderApp()

    const panel = await openRow(/Cine/)
    await userEvent.click(within(panel).getByRole('button', { name: 'Borrar movimiento' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Cine/ })).not.toBeInTheDocument()
    const notice = screen.getByRole('status')
    expect(notice).toHaveTextContent('Movimiento borrado')

    await userEvent.click(await within(notice).findByRole('button', { name: 'Deshacer' }))

    expect(await screen.findByRole('button', { name: /Cine/ })).toBeInTheDocument()
    expect(requestsTo(mock, 'POST', '/api/v1/movements/cine/restore')).toHaveLength(1)
    expect(screen.queryByText('Movimiento borrado')).not.toBeInTheDocument()
  })

  it('explains how to fix it by hand when the card limit refuses the undo', async () => {
    const { routes } = deletableCine()
    routes['POST /api/v1/movements/cine/restore'] = jsonResponse(
      {
        detail:
          "Restoring this purchase would go over the card's available credit by $250.00. To fix it by hand: ...",
      },
      409,
    )
    renderApp()

    const panel = await openRow(/Cine/)
    await userEvent.click(within(panel).getByRole('button', { name: 'Borrar movimiento' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Deshacer' }))

    const steps = await screen.findByRole('alert')
    expect(steps).toHaveTextContent('se pasa por $250.00')
    expect(steps).toHaveTextContent('1. Borra las compras posteriores')
    // It stays until closed
    await userEvent.click(screen.getByRole('button', { name: 'Cerrar' }))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('shows an MSI purchase read-only, with only the delete button', async () => {
    const laptop = {
      ...cine,
      id: 'laptop',
      account_id: 'tdc-oro',
      real_amount: '-12000.00',
      accounting_amount: '0.00',
      description: 'Laptop',
      installment_plan_id: 'plan-laptop',
    }
    stubApi({ ...homeRoutes, '/api/v1/movements': [laptop] })
    renderApp()

    const panel = await openRow(/Laptop/)

    expect(panel).toHaveAccessibleName('Compra a MSI')
    expect(within(panel).getByText('$12,000.00')).toBeInTheDocument()
    expect(within(panel).getByText(/todavía no se editan/)).toBeInTheDocument()
    expect(within(panel).queryByRole('textbox')).not.toBeInTheDocument()
    expect(within(panel).getByRole('button', { name: 'Borrar movimiento' })).toBeInTheDocument()
  })
})
