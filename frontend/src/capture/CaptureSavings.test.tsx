import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import App from '../App'
import type { MovementPreview } from '../api/types'
import { homeRoutes, movements } from '../test/fixtures'
import { jsonResponse, queryWrapper, stubApi } from '../test/query'

// Savings mode, multiple of 10, with the Luz commitment pending
const savingsRoutes = {
  ...homeRoutes,
  '/api/v1/preferences': { mode: 'savings', rounding_multiple: 10 },
  '/api/v1/commitments': [
    { id: 'luz', name: 'Luz', amount: '500.00', expected_on: null, paid_by_movement_id: null },
  ],
}

function previewReply(fields: Partial<MovementPreview>): MovementPreview {
  return {
    suggested_accounting_amount: null,
    first_installment: null,
    warning: null,
    credit_limit_excess: null,
    ...fields,
  }
}

async function openPanel() {
  render(<App />, { wrapper: queryWrapper() })
  await userEvent.keyboard('n')
  const panel = screen.getByRole('dialog', { name: 'Nuevo movimiento' })
  await within(panel).findByLabelText('Monto')
  return panel
}

async function posted(mock: ReturnType<typeof stubApi>['mock'], path: string) {
  const requests = mock.mock.calls
    .map(([request]) => request)
    .filter((request) => request.method === 'POST' && new URL(request.url).pathname === path)
  return Promise.all(requests.map((request) => request.clone().json() as Promise<unknown>))
}

beforeEach(() => {
  localStorage.clear()
})

describe('Capture in savings mode', () => {
  it('prefills the suggested accounting amount and sends it', async () => {
    const { mock } = stubApi({
      ...savingsRoutes,
      'POST /api/v1/movements/preview': previewReply({ suggested_accounting_amount: '390.00' }),
      'POST /api/v1/movements': movements[0],
    })
    const panel = await openPanel()

    await userEvent.keyboard('{Enter}387.56')

    const accounting = within(panel).getByLabelText(/Contable/)
    expect(await within(panel).findByDisplayValue('390.00')).toBe(accounting)
    await userEvent.click(within(panel).getByRole('button', { name: /Guardar/ }))

    expect(await within(panel).findByRole('status')).toHaveTextContent('Guardado')
    const [body] = await posted(mock, '/api/v1/movements')
    expect(body).toMatchObject({ amount: '387.56', accounting_amount: '390.00' })
  })

  it('stops following the suggestion once the accounting amount is typed by hand', async () => {
    const { mock } = stubApi({
      ...savingsRoutes,
      'POST /api/v1/movements/preview': previewReply({ suggested_accounting_amount: '390.00' }),
      'POST /api/v1/movements': movements[0],
    })
    const panel = await openPanel()

    await userEvent.keyboard('{Enter}387.56')
    const accounting = within(panel).getByLabelText(/Contable/)
    await within(panel).findByDisplayValue('390.00')
    await userEvent.clear(accounting)
    await userEvent.type(accounting, '400')
    await userEvent.click(within(panel).getByRole('button', { name: /Guardar/ }))

    expect(await within(panel).findByRole('status')).toHaveTextContent('Guardado')
    const [body] = await posted(mock, '/api/v1/movements')
    expect(body).toMatchObject({ accounting_amount: '400' })
  })

  it('pays a commitment chosen in the list', async () => {
    const { mock } = stubApi({ ...savingsRoutes, 'POST /api/v1/movements': movements[0] })
    const panel = await openPanel()

    await userEvent.keyboard('{Enter}487')
    await userEvent.selectOptions(within(panel).getByLabelText('Paga un apartado'), 'luz')
    await userEvent.click(within(panel).getByRole('button', { name: /Guardar/ }))

    expect(await within(panel).findByRole('status')).toHaveTextContent('Guardado')
    const [body] = await posted(mock, '/api/v1/movements')
    expect(body).toMatchObject({ amount: '487', commitment_id: 'luz' })
  })

  it('shows level 1 in yellow and saves on the first try', async () => {
    const { mock } = stubApi({
      ...savingsRoutes,
      'POST /api/v1/movements/preview': previewReply({
        suggested_accounting_amount: '4000.00',
        warning: { level: 'over_available', excess: '540.00' },
      }),
      'POST /api/v1/movements': movements[0],
    })
    const panel = await openPanel()

    await userEvent.keyboard('{Enter}3990')
    await userEvent.selectOptions(within(panel).getByLabelText('Cuenta'), 'TDC Oro')

    expect(await within(panel).findByText(/supera tu disponible por \$540\.00/)).toBeVisible()
    await userEvent.click(within(panel).getByRole('button', { name: /Guardar/ }))
    expect(await within(panel).findByRole('status')).toHaveTextContent('Guardado')
    expect(await posted(mock, '/api/v1/movements')).toHaveLength(1)
  })
})

describe('Capture warnings and MSI', () => {
  it('asks once more before saving over the real balance, also in simple mode', async () => {
    const { mock } = stubApi({
      ...homeRoutes,
      'POST /api/v1/movements/preview': previewReply({
        warning: { level: 'over_real_balance', excess: '919.33' },
      }),
      'POST /api/v1/movements': movements[0],
    })
    const panel = await openPanel()

    await userEvent.keyboard('{Enter}15000{Enter}')
    await userEvent.selectOptions(within(panel).getByLabelText('Cuenta'), 'TDC Oro')
    expect(await within(panel).findByText(/supera tu saldo real por \$919\.33/)).toBeVisible()

    // Ctrl+Enter, then Enter on the unreviewed notice: level 2 stops it once
    await userEvent.keyboard('{Control>}{Enter}{/Control}{Enter}')
    const confirm = await within(panel).findByRole('button', { name: /Guardar de todos modos/ })
    expect(confirm).toHaveFocus()
    expect(await posted(mock, '/api/v1/movements')).toEqual([])

    await userEvent.keyboard('{Enter}')
    expect(await within(panel).findByRole('status')).toHaveTextContent('Guardado')
    expect(await posted(mock, '/api/v1/movements')).toHaveLength(1)
  })

  it("never saves a card purchase over the card's available credit", async () => {
    const { mock } = stubApi({
      ...homeRoutes,
      'POST /api/v1/movements/preview': previewReply({ credit_limit_excess: '250.00' }),
      'POST /api/v1/movements': movements[0],
    })
    const panel = await openPanel()

    await userEvent.keyboard('{Enter}15000{Enter}')
    await userEvent.selectOptions(within(panel).getByLabelText('Cuenta'), 'TDC Oro')
    expect(
      await within(panel).findByText(/supera el crédito disponible de la tarjeta por \$250\.00/),
    ).toBeVisible()
    expect(within(panel).getByRole('button', { name: /^Guardar/ })).toBeDisabled()

    // Neither Ctrl+Enter (and Enter on the notice) saves it: back to the amount
    await userEvent.keyboard('{Control>}{Enter}{/Control}{Enter}')
    expect(within(panel).getByLabelText('Monto')).toHaveFocus()
    expect(await posted(mock, '/api/v1/movements')).toEqual([])
  })

  it('saves a card purchase in installments as an MSI plan', async () => {
    const { mock } = stubApi({
      ...homeRoutes,
      'POST /api/v1/movements/preview': previewReply({
        first_installment: { amount: '333.33', accounting_amount: '333.33' },
      }),
      'POST /api/v1/installment-plans': jsonResponse({}, 201),
    })
    const panel = await openPanel()

    await userEvent.keyboard('{Enter}1000')
    await userEvent.selectOptions(within(panel).getByLabelText('Cuenta'), 'TDC Oro')
    await userEvent.click(within(panel).getByRole('button', { name: '3' }))

    expect(await within(panel).findByText(/la primera de \$333\.33/)).toBeVisible()
    await userEvent.click(within(panel).getByRole('button', { name: /Guardar/ }))

    expect(await within(panel).findByRole('status')).toHaveTextContent('Guardado')
    expect(await posted(mock, '/api/v1/installment-plans')).toEqual([
      expect.objectContaining({ account_id: 'tdc-oro', total: '1000', months: 3 }),
    ])
    expect(await posted(mock, '/api/v1/movements')).toEqual([])
  })

  it('shows the new row right away, marked as saving, before the API answers', async () => {
    let answer: (response: Response) => void = () => undefined
    stubApi({
      ...homeRoutes,
      'POST /api/v1/movements': () =>
        new Promise<Response>((resolve) => {
          answer = resolve
        }),
    })
    const panel = await openPanel()
    await screen.findByText('Cine')

    await userEvent.keyboard('{Enter}90')
    await userEvent.click(within(panel).getByLabelText('Descripción'))
    await userEvent.keyboard('Tacos{Enter}')

    const list = screen.getByRole('region', { name: 'Movimientos' })
    const row = (await within(list).findByText('Tacos')).closest('li')
    expect(row).toHaveAttribute('aria-busy', 'true')
    expect(row).toHaveTextContent('Guardando…')

    answer(jsonResponse(movements[0], 201))
    expect(await within(panel).findByRole('status')).toHaveTextContent('Guardado')
  })
})
