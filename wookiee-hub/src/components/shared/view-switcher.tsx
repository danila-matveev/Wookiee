import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

interface ViewSwitcherProps {
  options: { id: string; label: string; icon: LucideIcon }[]
  value: string
  onChange: (value: string) => void
  className?: string
}

export function ViewSwitcher({
  options,
  value,
  onChange,
  className,
}: ViewSwitcherProps) {
  return (
    <div
      className={cn(
        "bg-bg-soft border border-border rounded-md p-0.5 flex gap-0.5",
        className,
      )}
    >
      {options.map((option) => {
        const Icon = option.icon
        const isActive = option.id === value

        return (
          <button
            key={option.id}
            type="button"
            onClick={() => onChange(option.id)}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1 rounded text-[12px] font-medium transition-colors",
              isActive
                ? "bg-accent text-white"
                : "bg-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon size={13} />
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
