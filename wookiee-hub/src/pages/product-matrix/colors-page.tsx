import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type Cvet } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable, type Column } from "@/components/matrix/data-table"
import { ViewTabs } from "@/components/matrix/view-tabs"
import { MatrixTopbar } from "@/components/matrix/matrix-topbar"

const columns: Column<Cvet>[] = [
  { key: "color_code", label: "Код цвета", width: 120, type: "text" },
  { key: "cvet", label: "Цвет (рус)", width: 160, type: "text" },
  { key: "color", label: "Color (en)", width: 160, type: "text" },
  { key: "lastovica", label: "Ластовица", width: 140, type: "text" },
  { key: "status_name", label: "Статус", width: 120, type: "readonly" },
  { key: "artikuly_count", label: "Артикулы", width: 100, type: "readonly" },
]

export function ColorsPage() {
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const toggleRowSelected = useMatrixStore((s) => s.toggleRowSelected)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)

  const { data, loading } = useApiQuery(
    () => matrixApi.listColors({ per_page: 200 }),
    [],
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
        onRowClick={openDetailPanel}
      />
    </div>
  )
}
