import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { CatalogTable, type TableColumn } from "@/components/catalog/layout/catalog-table"
import { useReferenceCrud } from "./_use-reference"
import {
  fetchKategorii,
  fetchModeliOsnovaCounts,
  insertKategoriya,
  updateKategoriya,
  deleteKategoriya,
  type KategoriyaPayload,
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
} from "./_shared"

interface KategoriyaRow {
  id: number
  nazvanie: string
  opisanie: string | null
}

const FIELDS: RefFieldDef[] = [
  { key: "nazvanie", label: "Название", type: "text", required: true, placeholder: "Например: Боди" },
  { key: "opisanie", label: "Описание", type: "textarea", placeholder: "Базовая категория товаров…" },
]

export function KategoriiPage() {
  const ref = useReferenceCrud<KategoriyaRow, KategoriyaPayload>(
    "kategorii",
    fetchKategorii,
    { insert: insertKategoriya, update: updateKategoriya, remove: deleteKategoriya },
  )
  const counts = useQuery({
    queryKey: ["catalog", "reference", "kategorii", "counts"],
    queryFn: fetchModeliOsnovaCounts,
    staleTime: 5 * 60 * 1000,
  })
  const [search, setSearch] = useState("")
  const [editing, setEditing] = useState<KategoriyaRow | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<KategoriyaRow | null>(null)

  const filtered = useMemo(() => {
    const data = ref.list.data ?? []
    if (!search.trim()) return data
    const q = search.toLowerCase()
    return data.filter(
      (r) =>
        r.nazvanie.toLowerCase().includes(q) ||
        (r.opisanie ?? "").toLowerCase().includes(q),
    )
  }, [ref.list.data, search])

  const columns: TableColumn<KategoriyaRow>[] = [
    { key: "id", label: "ID", mono: true, dim: true },
    { key: "nazvanie", label: "Название" },
    {
      key: "opisanie",
      label: "Описание",
      render: (r) =>
        r.opisanie ? (
          <span className="text-secondary line-clamp-1" title={r.opisanie}>
            {r.opisanie.length > 60 ? `${r.opisanie.slice(0, 60)}…` : r.opisanie}
          </span>
        ) : (
          <span className="text-label">—</span>
        ),
    },
    {
      key: "models_count",
      label: "Моделей",
      render: (r) => {
        const c = counts.data?.[r.id] ?? 0
        return (
          <span className="text-secondary tabular-nums font-mono text-xs">{c}</span>
        )
      },
    },
    {
      key: "actions",
      label: "",
      render: (r) => (
        <RowActions
          onEdit={() => setEditing(r)}
          onDelete={() => setDeleting(r)}
        />
      ),
    },
  ]

  const handleSave = async (vals: Record<string, unknown>) => {
    const payload: KategoriyaPayload = {
      nazvanie: String(vals.nazvanie ?? "").trim(),
      opisanie: vals.opisanie ? String(vals.opisanie) : null,
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
        title="Категории"
        subtitle="Базовые категории товаров"
        count={ref.list.data?.length ?? 0}
        isLoading={ref.list.isLoading}
        actions={<AddButton onClick={() => setCreating(true)} />}
      />
      <SearchBox value={search} onChange={setSearch} placeholder="Поиск по названию и описанию…" />
      {ref.list.error && <ErrorBlock message={ref.list.error.message} />}
      {ref.list.isLoading ? (
        <SkeletonTable rows={6} cols={4} />
      ) : (
        <CatalogTable columns={columns} data={filtered} emptyText="Категории не найдены" />
      )}

      {(creating || editing) && (
        <RefModal
          title={editing ? "Редактировать категорию" : "Новая категория"}
          fields={FIELDS}
          initial={
            editing
              ? { nazvanie: editing.nazvanie, opisanie: editing.opisanie ?? "" }
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
        title="Удалить категорию?"
        message={deleting ? `«${deleting.nazvanie}» будет удалена. Это действие нельзя отменить.` : undefined}
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
