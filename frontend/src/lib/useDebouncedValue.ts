import { useEffect, useState } from 'react'

/**
 * The value once it stops changing for `delay` ms. The preview waits for the typing to pause
 * instead of calling the API on every key.
 */
export function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(value)
    }, delay)
    return () => {
      clearTimeout(timer)
    }
  }, [value, delay])
  return debounced
}
