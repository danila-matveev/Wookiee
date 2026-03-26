import { useEffect, useState } from "react"
import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type ModelOsnova, type ModelVariation, type FieldDefinition } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable } from "@/components/matrix/data-table"
import { ViewTabs } from "@/components/matrix/view-tabs"
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
    [tableState.page, tableState.sort.field, tableState.sort.order],
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

  return (
    <div className="space-y-3">
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
    </div>
  )
}
