import { useState, useEffect, useCallback, useRef } from "react"
import { Sheet, SheetContent } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import { ENTITY_TITLE_FIELD, LOOKUP_TABLE_MAP } from "@/components/matrix/panel/types"
import { PanelHeader } from "@/components/matrix/panel/panel-header"
import { PanelBody } from "@/components/matrix/panel/panel-body"
import { PanelSaveBar } from "@/components/matrix/panel/panel-save-bar"
import { PanelRelated } from "@/components/matrix/panel/panel-related"
import type { ModelOsnova, Artikul, Tovar } from "@/lib/matrix-api"
import type { RelatedCount } from "@/components/matrix/panel/panel-header"

type AnyEntity = ModelOsnova | Artikul | Tovar

function fetchEntity(
  entityType: string | null,
  id: number | null,
): Promise<AnyEntity | null> {
  if (!id || !entityType) return Promise.resolve(null)
  if (entityType === "models") return matrixApi.getModel(id)
  if (entityType === "articles") return matrixApi.getArticle(id)
  if (entityType === "products") return matrixApi.getProduct(id)
  return Promise.resolve(null)
}

function fetchParentEntity(
  entityType: string | null,
  data: AnyEntity | null,
): Promise<AnyEntity | null> {
  if (!data || !entityType) return Promise.resolve(null)
  if (entityType === "articles") {
    const articleData = data as Artikul
    if (articleData.model_id) return matrixApi.getModel(articleData.model_id)
  }
  if (entityType === "products") {
    const productData = data as Tovar
    if (productData.artikul_id) return matrixApi.getArticle(productData.artikul_id)
  }
  return Promise.resolve(null)
}

function getParentEntityType(entityType: string | null): string | null {
  if (entityType === "articles") return "models"
  if (entityType === "products") return "articles"
  return null
}

function getParentEntityId(
  entityType: string | null,
  data: AnyEntity | null,
): number | null {
  if (!data) return null
  if (entityType === "articles") {
    return (data as Artikul).model_id ?? null
  }
  if (entityType === "products") {
    return (data as Tovar).artikul_id ?? null
  }
  return null
}

// All lookup tables used by select fields — prefetch in parallel on panel open
const ALL_LOOKUP_TABLES = [...new Set(Object.values(LOOKUP_TABLE_MAP))]

export function DetailPanel() {
  const detailPanelId = useMatrixStore((s) => s.detailPanelId)
  const detailPanelEntityType = useMatrixStore((s) => s.detailPanelEntityType)
  const closeDetailPanel = useMatrixStore((s) => s.closeDetailPanel)
  const notifyEntityUpdated = useMatrixStore((s) => s.notifyEntityUpdated)
  const lookupCache = useMatrixStore((s) => s.lookupCache)
  const setLookupCache = useMatrixStore((s) => s.setLookupCache)

  const [isEditing, setIsEditing] = useState(false)
  const [editState, setEditState] = useState<Record<string, unknown>>({})
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  // Local override of entity data after a successful save
  const [localData, setLocalData] = useState<AnyEntity | null>(null)

  // Main entity fetch
  const { data: fetchedData, loading, error } = useApiQuery<AnyEntity | null>(
    () => fetchEntity(detailPanelEntityType, detailPanelId),
    [detailPanelId, detailPanelEntityType],
  )

  // Merge fetched data with local override — local override wins after save
  const data = localData ?? fetchedData

  // Parent entity fetch (for inherited field popovers)
  const { data: parentData } = useApiQuery<AnyEntity | null>(
    () => fetchParentEntity(detailPanelEntityType, data),
    [detailPanelId, detailPanelEntityType, data != null],
  )

  // Reset state when panel is opened for a different entity
  const lastPanelIdRef = useRef<number | null>(null)
  useEffect(() => {
    if (detailPanelId !== lastPanelIdRef.current) {
      lastPanelIdRef.current = detailPanelId
      setIsEditing(false)
      setEditState({})
      setSaveError(null)
      setLocalData(null)
    }
  }, [detailPanelId])

  // Prefetch all lookup tables that aren't already in cache
  const lookupCacheRef = useRef(lookupCache)
  lookupCacheRef.current = lookupCache

  const prefetchLookups = useCallback(async () => {
    const missing = ALL_LOOKUP_TABLES.filter((table) => !lookupCacheRef.current[table])
    if (missing.length === 0) return

    const results = await Promise.allSettled(
      missing.map((table) => matrixApi.getLookup(table).then((items) => ({ table, items }))),
    )

    for (const result of results) {
      if (result.status === "fulfilled") {
        setLookupCache(result.value.table, result.value.items)
      }
    }
  }, [setLookupCache])

  // Prefetch lookups when panel opens
  useEffect(() => {
    if (detailPanelId) {
      void prefetchLookups()
    }
  }, [detailPanelId, prefetchLookups])

  function handleToggleEdit() {
    if (!isEditing && data) {
      setEditState({ ...(data as Record<string, unknown>) })
      setSaveError(null)
    }
    setIsEditing((v) => !v)
  }

  const handleChange = useCallback((fieldName: string, value: unknown) => {
    setEditState((prev) => ({ ...prev, [fieldName]: value }))
  }, [])

  async function handleSave() {
    if (!data || !detailPanelId || !detailPanelEntityType) return

    const originalData = data as Record<string, unknown>

    // Diff — only changed non-computed fields
    const changed: Record<string, unknown> = {}
    for (const [key, val] of Object.entries(editState)) {
      if (key === "id") continue
      if (key.endsWith("_name")) continue
      if (val !== originalData[key]) {
        changed[key] = val
      }
    }

    if (Object.keys(changed).length === 0) {
      setIsEditing(false)
      return
    }

    setSaving(true)
    setSaveError(null)

    try {
      let updated: AnyEntity

      if (detailPanelEntityType === "models") {
        updated = await matrixApi.updateModel(detailPanelId, changed as Partial<ModelOsnova>)
      } else if (detailPanelEntityType === "articles") {
        updated = await matrixApi.updateArticle(detailPanelId, changed as Partial<Artikul>)
      } else if (detailPanelEntityType === "products") {
        updated = await matrixApi.updateProduct(detailPanelId, changed as Partial<Tovar>)
      } else {
        throw new Error(`Unknown entity type: ${detailPanelEntityType}`)
      }

      // Merge server response as local override so panel shows updated data immediately
      setLocalData(updated)
      notifyEntityUpdated(detailPanelEntityType)
      setIsEditing(false)
      setEditState({})
    } catch (err) {
      const message = err instanceof Error ? err.message : "Ошибка сохранения"
      setSaveError(message)
      // Do NOT close edit mode on error — user can retry or cancel
    } finally {
      setSaving(false)
    }
  }

  function handleCancel() {
    setEditState({})
    setIsEditing(false)
    setSaveError(null)
  }

  const isOpen = !!detailPanelId

  const title =
    data && detailPanelEntityType
      ? String(
          (data as Record<string, unknown>)[ENTITY_TITLE_FIELD[detailPanelEntityType]] ?? "—",
        )
      : "Загрузка..."

  const parentEntityType = getParentEntityType(detailPanelEntityType)
  const parentEntityId = getParentEntityId(detailPanelEntityType, data)

  // Compute badge counters for related child entities
  const relatedCounts: RelatedCount[] = (() => {
    if (!data) return []
    if (detailPanelEntityType === "models") {
      const count = (data as ModelOsnova).children_count
      if (count && count > 0) return [{ label: "Артикулы", count, entityType: "articles" }]
    }
    if (detailPanelEntityType === "articles") {
      const count = (data as Artikul).tovary_count
      if (count && count > 0) return [{ label: "Товары", count, entityType: "products" }]
    }
    return []
  })()

  // Compute hasChanges for save bar
  const hasChanges = (() => {
    if (!data) return false
    const originalData = data as Record<string, unknown>
    for (const [key, val] of Object.entries(editState)) {
      if (key === "id" || key.endsWith("_name")) continue
      if (val !== originalData[key]) return true
    }
    return false
  })()

  function handleOpenChange(open: boolean) {
    if (!open) {
      closeDetailPanel()
      setIsEditing(false)
      setEditState({})
      setSaveError(null)
    }
  }

  return (
    <Sheet open={isOpen} onOpenChange={handleOpenChange}>
      <SheetContent className="flex flex-col p-0 overflow-hidden">
        <PanelHeader
          title={title}
          onClose={() => {
            closeDetailPanel()
            setIsEditing(false)
            setEditState({})
            setSaveError(null)
          }}
          isEditing={isEditing}
          onToggleEdit={handleToggleEdit}
          relatedCounts={relatedCounts}
        />

        {loading ? (
          <div className="flex flex-col gap-3 p-4 overflow-y-auto flex-1">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-3/5" />
          </div>
        ) : error ? (
          <div className="p-4 text-sm text-destructive">Ошибка загрузки: {error}</div>
        ) : data && detailPanelEntityType ? (
          <>
            <div className="overflow-y-auto flex-1 flex flex-col">
              <PanelBody
                data={data as Record<string, unknown>}
                entityType={detailPanelEntityType}
                isEditing={isEditing}
                editState={editState}
                onChange={handleChange}
                lookupCache={lookupCache}
                parentData={parentData as Record<string, unknown> | null}
                parentEntityType={parentEntityType}
                parentEntityId={parentEntityId}
              />

              <PanelRelated
                entityType={detailPanelEntityType}
                entityId={detailPanelId}
                entityData={data as Record<string, unknown>}
              />
            </div>

            {saveError && (
              <div className="px-3 pb-1 text-xs text-destructive">{saveError}</div>
            )}

            {isEditing && (
              <PanelSaveBar
                onSave={handleSave}
                onCancel={handleCancel}
                saving={saving}
                hasChanges={hasChanges}
              />
            )}
          </>
        ) : (
          <div className="p-4 text-sm text-muted-foreground">Не найдено</div>
        )}
      </SheetContent>
    </Sheet>
  )
}
