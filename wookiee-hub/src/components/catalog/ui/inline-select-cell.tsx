// W9.10 — Inline-edit ячейка типа «select» (выбор из списка).
//
// Используется для редактирования razmer_id на /catalog/tovary
// и других fields, где значение — id из справочника.

import { useCallback, useEffect, useRef, useState } from "react"
import { Loader2 } from "lucide-react"
import { translateError } from "@/lib/catalog/error-translator"
import { toast } from "@/lib/catalog/toast"

export interface InlineSelectOption<TValue extends string | number = number> {
  value: TValue
  label: string
}

export interface InlineSelectCellProps<TValue extends string | number = number> {
  /** Текущее значение (id или null). */
  value: TValue | null
  /** Список опций. */
  options: ReadonlyArray<InlineSelectOption<TValue>>
  /** Применить новое значение. */
  onCommit: (next: TValue) => Promise<void>
  /** Текст в read-mode, когда значения нет. */
  placeholder?: string
  /** CSS-класс для отображения метки в read-mode (font-mono / size). */
  className?: string
  /** Подпись над списком (например, «Размер»). */
  popoverLabel?: string
  /** Hint-tooltip над read-mode кнопкой. */
  hint?: string
  /** Запрещает редактирование. */
  disabled?: boolean
  /** Если задано — рендер пользовательской read-mode метки (вместо стандартной). */
  renderDisplay?: (currentLabel: string | null) => React.ReactNode
}

export function InlineSelectCell<TValue extends string | number = number>({
  value, options, onCommit, placeholder = "—",
  className = "", popoverLabel, hint, disabled = false, renderDisplay,
}: InlineSelectCellProps<TValue>) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
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

  const currentLabel = options.find((o) => o.value === value)?.label ?? null

  const onSelect = useCallback(async (next: TValue) => {
    if (saving) return
    if (next === value) {
      setOpen(false)
      return
    }
    setSaving(true)
    try {
      await onCommit(next)
      setOpen(false)
    } catch (e) {
      toast.error(translateError(e))
    } finally {
      setSaving(false)
    }
  }, [onCommit, saving, value])

  return (
    <div className="relative inline-block min-w-0" ref={ref} onClick={(e) => e.stopPropagation()}>
      <button
        type="button"
        onClick={() => !disabled && setOpen((p) => !p)}
        disabled={disabled}
        title={hint ?? "Кликните, чтобы изменить"}
        className={
          "text-left rounded px-1 -mx-1 py-0.5 " +
          "hover:bg-stone-100 hover:ring-1 hover:ring-stone-300 " +
          "disabled:hover:bg-transparent disabled:hover:ring-0 disabled:cursor-default " +
          "transition-colors flex items-center gap-1"
        }
      >
        {renderDisplay ? renderDisplay(currentLabel) : (
          currentLabel != null ? (
            <span className={className}>{currentLabel}</span>
          ) : (
            <span className="text-stone-400 italic text-xs">{placeholder}</span>
          )
        )}
        {saving && <Loader2 className="w-3 h-3 text-stone-400 animate-spin shrink-0" />}
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 w-44 bg-white border border-stone-200 rounded-lg shadow-lg z-30">
          {popoverLabel && (
            <div className="p-2 border-b border-stone-100 text-[10px] uppercase tracking-wider text-stone-400">
              {popoverLabel}
            </div>
          )}
          <div className="p-1 max-h-72 overflow-y-auto">
            {options.length === 0 && (
              <div className="px-2 py-3 text-xs text-stone-400 italic">Нет опций</div>
            )}
            {options.map((opt) => (
              <button
                key={String(opt.value)}
                type="button"
                disabled={saving}
                onClick={() => onSelect(opt.value)}
                className="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-stone-50 rounded text-left text-xs disabled:opacity-50"
              >
                <span className="font-mono">{opt.label}</span>
                {opt.value === value && (
                  <span className="ml-auto text-[10px] text-emerald-600">текущий</span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
