import { useEffect } from "react"
import { Outlet, useLocation } from "react-router-dom"

import { cn } from "@/lib/utils"
import { useThemeStore } from "@/stores/theme"
import { useNavigationStore } from "@/stores/navigation"
import { navigationGroups } from "@/config/navigation"

import { IconBar } from "./icon-bar"
import { SubSidebar } from "./sub-sidebar"
import { TopBar } from "./top-bar"
import { MobileNav } from "./mobile-nav"
import { MobileMenu } from "./mobile-menu"
import { CommandPalette } from "@/components/shared/command-palette"

function AppShell() {
  const { theme } = useThemeStore()
  const { sidebarOpen, mobileMenuOpen, closeMobileMenu } = useNavigationStore()
  const location = useLocation()

  // Sync dark class on documentElement
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark")
  }, [theme])

  // Sync active nav group from current URL (without toggling sidebar)
  useEffect(() => {
    const path = location.pathname
    let targetGroup: string | null = null

    if (path === "/" || path.startsWith("/dashboard")) {
      targetGroup = "home"
    } else {
      const segment = path.split("/")[1]
      const group = navigationGroups.find((g) =>
        g.items.some((item) => item.path.startsWith(`/${segment}`))
      )
      if (group) targetGroup = group.id
    }

    if (targetGroup) {
      const { activeGroup } = useNavigationStore.getState()
      if (activeGroup !== targetGroup) {
        useNavigationStore.setState({ activeGroup: targetGroup })
      }
    }
  }, [location.pathname])

  return (
    <div data-slot="app-shell" className="h-screen w-screen overflow-hidden flex bg-background">
      <IconBar />
      <SubSidebar />
      <main
        className={cn(
          "flex-1 flex flex-col transition-[margin-left] duration-200 ease-in-out md:ml-14",
          sidebarOpen && "lg:ml-[276px]"
        )}
      >
        <TopBar />
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 pb-16 sm:pb-6">
          <div className="max-w-screen-2xl mx-auto">
            <Outlet />
          </div>
        </div>
      </main>
      <MobileNav />
      <MobileMenu open={mobileMenuOpen} onClose={closeMobileMenu} />
      <CommandPalette />
    </div>
  )
}

export { AppShell }
