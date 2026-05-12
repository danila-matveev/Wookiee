import { useEffect, useRef, useState } from "react"
import { ChevronRight, Search } from "lucide-react"
import { cn } from "@/lib/utils"
import { ColorSwatch } from "./color-swatch"

export type CommandResultCategory = "Модели" | "Цвета" | "Артикулы" | "SKU"

export interface CommandResult {
  id: string | number
  category: CommandResultCategory
  label: string
  sub?: string
  /** Optional hex preview for color rows. */
  hex?: string
  /** Navigation target (e.g. /catalog/matrix/Vuki). */
  target?: string
  /** Custom on-pick handler — called with the full result. */
  onPick?: (r: CommandResult) => void
}

/**
 * SearchGlobalResult — flexible shape so both the live service (raw DB rows)
 * and tests/demo (already-shaped CommandResult[]) work.  Each bucket is `any[]`
 * because the service returns rows like `{id, kod, color_code, ...}` that we
 * adapt to CommandResult inside the palette.
 */
export interface SearchGlobalResult {
  models?: any[]
  colors?: any[]
  articles?: any[]
  skus?: any[]
}

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
  /** Called when user picks a result; defaults to navigation via `target`. */
  onPick?: (r: CommandResult) => void
  /** Override the search function (for tests/demo). Default — service.searchGlobal. */
  searchFn?: (query: string) => Promise<SearchGlobalResult>
}

const DEBOUNCE_MS = 200

const CATEGORY_ORDER: CommandResultCategory[] = ["Модели", "Цвета", "Артикулы", "SKU"]

/**
 * CommandPalette — глобальный поиск ⌘K.
 * Дебаунс 200ms, категории Модели/Цвета/Артикулы/SKU.
 */
export function CommandPalette({ open, onClose, onPick, searchFn }: CommandPaletteProps) {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<CommandResult[]>([])
  const [loading, setLoading] = useState(false)
  const debounceRef = useRef<number | null>(null)

  // Reset state when modal opens
  useEffect(() => {
    if (open) {
      setQuery("")
      setResults([])
    }
  }, [open])

  // Esc closes
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, onClose])

  // Debounced search
  useEffect(() => {
    if (!open) return
    const q = query.trim()
    if (debounceRef.current) {
      window.clearTimeout(debounceRef.current)
      debounceRef.current = null
    }
    if (!q) {
      setResults([])
      setLoading(false)
      return
    }
    setLoading(true)
    debounceRef.current = window.setTimeout(async () => {
      try {
        const fn = searchFn ?? (await loadSearchGlobal())
        if (!fn) {
          setResults([])
          return
        }
        const r = await fn(q)
        const flat: CommandResult[] = [
          ...adaptModels(r.models),
          ...adaptColors(r.colors),
          ...adaptArticles(r.articles),
          ...adaptSkus(r.skus),
        ]
        setResults(flat)
      } catch {
        setResults([])
      } finally {
        setLoading(false)
      }
    }, DEBOUNCE_MS)

    return () => {
      if (debounceRef.current) {
        window.clearTimeout(debounceRef.current)
        debounceRef.current = null
      }
    }
  }, [query, open, searchFn])

  if (!open) return null

  const grouped = CATEGORY_ORDER.map((cat) => ({
    category: cat,
    items: results.filter((r) => r.category === cat),
  })).filter((g) => g.items.length > 0)

  const handlePick = (r: CommandResult) => {
    if (r.onPick) r.onPick(r)
    else if (onPick) onPick(r)
    else if (r.target && typeof window !== "undefined") {
      window.location.href = r.target
    }
    onClose()
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-[var(--color-text-primary)]/40 flex items-start justify-center pt-[10vh]"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl bg-elevated rounded-xl shadow-2xl overflow-hidden border border-default"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 py-3 border-b border-default">
          <Search className="w-4 h-4 text-label shrink-0" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Найти модель, цвет, баркод, артикул…"
            className="flex-1 outline-none text-sm placeholder:text-label bg-transparent text-primary"
          />
          <kbd className="text-[10px] text-label border border-strong rounded px-1 py-0.5">
            esc
          </kbd>
        </div>
        <div className="max-h-96 overflow-y-auto">
          {!query && (
            <div className="p-6 text-center text-sm text-label">Начните печатать</div>
          )}
          {query && loading && (
            <div className="p-6 text-center text-sm text-label">Поиск…</div>
          )}
          {query && !loading && results.length === 0 && (
            <div className="p-6 text-center text-sm text-label">Ничего не найдено</div>
          )}
          {grouped.map((group) => (
            <div key={group.category}>
              <div className="px-4 pt-2 pb-1 text-[10px] uppercase tracking-wider text-label font-medium bg-surface-muted">
                {group.category}
              </div>
              {group.items.map((r) => (
                <button
                  type="button"
                  key={`${group.category}-${r.id}`}
                  onClick={() => handlePick(r)}
                  className={cn(
                    "w-full px-4 py-2.5 hover:bg-surface-muted flex items-center gap-3 text-left",
                    "border-b border-subtle last:border-0",
                  )}
                >
                  {r.hex && <ColorSwatch hex={r.hex} />}
                  <span className="font-medium text-primary text-sm font-mono shrink-0">
                    {r.label}
                  </span>
                  {r.sub && (
                    <span className="text-xs text-muted truncate">{r.sub}</span>
                  )}
                  <ChevronRight className="w-3.5 h-3.5 text-label ml-auto shrink-0" />
                </button>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

/**
 * Lazy-load service.searchGlobal via dynamic import (no hard dep until A2 lands).
 * TODO(A2): replace with direct import once service exports it.
 */
async function loadSearchGlobal(): Promise<
  ((q: string) => Promise<SearchGlobalResult>) | null
> {
  try {
    const mod = (await import("@/lib/catalog/service")) as Record<string, unknown>
    const fn = mod.searchGlobal as
      | ((q: string) => Promise<SearchGlobalResult>)
      | undefined
    return fn ?? null
  } catch {
    return null
  }
}

// ─── Adapters: raw service rows → CommandResult ────────────────────────────
// The service returns shapes like `{id, kod, nazvanie_etiketka}` for models,
// `{id, color_code, cvet, color}` for colors, etc.  We also accept rows that
// are already CommandResult-shaped (for tests/demo).

function isCommandResult(x: unknown): x is CommandResult {
  return !!x && typeof x === "object" && "category" in x && "label" in x
}

function adaptModels(rows: unknown[] = []): CommandResult[] {
  return rows.map((row) => {
    if (isCommandResult(row)) return row
    const r = row as { id: number; kod: string; nazvanie_etiketka?: string | null }
    return {
      id: `model-${r.id}`,
      category: "Модели",
      label: r.kod,
      sub: r.nazvanie_etiketka ?? undefined,
      target: `/catalog/matrix?model=${encodeURIComponent(r.kod)}`,
    }
  })
}

function adaptColors(rows: unknown[] = []): CommandResult[] {
  return rows.map((row) => {
    if (isCommandResult(row)) return row
    const r = row as { id: number; color_code: string; cvet?: string | null; color?: string | null }
    const sub = [r.cvet, r.color].filter(Boolean).join(" / ") || undefined
    return {
      id: `color-${r.id}`,
      category: "Цвета",
      label: r.color_code,
      sub,
      target: `/catalog/colors?color=${r.id}`,
    }
  })
}

function adaptArticles(rows: unknown[] = []): CommandResult[] {
  return rows.map((row) => {
    if (isCommandResult(row)) return row
    const r = row as {
      id: number
      artikul: string
      nomenklatura_wb?: number | null
      artikul_ozon?: string | null
    }
    const sub = [
      r.nomenklatura_wb ? `WB ${r.nomenklatura_wb}` : null,
      r.artikul_ozon ? `OZON ${r.artikul_ozon}` : null,
    ]
      .filter(Boolean)
      .join(" · ") || undefined
    return {
      id: `art-${r.id}`,
      category: "Артикулы",
      label: r.artikul,
      sub,
      target: `/catalog/artikuly?id=${r.id}`,
    }
  })
}

function adaptSkus(rows: unknown[] = []): CommandResult[] {
  return rows.map((row) => {
    if (isCommandResult(row)) return row
    const r = row as { id: number; barkod: string; barkod_gs1?: string | null }
    return {
      id: `sku-${r.id}`,
      category: "SKU",
      label: r.barkod,
      sub: r.barkod_gs1 ? `GS1 ${r.barkod_gs1}` : undefined,
      target: `/catalog/tovary?id=${r.id}`,
    }
  })
}
