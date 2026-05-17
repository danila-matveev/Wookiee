import { X } from "lucide-react"

import { cn } from "@/lib/utils"
import { useNavigationStore } from "@/stores/navigation"
import { navigationGroups } from "@/config/navigation"

import { SubSidebarItem } from "./sub-sidebar-item"

function SubSidebar() {
  const { activeGroup, sidebarOpen, closeSidebar } = useNavigationStore()

  const activeGroupData = navigationGroups.find(
    (group) => group.id === activeGroup
  )

  return (
    <aside
      id="sub-sidebar"
      data-slot="sub-sidebar"
      className={cn(
        "fixed left-14 top-0 bottom-0 bg-sub-sidebar border-r border-border z-40",
        "transition-[width] duration-200 ease-in-out overflow-hidden",
        sidebarOpen ? "w-[220px]" : "w-0"
      )}
    >
      <div className="w-[220px] h-full flex flex-col">
        <header className="h-12 flex items-center justify-between px-4 shrink-0">
          <span className="text-[11px] uppercase tracking-[0.04em] text-text-dim font-semibold">
            {activeGroupData?.label}
          </span>
          <button
            onClick={closeSidebar}
            aria-label="Закрыть панель"
            className="text-text-dim hover:text-foreground transition-colors p-1 rounded hover:bg-bg-hover"
          >
            <X size={14} />
          </button>
        </header>
        <nav className="flex-1 px-2 flex flex-col gap-[1px] overflow-y-auto">
          {activeGroupData?.items.map((item) => (
            <SubSidebarItem key={item.id} item={item} />
          ))}
        </nav>
      </div>
    </aside>
  )
}

export { SubSidebar }
