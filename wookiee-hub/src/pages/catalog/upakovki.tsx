import { useMemo, useState } from "react"
import { ExternalLink } from "lucide-react"
import { CatalogTable, type TableColumn } from "@/components/catalog/layout/catalog-table"
import { useReferenceCrud } from "./references/_use-reference"
import {
  fetchUpakovki,
  insertUpakovka,
  updateUpakovka,
  deleteUpakovka,
  type Upakovka,
  type UpakovkaPayload,
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
  { value: "pakey", label: "Пакет" },
  { value: "pakey_zip", label: "Пакет zip" },
  { value: "korobka", label: "Коробка" },
  { value: "korobka_print", label: "Коробка с принтом" },
]

const TIP_LABELS: Record<string, string> = Object.fromEntries(
  TIP_OPTIONS.map((o) => [o.value, o.label]),
)

const FIELDS: RefFieldDef[] = [
  { key: "nazvanie", label: "Название", type: "text", required: true, placeholder: "Mailer Box S" },
  { key: "tip", label: "Тип", type: "select", options: TIP_OPTIONS, placeholder: "Выберите тип…" },
  { key: "price_yuan", label: "Цена (¥)", type: "number" },
  { key: "dlina_cm", label: "Длина (см)", type: "number" },
  { key: "shirina_cm", label: "Ширина (см)", type: "number" },
  { key: "vysota_cm", label: "Высота (см)", type: "number" },
  { key: "obem_l", label: "Объём (л)", type: "number" },
  { key: "srok_izgotovleniya_dni", label: "Срок изгот. (дн.)", type: "number" },
  { key: "file_link", label: "Ссылка на файл", type: "file_url", placeholder: "https://drive.google.com/…" },
  { key: "notes", label: "Заметки", type: "textarea" },
  { key: "poryadok", label: "Порядок", type: "number" },
]

export function UpakovkiPage() {
  const ref = useReferenceCrud<Upakovka, UpakovkaPayload>(
    "upakovki",
    fetchUpakovki,
    { insert: insertUpakovka, update: updateUpakovka, remove: deleteUpakovka },
  )
  const [search, setSearch] = useState("")
  const [editing, setEditing] = useState<Upakovka | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<Upakovka | null>(null)

  const filtered = useMemo(() => {
    const data = ref.list.data ?? []
    if (!search.trim()) return data
    const q = search.toLowerCase()
    return data.filter((r) =>
      [r.nazvanie, r.tip, r.notes]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q)),
    )
  }, [ref.list.data, search])

  const columns: TableColumn<Upakovka>[] = [
    { key: "nazvanie", label: "Название" },
    {
      key: "tip",
      label: "Тип",
      render: (r) =>
        r.tip ? (
          <span className="inline-flex items-center px-2 py-0.5 text-[10px] uppercase tracking-wider bg-surface-muted text-secondary rounded">
            {TIP_LABELS[r.tip] ?? r.tip}
          </span>
        ) : (
          <span className="text-label">—</span>
        ),
    },
    {
      key: "price_yuan",
      label: "Цена ¥",
      render: (r) =>
        r.price_yuan != null ? (
          <span className="text-secondary tabular-nums font-mono text-xs">
            {r.price_yuan.toFixed(2)}
          </span>
        ) : (
          <span className="text-label">—</span>
        ),
    },
    {
      key: "dimensions",
      label: "ДxШxВ см",
      render: (r) => {
        const parts = [r.dlina_cm, r.shirina_cm, r.vysota_cm]
        if (parts.every((p) => p == null)) return <span className="text-label">—</span>
        return (
          <span className="text-secondary tabular-nums font-mono text-xs">
            {parts.map((p) => p ?? "—").join(" × ")}
          </span>
        )
      },
    },
    {
      key: "srok_izgotovleniya_dni",
      label: "Срок (дн.)",
      render: (r) =>
        r.srok_izgotovleniya_dni != null ? (
          <span className="text-secondary tabular-nums font-mono text-xs">
            {r.srok_izgotovleniya_dni}
          </span>
        ) : (
          <span className="text-label">—</span>
        ),
    },
    {
      key: "file_link",
      label: "Файл",
      render: (r) =>
        r.file_link ? (
          <a
            href={r.file_link}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-secondary hover:text-primary text-xs"
            onClick={(e) => e.stopPropagation()}
          >
            <ExternalLink className="w-3.5 h-3.5" />
            <span>открыть</span>
          </a>
        ) : (
          <span className="text-label">—</span>
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
    const num = (k: string): number | null => {
      const v = vals[k]
      return v == null || v === "" ? null : Number(v)
    }
    const str = (k: string): string | null => {
      const v = vals[k]
      return v == null || v === "" ? null : String(v)
    }
    const payload: UpakovkaPayload = {
      nazvanie: String(vals.nazvanie ?? "").trim(),
      tip: str("tip"),
      price_yuan: num("price_yuan"),
      dlina_cm: num("dlina_cm"),
      shirina_cm: num("shirina_cm"),
      vysota_cm: num("vysota_cm"),
      obem_l: num("obem_l"),
      srok_izgotovleniya_dni: num("srok_izgotovleniya_dni"),
      file_link: str("file_link"),
      notes: str("notes"),
      poryadok: num("poryadok"),
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
        title="Упаковки"
        subtitle="Виды упаковки с габаритами и стоимостью"
        count={ref.list.data?.length ?? 0}
        isLoading={ref.list.isLoading}
        actions={<AddButton onClick={() => setCreating(true)} />}
      />
      <SearchBox value={search} onChange={setSearch} placeholder="Поиск по названию или типу…" />
      {ref.list.error && <ErrorBlock message={ref.list.error.message} />}
      {ref.list.isLoading ? (
        <SkeletonTable rows={5} cols={7} />
      ) : (
        <CatalogTable columns={columns} data={filtered} emptyText="Упаковки не найдены" />
      )}

      {(creating || editing) && (
        <RefModal
          title={editing ? "Редактировать упаковку" : "Новая упаковка"}
          fields={FIELDS}
          initial={
            editing
              ? {
                  nazvanie: editing.nazvanie,
                  tip: editing.tip ?? "",
                  price_yuan: editing.price_yuan ?? null,
                  dlina_cm: editing.dlina_cm ?? null,
                  shirina_cm: editing.shirina_cm ?? null,
                  vysota_cm: editing.vysota_cm ?? null,
                  obem_l: editing.obem_l ?? null,
                  srok_izgotovleniya_dni: editing.srok_izgotovleniya_dni ?? null,
                  file_link: editing.file_link ?? "",
                  notes: editing.notes ?? "",
                  poryadok: editing.poryadok ?? null,
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
        title="Удалить упаковку?"
        message={deleting ? `«${deleting.nazvanie}» будет удалена.` : undefined}
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
