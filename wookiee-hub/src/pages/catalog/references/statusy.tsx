import { CatalogTable, type TableColumn } from "@/components/catalog/layout/catalog-table"
import { StatusBadge } from "@/components/catalog/ui/status-badge"
import { useReference } from "./_use-reference"
import { fetchStatusy } from "@/lib/catalog/service"
import { PageHeader, ErrorBlock, SkeletonTable } from "./_shared"
type StatusRow = { id: number; nazvanie: string; tip: string }

const STATUS_TIP_LABELS: Record<string, string> = {
  model: "Модель",
  product: "Товар",
  color: "Цвет",
}

const COLUMNS: TableColumn<StatusRow>[] = [
  { key: "id", label: "ID", mono: true, dim: true },
  {
    key: "nazvanie",
    label: "Статус",
    render: (row) => <StatusBadge statusId={row.id} />,
  },
  {
    key: "tip",
    label: "Тип",
    render: (row) => (
      <span className="text-xs text-muted">
        {STATUS_TIP_LABELS[row.tip] ?? row.tip}
      </span>
    ),
  },
]

export function StatusyPage() {
  const { data = [], isLoading, error } = useReference<StatusRow>("statusy", fetchStatusy as () => Promise<StatusRow[]>)
  return (
    <div className="px-6 py-6 max-w-4xl">
      <PageHeader title="Статусы" count={data.length} isLoading={isLoading} />
      {error && <ErrorBlock message={error.message} />}
      {isLoading ? (
        <SkeletonTable rows={7} cols={3} />
      ) : (
        <CatalogTable columns={COLUMNS} data={data} emptyText="Статусы не найдены" />
      )}
    </div>
  )
}
