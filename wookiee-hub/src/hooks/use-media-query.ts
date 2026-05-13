import { useEffect, useState } from "react"

/**
 * SSR-safe media query hook. Subscribes to viewport changes for the given query
 * and returns the current match state. Used by responsive layouts that need to
 * pick between e.g. inline split-pane (≥1024px) and Drawer fallback (<1024px).
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState<boolean>(() =>
    typeof window !== "undefined" ? window.matchMedia(query).matches : false,
  )

  useEffect(() => {
    if (typeof window === "undefined") return
    const mql = window.matchMedia(query)
    const onChange = () => setMatches(mql.matches)
    // Sync once on mount in case `query` changed.
    setMatches(mql.matches)
    mql.addEventListener("change", onChange)
    return () => mql.removeEventListener("change", onChange)
  }, [query])

  return matches
}
