import { X } from "lucide-react"
import { cn } from "@/lib/utils"
import { useMatrixStore, type ViewTab } from "@/stores/matrix-store"
import { useViewsStore } from "@/stores/views-store"

const builtInTabs: { id: ViewTab; label: string }[] = [
  { id: "spec", label: "Спецификация" },
  { id: "stock", label: "Склад" },
  { id: "finance", label: "Финансы" },
  { id: "rating", label: "Рейтинг" },
]

export function ViewTabs() {
  const activeEntity = useMatrixStore((s) => s.activeEntity)
  const activeView = useMatrixStore((s) => s.activeView)
  const setActiveView = useMatrixStore((s) => s.setActiveView)

  // Built-in view tabs only — saved views are handled by the page's own dropdown
  // (save/load view UI is scoped to models page for this phase)

  // Show entity-scoped saved views in the tab bar for context only (read only)
  const savedViews = useViewsStore((s) => s.savedViews).filter((v) => v.entity === String(activeEntity))
  const deleteView = useViewsStore((s) => s.deleteView)

  const handleRemoveView = (viewId: string) => {
    deleteView(viewId)
    if (activeView === `saved-${viewId}`) {
      setActiveView("spec")
    }
  }

  return (
    <div className="flex gap-1 border-b border-border">
      {builtInTabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => setActiveView(tab.id)}
          className={cn(
            "px-3 py-1.5 text-sm transition-colors",
            activeView === tab.id
              ? "border-b-2 border-primary font-medium text-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {tab.label}
        </button>
      ))}

      {savedViews.map((view) => {
        const viewId: ViewTab = `saved-${view.id}`
        return (
          <button
            key={view.id}
            onClick={() => setActiveView(viewId)}
            className={cn(
              "group flex items-center gap-1 px-3 py-1.5 text-sm transition-colors",
              activeView === viewId
                ? "border-b-2 border-primary font-medium text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {view.name}
            <span
              role="button"
              onClick={(e) => {
                e.stopPropagation()
                handleRemoveView(view.id)
              }}
              className="ml-1 hidden rounded p-0.5 hover:bg-destructive/20 group-hover:inline-flex"
            >
              <X className="h-3 w-3" />
            </span>
          </button>
        )
      })}
    </div>
  )
}
