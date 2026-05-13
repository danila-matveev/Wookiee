// W10.32 — SkuDrawer.
//
// Карточка SKU (tovary row). Открывается из реестра /tovary по single-click.
// Side-drawer справа, rounded-l-2xl shadow-2xl. Три вкладки: Описание (баркоды,
// размер, статусы по каналам, ozon/lamoda поля), История (audit_log).
//
// W10.8 — Валидация полей drawer'а:
//   - barkod: 13 цифр (EAN-13)
//   - barkod_gs1/gs2/perehod: 13 цифр (опциональные, пусто = null)
//
// Контракт см. .planning/catalog-management-overhaul/W10-FIXES-TZ.md
// разделы W10.32 + W10.8.

import { useCallback, useEffect, useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Loader2, Save, X } from "lucide-react"

import {
  bulkUpdateTovaryStatus,
  fetchAuditFor,
  fetchRazmery,
  fetchStatusy,
  fetchTovarDetail,
  updateTovar,
  type AuditEntry,
  type Razmer,
  type TovarChannel,
  type TovarDetail,
  type TovarPatch,
} from "@/lib/catalog/service"
import { ColorSwatch } from "@/components/catalog/ui/color-swatch"
import { StatusBadge } from "@/components/catalog/ui/status-badge"
import { EmptyState } from "@/components/catalog/ui/empty-state"
import { translateError } from "@/lib/catalog/error-translator"
import { toast } from "@/lib/catalog/toast"

// ─── Валидация (W10.8) ─────────────────────────────────────────────────────

const BARKOD_REGEX = /^\d{13}$/

interface SkuDraft {
  barkod: string
  barkod_gs1: string
  barkod_gs2: string
  barkod_perehod: string
  razmer_id: number | null
  sku_china_size: string
  lamoda_seller_sku: string
  ozon_product_id: string
  ozon_fbo_sku_id: string
  // Каналы — отдельно через bulkUpdateTovaryStatus.
  status_wb: number | null
  status_ozon: number | null
  status_sayt: number | null
  status_lamoda: number | null
}

interface SkuFormErrors {
  barkod?: string
  barkod_gs1?: string
  barkod_gs2?: string
  barkod_perehod?: string
  ozon_product_id?: string
  ozon_fbo_sku_id?: string
}

function detailToDraft(d: TovarDetail): SkuDraft {
  return {
    barkod: d.barkod ?? "",
    barkod_gs1: d.barkod_gs1 ?? "",
    barkod_gs2: d.barkod_gs2 ?? "",
    barkod_perehod: d.barkod_perehod ?? "",
    razmer_id: d.razmer_id ?? null,
    sku_china_size: d.sku_china_size ?? "",
    lamoda_seller_sku: d.lamoda_seller_sku ?? "",
    ozon_product_id: d.ozon_product_id != null ? String(d.ozon_product_id) : "",
    ozon_fbo_sku_id: d.ozon_fbo_sku_id != null ? String(d.ozon_fbo_sku_id) : "",
    status_wb: d.status_id ?? null,
    status_ozon: d.status_ozon_id ?? null,
    status_sayt: d.status_sayt_id ?? null,
    status_lamoda: d.status_lamoda_id ?? null,
  }
}

function validateDraft(d: SkuDraft): SkuFormErrors {
  const errs: SkuFormErrors = {}
  if (!d.barkod.trim()) {
    errs.barkod = "Баркод обязателен"
  } else if (!BARKOD_REGEX.test(d.barkod.trim())) {
    errs.barkod = "Баркод: 13 цифр (EAN-13)"
  }
  if (d.barkod_gs1.trim() && !BARKOD_REGEX.test(d.barkod_gs1.trim())) {
    errs.barkod_gs1 = "Баркод GS1: 13 цифр"
  }
  if (d.barkod_gs2.trim() && !BARKOD_REGEX.test(d.barkod_gs2.trim())) {
    errs.barkod_gs2 = "Баркод GS2: 13 цифр"
  }
  if (d.barkod_perehod.trim() && !BARKOD_REGEX.test(d.barkod_perehod.trim())) {
    errs.barkod_perehod = "Баркод переход: 13 цифр"
  }
  if (d.ozon_product_id.trim() && !/^\d+$/.test(d.ozon_product_id.trim())) {
    errs.ozon_product_id = "OZON product_id: только цифры"
  }
  if (d.ozon_fbo_sku_id.trim() && !/^\d+$/.test(d.ozon_fbo_sku_id.trim())) {
    errs.ozon_fbo_sku_id = "OZON FBO SKU: только цифры"
  }
  return errs
}

/** Diff между draft и detail → TovarPatch (поля таблицы tovary). */
function draftToPatch(d: SkuDraft, base: TovarDetail): TovarPatch {
  const patch: TovarPatch = {}
  if (d.barkod.trim() !== base.barkod) patch.barkod = d.barkod.trim()
  const gs1 = d.barkod_gs1.trim() || null
  if (gs1 !== (base.barkod_gs1 ?? null)) patch.barkod_gs1 = gs1
  const gs2 = d.barkod_gs2.trim() || null
  if (gs2 !== (base.barkod_gs2 ?? null)) patch.barkod_gs2 = gs2
  const perehod = d.barkod_perehod.trim() || null
  if (perehod !== (base.barkod_perehod ?? null)) patch.barkod_perehod = perehod
  if (d.razmer_id != null && d.razmer_id !== (base.razmer_id ?? null)) {
    patch.razmer_id = d.razmer_id
  }
  const china = d.sku_china_size.trim() || null
  if (china !== (base.sku_china_size ?? null)) patch.sku_china_size = china
  const lam = d.lamoda_seller_sku.trim() || null
  if (lam !== (base.lamoda_seller_sku ?? null)) patch.lamoda_seller_sku = lam
  const ozonProd = d.ozon_product_id.trim() ? Number(d.ozon_product_id.trim()) : null
  if (ozonProd !== (base.ozon_product_id ?? null)) patch.ozon_product_id = ozonProd
  const ozonFbo = d.ozon_fbo_sku_id.trim() ? Number(d.ozon_fbo_sku_id.trim()) : null
  if (ozonFbo !== (base.ozon_fbo_sku_id ?? null)) patch.ozon_fbo_sku_id = ozonFbo
  return patch
}

/** Diff статусов по каналам → массив (channel, newStatusId). */
interface StatusDiff {
  channel: TovarChannel
  newStatusId: number | null
}
function statusDiffs(d: SkuDraft, base: TovarDetail): StatusDiff[] {
  const out: StatusDiff[] = []
  if (d.status_wb !== (base.status_id ?? null)) out.push({ channel: "wb", newStatusId: d.status_wb })
  if (d.status_ozon !== (base.status_ozon_id ?? null)) out.push({ channel: "ozon", newStatusId: d.status_ozon })
  if (d.status_sayt !== (base.status_sayt_id ?? null)) out.push({ channel: "sayt", newStatusId: d.status_sayt })
  if (d.status_lamoda !== (base.status_lamoda_id ?? null)) out.push({ channel: "lamoda", newStatusId: d.status_lamoda })
  return out
}

// ─── Component ─────────────────────────────────────────────────────────────

type TabId = "description" | "history"

interface SkuDrawerProps {
  tovarId: number
  onClose: () => void
}

export function SkuDrawer({ tovarId, onClose }: SkuDrawerProps) {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<TabId>("description")
  const [draft, setDraft] = useState<SkuDraft | null>(null)
  const [errors, setErrors] = useState<SkuFormErrors>({})

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  const detailQ = useQuery({
    queryKey: ["catalog", "tovar-detail", tovarId],
    queryFn: () => fetchTovarDetail(tovarId),
    staleTime: 30 * 1000,
  })
  const detail = detailQ.data ?? null

  useEffect(() => {
    if (detail) setDraft(detailToDraft(detail))
  }, [detail])

  const razmeryQ = useQuery({
    queryKey: ["catalog", "razmery"],
    queryFn: fetchRazmery,
    staleTime: 5 * 60 * 1000,
  })
  const razmery: Razmer[] = razmeryQ.data ?? []

  const statusyQ = useQuery({
    queryKey: ["catalog", "statusy"],
    queryFn: fetchStatusy,
    staleTime: 5 * 60 * 1000,
  })
  const statusy = statusyQ.data ?? []
  const productStatuses = useMemo(
    () => statusy.filter((s) => s.tip === "product"),
    [statusy],
  )
  const statusById = useMemo(() => {
    const m = new Map<number, { nazvanie: string; color: string | null }>()
    for (const s of statusy) m.set(s.id, { nazvanie: s.nazvanie, color: s.color })
    return m
  }, [statusy])

  const saveMut = useMutation({
    mutationFn: async () => {
      if (!detail || !draft) return
      const patch = draftToPatch(draft, detail)
      if (Object.keys(patch).length > 0) {
        await updateTovar(detail.id, patch)
      }
      const sDiffs = statusDiffs(draft, detail)
      for (const diff of sDiffs) {
        await bulkUpdateTovaryStatus([detail.barkod], diff.newStatusId, diff.channel)
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["catalog", "tovar-detail", tovarId] })
      void queryClient.invalidateQueries({ queryKey: ["tovary-registry"] })
      void queryClient.invalidateQueries({ queryKey: ["artikuly-registry"] })
      toast.success("Сохранено")
    },
    onError: (err) => {
      toast.error(translateError(err))
    },
  })

  useEffect(() => {
    if (!draft) return
    setErrors(validateDraft(draft))
  }, [draft])

  const isDirty = useMemo(() => {
    if (!detail || !draft) return false
    const patch = draftToPatch(draft, detail)
    const sDiffs = statusDiffs(draft, detail)
    return Object.keys(patch).length > 0 || sDiffs.length > 0
  }, [detail, draft])

  const hasErrors = Object.keys(errors).length > 0
  const canSave = isDirty && !hasErrors && !saveMut.isPending

  return (
    <>
      <div
        className="fixed inset-0 bg-black/30 z-40"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        className="fixed inset-y-0 right-0 w-[720px] bg-white rounded-l-2xl shadow-2xl z-50 overflow-y-auto flex flex-col"
        role="dialog"
        aria-label="Карточка SKU"
      >
        {detailQ.isLoading && (
          <div className="flex-1 flex items-center justify-center text-stone-400 text-sm">
            <Loader2 className="w-4 h-4 animate-spin mr-2" /> Загрузка SKU…
          </div>
        )}
        {detailQ.error && (
          <div className="flex-1 flex items-center justify-center text-red-500 text-sm px-6">
            Ошибка загрузки: {String(detailQ.error)}
          </div>
        )}
        {!detailQ.isLoading && !detailQ.error && !detail && (
          <div className="flex-1 flex items-center justify-center text-stone-500 text-sm px-6">
            SKU #{tovarId} не найдено.
          </div>
        )}
        {detail && draft && (
          <>
            <SkuHeader detail={detail} onClose={onClose} />

            {/* Tabs */}
            <div className="border-b border-stone-200 bg-white px-6 flex gap-1 shrink-0">
              {(
                [
                  { id: "description", label: "Описание" },
                  { id: "history", label: "История" },
                ] as Array<{ id: TabId; label: string }>
              ).map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTab(t.id)}
                  className={`px-3 py-2.5 text-sm border-b-2 -mb-px transition-colors ${
                    tab === t.id
                      ? "border-stone-900 text-stone-900 font-medium"
                      : "border-transparent text-stone-500 hover:text-stone-700"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {/* Body */}
            <div className="flex-1 overflow-auto bg-stone-50">
              {tab === "description" && (
                <TabDescription
                  draft={draft}
                  setDraft={setDraft}
                  errors={errors}
                  detail={detail}
                  razmery={razmery}
                  productStatuses={productStatuses}
                  statusById={statusById}
                />
              )}
              {tab === "history" && <TabHistory rowId={detail.id} />}
            </div>

            {/* Footer */}
            {tab === "description" && (
              <div className="border-t border-stone-200 bg-white px-6 py-3 flex items-center justify-end gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => {
                    if (detail) setDraft(detailToDraft(detail))
                  }}
                  disabled={!isDirty || saveMut.isPending}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-md disabled:opacity-40"
                >
                  Отменить
                </button>
                <button
                  type="button"
                  onClick={() => saveMut.mutate()}
                  disabled={!canSave}
                  className="px-3 py-1.5 text-xs text-white bg-stone-900 hover:bg-stone-800 rounded-md flex items-center gap-1.5 disabled:opacity-40"
                >
                  <Save className="w-3.5 h-3.5" />
                  {saveMut.isPending ? "Сохранение…" : "Сохранить"}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </>
  )
}

// ─── Header ────────────────────────────────────────────────────────────────

function SkuHeader({ detail, onClose }: { detail: TovarDetail; onClose: () => void }) {
  return (
    <div className="border-b border-stone-200 bg-white shrink-0 px-6 py-4 flex items-center gap-4">
      <ColorSwatch hex={detail.cvet_hex} size={48} />
      <div className="flex-1 min-w-0">
        <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-0.5">
          SKU · Баркод
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-2xl text-stone-900 font-mono">{detail.barkod}</h2>
          {detail.razmer_nazvanie && (
            <span className="px-2 py-0.5 bg-stone-100 text-stone-700 rounded text-xs font-mono">
              {detail.razmer_nazvanie}
            </span>
          )}
        </div>
        <div className="mt-1 flex items-center gap-3 flex-wrap text-xs text-stone-500">
          {detail.artikul && (
            <span className="font-mono">{detail.artikul}</span>
          )}
          {detail.cvet_color_code && (
            <span>
              · {detail.cvet_color_code}
              {detail.cvet_nazvanie ? ` · ${detail.cvet_nazvanie}` : ""}
            </span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <button
          type="button"
          onClick={onClose}
          className="p-1.5 hover:bg-stone-100 rounded-md"
          aria-label="Закрыть"
        >
          <X className="w-4 h-4 text-stone-700" />
        </button>
      </div>
    </div>
  )
}

// ─── Tab: Описание ──────────────────────────────────────────────────────────

interface TabDescriptionProps {
  draft: SkuDraft
  setDraft: (d: SkuDraft) => void
  errors: SkuFormErrors
  detail: TovarDetail
  razmery: Razmer[]
  productStatuses: { id: number; nazvanie: string; color: string | null }[]
  statusById: Map<number, { nazvanie: string; color: string | null }>
}

function TabDescription({
  draft, setDraft, errors, detail, razmery, productStatuses,
}: TabDescriptionProps) {
  const set = useCallback(
    <K extends keyof SkuDraft>(k: K, v: SkuDraft[K]) => {
      setDraft({ ...draft, [k]: v })
    },
    [draft, setDraft],
  )

  return (
    <div className="px-6 py-5 space-y-5">
      {/* Идентификация SKU */}
      <section>
        <h3 className="text-[11px] uppercase tracking-wider text-stone-500 font-medium mb-2">
          Идентификация
        </h3>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Баркод" required error={errors.barkod} hint="EAN-13: 13 цифр">
            <input
              type="text"
              inputMode="numeric"
              value={draft.barkod}
              onChange={(e) => set("barkod", e.target.value.replace(/\D/g, ""))}
              className={inputClass(!!errors.barkod)}
              maxLength={13}
              placeholder="1234567890123"
            />
          </Field>
          <Field label="Размер">
            <select
              value={draft.razmer_id ?? ""}
              onChange={(e) => set("razmer_id", e.target.value ? Number(e.target.value) : null)}
              className={inputClass(false)}
            >
              <option value="">— не выбран —</option>
              {razmery.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.nazvanie}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Баркод GS1" error={errors.barkod_gs1} hint="Дополнительный (опционально)">
            <input
              type="text"
              inputMode="numeric"
              value={draft.barkod_gs1}
              onChange={(e) => set("barkod_gs1", e.target.value.replace(/\D/g, ""))}
              className={inputClass(!!errors.barkod_gs1)}
              maxLength={13}
            />
          </Field>
          <Field label="Баркод GS2" error={errors.barkod_gs2} hint="Дополнительный (опционально)">
            <input
              type="text"
              inputMode="numeric"
              value={draft.barkod_gs2}
              onChange={(e) => set("barkod_gs2", e.target.value.replace(/\D/g, ""))}
              className={inputClass(!!errors.barkod_gs2)}
              maxLength={13}
            />
          </Field>
          <Field label="Баркод (переход)" error={errors.barkod_perehod} hint="Для миграции упаковки">
            <input
              type="text"
              inputMode="numeric"
              value={draft.barkod_perehod}
              onChange={(e) => set("barkod_perehod", e.target.value.replace(/\D/g, ""))}
              className={inputClass(!!errors.barkod_perehod)}
              maxLength={13}
            />
          </Field>
          <Field label="SKU China" hint="Внутренний код фабрики">
            <input
              type="text"
              value={draft.sku_china_size}
              onChange={(e) => set("sku_china_size", e.target.value)}
              className={inputClass(false)}
            />
          </Field>
        </div>
      </section>

      {/* Статусы по каналам */}
      <section>
        <h3 className="text-[11px] uppercase tracking-wider text-stone-500 font-medium mb-2">
          Статусы по каналам
        </h3>
        <div className="grid grid-cols-2 gap-4">
          <Field label="WB">
            <ChannelStatusSelect
              value={draft.status_wb}
              onChange={(v) => set("status_wb", v)}
              options={productStatuses}
            />
          </Field>
          <Field label="OZON">
            <ChannelStatusSelect
              value={draft.status_ozon}
              onChange={(v) => set("status_ozon", v)}
              options={productStatuses}
            />
          </Field>
          <Field label="Сайт">
            <ChannelStatusSelect
              value={draft.status_sayt}
              onChange={(v) => set("status_sayt", v)}
              options={productStatuses}
            />
          </Field>
          <Field label="Lamoda">
            <ChannelStatusSelect
              value={draft.status_lamoda}
              onChange={(v) => set("status_lamoda", v)}
              options={productStatuses}
            />
          </Field>
        </div>
      </section>

      {/* Канальные идентификаторы */}
      <section>
        <h3 className="text-[11px] uppercase tracking-wider text-stone-500 font-medium mb-2">
          Идентификаторы по каналам
        </h3>
        <div className="grid grid-cols-2 gap-4">
          <Field label="OZON product_id" error={errors.ozon_product_id}>
            <input
              type="text"
              inputMode="numeric"
              value={draft.ozon_product_id}
              onChange={(e) => set("ozon_product_id", e.target.value.replace(/\D/g, ""))}
              className={inputClass(!!errors.ozon_product_id)}
            />
          </Field>
          <Field label="OZON FBO SKU" error={errors.ozon_fbo_sku_id}>
            <input
              type="text"
              inputMode="numeric"
              value={draft.ozon_fbo_sku_id}
              onChange={(e) => set("ozon_fbo_sku_id", e.target.value.replace(/\D/g, ""))}
              className={inputClass(!!errors.ozon_fbo_sku_id)}
            />
          </Field>
          <Field label="Lamoda seller SKU">
            <input
              type="text"
              value={draft.lamoda_seller_sku}
              onChange={(e) => set("lamoda_seller_sku", e.target.value)}
              className={inputClass(false)}
            />
          </Field>
        </div>
      </section>

      {/* Контекст артикула — read-only */}
      <section className="pt-3 border-t border-stone-200">
        <h3 className="text-[11px] uppercase tracking-wider text-stone-500 font-medium mb-2">
          Контекст артикула
        </h3>
        <div className="grid grid-cols-2 gap-4 text-xs">
          <ReadOnly label="Артикул" value={detail.artikul} />
          <ReadOnly label="Модель" value={detail.model_osnova_kod} />
          <ReadOnly label="WB-номенклатура" value={
            detail.nomenklatura_wb != null ? String(detail.nomenklatura_wb) : null
          } />
          <ReadOnly label="OZON-артикул" value={detail.artikul_ozon} />
        </div>
        <div className="mt-3 text-[11px] text-stone-400 italic">
          Перепривязка склейки доступна из реестра /tovary (bulk-action
          «Привязать к склейке»).
        </div>
      </section>
    </div>
  )
}

interface ChannelStatusSelectProps {
  value: number | null
  onChange: (v: number | null) => void
  options: { id: number; nazvanie: string; color: string | null }[]
}

function ChannelStatusSelect({ value, onChange, options }: ChannelStatusSelectProps) {
  return (
    <select
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
      className={inputClass(false)}
    >
      <option value="">— нет статуса —</option>
      {options.map((s) => (
        <option key={s.id} value={s.id}>
          {s.nazvanie}
        </option>
      ))}
    </select>
  )
}

// ─── Tab: История ───────────────────────────────────────────────────────────

function TabHistory({ rowId }: { rowId: number }) {
  const auditQ = useQuery({
    queryKey: ["catalog", "audit", "tovary", rowId],
    queryFn: () => fetchAuditFor("tovary", rowId, 50),
    staleTime: 30 * 1000,
  })

  if (auditQ.isLoading) {
    return (
      <div className="px-6 py-8 text-center text-stone-400 text-sm">
        <Loader2 className="w-4 h-4 inline animate-spin mr-2" /> Загрузка истории…
      </div>
    )
  }
  if (auditQ.error) {
    return (
      <div className="px-6 py-8 text-center text-red-500 text-sm">
        Ошибка загрузки истории: {String(auditQ.error)}
      </div>
    )
  }
  const entries = auditQ.data ?? []
  if (entries.length === 0) {
    return (
      <div className="px-6 py-8">
        <EmptyState
          title="Нет истории изменений"
          description="Аудит включён, но изменений по этому SKU пока нет."
        />
      </div>
    )
  }
  return (
    <div className="px-6 py-5">
      <ol className="space-y-3">
        {entries.map((e: AuditEntry) => (
          <li key={e.id} className="border-l-2 border-stone-300 pl-3">
            <div className="text-[11px] uppercase tracking-wider text-stone-400">
              {new Date(e.created_at).toLocaleString("ru-RU")} · {e.action}
            </div>
            {e.changed && Object.keys(e.changed).length > 0 && (
              <div className="text-xs text-stone-600 mt-1 space-y-0.5">
                {Object.entries(e.changed).map(([field, diff]) => (
                  <div key={field}>
                    <span className="font-mono text-stone-500">{field}:</span>{" "}
                    <span className="line-through text-stone-400">{formatVal(diff.from)}</span>
                    {" → "}
                    <span className="text-stone-800">{formatVal(diff.to)}</span>
                  </div>
                ))}
              </div>
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}

function formatVal(v: unknown): string {
  if (v == null) return "—"
  if (typeof v === "string") return v
  return JSON.stringify(v)
}

// ─── Helpers (UI) ──────────────────────────────────────────────────────────

interface FieldProps {
  label: string
  required?: boolean
  error?: string
  hint?: string
  children: React.ReactNode
}

function Field({ label, required, error, hint, children }: FieldProps) {
  return (
    <div>
      <label className="block text-xs font-medium text-stone-700 mb-1">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
      {error ? (
        <div className="mt-1 text-[11px] text-red-600">{error}</div>
      ) : hint ? (
        <div className="mt-1 text-[11px] text-stone-400">{hint}</div>
      ) : null}
    </div>
  )
}

function ReadOnly({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wider text-stone-400">{label}</div>
      <div className="text-stone-700 font-mono text-xs">{value ?? "—"}</div>
    </div>
  )
}

function inputClass(invalid: boolean): string {
  return [
    "w-full px-2.5 py-1.5 text-sm border rounded-md outline-none transition-colors",
    "focus:ring-2 focus:ring-stone-300",
    invalid
      ? "border-red-400 focus:border-red-500 bg-red-50/40"
      : "border-stone-300 focus:border-stone-500 bg-white",
  ].join(" ")
}
