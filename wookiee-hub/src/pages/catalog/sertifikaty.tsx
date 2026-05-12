import { useEffect, useMemo, useState } from "react"
import { ExternalLink, X } from "lucide-react"
import { CatalogTable, type TableColumn } from "@/components/catalog/layout/catalog-table"
import { AssetUploader } from "@/components/catalog/ui"
import { useReferenceCrud } from "./references/_use-reference"
import {
  fetchSertifikaty,
  insertSertifikat,
  updateSertifikat,
  deleteSertifikat,
  getCatalogAssetSignedUrl,
  makeStoragePathForSertifikat,
  type Sertifikat,
  type SertifikatPayload,
} from "@/lib/catalog/service"
import {
  AddButton,
  ConfirmDialog,
  ErrorBlock,
  PageHeader,
  PageShell,
  RowActions,
  SearchBox,
  SkeletonTable,
} from "./references/_shared"
import { cn } from "@/lib/utils"

const TIP_OPTIONS = [
  { value: "СоответствияТР", label: "Соответствия ТР" },
  { value: "Декларация", label: "Декларация" },
  { value: "Сертификат происхождения", label: "Сертификат происхождения" },
  { value: "Качества", label: "Качества" },
]

const GRUPPA_OPTIONS = [
  { value: "1", label: "1 (бельё, маленькие дети)" },
  { value: "2", label: "2 (одежда взрослые)" },
  { value: "3", label: "3 (спорт)" },
]

function formatDate(iso: string | null): string {
  if (!iso) return "—"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" })
}

/**
 * Резолвит значение `sertifikaty.file_url` в URL для открытия.
 *
 * Backwards compat:
 * - Если значение начинается с `http://` или `https://` — это legacy URL,
 *   возвращаем как есть (старые сертификаты до миграции на Storage).
 * - Иначе — это путь в bucket `catalog-assets`, генерируем signed URL.
 */
async function resolveSertifikatUrl(value: string | null): Promise<string | null> {
  if (!value) return null
  if (/^https?:\/\//i.test(value)) return value
  return getCatalogAssetSignedUrl(value)
}

export function SertifikatyPage() {
  const ref = useReferenceCrud<Sertifikat, SertifikatPayload>(
    "sertifikaty",
    fetchSertifikaty,
    {
      insert: insertSertifikat,
      update: updateSertifikat,
      remove: deleteSertifikat,
    },
  )
  const [search, setSearch] = useState("")
  const [editing, setEditing] = useState<Sertifikat | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<Sertifikat | null>(null)

  const filtered = useMemo(() => {
    const data = ref.list.data ?? []
    if (!search.trim()) return data
    const q = search.toLowerCase()
    return data.filter((r) =>
      [r.nazvanie, r.tip, r.nomer, r.organ_sertifikacii]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q)),
    )
  }, [ref.list.data, search])

  const columns: TableColumn<Sertifikat>[] = [
    { key: "nazvanie", label: "Название" },
    {
      key: "tip",
      label: "Тип",
      render: (r) =>
        r.tip ? (
          <span className="inline-flex items-center px-2 py-0.5 text-[10px] uppercase tracking-wider bg-stone-100 text-stone-700 rounded">
            {r.tip}
          </span>
        ) : (
          <span className="text-stone-400">—</span>
        ),
    },
    {
      key: "nomer",
      label: "Номер",
      render: (r) =>
        r.nomer ? (
          <span className="text-stone-700 font-mono text-xs">{r.nomer}</span>
        ) : (
          <span className="text-stone-400">—</span>
        ),
    },
    {
      key: "data_vydachi",
      label: "Выдан",
      render: (r) => (
        <span className="text-stone-600 text-xs tabular-nums">{formatDate(r.data_vydachi)}</span>
      ),
    },
    {
      key: "data_okonchaniya",
      label: "Окончание",
      render: (r) => (
        <span className="text-stone-600 text-xs tabular-nums">{formatDate(r.data_okonchaniya)}</span>
      ),
    },
    {
      key: "organ_sertifikacii",
      label: "Орган",
      render: (r) =>
        r.organ_sertifikacii ? (
          <span className="text-stone-600 text-xs" title={r.organ_sertifikacii}>
            {r.organ_sertifikacii.length > 30
              ? `${r.organ_sertifikacii.slice(0, 30)}…`
              : r.organ_sertifikacii}
          </span>
        ) : (
          <span className="text-stone-400">—</span>
        ),
    },
    {
      key: "gruppa_sertifikata",
      label: "Группа",
      render: (r) =>
        r.gruppa_sertifikata ? (
          <span className="text-stone-700 font-mono text-xs">{r.gruppa_sertifikata}</span>
        ) : (
          <span className="text-stone-400">—</span>
        ),
    },
    {
      key: "file_url",
      label: "Файл",
      render: (r) =>
        r.file_url ? (
          <button
            type="button"
            onClick={async (e) => {
              e.stopPropagation()
              try {
                const url = await resolveSertifikatUrl(r.file_url)
                if (url) window.open(url, "_blank", "noopener,noreferrer")
              } catch {
                /* swallow — UI: ничего страшного, signed URL может быть невалиден */
              }
            }}
            className="inline-flex items-center gap-1 text-stone-700 hover:text-stone-900 text-xs"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            <span>открыть</span>
          </button>
        ) : (
          <span className="text-stone-400">—</span>
        ),
    },
    {
      key: "actions",
      label: "",
      render: (r) => (
        <RowActions onEdit={() => setEditing(r)} onDelete={() => setDeleting(r)} />
      ),
    },
  ]

  const handleSave = async (payload: SertifikatPayload, id: number | null) => {
    if (id != null) {
      await ref.update.mutateAsync({ id, patch: payload })
    } else {
      await ref.insert.mutateAsync(payload)
    }
  }

  return (
    <PageShell>
      <PageHeader
        title="Сертификаты"
        subtitle="Сертификаты соответствия и декларации"
        count={ref.list.data?.length ?? 0}
        isLoading={ref.list.isLoading}
        actions={<AddButton onClick={() => setCreating(true)} />}
      />
      <SearchBox value={search} onChange={setSearch} placeholder="Поиск по названию, номеру, органу…" />
      {ref.list.error && <ErrorBlock message={ref.list.error.message} />}
      {ref.list.isLoading ? (
        <SkeletonTable rows={5} cols={9} />
      ) : (
        <CatalogTable columns={columns} data={filtered} emptyText="Сертификаты не найдены" />
      )}

      {(creating || editing) && (
        <SertifikatModal
          initial={editing}
          onSave={handleSave}
          onClose={() => {
            setEditing(null)
            setCreating(false)
          }}
          onPathChange={async (id, newPath) => {
            // После upload — патчим только file_url, не дёргая остальные поля.
            await ref.update.mutateAsync({ id, patch: { file_url: newPath } })
            // Синхронизируем локальный editing, чтобы AssetUploader перерисовался.
            setEditing((prev) => (prev && prev.id === id ? { ...prev, file_url: newPath } : prev))
          }}
        />
      )}

      <ConfirmDialog
        open={!!deleting}
        title="Удалить сертификат?"
        message={deleting ? `«${deleting.nazvanie}» будет удалён.` : undefined}
        onConfirm={async () => {
          if (deleting) {
            await ref.remove.mutateAsync(deleting.id)
            setDeleting(null)
          }
        }}
        onCancel={() => setDeleting(null)}
      />
    </PageShell>
  )
}

// ─── SertifikatModal ───────────────────────────────────────────────────────
//
// Кастомная модалка вместо общего RefModal — нам нужен AssetUploader для PDF,
// который не вписывается в типы RefModal (file_url там = `<input type="url">`).

interface SertifikatFormState {
  nazvanie: string
  tip: string
  nomer: string
  data_vydachi: string
  data_okonchaniya: string
  organ_sertifikacii: string
  gruppa_sertifikata: string
  file_url: string | null
}

const EMPTY_STATE: SertifikatFormState = {
  nazvanie: "",
  tip: "",
  nomer: "",
  data_vydachi: "",
  data_okonchaniya: "",
  organ_sertifikacii: "",
  gruppa_sertifikata: "",
  file_url: null,
}

function toFormState(s: Sertifikat | null): SertifikatFormState {
  if (!s) return EMPTY_STATE
  return {
    nazvanie: s.nazvanie ?? "",
    tip: s.tip ?? "",
    nomer: s.nomer ?? "",
    data_vydachi: s.data_vydachi ?? "",
    data_okonchaniya: s.data_okonchaniya ?? "",
    organ_sertifikacii: s.organ_sertifikacii ?? "",
    gruppa_sertifikata: s.gruppa_sertifikata ?? "",
    file_url: s.file_url ?? null,
  }
}

interface SertifikatModalProps {
  /** null = create mode; объект = edit mode. */
  initial: Sertifikat | null
  /** Сохранение метаданных (insert при initial=null, update иначе). */
  onSave: (payload: SertifikatPayload, id: number | null) => Promise<void>
  /** После успешного upload AssetUploader записывает path — родитель пишет в БД. */
  onPathChange: (id: number, newPath: string | null) => Promise<void>
  onClose: () => void
}

function SertifikatModal({ initial, onSave, onPathChange, onClose }: SertifikatModalProps) {
  const [form, setForm] = useState<SertifikatFormState>(() => toFormState(initial))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const id = initial?.id ?? null

  // Esc to close.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  const update = <K extends keyof SertifikatFormState>(k: K, v: SertifikatFormState[K]) => {
    setForm((p) => ({ ...p, [k]: v }))
  }

  const handleSave = async () => {
    if (!form.nazvanie.trim()) {
      setError("Заполните обязательное поле «Название»")
      return
    }
    setError(null)
    setSaving(true)
    try {
      const payload: SertifikatPayload = {
        nazvanie: form.nazvanie.trim(),
        tip: form.tip || null,
        nomer: form.nomer || null,
        data_vydachi: form.data_vydachi || null,
        data_okonchaniya: form.data_okonchaniya || null,
        organ_sertifikacii: form.organ_sertifikacii || null,
        gruppa_sertifikata: form.gruppa_sertifikata || null,
        file_url: form.file_url,
      }
      await onSave(payload, id)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения")
    } finally {
      setSaving(false)
    }
  }

  const inputCls =
    "w-full px-2.5 py-1.5 text-sm border border-stone-200 rounded-md bg-white outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900"
  const labelCls = "block text-[11px] uppercase tracking-wider text-stone-500 mb-1"

  // Если file_url выглядит как URL — это legacy, AssetUploader не покажет превью
  // через signed URL. Показываем подсказку и кнопку «убрать», чтобы оператор
  // мог удалить legacy URL и загрузить настоящий PDF.
  const isLegacyUrl = form.file_url != null && /^https?:\/\//i.test(form.file_url)

  return (
    <div
      className="fixed inset-0 z-50 bg-stone-900/40 flex items-center justify-center p-4"
      onClick={onClose}
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
            {id != null ? "Редактировать сертификат" : "Новый сертификат"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1 hover:bg-stone-100 rounded"
            aria-label="Close"
          >
            <X className="w-4 h-4 text-stone-500" />
          </button>
        </div>

        <div className="px-5 py-4 grid grid-cols-2 gap-3 max-h-[70vh] overflow-y-auto">
          <div className="col-span-2">
            <label className={labelCls}>
              Название<span className="text-red-500 ml-0.5">*</span>
            </label>
            <input
              type="text"
              value={form.nazvanie}
              onChange={(e) => update("nazvanie", e.target.value)}
              className={inputCls}
            />
          </div>

          <div>
            <label className={labelCls}>Тип</label>
            <select
              value={form.tip}
              onChange={(e) => update("tip", e.target.value)}
              className={inputCls}
            >
              <option value="">Выберите…</option>
              {TIP_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className={labelCls}>Номер</label>
            <input
              type="text"
              value={form.nomer}
              onChange={(e) => update("nomer", e.target.value)}
              className={inputCls}
            />
          </div>

          <div>
            <label className={labelCls}>Дата выдачи</label>
            <input
              type="date"
              value={form.data_vydachi}
              onChange={(e) => update("data_vydachi", e.target.value)}
              className={inputCls}
            />
          </div>

          <div>
            <label className={labelCls}>Дата окончания</label>
            <input
              type="date"
              value={form.data_okonchaniya}
              onChange={(e) => update("data_okonchaniya", e.target.value)}
              className={inputCls}
            />
          </div>

          <div className="col-span-2">
            <label className={labelCls}>Орган сертификации</label>
            <input
              type="text"
              value={form.organ_sertifikacii}
              onChange={(e) => update("organ_sertifikacii", e.target.value)}
              className={inputCls}
            />
          </div>

          <div>
            <label className={labelCls}>Группа</label>
            <select
              value={form.gruppa_sertifikata}
              onChange={(e) => update("gruppa_sertifikata", e.target.value)}
              className={inputCls}
            >
              <option value="">Выберите…</option>
              {GRUPPA_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {/* Файл сертификата — AssetUploader (PDF). */}
          <div className="col-span-2">
            <label className="block text-xs text-stone-600 mb-1.5">
              Файл сертификата (PDF)
            </label>
            {id == null ? (
              <div className="px-3 py-4 border border-dashed border-stone-300 rounded-lg bg-stone-50 text-xs text-stone-500">
                Сначала сохраните сертификат — потом откройте его на редактирование
                и загрузите PDF.
              </div>
            ) : isLegacyUrl ? (
              <div className="space-y-2">
                <div className="px-3 py-2 border border-stone-200 rounded-lg bg-stone-50 text-xs text-stone-600 flex items-center justify-between gap-2">
                  <a
                    href={form.file_url ?? "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="truncate hover:underline"
                  >
                    {form.file_url}
                  </a>
                  <button
                    type="button"
                    onClick={async () => {
                      // Сбрасываем file_url локально и в БД, чтобы AssetUploader
                      // перешёл в режим "загрузить новый".
                      update("file_url", null)
                      await onPathChange(id, null)
                    }}
                    className="shrink-0 text-[11px] text-stone-500 hover:text-stone-900 underline"
                  >
                    убрать legacy URL
                  </button>
                </div>
                <p className="text-[11px] text-stone-400">
                  Это старая ссылка. Уберите её и загрузите PDF в Storage —
                  будет работать стабильнее (через signed URL).
                </p>
              </div>
            ) : (
              <>
                <AssetUploader
                  kind="pdf"
                  path={form.file_url}
                  buildPath={(file) => makeStoragePathForSertifikat(id, file.name)}
                  onChange={async (newPath) => {
                    update("file_url", newPath)
                    await onPathChange(id, newPath)
                  }}
                  label="Сертификат"
                />
                <p className="text-[11px] text-stone-400 mt-1">
                  PDF до 10 МБ. Старые сертификаты с URL продолжают работать.
                </p>
              </>
            )}
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
            {saving ? "Сохраняем…" : "Сохранить"}
          </button>
        </div>
      </div>
    </div>
  )
}
