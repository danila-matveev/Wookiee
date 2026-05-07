import { useMemo, useState } from "react"
import { CatalogTable, type TableColumn } from "@/components/catalog/layout/catalog-table"
import { useReferenceCrud } from "./_use-reference"
import {
  fetchImportery,
  insertImporter,
  updateImporter,
  deleteImporter,
  type ImporterPayload,
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

interface ImporterRow {
  id: number
  nazvanie: string
  nazvanie_en: string | null
  inn: string | null
  adres: string | null
  short_name: string | null
  kpp: string | null
  ogrn: string | null
  bank: string | null
  rs: string | null
  ks: string | null
  bik: string | null
  kontakt: string | null
  telefon: string | null
}

const FIELDS: RefFieldDef[] = [
  { key: "short_name", label: "Short Name", type: "text", placeholder: "ИП Иванов" },
  { key: "nazvanie", label: "Полное название", type: "text", required: true },
  { key: "nazvanie_en", label: "Название EN", type: "text" },
  { key: "inn", label: "ИНН", type: "text" },
  { key: "kpp", label: "КПП", type: "text" },
  { key: "ogrn", label: "ОГРН", type: "text" },
  { key: "adres", label: "Адрес", type: "textarea" },
  { key: "bank", label: "Банк", type: "text" },
  { key: "rs", label: "Р/С", type: "text" },
  { key: "ks", label: "К/С", type: "text" },
  { key: "bik", label: "БИК", type: "text" },
  { key: "kontakt", label: "Контакт", type: "text" },
  { key: "telefon", label: "Телефон", type: "text" },
]

export function ImporteryPage() {
  const ref = useReferenceCrud<ImporterRow, ImporterPayload>(
    "importery",
    fetchImportery,
    { insert: insertImporter, update: updateImporter, remove: deleteImporter },
  )
  const [search, setSearch] = useState("")
  const [editing, setEditing] = useState<ImporterRow | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<ImporterRow | null>(null)

  const filtered = useMemo(() => {
    const data = ref.list.data ?? []
    if (!search.trim()) return data
    const q = search.toLowerCase()
    return data.filter((r) =>
      [r.nazvanie, r.nazvanie_en, r.short_name, r.inn, r.kpp, r.ogrn, r.bank, r.kontakt]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q)),
    )
  }, [ref.list.data, search])

  const columns: TableColumn<ImporterRow>[] = [
    {
      key: "short_name",
      label: "Short Name",
      render: (r) =>
        r.short_name ? (
          <span className="text-stone-900 font-medium text-xs">{r.short_name}</span>
        ) : (
          <span className="text-stone-400">—</span>
        ),
    },
    { key: "nazvanie", label: "Полное название" },
    {
      key: "inn",
      label: "ИНН",
      render: (r) => <span className="text-stone-700 font-mono text-xs">{r.inn ?? "—"}</span>,
    },
    {
      key: "kpp",
      label: "КПП",
      render: (r) => <span className="text-stone-700 font-mono text-xs">{r.kpp ?? "—"}</span>,
    },
    {
      key: "ogrn",
      label: "ОГРН",
      render: (r) => <span className="text-stone-700 font-mono text-xs">{r.ogrn ?? "—"}</span>,
    },
    {
      key: "bank",
      label: "Банк",
      render: (r) =>
        r.bank ? (
          <span className="text-stone-600 text-xs" title={r.bank}>
            {r.bank.length > 24 ? `${r.bank.slice(0, 24)}…` : r.bank}
          </span>
        ) : (
          <span className="text-stone-400">—</span>
        ),
    },
    {
      key: "rs",
      label: "Р/С",
      render: (r) => <span className="text-stone-600 font-mono text-xs">{r.rs ?? "—"}</span>,
    },
    {
      key: "kontakt",
      label: "Контакт",
      render: (r) => <span className="text-stone-600 text-xs">{r.kontakt ?? "—"}</span>,
    },
    {
      key: "telefon",
      label: "Телефон",
      render: (r) => <span className="text-stone-600 font-mono text-xs">{r.telefon ?? "—"}</span>,
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
    const payload: ImporterPayload = {
      nazvanie: String(vals.nazvanie ?? "").trim(),
      nazvanie_en: get("nazvanie_en"),
      short_name: get("short_name"),
      inn: get("inn"),
      kpp: get("kpp"),
      ogrn: get("ogrn"),
      adres: get("adres"),
      bank: get("bank"),
      rs: get("rs"),
      ks: get("ks"),
      bik: get("bik"),
      kontakt: get("kontakt"),
      telefon: get("telefon"),
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
        title="Юридические лица"
        subtitle="Юридические лица для документов"
        count={ref.list.data?.length ?? 0}
        isLoading={ref.list.isLoading}
        actions={<AddButton onClick={() => setCreating(true)} />}
      />
      <SearchBox
        value={search}
        onChange={setSearch}
        placeholder="Поиск по названию, ИНН, банку…"
      />
      {ref.list.error && <ErrorBlock message={ref.list.error.message} />}
      {ref.list.isLoading ? (
        <SkeletonTable rows={4} cols={9} />
      ) : (
        <CatalogTable columns={columns} data={filtered} emptyText="Юридические лица не найдены" />
      )}

      {(creating || editing) && (
        <RefModal
          title={editing ? "Редактировать юр.лицо" : "Новое юридическое лицо"}
          fields={FIELDS}
          initial={
            editing
              ? Object.fromEntries(
                  Object.entries(editing).map(([k, v]) => [k, v ?? ""]),
                )
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
        title="Удалить юридическое лицо?"
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
