import { formatMoney } from '../lib/money'

interface MoneyProps {
  amount: string
  // Movements: show income in green with "+", so it stands out from expenses
  signed?: boolean
  className?: string
}

export function Money({ amount, signed = false, className = '' }: MoneyProps) {
  const formatted = formatMoney(amount)
  const isIncome = signed && !amount.startsWith('-') && !/^0+(\.0+)?$/.test(amount)
  return (
    // tabular-nums: every digit has the same width, so amounts line up in columns
    <span className={`tabular-nums ${isIncome ? 'text-emerald-600' : ''} ${className}`}>
      {isIncome ? `+${formatted}` : formatted}
    </span>
  )
}
