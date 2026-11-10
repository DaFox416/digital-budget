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
  it('shows the main figures', async () => {
    stubApi(homeRoutes)

    renderApp()

    const section = await screen.findByRole('region', { name: 'Resumen' })
    expect(await within(section).findByText('$14,777.11')).toBeInTheDocument()
    expect(within(section).getByText('$12,634.00')).toBeInTheDocument()
    expect(within(section).getByText('$10,000.00')).toBeInTheDocument()
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
