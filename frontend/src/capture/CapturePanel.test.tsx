import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import App from '../App'
import { todayInMexico } from '../lib/dates'
import { homeRoutes, movements } from '../test/fixtures'
import { jsonResponse, queryWrapper, stubApi } from '../test/query'

const CTRL_ENTER = '{Control>}{Enter}{/Control}'

function renderApp() {
  render(<App />, { wrapper: queryWrapper() })
}

/** Open with N and wait for the form, which shows once the accounts load. */
async function openPanel() {
  await userEvent.keyboard('n')
  const panel = screen.getByRole('dialog', { name: 'Nuevo movimiento' })
  await within(panel).findByLabelText('Monto')
  return panel
}

/** Bodies of the POST requests the stubbed API got, by path. */
async function posted(mock: ReturnType<typeof stubApi>['mock'], path: string) {
  const requests = mock.mock.calls
    .map(([request]) => request)
    .filter((request) => request.method === 'POST' && new URL(request.url).pathname === path)
  return Promise.all(requests.map((request) => request.clone().json() as Promise<unknown>))
}

function optionNames(select: HTMLElement): string[] {
  return within(select)
    .getAllByRole('option')
    .map((option) => option.textContent)
}

beforeEach(() => {
  localStorage.clear()
})

describe('Capture panel', () => {
  it('opens with N on Gasto, with the focus on the tabs, and closes with Esc', async () => {
    stubApi(homeRoutes)
    renderApp()

    const panel = await openPanel()

    const expense = within(panel).getByRole('tab', { name: 'Gasto' })
    expect(expense).toHaveAttribute('aria-selected', 'true')
    expect(expense).toHaveFocus()

    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('picks the type with the arrows, without wrapping around, and Enter goes to the amount', async () => {
    stubApi(homeRoutes)
    renderApp()
    const panel = await openPanel()

    await userEvent.keyboard('{ArrowLeft}')
    expect(within(panel).getByRole('tab', { name: 'Gasto' })).toHaveFocus()
    await userEvent.keyboard('{ArrowRight}{ArrowRight}')
    expect(within(panel).getByRole('tab', { name: 'Transferencia' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    await userEvent.keyboard('{ArrowRight}{ArrowRight}{ArrowRight}')
    expect(within(panel).getByRole('tab', { name: 'Pago de tarjeta' })).toHaveFocus()

    await userEvent.keyboard('{Enter}')
    expect(within(panel).getByLabelText('Monto')).toHaveFocus()
  })

  it('walks the fields with Enter, saves on the last one and starts over on Gasto', async () => {
    const { mock } = stubApi({ ...homeRoutes, 'POST /api/v1/movements': movements[0] })
    renderApp()
    const panel = await openPanel()

    await userEvent.keyboard('{Enter}387.56{Enter}')
    const account = within(panel).getByLabelText('Cuenta')
    expect(account).toHaveFocus()
    await userEvent.selectOptions(account, 'TDC Oro')
    // A card expense can be in installments: that field comes next, on Sin MSI
    await userEvent.keyboard('{Enter}')
    expect(within(panel).getByRole('radio', { name: 'Sin MSI' })).toHaveFocus()
    await userEvent.keyboard('{Enter}')
    await userEvent.selectOptions(within(panel).getByLabelText('Categoría'), 'Comida')
    await userEvent.keyboard('{Enter}{Enter}')
    expect(within(panel).getByLabelText('Descripción')).toHaveFocus()
    await userEvent.keyboard('Cine{Enter}')

    expect(await within(panel).findByRole('status')).toHaveTextContent('Guardado')
    expect(await posted(mock, '/api/v1/movements')).toEqual([
      {
        account_id: 'tdc-oro',
        type: 'expense',
        amount: '387.56',
        occurred_on: todayInMexico(),
        description: 'Cine',
        category_id: 'comida',
        // Simple mode: the API takes the amount as accounting
        accounting_amount: null,
        commitment_id: null,
      },
    ])
    // Starts over: Gasto with the focus on the tabs, empty fields, the last account remembered
    expect(within(panel).getByRole('tab', { name: 'Gasto' })).toHaveFocus()
    expect(within(panel).getByLabelText('Monto')).toHaveValue('')
    expect(within(panel).getByLabelText('Categoría')).toHaveValue('')
    expect(within(panel).getByLabelText('Cuenta')).toHaveValue('tdc-oro')
  })

  it('asks before saving with Ctrl+Enter while fields are left to review', async () => {
    const { mock } = stubApi({ ...homeRoutes, 'POST /api/v1/movements': movements[0] })
    renderApp()
    const panel = await openPanel()

    await userEvent.keyboard(`{Enter}90${CTRL_ENTER}`)
    const notice = within(panel).getByRole('alertdialog')
    expect(notice).toHaveTextContent('Cuenta: BBVA · Sin categoría · Fecha: hoy · Sin descripción')

    // Esc goes back to the field, without closing the panel or saving
    await userEvent.keyboard('{Escape}')
    expect(within(panel).queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(within(panel).getByLabelText('Monto')).toHaveFocus()
    expect(await posted(mock, '/api/v1/movements')).toEqual([])

    await userEvent.keyboard(`${CTRL_ENTER}{Enter}`)
    expect(await within(panel).findByRole('status')).toHaveTextContent('Guardado')
    expect(await posted(mock, '/api/v1/movements')).toHaveLength(1)
  })

  it('saves right away with Ctrl+Enter on the last field', async () => {
    const { mock } = stubApi({ ...homeRoutes, 'POST /api/v1/movements': movements[0] })
    renderApp()
    const panel = await openPanel()

    await userEvent.keyboard('{Enter}90')
    await userEvent.click(within(panel).getByLabelText('Descripción'))
    await userEvent.keyboard(`Tacos${CTRL_ENTER}`)

    expect(await within(panel).findByRole('status')).toHaveTextContent('Guardado')
    expect(within(panel).queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(await posted(mock, '/api/v1/movements')).toHaveLength(1)
  })

  it('pays a card from a debit account, offering only cards as destination', async () => {
    const { mock } = stubApi({ ...homeRoutes, 'POST /api/v1/transfers': {} })
    renderApp()
    const panel = await openPanel()

    await userEvent.keyboard('{ArrowRight}{ArrowRight}{ArrowRight}')
    expect(optionNames(within(panel).getByLabelText('Desde'))).toEqual(['BBVA'])
    expect(optionNames(within(panel).getByLabelText('Tarjeta'))).toEqual(['TDC Oro'])
    await userEvent.click(within(panel).getByRole('button', { name: /Guardar/ }))
    expect(within(panel).getByRole('alert')).toHaveTextContent('Escribe un monto')

    await userEvent.type(within(panel).getByLabelText('Monto'), '634')
    await userEvent.click(within(panel).getByRole('button', { name: /Guardar/ }))

    expect(await within(panel).findByRole('status')).toHaveTextContent('Guardado')
    expect(await posted(mock, '/api/v1/transfers')).toEqual([
      {
        source_account_id: 'bbva',
        destination_account_id: 'tdc-oro',
        amount: '634',
        occurred_on: todayInMexico(),
        description: '',
      },
    ])
  })

  it("doesn't send an invalid amount, and Ctrl+Enter goes back to it", async () => {
    const { mock } = stubApi(homeRoutes)
    renderApp()
    const panel = await openPanel()

    await userEvent.keyboard('{Enter}12.345{Enter}')
    await userEvent.keyboard(CTRL_ENTER)

    expect(within(panel).getByRole('alert')).toHaveTextContent('hasta 2 decimales')
    expect(within(panel).queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(within(panel).getByLabelText('Monto')).toHaveFocus()
    expect(await posted(mock, '/api/v1/movements')).toEqual([])
  })

  it('shows the API error and keeps what was typed', async () => {
    stubApi({
      ...homeRoutes,
      'POST /api/v1/movements': jsonResponse({ detail: 'Category not found' }, 404),
    })
    renderApp()
    const panel = await openPanel()

    await userEvent.keyboard('{Enter}90')
    await userEvent.click(within(panel).getByRole('button', { name: /Guardar/ }))

    expect(await within(panel).findByRole('alert')).toHaveTextContent('Category not found')
    expect(within(panel).getByLabelText('Monto')).toHaveValue('90')
  })
})
