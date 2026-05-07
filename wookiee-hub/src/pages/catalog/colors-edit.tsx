import { useEffect, useMemo, useState } from "react"
import { X } from "lucide-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  fetchSemeystvaCvetov,
  fetchStatusy,
  insertCvet,
  updateCvet,
  type CvetPayload,
  type CvetRow,
} from "@/lib/catalog/service"

interface CvetEditModalProps {
  initial?: CvetRow | null
  onClose: () => void
}

interface CvetFormState {
  color_code: string
  cvet: string
  color: string
  lastovica: string
  hex: string
  semeystvo_id: number | null
  status_id: number | null
}

/**
 * Standalone modal for creating/editing a colour entry.
 *
 * Uses native <input type="color"> — RefModal does not support a `color` field
 * type, and adding one was rolled back by the linter, so this lives outside
 * the generic atomic UI.
 */
export function CvetEditModal({ initial, onClose }: CvetEditModalProps) {
  const qc = useQueryClient()

  const { data: semeystva } = useQuery({
    queryKey: ["semeystva-cvetov"],
    queryFn: fetchSemeystvaCvetov,
    staleTime: 10 * 60 * 1000,
  })
  const { data: statuses } = useQuery({
    queryKey: ["statusy"],
    queryFn: fetchStatusy,
    staleTime: 10 * 60 * 1000,
    select: (rows) => rows.filter((s) => s.tip === "color"),
  })

  const lastovicaOptions = useMemo(() => ["", "есть", "нет"], [])

  const [form, setForm] = useState<CvetFormState>(() => ({
    color_code: initial?.color_code ?? "",
    cvet: initial?.cvet ?? "",
    color: initial?.color ?? "",
    lastovica: initial?.lastovica ?? "",
    hex: initial?.hex ?? "",
    semeystvo_id: initial?.semeystvo_id ?? null,
    status_id: initial?.status_id ?? null,
  }))
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  const set = <K extends keyof CvetFormState>(k: K, v: CvetFormState[K]) =>
    setForm((p) => ({ ...p, [k]: v }))

  const insert = useMutation({
    mutationFn: (payload: CvetPayload) => insertCvet(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cveta-with-usage"] })
      onClose()
    },
  })
  const update = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Partial<CvetPayload> }) => updateCvet(id, patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cveta-with-usage"] })
      qc.invalidateQueries({ queryKey: ["color-detail-by-code"] })
      onClose()
    },
  })

  const onSave = async () => {
    if (!form.color_code.trim()) {
      setError("Заполните Color Code")
      return
    }
    if (form.hex && !/^#[0-9A-Fa-f]{6}$/.test(form.hex)) {
      setError("HEX должен быть в формате #RRGGBB")
      return
    }
    setError(null)
    setSaving(true)
    try {
      const payload: CvetPayload = {
        color_code: form.color_code.trim(),
        cvet: form.cvet || null,
        color: form.color || null,
        lastovica: form.lastovica || null,
        hex: form.hex || null,
        semeystvo_id: form.semeystvo_id ?? null,
        status_id: form.status_id ?? null,
      }
      if (initial) await update.mutateAsync({ id: initial.id, patch: payload })
      else await insert.mutateAsync(payload)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения")
      setSaving(false)
    }
  }

  const inputCls =
    "w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900"
  const labelCls = "block text-[11px] uppercase tracking-wider text-stone-500 mb-1"
  const previewHex = /^#[0-9A-Fa-f]{6}$/.test(form.hex) ? form.hex : "#e7e5e4"

  return (
    <div
      className="fixed inset-0 z-[60] bg-stone-900/40 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg bg-white rounded-xl shadow-2xl overflow-hidden border border-stone-200"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-stone-200">
          <h2 className="cat-font-serif text-xl text-stone-900 italic">
            {initial ? `Редактировать ${initial.color_code}` : "Новый цвет"}
          </h2>
          <button onClick={onClose} className="p-1 hover:bg-stone-100 rounded" aria-label="Close">
            <X className="w-4 h-4 text-stone-500" />
          </button>
        </div>

        <div className="px-5 py-4 grid grid-cols-2 gap-3 max-h-[70vh] overflow-y-auto">
          <div className="col-span-1">
            <label className={labelCls}>Color Code <span className="text-red-500">*</span></label>
            <input
              autoFocus
              value={form.color_code}
              onChange={(e) => set("color_code", e.target.value)}
              placeholder="A001"
              className={inputCls + " font-mono"}
            />
          </div>
          <div className="col-span-1">
            <label className={labelCls}>Ластовица</label>
            <select
              value={form.lastovica}
              onChange={(e) => set("lastovica", e.target.value)}
              className={inputCls}
            >
              {lastovicaOptions.map((o) => (
                <option key={o || "none"} value={o}>{o || "—"}</option>
              ))}
            </select>
          </div>

          <div className="col-span-1">
            <label className={labelCls}>Цвет (RU)</label>
            <input
              value={form.cvet}
              onChange={(e) => set("cvet", e.target.value)}
              placeholder="например, бордо"
              className={inputCls}
            />
          </div>
          <div className="col-span-1">
            <label className={labelCls}>Color (EN)</label>
            <input
              value={form.color}
              onChange={(e) => set("color", e.target.value)}
              placeholder="for example, burgundy"
              className={inputCls}
            />
          </div>

          <div className="col-span-2">
            <label className={labelCls}>HEX</label>
            <div className="flex items-center gap-3">
              <input
                type="color"
                value={previewHex}
                onChange={(e) => set("hex", e.target.value)}
                className="w-12 h-10 rounded-md border border-stone-200 bg-white p-0 cursor-pointer"
                aria-label="Hex picker"
              />
              <input
                type="text"
                value={form.hex}
                placeholder="#RRGGBB"
                onChange={(e) => set("hex", e.target.value)}
                className={inputCls + " font-mono w-40"}
              />
              <div
                className="w-10 h-10 rounded-md ring-1 ring-stone-200"
                style={{ background: previewHex }}
                title="Предпросмотр"
              />
            </div>
          </div>

          <div className="col-span-1">
            <label className={labelCls}>Семейство</label>
            <select
              value={form.semeystvo_id ?? ""}
              onChange={(e) => set("semeystvo_id", e.target.value ? Number(e.target.value) : null)}
              className={inputCls}
            >
              <option value="">—</option>
              {(semeystva ?? []).map((s) => (
                <option key={s.id} value={s.id}>{s.nazvanie}</option>
              ))}
            </select>
          </div>
          <div className="col-span-1">
            <label className={labelCls}>Статус</label>
            <select
              value={form.status_id ?? ""}
              onChange={(e) => set("status_id", e.target.value ? Number(e.target.value) : null)}
              className={inputCls}
            >
              <option value="">—</option>
              {(statuses ?? []).map((s) => (
                <option key={s.id} value={s.id}>{s.nazvanie}</option>
              ))}
            </select>
          </div>
        </div>

        {error && (
          <div className="px-5 py-2 text-xs text-red-600 bg-red-50 border-t border-red-100">
            {error}
          </div>
        )}

        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-stone-200 bg-stone-50">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm text-stone-700 hover:bg-stone-100 rounded-md"
          >Отмена</button>
          <button
            onClick={onSave}
            disabled={saving}
            className="px-3 py-1.5 text-sm text-white bg-stone-900 hover:bg-stone-800 rounded-md disabled:opacity-50"
          >{saving ? "Сохраняем…" : "Сохранить"}</button>
        </div>
      </div>
    </div>
  )
}
