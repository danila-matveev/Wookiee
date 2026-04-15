import { cn } from "@/lib/utils"
import type { ReviewSource } from "@/types/comms"

const tabs: { value: ReviewSource | "all"; label: string }[] = [
  { value: "all", label: "Все" },
  { value: "review", label: "Отзывы" },
  { value: "question", label: "Вопросы" },
  { value: "chat", label: "Чаты" },
]

interface CommsDashboardTabsProps {
  className?: string
  activeTab: ReviewSource | "all"
  onTabChange: (tab: ReviewSource | "all") => void
}

export function CommsDashboardTabs({ className, activeTab, onTabChange }: CommsDashboardTabsProps) {
  return (
    <div className={cn("flex gap-1 p-1 rounded-lg bg-bg-soft w-fit", className)}>
      {tabs.map((tab) => (
        <button
          key={tab.value}
          onClick={() => onTabChange(tab.value)}
          className={cn(
            "px-3 py-1.5 rounded-md text-[13px] font-medium transition-all",
            activeTab === tab.value
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
