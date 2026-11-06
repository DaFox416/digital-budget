import { useEffect, useState } from 'react'

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

function App() {
  const [status, setStatus] = useState<ApiStatus>('checking')

  useEffect(() => {
    const controller = new AbortController()

    fetch('/api/v1/health', { signal: controller.signal })
      .then((response) => {
        setStatus(response.ok ? 'ok' : 'down')
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setStatus('down')
      })

    return () => {
      controller.abort()
    }
  }, [])

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
        <h1 className="text-2xl font-semibold text-slate-900">Digital Budget</h1>
        <p className="mt-1 text-sm text-slate-500">Finanzas personales para México</p>

        <div className="mt-6 flex items-center gap-2 text-sm text-slate-700">
          <span className={`h-2.5 w-2.5 rounded-full ${statusColor[status]}`} aria-hidden="true" />
          <span>
            API: <strong>{statusLabel[status]}</strong>
          </span>
        </div>
      </div>
    </main>
  )
}

export default App
