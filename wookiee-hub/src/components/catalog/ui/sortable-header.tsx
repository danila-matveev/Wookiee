import { ChevronDown, ChevronUp, ChevronsUpDown } from "lucide-react"
import type { CSSProperties, ReactNode } from "react"

interface Props {
  active: boolean
  direction: "asc" | "desc" | null
  onClick: () => void
  children: ReactNode
  className?: string
  /** W9.5 — позволяет скрыть колонку через `display: none` без рефакторинга tbody. */
  style?: CSSProperties
}

/**
 * Click-to-sort <th> wrapper.  Cycles asc → desc → none on each click;
 * cycling is owned by `useTableSort`.  The icon is permanently visible so
 * users discover the affordance without hover.
 */
export function SortableHeader({ active, direction, onClick, children, className, style }: Props) {
  return (
    <th
      onClick={onClick}
      className={`cursor-pointer select-none hover:bg-stone-100 ${className ?? ""}`}
      style={style}
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
