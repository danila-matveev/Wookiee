import { NavLink } from "react-router-dom"

import { cn } from "@/lib/utils"
import type { NavItem } from "@/types/navigation"

interface SubSidebarItemProps {
  item: NavItem
}

function SubSidebarItem({ item }: SubSidebarItemProps) {
  const Icon = item.icon

  return (
    <NavLink
      to={item.path}
      data-slot="sub-sidebar-item"
      className={({ isActive }) =>
        cn(
          "flex items-center gap-2 px-3 py-2 rounded-md text-[13px] transition-colors duration-100",
          isActive
            ? "bg-accent-soft text-accent font-semibold"
            : "text-text-dim hover:bg-bg-hover hover:text-foreground font-medium"
        )
      }
    >
      <Icon size={16} className="shrink-0" />
      <span className="truncate">{item.label}</span>
      {item.badge && (
        <span className="ml-auto text-[10px] border border-border bg-bg-soft text-text-dim rounded-[3px] px-1 py-0 shrink-0">
          {item.badge}
        </span>
      )}
    </NavLink>
  )
}

export { SubSidebarItem }
