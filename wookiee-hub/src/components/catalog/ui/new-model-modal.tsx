// W4.1 — Модалка «+ Новая модель»
// Заменяет старый `window.prompt("Код новой модели…")` в matrix.tsx.
// Wizard-форма с 9 полями + транзакционный save через
// createModelTransactional(): создаёт modeli_osnova + первую modeli +
// опц. modeli_osnova_razmery.

import { useEffect, useMemo, useState } from "react"
import { X } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { cn } from "@/lib/utils"
import {
  createModelTransactional,
  fetchBrendy,
  fetchFabriki,
  fetchImportery,
  fetchKategorii,
  fetchKollekcii,
  fetchRazmery,
  fetchStatusy,
  fetchTipyKollekciy,
} from "@/lib/catalog/service"
import { translateError } from "@/lib/catalog/error-translator"

interface NewModelModalProps {
  isOpen: boolean
  onClose: () => void
  /** Вызывается после успешного create — caller обычно делает navigate. */
  onCreated: (kod: string) => void
}

const KOD_REGEX = /^[a-zA-Z][a-zA-Z0-9_]*$/

export function NewModelModal({ isOpen, onClose, onCreated }: NewModelModalProps) {
  const [kod, setKod] = useState("")
  const [brandId, setBrandId] = useState<number | null>(null)
  const [kategoriyaId, setKategoriyaId] = useState<number | null>(null)
  const [kollekciyaId, setKollekciyaId] = useState<number | null>(null)
  const [tipKollekciiId, setTipKollekciiId] = useState<number | null>(null)
  const [fabrikaId, setFabrikaId] = useState<number | null>(null)
  const [importerId, setImporterId] = useState<number | null>(null)
  const [statusId, setStatusId] = useState<number | null>(null)
  const [razmeryIds, setRazmeryIds] = useState<number[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // ─── Reference data ──────────────────────────────────────────────────────
  const brendyQ = useQuery({
    queryKey: ["catalog", "brendy"],
    queryFn: fetchBrendy,
    staleTime: 10 * 60 * 1000,
    enabled: isOpen,
  })
  const kategoriiQ = useQuery({
    queryKey: ["kategorii"],
    queryFn: fetchKategorii,
    staleTime: 10 * 60 * 1000,
    enabled: isOpen,
  })
  const kollekciiQ = useQuery({
    queryKey: ["kollekcii"],
    queryFn: fetchKollekcii,
    staleTime: 10 * 60 * 1000,
    enabled: isOpen,
  })
  const tipyKollekciyQ = useQuery({
    queryKey: ["tipy_kollekciy"],
    queryFn: fetchTipyKollekciy,
    staleTime: 10 * 60 * 1000,
    enabled: isOpen,
  })
  const fabrikiQ = useQuery({
    queryKey: ["fabriki"],
    queryFn: fetchFabriki,
    staleTime: 10 * 60 * 1000,
    enabled: isOpen,
  })
  const importeryQ = useQuery({
    queryKey: ["importery"],
    queryFn: fetchImportery,
    staleTime: 10 * 60 * 1000,
    enabled: isOpen,
  })
  const statusyQ = useQuery({
    queryKey: ["statusy"],
    queryFn: fetchStatusy,
    staleTime: 30 * 60 * 1000,
    enabled: isOpen,
  })
  const razmeryQ = useQuery({
    queryKey: ["razmery"],
    queryFn: fetchRazmery,
    staleTime: 30 * 60 * 1000,
    enabled: isOpen,
  })

  const modelStatuses = useMemo(
    () => (statusyQ.data ?? []).filter((s) => s.tip === "model"),
    [statusyQ.data],
  )

  // Default razmery XS-XXL on first open (если справочник загрузился).
  useEffect(() => {
    if (!isOpen) return
    if (razmeryIds.length > 0) return
    const data = razmeryQ.data
    if (!data || data.length === 0) return
    const defaultNames = new Set(["XS", "S", "M", "L", "XL", "XXL"])
    const defaults = data.filter((r) => defaultNames.has(r.nazvanie.toUpperCase())).map((r) => r.id)
    if (defaults.length > 0) setRazmeryIds(defaults)
  }, [isOpen, razmeryQ.data, razmeryIds.length])

  // Reset on close.
  useEffect(() => {
    if (isOpen) return
    setKod("")
    setBrandId(null)
    setKategoriyaId(null)
    setKollekciyaId(null)
    setTipKollekciiId(null)
    setFabrikaId(null)
    setImporterId(null)
    setStatusId(null)
    setRazmeryIds([])
    setError(null)
    setSaving(false)
  }, [isOpen])

  // Esc to close.
  useEffect(() => {
    if (!isOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !saving) onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [isOpen, onClose, saving])

  if (!isOpen) return null

  const validate = (): string | null => {
    const trimmed = kod.trim()
    if (!trimmed) return "Введите код модели"
    if (!KOD_REGEX.test(trimmed))
      return "Код: только латиница/цифры/_, без пробелов, начинается с буквы"
    if (brandId == null) return "Выберите бренд"
    if (kategoriyaId == null) return "Выберите категорию"
    if (kollekciyaId == null) return "Выберите коллекцию"
    if (importerId == null) return "Выберите юрлицо (импортёра)"
    if (statusId == null) return "Выберите статус"
    return null
  }

  const handleSave = async () => {
    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }
    setError(null)
    setSaving(true)
    try {
      const createdKod = await createModelTransactional({
        kod: kod.trim(),
        brand_id: brandId!,
        kategoriya_id: kategoriyaId!,
        kollekciya_id: kollekciyaId!,
        tip_kollekcii_id: tipKollekciiId ?? null,
        fabrika_id: fabrikaId ?? null,
        importer_id: importerId!,
        status_id: statusId!,
        razmery_ids: razmeryIds,
      })
      onCreated(createdKod)
    } catch (e) {
      setError(translateError(e))
    } finally {
      setSaving(false)
    }
  }

  const toggleRazmer = (id: number) => {
    setRazmeryIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    )
  }

  const inputCls =
    "w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900"
  const labelCls =
    "block text-[11px] uppercase tracking-wider text-stone-500 mb-1"
  const requiredStar = <span className="text-red-500 ml-0.5">*</span>

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="new-model-modal-title"
      className="fixed inset-0 z-50 bg-stone-900/40 flex items-center justify-center p-4"
      onClick={() => !saving && onClose()}
    >
      <div
        className="w-full max-w-2xl bg-white rounded-xl shadow-2xl overflow-hidden border border-stone-200"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-stone-200">
          <h2
            id="new-model-modal-title"
            className="cat-font-serif text-xl text-stone-900 italic"
            style={{ fontFamily: "'Instrument Serif', ui-serif, Georgia, serif" }}
          >
            Новая модель
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="p-1 hover:bg-stone-100 rounded disabled:opacity-50"
            aria-label="Закрыть"
          >
            <X className="w-4 h-4 text-stone-500" />
          </button>
        </div>

        <div className="px-5 py-4 grid grid-cols-2 gap-3 max-h-[70vh] overflow-y-auto">
          {/* kod */}
          <div className="col-span-2">
            <label className={labelCls}>
              Код модели{requiredStar}
            </label>
            <input
              type="text"
              value={kod}
              autoFocus
              onChange={(e) => setKod(e.target.value)}
              placeholder="например, wendy_pro_2026"
              className={inputCls}
            />
            <div className="text-[10px] text-stone-400 mt-1">
              Латиница, цифры, _, без пробелов. Начинается с буквы. Должен быть уникальным.
            </div>
          </div>

          {/* brand_id */}
          <div>
            <label className={labelCls}>
              Бренд{requiredStar}
            </label>
            <select
              value={brandId ?? ""}
              onChange={(e) => setBrandId(e.target.value === "" ? null : Number(e.target.value))}
              className={inputCls}
            >
              <option value="">Выберите…</option>
              {(brendyQ.data ?? []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.nazvanie}
                </option>
              ))}
            </select>
          </div>

          {/* status_id */}
          <div>
            <label className={labelCls}>
              Статус{requiredStar}
            </label>
            <select
              value={statusId ?? ""}
              onChange={(e) => setStatusId(e.target.value === "" ? null : Number(e.target.value))}
              className={inputCls}
            >
              <option value="">Выберите…</option>
              {modelStatuses.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.nazvanie}
                </option>
              ))}
            </select>
          </div>

          {/* kategoriya_id */}
          <div>
            <label className={labelCls}>
              Категория{requiredStar}
            </label>
            <select
              value={kategoriyaId ?? ""}
              onChange={(e) =>
                setKategoriyaId(e.target.value === "" ? null : Number(e.target.value))
              }
              className={inputCls}
            >
              <option value="">Выберите…</option>
              {(kategoriiQ.data ?? []).map((k) => (
                <option key={k.id} value={k.id}>
                  {k.nazvanie}
                </option>
              ))}
            </select>
          </div>

          {/* kollekciya_id */}
          <div>
            <label className={labelCls}>
              Коллекция{requiredStar}
            </label>
            <select
              value={kollekciyaId ?? ""}
              onChange={(e) =>
                setKollekciyaId(e.target.value === "" ? null : Number(e.target.value))
              }
              className={inputCls}
            >
              <option value="">Выберите…</option>
              {(kollekciiQ.data ?? []).map((k) => (
                <option key={k.id} value={k.id}>
                  {k.nazvanie}
                </option>
              ))}
            </select>
          </div>

          {/* tip_kollekcii_id */}
          <div>
            <label className={labelCls}>Тип коллекции</label>
            <select
              value={tipKollekciiId ?? ""}
              onChange={(e) =>
                setTipKollekciiId(e.target.value === "" ? null : Number(e.target.value))
              }
              className={inputCls}
            >
              <option value="">— не выбрано —</option>
              {(tipyKollekciyQ.data ?? []).map((t) => (
                <option key={t.id} value={t.id}>
                  {t.nazvanie}
                </option>
              ))}
            </select>
          </div>

          {/* fabrika_id */}
          <div>
            <label className={labelCls}>Фабрика</label>
            <select
              value={fabrikaId ?? ""}
              onChange={(e) =>
                setFabrikaId(e.target.value === "" ? null : Number(e.target.value))
              }
              className={inputCls}
            >
              <option value="">— не выбрано —</option>
              {(fabrikiQ.data ?? []).map((f) => (
                <option key={f.id} value={f.id}>
                  {f.nazvanie}
                </option>
              ))}
            </select>
          </div>

          {/* importer_id */}
          <div className="col-span-2">
            <label className={labelCls}>
              Юрлицо (первая вариация){requiredStar}
            </label>
            <select
              value={importerId ?? ""}
              onChange={(e) =>
                setImporterId(e.target.value === "" ? null : Number(e.target.value))
              }
              className={inputCls}
            >
              <option value="">Выберите…</option>
              {(importeryQ.data ?? []).map((i) => (
                <option key={i.id} value={i.id}>
                  {i.short_name ?? i.nazvanie}
                </option>
              ))}
            </select>
            <div className="text-[10px] text-stone-400 mt-1">
              Юрлицо для первой вариации (modeli). Дополнительные вариации добавляются из карточки модели.
            </div>
          </div>

          {/* razmery[] */}
          <div className="col-span-2">
            <label className={labelCls}>Размерная линейка</label>
            <div className="flex flex-wrap gap-1.5">
              {(razmeryQ.data ?? []).map((r) => {
                const active = razmeryIds.includes(r.id)
                return (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => toggleRazmer(r.id)}
                    className={cn(
                      "px-2.5 py-1 text-xs rounded-md border transition-colors",
                      active
                        ? "bg-stone-900 text-white border-stone-900"
                        : "bg-white border-stone-200 text-stone-600 hover:border-stone-400",
                    )}
                  >
                    {r.nazvanie}
                  </button>
                )
              })}
            </div>
            <div className="text-[10px] text-stone-400 mt-1">
              По умолчанию: XS, S, M, L, XL, XXL. Можно изменить позже в карточке модели.
            </div>
          </div>
        </div>

        {error && (
          <div className="px-5 py-2 text-xs text-red-600 bg-red-50 border-t border-red-100">
            {error}
          </div>
        )}

        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-stone-200 bg-stone-50">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="px-3 py-1.5 text-sm text-stone-700 hover:bg-stone-100 rounded-md disabled:opacity-50"
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
            {saving ? "Создаём…" : "Создать"}
          </button>
        </div>
      </div>
    </div>
  )
}
