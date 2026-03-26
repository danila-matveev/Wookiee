import { useEffect, useState } from "react"
import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type ModelOsnova, type ModelVariation, type FieldDefinition } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable } from "@/components/matrix/data-table"
import { ViewTabs } from "@/components/matrix/view-tabs"
import { MatrixTopbar } from "@/components/matrix/matrix-topbar"
import { PaginationControls } from "@/components/matrix/pagination-controls"
import { CreateRecordDialog } from "@/components/matrix/create-record-dialog"
import { useTableState } from "@/hooks/use-table-state"
import { fieldDefsToColumns } from "@/lib/field-def-columns"
import { ENTITY_BACKEND_MAP } from "@/components/matrix/panel/types"

export function ModelsPage() {
  const expandedRows = useMatrixStore((s) => s.expandedRows)
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const toggleRowExpanded = useMatrixStore((s) => s.toggleRowExpanded)
  const toggleRowSelected = useMatrixStore((s) => s.toggleRowSelected)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)
  const lookupCache = useMatrixStore((s) => s.lookupCache)

  const tableState = useTableState("models")
  const [createOpen, setCreateOpen] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  // Fetch field definitions for column generation
  const { data: fieldDefs } = useApiQuery<FieldDefinition[]>(
    () => matrixApi.listFields(ENTITY_BACKEND_MAP.models),
    [],
  )

  const columns = fieldDefs
    ? fieldDefsToColumns<ModelOsnova>(fieldDefs, lookupCache, tableState.hiddenFields)
    : []

  const { data, loading } = useApiQuery(
    () => matrixApi.listModels(tableState.apiParams),
    [tableState.page, tableState.sort.field, tableState.sort.order, refreshKey],
  )

  const [childrenMap, setChildrenMap] = useState<Map<number, ModelVariation[]>>(new Map())

  // Fetch children when a row is expanded
  useEffect(() => {
    for (const id of expandedRows) {
      if (!childrenMap.has(id)) {
        matrixApi.listChildren(id).then((kids) => {
          setChildrenMap((prev) => new Map(prev).set(id, kids))
        })
      }
    }
  }, [expandedRows])

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
      />
      <ViewTabs />
      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={loading}
        expandedRows={expandedRows}
        selectedRows={selectedRows}
        childrenMap={childrenMap as unknown as Map<number, ModelOsnova[]>}
        hasChildren={(row) => (row.children_count ?? 0) > 0}
        onToggleExpand={toggleRowExpanded}
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
          entityType="models"
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
