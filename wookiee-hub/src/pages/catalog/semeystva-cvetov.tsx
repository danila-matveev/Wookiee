import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { CatalogTable, type TableColumn } from "@/components/catalog/layout/catalog-table"
import { useReferenceCrud } from "./references/_use-reference"
import { supabase } from "@/lib/supabase"
import {
  fetchSemeystvaCvetov,
  insertSemeystvoCveta,
  updateSemeystvoCveta,
  deleteSemeystvoCveta,
  type SemeystvoCveta,
  type SemeystvoCvetaPayload,
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
  { key: "kod", label: "Код", type: "text", required: true, placeholder: "neutral / warm / cool…" },
  { key: "nazvanie", label: "Название", type: "text", required: true, placeholder: "Нейтральные" },
  { key: "opisanie", label: "Описание", type: "textarea" },
  { key: "poryadok", label: "Порядок", type: "number" },
]

async function fetchCvetaCountsBySemeystvo(): Promise<Record<string, number>> {
  // Cveta currently store family code in `semeystvo` (text). Future schema
  // exposes `semeystvo_id`; we count by both, falling back to the text key.
  const { data, error } = await supabase.from("cveta").select("semeystvo, semeystvo_id")
  if (error) throw new Error(error.message)
  const acc: Record<string, number> = {}
  for (const row of (data ?? []) as { semeystvo: string | null; semeystvo_id: number | null }[]) {
    if (!row.semeystvo) continue
    acc[row.semeystvo] = (acc[row.semeystvo] ?? 0) + 1
  }
  return acc
}

export function SemeystvaCvetovPage() {
  const ref = useReferenceCrud<SemeystvoCveta, SemeystvoCvetaPayload>(
    "semeystva_cvetov",
    fetchSemeystvaCvetov,
    {
      insert: insertSemeystvoCveta,
      update: updateSemeystvoCveta,
      remove: deleteSemeystvoCveta,
    },
  )
  const counts = useQuery({
    queryKey: ["catalog", "reference", "semeystva_cvetov", "counts"],
    queryFn: fetchCvetaCountsBySemeystvo,
    staleTime: 5 * 60 * 1000,
  })
  const [search, setSearch] = useState("")
  const [editing, setEditing] = useState<SemeystvoCveta | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<SemeystvoCveta | null>(null)

  const filtered = useMemo(() => {
    const data = ref.list.data ?? []
    if (!search.trim()) return data
    const q = search.toLowerCase()
    return data.filter((r) =>
      [r.kod, r.nazvanie, r.opisanie]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q)),
    )
  }, [ref.list.data, search])

  const columns: TableColumn<SemeystvoCveta>[] = [
    {
      key: "kod",
      label: "Код",
      render: (r) => (
        <span className="text-stone-900 font-mono text-xs font-medium">{r.kod}</span>
      ),
    },
    { key: "nazvanie", label: "Название" },
    {
      key: "opisanie",
      label: "Описание",
      render: (r) =>
        r.opisanie ? (
          <span className="text-stone-600 text-xs" title={r.opisanie}>
            {r.opisanie.length > 60 ? `${r.opisanie.slice(0, 60)}…` : r.opisanie}
          </span>
        ) : (
          <span className="text-stone-400">—</span>
        ),
    },
    {
      key: "color_count",
      label: "Цветов",
      render: (r) => (
        <span className="text-stone-700 tabular-nums font-mono text-xs">
          {counts.data?.[r.kod] ?? 0}
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
    const payload: SemeystvoCvetaPayload = {
      kod: String(vals.kod ?? "").trim(),
      nazvanie: String(vals.nazvanie ?? "").trim(),
      opisanie: vals.opisanie ? String(vals.opisanie) : null,
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
        title="Семейства цветов"
        subtitle="5 семейств для группировки цветовой матрицы"
        count={ref.list.data?.length ?? 0}
        isLoading={ref.list.isLoading}
        actions={<AddButton onClick={() => setCreating(true)} />}
      />
      <SearchBox value={search} onChange={setSearch} placeholder="Поиск по коду или названию…" />
      {ref.list.error && <ErrorBlock message={ref.list.error.message} />}
      {ref.list.isLoading ? (
        <SkeletonTable rows={5} cols={6} />
      ) : (
        <CatalogTable columns={columns} data={filtered} emptyText="Семейства цветов не найдены" />
      )}

      {(creating || editing) && (
        <RefModal
          title={editing ? "Редактировать семейство цветов" : "Новое семейство цветов"}
          fields={FIELDS}
          initial={
            editing
              ? {
                  kod: editing.kod,
                  nazvanie: editing.nazvanie,
                  opisanie: editing.opisanie ?? "",
                  poryadok: editing.poryadok ?? null,
                }
              : { poryadok: (ref.list.data?.length ?? 0) + 1 }
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
        title="Удалить семейство цветов?"
        message={deleting ? `«${deleting.nazvanie}» будет удалено.` : undefined}
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
