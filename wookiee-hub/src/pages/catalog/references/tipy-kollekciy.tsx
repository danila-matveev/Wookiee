import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { CatalogTable, type TableColumn } from "@/components/catalog/layout/catalog-table"
import { useReferenceCrud } from "./_use-reference"
import { supabase } from "@/lib/supabase"
import {
  fetchTipyKollekciy,
  insertTipKollekcii,
  updateTipKollekcii,
  deleteTipKollekcii,
  type TipKollekcii,
  type TipKollekciiPayload,
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
import { ReferenceDrawer } from "@/pages/catalog/reference-card"

const FIELDS: RefFieldDef[] = [
  {
    key: "nazvanie",
    label: "Название",
    type: "text",
    required: true,
    placeholder: "Например: Бесшовное белье Jelly",
  },
]

async function fetchTipKollekciiCounts(): Promise<Record<number, number>> {
  const { data, error } = await supabase
    .from("modeli_osnova")
    .select("tip_kollekcii_id")
  if (error) throw new Error(error.message)
  const acc: Record<number, number> = {}
  for (const row of (data ?? []) as { tip_kollekcii_id: number | null }[]) {
    if (row.tip_kollekcii_id == null) continue
    acc[row.tip_kollekcii_id] = (acc[row.tip_kollekcii_id] ?? 0) + 1
  }
  return acc
}

export function TipyKollekciyPage() {
  const ref = useReferenceCrud<TipKollekcii, TipKollekciiPayload>(
    "tipy-kollekciy",
    fetchTipyKollekciy,
    { insert: insertTipKollekcii, update: updateTipKollekcii, remove: deleteTipKollekcii },
  )
  const counts = useQuery({
    queryKey: ["catalog", "reference", "tipy-kollekciy", "counts"],
    queryFn: fetchTipKollekciiCounts,
    staleTime: 5 * 60 * 1000,
  })
  const [search, setSearch] = useState("")
  const [editing, setEditing] = useState<TipKollekcii | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<TipKollekcii | null>(null)

  const filtered = useMemo(() => {
    const data = ref.list.data ?? []
    if (!search.trim()) return data
    const q = search.toLowerCase()
    return data.filter((r) => r.nazvanie.toLowerCase().includes(q))
  }, [ref.list.data, search])

  const columns: TableColumn<TipKollekcii>[] = [
    { key: "id", label: "ID", mono: true, dim: true },
    { key: "nazvanie", label: "Название" },
    {
      key: "models_count",
      label: "Моделей",
      render: (r) => (
        <span className="text-stone-700 tabular-nums font-mono text-xs">
          {counts.data?.[r.id] ?? 0}
        </span>
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
    const payload: TipKollekciiPayload = {
      nazvanie: String(vals.nazvanie ?? "").trim(),
    }
    if (!payload.nazvanie) return
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
        title="Типы коллекций"
        subtitle="Справочник типов коллекций (бесшовное белье, трикотаж и т.п.)"
        count={ref.list.data?.length ?? 0}
        isLoading={ref.list.isLoading}
        actions={<AddButton onClick={() => setCreating(true)} />}
      />
      <SearchBox value={search} onChange={setSearch} placeholder="Поиск по названию…" />
      {ref.list.error && <ErrorBlock message={ref.list.error.message} />}
      {ref.list.isLoading ? (
        <SkeletonTable rows={6} cols={4} />
      ) : (
        <CatalogTable
          columns={columns}
          data={filtered}
          emptyText="Типы коллекций не найдены"
          onRowClick={(r) => setEditing(r)}
        />
      )}

      {creating && (
        <RefModal
          title="Новый тип коллекции"
          fields={FIELDS}
          onSave={handleSave}
          onCancel={() => setCreating(false)}
        />
      )}

      {editing && (
        <ReferenceDrawer
          kind="Тип коллекции"
          title={editing.nazvanie}
          fields={FIELDS}
          initial={{ nazvanie: editing.nazvanie }}
          onSave={async (vals) => {
            await handleSave(vals)
          }}
          onClose={() => setEditing(null)}
          linkedSections={[
            {
              kind: "models",
              title: "Модели этого типа",
              refColumn: "tip_kollekcii_id",
              refId: editing.id,
            },
          ]}
        />
      )}

      <ConfirmDialog
        open={!!deleting}
        title="Удалить тип коллекции?"
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
