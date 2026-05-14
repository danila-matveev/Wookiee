import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { CatalogTable, type TableColumn } from "@/components/catalog/layout/catalog-table"
import { SyncMirrorButton } from "@/components/catalog/sync-mirror-button"
import { useReferenceCrud } from "./_use-reference"
import { supabase } from "@/lib/supabase"
import {
  fetchKollekcii,
  insertKollekciya,
  updateKollekciya,
  deleteKollekciya,
  type KollekciyaPayload,
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

interface KollekciyaRow {
  id: number
  nazvanie: string
  opisanie: string | null
  god_zapuska: number | null
}

const FIELDS: RefFieldDef[] = [
  { key: "nazvanie", label: "Название", type: "text", required: true, placeholder: "Например: Трикотажное белье" },
  { key: "opisanie", label: "Описание", type: "textarea" },
  { key: "god_zapuska", label: "Год запуска", type: "number", placeholder: "2024" },
]

async function fetchKollekciyaCounts(): Promise<Record<number, number>> {
  const { data, error } = await supabase
    .from("modeli_osnova")
    .select("kollekciya_id")
  if (error) throw new Error(error.message)
  const acc: Record<number, number> = {}
  for (const row of (data ?? []) as { kollekciya_id: number | null }[]) {
    if (row.kollekciya_id == null) continue
    acc[row.kollekciya_id] = (acc[row.kollekciya_id] ?? 0) + 1
  }
  return acc
}

export function KollekciiPage() {
  const ref = useReferenceCrud<KollekciyaRow, KollekciyaPayload>(
    "kollekcii",
    fetchKollekcii,
    { insert: insertKollekciya, update: updateKollekciya, remove: deleteKollekciya },
  )
  const counts = useQuery({
    queryKey: ["catalog", "reference", "kollekcii", "counts"],
    queryFn: fetchKollekciyaCounts,
    staleTime: 5 * 60 * 1000,
  })
  const [search, setSearch] = useState("")
  const [editing, setEditing] = useState<KollekciyaRow | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<KollekciyaRow | null>(null)

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

  const columns: TableColumn<KollekciyaRow>[] = [
    { key: "id", label: "ID", mono: true, dim: true },
    { key: "nazvanie", label: "Название" },
    {
      key: "opisanie",
      label: "Описание",
      render: (r) =>
        r.opisanie ? (
          <span className="text-stone-600" title={r.opisanie}>
            {r.opisanie.length > 60 ? `${r.opisanie.slice(0, 60)}…` : r.opisanie}
          </span>
        ) : (
          <span className="text-stone-400">—</span>
        ),
    },
    {
      key: "god_zapuska",
      label: "Год запуска",
      render: (r) =>
        r.god_zapuska ? (
          <span className="text-stone-700 tabular-nums font-mono text-xs">{r.god_zapuska}</span>
        ) : (
          <span className="text-stone-400">—</span>
        ),
    },
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
    const payload: KollekciyaPayload = {
      nazvanie: String(vals.nazvanie ?? "").trim(),
      opisanie: vals.opisanie ? String(vals.opisanie) : null,
      god_zapuska:
        vals.god_zapuska == null || vals.god_zapuska === ""
          ? null
          : Number(vals.god_zapuska),
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
        title="Коллекции"
        subtitle="Коллекции продуктов по году/тематике"
        count={ref.list.data?.length ?? 0}
        isLoading={ref.list.isLoading}
        actions={<><SyncMirrorButton /><AddButton onClick={() => setCreating(true)} /></>}
      />
      <SearchBox value={search} onChange={setSearch} placeholder="Поиск по названию и описанию…" />
      {ref.list.error && <ErrorBlock message={ref.list.error.message} />}
      {ref.list.isLoading ? (
        <SkeletonTable rows={6} cols={5} />
      ) : (
        <CatalogTable
          columns={columns}
          data={filtered}
          emptyText="Коллекции не найдены"
          onRowClick={(r) => setEditing(r)}
        />
      )}

      {creating && (
        <RefModal
          title="Новая коллекция"
          fields={FIELDS}
          onSave={handleSave}
          onCancel={() => setCreating(false)}
        />
      )}

      {editing && (
        <ReferenceDrawer
          kind="Коллекция"
          title={editing.nazvanie}
          fields={FIELDS}
          initial={{
            nazvanie: editing.nazvanie,
            opisanie: editing.opisanie ?? "",
            god_zapuska: editing.god_zapuska ?? null,
          }}
          onSave={async (vals) => {
            await handleSave(vals)
          }}
          onClose={() => setEditing(null)}
          linkedSections={[
            {
              kind: "models",
              title: "Модели коллекции",
              refColumn: "kollekciya_id",
              refId: editing.id,
            },
          ]}
        />
      )}

      <ConfirmDialog
        open={!!deleting}
        title="Удалить коллекцию?"
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
