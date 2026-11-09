import type { Account, CardSummary } from '../../api/types'
import { formatShortDate } from '../../lib/dates'
import { Money } from '../../ui/Money'

const typeLabel: Record<Account['type'], string> = {
  debit: 'Débito',
  cash: 'Efectivo',
  credit: 'Crédito',
  savings: 'Ahorro',
}

interface AccountCardProps {
  account: Account
  // From /summary: debt and next payment of a credit card, already calculated by the API
  card?: CardSummary
}

export function AccountCard({ account, card }: AccountCardProps) {
  return (
    <article
      aria-label={account.name}
      className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200"
      // A thin stripe in the account's color, if it has one
      style={account.color ? { borderLeft: `4px solid ${account.color}` } : undefined}
    >
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <h3 className="font-medium text-slate-900">{account.name}</h3>
          <p className="text-xs text-slate-400">{typeLabel[account.type]}</p>
        </div>
        {account.credit && card ? (
          <p className="text-right">
            <span className="block text-xs text-slate-500">Debes</span>
            <Money amount={card.debt} className="font-semibold text-slate-900" />
          </p>
        ) : (
          <Money amount={account.balance} className="font-semibold text-slate-900" />
        )}
      </div>

      {account.credit && (
        <dl className="mt-3 space-y-1 border-t border-slate-100 pt-3 text-sm">
          <div className="flex justify-between gap-3">
            <dt className="text-slate-500">Crédito disponible</dt>
            <dd>
              <Money amount={account.credit.available} />
            </dd>
          </div>
          {card && <NextPayment card={card} />}
        </dl>
      )}
    </article>
  )
}

function NextPayment({ card }: { card: CardSummary }) {
  const payment = card.next_payment
  if (!payment.is_closed) {
    // The last statement is past due: this is the open cycle, still growing
    return (
      <div className="flex justify-between gap-3">
        <dt className="text-slate-500">Llevas · corte {formatShortDate(payment.cutoff)}</dt>
        <dd>
          <Money amount={payment.amount} />
        </dd>
      </div>
    )
  }
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-slate-500">Pagar antes del {formatShortDate(payment.payment_due)}</dt>
      <dd className="font-medium text-slate-900">
        <Money amount={payment.amount} />
      </dd>
    </div>
  )
}
