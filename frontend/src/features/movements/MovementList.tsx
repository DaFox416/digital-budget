import { useAccounts, useCategories, useMovements } from '../../api/queries'
import type { Movement } from '../../api/types'
import { formatDay } from '../../lib/dates'
import { groupByDay, groupTransfers, type MovementRow } from '../../lib/movements'
import { Money } from '../../ui/Money'
import { EmptyState, ErrorState, LoadingState } from '../../ui/Section'

const MOVEMENT_LIMIT = 50

const typeLabel: Record<Movement['type'], string> = {
  expense: 'Gasto',
  income: 'Ingreso',
  transfer: 'Transferencia',
  card_payment: 'Pago de tarjeta',
}

export function MovementList() {
  const movements = useMovements({ limit: MOVEMENT_LIMIT })
  // Only for names: while they load, rows show without account or category
  const accounts = useAccounts()
  const categories = useCategories()

  if (movements.isPending) return <LoadingState />
  if (movements.isError) {
    return <ErrorState error={movements.error} onRetry={() => void movements.refetch()} />
  }
  if (movements.data.length === 0) {
    return <EmptyState>Aún no hay movimientos.</EmptyState>
  }

  const accountNames = new Map(accounts.data?.map((account) => [account.id, account.name]))
  const categoryNames = new Map(categories.data?.map((category) => [category.id, category.name]))
  const days = groupByDay(groupTransfers(movements.data))

  return (
    <div className="space-y-4">
      {days.map((day) => (
        <section key={day.day} aria-label={formatDay(day.day)}>
          <h3 className="mb-1 text-xs font-medium text-slate-400">{formatDay(day.day)}</h3>
          <ul className="divide-y divide-slate-100 rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
            {day.rows.map((row) => (
              <li key={row.key} className="flex items-center justify-between gap-3 px-4 py-3">
                <RowText row={row} accountNames={accountNames} categoryNames={categoryNames} />
                <RowAmount row={row} />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

interface RowTextProps {
  row: MovementRow
  accountNames: Map<string, string>
  categoryNames: Map<string, string>
}

function RowText({ row, accountNames, categoryNames }: RowTextProps) {
  if (row.kind === 'transfer') {
    const from = accountNames.get(row.source.account_id) ?? '…'
    const to = accountNames.get(row.destination.account_id) ?? '…'
    return (
      <div className="min-w-0">
        <p className="truncate text-slate-900">{row.source.description || typeLabel[row.type]}</p>
        <p className="truncate text-xs text-slate-400">
          {from} → {to}
        </p>
      </div>
    )
  }

  const { movement } = row
  const category = movement.category_id ? categoryNames.get(movement.category_id) : undefined
  const details = [accountNames.get(movement.account_id), category].filter(Boolean).join(' · ')
  return (
    <div className="min-w-0">
      <p className="truncate text-slate-900">
        {movement.description || category || typeLabel[movement.type]}
      </p>
      {details && <p className="truncate text-xs text-slate-400">{details}</p>}
    </div>
  )
}

function RowAmount({ row }: { row: MovementRow }) {
  // A transfer moves money between your own accounts: shown without sign or color
  if (row.kind === 'transfer') {
    return <Money amount={row.destination.real_amount} className="shrink-0 text-slate-700" />
  }
  return <Money amount={row.movement.real_amount} signed className="shrink-0 text-slate-900" />
}
