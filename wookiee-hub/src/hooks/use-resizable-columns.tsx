// useResizableColumns — drag-resize <th> columns with persistence via ui_preferences.
//
// Usage:
//   const cols = [
//     { id: "name", defaultWidth: 220 },
//     { id: "status", defaultWidth: 120 },
//   ]
//   const { widths, bindResizer, ColGroup } = useResizableColumns("matrix.modeli", cols)
//
//   <table>
//     <ColGroup />
//     <thead>
//       <tr>
//         <th style={{ position: "relative" }}>
//           Name
//           <span {...bindResizer("name")} />
//         </th>
//       </tr>
//     </thead>
//   </table>
//
// Persistence: widths are stored in ui_preferences(scope=pageKey, key="column_widths") as
// JSON { [columnId]: pixelWidth }. Writes are debounced ~300ms; loads happen once on mount.
//
// Min width: 40px. Max width: 600px.

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type { ReactElement } from "react"
import { getUiPref, setUiPref } from "@/lib/catalog/service"

export interface ResizableColumn {
  id: string
  defaultWidth: number
}

export interface ResizerBindings {
  /** Mouse-down on a 4px grab strip at the right edge of <th> starts the drag. */
  onMouseDown: (e: React.MouseEvent<HTMLElement>) => void
  /** className with the right-edge cursor styling. */
  className: string
  /** role="separator" + aria-orientation for a11y. */
  role: "separator"
  "aria-orientation": "vertical"
  "aria-label": string
  /** Stop click propagation — don't let header sort etc. fire. */
  onClick: (e: React.MouseEvent<HTMLElement>) => void
}

const MIN_WIDTH = 40
const MAX_WIDTH = 600
const DEBOUNCE_MS = 300

function clamp(value: number): number {
  if (Number.isNaN(value)) return MIN_WIDTH
  return Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, Math.round(value)))
}

export interface UseResizableColumns {
  /** Map of columnId -> px width to apply via <col style={{ width }}/>. */
  widths: Record<string, number>
  /** Spread on a small handle element placed at right edge of <th>. */
  bindResizer: (columnId: string) => ResizerBindings
  /** Component that renders <colgroup><col .../>...</colgroup>. Place inside <table>. */
  ColGroup: () => ReactElement
  /** Whether widths have been loaded from server (false while initial fetch is pending). */
  ready: boolean
}

/**
 * Drag-resize table columns + persist widths in ui_preferences.
 * pageKey is the scope (e.g. "matrix.modeli", "artikuly", "tovary").
 */
export function useResizableColumns(pageKey: string, columns: ResizableColumn[]): UseResizableColumns {
  // Defaults are pure function of the columns argument.
  const defaults = useMemo<Record<string, number>>(() => {
    const acc: Record<string, number> = {}
    for (const c of columns) acc[c.id] = clamp(c.defaultWidth)
    return acc
  }, [columns])

  const [widths, setWidths] = useState<Record<string, number>>(defaults)
  const [ready, setReady] = useState(false)

  // Keep latest widths in a ref so debounced flush always sees fresh state.
  const widthsRef = useRef(widths)
  widthsRef.current = widths

  const loadedRef = useRef(false)
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const dragStateRef = useRef<{ columnId: string; startX: number; startWidth: number } | null>(null)

  // Load saved widths once on mount, merge over defaults.
  useEffect(() => {
    if (loadedRef.current) return
    loadedRef.current = true
    getUiPref<Record<string, number>>(pageKey, "column_widths")
      .then((saved) => {
        if (saved && typeof saved === "object") {
          setWidths((prev) => {
            const next = { ...prev }
            for (const c of columns) {
              const v = saved[c.id]
              if (typeof v === "number") next[c.id] = clamp(v)
            }
            return next
          })
        }
      })
      .catch(() => { /* non-fatal — defaults already applied */ })
      .finally(() => setReady(true))
    // pageKey and columns intentionally captured once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Debounced persist.
  const schedulePersist = useCallback(() => {
    if (flushTimerRef.current) clearTimeout(flushTimerRef.current)
    flushTimerRef.current = setTimeout(() => {
      flushTimerRef.current = null
      setUiPref(pageKey, "column_widths", widthsRef.current).catch(() => {
        /* non-fatal */
      })
    }, DEBOUNCE_MS)
  }, [pageKey])

  // Cleanup any pending timer on unmount.
  useEffect(() => {
    return () => {
      if (flushTimerRef.current) clearTimeout(flushTimerRef.current)
    }
  }, [])

  // Global mousemove/mouseup listeners while dragging.
  useEffect(() => {
    function onMove(e: MouseEvent) {
      const drag = dragStateRef.current
      if (!drag) return
      const delta = e.clientX - drag.startX
      const next = clamp(drag.startWidth + delta)
      setWidths((prev) => (prev[drag.columnId] === next ? prev : { ...prev, [drag.columnId]: next }))
    }
    function onUp() {
      if (!dragStateRef.current) return
      dragStateRef.current = null
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
      // Persist on mouseup (and the debounced one running during drag).
      schedulePersist()
    }
    window.addEventListener("mousemove", onMove)
    window.addEventListener("mouseup", onUp)
    return () => {
      window.removeEventListener("mousemove", onMove)
      window.removeEventListener("mouseup", onUp)
    }
  }, [schedulePersist])

  const bindResizer = useCallback(
    (columnId: string): ResizerBindings => ({
      onMouseDown: (e: React.MouseEvent<HTMLElement>) => {
        e.preventDefault()
        e.stopPropagation()
        const startWidth = widthsRef.current[columnId] ?? defaults[columnId] ?? 120
        dragStateRef.current = { columnId, startX: e.clientX, startWidth }
        document.body.style.cursor = "col-resize"
        document.body.style.userSelect = "none"
      },
      onClick: (e) => {
        e.stopPropagation()
      },
      className:
        "absolute right-0 top-0 h-full w-1 cursor-col-resize select-none bg-transparent hover:bg-stone-300/70 active:bg-stone-400 transition-colors",
      role: "separator",
      "aria-orientation": "vertical",
      "aria-label": `Изменить ширину колонки ${columnId}`,
    }),
    [defaults],
  )

  // Schedule persist whenever widths change after the initial load. Skip the
  // first post-ready effect run (it reflects freshly-loaded server state).
  const firstAfterReadyRef = useRef(true)
  useEffect(() => {
    if (!ready) return
    if (firstAfterReadyRef.current) {
      firstAfterReadyRef.current = false
      return
    }
    schedulePersist()
  }, [widths, ready, schedulePersist])

  const ColGroup = useCallback((): ReactElement => {
    return (
      <colgroup>
        {columns.map((c) => (
          <col key={c.id} style={{ width: `${widths[c.id] ?? defaults[c.id]}px` }} />
        ))}
      </colgroup>
    )
  }, [columns, widths, defaults])

  return { widths, bindResizer, ColGroup, ready }
}
