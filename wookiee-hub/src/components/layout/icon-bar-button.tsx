import type { LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"

interface IconBarButtonProps {
  icon: LucideIcon
  isActive: boolean
  onClick: () => void
  tooltip?: string
}

function IconBarButton({ icon: Icon, isActive, onClick, tooltip }: IconBarButtonProps) {
  return (
    <button
      data-slot="icon-bar-button"
      onClick={onClick}
      title={tooltip}
      aria-label={tooltip}
      aria-expanded={isActive}
      aria-controls="sub-sidebar"
      className={cn(
        "flex items-center justify-center w-11 h-11 rounded-lg transition-colors duration-100 shrink-0",
        isActive
          ? "bg-accent-soft text-accent"
          : "bg-transparent text-text-dim hover:bg-bg-hover hover:text-foreground"
      )}
    >
      <Icon size={20} strokeWidth={isActive ? 2.2 : 1.8} />
    </button>
  )
}

export { IconBarButton }
