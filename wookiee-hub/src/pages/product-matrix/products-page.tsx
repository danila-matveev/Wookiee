import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type Tovar, type FieldDefinition } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable } from "@/components/matrix/data-table"
import { ViewTabs } from "@/components/matrix/view-tabs"
import { useTableState } from "@/hooks/use-table-state"
import { fieldDefsToColumns } from "@/lib/field-def-columns"
import { ENTITY_BACKEND_MAP } from "@/components/matrix/panel/types"

export function ProductsPage() {
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const toggleRowSelected = useMatrixStore((s) => s.toggleRowSelected)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)
  const lookupCache = useMatrixStore((s) => s.lookupCache)

  const tableState = useTableState("products")

  // Fetch field definitions for column generation
  const { data: fieldDefs } = useApiQuery<FieldDefinition[]>(
    () => matrixApi.listFields(ENTITY_BACKEND_MAP.products),
    [],
  )

  const columns = fieldDefs
    ? fieldDefsToColumns<Tovar>(fieldDefs, lookupCache, tableState.hiddenFields)
    : []

  const { data, loading } = useApiQuery(
    () => matrixApi.listProducts(tableState.apiParams),
    [tableState.page, tableState.sort.field, tableState.sort.order],
  )

  return (
    <div className="space-y-3">
      <ViewTabs />
      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={loading}
        selectedRows={selectedRows}
        onToggleSelect={toggleRowSelected}
        onRowClick={openDetailPanel}
        onSort={tableState.toggleSort}
        sortState={tableState.sort}
      />
    </div>
  )
}
