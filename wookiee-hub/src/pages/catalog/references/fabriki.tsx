import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { CatalogTable, type TableColumn } from "@/components/catalog/layout/catalog-table"
import { useReferenceCrud } from "./_use-reference"
import { supabase } from "@/lib/supabase"
import {
  fetchFabriki,
  insertFabrika,
  updateFabrika,
  deleteFabrika,
  type FabrikaPayload,
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

interface FabrikaRow {
  id: number
  nazvanie: string
  strana: string | null
  gorod: string | null
  kontakt: string | null
  email: string | null
  wechat: string | null
  specializaciya: string | null
  leadtime_dni: number | null
  notes: string | null
}

const STRANA_OPTIONS = [
  { value: "CN", label: "Китай (CN)" },
  { value: "RU", label: "Россия (RU)" },
  { value: "TR", label: "Турция (TR)" },
  { value: "BY", label: "Беларусь (BY)" },
  { value: "UZ", label: "Узбекистан (UZ)" },
  { value: "KZ", label: "Казахстан (KZ)" },
  { value: "OTHER", label: "Другая" },
]

const FIELDS: RefFieldDef[] = [
  { key: "nazvanie", label: "Название", type: "text", required: true },
  { key: "strana", label: "Страна", type: "select", options: STRANA_OPTIONS, placeholder: "Выберите страну…" },
  { key: "gorod", label: "Город", type: "text", placeholder: "Шэньчжэнь" },
  { key: "kontakt", label: "Контакт", type: "text", placeholder: "Имя представителя" },
  { key: "email", label: "Email", type: "text", placeholder: "factory@example.com" },
  { key: "wechat", label: "WeChat", type: "text" },
  { key: "specializaciya", label: "Специализация", type: "textarea", placeholder: "Что производит" },
  { key: "leadtime_dni", label: "Lead time (дн.)", type: "number" },
  { key: "notes", label: "Заметки", type: "textarea" },
]

async function fetchFabrikaCounts(): Promise<Record<number, number>> {
  const { data, error } = await supabase
    .from("modeli_osnova")
    .select("fabrika_id")
  if (error) throw new Error(error.message)
  const acc: Record<number, number> = {}
  for (const row of (data ?? []) as { fabrika_id: number | null }[]) {
    if (row.fabrika_id == null) continue
    acc[row.fabrika_id] = (acc[row.fabrika_id] ?? 0) + 1
  }
  return acc
}

export function FabrikiPage() {
  const ref = useReferenceCrud<FabrikaRow, FabrikaPayload>(
    "fabriki",
    fetchFabriki,
    { insert: insertFabrika, update: updateFabrika, remove: deleteFabrika },
  )
  const counts = useQuery({
    queryKey: ["catalog", "reference", "fabriki", "counts"],
    queryFn: fetchFabrikaCounts,
    staleTime: 5 * 60 * 1000,
  })
  const [search, setSearch] = useState("")
  const [editing, setEditing] = useState<FabrikaRow | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<FabrikaRow | null>(null)

  const filtered = useMemo(() => {
    const data = ref.list.data ?? []
    if (!search.trim()) return data
    const q = search.toLowerCase()
    return data.filter((r) =>
      [r.nazvanie, r.strana, r.gorod, r.kontakt, r.email, r.wechat, r.specializaciya]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q)),
    )
  }, [ref.list.data, search])

  const columns: TableColumn<FabrikaRow>[] = [
    { key: "nazvanie", label: "Название" },
    {
      key: "strana",
      label: "Страна",
      render: (r) => <span className="text-secondary text-xs">{r.strana ?? "—"}</span>,
    },
    {
      key: "gorod",
      label: "Город",
      render: (r) => <span className="text-secondary text-xs">{r.gorod ?? "—"}</span>,
    },
    {
      key: "kontakt",
      label: "Контакт",
      render: (r) => <span className="text-secondary text-xs">{r.kontakt ?? "—"}</span>,
    },
    {
      key: "email",
      label: "Email",
      render: (r) => <span className="text-secondary text-xs font-mono">{r.email ?? "—"}</span>,
    },
    {
      key: "wechat",
      label: "WeChat",
      render: (r) => <span className="text-secondary text-xs font-mono">{r.wechat ?? "—"}</span>,
    },
    {
      key: "specializaciya",
      label: "Специализация",
      render: (r) =>
        r.specializaciya ? (
          <span className="text-secondary text-xs" title={r.specializaciya}>
            {r.specializaciya.length > 40
              ? `${r.specializaciya.slice(0, 40)}…`
              : r.specializaciya}
          </span>
        ) : (
          <span className="text-label">—</span>
        ),
    },
    {
      key: "leadtime_dni",
      label: "Lead time",
      render: (r) =>
        r.leadtime_dni != null ? (
          <span className="text-secondary tabular-nums font-mono text-xs">{r.leadtime_dni} дн.</span>
        ) : (
          <span className="text-label">—</span>
        ),
    },
    {
      key: "models_count",
      label: "Моделей",
      render: (r) => (
        <span className="text-secondary tabular-nums font-mono text-xs">
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
    const payload: FabrikaPayload = {
      nazvanie: String(vals.nazvanie ?? "").trim(),
      strana: vals.strana ? String(vals.strana) : null,
      gorod: vals.gorod ? String(vals.gorod) : null,
      kontakt: vals.kontakt ? String(vals.kontakt) : null,
      email: vals.email ? String(vals.email) : null,
      wechat: vals.wechat ? String(vals.wechat) : null,
      specializaciya: vals.specializaciya ? String(vals.specializaciya) : null,
      leadtime_dni:
        vals.leadtime_dni == null || vals.leadtime_dni === ""
          ? null
          : Number(vals.leadtime_dni),
      notes: vals.notes ? String(vals.notes) : null,
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
        title="Производители"
        subtitle="Фабрики и партнёры производства"
        count={ref.list.data?.length ?? 0}
        isLoading={ref.list.isLoading}
        actions={<AddButton onClick={() => setCreating(true)} />}
      />
      <SearchBox
        value={search}
        onChange={setSearch}
        placeholder="Поиск по названию, городу, email, WeChat…"
      />
      {ref.list.error && <ErrorBlock message={ref.list.error.message} />}
      {ref.list.isLoading ? (
        <SkeletonTable rows={6} cols={9} />
      ) : (
        <CatalogTable columns={columns} data={filtered} emptyText="Производители не найдены" />
      )}

      {(creating || editing) && (
        <RefModal
          title={editing ? "Редактировать производителя" : "Новый производитель"}
          fields={FIELDS}
          initial={
            editing
              ? {
                  nazvanie: editing.nazvanie,
                  strana: editing.strana ?? "",
                  gorod: editing.gorod ?? "",
                  kontakt: editing.kontakt ?? "",
                  email: editing.email ?? "",
                  wechat: editing.wechat ?? "",
                  specializaciya: editing.specializaciya ?? "",
                  leadtime_dni: editing.leadtime_dni ?? null,
                  notes: editing.notes ?? "",
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
        title="Удалить производителя?"
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
