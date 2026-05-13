// W9.4 + W9.16 — Compact Notion-style filter bar for catalog registries.
//
// Заменяет «тяжёлые» открытые блоки фильтров на горизонтальную панель
// chip-кнопок. Каждая кнопка открывает popover со списком чекбоксов
// (+ поиск внутри popover, если опций > 10). Активные фильтры подсвечены и
// показывают счётчик (например, `Бренд · 2`). Справа — кнопка «Сбросить все»,
// если хоть один фильтр активен.
//
// Используется на 3 реестрах: /catalog (matrix), /catalog/artikuly,
// /catalog/tovary. Состояние выбора — `values: Record<key, string[]>`
// (значения сериализуются как строки, чтобы их можно было класть в URL params
// или sets без танцев с дженериками).

import { useMemo, useRef, useState, useEffect } from "react"
import { Check, ChevronDown, Search, X } from "lucide-react"

// ─── Public types ──────────────────────────────────────────────────────────

export interface FilterBarOption {
  /** Сериализованное значение фильтра. */
  value: string
  /** Подпись опции в popover. */
  label: string
  /** Необязательный счётчик (число записей с этим значением). */
  count?: number
}

export interface FilterBarFilter {
  /** Уникальный ключ фильтра (используется в `values`). */
  key: string
  /** Подпись на chip-кнопке. */
  label: string
  /** Опции для multi-select popover. */
  options: FilterBarOption[]
  /** Если задано — заголовок поиска внутри popover. По умолчанию `label`. */
  searchPlaceholder?: string
}

export interface FilterBarProps {
  /** Список фильтров (рендерятся слева направо). */
  filters: FilterBarFilter[]
  /** Текущее состояние выбранных значений по каждому ключу. */
  values: Record<string, string[]>
  /** Колбэк изменения значений конкретного фильтра. */
  onChange: (key: string, values: string[]) => void
  /** Колбэк сброса всех фильтров (опционально — если не задан, по «Сбросить все» зануляем последовательно). */
  onResetAll?: () => void
  /** Дополнительный className контейнера. */
  className?: string
}

// ─── Single chip with popover ──────────────────────────────────────────────

interface FilterChipProps {
  filter: FilterBarFilter
  selected: string[]
  onChange: (values: string[]) => void
}

function FilterChip({ filter, selected, onChange }: FilterChipProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const containerRef = useRef<HTMLDivElement | null>(null)
  const searchInputRef = useRef<HTMLInputElement | null>(null)
  const showSearch = filter.options.length > 10

  // Close popover on outside click + Escape.
  useEffect(() => {
    if (!open) return
    function onDocDown(e: MouseEvent) {
      if (!containerRef.current) return
      if (!containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onDocDown)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDocDown)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  // Autofocus search input when popover opens.
  useEffect(() => {
    if (!open || !showSearch) return
    const t = setTimeout(() => searchInputRef.current?.focus(), 30)
    return () => clearTimeout(t)
  }, [open, showSearch])

  const filteredOptions = useMemo(() => {
    if (!query.trim()) return filter.options
    const q = query.trim().toLowerCase()
    return filter.options.filter((o) => o.label.toLowerCase().includes(q))
  }, [filter.options, query])

  const selectedSet = useMemo(() => new Set(selected), [selected])
  const active = selected.length > 0

  function toggle(value: string) {
    const next = new Set(selectedSet)
    if (next.has(value)) next.delete(value)
    else next.add(value)
    onChange(Array.from(next))
  }

  function clearOne() {
    onChange([])
  }

  const chipClass = active
    ? "bg-stone-900 text-white border-stone-900"
    : "text-stone-700 hover:bg-stone-100 border-stone-200 bg-white"

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`px-2.5 py-1 text-xs rounded-md border transition-colors flex items-center gap-1.5 ${chipClass}`}
      >
        <span>{filter.label}</span>
        {active && (
          <span
            className={`text-[10px] tabular-nums rounded px-1 ${
              active ? "bg-white/15 text-white" : "bg-stone-100 text-stone-500"
            }`}
          >
            {selected.length}
          </span>
        )}
        <ChevronDown
          className={`w-3 h-3 transition-transform ${active ? "text-white/80" : "text-stone-400"} ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>
      {open && (
        <div className="absolute left-0 top-full mt-1 z-30 w-64 bg-white border border-stone-200 rounded-md shadow-lg flex flex-col max-h-[320px]">
          {showSearch && (
            <div className="px-2 pt-2 pb-1.5 border-b border-stone-100 shrink-0">
              <div className="relative">
                <Search className="w-3 h-3 text-stone-400 absolute left-2 top-1/2 -translate-y-1/2" />
                <input
                  ref={searchInputRef}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={filter.searchPlaceholder ?? `Поиск: ${filter.label.toLowerCase()}…`}
                  className="w-full pl-6 pr-2 py-1 text-xs border border-stone-200 rounded outline-none focus:border-stone-400"
                />
              </div>
            </div>
          )}
          <div className="flex-1 overflow-y-auto py-1">
            {filteredOptions.length === 0 ? (
              <div className="px-3 py-2 text-xs text-stone-400 italic">Ничего не найдено</div>
            ) : (
              filteredOptions.map((o) => {
                const isSelected = selectedSet.has(o.value)
                return (
                  <button
                    key={o.value}
                    type="button"
                    onClick={() => toggle(o.value)}
                    className="w-full flex items-center gap-2 px-2.5 py-1.5 text-xs text-left hover:bg-stone-50"
                  >
                    <span
                      className={`w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0 ${
                        isSelected ? "bg-stone-900 border-stone-900" : "bg-white border-stone-300"
                      }`}
                    >
                      {isSelected && <Check className="w-2.5 h-2.5 text-white" />}
                    </span>
                    <span className="flex-1 truncate text-stone-700">{o.label}</span>
                    {o.count != null && (
                      <span className="text-[10px] tabular-nums text-stone-400">{o.count}</span>
                    )}
                  </button>
                )
              })
            )}
          </div>
          {active && (
            <div className="border-t border-stone-100 px-2 py-1.5 shrink-0">
              <button
                type="button"
                onClick={clearOne}
                className="w-full text-[11px] text-stone-500 hover:text-stone-800 flex items-center justify-center gap-1 py-1 rounded hover:bg-stone-50"
              >
                <X className="w-3 h-3" /> Сбросить «{filter.label}»
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── FilterBar root ────────────────────────────────────────────────────────

export function FilterBar({ filters, values, onChange, onResetAll, className = "" }: FilterBarProps) {
  const hasAnyActive = useMemo(
    () => Object.values(values).some((arr) => Array.isArray(arr) && arr.length > 0),
    [values],
  )

  function handleResetAll() {
    if (onResetAll) {
      onResetAll()
      return
    }
    for (const f of filters) {
      if ((values[f.key]?.length ?? 0) > 0) onChange(f.key, [])
    }
  }

  if (filters.length === 0) return null

  return (
    <div className={`flex items-center gap-1.5 flex-wrap ${className}`}>
      {filters.map((f) => (
        <FilterChip
          key={f.key}
          filter={f}
          selected={values[f.key] ?? []}
          onChange={(next) => onChange(f.key, next)}
        />
      ))}
      {hasAnyActive && (
        <button
          type="button"
          onClick={handleResetAll}
          className="ml-1 text-[11px] text-stone-500 hover:text-stone-800 underline underline-offset-2"
        >
          Сбросить все
        </button>
      )}
    </div>
  )
}
