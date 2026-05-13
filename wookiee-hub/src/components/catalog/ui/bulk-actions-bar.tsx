import { useCallback, useEffect, useRef, useState, type ReactNode } from "react"
import { ChevronDown, X } from "lucide-react"
import { cn } from "@/lib/utils"

// ─── Action types (W10.33) ────────────────────────────────────────────────
//
// До W10.33 BulkActionsBar поддерживал только plain-buttons (см. /tovary).
// Параллельно /artikuly использовал собственный bulk-бар, поскольку требовал
// dropdown-popover для выбора статуса. W10.33 объединяет оба варианта в один
// компонент с дискриминированным union-типом:
//
//   - "button"   — обычная кнопка (исходное поведение).
//   - "dropdown" — кнопка с popover-списком опций. Каждая опция — клик с id.
//   - "confirm"  — кнопка с window.confirm() перед выполнением (для удалений).

/** Опция для dropdown-action: id, label и опциональный icon. */
export interface BulkDropdownOption {
  id: string | number
  label: ReactNode
  /** Помечает текущую/выбранную опцию (визуально). */
  current?: boolean
  /** Отключает опцию. */
  disabled?: boolean
}

interface BulkActionBase {
  id: string
  label: string
  icon?: ReactNode
  /** Визуально красит в red (destructive). */
  destructive?: boolean
  /** Отключает action. */
  disabled?: boolean
}

export interface BulkButtonAction extends BulkActionBase {
  type?: "button"
  onClick: () => void
}

export interface BulkDropdownAction extends BulkActionBase {
  type: "dropdown"
  /** Опции popover. */
  options: BulkDropdownOption[]
  /** Callback с id выбранной опции. */
  onSelect: (optionId: string | number) => void
  /** Подпись над списком в popover (e.g. «Статус артикула»). Опционально. */
  popoverTitle?: string
  /** Custom render опции (вместо плоского label). */
  renderOption?: (opt: BulkDropdownOption) => ReactNode
  /** Сообщение когда список пуст. По умолчанию «Нет опций». */
  emptyText?: string
}

export interface BulkConfirmAction extends BulkActionBase {
  type: "confirm"
  /** Текст в window.confirm(). */
  confirmText: string
  onClick: () => void
}

export type BulkAction = BulkButtonAction | BulkDropdownAction | BulkConfirmAction

interface BulkActionsBarProps {
  selectedCount: number
  actions: BulkAction[]
  onClear: () => void
  className?: string
  /** Position: 'sticky-bottom' is the MVP default — pinned to bottom of parent flex container. */
  position?: "sticky-bottom" | "fixed-bottom"
}

/**
 * BulkActionsBar — единый нижний бар для bulk-операций.
 *
 * Поддерживает 3 типа actions:
 *   - "button"   — обычная кнопка (исходное поведение).
 *   - "dropdown" — popover-список опций (статусы, фабрики, категории).
 *   - "confirm"  — кнопка с window.confirm() (для удалений / archive).
 *
 * Spec: «Выбрано: N | actions… | Очистить».
 */
export function BulkActionsBar({
  selectedCount, actions, onClear, className, position = "sticky-bottom",
}: BulkActionsBarProps) {
  if (selectedCount <= 0) return null

  const positionCls = position === "fixed-bottom"
    ? "fixed bottom-0 left-0 right-0 z-40"
    : ""

  return (
    <div
      className={cn(
        "border-t border-stone-200 bg-white px-6 py-3 flex items-center gap-3 shrink-0",
        "shadow-[0_-4px_16px_-8px_rgba(0,0,0,0.08)]",
        positionCls,
        className,
      )}
      onClick={(e) => e.stopPropagation()}
    >
      <span className="text-sm">
        Выбрано: <span className="font-medium tabular-nums">{selectedCount}</span>
      </span>
      <div className="h-5 w-px bg-stone-200" />
      {actions.map((a) => {
        if (a.type === "dropdown") {
          return <DropdownButton key={a.id} action={a} />
        }
        if (a.type === "confirm") {
          return <ConfirmButton key={a.id} action={a} />
        }
        return <PlainButton key={a.id} action={a} />
      })}
      <button
        type="button"
        onClick={onClear}
        className="ml-auto px-3 py-1 text-xs text-stone-500 hover:bg-stone-100 rounded-md flex items-center gap-1.5"
      >
        <X className="w-3 h-3" /> Очистить
      </button>
    </div>
  )
}

// ─── Plain button ─────────────────────────────────────────────────────────

function PlainButton({ action }: { action: BulkButtonAction }) {
  return (
    <button
      type="button"
      onClick={action.onClick}
      disabled={action.disabled}
      className={cn(
        "px-3 py-1 text-xs rounded-md flex items-center gap-1.5",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        action.destructive
          ? "text-red-600 hover:bg-red-50"
          : "text-stone-700 hover:bg-stone-100",
      )}
    >
      {action.icon}
      {action.label}
    </button>
  )
}

// ─── Confirm button ───────────────────────────────────────────────────────

function ConfirmButton({ action }: { action: BulkConfirmAction }) {
  const onClick = useCallback(() => {
    // eslint-disable-next-line no-alert
    if (window.confirm(action.confirmText)) {
      action.onClick()
    }
  }, [action])

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={action.disabled}
      className={cn(
        "px-3 py-1 text-xs rounded-md flex items-center gap-1.5",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        action.destructive
          ? "text-red-600 hover:bg-red-50"
          : "text-stone-700 hover:bg-stone-100",
      )}
    >
      {action.icon}
      {action.label}
    </button>
  )
}

// ─── Dropdown button ──────────────────────────────────────────────────────

function DropdownButton({ action }: { action: BulkDropdownAction }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

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

  const onPick = useCallback((id: string | number) => {
    action.onSelect(id)
    setOpen(false)
  }, [action])

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((p) => !p)}
        disabled={action.disabled}
        className={cn(
          "px-3 py-1 text-xs rounded-md flex items-center gap-1.5",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          action.destructive
            ? "text-red-600 hover:bg-red-50"
            : "text-stone-700 hover:bg-stone-100",
        )}
      >
        {action.icon}
        {action.label}
        <ChevronDown className="w-3 h-3" />
      </button>
      {open && (
        <div className="absolute bottom-9 left-0 z-50 w-56 bg-white border border-stone-200 rounded-md shadow-lg py-1 max-h-72 overflow-y-auto">
          {action.popoverTitle && (
            <div className="px-3 pt-1 pb-1 text-[10px] uppercase tracking-wider text-stone-400 border-b border-stone-100">
              {action.popoverTitle}
            </div>
          )}
          {action.options.length === 0 ? (
            <div className="px-3 py-2 text-xs text-stone-400 italic">
              {action.emptyText ?? "Нет опций"}
            </div>
          ) : (
            action.options.map((opt) => (
              <button
                key={opt.id}
                type="button"
                disabled={opt.disabled}
                onClick={() => onPick(opt.id)}
                className={cn(
                  "w-full text-left px-3 py-1.5 text-xs hover:bg-stone-50 flex items-center gap-2",
                  "disabled:opacity-50 disabled:cursor-not-allowed",
                  opt.current && "bg-stone-50",
                )}
              >
                {action.renderOption ? action.renderOption(opt) : opt.label}
                {opt.current && (
                  <span className="ml-auto text-[10px] text-emerald-600">текущий</span>
                )}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
