import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type Fabrika } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable, type Column } from "@/components/matrix/data-table"
import { ViewTabs } from "@/components/matrix/view-tabs"
import { MatrixTopbar } from "@/components/matrix/matrix-topbar"

const columns: Column<Fabrika>[] = [
  { key: "nazvanie", label: "Название", width: 200, type: "text" },
  { key: "strana", label: "Страна", width: 160, type: "text" },
  { key: "modeli_count", label: "Модели", width: 100, type: "readonly" },
]

export function FactoriesPage() {
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const toggleRowSelected = useMatrixStore((s) => s.toggleRowSelected)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)
  const entityUpdateStamp = useMatrixStore((s) => s.entityUpdateStamp["factories"] ?? 0)

  const { data, loading } = useApiQuery(
    () => matrixApi.listFactories({ per_page: 200 }),
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
        onRowClick={(id) => openDetailPanel(id, "factories")}
      />
    </div>
  )
}
