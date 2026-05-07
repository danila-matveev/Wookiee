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

export interface SearchGlobalResult {
  models?: CommandResult[]
  colors?: CommandResult[]
  articles?: CommandResult[]
  skus?: CommandResult[]
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
          ...(r.models ?? []),
          ...(r.colors ?? []),
          ...(r.articles ?? []),
          ...(r.skus ?? []),
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
      className="fixed inset-0 z-50 bg-stone-900/40 flex items-start justify-center pt-[10vh]"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl bg-white rounded-xl shadow-2xl overflow-hidden border border-stone-200"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 py-3 border-b border-stone-200">
          <Search className="w-4 h-4 text-stone-400 shrink-0" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Найти модель, цвет, баркод, артикул…"
            className="flex-1 outline-none text-sm placeholder:text-stone-400 bg-transparent"
          />
          <kbd className="text-[10px] text-stone-400 border border-stone-300 rounded px-1 py-0.5">
            esc
          </kbd>
        </div>
        <div className="max-h-96 overflow-y-auto">
          {!query && (
            <div className="p-6 text-center text-sm text-stone-400">Начните печатать</div>
          )}
          {query && loading && (
            <div className="p-6 text-center text-sm text-stone-400">Поиск…</div>
          )}
          {query && !loading && results.length === 0 && (
            <div className="p-6 text-center text-sm text-stone-400">Ничего не найдено</div>
          )}
          {grouped.map((group) => (
            <div key={group.category}>
              <div className="px-4 pt-2 pb-1 text-[10px] uppercase tracking-wider text-stone-400 font-medium bg-stone-50/50">
                {group.category}
              </div>
              {group.items.map((r) => (
                <button
                  type="button"
                  key={`${group.category}-${r.id}`}
                  onClick={() => handlePick(r)}
                  className={cn(
                    "w-full px-4 py-2.5 hover:bg-stone-50 flex items-center gap-3 text-left",
                    "border-b border-stone-100 last:border-0",
                  )}
                >
                  {r.hex && <ColorSwatch hex={r.hex} />}
                  <span className="font-medium text-stone-900 text-sm font-mono shrink-0">
                    {r.label}
                  </span>
                  {r.sub && (
                    <span className="text-xs text-stone-500 truncate">{r.sub}</span>
                  )}
                  <ChevronRight className="w-3.5 h-3.5 text-stone-300 ml-auto shrink-0" />
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
