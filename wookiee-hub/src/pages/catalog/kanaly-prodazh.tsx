import { useMemo, useState } from "react"
import { CatalogTable, type TableColumn } from "@/components/catalog/layout/catalog-table"
import { useReferenceCrud } from "./references/_use-reference"
import {
  fetchKanalyProdazh,
  insertKanalProdazh,
  updateKanalProdazh,
  deleteKanalProdazh,
  type KanalProdazh,
  type KanalProdazhPayload,
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

const FIELDS: RefFieldDef[] = [
  { key: "kod", label: "Код", type: "text", required: true, placeholder: "wb / ozon / sayt / lamoda" },
  { key: "nazvanie", label: "Название", type: "text", required: true, placeholder: "Wildberries" },
  { key: "short", label: "Short", type: "text", placeholder: "WB" },
  { key: "color", label: "Цвет (HEX)", type: "text", placeholder: "#7B1FA2", hint: "Цвет акцента в UI" },
  { key: "active", label: "Активен", type: "checkbox" },
  { key: "poryadok", label: "Порядок", type: "number" },
]

export function KanalyProdazhPage() {
  const ref = useReferenceCrud<KanalProdazh, KanalProdazhPayload>(
    "kanaly_prodazh",
    fetchKanalyProdazh,
    {
      insert: insertKanalProdazh,
      update: updateKanalProdazh,
      remove: deleteKanalProdazh,
    },
  )
  const [search, setSearch] = useState("")
  const [editing, setEditing] = useState<KanalProdazh | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<KanalProdazh | null>(null)

  const filtered = useMemo(() => {
    const data = ref.list.data ?? []
    if (!search.trim()) return data
    const q = search.toLowerCase()
    return data.filter((r) =>
      [r.kod, r.nazvanie, r.short]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q)),
    )
  }, [ref.list.data, search])

  const columns: TableColumn<KanalProdazh>[] = [
    {
      key: "kod",
      label: "Код",
      render: (r) => (
        <span className="text-stone-900 font-mono text-xs font-medium">{r.kod}</span>
      ),
    },
    { key: "nazvanie", label: "Название" },
    {
      key: "short",
      label: "Short",
      render: (r) =>
        r.short ? (
          <span className="text-stone-700 font-mono text-xs">{r.short}</span>
        ) : (
          <span className="text-stone-400">—</span>
        ),
    },
    {
      key: "color",
      label: "Color",
      render: (r) =>
        r.color ? (
          <div className="flex items-center gap-2">
            <span
              className="inline-block w-4 h-4 rounded border border-stone-200"
              style={{ background: r.color }}
              aria-hidden
            />
            <span className="text-stone-600 font-mono text-xs">{r.color}</span>
          </div>
        ) : (
          <span className="text-stone-400">—</span>
        ),
    },
    {
      key: "active",
      label: "Активен",
      render: (r) =>
        r.active ? (
          <span className="inline-flex items-center px-2 py-0.5 text-[10px] uppercase tracking-wider bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20 rounded">
            активен
          </span>
        ) : (
          <span className="inline-flex items-center px-2 py-0.5 text-[10px] uppercase tracking-wider bg-stone-100 text-stone-500 rounded">
            выкл.
          </span>
        ),
    },
    {
      key: "poryadok",
      label: "Порядок",
      mono: true,
      dim: true,
      render: (r) => (
        <span className="text-stone-500 font-mono text-xs">{r.poryadok ?? "—"}</span>
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
    const payload: KanalProdazhPayload = {
      kod: String(vals.kod ?? "").trim(),
      nazvanie: String(vals.nazvanie ?? "").trim(),
      short: vals.short ? String(vals.short) : null,
      color: vals.color ? String(vals.color) : null,
      active: Boolean(vals.active),
      poryadok:
        vals.poryadok == null || vals.poryadok === "" ? null : Number(vals.poryadok),
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
        title="Каналы продаж"
        subtitle="4 канала продаж и их настройки видимости"
        count={ref.list.data?.length ?? 0}
        isLoading={ref.list.isLoading}
        actions={<AddButton onClick={() => setCreating(true)} />}
      />
      <SearchBox value={search} onChange={setSearch} placeholder="Поиск по коду или названию…" />
      {ref.list.error && <ErrorBlock message={ref.list.error.message} />}
      {ref.list.isLoading ? (
        <SkeletonTable rows={4} cols={7} />
      ) : (
        <CatalogTable columns={columns} data={filtered} emptyText="Каналы продаж не найдены" />
      )}

      {(creating || editing) && (
        <RefModal
          title={editing ? "Редактировать канал продаж" : "Новый канал продаж"}
          fields={FIELDS}
          initial={
            editing
              ? {
                  kod: editing.kod,
                  nazvanie: editing.nazvanie,
                  short: editing.short ?? "",
                  color: editing.color ?? "",
                  active: Boolean(editing.active),
                  poryadok: editing.poryadok ?? null,
                }
              : { active: true, poryadok: (ref.list.data?.length ?? 0) + 1 }
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
        title="Удалить канал продаж?"
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
