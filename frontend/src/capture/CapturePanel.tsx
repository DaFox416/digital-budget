import { useQueryClient } from '@tanstack/react-query'
import { useRef, useState, type KeyboardEvent, type MouseEvent } from 'react'

import { useCreateInstallmentPlan, useCreateMovement, useCreateTransfer } from '../api/mutations'
import {
  previewQuery,
  useAccounts,
  useCategories,
  useCommitments,
  usePreferences,
  usePreview,
} from '../api/queries'
import type {
  Account,
  MovementPreview,
  MovementPreviewRequest,
  PurchaseWarning,
} from '../api/types'
import { formatShortDate, todayInMexico } from '../lib/dates'
import { formatMoney, isMoney, parseAmountInput } from '../lib/money'
import { useDebouncedValue } from '../lib/useDebouncedValue'
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

// MSI terms shown first (docs/PLANEACION.md); any term from 3 to 48 can be typed
const COMMON_MONTHS = [3, 6, 9, 12]
const MIN_MONTHS = 3
const MAX_MONTHS = 48

// Wait for the typing to pause before asking the API for the preview
const PREVIEW_DELAY_MS = 300

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

/** "12" -> 12; null for an empty field. NaN for anything outside 3 to 48. */
function parseMonths(text: string): number | null {
  const value = text.trim()
  if (value === '') return null
  return /^\d+$/.test(value) && Number(value) >= MIN_MONTHS && Number(value) <= MAX_MONTHS
    ? Number(value)
    : Number.NaN
}

function money(amount: string): string {
  return isMoney(amount) ? formatMoney(amount) : amount
}

const FIELD_KEYS = [
  'amount',
  'accounting',
  'source',
  'months',
  'destination',
  'category',
  'commitment',
  'date',
  'description',
] as const
type FieldKey = (typeof FIELD_KEYS)[number]

interface CaptureField {
  key: FieldKey
  // How it reads in the Ctrl+Enter notice; null for the amount, which can't be left out
  summary: string | null
}

/** The field an element is, from its `data-field`; null for tabs, buttons and the rest. */
function fieldOf(element: HTMLElement): FieldKey | null {
  const key = element.dataset.field
  return FIELD_KEYS.find((item) => item === key) ?? null
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
  const queryClient = useQueryClient()
  const categories = useCategories()
  const preferences = usePreferences()
  const commitments = useCommitments()
  const createMovement = useCreateMovement()
  const createTransfer = useCreateTransfer()
  const createPlan = useCreateInstallmentPlan()

  const [type, setType] = useState<CaptureType>('expense')
  const [amountText, setAmountText] = useState('')
  // Follows the suggestion until it's typed by hand
  const [accountingText, setAccountingText] = useState<string | null>(null)
  const [chosenSource, setChosenSource] = useState<string | null>(readLastAccount)
  const [chosenDestination, setChosenDestination] = useState<string | null>(null)
  const [monthsText, setMonthsText] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [commitmentId, setCommitmentId] = useState('')
  const [occurredOn, setOccurredOn] = useState(todayInMexico)
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  // Ctrl+Enter with fields left to review: what they hold, and where Esc goes back to
  const [unreviewed, setUnreviewed] = useState<{ items: string[]; returnTo: FieldKey } | null>(null)
  // Level 2 warning: the preview it was shown for; saving that same one again goes ahead
  const [overRealShownFor, setOverRealShownFor] = useState<string | null>(null)
  const formRef = useRef<HTMLFormElement>(null)
  const submitRef = useRef<HTMLButtonElement>(null)
  const tabRefs = useRef(new Map<CaptureType, HTMLButtonElement>())

  // Derived, not stored: switching tabs falls back to a valid account without extra state
  const { sources } = accountChoices(type, accounts, '')
  const sourceId = pick(sources, chosenSource)
  const { destinations } = accountChoices(type, accounts, sourceId)
  const destinationId = pick(destinations, chosenDestination)
  const source = accounts.find((account) => account.id === sourceId)

  // Without preferences (still loading or failed), behave as simple mode
  const savingsMode = preferences.data?.mode === 'savings'
  const isTransfer = type === 'transfer' || type === 'card_payment'
  const cardExpense = type === 'expense' && source?.type === 'credit'
  const months = cardExpense ? parseMonths(monthsText) : null
  const isInstallments = months !== null && !Number.isNaN(months)
  const pendingCommitments = (commitments.data ?? []).filter((c) => c.paid_by_movement_id === null)
  const showAccounting = savingsMode && !isTransfer && !isInstallments
  const showCommitment =
    savingsMode && type === 'expense' && !isInstallments && pendingCommitments.length > 0
  const saving = createMovement.isPending || createTransfer.isPending || createPlan.isPending

  const amount = parseAmountInput(amountText)
  const typedAccounting =
    showAccounting && accountingText !== null ? parseAmountInput(accountingText) : null
  const sentCommitment = showCommitment && commitmentId ? commitmentId : null

  // Savings mode needs the suggestion; card expenses, the warnings. Transfers need neither
  const previewBody: MovementPreviewRequest | null =
    amount !== null && !isTransfer && sourceId && (savingsMode || cardExpense)
      ? {
          account_id: sourceId,
          type: type === 'income' ? 'income' : 'expense',
          amount,
          accounting_amount: typedAccounting,
          commitment_id: sentCommitment,
          months: isInstallments ? months : null,
        }
      : null
  const previewKey = previewBody && JSON.stringify(previewBody)
  const debouncedKey = useDebouncedValue(previewKey, PREVIEW_DELAY_MS)
  const preview = usePreview(
    debouncedKey === previewKey && previewBody !== null ? previewBody : null,
  )
  // Only what belongs to the current values: a reply for an older amount isn't shown
  const current = debouncedKey === previewKey ? preview.data : undefined
  const suggestion = current?.suggested_accounting_amount ?? null
  const accountingValue = accountingText ?? suggestion ?? ''

  const accountName = (id: string) => accounts.find((account) => account.id === id)?.name ?? '—'
  const categoryName = categories.data?.find((category) => category.id === categoryId)?.name
  const commitmentName = pendingCommitments.find((c) => c.id === commitmentId)?.name
  const sourceLabel = isTransfer ? 'Desde' : 'Cuenta'
  const destinationLabel = type === 'card_payment' ? 'Tarjeta' : 'Hacia'

  // This tab's fields in screen order: Enter walks this list, and Ctrl+Enter lists the ones
  // after the current field (the ones not reviewed yet) with what they hold
  const fields: CaptureField[] = [
    { key: 'amount', summary: null },
    ...(showAccounting
      ? [
          {
            key: 'accounting' as const,
            summary: `Contable: ${accountingValue ? money(accountingValue) : 'igual al monto'}`,
          },
        ]
      : []),
    { key: 'source', summary: `${sourceLabel}: ${accountName(sourceId)}` },
    ...(cardExpense
      ? [{ key: 'months' as const, summary: isInstallments ? `${String(months)} MSI` : 'Sin MSI' }]
      : []),
    isTransfer
      ? { key: 'destination', summary: `${destinationLabel}: ${accountName(destinationId)}` }
      : { key: 'category', summary: categoryName ?? 'Sin categoría' },
    ...(showCommitment
      ? [
          {
            key: 'commitment' as const,
            summary: commitmentName ? `Paga: ${commitmentName}` : 'Sin apartado',
          },
        ]
      : []),
    {
      key: 'date',
      summary: `Fecha: ${!occurredOn || occurredOn === todayInMexico() ? 'hoy' : formatShortDate(occurredOn)}`,
    },
    { key: 'description', summary: description ? `"${description}"` : 'Sin descripción' },
  ]

  function focusField(key: FieldKey) {
    formRef.current?.querySelector<HTMLElement>(`[data-field="${key}"]`)?.focus()
  }

  function chooseType(next: CaptureType) {
    setType(next)
    setError(null)
    setSaved(false)
  }

  function restart() {
    // Every capture starts over from Gasto: the number of → presses always means the same type
    setType('expense')
    setAmountText('')
    setAccountingText(null)
    setChosenSource(readLastAccount())
    setChosenDestination(null)
    setMonthsText('')
    setCategoryId('')
    setCommitmentId('')
    setOccurredOn(todayInMexico())
    setDescription('')
    setOverRealShownFor(null)
    tabRefs.current.get('expense')?.focus()
  }

  /** The preview for exactly what's being saved; the cached one if it's already there. */
  async function previewNow(body: MovementPreviewRequest): Promise<MovementPreview | null> {
    try {
      return await queryClient.query(previewQuery(body))
    } catch {
      // Warnings and suggestions only advise: the API still validates what's saved
      return null
    }
  }

  async function save() {
    setSaved(false)
    setUnreviewed(null)
    if (amount === null) {
      setError('Escribe un monto mayor a 0, con hasta 2 decimales.')
      focusField('amount')
      return
    }
    if (months !== null && Number.isNaN(months)) {
      setError(`Los meses sin intereses van de ${String(MIN_MONTHS)} a ${String(MAX_MONTHS)}.`)
      focusField('months')
      return
    }
    if (showAccounting && accountingText !== null && accountingText.trim() !== '') {
      if (typedAccounting === null) {
        setError('El contable debe ser un monto mayor a 0, con hasta 2 decimales.')
        focusField('accounting')
        return
      }
    }
    if (!sourceId || (isTransfer && !destinationId)) {
      setError('Elige las cuentas.')
      return
    }

    const checked = previewBody && (await previewNow(previewBody))
    if (checked?.warning?.level === 'over_real_balance' && overRealShownFor !== previewKey) {
      // Level 2 asks once more: the next Enter, Ctrl+Enter or click saves it
      setOverRealShownFor(previewKey)
      setError(null)
      submitRef.current?.focus()
      return
    }

    setError(null)
    const date = occurredOn || null
    try {
      if (isTransfer) {
        await createTransfer.mutateAsync({
          type,
          body: {
            source_account_id: sourceId,
            destination_account_id: destinationId,
            amount,
            // An emptied date field: the API uses today
            occurred_on: date,
            description,
          },
        })
      } else if (isInstallments) {
        await createPlan.mutateAsync({
          account_id: sourceId,
          total: amount,
          months,
          purchased_on: date,
          description,
          category_id: categoryId || null,
        })
      } else {
        await createMovement.mutateAsync({
          account_id: sourceId,
          type,
          amount,
          // Savings mode: what was typed, else the suggestion. Left out, the API uses the
          // amount (or, paying a commitment, the larger of both)
          accounting_amount: showAccounting
            ? (typedAccounting ?? checked?.suggested_accounting_amount ?? null)
            : null,
          occurred_on: date,
          description,
          category_id: categoryId || null,
          commitment_id: sentCommitment,
        })
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo guardar.')
      return
    }

    saveLastAccount(sourceId)
    setSaved(true)
    restart()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLFormElement>) {
    // The notice handles its own keys
    if (unreviewed !== null || !(event.target instanceof HTMLElement)) return
    const target = event.target
    const tab = tabs.findIndex((item) => tabRefs.current.get(item.type) === target)

    if (tab !== -1 && (event.key === 'ArrowRight' || event.key === 'ArrowLeft')) {
      event.preventDefault()
      // No wrapping around: pressing → n times always lands on the same type
      const index = Math.min(Math.max(tab + (event.key === 'ArrowRight' ? 1 : -1), 0), 3)
      const next = tabs[index].type
      chooseType(next)
      tabRefs.current.get(next)?.focus()
      return
    }
    if (event.key !== 'Enter') return
    event.preventDefault()

    const currentField = fieldOf(target)
    const position = fields.findIndex((field) => field.key === currentField)
    // From the tabs every field is still ahead; from the Save button, none is
    const ahead = tab !== -1 ? fields : position === -1 ? [] : fields.slice(position + 1)

    if (event.ctrlKey || event.metaKey) {
      const items = ahead.flatMap((field) => (field.summary === null ? [] : [field.summary]))
      // Without an amount, save() shows the error instead of the notice
      if (items.length > 0 && amount !== null) {
        setUnreviewed({ items, returnTo: currentField ?? 'amount' })
      } else {
        void save()
      }
      return
    }
    const next = ahead.at(0)
    if (next) focusField(next.key)
    else void save()
  }

  function cancelNotice() {
    const returnTo = unreviewed?.returnTo ?? 'amount'
    setUnreviewed(null)
    focusField(returnTo)
  }

  const warning = current?.warning ?? null
  const confirmingOverReal = overRealShownFor !== null && overRealShownFor === previewKey

  return (
    <form
      ref={formRef}
      onSubmit={(event) => {
        event.preventDefault()
        void save()
      }}
      onKeyDown={handleKeyDown}
      className="space-y-4"
      noValidate
    >
      <div role="tablist" aria-label="Tipo" className="grid grid-cols-2 gap-1 sm:grid-cols-4">
        {tabs.map((tab) => (
          <button
            key={tab.type}
            ref={(element) => {
              if (element) tabRefs.current.set(tab.type, element)
            }}
            type="button"
            role="tab"
            aria-selected={type === tab.type}
            // Roving focus: only the selected tab is in the Tab order; arrows move between them
            tabIndex={type === tab.type ? 0 : -1}
            autoFocus={tab.type === 'expense'}
            onClick={() => {
              chooseType(tab.type)
            }}
            className={`rounded-lg px-2 py-2 text-sm font-medium focus:ring-2 focus:ring-sky-500 focus:outline-none ${
              type === tab.type
                ? 'bg-slate-900 text-white'
                : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <p className="hidden text-xs text-slate-400 sm:block">
        <kbd>←</kbd> <kbd>→</kbd> tipo · <kbd>Enter</kbd> siguiente campo · <kbd>Ctrl+Enter</kbd>{' '}
        guardar
      </p>

      <label className={labelClass}>
        {isInstallments ? 'Monto total' : 'Monto'}
        <input
          data-field="amount"
          // Text, not type="number": no float parsing, and "1,234.50" can be typed as is.
          // inputMode opens the phone's numeric keypad with a decimal point
          type="text"
          inputMode="decimal"
          autoComplete="off"
          placeholder="0.00"
          value={amountText}
          onChange={(event) => {
            setAmountText(event.target.value)
            setSaved(false)
          }}
          className={`${fieldClass} text-lg tabular-nums`}
        />
      </label>

      {showAccounting && (
        <label className={labelClass}>
          Contable
          <input
            data-field="accounting"
            type="text"
            inputMode="decimal"
            autoComplete="off"
            placeholder={amount ?? '0.00'}
            value={accountingValue}
            onChange={(event) => {
              setAccountingText(event.target.value)
            }}
            className={`${fieldClass} tabular-nums`}
          />
          <span className="mt-1 block text-xs font-normal text-slate-400">
            {accountingText === null
              ? 'Redondeo sugerido; lo que pase del monto va al sobrante.'
              : 'Escrito a mano.'}
          </span>
        </label>
      )}

      <label className={labelClass}>
        {sourceLabel}
        <select
          data-field="source"
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

      {cardExpense && (
        <div>
          <label className={labelClass}>
            Meses sin intereses
            <input
              data-field="months"
              type="text"
              inputMode="numeric"
              autoComplete="off"
              placeholder="Sin MSI"
              value={monthsText}
              onChange={(event) => {
                setMonthsText(event.target.value)
              }}
              className={`${fieldClass} tabular-nums`}
            />
          </label>
          <div className="mt-2 flex gap-2">
            {COMMON_MONTHS.map((value) => (
              <button
                key={value}
                type="button"
                // For mouse and touch; the keyboard types the number
                tabIndex={-1}
                onClick={() => {
                  setMonthsText(monthsText === String(value) ? '' : String(value))
                }}
                className={`rounded-full px-3 py-1 text-sm ${
                  monthsText === String(value)
                    ? 'bg-slate-900 text-white'
                    : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100'
                }`}
              >
                {value}
              </button>
            ))}
          </div>
          {isInstallments && current?.first_installment && (
            <p className="mt-2 text-xs text-slate-500">
              {months} mensualidades; la primera de {money(current.first_installment.amount)}
              {savingsMode &&
                ` (contable ${money(current.first_installment.accounting_amount)} al mes)`}
              .
            </p>
          )}
        </div>
      )}

      {isTransfer ? (
        <label className={labelClass}>
          {destinationLabel}
          <select
            data-field="destination"
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
      ) : (
        <label className={labelClass}>
          Categoría
          <select
            data-field="category"
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

      {showCommitment && (
        <label className={labelClass}>
          Paga un apartado
          <select
            data-field="commitment"
            value={commitmentId}
            onChange={(event) => {
              setCommitmentId(event.target.value)
            }}
            className={fieldClass}
          >
            <option value="">Ninguno</option>
            {pendingCommitments.map((commitment) => (
              <option key={commitment.id} value={commitment.id}>
                {commitment.name} · {money(commitment.amount)}
              </option>
            ))}
          </select>
        </label>
      )}

      <div className="grid grid-cols-2 gap-3">
        <label className={labelClass}>
          Fecha
          <input
            data-field="date"
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
            data-field="description"
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

      {warning && <WarningMessage warning={warning} confirming={confirmingOverReal} />}
      {unreviewed && (
        <UnreviewedNotice
          items={unreviewed.items}
          onSave={() => void save()}
          onCancel={cancelNotice}
        />
      )}
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
        ref={submitRef}
        type="submit"
        disabled={saving}
        className={`w-full rounded-lg px-4 py-3 font-semibold text-white disabled:opacity-60 ${
          confirmingOverReal ? 'bg-rose-600 hover:bg-rose-700' : 'bg-sky-600 hover:bg-sky-700'
        }`}
      >
        {saving ? 'Guardando…' : confirmingOverReal ? 'Guardar de todos modos' : 'Guardar'}{' '}
        <kbd className="hidden text-xs opacity-75 sm:inline">
          {confirmingOverReal ? 'Enter' : 'Ctrl+Enter'}
        </kbd>
      </button>
    </form>
  )
}

/** Level 1 in yellow (over "available"), level 2 in red (over the real balance). */
function WarningMessage({
  warning,
  confirming,
}: {
  warning: PurchaseWarning
  confirming: boolean
}) {
  if (warning.level === 'over_available') {
    return (
      <p
        data-warning="1"
        className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200"
      >
        Esta compra supera tu disponible por {money(warning.excess)}.
      </p>
    )
  }
  return (
    <div
      data-warning="2"
      role="alert"
      className="rounded-lg bg-rose-50 p-3 text-sm font-medium text-rose-900 ring-2 ring-rose-400"
    >
      <p>Esta compra supera tu saldo real por {money(warning.excess)}.</p>
      {confirming && (
        <p className="mt-1 font-normal">
          Si de todos modos quieres guardarla, presiona Enter o el botón rojo.
        </p>
      )}
    </div>
  )
}

interface UnreviewedNoticeProps {
  items: string[]
  onSave: () => void
  onCancel: () => void
}

/** Quick check before saving with Ctrl+Enter while some fields weren't reviewed. */
function UnreviewedNotice({ items, onSave, onCancel }: UnreviewedNoticeProps) {
  return (
    <div
      role="alertdialog"
      aria-label="Guardar sin revisar todo"
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          // Back to filling in, without closing the panel
          event.stopPropagation()
          onCancel()
        }
      }}
      className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200"
    >
      <p>{items.join(' · ')}</p>
      <div className="mt-2 flex gap-2">
        {/* Focused on show: Enter "clicks" it, the browser's own behavior for buttons */}
        <button
          type="button"
          autoFocus
          onClick={onSave}
          className="rounded-lg bg-amber-600 px-3 py-1.5 font-semibold text-white hover:bg-amber-700"
        >
          Guardar <kbd className="text-xs opacity-75">Enter</kbd>
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg px-3 py-1.5 text-amber-900 ring-1 ring-amber-300 hover:bg-amber-100"
        >
          Seguir llenando <kbd className="text-xs opacity-75">Esc</kbd>
        </button>
      </div>
    </div>
  )
}
