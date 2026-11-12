import { usePreferences, useSummary } from '../../api/queries'
import type { Summary } from '../../api/types'
import { Money } from '../../ui/Money'
import { ErrorState, LoadingState } from '../../ui/Section'

interface Figure {
  label: string
  amount: string
  hint: string
  highlight?: boolean
}

// Every amount comes from the API as is: the frontend doesn't do math with money
function mainFigures(summary: Summary, savingsMode: boolean): Figure[] {
  const realBalance = {
    label: 'Saldo real',
    amount: summary.real_balance,
    hint: 'Débito y efectivo',
  }
  const rest = [
    { label: 'Deuda de tarjetas', amount: summary.card_debt, hint: 'Incluye compras a MSI' },
    {
      label: 'MSI por cargar',
      amount: summary.installments_pending,
      hint: 'Mensualidades que aún no se descuentan',
    },
  ]
  if (!savingsMode) return [realBalance, ...rest]
  const available = {
    label: 'Disponible',
    amount: summary.available,
    hint: 'Lo que puedes gastar',
    highlight: true,
  }
  return [realBalance, available, ...rest]
}

export function SummaryFigures() {
  const summary = useSummary()
  const preferences = usePreferences()

  if (summary.isPending) return <LoadingState />
  if (summary.isError) {
    return <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />
  }

  // Without preferences (still loading or failed), behave as simple mode, like the panel
  const savingsMode = preferences.data?.mode === 'savings'
  const figures = mainFigures(summary.data, savingsMode)

  return (
    <div className="space-y-3">
      <dl
        // Simple mode keeps its 3 columns from sm; savings mode goes 2 x 2, then 4 in a row
        className={`grid gap-3 ${savingsMode ? 'sm:grid-cols-2 lg:grid-cols-4' : 'sm:grid-cols-3'}`}
      >
        {figures.map((figure) => (
          <div
            key={figure.label}
            className={`rounded-xl p-4 shadow-sm ring-1 ${
              figure.highlight ? 'bg-sky-50 ring-sky-200' : 'bg-white ring-slate-200'
            }`}
          >
            <dt className={`text-sm ${figure.highlight ? 'text-sky-700' : 'text-slate-500'}`}>
              {figure.label}
            </dt>
            <dd className="mt-1 text-2xl font-semibold text-slate-900">
              <Money amount={figure.amount} />
            </dd>
            <dd className="mt-1 text-xs text-slate-400">{figure.hint}</dd>
          </div>
        ))}
      </dl>
      {savingsMode && <SavingsDetail summary={summary.data} />}
    </div>
  )
}

/** The secondary figures of savings mode, in one discreet line. */
function SavingsDetail({ summary }: { summary: Summary }) {
  return (
    <dl
      aria-label="Detalle del disponible"
      className="flex flex-wrap gap-x-6 gap-y-1 px-1 text-sm text-slate-500"
    >
      <div className="flex gap-1">
        <dt>Apartado:</dt>
        <dd className="font-medium text-slate-700">
          <Money amount={summary.set_aside} />
        </dd>
      </div>
      <div className="flex gap-1">
        <dt>Ahorros con meta:</dt>
        <dd className="font-medium text-slate-700">
          <Money amount={summary.savings_goals} />
        </dd>
      </div>
      <div className="flex gap-1">
        <dt>Sobrante:</dt>
        <dd className="font-medium text-slate-700">
          <Money amount={summary.leftover} />
        </dd>
        <dd className="text-slate-400">
          (puedes liberar <Money amount={summary.leftover_releasable} />)
        </dd>
      </div>
    </dl>
  )
}
