import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type SleykaOzon } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable, type Column } from "@/components/matrix/data-table"
import { ViewTabs } from "@/components/matrix/view-tabs"
import { MatrixTopbar } from "@/components/matrix/matrix-topbar"

const columns: Column<SleykaOzon>[] = [
  { key: "nazvanie", label: "Название", width: 240, type: "text" },
  { key: "importer_name", label: "Импортёр", width: 180, type: "readonly" },
  { key: "tovary_count", label: "Товары", width: 100, type: "readonly" },
]

export function CardsOzonPage() {
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const toggleRowSelected = useMatrixStore((s) => s.toggleRowSelected)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)
  const entityUpdateStamp = useMatrixStore((s) => s.entityUpdateStamp["cards-ozon"] ?? 0)

  const { data, loading } = useApiQuery(
    () => matrixApi.listCardsOzon({ per_page: 200 }),
    [entityUpdateStamp],
  )

  return (
    <div className="space-y-0">
      <MatrixTopbar />
      <ViewTabs />
      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={loading}
        selectedRows={selectedRows}
        onToggleSelect={toggleRowSelected}
        onRowClick={(id) => openDetailPanel(id, "cards-ozon")}
      />
    </div>
  )
}
