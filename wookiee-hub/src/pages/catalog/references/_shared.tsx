import { useState } from "react"
import { X } from "lucide-react"

interface FieldDef {
  key: string
  label: string
  type?: "text" | "number"
  placeholder?: string
}

interface RefModalProps {
  title: string
  fields: FieldDef[]
  initialValues?: Record<string, string>
  onSave: (values: Record<string, string>) => Promise<void>
  onClose: () => void
}

export function RefModal({ title, fields, initialValues = {}, onSave, onClose }: RefModalProps) {
  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(fields.map((f) => [f.key, initialValues[f.key] ?? ""]))
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      await onSave(values)
      onClose()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-white rounded-xl border border-stone-200 shadow-2xl w-full max-w-md p-6 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium text-stone-900">{title}</h3>
          <button onClick={onClose} className="p-1 hover:bg-stone-100 rounded-md">
            <X className="w-4 h-4 text-stone-500" />
          </button>
        </div>
        <div className="space-y-3">
          {fields.map((f) => (
            <div key={f.key}>
              <label className="block text-[11px] uppercase tracking-wider text-stone-500 mb-1">{f.label}</label>
              <input
                type={f.type ?? "text"}
                value={values[f.key] ?? ""}
                onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                placeholder={f.placeholder}
                className="w-full px-3 py-2 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-400"
              />
            </div>
          ))}
        </div>
        {error && <div className="text-xs text-red-500">{error}</div>}
        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs text-stone-700 hover:bg-stone-100 rounded-md"
          >
            Отмена
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-xs text-white bg-stone-900 hover:bg-stone-800 disabled:opacity-50 rounded-md"
          >
            {saving ? "Сохранение…" : "Сохранить"}
          </button>
        </div>
      </div>
    </div>
  )
}

interface PageHeaderProps {
  title: string
  count: number
  isLoading: boolean
}

export function PageHeader({ title, count, isLoading }: PageHeaderProps) {
  return (
    <div className="mb-5">
      <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-1">
        Справочник
      </div>
      <div className="flex items-end justify-between">
        <h1
          className="text-3xl text-stone-900"
          style={{ fontFamily: "'Instrument Serif', ui-serif, Georgia, serif" }}
        >
          {title}
        </h1>
        <div className="flex items-center gap-3">
          {isLoading ? (
            <span className="text-sm text-stone-400">Загрузка…</span>
          ) : (
            <span className="text-sm text-stone-500 tabular-nums">
              {count} записей
            </span>
          )}
          <span className="text-xs text-stone-400 bg-stone-100 px-2 py-0.5 rounded-md">
            только чтение
          </span>
        </div>
      </div>
    </div>
  )
}

interface ErrorBlockProps {
  message: string
}

export function ErrorBlock({ message }: ErrorBlockProps) {
  return (
    <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
      Ошибка загрузки: {message}
    </div>
  )
}

export function SkeletonTable({
  rows = 5,
  cols = 3,
}: {
  rows?: number
  cols?: number
}) {
  return (
    <div className="bg-white rounded-lg border border-stone-200 overflow-hidden">
      <div className="bg-stone-50/80 border-b border-stone-200 px-3 py-2.5 flex gap-6">
        {Array.from({ length: cols }).map((_, i) => (
          <div
            key={i}
            className="h-3 bg-stone-200 rounded animate-pulse"
            style={{ width: `${60 + i * 20}px` }}
          />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex gap-6 px-3 py-3 border-b border-stone-100 last:border-0"
        >
          {Array.from({ length: cols }).map((_, j) => (
            <div
              key={j}
              className="h-3 bg-stone-100 rounded animate-pulse"
              style={{ width: `${80 + j * 30}px` }}
            />
          ))}
        </div>
      ))}
    </div>
  )
}
