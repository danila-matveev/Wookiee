import { ChevronDown, ChevronRight } from "lucide-react"

export interface SectionHeaderProps {
  icon: string                  // emoji like '🎯', '📦', '🎥', '👤'
  label: string
  count: number
  collapsed: boolean
  onToggle: () => void
  colSpan?: number               // default 12
}

export function SectionHeader({ icon, label, count, collapsed, onToggle, colSpan = 12 }: SectionHeaderProps) {
  return (
    <tr
      className="bg-muted/50 border-y border-border cursor-pointer select-none hover:bg-muted/80 transition-colors"
      onClick={onToggle}
    >
      <td colSpan={colSpan} className="px-3 py-2">
        <div className="flex items-center gap-2">
          {collapsed
            ? <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" aria-hidden />
            : <ChevronDown  className="w-3.5 h-3.5 text-muted-foreground" aria-hidden />}
          <span className="text-[12px] font-medium text-foreground">{icon} {label}</span>
          <span className="text-[11px] tabular-nums text-muted-foreground">{count}</span>
        </div>
      </td>
    </tr>
  )
}
