import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import App from './App'
import { homeRoutes, summary, tdcOroSummary } from './test/fixtures'
import { jsonResponse, queryWrapper, stubApi } from './test/query'

function renderApp() {
  render(<App />, { wrapper: queryWrapper() })
}

describe('Summary', () => {
  it('shows the main figures, without "available" in simple mode', async () => {
    stubApi(homeRoutes)

    renderApp()

    const section = await screen.findByRole('region', { name: 'Resumen' })
    expect(await within(section).findByText('$14,777.11')).toBeInTheDocument()
    expect(within(section).getByText('$12,634.00')).toBeInTheDocument()
    expect(within(section).getByText('$10,000.00')).toBeInTheDocument()
    expect(within(section).queryByText('Disponible')).not.toBeInTheDocument()
    expect(within(section).queryByLabelText('Detalle del disponible')).not.toBeInTheDocument()
  })

  it('adds "available" and the savings detail in savings mode', async () => {
    stubApi({
      ...homeRoutes,
      '/api/v1/preferences': { mode: 'savings', rounding_multiple: 10 },
      '/api/v1/summary': { ...summary, set_aside: '500.00', available: '11500.00' },
    })

    renderApp()

    const section = await screen.findByRole('region', { name: 'Resumen' })
    expect(await within(section).findByText('Disponible')).toBeInTheDocument()
    expect(within(section).getByText('$11,500.00')).toBeInTheDocument()
    const detail = within(section).getByLabelText('Detalle del disponible')
    expect(detail).toHaveTextContent('Apartado:$500.00')
    expect(detail).toHaveTextContent('Ahorros con meta:$0.00')
    expect(detail).toHaveTextContent('Sobrante:$143.11(puedes liberar $140.00)')
  })

  it('keeps the other sections when the summary fails, and retries', async () => {
    const { routes } = stubApi({
      ...homeRoutes,
      '/api/v1/summary': jsonResponse({ detail: 'Database is down' }, 500),
    })
    renderApp()

    const section = screen.getByRole('region', { name: 'Resumen' })
    expect(await within(section).findByRole('alert')).toHaveTextContent('Database is down')
    // Accounts and movements still show
    expect(await screen.findByRole('article', { name: 'BBVA' })).toBeInTheDocument()
    expect(await screen.findByText('Cine')).toBeInTheDocument()

    routes['/api/v1/summary'] = summary
    await userEvent.click(within(section).getByRole('button', { name: 'Reintentar' }))

    expect(await within(section).findByText('$14,777.11')).toBeInTheDocument()
  })
})

describe('Accounts', () => {
  it('shows debit balance and the card debt, available credit and next payment', async () => {
    stubApi(homeRoutes)

    renderApp()

    const bbva = await screen.findByRole('article', { name: 'BBVA' })
    expect(within(bbva).getByText('$14,777.11')).toBeInTheDocument()

    const card = screen.getByRole('article', { name: 'TDC Oro' })
    expect(await within(card).findByText('Debes')).toBeInTheDocument()
    expect(within(card).getByText('$12,634.00')).toBeInTheDocument()
    expect(within(card).getByText('$7,366.00')).toBeInTheDocument()
    expect(within(card).getByText('Pagar antes del 5 dic')).toBeInTheDocument()
    expect(within(card).getByText('$1,634.00')).toBeInTheDocument()
  })

  it('shows what was charged so far when the last statement is past due', async () => {
    stubApi({
      ...homeRoutes,
      '/api/v1/summary': {
        ...summary,
        cards: [
          {
            ...tdcOroSummary,
            next_payment: {
              cutoff: '2026-12-15',
              payment_due: '2027-01-05',
              amount: '1200.00',
              is_closed: false,
              days_until_due: 26,
            },
          },
        ],
      },
    })

    renderApp()

    const tdc = await screen.findByRole('article', { name: 'TDC Oro' })
    expect(await within(tdc).findByText('Llevas · corte 15 dic')).toBeInTheDocument()
    expect(within(tdc).getByText('$1,200.00')).toBeInTheDocument()
  })

  it('says how to add accounts when there are none', async () => {
    stubApi({ ...homeRoutes, '/api/v1/accounts': [] })

    renderApp()

    expect(await screen.findByText(/Aún no tienes cuentas/)).toBeInTheDocument()
  })
})

describe('Movements', () => {
  it('groups by day and shows a card payment as one row', async () => {
    stubApi(homeRoutes)

    renderApp()

    const today = await screen.findByRole('region', { name: 'vie 20 de nov' })
    const rows = within(today).getAllByRole('listitem')
    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveTextContent('Cine')
    expect(rows[0]).toHaveTextContent('-$387.56')
    expect(rows[1]).toHaveTextContent('Pago de tarjeta')
    expect(await within(today).findByText('BBVA → TDC Oro')).toBeInTheDocument()
    expect(rows[1]).toHaveTextContent('$634.00')

    const yesterday = screen.getByRole('region', { name: 'jue 19 de nov' })
    expect(within(yesterday).getByText('+$10,164.67')).toBeInTheDocument()
  })
})

describe('New movement button for phones', () => {
  it('opens the capture panel and hides while it is open', async () => {
    stubApi(homeRoutes)
    renderApp()

    await userEvent.click(screen.getByRole('button', { name: 'Nuevo movimiento' }))

    expect(await screen.findByRole('dialog', { name: 'Nuevo movimiento' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Nuevo movimiento' })).not.toBeInTheDocument()
  })
})

describe('Card detail', () => {
  it('opens from the card with what to pay, its statement and active MSI, and closes with Esc', async () => {
    stubApi({
      ...homeRoutes,
      '/api/v1/cards/tdc-oro/statement': {
        account_id: 'tdc-oro',
        start: '2026-10-16',
        cutoff: '2026-11-15',
        payment_due: '2026-12-05',
        regular_charges: '634.00',
        installments_due: '1000.00',
        installments: [],
        payments_after_cutoff: '0.00',
        payment_for_no_interest: '1634.00',
      },
      '/api/v1/cards/tdc-oro/installment-plans': [
        {
          plan_id: 'laptop',
          description: 'Laptop',
          purchased_on: '2026-11-10',
          total: '12000.00',
          months: 12,
          installment_amount: '1000.00',
          billed: 1,
          remaining: '11000.00',
          next_cutoff: '2026-12-15',
        },
      ],
    })
    renderApp()

    const card = await screen.findByRole('article', { name: 'TDC Oro' })
    await userEvent.click(within(card).getByRole('button', { name: /Ver detalle/ }))

    const panel = await screen.findByRole('dialog', { name: 'TDC Oro' })
    const toPay = within(panel).getByRole('region', { name: 'Por pagar' })
    expect(await within(toPay).findByText('$1,634.00')).toBeVisible()
    expect(toPay).toHaveTextContent('Pagar antes del 5 dic')
    expect(toPay).toHaveTextContent('vence en 15 días')

    const statement = within(panel).getByRole('region', { name: 'Estado de cuenta' })
    expect(await within(statement).findByText('Del 16 oct al 15 nov')).toBeVisible()
    expect(statement).toHaveTextContent('Mensualidades MSI$1,000.00')

    const plans = within(panel).getByRole('region', { name: 'MSI activos' })
    expect(await within(plans).findByText('Laptop')).toBeVisible()
    expect(plans).toHaveTextContent('1 de 12 facturadas · siguiente corte 15 dic')
    expect(plans).toHaveTextContent('faltan $11,000.00')

    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
