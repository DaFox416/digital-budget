import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import App from '../App'
import { todayInMexico } from '../lib/dates'
import { homeRoutes, movements } from '../test/fixtures'
import { jsonResponse, queryWrapper, stubApi } from '../test/query'

function renderApp() {
  render(<App />, { wrapper: queryWrapper() })
}

async function openPanel() {
  await userEvent.click(screen.getByRole('button', { name: /Nuevo/ }))
  const panel = screen.getByRole('dialog', { name: 'Nuevo movimiento' })
  // The form shows once the accounts load
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
  it('opens with N, with the amount focused and empty, and closes with Esc', async () => {
    stubApi(homeRoutes)
    renderApp()

    await userEvent.keyboard('n')

    const panel = screen.getByRole('dialog', { name: 'Nuevo movimiento' })
    const amount = await within(panel).findByLabelText('Monto')
    expect(amount).toHaveFocus()
    expect(amount).toHaveValue('')

    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('saves an expense with Enter and stays ready for the next one', async () => {
    const { mock } = stubApi({ ...homeRoutes, 'POST /api/v1/movements': movements[0] })
    renderApp()
    const panel = await openPanel()

    await userEvent.type(within(panel).getByLabelText('Monto'), '1,234.5')
    await userEvent.selectOptions(within(panel).getByLabelText('Cuenta'), 'TDC Oro')
    await userEvent.selectOptions(within(panel).getByLabelText('Categoría'), 'Comida')
    await userEvent.type(within(panel).getByLabelText('Descripción'), 'Cine{Enter}')

    expect(await within(panel).findByRole('status')).toHaveTextContent('Guardado')
    expect(await posted(mock, '/api/v1/movements')).toEqual([
      {
        account_id: 'tdc-oro',
        type: 'expense',
        amount: '1234.5',
        occurred_on: todayInMexico(),
        description: 'Cine',
        category_id: 'comida',
      },
    ])
    // Amount and description clear; account and category stay, and the account is remembered
    expect(within(panel).getByLabelText('Monto')).toHaveValue('')
    expect(within(panel).getByLabelText('Monto')).toHaveFocus()
    expect(within(panel).getByLabelText('Descripción')).toHaveValue('')
    expect(within(panel).getByLabelText('Cuenta')).toHaveValue('tdc-oro')
    expect(localStorage.getItem('capture.lastAccountId')).toBe('tdc-oro')
  })

  it('pays a card from a debit account, offering only cards as destination', async () => {
    const { mock } = stubApi({ ...homeRoutes, 'POST /api/v1/transfers': {} })
    renderApp()
    const panel = await openPanel()

    await userEvent.click(within(panel).getByRole('tab', { name: 'Pago de tarjeta' }))
    expect(optionNames(within(panel).getByLabelText('Desde'))).toEqual(['BBVA'])
    expect(optionNames(within(panel).getByLabelText('Tarjeta'))).toEqual(['TDC Oro'])
    await userEvent.type(within(panel).getByLabelText('Monto'), '634{Enter}')

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

  it("doesn't send an invalid amount", async () => {
    const { mock } = stubApi(homeRoutes)
    renderApp()
    const panel = await openPanel()

    await userEvent.type(within(panel).getByLabelText('Monto'), '12.345{Enter}')

    expect(within(panel).getByRole('alert')).toHaveTextContent('hasta 2 decimales')
    expect(await posted(mock, '/api/v1/movements')).toEqual([])
  })

  it('shows the API error and keeps what was typed', async () => {
    stubApi({
      ...homeRoutes,
      'POST /api/v1/movements': jsonResponse({ detail: 'Category not found' }, 404),
    })
    renderApp()
    const panel = await openPanel()

    await userEvent.type(within(panel).getByLabelText('Monto'), '90{Enter}')

    expect(await within(panel).findByRole('alert')).toHaveTextContent('Category not found')
    expect(within(panel).getByLabelText('Monto')).toHaveValue('90')
  })
})
