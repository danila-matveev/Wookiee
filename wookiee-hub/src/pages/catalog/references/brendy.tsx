// W3.2 — Brendy CRUD page.
//
// Бренд (TELOWAY, WOOKIEE, …) — первоклассная сущность каталога. Модели
// привязываются через `modeli_osnova.brand_id NOT NULL FK brendy(id)`.
// Эта страница — справочник для добавления/редактирования брендов.
//
// Шаблон скопирован с `tipy-kollekciy.tsx` (W2.3) — самой свежей канонической
// reference page. Single source of truth.

import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { CatalogTable, type TableColumn } from "@/components/catalog/layout/catalog-table"
import { useReferenceCrud } from "./_use-reference"
import { supabase } from "@/lib/supabase"
import {
  fetchBrendy,
  insertBrend,
  updateBrend,
  archiveBrend,
  fetchStatusy,
  type Brend,
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

/**
 * Валидация `kod`: lowercase, начинается с латинской буквы, далее буквы /
 * цифры / `_` / `-`. URL-safe, потому что бренд может попасть в подкаталоги,
 * импорт CSV, и т.д.
 */
const KOD_RE = /^[a-z][a-z0-9_-]*$/

async function fetchBrendyModelCounts(): Promise<Record<number, number>> {
  const { data, error } = await supabase
    .from("modeli_osnova")
    .select("brand_id")
  if (error) throw new Error(error.message)
  const acc: Record<number, number> = {}
  for (const row of (data ?? []) as { brand_id: number | null }[]) {
    if (row.brand_id == null) continue
    acc[row.brand_id] = (acc[row.brand_id] ?? 0) + 1
  }
  return acc
}

type BrendPayload = Omit<Brend, "id">

export function BrendyPage() {
  const ref = useReferenceCrud<Brend, BrendPayload>(
    "brendy",
    fetchBrendy,
    {
      insert: (data) => insertBrend(data),
      update: (id, patch) => updateBrend(id, patch),
      // archiveBrend — soft-delete. UI продолжает использовать `remove`
      // как «убрать со страницы», но на самом деле hard-delete блокируется
      // FK с `modeli_osnova.brand_id NOT NULL`.
      remove: (id) => archiveBrend(id),
    },
  )

  const counts = useQuery({
    queryKey: ["catalog", "reference", "brendy", "counts"],
    queryFn: fetchBrendyModelCounts,
    staleTime: 5 * 60 * 1000,
  })

  const statusyQ = useQuery({
    queryKey: ["catalog", "statusy"],
    queryFn: fetchStatusy,
    staleTime: 5 * 60 * 1000,
  })

  const [search, setSearch] = useState("")
  const [editing, setEditing] = useState<Brend | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<Brend | null>(null)

  const filtered = useMemo(() => {
    const data = ref.list.data ?? []
    if (!search.trim()) return data
    const q = search.toLowerCase()
    return data.filter(
      (r) =>
        r.kod.toLowerCase().includes(q) ||
        r.nazvanie.toLowerCase().includes(q) ||
        (r.opisanie ?? "").toLowerCase().includes(q),
    )
  }, [ref.list.data, search])

  // Бренд-статусы можно фильтровать по тип = 'model' (общие для модели).
  // Если в будущем появится отдельный тип 'brand' — поправим.
  const statusOptions = (statusyQ.data ?? []).map((s) => ({
    value: s.id,
    label: s.nazvanie,
  }))

  const fields: RefFieldDef[] = [
    {
      key: "kod",
      label: "Код",
      type: "text",
      required: true,
      placeholder: "wookiee, teloway, …",
      hint: "lowercase, латиница, цифры, `_` `-`. URL-safe.",
    },
    {
      key: "nazvanie",
      label: "Название",
      type: "text",
      required: true,
      placeholder: "WOOKIEE",
    },
    {
      key: "opisanie",
      label: "Описание",
      type: "textarea",
      placeholder: "Бельё / Спортивная одежда / …",
      full: true,
    },
    {
      key: "logo_url",
      label: "Логотип (URL)",
      type: "file_url",
      placeholder: "https://…",
      full: true,
    },
    {
      key: "status_id",
      label: "Статус",
      type: "select",
      options: statusOptions,
      placeholder: "Без статуса",
    },
  ]

  const columns: TableColumn<Brend>[] = [
    { key: "id", label: "ID", mono: true, dim: true },
    {
      key: "kod",
      label: "Код",
      mono: true,
      render: (r) => <span className="font-mono text-xs text-stone-700">{r.kod}</span>,
    },
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
      key: "logo_url",
      label: "Лого",
      render: (r) =>
        r.logo_url ? (
          <a
            href={r.logo_url}
            target="_blank"
            rel="noreferrer noopener"
            className="text-stone-700 hover:text-stone-900 underline text-xs"
          >
            ссылка
          </a>
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
    const kod = String(vals.kod ?? "").trim().toLowerCase()
    const nazvanie = String(vals.nazvanie ?? "").trim()
    if (!kod || !nazvanie) return

    if (!KOD_RE.test(kod)) {
      throw new Error(
        "Код должен начинаться с латинской буквы и содержать только латиницу, цифры, `_` и `-`.",
      )
    }

    const payload: BrendPayload = {
      kod,
      nazvanie,
      opisanie: vals.opisanie ? String(vals.opisanie).trim() || null : null,
      logo_url: vals.logo_url ? String(vals.logo_url).trim() || null : null,
      status_id:
        vals.status_id == null || vals.status_id === ""
          ? null
          : Number(vals.status_id),
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
        title="Бренды"
        subtitle="Маркетинговые бренды каталога (WOOKIEE — бельё, TELOWAY — спорт)."
        count={ref.list.data?.length ?? 0}
        isLoading={ref.list.isLoading}
        actions={<AddButton onClick={() => setCreating(true)} />}
      />
      <SearchBox
        value={search}
        onChange={setSearch}
        placeholder="Поиск по коду, названию, описанию…"
      />
      {ref.list.error && <ErrorBlock message={ref.list.error.message} />}
      {ref.list.isLoading ? (
        <SkeletonTable rows={4} cols={6} />
      ) : (
        <CatalogTable
          columns={columns}
          data={filtered}
          emptyText="Брендов пока нет — нажмите «Добавить»"
        />
      )}

      {(creating || editing) && (
        <RefModal
          title={editing ? "Редактировать бренд" : "Новый бренд"}
          fields={fields}
          initial={
            editing
              ? {
                  kod: editing.kod,
                  nazvanie: editing.nazvanie,
                  opisanie: editing.opisanie ?? "",
                  logo_url: editing.logo_url ?? "",
                  status_id: editing.status_id ?? "",
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
        title="Архивировать бренд?"
        message={
          deleting
            ? `«${deleting.nazvanie}» нельзя удалить (есть привязанные модели). Бренд будет помечен как архивный.`
            : undefined
        }
        confirmLabel="Архивировать"
        destructive={false}
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
