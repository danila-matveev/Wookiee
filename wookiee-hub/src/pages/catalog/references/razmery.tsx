import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { CatalogTable, type TableColumn } from "@/components/catalog/layout/catalog-table"
import { useReferenceCrud } from "./_use-reference"
import { supabase } from "@/lib/supabase"
import {
  fetchRazmery,
  insertRazmer,
  updateRazmer,
  deleteRazmer,
  type RazmerPayload,
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

interface RazmerRow {
  id: number
  nazvanie: string
  poryadok: number
  ru: string | null
  eu: string | null
  china: string | null
}

const FIELDS: RefFieldDef[] = [
  { key: "kod", label: "Код", type: "text", required: true, placeholder: "XS / S / M…" },
  { key: "nazvanie", label: "Название", type: "text" },
  { key: "ru", label: "RU размер", type: "text", placeholder: "44" },
  { key: "eu", label: "EU размер", type: "text", placeholder: "36" },
  { key: "china", label: "China размер", type: "text", placeholder: "S" },
  { key: "poryadok", label: "Порядок", type: "number" },
]

async function fetchRazmerCounts(): Promise<Record<number, number>> {
  const { data, error } = await supabase.from("tovary").select("razmer_id")
  if (error) throw new Error(error.message)
  const acc: Record<number, number> = {}
  for (const row of (data ?? []) as { razmer_id: number | null }[]) {
    if (row.razmer_id == null) continue
    acc[row.razmer_id] = (acc[row.razmer_id] ?? 0) + 1
  }
  return acc
}

/**
 * Note: razmery currently has only `nazvanie` as a NOT-NULL string. We treat
 * `nazvanie` as the human-friendly "code" (XS/S/M/...) for backward compat —
 * the form exposes a separate "Код" alias that maps to `nazvanie` on save
 * if a separate "Название" is provided; otherwise both are the same.
 */
export function RazmeryPage() {
  const ref = useReferenceCrud<RazmerRow, RazmerPayload>(
    "razmery",
    fetchRazmery,
    { insert: insertRazmer, update: updateRazmer, remove: deleteRazmer },
  )
  const counts = useQuery({
    queryKey: ["catalog", "reference", "razmery", "counts"],
    queryFn: fetchRazmerCounts,
    staleTime: 5 * 60 * 1000,
  })
  const [search, setSearch] = useState("")
  const [editing, setEditing] = useState<RazmerRow | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<RazmerRow | null>(null)

  const filtered = useMemo(() => {
    const data = ref.list.data ?? []
    if (!search.trim()) return data
    const q = search.toLowerCase()
    return data.filter((r) =>
      [r.nazvanie, r.ru, r.eu, r.china]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q)),
    )
  }, [ref.list.data, search])

  const columns: TableColumn<RazmerRow>[] = [
    {
      key: "kod",
      label: "Код",
      render: (r) => (
        <span className="text-stone-900 font-mono text-xs font-medium">{r.nazvanie}</span>
      ),
    },
    {
      key: "nazvanie",
      label: "Название",
      render: (r) => <span className="text-stone-700">{r.nazvanie}</span>,
    },
    {
      key: "ru",
      label: "RU",
      render: (r) => <span className="text-stone-600 font-mono text-xs">{r.ru ?? "—"}</span>,
    },
    {
      key: "eu",
      label: "EU",
      render: (r) => <span className="text-stone-600 font-mono text-xs">{r.eu ?? "—"}</span>,
    },
    {
      key: "china",
      label: "China",
      render: (r) => <span className="text-stone-600 font-mono text-xs">{r.china ?? "—"}</span>,
    },
    {
      key: "poryadok",
      label: "Порядок",
      mono: true,
      dim: true,
    },
    {
      key: "sku_count",
      label: "SKU",
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
    const code = String(vals.kod ?? "").trim()
    const name = vals.nazvanie ? String(vals.nazvanie).trim() : code
    const payload: RazmerPayload = {
      nazvanie: name || code,
      poryadok:
        vals.poryadok == null || vals.poryadok === ""
          ? 0
          : Number(vals.poryadok),
      ru: vals.ru ? String(vals.ru) : null,
      eu: vals.eu ? String(vals.eu) : null,
      china: vals.china ? String(vals.china) : null,
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
        title="Размеры"
        subtitle="Размерная сетка с RU / EU / China"
        count={ref.list.data?.length ?? 0}
        isLoading={ref.list.isLoading}
        actions={<AddButton onClick={() => setCreating(true)} />}
      />
      <SearchBox value={search} onChange={setSearch} placeholder="Поиск по размеру…" />
      {ref.list.error && <ErrorBlock message={ref.list.error.message} />}
      {ref.list.isLoading ? (
        <SkeletonTable rows={6} cols={7} />
      ) : (
        <CatalogTable columns={columns} data={filtered} emptyText="Размеры не найдены" />
      )}

      {(creating || editing) && (
        <RefModal
          title={editing ? "Редактировать размер" : "Новый размер"}
          fields={FIELDS}
          initial={
            editing
              ? {
                  kod: editing.nazvanie,
                  nazvanie: editing.nazvanie,
                  ru: editing.ru ?? "",
                  eu: editing.eu ?? "",
                  china: editing.china ?? "",
                  poryadok: editing.poryadok ?? 0,
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
        title="Удалить размер?"
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
