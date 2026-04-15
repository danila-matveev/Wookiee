import * as React from "react"
import { Collapsible } from "@base-ui/react/collapsible"
import { ChevronDown, ChevronRight } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { useApiQuery } from "@/hooks/use-api-query"
import { matrixApi } from "@/lib/matrix-api"
import { useMatrixStore } from "@/stores/matrix-store"
import type { MatrixEntity } from "@/stores/matrix-store"
import type { Artikul, Tovar } from "@/lib/matrix-api"
import { cn } from "@/lib/utils"

const MAX_VISIBLE = 5

interface PanelRelatedProps {
  entityType: string
  entityId: number
  entityData: Record<string, unknown>
}

// ── Child row ────────────────────────────────────────────────────────────────

interface ChildRowProps {
  label: string
  onClick: () => void
}

function ChildRow({ label, onClick }: ChildRowProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center gap-1.5 rounded px-1 py-1 text-sm text-left hover:bg-accent/40 transition-colors cursor-pointer group"
    >
      <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0 group-hover:text-foreground transition-colors" />
      <span className="truncate">{label}</span>
    </button>
  )
}

// ── Parent link ──────────────────────────────────────────────────────────────

interface ParentLinkProps {
  label: string
  name: string
  onClick: () => void
}

function ParentLink({ label, name, onClick }: ParentLinkProps) {
  return (
    <div className="flex items-center gap-1.5 px-1 py-1.5 text-sm border-b border-border">
      <span className="text-muted-foreground shrink-0">{label}:</span>
      <button
        type="button"
        onClick={onClick}
        className="truncate font-medium text-primary hover:underline cursor-pointer"
      >
        {name}
      </button>
    </div>
  )
}

// ── Articles children (for models) ──────────────────────────────────────────

function ArticlesChildren({ entityId }: { entityId: number }) {
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)
  const setActiveEntity = useMatrixStore((s) => s.setActiveEntity)
  const closeDetailPanel = useMatrixStore((s) => s.closeDetailPanel)

  const { data, loading } = useApiQuery<{ items: Artikul[]; total: number } | null>(
    () => matrixApi.listArticles({ model_id: entityId, per_page: 6 }),
    [entityId],
  )

  if (loading) {
    return (
      <div className="space-y-1.5 py-1">
        <Skeleton className="h-6 w-full" />
        <Skeleton className="h-6 w-4/5" />
        <Skeleton className="h-6 w-3/4" />
      </div>
    )
  }

  const items = data?.items ?? []
  const total = data?.total ?? 0

  if (items.length === 0) {
    return (
      <p className="py-1 text-xs text-muted-foreground">Нет связанных записей</p>
    )
  }

  const visible = items.slice(0, MAX_VISIBLE)

  return (
    <div className="space-y-0.5">
      {visible.map((artikul) => (
        <ChildRow
          key={artikul.id}
          label={artikul.artikul}
          onClick={() => openDetailPanel(artikul.id, "articles" as MatrixEntity)}
        />
      ))}
      {total > MAX_VISIBLE && (
        <button
          type="button"
          className="mt-1 text-xs text-primary hover:underline cursor-pointer px-1"
          onClick={() => {
            setActiveEntity("articles" as MatrixEntity)
            closeDetailPanel()
          }}
        >
          Показать все ({total})
        </button>
      )}
    </div>
  )
}

// ── Products children (for articles) ────────────────────────────────────────

function ProductsChildren({ entityId }: { entityId: number }) {
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)
  const setActiveEntity = useMatrixStore((s) => s.setActiveEntity)
  const closeDetailPanel = useMatrixStore((s) => s.closeDetailPanel)

  const { data, loading } = useApiQuery<{ items: Tovar[]; total: number } | null>(
    () => matrixApi.listProducts({ artikul_id: entityId, per_page: 6 }),
    [entityId],
  )

  if (loading) {
    return (
      <div className="space-y-1.5 py-1">
        <Skeleton className="h-6 w-full" />
        <Skeleton className="h-6 w-4/5" />
        <Skeleton className="h-6 w-3/4" />
      </div>
    )
  }

  const items = data?.items ?? []
  const total = data?.total ?? 0

  if (items.length === 0) {
    return (
      <p className="py-1 text-xs text-muted-foreground">Нет связанных записей</p>
    )
  }

  const visible = items.slice(0, MAX_VISIBLE)

  return (
    <div className="space-y-0.5">
      {visible.map((tovar) => (
        <ChildRow
          key={tovar.id}
          label={tovar.barkod}
          onClick={() => openDetailPanel(tovar.id, "products" as MatrixEntity)}
        />
      ))}
      {total > MAX_VISIBLE && (
        <button
          type="button"
          className="mt-1 text-xs text-primary hover:underline cursor-pointer px-1"
          onClick={() => {
            setActiveEntity("products" as MatrixEntity)
            closeDetailPanel()
          }}
        >
          Показать все ({total})
        </button>
      )}
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────────────────

export function PanelRelated({ entityType, entityId, entityData }: PanelRelatedProps) {
  const openDetailPanel = useMatrixStore((s) => s.openDetailPanel)

  // Parent link for articles (-> model)
  const modelName = entityType === "articles"
    ? (entityData.model_name as string | null)
    : null
  const modelId = entityType === "articles"
    ? (entityData.model_id as number | null)
    : null

  // Parent link for products (-> article)
  const artikulName = entityType === "products"
    ? (entityData.artikul_name as string | null)
    : null
  const artikulId = entityType === "products"
    ? (entityData.artikul_id as number | null)
    : null

  // Determine which children section to show
  const showArticlesChildren = entityType === "models"
  const showProductsChildren = entityType === "articles"
  const hasChildren = showArticlesChildren || showProductsChildren

  const childrenTitle = showArticlesChildren ? "Артикулы" : "Товары"

  return (
    <div className="border-t border-border">
      {/* Parent link */}
      {modelName && modelId && (
        <div className="px-4 py-2">
          <ParentLink
            label="Модель"
            name={modelName}
            onClick={() => openDetailPanel(modelId, "models" as MatrixEntity)}
          />
        </div>
      )}
      {artikulName && artikulId && (
        <div className="px-4 py-2">
          <ParentLink
            label="Артикул"
            name={artikulName}
            onClick={() => openDetailPanel(artikulId, "articles" as MatrixEntity)}
          />
        </div>
      )}

      {/* Children collapsible section */}
      {hasChildren && (
        <Collapsible.Root
          defaultOpen={true}
          className={cn("border-b border-border last:border-b-0")}
        >
          <Collapsible.Trigger className="flex w-full items-center justify-between px-4 py-2.5 hover:bg-accent/30 transition-colors cursor-pointer group">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {childrenTitle}
            </span>
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground transition-transform duration-200 group-data-[panel-open]:rotate-0 rotate-[-90deg]" />
          </Collapsible.Trigger>
          <Collapsible.Panel className="overflow-hidden">
            <div className="px-4 pb-3 pt-0.5">
              {showArticlesChildren && <ArticlesChildren entityId={entityId} />}
              {showProductsChildren && <ProductsChildren entityId={entityId} />}
            </div>
          </Collapsible.Panel>
        </Collapsible.Root>
      )}
    </div>
  )
}
