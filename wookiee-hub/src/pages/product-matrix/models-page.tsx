import { useEffect, useState, useCallback } from "react"
import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type ModelOsnova, type ModelVariation } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { DataTable } from "@/components/matrix/data-table"
import { ViewTabs } from "@/components/matrix/view-tabs"
import { MatrixTopbar } from "@/components/matrix/matrix-topbar"
import { PaginationControls } from "@/components/matrix/pagination-controls"
import { buildModelColumns, MODEL_FIELD_DEFS, MODEL_DEFAULT_HIDDEN } from "@/lib/model-columns"
import { LOOKUP_TABLE_MAP } from "@/components/matrix/panel/types"
import type { FilterableDef } from "@/components/matrix/filter-popover"

const MODELS_FILTERABLE_DEFS: FilterableDef[] = [
  { field: "kategoriya_id", label: "Категория", lookupTable: "kategorii" },
  { field: "kollekciya_id", label: "Коллекция", lookupTable: "kollekcii" },
  { field: "fabrika_id", label: "Фабрика", lookupTable: "fabriki" },
  { field: "status_id", label: "Статус", lookupTable: "statusy" },
]

/** Prefetch all lookup tables needed for reference field resolution */
function usePrefetchLookups() {
  const lookupCache = useMatrixStore((s) => s.lookupCache)
  const setLookupCache = useMatrixStore((s) => s.setLookupCache)

  useEffect(() => {
    const tables = new Set(Object.values(LOOKUP_TABLE_MAP))
    for (const table of tables) {
      if (!lookupCache[table]) {
        matrixApi.getLookup(table).then((items) => setLookupCache(table, items))
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
}

export function ModelsPage() {
  const expandedRows = useMatrixStore((s) => s.expandedRows)
  const selectedRows = useMatrixStore((s) => s.selectedRows)
  const toggleRowExpanded = useMatrixStore((s) => s.toggleRowExpanded)
  const toggleRowSelected = useMatrixStore((s) => s.toggleRowSelected)
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)
  const lookupCache = useMatrixStore((s) => s.lookupCache)
  const activeFilters = useMatrixStore((s) => s.activeFilters)
  const addFilter = useMatrixStore((s) => s.addFilter)
  const removeFilter = useMatrixStore((s) => s.removeFilter)

  usePrefetchLookups()

  // Local state for pagination, sort, column visibility
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState<{ field: string | null; order: "asc" | "desc" }>({ field: null, order: "asc" })
  const [hiddenFields, setHiddenFields] = useState<Set<string>>(() => new Set(MODEL_DEFAULT_HIDDEN))
  const [refreshKey, setRefreshKey] = useState(0)

  // Reset page when filters change
  useEffect(() => {
    setPage(1)
  }, [activeFilters])

  const toggleSort = useCallback((field: string) => {
    setSort((prev) => {
      if (prev.field === field) {
        return { field, order: prev.order === "asc" ? "desc" : "asc" }
      }
      return { field, order: "asc" }
    })
    setPage(1)
  }, [])

  const toggleFieldVisibility = useCallback((field: string) => {
    setHiddenFields((prev) => {
      const next = new Set(prev)
      next.has(field) ? next.delete(field) : next.add(field)
      return next
    })
  }, [])

  const columns = buildModelColumns<ModelOsnova>(lookupCache, hiddenFields)

  const apiParams: Record<string, string | number> = { page, per_page: 50 }
  if (sort.field) {
    apiParams.sort = sort.field
    apiParams.order = sort.order
  }
  // Append active filter params
  for (const f of activeFilters) {
    if (f.values.length === 1) {
      apiParams[f.field] = f.values[0]
    } else if (f.values.length > 1) {
      apiParams[f.field] = f.values.join(",")
    }
  }

  const { data, loading } = useApiQuery(
    () => matrixApi.listModels(apiParams),
    [page, sort.field, sort.order, refreshKey, activeFilters],
  )

  const [childrenMap, setChildrenMap] = useState<Map<number, ModelVariation[]>>(new Map())

  useEffect(() => {
    for (const id of expandedRows) {
      if (!childrenMap.has(id)) {
        matrixApi.listChildren(id).then((kids) => {
          setChildrenMap((prev) => new Map(prev).set(id, kids))
        })
      }
    }
  }, [expandedRows]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleCreated(newId: number) {
    setPage(1)
    setRefreshKey((k) => k + 1)
    openDetailPanel(newId)
  }

  return (
    <div className="space-y-0">
      <MatrixTopbar
        fieldDefs={MODEL_FIELD_DEFS as any}
        hiddenFields={hiddenFields}
        onToggleField={toggleFieldVisibility}
        onCreateClick={() => {/* TODO: create dialog */}}
        activeFilters={activeFilters}
        onAddFilter={addFilter}
        onRemoveFilter={removeFilter}
        filterableDefs={MODELS_FILTERABLE_DEFS}
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
        onSort={toggleSort}
        sortState={sort}
      />
      {data && (
        <PaginationControls
          page={data.page}
          pages={data.pages}
          total={data.total}
          perPage={data.per_page}
          onPageChange={setPage}
        />
      )}
    </div>
  )
}
