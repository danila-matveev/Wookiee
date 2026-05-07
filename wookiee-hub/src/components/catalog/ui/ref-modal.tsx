import { useEffect, useState } from "react"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

export type RefFieldType =
  | "text"
  | "number"
  | "textarea"
  | "select"
  | "multiselect"
  | "file_url"
  | "date"
  | "checkbox"

export interface RefFieldOption {
  value: string | number
  label: string
}

export interface RefFieldDef {
  key: string
  label: string
  type: RefFieldType
  options?: RefFieldOption[]
  required?: boolean
  placeholder?: string
  hint?: string
  /** Span the full row width. */
  full?: boolean
}

type FormValues = Record<string, unknown>

interface RefModalProps {
  title: string
  fields: RefFieldDef[]
  initial?: FormValues
  onSave: (values: FormValues) => Promise<void> | void
  onCancel: () => void
  saveLabel?: string
}

/**
 * RefModal — расширенная модалка для CRUD справочников.
 * Поддерживает: text, number, textarea, select, multiselect, file_url, date, checkbox.
 */
export function RefModal({
  title, fields, initial, onSave, onCancel, saveLabel = "Сохранить",
}: RefModalProps) {
  const [values, setValues] = useState<FormValues>(() => initial ?? {})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Esc to close
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onCancel])

  const setVal = (key: string, v: unknown) => {
    setValues((prev) => ({ ...prev, [key]: v }))
  }

  const handleSave = async () => {
    // required check
    for (const f of fields) {
      if (!f.required) continue
      const v = values[f.key]
      if (v == null || v === "" || (Array.isArray(v) && v.length === 0)) {
        setError(`Заполните обязательное поле «${f.label}»`)
        return
      }
    }
    setError(null)
    setSaving(true)
    try {
      await onSave(values)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-stone-900/40 flex items-center justify-center p-4"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-lg bg-white rounded-xl shadow-2xl overflow-hidden border border-stone-200"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-stone-200">
          <h2
            className="cat-font-serif text-xl text-stone-900 italic"
            style={{ fontFamily: "'Instrument Serif', ui-serif, Georgia, serif" }}
          >
            {title}
          </h2>
          <button
            type="button"
            onClick={onCancel}
            className="p-1 hover:bg-stone-100 rounded"
            aria-label="Close"
          >
            <X className="w-4 h-4 text-stone-500" />
          </button>
        </div>
        <div className="px-5 py-4 grid grid-cols-2 gap-3 max-h-[70vh] overflow-y-auto">
          {fields.map((f) => (
            <FieldInput
              key={f.key}
              field={f}
              value={values[f.key]}
              onChange={(v) => setVal(f.key, v)}
            />
          ))}
        </div>
        {error && (
          <div className="px-5 py-2 text-xs text-red-600 bg-red-50 border-t border-red-100">
            {error}
          </div>
        )}
        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-stone-200 bg-stone-50">
          <button
            type="button"
            onClick={onCancel}
            className="px-3 py-1.5 text-sm text-stone-700 hover:bg-stone-100 rounded-md"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className={cn(
              "px-3 py-1.5 text-sm text-white bg-stone-900 hover:bg-stone-800 rounded-md",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            {saving ? "Сохраняем…" : saveLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

interface FieldInputProps {
  field: RefFieldDef
  value: unknown
  onChange: (v: unknown) => void
}

function FieldInput({ field, value, onChange }: FieldInputProps) {
  const labelEl = (
    <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">
      {field.label}
      {field.required && <span className="text-red-500 ml-0.5">*</span>}
    </label>
  )
  const wrap = (children: React.ReactNode) => (
    <div className={field.full ?? field.type === "textarea" ? "col-span-2" : ""}>
      {labelEl}
      {children}
      {field.hint && <div className="text-[10px] text-stone-400 mt-1">{field.hint}</div>}
    </div>
  )
  const inputCls =
    "w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900"

  switch (field.type) {
    case "text":
    case "file_url":
      return wrap(
        <input
          type={field.type === "file_url" ? "url" : "text"}
          value={typeof value === "string" ? value : ""}
          placeholder={field.placeholder}
          onChange={(e) => onChange(e.target.value)}
          className={inputCls}
        />,
      )
    case "number":
      return wrap(
        <input
          type="number"
          value={typeof value === "number" ? value : value === "" || value == null ? "" : Number(value)}
          placeholder={field.placeholder}
          onChange={(e) => {
            const v = e.target.value
            onChange(v === "" ? null : Number(v))
          }}
          className={cn(inputCls, "tabular-nums")}
        />,
      )
    case "textarea":
      return wrap(
        <textarea
          rows={3}
          value={typeof value === "string" ? value : ""}
          placeholder={field.placeholder}
          onChange={(e) => onChange(e.target.value)}
          className={cn(inputCls, "resize-none")}
        />,
      )
    case "date":
      return wrap(
        <input
          type="date"
          value={typeof value === "string" ? value : ""}
          onChange={(e) => onChange(e.target.value)}
          className={inputCls}
        />,
      )
    case "checkbox":
      return (
        <div className="col-span-2 flex items-center gap-2">
          <input
            type="checkbox"
            checked={Boolean(value)}
            onChange={(e) => onChange(e.target.checked)}
            className="rounded border-stone-300"
            id={`refmodal-${field.key}`}
          />
          <label
            htmlFor={`refmodal-${field.key}`}
            className="text-sm text-stone-700 cursor-pointer"
          >
            {field.label}
          </label>
        </div>
      )
    case "select":
      return wrap(
        <select
          value={value == null ? "" : String(value)}
          onChange={(e) => {
            const v = e.target.value
            const opt = field.options?.find((o) => String(o.value) === v)
            onChange(opt ? opt.value : v)
          }}
          className={inputCls}
        >
          <option value="">{field.placeholder ?? "Выберите…"}</option>
          {field.options?.map((o) => (
            <option key={String(o.value)} value={String(o.value)}>{o.label}</option>
          ))}
        </select>,
      )
    case "multiselect": {
      const arr = Array.isArray(value) ? (value as Array<string | number>) : []
      const toggle = (v: string | number) => {
        const has = arr.some((x) => String(x) === String(v))
        onChange(has ? arr.filter((x) => String(x) !== String(v)) : [...arr, v])
      }
      return wrap(
        <div className="flex flex-wrap gap-1.5">
          {field.options?.map((o) => {
            const active = arr.some((x) => String(x) === String(o.value))
            return (
              <button
                key={String(o.value)}
                type="button"
                onClick={() => toggle(o.value)}
                className={cn(
                  "px-2.5 py-1 text-xs rounded-md border transition-colors",
                  active
                    ? "bg-stone-900 text-white border-stone-900"
                    : "bg-white border-stone-200 text-stone-600 hover:border-stone-400",
                )}
              >
                {o.label}
              </button>
            )
          })}
        </div>,
      )
    }
    default:
      return null
  }
}
