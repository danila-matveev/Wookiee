import { useEffect, useState, useRef, useCallback } from "react"

interface ApiQueryResult<T> {
  data: T | null
  loading: boolean
  error: string | null
}

/**
 * Lightweight data-fetching hook.
 *
 * Calls `fetcher` whenever `deps` change, manages loading / error state,
 * and discards stale responses via AbortController.
 */
export function useApiQuery<T>(
  fetcher: () => Promise<T>,
  deps: unknown[],
): ApiQueryResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Keep the latest fetcher ref so we don't need it in deps
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const stableRefetch = useCallback(() => {
    let cancelled = false

    setLoading(true)
    setError(null)

    fetcherRef
      .current()
      .then((result) => {
        if (!cancelled) {
          setData(result)
          setLoading(false)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const message =
            err instanceof Error ? err.message : "Unknown error"
          setError(message)
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    const cleanup = stableRefetch()
    return cleanup
  }, [stableRefetch])

  return { data, loading, error }
}
