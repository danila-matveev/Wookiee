import { useEffect } from "react"

/**
 * Per-route document.title — improves screen-reader announcement on navigation
 * and gives meaningful browser-tab labels (WCAG SC 2.4.2 Level A).
 *
 * Usage: call at the top of a page component with the route-specific suffix-less
 * title; the hook appends " — Wookiee Hub" and restores the previous title on
 * unmount, so tab-switching between routes stays correct.
 */
export function useDocumentTitle(title: string): void {
  useEffect(() => {
    const prev = document.title
    document.title = title ? `${title} — Wookiee Hub` : "Wookiee Hub"
    return () => {
      document.title = prev
    }
  }, [title])
}
