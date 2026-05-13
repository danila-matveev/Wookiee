import { useEffect, useMemo, useRef, useState } from "react"
import {
  DndContext,
  type DragEndEvent,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core"
import { CSS } from "@dnd-kit/utilities"
import {
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
 * W9.5 — единый конфигуратор колонок для реестров каталога.
 *
 * Поддерживает два режима использования:
 *
 * 1) Расширенный (рекомендуемый, новые места):
 *    передать `state` от хука `useColumnConfig` — компонент сам управляет
 *    видимостью/порядком, drag-and-drop, сбросом и поиском.
 *
 * 2) Совместимость с W8 API: `columns` (полный набор) + `value` (видимые,
 *    в текущем порядке) + `onChange`. Компонент сам мержит видимость и
 *    порядок в стороннее состояние.
 *
 * Триггер-кнопка стилизована 1:1 с MVP wookiee_matrix_mvp_v4.jsx.
 */

export interface ColumnDef {
  key: string
  label: string
  /** Видимость по умолчанию (используется при первом запуске / Reset). */
  default: boolean
  /** Опциональный бейдж (например «канал» для status-колонок). */
  badge?: string
  /** Опциональная группа для разделения в дропдауне. */
  group?: string
  /** Опциональное описание для подсказки. */
  description?: string
}

interface ColumnConfigHandle {
  order: string[]
  visibility: Record<string, boolean>
  setVisibility: (key: string, visible: boolean) => void
  toggleVisibility: (key: string) => void
  setOrder: (next: string[]) => void
  moveColumn: (fromKey: string, toKey: string) => void
  reset: () => void
  all: ColumnDef[]
}

interface CommonProps {
  /** Открыть конфигуратор по умолчанию (для тестов / dev-демо). */
  defaultOpen?: boolean
}

interface ControlledProps extends CommonProps {
  /** Новый расширенный API: всё состояние идёт через хук. */
  state: ColumnConfigHandle
}

interface LegacyProps extends CommonProps {
  /** Полный набор доступных колонок. */
  columns: ColumnDef[]
  /** Видимые колонки в текущем порядке. */
  value: string[]
  /** Колбэк смены видимых колонок. */
  onChange: (visible: string[]) => void
  /** Опциональный scope/storageKey (no-op в W9.5: контрол ушёл на useColumnConfig). */
  scope?: string
  storageKey?: string
}

type ColumnsManagerProps = ControlledProps | LegacyProps

function isControlled(p: ColumnsManagerProps): p is ControlledProps {
  return "state" in p && p.state != null
}

// Минимальное число колонок, при котором появляется поле поиска внутри popover.
const SEARCH_THRESHOLD = 15

// ─── Sortable row (drag handle + reorder) ─────────────────────────────────

interface SortableRowProps {
  id: string
  index: number
  total: number
  children: React.ReactNode
}

function SortableRow({ id, children }: SortableRowProps) {
  // Use draggable + droppable on the same node to keep API minimal (we don't
  // depend on @dnd-kit/sortable to avoid adding a dependency — drag-end handler
  // reorders by from-key → to-key).
  const { attributes, listeners, setNodeRef: setDragRef, transform, isDragging } =
    useDraggable({ id })
  const { isOver, setNodeRef: setDropRef } = useDroppable({ id })

  const style: React.CSSProperties = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.5 : 1,
    backgroundColor: isOver ? "rgb(245 245 244 / 1)" : undefined, // stone-100
  }

  return (
    <div
      ref={(node) => {
        setDragRef(node)
        setDropRef(node)
      }}
      style={style}
      className="rounded"
    >
      <div className="flex items-center gap-1.5 px-1.5 py-1">
        <button
          type="button"
          {...listeners}
          {...attributes}
          className="cursor-grab active:cursor-grabbing touch-none p-0.5 -m-0.5"
          aria-label="Перетащить для изменения порядка"
        >
          <GripVertical className="w-3 h-3 text-stone-400" />
        </button>
        <div className="flex-1 min-w-0 flex items-center gap-1.5">{children}</div>
      </div>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────

export function ColumnsManager(props: ColumnsManagerProps) {
  const [open, setOpen] = useState(props.defaultOpen ?? false)
  const [query, setQuery] = useState("")
  const popoverRef = useRef<HTMLDivElement>(null)

  // ─── Adapter: legacy → handle-like ──────────────────────────────────────
  const handle: ColumnConfigHandle = useMemo(() => {
    if (isControlled(props)) return props.state
    const { columns, value, onChange } = props
    const visibleSet = new Set(value)
    // Стабильный порядок: сначала видимые в их сохранённом порядке, затем
    // оставшиеся колонки в их исходном порядке.
    const inactive = columns.map((c) => c.key).filter((k) => !visibleSet.has(k))
    const order = [...value.filter((k) => columns.some((c) => c.key === k)), ...inactive]
    const visibility: Record<string, boolean> = {}
    for (const k of order) visibility[k] = visibleSet.has(k)

    const apply = (nextOrder: string[], nextVisibility: Record<string, boolean>) => {
      const nextVisible = nextOrder.filter((k) => nextVisibility[k])
      onChange(nextVisible)
    }

    return {
      order,
      visibility,
      all: columns,
      setVisibility: (key, vis) => {
        const v = { ...visibility, [key]: vis }
        apply(order, v)
      },
      toggleVisibility: (key) => {
        const v = { ...visibility, [key]: !visibility[key] }
        apply(order, v)
      },
      setOrder: (next) => apply(next, visibility),
      moveColumn: (fromKey, toKey) => {
        if (fromKey === toKey) return
        const idxFrom = order.indexOf(fromKey)
        const idxTo = order.indexOf(toKey)
        if (idxFrom < 0 || idxTo < 0) return
        const nextOrder = [...order]
        nextOrder.splice(idxFrom, 1)
        nextOrder.splice(idxTo, 0, fromKey)
        apply(nextOrder, visibility)
      },
      reset: () => {
        // Восстановить дефолтную видимость; порядок — исходный из columns.
        const v: Record<string, boolean> = {}
        for (const c of columns) v[c.key] = c.default
        apply(columns.map((c) => c.key), v)
      },
    }
  }, [props])

  const visibleCount = useMemo(
    () => handle.order.filter((k) => handle.visibility[k]).length,
    [handle.order, handle.visibility],
  )

  // Close popover on outside click.
  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", onDoc)
    return () => document.removeEventListener("mousedown", onDoc)
  }, [open])

  // Escape to close.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [open])

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))

  const handleDragEnd = (e: DragEndEvent) => {
    if (!e.over || !e.active) return
    if (e.active.id === e.over.id) return
    handle.moveColumn(String(e.active.id), String(e.over.id))
  }

  // ─── List filtering (search) ────────────────────────────────────────────
  const showSearch = handle.all.length > SEARCH_THRESHOLD
  const normalizedQuery = query.trim().toLowerCase()
  const matches = (key: string): boolean => {
    if (!normalizedQuery) return true
    const col = handle.all.find((c) => c.key === key)
    if (!col) return false
    return (
      col.key.toLowerCase().includes(normalizedQuery) ||
      col.label.toLowerCase().includes(normalizedQuery)
    )
  }

  // Split active/inactive while preserving the user's order.
  const orderedVisible = handle.order.filter((k) => handle.visibility[k] && matches(k))
  const orderedHidden = handle.order.filter((k) => !handle.visibility[k] && matches(k))

  return (
    <div className="relative" ref={popoverRef}>
      <button
        type="button"
        onClick={() => setOpen((p) => !p)}
        className="px-2.5 py-1 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5 border border-stone-200"
      >
        <Sliders className="w-3 h-3" />
        Колонки
        <span className="text-stone-400 tabular-nums">
          ({visibleCount}/{handle.all.length})
        </span>
      </button>
      {open && (
        <div className="absolute top-full right-0 mt-1 w-80 bg-white border border-stone-200 rounded-lg shadow-lg z-30 max-h-[480px] flex flex-col">
          {/* Header — title + reset */}
          <div className="px-3 py-2 border-b border-stone-100 flex items-center justify-between shrink-0">
            <div className="text-[11px] uppercase tracking-wider text-stone-500">
              Колонки таблицы
            </div>
            <button
              type="button"
              onClick={handle.reset}
              className="px-1.5 py-0.5 text-[11px] text-stone-500 hover:text-stone-900 hover:bg-stone-100 rounded flex items-center gap-1"
              title="Сбросить к стандартному виду"
            >
              <RotateCcw className="w-3 h-3" />
              Сбросить
            </button>
          </div>

          {/* Optional search */}
          {showSearch && (
            <div className="px-2 py-2 border-b border-stone-100 shrink-0">
              <div className="relative">
                <Search className="w-3 h-3 text-stone-400 absolute left-2 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Поиск колонки…"
                  className="w-full pl-7 pr-7 py-1 text-xs border border-stone-200 rounded outline-none focus:border-stone-400"
                />
                {query && (
                  <button
                    type="button"
                    onClick={() => setQuery("")}
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-700"
                    aria-label="Очистить поиск"
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Scrollable list */}
          <div className="overflow-y-auto">
            <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
              {/* Active section */}
              <div className="p-2 border-b border-stone-100">
                <div className="text-[10px] uppercase tracking-wider text-stone-400 px-1.5 mb-1.5">
                  Активные · перетащите для порядка
                </div>
                {orderedVisible.length === 0 ? (
                  <div className="px-1.5 py-2 text-[11px] text-stone-400 italic">
                    {normalizedQuery ? "Ничего не найдено" : "Ни одна колонка не выбрана"}
                  </div>
                ) : (
                  orderedVisible.map((key, i) => {
                    const col = handle.all.find((c) => c.key === key)
                    if (!col) return null
                    return (
                      <SortableRow key={key} id={key} index={i} total={orderedVisible.length}>
                        <Eye className="w-3 h-3 text-emerald-600 shrink-0" />
                        <span
                          className="text-sm text-stone-700 flex-1 truncate"
                          title={col.description || col.label}
                        >
                          {col.label}
                        </span>
                        {col.badge && (
                          <span className="text-[9px] uppercase tracking-wider text-stone-400">
                            {col.badge}
                          </span>
                        )}
                        <button
                          type="button"
                          onClick={() => handle.setVisibility(key, false)}
                          className="p-0.5 hover:bg-red-50 rounded"
                          aria-label="Скрыть колонку"
                          title="Скрыть"
                        >
                          <X className="w-3 h-3 text-stone-400 hover:text-red-600" />
                        </button>
                      </SortableRow>
                    )
                  })
                )}
              </div>
            </DndContext>

            {/* Hidden section */}
            {orderedHidden.length > 0 && (
              <div className="p-2">
                <div className="text-[10px] uppercase tracking-wider text-stone-400 px-1.5 mb-1.5">
                  Скрытые
                </div>
                {orderedHidden.map((key) => {
                  const col = handle.all.find((c) => c.key === key)
                  if (!col) return null
                  return (
                    <button
                      type="button"
                      key={key}
                      onClick={() => handle.setVisibility(key, true)}
                      className={cn(
                        "w-full flex items-center gap-1.5 px-1.5 py-1 hover:bg-stone-50 rounded text-left",
                      )}
                      title={col.description || col.label}
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
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
