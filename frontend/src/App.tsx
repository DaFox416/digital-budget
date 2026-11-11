import { useCallback, useState } from 'react'

import { useHealth } from './api/queries'
import { CapturePanel } from './capture/CapturePanel'
import { useNewShortcut } from './capture/useNewShortcut'
import { AccountList } from './features/accounts/AccountList'
import { MovementList } from './features/movements/MovementList'
import { SummaryFigures } from './features/summary/SummaryFigures'
import { Section } from './ui/Section'

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
      API: {statusLabel[status]}
    </p>
  )
}

function App() {
  const [capturing, setCapturing] = useState(false)
  const openCapture = useCallback(() => {
    setCapturing(true)
  }, [])
  useNewShortcut(openCapture, !capturing)

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
              className="rounded-lg bg-sky-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-sky-700"
            >
              Nuevo <kbd className="hidden text-xs opacity-75 sm:inline">N</kbd>
            </button>
          </div>
        </div>
      </header>

      {/* One column on phones; accounts and movements side by side from lg (1024 px) */}
      <main className="mx-auto max-w-5xl space-y-6 px-4 py-6">
        <Section title="Resumen">
          <SummaryFigures />
        </Section>
        <div className="grid gap-6 lg:grid-cols-[1fr_1.5fr]">
          <Section title="Cuentas">
            <AccountList />
          </Section>
          <Section title="Movimientos">
            <MovementList />
          </Section>
        </div>
      </main>

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
