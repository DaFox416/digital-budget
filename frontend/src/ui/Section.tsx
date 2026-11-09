import type { ReactNode } from 'react'

interface SectionProps {
  title: string
  children: ReactNode
  className?: string
}

export function Section({ title, children, className = '' }: SectionProps) {
  return (
    <section aria-label={title} className={className}>
      <h2 className="mb-3 text-sm font-semibold tracking-wide text-slate-500 uppercase">{title}</h2>
      {children}
    </section>
  )
}

export function LoadingState() {
  return (
    <p role="status" className="animate-pulse rounded-xl bg-white p-4 text-sm text-slate-400">
      Cargando…
    </p>
  )
}

interface ErrorStateProps {
  error: Error
  onRetry: () => void
}

/** Each section shows its own error, so one failing request doesn't blank the whole page. */
export function ErrorState({ error, onRetry }: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="rounded-xl bg-rose-50 p-4 text-sm text-rose-800 ring-1 ring-rose-200"
    >
      <p>No se pudo cargar: {error.message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-2 rounded-lg bg-white px-3 py-1 font-medium ring-1 ring-rose-300 hover:bg-rose-100"
      >
        Reintentar
      </button>
    </div>
  )
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-xl bg-white p-4 text-sm text-slate-500 ring-1 ring-slate-200">
      {children}
    </p>
  )
}
