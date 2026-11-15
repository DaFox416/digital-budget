import { useEffect, useState } from 'react'

import { ApiError } from '../../api/client'
import { useRestoreMovement } from '../../api/mutations'
import type { Movement } from '../../api/types'

// Long enough to notice it and reach the button on a phone
export const UNDO_MS = 8000

interface UndoToastProps {
  movement: Movement
  // The delete is still on its way: undoing now would find nothing to restore
  deleting: boolean
  // The delete failed (the row is back in the list)
  deleteError: Error | null
  onClose: () => void
}

/** "Movimiento borrado · Deshacer", for a few seconds after a delete. */
export function UndoToast({ movement, deleting, deleteError, onClose }: UndoToastProps) {
  const restore = useRestoreMovement()
  const [restoreError, setRestoreError] = useState<string | null>(null)
  // Errors stay until closed: the steps to fix a refused undo take a while to read
  const stays = restore.isPending || restoreError !== null || deleteError !== null

  useEffect(() => {
    if (stays) return
    const timer = setTimeout(onClose, UNDO_MS)
    return () => {
      clearTimeout(timer)
    }
  }, [stays, onClose])

  async function undo() {
    try {
      await restore.mutateAsync(movement.id)
    } catch (caught) {
      setRestoreError(restoreMessage(caught, movement))
      return
    }
    onClose()
  }

  return (
    <div
      role="status"
      className="fixed inset-x-4 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-30 rounded-xl bg-slate-900 p-3 text-sm text-white shadow-lg sm:right-auto sm:bottom-4 sm:w-96"
    >
      {deleteError ? (
        <p>No se pudo borrar: {deleteError.message}</p>
      ) : restoreError ? (
        <div className="space-y-2" role="alert">
          {restoreError.split('\n').map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-between gap-3">
          <p>Movimiento borrado</p>
          <button
            type="button"
            onClick={() => void undo()}
            disabled={deleting || restore.isPending}
            className="rounded-lg px-3 py-1.5 font-semibold text-sky-300 hover:bg-white/10 disabled:opacity-60"
          >
            {restore.isPending ? 'Deshaciendo…' : 'Deshacer'}
          </button>
        </div>
      )}
      {stays && !restore.isPending && (
        <button
          type="button"
          onClick={onClose}
          className="mt-2 rounded-lg px-3 py-1.5 text-slate-300 ring-1 ring-white/20 hover:bg-white/10"
        >
          Cerrar
        </button>
      )}
    </div>
  )
}

/**
 * Why the undo was refused, one step per line. The backend checks the commitment first, so a
 * 409 for a movement without one can only be the card's credit limit.
 */
function restoreMessage(caught: unknown, movement: Movement): string {
  if (!(caught instanceof ApiError)) return 'No se pudo deshacer. Revisa tu conexión.'
  if (caught.status !== 409 || movement.commitment_id !== null) {
    return `No se pudo deshacer: ${caught.message}`
  }
  // The amount comes formatted in the API's message ("by $1,234.00"); shown as is
  const excess = /\$[\d,]+\.\d{2}/.exec(caught.message)?.[0]
  return [
    `No se puede deshacer: esta compra ya no cabe en el crédito disponible de la tarjeta${
      excess ? ` (se pasa por ${excess})` : ''
    }.`,
    'Para corregirlo a mano:',
    '1. Borra las compras posteriores de esta tarjeta que no debieron aceptarse.',
    '2. Captura de nuevo esta compra.',
    '3. Captura de nuevo las compras que sí ocurrieron.',
  ].join('\n')
}
