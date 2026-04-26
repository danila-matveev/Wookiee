import { cn } from "@/lib/utils"

type ProcessedSubTab = "pending" | "answered" | "archived"

const processedSubTabs: { value: ProcessedSubTab; label: string }[] = [
  { value: "pending", label: "На отправке" },
  { value: "answered", label: "Отвеченные" },
  { value: "archived", label: "Архив" },
]

interface ReviewsStatusTabsProps {
  className?: string
  activeTab: "new" | "processed"
  onTabChange: (tab: "new" | "processed") => void
  newCount: number
  processedCount: number
  processedSubTab?: ProcessedSubTab
  onProcessedSubTabChange?: (sub: ProcessedSubTab) => void
  pendingCount?: number
  answeredCount?: number
  archivedCount?: number
}

export function ReviewsStatusTabs({
  className,
  activeTab,
  onTabChange,
  newCount,
  processedCount,
  processedSubTab = "pending",
  onProcessedSubTabChange,
  pendingCount = 0,
  answeredCount = 0,
  archivedCount = 0,
}: ReviewsStatusTabsProps) {
  const subCounts: Record<ProcessedSubTab, number> = {
    pending: pendingCount,
    answered: answeredCount,
    archived: archivedCount,
  }

  return (
    <div className={cn("flex flex-col", className)}>
      <div className="flex border-b border-border">
        <button
          onClick={() => onTabChange("new")}
          className={cn(
            "px-4 py-2 text-[13px] font-medium border-b-2 transition-colors -mb-px",
            activeTab === "new"
              ? "border-accent text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          Новые{" "}
          {newCount > 0 && (
            <span className="ml-1 text-[11px] bg-accent-soft text-accent px-1.5 py-0.5 rounded-full">
              {newCount}
            </span>
          )}
        </button>
        <button
          onClick={() => onTabChange("processed")}
          className={cn(
            "px-4 py-2 text-[13px] font-medium border-b-2 transition-colors -mb-px",
            activeTab === "processed"
              ? "border-accent text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          Обработанные{" "}
          {processedCount > 0 && (
            <span className="ml-1 text-[11px] bg-bg-soft text-muted-foreground px-1.5 py-0.5 rounded-full">
              {processedCount}
            </span>
          )}
        </button>
      </div>
      {activeTab === "processed" && onProcessedSubTabChange && (
        <div className="flex gap-1 p-1.5 bg-bg-soft/50">
          {processedSubTabs.map((sub) => (
            <button
              key={sub.value}
              onClick={() => onProcessedSubTabChange(sub.value)}
              className={cn(
                "px-2.5 py-1 rounded-md text-[12px] font-medium transition-all",
                processedSubTab === sub.value
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {sub.label}
              {subCounts[sub.value] > 0 && (
                <span className="ml-1 text-[10px] text-muted-foreground">
                  {subCounts[sub.value]}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
