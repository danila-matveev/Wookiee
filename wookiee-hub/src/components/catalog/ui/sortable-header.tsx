import { ChevronDown, ChevronUp, ChevronsUpDown } from "lucide-react"
import type { ReactNode } from "react"

interface Props {
  active: boolean
  direction: "asc" | "desc" | null
  onClick: () => void
  children: ReactNode
  className?: string
}

/**
 * Click-to-sort <th> wrapper.  Cycles asc → desc → none on each click;
 * cycling is owned by `useTableSort`.  The icon is permanently visible so
 * users discover the affordance without hover.
 */
export function SortableHeader({ active, direction, onClick, children, className }: Props) {
  return (
    <th
      onClick={onClick}
      className={`cursor-pointer select-none hover:bg-stone-100 ${className ?? ""}`}
    >
      <span className="inline-flex items-center gap-1">
        {children}
        {active && direction === "asc" && <ChevronUp className="w-3 h-3" />}
        {active && direction === "desc" && <ChevronDown className="w-3 h-3" />}
        {!active && <ChevronsUpDown className="w-3 h-3 text-stone-300" />}
      </span>
    </th>
  )
}
