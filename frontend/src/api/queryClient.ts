import { QueryClient } from '@tanstack/react-query'

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Data counts as fresh for 30 s: switching tabs or screens doesn't refetch right away
        staleTime: 30_000,
        // One retry: enough for a hiccup, quick to show an error when the backend is down
        retry: 1,
      },
    },
  })
}
