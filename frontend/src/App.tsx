import { useCallback, useState } from 'react'

import { useDeleteMovement } from './api/mutations'
import { useAccounts, useHealth } from './api/queries'
import type { Movement } from './api/types'
import { CapturePanel } from './capture/CapturePanel'
import { useNewShortcut } from './capture/useNewShortcut'
import { AccountList } from './features/accounts/AccountList'
import { CardDetail } from './features/cards/CardDetail'
import { EditPanel } from './features/movements/EditPanel'
import { MovementList } from './features/movements/MovementList'
import { UndoToast } from './features/movements/UndoToast'
import { SummaryFigures } from './features/summary/SummaryFigures'
import type { MovementRow } from './lib/movements'
import { Section } from './ui/Section'
import { SidePanel } from './ui/SidePanel'

type ApiStatus = 'checking' | 'ok' | 'down'

const statusLabel: Record<ApiStatus, string> = {
  checking: 'Verificando…',
  ok: 'Conectada',
  down: 'Sin conexión',
}

const statusColor: Record<ApiStatus, string> = {
  checking: 'bg-slate-400',
  ok: 'bg-emerald-500',
  down: 'bg-rose-500',
}

function ApiStatusBadge() {
  const health = useHealth()
  const status: ApiStatus = health.isPending ? 'checking' : health.isError ? 'down' : 'ok'
  return (
    <p className="flex items-center gap-2 text-xs text-slate-500">
      <span className={`h-2 w-2 rounded-full ${statusColor[status]}`} aria-hidden="true" />
      {/* Phones only show the dot; the text stays for screen readers */}
      <span className="sr-only sm:not-sr-only">API: {statusLabel[status]}</span>
    </p>
  )
}

function App() {
  const [capturing, setCapturing] = useState(false)
  const openCapture = useCallback(() => {
    setCapturing(true)
  }, [])
  // The credit card whose detail is open
  const [openCard, setOpenCard] = useState<string | null>(null)
  const openCardName = useAccounts().data?.find((account) => account.id === openCard)?.name
  // The movement open to edit or delete
  const [editing, setEditing] = useState<MovementRow | null>(null)
  // The last deleted movement, while its undo notice shows. `key` restarts the notice (and
  // its timer) when another one is deleted
  const [deleted, setDeleted] = useState<{ movement: Movement; key: number } | null>(null)
  const deleteMovement = useDeleteMovement()
  const closeUndo = useCallback(() => {
    setDeleted(null)
  }, [])
  const noPanel = !capturing && openCard === null && editing === null
  // N doesn't open the capture on top of another panel
  useNewShortcut(openCapture, noPanel)

  function handleDelete(movement: Movement) {
    // No confirmation before: the notice offers to undo it
    setEditing(null)
    setDeleted((last) => ({ movement, key: (last?.key ?? 0) + 1 }))
    deleteMovement.reset()
    deleteMovement.mutate(movement)
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <h1 className="text-lg font-semibold text-slate-900">Digital Budget</h1>
          <div className="flex items-center gap-4">
            <ApiStatusBadge />
            <button
              type="button"
              onClick={openCapture}
              aria-keyshortcuts="N"
              // Phones use the + button at the bottom, within reach of the thumb
              className="hidden rounded-lg bg-sky-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-sky-700 sm:block"
            >
              Nuevo <kbd className="hidden text-xs opacity-75 sm:inline">N</kbd>
            </button>
          </div>
        </div>
      </header>

      {/* One column on phones; accounts and movements side by side from lg (1024 px) */}
      {/* Bottom padding on phones, so the + button doesn't cover the last movement */}
      <main className="mx-auto max-w-5xl space-y-6 px-4 pt-6 pb-24 sm:pb-6">
        <Section title="Resumen">
          <SummaryFigures />
        </Section>
        <div className="grid gap-6 lg:grid-cols-[1fr_1.5fr]">
          <Section title="Cuentas">
            <AccountList onOpenCard={setOpenCard} />
          </Section>
          <Section title="Movimientos">
            <MovementList onOpen={setEditing} />
          </Section>
        </div>
      </main>

      {/* Phones: a big + at the bottom right opens the capture (first step of phase 2's touch
          capture). Hidden while the panel is open, which fills the screen */}
      {noPanel && (
        <button
          type="button"
          onClick={openCapture}
          aria-label="Nuevo movimiento"
          className="fixed right-4 bottom-[calc(1rem+env(safe-area-inset-bottom))] z-10 flex h-14 w-14 items-center justify-center rounded-full bg-sky-600 text-3xl leading-none text-white shadow-lg hover:bg-sky-700 active:bg-sky-800 sm:hidden"
        >
          <span aria-hidden="true">+</span>
        </button>
      )}

      {openCard !== null && (
        <SidePanel
          title={openCardName ?? 'Tarjeta'}
          onClose={() => {
            setOpenCard(null)
          }}
        >
          <CardDetail accountId={openCard} />
        </SidePanel>
      )}

      {editing !== null && (
        <EditPanel
          row={editing}
          onClose={() => {
            setEditing(null)
          }}
          onDelete={handleDelete}
        />
      )}

      {deleted !== null && (
        <UndoToast
          key={deleted.key}
          movement={deleted.movement}
          deleting={deleteMovement.isPending}
          deleteError={deleteMovement.error}
          onClose={closeUndo}
        />
      )}

      {capturing && (
        <CapturePanel
          onClose={() => {
            setCapturing(false)
          }}
        />
      )}
    </div>
  )
}

export default App
