import { useRef, useState, type KeyboardEvent, type MouseEvent, type SubmitEvent } from 'react'

import { useCreateMovement, useCreateTransfer } from '../api/mutations'
import { useAccounts, useCategories } from '../api/queries'
import type { Account } from '../api/types'
import { todayInMexico } from '../lib/dates'
import { parseAmountInput } from '../lib/money'
import { ErrorState, LoadingState } from '../ui/Section'

export type CaptureType = 'expense' | 'income' | 'transfer' | 'card_payment'

const tabs: { type: CaptureType; label: string }[] = [
  { type: 'expense', label: 'Gasto' },
  { type: 'income', label: 'Ingreso' },
  { type: 'transfer', label: 'Transferencia' },
  { type: 'card_payment', label: 'Pago de tarjeta' },
]

// Savings accounts are filled from "available", not with expenses, income or transfers
const SPENDING = new Set<Account['type']>(['debit', 'cash', 'credit'])
const MONEY_SOURCES = new Set<Account['type']>(['debit', 'cash'])

const LAST_ACCOUNT_KEY = 'capture.lastAccountId'

// A convenience only: storage can be blocked (private windows), so failures are ignored
function readLastAccount(): string | null {
  try {
    return localStorage.getItem(LAST_ACCOUNT_KEY)
  } catch {
    return null
  }
}

function saveLastAccount(id: string): void {
  try {
    localStorage.setItem(LAST_ACCOUNT_KEY, id)
  } catch {
    // Not remembering the account is fine
  }
}

/** Accounts each tab can use: where the money comes from, and where it goes to. */
function accountChoices(type: CaptureType, accounts: readonly Account[], sourceId: string) {
  const sources = accounts.filter((account) =>
    type === 'expense' || type === 'income'
      ? SPENDING.has(account.type)
      : MONEY_SOURCES.has(account.type),
  )
  const destinations =
    type === 'transfer'
      ? accounts.filter((account) => MONEY_SOURCES.has(account.type) && account.id !== sourceId)
      : type === 'card_payment'
        ? accounts.filter((account) => account.type === 'credit')
        : []
  return { sources, destinations }
}

/** The chosen id if it's still a valid choice, else the first one. */
function pick(choices: readonly Account[], id: string | null): string {
  return choices.find((account) => account.id === id)?.id ?? choices.at(0)?.id ?? ''
}

const fieldClass =
  'mt-1 block w-full rounded-lg border-0 bg-white px-3 py-2 text-slate-900 ring-1 ring-slate-300 focus:ring-2 focus:ring-sky-500'
const labelClass = 'block text-sm font-medium text-slate-700'

interface CapturePanelProps {
  onClose: () => void
}

export function CapturePanel({ onClose }: CapturePanelProps) {
  const accounts = useAccounts()

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === 'Escape') onClose()
  }

  // Clicking outside the panel closes it (on wide screens, where the page shows behind)
  function handleBackdrop(event: MouseEvent) {
    if (event.target === event.currentTarget) onClose()
  }

  return (
    <div
      className="fixed inset-0 z-20 flex justify-end bg-slate-900/30"
      onMouseDown={handleBackdrop}
      onKeyDown={handleKeyDown}
    >
      {/* Full screen on phones; a side panel from sm (640 px) */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="capture-title"
        className="flex h-full w-full flex-col overflow-y-auto bg-slate-50 shadow-xl sm:max-w-md"
      >
        <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
          <h2 id="capture-title" className="text-base font-semibold text-slate-900">
            Nuevo movimiento
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-sm text-slate-500 hover:bg-slate-100"
          >
            Cerrar <kbd className="text-xs text-slate-400">Esc</kbd>
          </button>
        </div>
        <div className="p-4">
          {accounts.isPending ? (
            <LoadingState />
          ) : accounts.isError ? (
            <ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} />
          ) : (
            <CaptureForm accounts={accounts.data} />
          )}
        </div>
      </div>
    </div>
  )
}

function CaptureForm({ accounts }: { accounts: readonly Account[] }) {
  const categories = useCategories()
  const createMovement = useCreateMovement()
  const createTransfer = useCreateTransfer()

  const [type, setType] = useState<CaptureType>('expense')
  const [amountText, setAmountText] = useState('')
  const [chosenSource, setChosenSource] = useState<string | null>(readLastAccount)
  const [chosenDestination, setChosenDestination] = useState<string | null>(null)
  const [categoryId, setCategoryId] = useState('')
  const [occurredOn, setOccurredOn] = useState(todayInMexico)
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const amountRef = useRef<HTMLInputElement>(null)

  // Derived, not stored: switching tabs falls back to a valid account without extra state
  const { sources } = accountChoices(type, accounts, '')
  const sourceId = pick(sources, chosenSource)
  const { destinations } = accountChoices(type, accounts, sourceId)
  const destinationId = pick(destinations, chosenDestination)
  const isTransfer = type === 'transfer' || type === 'card_payment'
  const saving = createMovement.isPending || createTransfer.isPending

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    // Enter in any field submits the form
    event.preventDefault()
    setSaved(false)
    const amount = parseAmountInput(amountText)
    if (amount === null) {
      setError('Escribe un monto mayor a 0, con hasta 2 decimales.')
      amountRef.current?.focus()
      return
    }
    if (!sourceId || (isTransfer && !destinationId)) {
      setError('Elige las cuentas.')
      return
    }

    setError(null)
    try {
      if (isTransfer) {
        await createTransfer.mutateAsync({
          source_account_id: sourceId,
          destination_account_id: destinationId,
          amount,
          // An emptied date field: the API uses today
          occurred_on: occurredOn || null,
          description,
        })
      } else {
        await createMovement.mutateAsync({
          account_id: sourceId,
          type,
          amount,
          // An emptied date field: the API uses today
          occurred_on: occurredOn || null,
          description,
          category_id: categoryId || null,
        })
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo guardar.')
      return
    }

    saveLastAccount(sourceId)
    // Ready for the next one: keep type, accounts, category and date
    setAmountText('')
    setDescription('')
    setSaved(true)
    amountRef.current?.focus()
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)} className="space-y-4" noValidate>
      <div role="tablist" aria-label="Tipo" className="grid grid-cols-2 gap-1 sm:grid-cols-4">
        {tabs.map((tab) => (
          <button
            key={tab.type}
            type="button"
            role="tab"
            aria-selected={type === tab.type}
            onClick={() => {
              setType(tab.type)
              setError(null)
              setSaved(false)
            }}
            className={`rounded-lg px-2 py-2 text-sm font-medium ${
              type === tab.type
                ? 'bg-slate-900 text-white'
                : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <label className={labelClass}>
        Monto
        <input
          ref={amountRef}
          // Text, not type="number": no float parsing, and "1,234.50" can be typed as is.
          // inputMode opens the phone's numeric keypad with a decimal point
          type="text"
          inputMode="decimal"
          autoComplete="off"
          autoFocus
          placeholder="0.00"
          value={amountText}
          onChange={(event) => {
            setAmountText(event.target.value)
            setSaved(false)
          }}
          className={`${fieldClass} text-lg tabular-nums`}
        />
      </label>

      <label className={labelClass}>
        {isTransfer ? 'Desde' : 'Cuenta'}
        <select
          value={sourceId}
          onChange={(event) => {
            setChosenSource(event.target.value)
          }}
          className={fieldClass}
        >
          {sources.map((account) => (
            <option key={account.id} value={account.id}>
              {account.name}
            </option>
          ))}
        </select>
      </label>

      {isTransfer && (
        <label className={labelClass}>
          {type === 'card_payment' ? 'Tarjeta' : 'Hacia'}
          <select
            value={destinationId}
            onChange={(event) => {
              setChosenDestination(event.target.value)
            }}
            className={fieldClass}
          >
            {destinations.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name}
              </option>
            ))}
          </select>
        </label>
      )}

      {!isTransfer && (
        <label className={labelClass}>
          Categoría
          <select
            value={categoryId}
            onChange={(event) => {
              setCategoryId(event.target.value)
            }}
            className={fieldClass}
          >
            <option value="">Sin categoría</option>
            {categories.data?.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </label>
      )}

      <div className="grid grid-cols-2 gap-3">
        <label className={labelClass}>
          Fecha
          <input
            type="date"
            required
            value={occurredOn}
            onChange={(event) => {
              setOccurredOn(event.target.value)
            }}
            className={fieldClass}
          />
        </label>
        <label className={labelClass}>
          Descripción
          <input
            type="text"
            maxLength={200}
            value={description}
            onChange={(event) => {
              setDescription(event.target.value)
            }}
            className={fieldClass}
          />
        </label>
      </div>

      {error && (
        <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">
          {error}
        </p>
      )}
      {saved && (
        <p role="status" className="text-sm text-emerald-700">
          Guardado. Puedes capturar el siguiente.
        </p>
      )}

      <button
        type="submit"
        disabled={saving}
        className="w-full rounded-lg bg-sky-600 px-4 py-3 font-semibold text-white hover:bg-sky-700 disabled:opacity-60"
      >
        {saving ? 'Guardando…' : 'Guardar'} <kbd className="text-xs opacity-75">Enter</kbd>
      </button>
    </form>
  )
}
