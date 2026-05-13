// W10.6 — ArtikulDrawer.
//
// Карточка артикула. Открывается из реестра /artikuly по single-click на
// строку и из /matrix?model=KOD (вкладка «Артикулы»). Side-drawer справа,
// rounded-l-2xl shadow-2xl. Три вкладки: Описание (поля с inline-edit),
// SKU (read-only список tovary), История (audit_log по таблице artikuly).
//
// W10.8 — Валидация полей drawer'а:
//   - artikul: ^[\wА-я\-]+\/[\wА-я\-]+$
//   - nomenklatura_wb: 7–12 цифр
//   - artikul_ozon: непустое, до 50 символов
//
// Контракт см. .planning/catalog-management-overhaul/W10-FIXES-TZ.md
// разделы W10.6 + W10.8.

import { useCallback, useEffect, useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Archive, Copy, Loader2, Save, X } from "lucide-react"

import {
  fetchArtikulDetail,
  fetchAuditFor,
  fetchStatusy,
  updateArtikul,
  type ArtikulDetail,
  type ArtikulPatch,
  type AuditEntry,
} from "@/lib/catalog/service"
import { ColorSwatch } from "@/components/catalog/ui/color-swatch"
import { StatusBadge } from "@/components/catalog/ui/status-badge"
import { CellText } from "@/components/catalog/ui/cell-text"
import { EmptyState } from "@/components/catalog/ui/empty-state"
import { translateError } from "@/lib/catalog/error-translator"
import { toast } from "@/lib/catalog/toast"
import { compareRazmer } from "@/lib/catalog/size-utils"

// ─── Валидация (W10.8) ─────────────────────────────────────────────────────

const ARTIKUL_REGEX = /^[\wА-я\-]+\/[\wА-я\-]+$/
const WB_NOM_REGEX = /^\d{7,12}$/

interface ArtikulDraft {
  artikul: string
  nomenklatura_wb: string
  artikul_ozon: string
  status_id: number | null
}

interface FormErrors {
  artikul?: string
  nomenklatura_wb?: string
  artikul_ozon?: string
}

function detailToDraft(d: ArtikulDetail): ArtikulDraft {
  return {
    artikul: d.artikul ?? "",
    nomenklatura_wb: d.nomenklatura_wb != null ? String(d.nomenklatura_wb) : "",
    artikul_ozon: d.artikul_ozon ?? "",
    status_id: d.status_id ?? null,
  }
}

function validateDraft(draft: ArtikulDraft): FormErrors {
  const errs: FormErrors = {}
  if (!draft.artikul.trim()) {
    errs.artikul = "Артикул обязателен"
  } else if (!ARTIKUL_REGEX.test(draft.artikul.trim())) {
    errs.artikul = "Формат: model/color (например: Wendy/black)"
  }
  if (draft.nomenklatura_wb.trim() && !WB_NOM_REGEX.test(draft.nomenklatura_wb.trim())) {
    errs.nomenklatura_wb = "WB-номенклатура: 7–12 цифр"
  }
  if (draft.artikul_ozon.length > 50) {
    errs.artikul_ozon = "OZON-артикул: до 50 символов"
  }
  return errs
}

function draftToPatch(d: ArtikulDraft, base: ArtikulDetail): ArtikulPatch {
  const patch: ArtikulPatch = {}
  if (d.artikul.trim() !== base.artikul) patch.artikul = d.artikul.trim()
  const wbNomNum = d.nomenklatura_wb.trim()
    ? Number(d.nomenklatura_wb.trim())
    : null
  if (wbNomNum !== (base.nomenklatura_wb ?? null)) {
    patch.nomenklatura_wb = wbNomNum
  }
  const ozon = d.artikul_ozon.trim() || null
  if (ozon !== (base.artikul_ozon ?? null)) {
    patch.artikul_ozon = ozon
  }
  if (d.status_id != null && d.status_id !== (base.status_id ?? null)) {
    patch.status_id = d.status_id
  }
  return patch
}

// ─── Component ─────────────────────────────────────────────────────────────

type TabId = "description" | "sku" | "history"

interface ArtikulDrawerProps {
  artikulId: number
  onClose: () => void
}

export function ArtikulDrawer({ artikulId, onClose }: ArtikulDrawerProps) {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<TabId>("description")
  const [draft, setDraft] = useState<ArtikulDraft | null>(null)
  const [errors, setErrors] = useState<FormErrors>({})

  // Esc → закрыть.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  // Detail.
  const detailQ = useQuery({
    queryKey: ["catalog", "artikul-detail", artikulId],
    queryFn: () => fetchArtikulDetail(artikulId),
    staleTime: 30 * 1000,
  })
  const detail = detailQ.data ?? null

  // Resync draft when detail loads/changes.
  useEffect(() => {
    if (detail) setDraft(detailToDraft(detail))
  }, [detail])

  // Statusy lookup (для бейджей + selector).
  const statusyQ = useQuery({
    queryKey: ["catalog", "statusy"],
    queryFn: fetchStatusy,
    staleTime: 5 * 60 * 1000,
  })
  const statusy = statusyQ.data ?? []
  const artikulStatuses = useMemo(
    () => statusy.filter((s) => s.tip === "artikul"),
    [statusy],
  )
  const statusById = useMemo(() => {
    const m = new Map<number, { nazvanie: string; color: string | null }>()
    for (const s of statusy) m.set(s.id, { nazvanie: s.nazvanie, color: s.color })
    return m
  }, [statusy])

  // Save mutation.
  const saveMut = useMutation({
    mutationFn: async () => {
      if (!detail || !draft) return
      const patch = draftToPatch(draft, detail)
      if (Object.keys(patch).length === 0) return
      await updateArtikul(detail.id, patch)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["catalog", "artikul-detail", artikulId] })
      void queryClient.invalidateQueries({ queryKey: ["artikuly-registry"] })
      void queryClient.invalidateQueries({ queryKey: ["catalog", "matrix-list"] })
      toast.success("Сохранено")
    },
    onError: (err) => {
      toast.error(translateError(err))
    },
  })

  // Archive (set status to «Архив» из artikulStatuses).
  const archiveMut = useMutation({
    mutationFn: async () => {
      if (!detail) return
      const archiveStatus = artikulStatuses.find(
        (s) => s.nazvanie.toLowerCase().includes("архив"),
      )
      if (!archiveStatus) {
        throw new Error("Статус 'Архив' не найден в справочнике")
      }
      await updateArtikul(detail.id, { status_id: archiveStatus.id })
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["catalog", "artikul-detail", artikulId] })
      void queryClient.invalidateQueries({ queryKey: ["artikuly-registry"] })
      toast.success("Артикул отправлен в архив")
    },
    onError: (err) => {
      toast.error(translateError(err))
    },
  })

  // Validate on draft change.
  useEffect(() => {
    if (!draft) return
    setErrors(validateDraft(draft))
  }, [draft])

  const isDirty = useMemo(() => {
    if (!detail || !draft) return false
    return Object.keys(draftToPatch(draft, detail)).length > 0
  }, [detail, draft])

  const hasErrors = Object.keys(errors).length > 0
  const canSave = isDirty && !hasErrors && !saveMut.isPending

  return (
    <>
      {/* backdrop */}
      <div
        className="fixed inset-0 bg-black/30 z-40"
        onClick={onClose}
        aria-hidden="true"
      />
      {/* drawer */}
      <div
        className="fixed inset-y-0 right-0 w-[720px] bg-white rounded-l-2xl shadow-2xl z-50 overflow-y-auto flex flex-col"
        role="dialog"
        aria-label="Карточка артикула"
      >
        {detailQ.isLoading && (
          <div className="flex-1 flex items-center justify-center text-stone-400 text-sm">
            <Loader2 className="w-4 h-4 animate-spin mr-2" /> Загрузка артикула…
          </div>
        )}
        {detailQ.error && (
          <div className="flex-1 flex items-center justify-center text-red-500 text-sm px-6">
            Ошибка загрузки: {String(detailQ.error)}
          </div>
        )}
        {!detailQ.isLoading && !detailQ.error && !detail && (
          <div className="flex-1 flex items-center justify-center text-stone-500 text-sm px-6">
            Артикул #{artikulId} не найден.
          </div>
        )}
        {detail && draft && (
          <>
            <ArtikulHeader
              detail={detail}
              statusById={statusById}
              onDuplicate={() => {
                // W10.6 — заглушка под Wave D (CRUD дублирования). Минимально —
                // копируем имя в буфер.
                if (navigator.clipboard) {
                  void navigator.clipboard.writeText(detail.artikul)
                  toast.success("Имя артикула скопировано в буфер обмена")
                }
              }}
              onArchive={() => archiveMut.mutate()}
              onClose={onClose}
              archiving={archiveMut.isPending}
            />

            {/* Tabs */}
            <div className="border-b border-stone-200 bg-white px-6 flex gap-1 shrink-0">
              {(
                [
                  { id: "description", label: "Описание" },
                  { id: "sku", label: "SKU", count: detail.tovary.length },
                  { id: "history", label: "История" },
                ] as Array<{ id: TabId; label: string; count?: number }>
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
                  {typeof t.count === "number" && (
                    <span className="ml-1.5 text-xs text-stone-400 tabular-nums">
                      {t.count}
                    </span>
                  )}
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
                  artikulStatuses={artikulStatuses}
                  detail={detail}
                />
              )}
              {tab === "sku" && (
                <TabSKU detail={detail} statusById={statusById} />
              )}
              {tab === "history" && (
                <TabHistory rowId={detail.id} />
              )}
            </div>

            {/* Footer (save/cancel) */}
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

interface ArtikulHeaderProps {
  detail: ArtikulDetail
  statusById: Map<number, { nazvanie: string; color: string | null }>
  onDuplicate: () => void
  onArchive: () => void
  onClose: () => void
  archiving: boolean
}

function ArtikulHeader({
  detail, statusById, onDuplicate, onArchive, onClose, archiving,
}: ArtikulHeaderProps) {
  const status = detail.status_id != null ? statusById.get(detail.status_id) : null
  return (
    <div className="border-b border-stone-200 bg-white shrink-0 px-6 py-4 flex items-center gap-4">
      {/* color swatch */}
      <ColorSwatch hex={detail.cvet_hex} size={48} />
      <div className="flex-1 min-w-0">
        <div className="text-[11px] uppercase tracking-wider text-stone-400 mb-0.5">
          Артикул
          {detail.fabrika && (
            <>
              <span className="mx-1.5 text-stone-300">·</span>
              <span>{detail.fabrika}</span>
            </>
          )}
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-2xl text-stone-900 font-mono">{detail.artikul}</h2>
          {status && (
            <StatusBadge
              status={{ nazvanie: status.nazvanie, color: status.color ?? "gray" }}
            />
          )}
        </div>
        <div className="mt-1 flex items-center gap-3 flex-wrap text-xs text-stone-500">
          {detail.model_osnova_kod && (
            <span className="font-mono">{detail.model_osnova_kod}</span>
          )}
          {detail.nazvanie_etiketka && (
            <span className="truncate max-w-[280px]">{detail.nazvanie_etiketka}</span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <button
          type="button"
          onClick={onDuplicate}
          className="px-3 py-1.5 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5"
          title="Скопировать имя артикула в буфер обмена"
        >
          <Copy className="w-3.5 h-3.5" /> Дублировать
        </button>
        <button
          type="button"
          onClick={onArchive}
          disabled={archiving}
          className="px-3 py-1.5 text-xs text-stone-700 hover:bg-stone-100 rounded-md flex items-center gap-1.5 disabled:opacity-40"
        >
          <Archive className="w-3.5 h-3.5" /> В архив
        </button>
        <div className="h-6 w-px bg-stone-200 mx-1" />
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
  draft: ArtikulDraft
  setDraft: (d: ArtikulDraft) => void
  errors: FormErrors
  artikulStatuses: { id: number; nazvanie: string; color: string | null }[]
  detail: ArtikulDetail
}

function TabDescription({ draft, setDraft, errors, artikulStatuses, detail }: TabDescriptionProps) {
  const set = useCallback(
    <K extends keyof ArtikulDraft>(k: K, v: ArtikulDraft[K]) => {
      setDraft({ ...draft, [k]: v })
    },
    [draft, setDraft],
  )
  return (
    <div className="px-6 py-5 space-y-5">
      <Field label="Артикул" required error={errors.artikul} hint="Формат: model/color (например: Wendy/black)">
        <input
          type="text"
          value={draft.artikul}
          onChange={(e) => set("artikul", e.target.value)}
          className={inputClass(!!errors.artikul)}
          placeholder="Wendy/black"
        />
      </Field>

      <Field label="Статус">
        <select
          value={draft.status_id ?? ""}
          onChange={(e) => set("status_id", e.target.value ? Number(e.target.value) : null)}
          className={inputClass(false)}
        >
          <option value="">— не выбран —</option>
          {artikulStatuses.map((s) => (
            <option key={s.id} value={s.id}>
              {s.nazvanie}
            </option>
          ))}
        </select>
      </Field>

      <div className="grid grid-cols-2 gap-4">
        <Field label="WB-номенклатура" error={errors.nomenklatura_wb} hint="7–12 цифр">
          <input
            type="text"
            inputMode="numeric"
            value={draft.nomenklatura_wb}
            onChange={(e) => set("nomenklatura_wb", e.target.value.replace(/\D/g, ""))}
            className={inputClass(!!errors.nomenklatura_wb)}
            placeholder="123456789"
          />
        </Field>
        <Field label="OZON-артикул" error={errors.artikul_ozon} hint="До 50 символов">
          <input
            type="text"
            value={draft.artikul_ozon}
            onChange={(e) => set("artikul_ozon", e.target.value)}
            className={inputClass(!!errors.artikul_ozon)}
            placeholder="OZ-12345"
            maxLength={50}
          />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-4 text-xs">
        <ReadOnly label="Модель" value={detail.model_osnova_kod} />
        <ReadOnly label="Вариация" value={detail.model_kod} />
        <ReadOnly label="Цвет" value={
          detail.cvet_color_code
            ? `${detail.cvet_color_code}${detail.cvet_nazvanie ? ` · ${detail.cvet_nazvanie}` : ""}`
            : null
        } />
        <ReadOnly label="Категория" value={detail.kategoriya} />
        <ReadOnly label="Коллекция" value={detail.kollekciya} />
        <ReadOnly label="Фабрика" value={detail.fabrika} />
      </div>

      <div className="text-[11px] text-stone-400 italic pt-3 border-t border-stone-200">
        Цвет, модель, категория редактируются inline в реестре (double-click по
        ячейке) или в карточке модели.
      </div>
    </div>
  )
}

// ─── Tab: SKU ──────────────────────────────────────────────────────────────

interface TabSKUProps {
  detail: ArtikulDetail
  statusById: Map<number, { nazvanie: string; color: string | null }>
}

function TabSKU({ detail, statusById }: TabSKUProps) {
  const sorted = useMemo(
    () =>
      [...detail.tovary].sort((a, b) =>
        compareRazmer(a.razmer_nazvanie ?? null, b.razmer_nazvanie ?? null),
      ),
    [detail.tovary],
  )

  if (sorted.length === 0) {
    return (
      <div className="px-6 py-8">
        <EmptyState
          title="Нет SKU для этого артикула"
          description="SKU создаются автоматически по размерному ряду модели."
        />
      </div>
    )
  }

  return (
    <div className="px-6 py-5">
      <div className="border border-stone-200 rounded-md overflow-hidden bg-white">
        <table className="w-full text-sm">
          <thead className="bg-stone-50/80 border-b border-stone-200">
            <tr className="text-left text-[11px] uppercase tracking-wider text-stone-500">
              <th className="px-3 py-2 font-medium">Баркод</th>
              <th className="px-3 py-2 font-medium">Размер</th>
              <th className="px-3 py-2 font-medium border-l border-stone-200">WB</th>
              <th className="px-3 py-2 font-medium">OZON</th>
              <th className="px-3 py-2 font-medium">Сайт</th>
              <th className="px-3 py-2 font-medium">Lamoda</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((t) => (
              <tr key={t.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60">
                <td className="px-3 py-2 font-mono text-xs text-stone-700">
                  <CellText title={t.barkod}>{t.barkod}</CellText>
                </td>
                <td className="px-3 py-2 font-mono text-xs">
                  <CellText title={t.razmer_nazvanie ?? ""}>{t.razmer_nazvanie ?? "—"}</CellText>
                </td>
                <td className="px-3 py-2 border-l border-stone-100">
                  {renderSkuStatus(t.status_id, statusById)}
                </td>
                <td className="px-3 py-2">{renderSkuStatus(t.status_ozon_id, statusById)}</td>
                <td className="px-3 py-2">{renderSkuStatus(t.status_sayt_id, statusById)}</td>
                <td className="px-3 py-2">{renderSkuStatus(t.status_lamoda_id, statusById)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function renderSkuStatus(
  statusId: number | null,
  statusById: Map<number, { nazvanie: string; color: string | null }>,
): React.ReactNode {
  if (statusId == null) {
    return <span className="text-[11px] text-stone-400 italic">—</span>
  }
  const s = statusById.get(statusId)
  if (!s) return <span className="text-[11px] text-stone-500 font-mono">#{statusId}</span>
  return (
    <StatusBadge
      status={{ nazvanie: s.nazvanie, color: s.color ?? "gray" }}
      compact
      size="sm"
    />
  )
}

// ─── Tab: История ───────────────────────────────────────────────────────────

function TabHistory({ rowId }: { rowId: number }) {
  const auditQ = useQuery({
    queryKey: ["catalog", "audit", "artikuly", rowId],
    queryFn: () => fetchAuditFor("artikuly", rowId, 50),
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
          description="Аудит включён, но изменений по этому артикулу пока нет."
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
