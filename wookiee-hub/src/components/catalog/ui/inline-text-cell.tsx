// W9.10 — Inline-edit ячейка с text/number input.
//
// Поведение:
// - Read mode: показывает значение (или плейсхолдер «—»).  По клику переходит
//   в edit mode.
// - Edit mode: input авто-фокусится, текст выделяется.
// - Enter — сохранить (вызвать `onCommit`), Esc — отмена.
// - Blur — сохранить (как Enter), если значение изменилось; иначе закрыть.
// - Во время сохранения input блокируется, показывается мини-спиннер.
// - При ошибке (`onCommit` throws) — input возвращается в edit mode со старым
//   текстом + alert через translateError.
//
// Optimistic update — на стороне вызывающего: он передаёт текущее значение, а
// после успешного `onCommit` вызывает react-query invalidate / patch стейта.

import { useCallback, useEffect, useRef, useState } from "react"
import { Loader2 } from "lucide-react"
import { translateError } from "@/lib/catalog/error-translator"
import { toast } from "@/lib/catalog/toast"

export interface InlineTextCellProps {
  /** Текущее значение из БД. null/undefined — пустое поле. */
  value: string | number | null | undefined
  /**
   * Сохранить новое значение.  Получает `string`, либо `null` если поле очищено.
   * Должен бросить — ошибка покажется через alert(translateError(e)).
   */
  onCommit: (next: string | null) => Promise<void>
  /** Плейсхолдер в read-mode (по умолчанию «—»). */
  placeholder?: string
  /** Тип input-а (text/number). По умолчанию text. */
  type?: "text" | "number"
  /** Доп. CSS-классы для read-mode span (font-mono, размер). */
  className?: string
  /** title (для tooltip) в read-mode. */
  title?: string
  /** Запрещает редактирование. */
  disabled?: boolean
  /** Подсказка-tooltip для кнопки (read-mode). */
  hint?: string
  /** Валидация (вернуть null = ok, string = текст ошибки). */
  validate?: (next: string) => string | null
}

/**
 * InlineTextCell — клик-по-ячейке-редактирование.
 *
 * Используется в `/catalog/artikuly` (artikul, wb_nom, ozon_art),
 * `/catalog/tovary` (barkod, barkod_gs1, barkod_gs2, barkod_perehod).
 *
 * Не хранит локальный `value` после сохранения — родитель обновляет его
 * через react-query invalidate.  Это исключает рассинхронизацию при
 * сетевой ошибке.
 */
export function InlineTextCell({
  value, onCommit, placeholder = "—", type = "text",
  className = "", title, disabled = false, hint, validate,
}: InlineTextCellProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState("")
  const [saving, setSaving] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  // Read-mode → нормализованное отображение.
  const display = value == null || value === "" ? null : String(value)

  // При входе в edit — авто-фокус + select-all.
  useEffect(() => {
    if (!editing) return
    const el = inputRef.current
    if (el) {
      el.focus()
      el.select()
    }
  }, [editing])

  const enter = useCallback(() => {
    if (disabled || saving) return
    setDraft(display ?? "")
    setEditing(true)
  }, [display, disabled, saving])

  const cancel = useCallback(() => {
    setEditing(false)
    setDraft("")
  }, [])

  const commit = useCallback(async () => {
    if (saving) return
    const trimmed = draft.trim()
    // Без изменений — просто закрыть.
    if (trimmed === (display ?? "")) {
      cancel()
      return
    }
    // Валидация.
    if (validate) {
      const err = validate(trimmed)
      if (err) {
        toast.warning(err)
        // не закрываем — позволяем поправить.
        return
      }
    }
    const next = trimmed === "" ? null : trimmed
    setSaving(true)
    try {
      await onCommit(next)
      setEditing(false)
      setDraft("")
    } catch (e) {
      toast.error(translateError(e))
      // Остаёмся в edit-mode, чтобы пользователь видел исходное значение
      // и мог поправить / нажать Esc.
    } finally {
      setSaving(false)
    }
  }, [draft, display, onCommit, saving, validate, cancel])

  const onKey = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        e.preventDefault()
        void commit()
      } else if (e.key === "Escape") {
        e.preventDefault()
        cancel()
      }
    },
    [commit, cancel],
  )

  if (!editing) {
    return (
      <button
        type="button"
        onClick={enter}
        disabled={disabled}
        title={hint ?? "Кликните, чтобы изменить"}
        className={
          "block text-left w-full min-w-0 rounded px-1 -mx-1 py-0.5 overflow-hidden " +
          "hover:bg-stone-100 hover:ring-1 hover:ring-stone-300 " +
          "disabled:hover:bg-transparent disabled:hover:ring-0 disabled:cursor-default " +
          "transition-colors"
        }
      >
        {display != null ? (
          // W10.3 — ellipsis на длинных значениях в read-mode.  `title` + текст
          // прозрачно отдаём дальше — браузер сам покажет полную строку при hover.
          <span
            className={`block overflow-hidden text-ellipsis whitespace-nowrap ${className}`}
            title={title ?? (typeof display === "string" || typeof display === "number" ? String(display) : undefined)}
          >
            {display}
          </span>
        ) : (
          <span className="text-stone-400 italic text-xs">{placeholder}</span>
        )}
      </button>
    )
  }

  return (
    <div className="relative flex items-center gap-1 min-w-0" onClick={(e) => e.stopPropagation()}>
      <input
        ref={inputRef}
        type={type}
        value={draft}
        disabled={saving}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKey}
        onBlur={() => { void commit() }}
        className={
          "w-full min-w-0 px-1.5 py-0.5 text-xs border border-stone-400 " +
          "rounded outline-none focus:border-stone-700 bg-white " +
          "disabled:bg-stone-50 disabled:text-stone-400"
        }
      />
      {saving && <Loader2 className="w-3 h-3 text-stone-400 animate-spin shrink-0" />}
    </div>
  )
}
