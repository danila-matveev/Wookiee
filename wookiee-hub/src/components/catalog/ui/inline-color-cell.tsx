// W9.10 — Inline-edit ячейка для выбора цвета.
// W10.34 — popover открывается по double-click + hover-индикатор (карандаш).
//
// Поведение:
// - Read mode: показывает текущий цвет (свотч + код + название).
// - ДВОЙНОЙ клик — открывает popover с ColorPicker (single mode), отфильтрованным
//   по categoryId.  Single-click игнорируется — защита от случайной правки.
//   В правом краю при hover видна иконка карандаша.
// - Выбор цвета → onCommit(cvet_id) → save → закрытие popover.
// - Esc / клик вне popover — закрытие без сохранения.
// - При ошибке — alert(translateError(e)), popover остаётся открытым.

import { useCallback, useEffect, useRef, useState } from "react"
import { Loader2, Pencil } from "lucide-react"
import { ColorPicker } from "@/components/catalog/ui/color-picker"
import { ColorSwatch } from "@/components/catalog/ui/color-swatch"
import { swatchColor } from "@/lib/catalog/color-utils"
import { translateError } from "@/lib/catalog/error-translator"
import { toast } from "@/lib/catalog/toast"

export interface InlineColorCellProps {
  /** Текущий cvet_id (null если не выставлен). */
  currentCvetId: number | null
  /** Текущий код цвета (для read-mode отображения). */
  currentColorCode: string | null
  /** Текущее RU-название цвета (для read-mode отображения). */
  currentColorName?: string | null
  /** Текущий hex (для свотча). */
  currentHex?: string | null
  /** Категория модели → фильтр палитры (W9.12). null → все цвета. */
  categoryId: number | null
  /** Применить новый cvet_id. */
  onCommit: (cvetId: number) => Promise<void>
}

/**
 * InlineColorCell — popover-редактор цвета артикула.
 *
 * Используется в `/catalog/artikuly` (колонка `cvet`).  Берёт categoryId
 * с уровня модели (modeli_osnova.kategoriya_id) и передаёт в ColorPicker
 * — палитра отфильтрована, как в модалке create-artikul (W9.12).
 */
export function InlineColorCell({
  currentCvetId, currentColorCode, currentColorName, currentHex,
  categoryId, onCommit,
}: InlineColorCellProps) {
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

  const onSelect = useCallback(async (id: number) => {
    if (saving) return
    if (id === currentCvetId) {
      setOpen(false)
      return
    }
    setSaving(true)
    try {
      await onCommit(id)
      setOpen(false)
    } catch (e) {
      toast.error(translateError(e))
    } finally {
      setSaving(false)
    }
  }, [currentCvetId, onCommit, saving])

  const swatch = currentHex ?? swatchColor(currentColorCode ?? "")

  return (
    <div className="relative inline-flex items-center gap-1.5 min-w-0" ref={ref} onClick={(e) => e.stopPropagation()}>
      <button
        type="button"
        onDoubleClick={() => setOpen((p) => !p)}
        title="Двойной клик — изменить цвет"
        className="group relative flex items-center gap-1.5 min-w-0 rounded px-1 -mx-1 py-0.5 pr-5 hover:bg-stone-100 hover:ring-1 hover:ring-stone-300 transition-colors"
      >
        <ColorSwatch hex={swatch} size={14} />
        <span className="font-mono text-xs text-stone-700 truncate">{currentColorCode ?? "—"}</span>
        {currentColorName && (
          <span className="text-stone-500 text-xs truncate">{currentColorName}</span>
        )}
        {saving && <Loader2 className="w-3 h-3 text-stone-400 animate-spin shrink-0" />}
        {!saving && (
          <Pencil
            aria-hidden="true"
            className="pointer-events-none absolute right-1 top-1/2 -translate-y-1/2 w-3 h-3 text-stone-400 opacity-0 group-hover:opacity-100 transition-opacity"
          />
        )}
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 w-72 bg-white border border-stone-200 rounded-lg shadow-lg z-30 p-2">
          <div className="px-1 pb-2 border-b border-stone-100 mb-2 flex items-center justify-between">
            <div className="text-[10px] uppercase tracking-wider text-stone-400">
              Цвет артикула
            </div>
            {saving && <Loader2 className="w-3 h-3 text-stone-400 animate-spin" />}
          </div>
          <ColorPicker
            mode="single"
            categoryId={categoryId}
            value={currentCvetId}
            onChange={onSelect}
            className="grid grid-cols-1 gap-1 max-h-72 overflow-y-auto pr-1"
          />
        </div>
      )}
    </div>
  )
}
