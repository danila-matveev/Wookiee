import { useNavigate, useLocation } from "react-router-dom"
import { LayoutDashboard, Package, Truck, MoreHorizontal } from "lucide-react"
import { cn } from "@/lib/utils"
import { useNavigationStore } from "@/stores/navigation"

const tabs = [
  { id: "home", label: "Главная", icon: LayoutDashboard, path: "/dashboard" },
  { id: "product", label: "Продукт", icon: Package, path: "/product/catalog" },
  { id: "operations", label: "Операции", icon: Truck, path: "/operations/shipments" },
  { id: "more", label: "Ещё", icon: MoreHorizontal, path: null },
] as const

function MobileNav() {
  const navigate = useNavigate()
  const location = useLocation()
  const { openMobileMenu } = useNavigationStore()

  function isActive(tab: (typeof tabs)[number]) {
    if (!tab.path) return false
    if (tab.id === "home") return location.pathname === "/" || location.pathname.startsWith("/dashboard")
    const segment = tab.path.split("/")[1]
    return location.pathname.startsWith(`/${segment}`)
  }

  function handleTabClick(tab: (typeof tabs)[number]) {
    if (tab.path) {
      navigate(tab.path)
    } else {
      openMobileMenu()
    }
  }

  return (
    <nav
      data-slot="mobile-nav"
      className="sm:hidden fixed bottom-0 left-0 right-0 z-50 h-14 bg-background border-t border-border flex"
    >
      {tabs.map((tab) => {
        const Icon = tab.icon
        const active = isActive(tab)
        return (
          <button
            key={tab.id}
            onClick={() => handleTabClick(tab)}
            className={cn(
              "flex-1 flex flex-col items-center justify-center gap-0.5 text-[10px] transition-colors",
              active ? "text-accent" : "text-text-dim"
            )}
          >
            <Icon size={20} />
            <span>{tab.label}</span>
          </button>
        )
      })}
    </nav>
  )
}

export { MobileNav }
