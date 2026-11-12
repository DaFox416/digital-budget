import { useAccounts, useCardPlans, useStatement, useSummary } from '../../api/queries'
import type { ActiveInstallmentPlan, CardSummary } from '../../api/types'
import { formatShortDate } from '../../lib/dates'
import { Money } from '../../ui/Money'
import { EmptyState, ErrorState, LoadingState } from '../../ui/Section'

/** "vence hoy", "vence mañana", "vence en 12 días". */
function dueText(days: number): string {
  if (days <= 0) return 'vence hoy'
  if (days === 1) return 'vence mañana'
  return `vence en ${String(days)} días`
}

const blockClass = 'rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200'
const blockTitle = 'mb-2 text-sm font-semibold tracking-wide text-slate-500 uppercase'

/**
 * A credit card's detail: what to pay and by when, its statement and active MSI purchases.
 * Every amount and date comes from the API: the frontend does no math with money.
 */
export function CardDetail({ accountId }: { accountId: string }) {
  const accounts = useAccounts()
  const summary = useSummary()
  const account = accounts.data?.find((item) => item.id === accountId)
  const card = summary.data?.cards.find((item) => item.account_id === accountId)

  return (
    <div className="space-y-4">
      {account?.credit && (
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div className={blockClass}>
            <dt className="text-slate-500">Debes</dt>
            <dd className="mt-1 text-lg font-semibold text-slate-900">
              <Money amount={card?.debt ?? '0.00'} />
            </dd>
          </div>
          <div className={blockClass}>
            <dt className="text-slate-500">Crédito disponible</dt>
            <dd className="mt-1 text-lg font-semibold text-slate-900">
              <Money amount={account.credit.available} />
            </dd>
            <dd className="text-xs text-slate-400">
              de <Money amount={account.credit.credit_limit} />
            </dd>
          </div>
        </dl>
      )}

      <section aria-label="Por pagar" className={blockClass}>
        <h3 className={blockTitle}>Por pagar</h3>
        {summary.isPending ? (
          <LoadingState />
        ) : summary.isError ? (
          <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />
        ) : card ? (
          <NextPayment card={card} />
        ) : (
          <EmptyState>No se encontró la tarjeta.</EmptyState>
        )}
      </section>

      {card && <StatementBreakdown accountId={accountId} cutoff={card.next_payment.cutoff} />}

      <ActivePlans accountId={accountId} />
    </div>
  )
}

function NextPayment({ card }: { card: CardSummary }) {
  const payment = card.next_payment
  const days = payment.days_until_due
  // Three days or less: time to pay
  const urgent = days <= 3
  return (
    <div>
      <p className="text-3xl font-semibold text-slate-900">
        <Money amount={payment.amount} />
      </p>
      <p className="mt-1 text-sm text-slate-600">
        {payment.is_closed
          ? `Pagar antes del ${formatShortDate(payment.payment_due)}`
          : `Llevas en el ciclo que cierra el ${formatShortDate(payment.cutoff)}; se paga el ${formatShortDate(payment.payment_due)}`}
      </p>
      <p
        className={`mt-2 inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
          urgent ? 'bg-rose-100 text-rose-800' : 'bg-slate-100 text-slate-600'
        }`}
      >
        {dueText(days)}
      </p>
    </div>
  )
}

function StatementBreakdown({ accountId, cutoff }: { accountId: string; cutoff: string }) {
  const statement = useStatement(accountId, cutoff)

  return (
    <section aria-label="Estado de cuenta" className={blockClass}>
      <h3 className={blockTitle}>Estado de cuenta</h3>
      {statement.isPending ? (
        <LoadingState />
      ) : statement.isError ? (
        <ErrorState error={statement.error} onRetry={() => void statement.refetch()} />
      ) : (
        <>
          <p className="mb-2 text-xs text-slate-400">
            Del {formatShortDate(statement.data.start)} al {formatShortDate(statement.data.cutoff)}
          </p>
          <dl className="space-y-1 text-sm">
            <Row label="Cargos del ciclo" amount={statement.data.regular_charges} />
            <Row label="Mensualidades MSI" amount={statement.data.installments_due} />
            <Row
              label="Pagos después del corte"
              amount={statement.data.payments_after_cutoff}
              minus
            />
            <div className="flex justify-between gap-3 border-t border-slate-100 pt-2 font-medium text-slate-900">
              <dt>Pago para no generar intereses</dt>
              <dd>
                <Money amount={statement.data.payment_for_no_interest} />
              </dd>
            </div>
          </dl>
        </>
      )}
    </section>
  )
}

function Row({ label, amount, minus = false }: { label: string; amount: string; minus?: boolean }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-slate-900">
        {minus && '− '}
        <Money amount={amount} />
      </dd>
    </div>
  )
}

function ActivePlans({ accountId }: { accountId: string }) {
  const plans = useCardPlans(accountId)

  return (
    <section aria-label="MSI activos" className={blockClass}>
      <h3 className={blockTitle}>MSI activos</h3>
      {plans.isPending ? (
        <LoadingState />
      ) : plans.isError ? (
        <ErrorState error={plans.error} onRetry={() => void plans.refetch()} />
      ) : plans.data.length === 0 ? (
        <p className="text-sm text-slate-500">Sin compras a meses sin intereses pendientes.</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {plans.data.map((plan) => (
            <PlanRow key={plan.plan_id} plan={plan} />
          ))}
        </ul>
      )}
    </section>
  )
}

function PlanRow({ plan }: { plan: ActiveInstallmentPlan }) {
  return (
    <li className="flex items-start justify-between gap-3 py-2 first:pt-0 last:pb-0">
      <div className="min-w-0">
        <p className="truncate text-slate-900">{plan.description || 'Compra a MSI'}</p>
        <p className="text-xs text-slate-400">
          {plan.billed} de {plan.months} facturadas · siguiente corte{' '}
          {formatShortDate(plan.next_cutoff)}
        </p>
      </div>
      <div className="shrink-0 text-right text-sm">
        <p className="text-slate-900">
          <Money amount={plan.installment_amount} />
          <span className="text-xs text-slate-400"> /mes</span>
        </p>
        <p className="text-xs text-slate-500">
          faltan <Money amount={plan.remaining} />
        </p>
      </div>
    </li>
  )
}
