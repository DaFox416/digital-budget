import { useQueryClient } from '@tanstack/react-query'
import { useRef, useState, type KeyboardEvent } from 'react'

import { useUpdateMovement } from '../../api/mutations'
import {
  previewQuery,
  useAccounts,
  useCategories,
  useCommitments,
  usePreferences,
  usePreview,
} from '../../api/queries'
import type { Movement, MovementPreviewRequest, MovementUpdate } from '../../api/types'
import { formatShortDate } from '../../lib/dates'
import { formatMoney, parseAmountInput } from '../../lib/money'
import { movementTypeLabel, unsigned, type MovementRow } from '../../lib/movements'
import { fieldBase, fieldClass, labelClass } from '../../ui/form'
import { SidePanel } from '../../ui/SidePanel'

interface EditPanelProps {
  row: MovementRow
  onClose: () => void
  // The panel closes and the parent deletes it, with the undo notice
  onDelete: (movement: Movement) => void
}

/** Edit or delete a movement from the list. The account and the type can't change. */
export function EditPanel({ row, onClose, onDelete }: EditPanelProps) {
  const accounts = useAccounts()
  const accountName = (id: string) =>
    accounts.data?.find((account) => account.id === id)?.name ?? '…'
  // What PATCH and DELETE get: either leg of a transfer changes both
  const movement = row.kind === 'transfer' ? row.source : row.movement
  const where =
    row.kind === 'transfer'
      ? `${accountName(row.source.account_id)} → ${accountName(row.destination.account_id)}`
      : accountName(movement.account_id)
  const isInstallments = row.kind === 'single' && movement.installment_plan_id !== null

  return (
    <SidePanel title={isInstallments ? 'Compra a MSI' : 'Editar movimiento'} onClose={onClose}>
      <div className="space-y-4">
        <div>
          <p className="text-sm font-medium text-slate-900">
            {movementTypeLabel[movement.type]} · {where}
          </p>
          {!isInstallments && (
            <p className="mt-1 text-xs text-slate-500">
              La cuenta y el tipo no se cambian: si están mal, borra el movimiento y captúralo de
              nuevo.
            </p>
          )}
        </div>

        {isInstallments ? (
          <InstallmentsDetail movement={movement} />
        ) : (
          <EditForm row={row} onSaved={onClose} />
        )}

        <button
          type="button"
          onClick={() => {
            onDelete(movement)
          }}
          className="w-full rounded-lg px-4 py-2 text-sm font-medium text-rose-700 ring-1 ring-rose-200 hover:bg-rose-50"
        >
          Borrar {row.kind === 'transfer' ? 'las dos partes' : 'movimiento'}
        </button>
      </div>
    </SidePanel>
  )
}

/** MSI purchases are read-only until advancing or settling them arrives (v1). */
function InstallmentsDetail({ movement }: { movement: Movement }) {
  const categories = useCategories()
  const category = categories.data?.find((item) => item.id === movement.category_id)?.name
  return (
    <>
      <dl className="grid grid-cols-2 gap-3 rounded-xl bg-white p-4 text-sm shadow-sm ring-1 ring-slate-200">
        <div>
          <dt className="text-xs text-slate-500">Monto total</dt>
          <dd className="text-slate-900 tabular-nums">
            {formatMoney(unsigned(movement.real_amount))}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Fecha</dt>
          <dd className="text-slate-900">{formatShortDate(movement.occurred_on)}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Descripción</dt>
          <dd className="text-slate-900">{movement.description || '—'}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Categoría</dt>
          <dd className="text-slate-900">{category ?? 'Sin categoría'}</dd>
        </div>
      </dl>
      <p className="rounded-lg bg-slate-100 p-3 text-sm text-slate-600">
        Las compras a MSI todavía no se editan: adelantar o liquidar mensualidades llega en la v1.
        Si la capturaste mal, bórrala y captúrala de nuevo.
      </p>
    </>
  )
}

function EditForm({ row, onSaved }: { row: MovementRow; onSaved: () => void }) {
  const queryClient = useQueryClient()
  const categories = useCategories()
  const preferences = usePreferences()
  const commitments = useCommitments()
  const update = useUpdateMovement()

  const isTransfer = row.kind === 'transfer'
  const movement = isTransfer ? row.source : row.movement
  // The destination leg is the positive one; a single movement's sign comes from its type
  const original = {
    amount: unsigned(isTransfer ? row.destination.real_amount : movement.real_amount),
    accounting: unsigned(movement.accounting_amount),
    occurredOn: movement.occurred_on,
    description: movement.description,
    categoryId: movement.category_id ?? '',
    commitmentId: movement.commitment_id ?? '',
  }

  const [amountText, setAmountText] = useState(original.amount)
  // What the preview was asked for: the amount once it's complete (Enter or leaving the field)
  const [committedAmountText, setCommittedAmountText] = useState(original.amount)
  // Typed by hand; null follows the stored amount or, after a change, the suggestion
  const [accountingText, setAccountingText] = useState<string | null>(null)
  const [occurredOn, setOccurredOn] = useState(original.occurredOn)
  const [description, setDescription] = useState(original.description)
  const [categoryId, setCategoryId] = useState(original.categoryId)
  const [commitmentId, setCommitmentId] = useState(original.commitmentId)
  const [error, setError] = useState<string | null>(null)
  const formRef = useRef<HTMLFormElement>(null)

  const savingsMode = preferences.data?.mode === 'savings'
  const showAccounting = savingsMode && !isTransfer
  // Pending commitments, plus the one this expense already pays
  const commitmentChoices = (commitments.data ?? []).filter(
    (item) => item.paid_by_movement_id === null || item.paid_by_movement_id === movement.id,
  )
  const showCommitment = savingsMode && movement.type === 'expense' && commitmentChoices.length > 0
  const commitmentChanged = showCommitment && commitmentId !== original.commitmentId

  /**
   * Savings mode asks for the suggested accounting amount once the amount or the commitment
   * changes: left out, the API would reset it to the real amount. Its warnings aren't used:
   * the preview would count the old amount twice (docs/PLANEACION.md, Nov 14).
   */
  function previewFor(text: string): MovementPreviewRequest | null {
    const amount = parseAmountInput(text)
    if (!showAccounting || amount === null) return null
    if (amount === original.amount && !commitmentChanged) return null
    return {
      account_id: movement.account_id,
      type: movement.type === 'income' ? 'income' : 'expense',
      amount,
      commitment_id: showCommitment && commitmentId ? commitmentId : null,
    }
  }
  const previewBody = previewFor(amountText)
  const committedBody = previewFor(committedAmountText)
  const preview = usePreview(committedBody)
  // Only a reply for what's on screen: not one for an amount being changed
  const suggestion =
    committedBody !== null && JSON.stringify(committedBody) === JSON.stringify(previewBody)
      ? (preview.data?.suggested_accounting_amount ?? null)
      : null
  const accountingValue =
    accountingText ?? (previewBody === null ? original.accounting : (suggestion ?? ''))

  async function suggestionNow(body: MovementPreviewRequest): Promise<string | null> {
    try {
      return (await queryClient.query(previewQuery(body))).suggested_accounting_amount
    } catch {
      // Left out, the API uses the real amount (or the commitment's, if larger)
      return null
    }
  }

  async function save() {
    setCommittedAmountText(amountText)
    const amount = parseAmountInput(amountText)
    if (amount === null) {
      setError('Escribe un monto mayor a 0, con hasta 2 decimales.')
      return
    }
    // Only what changed: fields left out stay as they are
    const body: MovementUpdate = {}
    if (amount !== original.amount) body.amount = amount
    if (occurredOn && occurredOn !== original.occurredOn) body.occurred_on = occurredOn
    if (description !== original.description) body.description = description
    if (!isTransfer) {
      if (categoryId !== original.categoryId) body.category_id = categoryId || null
      if (commitmentChanged) body.commitment_id = commitmentId || null
      if (showAccounting && accountingText !== null && accountingText.trim() !== '') {
        const typed = parseAmountInput(accountingText)
        if (typed === null) {
          setError('El contable debe ser un monto mayor a 0, con hasta 2 decimales.')
          return
        }
        body.accounting_amount = typed
      } else if (previewBody !== null) {
        const suggested = await suggestionNow(previewBody)
        if (suggested !== null) body.accounting_amount = suggested
      }
    }

    setError(null)
    if (Object.keys(body).length === 0) {
      onSaved()
      return
    }
    try {
      await update.mutateAsync({ id: movement.id, body })
    } catch (caught) {
      // The panel stays open, so the amount can be fixed (e.g. over the credit limit)
      setError(caught instanceof Error ? caught.message : 'No se pudo guardar.')
      return
    }
    onSaved()
  }

  // Enter goes to the next field and saves on the last one; Ctrl+Enter saves from anywhere
  function handleKeyDown(event: KeyboardEvent<HTMLFormElement>) {
    if (event.key !== 'Enter' || !(event.target instanceof HTMLElement)) return
    const target = event.target
    if (event.ctrlKey || event.metaKey) {
      event.preventDefault()
      void save()
      return
    }
    if (target.dataset.field === undefined) return
    event.preventDefault()
    setCommittedAmountText(amountText)
    const fields = [...(formRef.current?.querySelectorAll<HTMLElement>('[data-field]') ?? [])]
    const next = fields.at(fields.indexOf(target) + 1)
    if (next && fields.indexOf(target) !== -1) next.focus()
    else void save()
  }

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
      <label className={labelClass}>
        Monto
        <input
          data-field="amount"
          type="text"
          inputMode="decimal"
          autoComplete="off"
          value={amountText}
          onChange={(event) => {
            setAmountText(event.target.value)
          }}
          onBlur={() => {
            setCommittedAmountText(amountText)
          }}
          className={`${fieldBase} text-lg tabular-nums`}
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
            value={accountingValue}
            onChange={(event) => {
              setAccountingText(event.target.value)
            }}
            className={`${fieldClass} tabular-nums`}
          />
          <span className="mt-1 block text-xs font-normal text-slate-400">
            {accountingText !== null
              ? 'Escrito a mano.'
              : previewBody === null
                ? 'El que tiene guardado.'
                : 'Redondeo sugerido para el monto nuevo.'}
          </span>
        </label>
      )}

      {!isTransfer && (
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
            {commitmentChoices.map((commitment) => (
              <option key={commitment.id} value={commitment.id}>
                {commitment.name} · {formatMoney(commitment.amount)}
              </option>
            ))}
          </select>
        </label>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
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

      {error && (
        <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={update.isPending}
        className="w-full rounded-lg bg-sky-600 px-4 py-3 font-semibold text-white hover:bg-sky-700 disabled:opacity-60"
      >
        {update.isPending ? 'Guardando…' : 'Guardar cambios'}{' '}
        <kbd className="hidden text-xs opacity-75 sm:inline">Ctrl+Enter</kbd>
      </button>
    </form>
  )
}
