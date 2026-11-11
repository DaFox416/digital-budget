/**
 * Money in the frontend is a decimal string from the API ("-387.56"), never a float.
 *
 * Intl.NumberFormat formats strings as exact decimals (ES2023): "90071992547409.93" stays
 * .93, while the same value as a number prints .94 because floats can't hold it exactly.
 */
const mxn = new Intl.NumberFormat('es-MX', {
  style: 'currency',
  currency: 'MXN',
  // Shows "-" only for negatives: "-0.00" becomes "$0.00", not "-$0.00"
  signDisplay: 'negative',
})

// Same shape the API sends: optional minus, digits, up to 2 decimals
const MONEY_PATTERN = /^-?\d+(\.\d{1,2})?$/

export function isMoney(value: string): value is `${number}` {
  return MONEY_PATTERN.test(value)
}

/** "-387.56" -> "-$387.56", "14777.11" -> "$14,777.11". Throws on anything else. */
export function formatMoney(amount: string): string {
  if (!isMoney(amount)) {
    // Fail loudly: showing "NaN" or a wrong figure in a finance app is worse than an error
    throw new Error(`Not a money amount: ${JSON.stringify(amount)}`)
  }
  return mxn.format(amount)
}

// What a person types: digits with optional thousands commas and up to 2 decimals
const AMOUNT_INPUT = /^\d+(\.\d{1,2})?$/

/**
 * Turn a typed amount into the string the API takes ("1,234.5" -> "1234.5"), or null if it
 * isn't a positive amount. It stays a string end to end: no parseFloat.
 */
export function parseAmountInput(text: string): string | null {
  const value = text.trim().replaceAll(',', '')
  if (!AMOUNT_INPUT.test(value)) return null
  // Has a non-zero digit: "0", "0.00" and "000" are not amounts
  return /[1-9]/.test(value) ? value : null
}
