import { useEffect } from 'react'

/** True while typing somewhere, where "n" is a letter and not a shortcut. */
function isTyping(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))
  )
}

/** The N key opens the capture panel, unless a field has the focus or a modifier is held. */
export function useNewShortcut(onNew: () => void, enabled: boolean): void {
  useEffect(() => {
    if (!enabled) return
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key.toLowerCase() !== 'n') return
      if (event.ctrlKey || event.metaKey || event.altKey || isTyping(event.target)) return
      // Otherwise the "n" would land in the amount field that gets the focus
      event.preventDefault()
      onNew()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [onNew, enabled])
}
