import { useState } from "react"
import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type Tovar, type FieldDefinition } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable } from "@/components/matrix/data-table"
import { ViewTabs } from "@/components/matrix/view-tabs"
import { MatrixTopbar } from "@/components/matrix/matrix-topbar"
import { PaginationControls } from "@/components/matrix/pagination-controls"
import { CreateRecordDialog } from "@/components/matrix/create-record-dialog"
import { useTableState } from "@/hooks/use-table-state"
import { fieldDefsToColumns } from "@/lib/field-def-columns"
import { getBackendType } from "@/lib/entity-registry"
import type { FilterableDef } from "@/components/matrix/filter-popover"

const PRODUCTS_FILTERABLE_DEFS: FilterableDef[] = [
  { field: "status_id", label: "Статус", lookupTable: "statusy" },
]

export function ProductsPage() {
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const toggleRowSelected = useMatrixStore((s) => s.toggleRowSelected)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)
  const lookupCache = useMatrixStore((s) => s.lookupCache)
  const activeFilters = useMatrixStore((s) => s.activeFilters)
  const addFilter = useMatrixStore((s) => s.addFilter)
  const removeFilter = useMatrixStore((s) => s.removeFilter)

  const tableState = useTableState("products", 50, activeFilters)
  const [createOpen, setCreateOpen] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  // Fetch field definitions for column generation
  const { data: fieldDefs } = useApiQuery<FieldDefinition[]>(
    () => matrixApi.listFields(getBackendType('products')),
    [],
  )

  const columns = fieldDefs
    ? fieldDefsToColumns<Tovar>(fieldDefs, lookupCache, tableState.hiddenFields)
    : []

  const { data, loading } = useApiQuery(
    () => matrixApi.listProducts(tableState.apiParams),
    [tableState.page, tableState.sort.field, tableState.sort.order, refreshKey, activeFilters],
  )

  function handleCreated(newId: number) {
    tableState.setPage(1)
    setRefreshKey((k) => k + 1)
    openDetailPanel(newId)
  }

  return (
    <div className="space-y-0">
      <MatrixTopbar
        fieldDefs={fieldDefs ?? undefined}
        hiddenFields={tableState.hiddenFields}
        onToggleField={tableState.toggleFieldVisibility}
        onCreateClick={() => setCreateOpen(true)}
        activeFilters={activeFilters}
        onAddFilter={addFilter}
        onRemoveFilter={removeFilter}
        filterableDefs={PRODUCTS_FILTERABLE_DEFS}
      />
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
      {data && (
        <PaginationControls
          page={data.page}
          pages={data.pages}
          total={data.total}
          perPage={data.per_page}
          onPageChange={tableState.setPage}
        />
      )}
      {fieldDefs && (
        <CreateRecordDialog
          entityType="products"
          fieldDefs={fieldDefs}
          lookupCache={lookupCache}
          open={createOpen}
          onOpenChange={setCreateOpen}
          onCreated={handleCreated}
        />
      )}
    </div>
  )
}
