import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type ImporterEntity } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable, type Column } from "@/components/matrix/data-table"
import { ViewTabs } from "@/components/matrix/view-tabs"
import { MatrixTopbar } from "@/components/matrix/matrix-topbar"

const columns: Column<ImporterEntity>[] = [
  { key: "nazvanie", label: "Название", width: 200, type: "text" },
  { key: "nazvanie_en", label: "Name (en)", width: 200, type: "text" },
  { key: "inn", label: "ИНН", width: 140, type: "text" },
  { key: "adres", label: "Адрес", width: 300, type: "text" },
  { key: "modeli_count", label: "Модели", width: 100, type: "readonly" },
]

export function ImportersPage() {
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const toggleRowSelected = useMatrixStore((s) => s.toggleRowSelected)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)
  const entityUpdateStamp = useMatrixStore((s) => s.entityUpdateStamp["importers"] ?? 0)

  const { data, loading } = useApiQuery(
    () => matrixApi.listImporters({ per_page: 200 }),
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
        onRowClick={(id) => openDetailPanel(id, "importers")}
      />
    </div>
  )
}
