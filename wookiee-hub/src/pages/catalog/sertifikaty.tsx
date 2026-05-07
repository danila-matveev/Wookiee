import { useMemo, useState } from "react"
import { ExternalLink } from "lucide-react"
import { CatalogTable, type TableColumn } from "@/components/catalog/layout/catalog-table"
import { useReferenceCrud } from "./references/_use-reference"
import {
  fetchSertifikaty,
  insertSertifikat,
  updateSertifikat,
  deleteSertifikat,
  type Sertifikat,
  type SertifikatPayload,
} from "@/lib/catalog/service"
import {
  AddButton,
  ConfirmDialog,
  ErrorBlock,
  PageHeader,
  PageShell,
  RefModal,
  RowActions,
  SearchBox,
  SkeletonTable,
  type RefFieldDef,
} from "./references/_shared"

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

const FIELDS: RefFieldDef[] = [
  { key: "nazvanie", label: "Название", type: "text", required: true },
  { key: "tip", label: "Тип", type: "select", options: TIP_OPTIONS },
  { key: "nomer", label: "Номер", type: "text" },
  { key: "data_vydachi", label: "Дата выдачи", type: "date" },
  { key: "data_okonchaniya", label: "Дата окончания", type: "date" },
  { key: "organ_sertifikacii", label: "Орган сертификации", type: "text" },
  { key: "gruppa_sertifikata", label: "Группа", type: "select", options: GRUPPA_OPTIONS },
  { key: "file_url", label: "Ссылка на файл", type: "file_url", placeholder: "https://…" },
]

function formatDate(iso: string | null): string {
  if (!iso) return "—"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" })
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
          <a
            href={r.file_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-stone-700 hover:text-stone-900 text-xs"
            onClick={(e) => e.stopPropagation()}
          >
            <ExternalLink className="w-3.5 h-3.5" />
            <span>открыть</span>
          </a>
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

  const handleSave = async (vals: Record<string, unknown>) => {
    const get = (k: string): string | null => {
      const v = vals[k]
      return v == null || v === "" ? null : String(v)
    }
    const payload: SertifikatPayload = {
      nazvanie: String(vals.nazvanie ?? "").trim(),
      tip: get("tip"),
      nomer: get("nomer"),
      data_vydachi: get("data_vydachi"),
      data_okonchaniya: get("data_okonchaniya"),
      organ_sertifikacii: get("organ_sertifikacii"),
      gruppa_sertifikata: get("gruppa_sertifikata"),
      file_url: get("file_url"),
    }
    if (editing) {
      await ref.update.mutateAsync({ id: editing.id, patch: payload })
      setEditing(null)
    } else {
      await ref.insert.mutateAsync(payload)
      setCreating(false)
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
        <RefModal
          title={editing ? "Редактировать сертификат" : "Новый сертификат"}
          fields={FIELDS}
          initial={
            editing
              ? {
                  nazvanie: editing.nazvanie,
                  tip: editing.tip ?? "",
                  nomer: editing.nomer ?? "",
                  data_vydachi: editing.data_vydachi ?? "",
                  data_okonchaniya: editing.data_okonchaniya ?? "",
                  organ_sertifikacii: editing.organ_sertifikacii ?? "",
                  gruppa_sertifikata: editing.gruppa_sertifikata ?? "",
                  file_url: editing.file_url ?? "",
                }
              : undefined
          }
          onSave={handleSave}
          onCancel={() => {
            setEditing(null)
            setCreating(false)
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
