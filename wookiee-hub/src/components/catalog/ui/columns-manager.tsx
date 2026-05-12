import { useEffect, useRef, useState } from "react"
import {
  ArrowDown,
  ArrowUp,
  Eye,
  EyeOff,
  GripVertical,
  Sliders,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"

export interface ColumnDef {
  key: string
  label: string
  /** Default visibility — used on first load when no preference is stored. */
  default: boolean
  /** Optional badge (e.g. "канал" for channel-status columns in MVP). */
  badge?: string
}

interface ColumnsManagerProps {
  columns: ColumnDef[]
  /** Current visible-keys order — controlled. */
  value: string[]
  onChange: (visible: string[]) => void
  /** Persistence: ui_preferences scope (e.g. 'tovary-table'). */
  scope?: string
  /** Persistence: ui_preferences key (e.g. 'visible-columns'). */
  storageKey?: string
}

/**
 * ColumnsManager — popover чекбоксов с drag/move-up/move-down,
 * стилизация и логика 1:1 с MVP wookiee_matrix_mvp_v4.jsx.
 *
 * Persistence — controlled by parent (consume `value` + `onChange`).
 * If `scope` and `storageKey` provided — the manager will lazy-load initial
 * preference via service.getUiPref / setUiPref. Until A2 lands those exports,
 * we do a runtime feature-detect via dynamic import (no hard dep).
 *
 * TODO(A2): replace dynamic import with direct `import { getUiPref, setUiPref } from
 * "@/lib/catalog/service"` once the service module exports them.
 */
export function ColumnsManager({
  columns, value, onChange, scope, storageKey,
}: ColumnsManagerProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const hydratedRef = useRef(false)

  // Close popover on outside click
  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", onDoc)
    return () => document.removeEventListener("mousedown", onDoc)
  }, [open])

  // Lazy-load persisted preference (best-effort; no-op if service not wired yet)
  useEffect(() => {
    if (hydratedRef.current) return
    if (!scope || !storageKey) return
    hydratedRef.current = true
    void (async () => {
      try {
        const mod = (await import("@/lib/catalog/service")) as Record<string, unknown>
        const getter = mod.getUiPref as
          | ((scope: string, key: string) => Promise<unknown>)
          | undefined
        if (!getter) return
        const stored = await getter(scope, storageKey)
        if (Array.isArray(stored) && stored.every((x) => typeof x === "string")) {
          onChange(stored as string[])
        }
      } catch {
        // service.getUiPref not implemented yet — keep current value
      }
    })()
    // We intentionally run this once per scope/key.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, storageKey])

  const persist = async (next: string[]) => {
    onChange(next)
    if (!scope || !storageKey) return
    try {
      const mod = (await import("@/lib/catalog/service")) as Record<string, unknown>
      const setter = mod.setUiPref as
        | ((scope: string, key: string, value: unknown) => Promise<void>)
        | undefined
      if (setter) await setter(scope, storageKey, next)
    } catch {
      // best-effort persistence
    }
  }

  const move = (key: string, dir: -1 | 1) => {
    const idx = value.indexOf(key)
    if (idx < 0) return
    const newIdx = idx + dir
    if (newIdx < 0 || newIdx >= value.length) return
    const next = [...value]
    ;[next[idx], next[newIdx]] = [next[newIdx], next[idx]]
    void persist(next)
  }

  const toggle = (key: string) => {
    const next = value.includes(key)
      ? value.filter((k) => k !== key)
      : [...value, key]
    void persist(next)
  }

  const orderedActive = value.filter((k) => columns.find((c) => c.key === k))
  const inactive = columns.filter((c) => !value.includes(c.key))

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((p) => !p)}
        className="px-2.5 py-1 text-xs text-secondary hover:bg-surface-muted rounded-md flex items-center gap-1.5 border border-default"
      >
        <Sliders className="w-3 h-3" />
        Колонки
        <span className="text-label tabular-nums">({value.length})</span>
      </button>
      {open && (
        <div className="absolute top-full right-0 mt-1 w-72 bg-elevated border border-default rounded-lg shadow-lg z-30 max-h-96 overflow-y-auto">
          <div className="p-2 border-b border-subtle">
            <div className="text-[10px] uppercase tracking-wider text-label px-1.5 mb-1.5">
              Активные · перетаскивайте порядок
            </div>
            {orderedActive.map((key, i) => {
              const col = columns.find((c) => c.key === key)
              if (!col) return null
              return (
                <div
                  key={key}
                  className="flex items-center gap-1.5 px-1.5 py-1 hover:bg-surface-muted rounded"
                >
                  <GripVertical className="w-3 h-3 text-label shrink-0" />
                  <Eye className="w-3 h-3 text-success shrink-0" />
                  <span className="text-sm text-secondary flex-1 truncate">{col.label}</span>
                  <button
                    type="button"
                    onClick={() => move(key, -1)}
                    disabled={i === 0}
                    className="p-0.5 hover:bg-surface-muted rounded disabled:opacity-30 disabled:cursor-default"
                    aria-label="Move up"
                  >
                    <ArrowUp className="w-3 h-3 text-muted" />
                  </button>
                  <button
                    type="button"
                    onClick={() => move(key, 1)}
                    disabled={i === orderedActive.length - 1}
                    className="p-0.5 hover:bg-surface-muted rounded disabled:opacity-30 disabled:cursor-default"
                    aria-label="Move down"
                  >
                    <ArrowDown className="w-3 h-3 text-muted" />
                  </button>
                  <button
                    type="button"
                    onClick={() => toggle(key)}
                    className="p-0.5 hover:bg-danger-soft rounded"
                    aria-label="Hide column"
                  >
                    <X className="w-3 h-3 text-label hover:text-danger" />
                  </button>
                </div>
              )
            })}
          </div>
          {inactive.length > 0 && (
            <div className="p-2">
              <div className="text-[10px] uppercase tracking-wider text-label px-1.5 mb-1.5">
                Скрытые
              </div>
              {inactive.map((col) => (
                <button
                  type="button"
                  key={col.key}
                  onClick={() => toggle(col.key)}
                  className={cn(
                    "w-full flex items-center gap-1.5 px-1.5 py-1 hover:bg-surface-muted rounded text-left",
                  )}
                >
                  <div className="w-3 h-3" />
                  <EyeOff className="w-3 h-3 text-label shrink-0" />
                  <span className="text-sm text-muted flex-1 truncate">{col.label}</span>
                  {col.badge && (
                    <span className="text-[9px] uppercase tracking-wider text-label">
                      {col.badge}
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
