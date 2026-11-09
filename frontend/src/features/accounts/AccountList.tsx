import { useAccounts, useSummary } from '../../api/queries'
import { EmptyState, ErrorState, LoadingState } from '../../ui/Section'
import { AccountCard } from './AccountCard'

export function AccountList() {
  const accounts = useAccounts()
  // Optional here: if the summary fails, cards still show their balance and available credit
  const summary = useSummary()

  if (accounts.isPending) return <LoadingState />
  if (accounts.isError) {
    return <ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} />
  }
  if (accounts.data.length === 0) {
    return <EmptyState>Aún no tienes cuentas. Por ahora se crean desde /docs.</EmptyState>
  }

  const cards = new Map(summary.data?.cards.map((card) => [card.account_id, card]))

  return (
    <ul className="space-y-3">
      {accounts.data.map((account) => (
        <li key={account.id}>
          <AccountCard account={account} card={cards.get(account.id)} />
        </li>
      ))}
    </ul>
  )
}
