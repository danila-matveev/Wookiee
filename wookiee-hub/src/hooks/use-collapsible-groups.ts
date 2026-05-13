// useCollapsibleGroups — Notion-style collapsible group headers (W9.6).
//
// Stores collapsed group keys in a Set<string> and persists them to
// localStorage under `catalog-<page>-collapsed-groups-v1`.  When the
// available group keys change (filters / groupBy switch), stale keys
// are kept in storage but simply not surfaced — they get pruned the
// next time the user toggles a group.
//
// API:
//   const { isCollapsed, toggle, collapseAll, expandAll } =
//     useCollapsibleGroups("matrix")
//   <button onClick={() => toggle("TELOWAY")}>…</button>
//   { !isCollapsed("TELOWAY") && rows.map(...) }

import { useCallback, useEffect, useState } from "react"

const STORAGE_PREFIX = "catalog-"
const STORAGE_SUFFIX = "-collapsed-groups-v1"

function readStorage(page: string): Set<string> {
  if (typeof window === "undefined") return new Set()
  try {
    const raw = window.localStorage.getItem(`${STORAGE_PREFIX}${page}${STORAGE_SUFFIX}`)
    if (!raw) return new Set()
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return new Set()
    return new Set(parsed.filter((v): v is string => typeof v === "string"))
  } catch {
    return new Set()
  }
}

function writeStorage(page: string, collapsed: Set<string>): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(
      `${STORAGE_PREFIX}${page}${STORAGE_SUFFIX}`,
      JSON.stringify(Array.from(collapsed)),
    )
  } catch {
    /* quota / private mode — non-fatal */
  }
}

export interface CollapsibleGroupsApi {
  /** Returns true when the group with the given key is currently collapsed. */
  isCollapsed: (key: string) => boolean
  /** Toggles the collapsed state for a single group key. */
  toggle: (key: string) => void
  /** Collapses every group key in the provided list. */
  collapseAll: (keys: string[]) => void
  /** Expands every group key in the provided list (clears storage). */
  expandAll: () => void
  /** Number of currently collapsed groups (for UX badges). */
  collapsedCount: number
}

export function useCollapsibleGroups(page: string): CollapsibleGroupsApi {
  const [collapsed, setCollapsed] = useState<Set<string>>(() => readStorage(page))

  // If the page key ever changes (rare — components don't usually swap it),
  // re-hydrate from storage.
  useEffect(() => {
    setCollapsed(readStorage(page))
  }, [page])

  // Persist after every mutation.
  useEffect(() => {
    writeStorage(page, collapsed)
  }, [page, collapsed])

  const isCollapsed = useCallback(
    (key: string) => collapsed.has(key),
    [collapsed],
  )

  const toggle = useCallback((key: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }, [])

  const collapseAll = useCallback((keys: string[]) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      for (const k of keys) next.add(k)
      return next
    })
  }, [])

  const expandAll = useCallback(() => {
    setCollapsed(new Set())
  }, [])

  return {
    isCollapsed,
    toggle,
    collapseAll,
    expandAll,
    collapsedCount: collapsed.size,
  }
}
