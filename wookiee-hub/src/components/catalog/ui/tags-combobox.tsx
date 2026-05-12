// TagsCombobox — multi-select combobox с автокомплитом из существующих тегов
// + возможностью создать новый тег on-the-fly (Enter).
//
// Контракт: value/onChange — comma-separated string (как persist'ится сейчас
// в `modeli_osnova.tegi`). Опции — string[] всех уникальных тегов из БД
// (загружаются через `fetchAllTags`).

import { useEffect, useMemo, useRef, useState } from "react"
import { Plus, X } from "lucide-react"
import { FieldWrap, type FieldLevel } from "./fields"

interface TagsComboboxProps {
  label: string
  /** CSV-строка тегов, разделённых запятой (как хранится в БД). */
  value?: string | null
  /** onChange отдаёт обратно CSV-строку. */
  onChange?: (v: string) => void
  /** Все известные теги (для автокомплита). */
  options?: string[]
  placeholder?: string
  readonly?: boolean
  full?: boolean
  hint?: string
  level?: FieldLevel
}

/** Parse CSV → trimmed unique tags. */
function parseTags(raw: string | null | undefined): string[] {
  if (!raw) return []
  const seen = new Set<string>()
  const out: string[] = []
  for (const part of raw.split(",")) {
    const t = part.trim()
    if (!t) continue
    const key = t.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    out.push(t)
  }
  return out
}

function serializeTags(arr: string[]): string {
  return arr.join(", ")
}

export function TagsCombobox({
  label,
  value,
  onChange,
  options = [],
  placeholder = "Добавить тег…",
  readonly,
  full,
  hint,
  level,
}: TagsComboboxProps) {
  const tags = useMemo(() => parseTags(value), [value])
  const [input, setInput] = useState("")
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Suggestions — все опции, не входящие в текущие теги, отфильтрованные по input.
  const suggestions = useMemo(() => {
    const tagSet = new Set(tags.map((t) => t.toLowerCase()))
    const q = input.trim().toLowerCase()
    return options
      .filter((o) => {
        const ol = o.toLowerCase()
        if (tagSet.has(ol)) return false
        if (q && !ol.includes(q)) return false
        return true
      })
      .slice(0, 20)
  }, [options, tags, input])

  // Можем ли создать новый тег (input не пустой и его нет ни в tags, ни в options).
  const canCreate = useMemo(() => {
    const q = input.trim()
    if (!q) return false
    const ql = q.toLowerCase()
    const exists =
      tags.some((t) => t.toLowerCase() === ql) ||
      options.some((o) => o.toLowerCase() === ql)
    return !exists
  }, [input, tags, options])

  // Close dropdown when clicking outside.
  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (!containerRef.current) return
      if (!containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    window.addEventListener("mousedown", onClick)
    return () => window.removeEventListener("mousedown", onClick)
  }, [open])

  const addTag = (raw: string) => {
    const t = raw.trim()
    if (!t) return
    const tl = t.toLowerCase()
    if (tags.some((x) => x.toLowerCase() === tl)) return
    const next = [...tags, t]
    onChange?.(serializeTags(next))
    setInput("")
  }

  const removeTag = (tag: string) => {
    const tl = tag.toLowerCase()
    const next = tags.filter((t) => t.toLowerCase() !== tl)
    onChange?.(serializeTags(next))
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault()
      const q = input.trim()
      if (q) addTag(q)
      return
    }
    if (e.key === "Backspace" && input === "" && tags.length > 0) {
      e.preventDefault()
      removeTag(tags[tags.length - 1])
      return
    }
    if (e.key === "Escape") {
      setOpen(false)
      return
    }
  }

  if (readonly) {
    return (
      <FieldWrap label={label} level={level} full={full} hint={hint}>
        {tags.length === 0 ? (
          <div className="px-2.5 py-1.5 text-sm">
            <span className="text-stone-400 italic">не задано</span>
          </div>
        ) : (
          <div className="flex flex-wrap gap-1.5 px-0.5 py-1">
            {tags.map((t) => (
              <span
                key={t}
                className="inline-flex items-center px-2 py-0.5 text-xs rounded-md bg-stone-100 text-stone-700 border border-stone-200"
              >
                {t}
              </span>
            ))}
          </div>
        )}
      </FieldWrap>
    )
  }

  return (
    <FieldWrap label={label} level={level} full={full} hint={hint}>
      <div ref={containerRef} className="relative">
        <div
          className="flex flex-wrap items-center gap-1.5 min-h-[34px] w-full px-2 py-1 text-sm border border-stone-200 rounded-md bg-white focus-within:border-stone-900 focus-within:ring-1 focus-within:ring-stone-900"
          onClick={() => {
            inputRef.current?.focus()
            setOpen(true)
          }}
        >
          {tags.map((t) => (
            <span
              key={t}
              className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-md bg-stone-900 text-white"
            >
              {t}
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  removeTag(t)
                }}
                className="-mr-0.5 ml-0.5 inline-flex items-center justify-center w-3.5 h-3.5 rounded-sm hover:bg-stone-700"
                aria-label={`Удалить тег ${t}`}
              >
                <X className="w-2.5 h-2.5" />
              </button>
            </span>
          ))}
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => {
              setInput(e.target.value)
              setOpen(true)
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={onKeyDown}
            placeholder={tags.length === 0 ? placeholder : ""}
            className="flex-1 min-w-[80px] bg-transparent outline-none border-0 text-sm py-0.5"
          />
        </div>

        {open && (suggestions.length > 0 || canCreate) && (
          <div className="absolute z-20 left-0 right-0 mt-1 max-h-56 overflow-y-auto bg-white border border-stone-200 rounded-md shadow-lg">
            {suggestions.map((s) => (
              <button
                key={s}
                type="button"
                onMouseDown={(e) => {
                  // mousedown — иначе input теряет фокус раньше клика
                  e.preventDefault()
                  addTag(s)
                }}
                className="w-full text-left px-2.5 py-1.5 text-sm text-stone-700 hover:bg-stone-100"
              >
                {s}
              </button>
            ))}
            {canCreate && (
              <button
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault()
                  addTag(input)
                }}
                className="w-full text-left px-2.5 py-1.5 text-sm text-stone-900 hover:bg-stone-100 flex items-center gap-1.5 border-t border-stone-100"
              >
                <Plus className="w-3.5 h-3.5 text-stone-500" />
                Создать «{input.trim()}»
              </button>
            )}
          </div>
        )}
      </div>
    </FieldWrap>
  )
}
