import { useLocation } from "react-router-dom"
import { ChevronRight, Search, Menu } from "lucide-react"

import { cn } from "@/lib/utils"
import { useNavigationStore } from "@/stores/navigation"
import { navigationGroups } from "@/config/navigation"

function TopBar() {
  const location = useLocation()
  const { sidebarOpen, toggleSidebar, openMobileMenu } = useNavigationStore()

  // Build breadcrumb from current pathname
  const breadcrumbs = buildBreadcrumbs(location.pathname)
  const pageTitle = breadcrumbs[breadcrumbs.length - 1] || "Главная"

  return (
    <header
      data-slot="top-bar"
      className="h-12 flex items-center justify-between px-4 border-b border-border shrink-0"
    >
      {/* Left side: toggle + breadcrumbs */}
      <div className="flex items-center gap-1.5">
        {/* Hamburger button for tablet/mobile */}
        <button
          onClick={openMobileMenu}
          aria-label="Открыть меню"
          className="md:hidden text-text-dim hover:text-foreground transition-colors p-1 rounded hover:bg-bg-hover mr-1"
        >
          <Menu size={18} />
        </button>

        {/* Sidebar toggle — desktop only */}
        {!sidebarOpen && (
          <button
            onClick={toggleSidebar}
            aria-label="Развернуть навигацию"
            className="hidden md:block text-text-dim hover:text-foreground transition-colors p-1 rounded hover:bg-bg-hover mr-1"
          >
            <ChevronRight size={16} />
          </button>
        )}

        {/* Breadcrumbs — desktop only */}
        <nav className="hidden md:flex items-center gap-1 text-[13px]">
          {breadcrumbs.map((crumb, index) => {
            const isLast = index === breadcrumbs.length - 1
            return (
              <span key={index} className="flex items-center gap-1">
                {index > 0 && (
                  <ChevronRight size={12} className="text-text-dim shrink-0" />
                )}
                <span
                  className={cn(
                    "transition-colors",
                    isLast
                      ? "text-foreground font-medium"
                      : "text-muted-foreground hover:text-foreground cursor-default"
                  )}
                >
                  {crumb}
                </span>
              </span>
            )
          })}
        </nav>

        {/* Page title — tablet/mobile only */}
        <span className="md:hidden text-[14px] font-semibold text-foreground">
          {pageTitle}
        </span>
      </div>

      {/* Right side: search placeholder */}
      <button
        data-slot="search-trigger"
        aria-label="Поиск"
        className="flex items-center gap-2 bg-bg-soft border border-border rounded-md px-3 py-1.5 text-[12px] text-text-dim hover:text-foreground transition-colors"
        onClick={() => {
          document.dispatchEvent(
            new KeyboardEvent("keydown", {
              key: "k",
              metaKey: true,
              bubbles: true,
            })
          )
        }}
      >
        <Search size={14} />
        <span className="hidden sm:inline">Поиск...</span>
        <kbd className="hidden sm:inline text-[10px] border border-border bg-background rounded px-1 py-0 ml-1 text-text-dim">
          ⌘K
        </kbd>
      </button>
    </header>
  )
}

function buildBreadcrumbs(pathname: string): string[] {
  const crumbs: string[] = ["Главная"]

  if (pathname === "/" || pathname === "/dashboard") {
    return crumbs
  }

  const segments = pathname.split("/").filter(Boolean)

  // Find matching group
  const group = navigationGroups.find((g) =>
    g.items.some((item) => item.path.startsWith(`/${segments[0]}`))
  )

  if (group) {
    crumbs.push(group.label)

    // Find matching item
    const item = group.items.find((i) => i.path === pathname)
    if (item) {
      crumbs.push(item.label)
    }
  }

  return crumbs
}

export { TopBar }
