import { useEffect, useState, useCallback } from "react"
import { ChevronRight } from "lucide-react"
import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi, type ModelOsnova, type ModelVariation } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { useViewsStore } from "@/stores/views-store"
import { DataTable } from "@/components/matrix/data-table"
import { ViewTabs } from "@/components/matrix/view-tabs"
import { MatrixTopbar } from "@/components/matrix/matrix-topbar"
import { PaginationControls } from "@/components/matrix/pagination-controls"
import { SaveViewDialog } from "@/components/matrix/save-view-dialog"
import { buildModelColumns, MODEL_FIELD_DEFS, MODEL_DEFAULT_HIDDEN } from "@/lib/model-columns"
import { LOOKUP_TABLE_MAP } from "@/components/matrix/panel/types"
import type { FilterableDef } from "@/components/matrix/filter-popover"
import type { Column } from "@/components/matrix/data-table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"

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
  const setFilters = useMatrixStore((s) => s.setFilters)
  const drillDown = useMatrixStore((s) => s.drillDown)

  const savedViews = useViewsStore((s) => s.savedViews)
  const loadedViewConfig = useViewsStore((s) => s.loadedViewConfig)
  const clearLoadedView = useViewsStore((s) => s.clearLoadedView)
  const loadView = useViewsStore((s) => s.loadView)

  usePrefetchLookups()

  // Local state for pagination, sort, column visibility
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState<{ field: string | null; order: "asc" | "desc" }>({ field: null, order: "asc" })
  const [hiddenFields, setHiddenFields] = useState<Set<string>>(() => new Set(MODEL_DEFAULT_HIDDEN))
  const [refreshKey, setRefreshKey] = useState(0)
  const [saveViewOpen, setSaveViewOpen] = useState(false)

  // Restore state from loaded view config
  useEffect(() => {
    if (loadedViewConfig) {
      setFilters(loadedViewConfig.filters)
      if (loadedViewConfig.sort) {
        setSort({ field: loadedViewConfig.sort.field, order: loadedViewConfig.sort.order })
      }
      if (loadedViewConfig.columns.length > 0) {
        const allKeys = MODEL_FIELD_DEFS.map((d) => d.key)
        const visibleSet = new Set(loadedViewConfig.columns)
        setHiddenFields(new Set(allKeys.filter((k) => !visibleSet.has(k))))
      }
      setPage(1)
      clearLoadedView()
    }
  }, [loadedViewConfig]) // eslint-disable-line react-hooks/exhaustive-deps

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

  // Visible column keys for saved views config
  const visibleColumnKeys = MODEL_FIELD_DEFS
    .filter((d) => !hiddenFields.has(d.key))
    .map((d) => d.key)

  // Drill-down action column (always appended at end)
  const drillDownColumn: Column<ModelOsnova> = {
    key: "__drill_down",
    label: "",
    width: 36,
    render: (row: ModelOsnova) => (
      <div className="flex justify-center px-1" onClick={(e) => e.stopPropagation()}>
        <button
          title="Показать артикулы этой модели"
          onClick={() => drillDown("articles", "model_osnova_id", row.id, (row as any).kod ?? String(row.id))}
          className="rounded p-1 text-muted-foreground hover:bg-accent/50 hover:text-foreground transition-colors"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    ),
  }

  const columns = [...buildModelColumns<ModelOsnova>(lookupCache, hiddenFields), drillDownColumn]

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

  // Models-only saved views
  const modelSavedViews = savedViews.filter((v) => v.entity === "models")

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
        extraActions={
          <div className="flex items-center gap-1.5">
            {/* Load saved view dropdown */}
            {modelSavedViews.length > 0 && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="h-7 text-xs">
                    Виды
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="min-w-40">
                  {modelSavedViews.map((view) => (
                    <DropdownMenuItem key={view.id} onClick={() => loadView(view)}>
                      {view.name}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
            {/* Save current view */}
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-xs"
              onClick={() => setSaveViewOpen(true)}
            >
              Сохранить вид
            </Button>
          </div>
        }
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

      <SaveViewDialog
        open={saveViewOpen}
        onOpenChange={setSaveViewOpen}
        entity="models"
        currentColumns={visibleColumnKeys}
        activeFilters={activeFilters}
        sort={sort.field ? { field: sort.field, order: sort.order } : null}
      />
    </div>
  )
}
