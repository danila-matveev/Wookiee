import { ChevronDown, ChevronRight } from "lucide-react"

interface SectionHeaderProps {
  icon: string
  label: string
  count: number
  collapsed: boolean
  onToggle: () => void
  colSpan?: number
}

export function SectionHeader({ icon, label, count, collapsed, onToggle, colSpan = 12 }: SectionHeaderProps) {
  return (
    <tr
      className="bg-stone-50/80 border-y border-stone-200 cursor-pointer select-none hover:bg-stone-100/60 transition-colors"
      onClick={onToggle}
    >
      <td colSpan={colSpan} className="px-3 py-2">
        <div className="flex items-center gap-2">
          {collapsed ? (
            <ChevronRight className="w-3.5 h-3.5 text-stone-400" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-stone-400" />
          )}
          <span className="text-[12px] font-medium text-stone-700">
            {icon} {label}
          </span>
          <span className="text-[11px] tabular-nums text-stone-400">{count}</span>
        </div>
      </td>
    </tr>
  )
}
