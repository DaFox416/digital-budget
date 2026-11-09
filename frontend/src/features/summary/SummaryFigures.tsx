import { useSummary } from '../../api/queries'
import { Money } from '../../ui/Money'
import { ErrorState, LoadingState } from '../../ui/Section'

// "Disponible" joins these on day 10, when the API calculates it
export function SummaryFigures() {
  const summary = useSummary()

  if (summary.isPending) return <LoadingState />
  if (summary.isError) {
    return <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />
  }

  const figures = [
    { label: 'Saldo real', amount: summary.data.real_balance, hint: 'Débito y efectivo' },
    { label: 'Deuda de tarjetas', amount: summary.data.card_debt, hint: 'Incluye compras a MSI' },
    {
      label: 'MSI por cargar',
      amount: summary.data.installments_pending,
      hint: 'Mensualidades que aún no se descuentan',
    },
  ]

  return (
    <dl className="grid gap-3 sm:grid-cols-3">
      {figures.map((figure) => (
        <div key={figure.label} className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
          <dt className="text-sm text-slate-500">{figure.label}</dt>
          <dd className="mt-1 text-2xl font-semibold text-slate-900">
            <Money amount={figure.amount} />
          </dd>
          <dd className="mt-1 text-xs text-slate-400">{figure.hint}</dd>
        </div>
      ))}
    </dl>
  )
}
