import { useEffect, useMemo, useRef, useState } from "react"
import type React from "react"
import {
  ArrowDown,
  ArrowUp,
  Eye,
  EyeOff,
  GripVertical,
  RotateCcw,
  Search,
  Sliders,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Описание колонки реестра каталога.
 *
 * Используется и в новой UI-компоненте `<ColumnConfig />` (W9.5), и в legacy
 * `<ColumnsManager />` — поэтому форма namespace-совместима с ним.
 */
export interface CatalogColumnDef {
  /** Уникальный ключ колонки (стабильный, ASCII). */
  key: string
  /** Русский лейбл, отображаемый и в шапке таблицы, и в конфигураторе. */
  label: string
  /** Видимость по умолчанию (для первой инициализации/сброса). */
  default: boolean
  /** Опциональный badge в попапе конфигуратора (например, "канал"). */
  badge?: string
  /** Группа колонок (для секционирования в попапе). Например: "Идентификация", "Атрибуты". */
  group?: string
}

interface ColumnConfigProps {
  /** Полный реестр колонок страницы (все возможные). */
  columns: CatalogColumnDef[]
  /** Текущий упорядоченный список видимых ключей. */
  order: string[]
  /** Карта видимости по ключам (включает скрытые). Если ключа нет — считаем true для colы в `order`, иначе false. */
  visibility: Record<string, boolean>
  /** Колбэк применения изменений (controlled). */
  onChange: (next: { visibility: Record<string, boolean>; order: string[] }) => void
  /** Сброс к стандартному виду — список default-видимых ключей в дефолтном порядке. */
  onReset: () => void
  /** Заголовок попапа. */
  title?: string
}

/**
 * ColumnConfig — единый конфигуратор колонок для всех реестров каталога (W9.5).
 *
 * Возможности:
 * - чекбокс видимости на каждой колонке (включая «недоступные сейчас»);
 * - drag-and-drop ручкой (HTML5 native — без зависимости от @dnd-kit/sortable);
 * - move-up / move-down кнопки как accessibility fallback;
 * - поиск внутри списка колонок (показывается, если колонок > 15);
 * - кнопка «Сбросить к стандартному виду» (вызывает `onReset`).
 *
 * Persistence — за пределами компонента: храните `visibility`+`order` в хуке
 * `useColumnConfig(pageKey, defaultColumns)`.
 */
export function ColumnConfig({
  columns, order, visibility, onChange, onReset, title = "Колонки",
}: ColumnConfigProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState("")
  const [dragKey, setDragKey] = useState<string | null>(null)
  const [dragOverKey, setDragOverKey] = useState<string | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  // Close popover on outside click / Escape
  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onDoc)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDoc)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  const isVisible = (key: string): boolean => {
    if (visibility[key] !== undefined) return visibility[key]
    return order.includes(key)
  }

  // Visible/active list (preserves `order`), inactive list (registry order).
  const activeKeys = useMemo(
    () => order.filter((k) => columns.find((c) => c.key === k) && isVisible(k)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [order, columns, visibility],
  )
  const inactiveCols = useMemo(
    () => columns.filter((c) => !activeKeys.includes(c.key)),
    [columns, activeKeys],
  )

  const showSearch = columns.length > 15
  const lcSearch = search.trim().toLowerCase()
  const matches = (label: string, key: string) =>
    !lcSearch ||
    label.toLowerCase().includes(lcSearch) ||
    key.toLowerCase().includes(lcSearch)

  const applyChange = (nextOrder: string[], nextVisibility: Record<string, boolean>) => {
    onChange({ order: nextOrder, visibility: nextVisibility })
  }

  const toggle = (key: string) => {
    const nextVis = { ...visibility, [key]: !isVisible(key) }
    let nextOrder = order.slice()
    // If turning ON and key is not in order — append at end.
    if (nextVis[key] && !nextOrder.includes(key)) nextOrder = [...nextOrder, key]
    // If turning OFF — keep in order so re-enable restores position.
    applyChange(nextOrder, nextVis)
  }

  const move = (key: string, dir: -1 | 1) => {
    const idx = activeKeys.indexOf(key)
    if (idx < 0) return
    const target = idx + dir
    if (target < 0 || target >= activeKeys.length) return
    const newActive = activeKeys.slice()
    ;[newActive[idx], newActive[target]] = [newActive[target], newActive[idx]]
    // Compose new order: active in new order + inactive (preserve original `order` for inactive).
    const inactiveOrdered = order.filter((k) => !newActive.includes(k))
    applyChange([...newActive, ...inactiveOrdered], visibility)
  }

  // HTML5 native DnD — без зависимости от @dnd-kit/sortable.
  const onDragStart = (key: string) => (e: React.DragEvent) => {
    setDragKey(key)
    e.dataTransfer.effectAllowed = "move"
    // Firefox требует setData; пустая строка часто игнорируется.
    try { e.dataTransfer.setData("text/plain", key) } catch { /* noop */ }
  }
  const onDragOver = (key: string) => (e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = "move"
    if (dragOverKey !== key) setDragOverKey(key)
  }
  const onDragLeave = () => setDragOverKey(null)
  const onDrop = (overKey: string) => (e: React.DragEvent) => {
    e.preventDefault()
    const src = dragKey
    setDragKey(null)
    setDragOverKey(null)
    if (!src || src === overKey) return
    const srcIdx = activeKeys.indexOf(src)
    const dstIdx = activeKeys.indexOf(overKey)
    if (srcIdx < 0 || dstIdx < 0) return
    const next = activeKeys.slice()
    next.splice(srcIdx, 1)
    next.splice(dstIdx, 0, src)
    const inactiveOrdered = order.filter((k) => !next.includes(k))
    applyChange([...next, ...inactiveOrdered], visibility)
  }
  const onDragEnd = () => {
    setDragKey(null)
    setDragOverKey(null)
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((p) => !p)}
        className="px-2.5 py-1 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5 border border-stone-200"
        title={title}
      >
        <Sliders className="w-3 h-3" />
        Колонки
        <span className="text-stone-400 tabular-nums">({activeKeys.length}/{columns.length})</span>
      </button>
      {open && (
        <div className="absolute top-full right-0 mt-1 w-80 bg-white border border-stone-200 rounded-lg shadow-lg z-30 max-h-[480px] flex flex-col">
          {/* Header */}
          <div className="px-3 py-2 border-b border-stone-100 flex items-center justify-between gap-2">
            <div className="text-[10px] uppercase tracking-wider text-stone-400">{title}</div>
            <button
              type="button"
              onClick={() => { onReset(); setSearch("") }}
              className="text-[11px] text-stone-500 hover:text-stone-900 flex items-center gap-1"
              title="Сбросить к стандартному виду"
            >
              <RotateCcw className="w-3 h-3" />
              Сбросить
            </button>
          </div>

          {/* Search */}
          {showSearch && (
            <div className="px-2 pt-2 pb-1 border-b border-stone-100 shrink-0">
              <div className="relative">
                <Search className="w-3 h-3 text-stone-400 absolute left-2 top-1/2 -translate-y-1/2" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Найти колонку…"
                  className="w-full pl-7 pr-2 py-1 text-xs border border-stone-200 rounded-md outline-none focus:border-stone-400"
                />
              </div>
            </div>
          )}

          {/* Scrollable body */}
          <div className="overflow-y-auto flex-1">
            {/* Active section */}
            <div className="p-2 border-b border-stone-100">
              <div className="text-[10px] uppercase tracking-wider text-stone-400 px-1.5 mb-1.5">
                Активные · перетаскивайте порядок
              </div>
              {activeKeys.length === 0 && (
                <div className="px-1.5 py-2 text-xs text-stone-400 italic">
                  Все колонки скрыты — выберите хотя бы одну ниже.
                </div>
              )}
              {activeKeys.map((key, i) => {
                const col = columns.find((c) => c.key === key)
                if (!col) return null
                if (!matches(col.label, key)) return null
                const isDragging = dragKey === key
                const isOver = dragOverKey === key && dragKey !== key
                return (
                  <div
                    key={key}
                    draggable
                    onDragStart={onDragStart(key)}
                    onDragOver={onDragOver(key)}
                    onDragLeave={onDragLeave}
                    onDrop={onDrop(key)}
                    onDragEnd={onDragEnd}
                    className={cn(
                      "flex items-center gap-1.5 px-1.5 py-1 rounded select-none",
                      isDragging && "opacity-40",
                      isOver
                        ? "bg-stone-100 ring-1 ring-stone-300"
                        : "hover:bg-stone-50",
                    )}
                  >
                    <GripVertical className="w-3 h-3 text-stone-300 shrink-0 cursor-grab active:cursor-grabbing" />
                    <Eye className="w-3 h-3 text-emerald-600 shrink-0" />
                    <span className="text-sm text-stone-700 flex-1 truncate">{col.label}</span>
                    {col.badge && (
                      <span className="text-[9px] uppercase tracking-wider text-stone-400 mr-1">
                        {col.badge}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => move(key, -1)}
                      disabled={i === 0}
                      className="p-0.5 hover:bg-stone-200 rounded disabled:opacity-30 disabled:cursor-default"
                      aria-label="Переместить вверх"
                    >
                      <ArrowUp className="w-3 h-3 text-stone-500" />
                    </button>
                    <button
                      type="button"
                      onClick={() => move(key, 1)}
                      disabled={i === activeKeys.length - 1}
                      className="p-0.5 hover:bg-stone-200 rounded disabled:opacity-30 disabled:cursor-default"
                      aria-label="Переместить вниз"
                    >
                      <ArrowDown className="w-3 h-3 text-stone-500" />
                    </button>
                    <button
                      type="button"
                      onClick={() => toggle(key)}
                      className="p-0.5 hover:bg-red-50 rounded"
                      aria-label="Скрыть колонку"
                    >
                      <X className="w-3 h-3 text-stone-400 hover:text-red-600" />
                    </button>
                  </div>
                )
              })}
            </div>

            {/* Hidden section */}
            {inactiveCols.length > 0 && (
              <div className="p-2">
                <div className="text-[10px] uppercase tracking-wider text-stone-400 px-1.5 mb-1.5">
                  Скрытые
                </div>
                {inactiveCols
                  .filter((c) => matches(c.label, c.key))
                  .map((col) => (
                    <button
                      type="button"
                      key={col.key}
                      onClick={() => toggle(col.key)}
                      className={cn(
                        "w-full flex items-center gap-1.5 px-1.5 py-1 hover:bg-stone-50 rounded text-left",
                      )}
                    >
                      <div className="w-3 h-3" />
                      <EyeOff className="w-3 h-3 text-stone-400 shrink-0" />
                      <span className="text-sm text-stone-500 flex-1 truncate">{col.label}</span>
                      {col.badge && (
                        <span className="text-[9px] uppercase tracking-wider text-stone-400">
                          {col.badge}
                        </span>
                      )}
                    </button>
                  ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
