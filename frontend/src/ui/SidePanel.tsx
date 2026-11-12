import {
  useEffect,
  useId,
  useRef,
  type KeyboardEvent,
  type MouseEvent,
  type ReactNode,
} from 'react'

interface SidePanelProps {
  title: string
  onClose: () => void
  children: ReactNode
}

/** Full screen on phones, a side panel from sm (640 px). Esc or a click outside closes it. */
export function SidePanel({ title, onClose, children }: SidePanelProps) {
  const titleId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)

  // The focus goes into the panel, so Esc reaches it and the keyboard starts there. Unless
  // something inside already took it (the capture form focuses its tabs)
  useEffect(() => {
    const dialog = dialogRef.current
    if (dialog && !dialog.contains(document.activeElement)) dialog.focus()
  }, [])

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
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="flex h-full w-full flex-col overflow-y-auto bg-slate-50 shadow-xl outline-none sm:max-w-md"
      >
        <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
          <h2 id={titleId} className="text-base font-semibold text-slate-900">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-sm text-slate-500 hover:bg-slate-100"
          >
            Cerrar <kbd className="text-xs text-slate-400">Esc</kbd>
          </button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  )
}
