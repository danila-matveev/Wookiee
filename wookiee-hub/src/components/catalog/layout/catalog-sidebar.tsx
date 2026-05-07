import { useState } from "react"
import { useLocation, Link } from "react-router-dom"
import {
  Package,
  Palette,
  Layers,
  FolderTree,
  BookOpen,
  Building2,
  Briefcase,
  Ruler,
  Sparkles,
  ChevronsLeft,
} from "lucide-react"

interface SidebarItem {
  key: string
  icon: React.ElementType
  label: string
  path: string
}

interface SidebarGroup {
  title: string
  items: SidebarItem[]
}

const GROUPS: SidebarGroup[] = [
  {
    title: "Каталог",
    items: [
      { key: "matrix",  icon: Package, label: "Матрица товаров", path: "/catalog/matrix"  },
      { key: "colors",  icon: Palette, label: "Цвета",            path: "/catalog/colors"  },
      { key: "skleyki", icon: Layers,  label: "Склейки МП",       path: "/catalog/skleyki" },
    ],
  },
  {
    title: "Справочники",
    items: [
      { key: "kategorii", icon: FolderTree, label: "Категории",     path: "/catalog/references/kategorii" },
      { key: "kollekcii", icon: BookOpen,   label: "Коллекции",     path: "/catalog/references/kollekcii" },
      { key: "fabriki",   icon: Building2,  label: "Производители", path: "/catalog/references/fabriki"   },
      { key: "importery", icon: Briefcase,  label: "Юрлица",        path: "/catalog/references/importery" },
      { key: "razmery",   icon: Ruler,      label: "Размеры",       path: "/catalog/references/razmery"   },
      { key: "statusy",   icon: Sparkles,   label: "Статусы",       path: "/catalog/references/statusy"   },
    ],
  },
]

export function CatalogSidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const { pathname } = useLocation()

  const isActive = (path: string) =>
    pathname === path || pathname.startsWith(path + "/")

  return (
    <aside
      className={`${collapsed ? "w-16" : "w-60"} shrink-0 border-r border-stone-200 bg-stone-50/60 flex flex-col transition-all duration-200`}
    >
      {/* Header */}
      <div className="h-14 px-4 flex items-center justify-between border-b border-stone-200">
        {!collapsed && (
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-md bg-stone-900 text-white flex items-center justify-center text-xs font-semibold">
              W
            </div>
            <span
              className="text-lg leading-none italic text-stone-900"
              style={{ fontFamily: "'Instrument Serif', ui-serif, Georgia, serif" }}
            >
              Wookiee
            </span>
            <span className="text-[10px] text-stone-400 mt-1 uppercase tracking-wider">
              Каталог
            </span>
          </div>
        )}
        {collapsed && (
          <div className="w-7 h-7 rounded-md bg-stone-900 text-white flex items-center justify-center text-xs font-semibold mx-auto">
            W
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="text-stone-400 hover:text-stone-700 -mr-1 shrink-0"
        >
          <ChevronsLeft
            className={`w-4 h-4 transition-transform ${collapsed ? "rotate-180" : ""}`}
          />
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3">
        {GROUPS.map((g) => (
          <div key={g.title} className="mb-4">
            {!collapsed && (
              <div className="px-4 pb-1 text-[10px] uppercase tracking-wider text-stone-400 font-medium">
                {g.title}
              </div>
            )}
            {g.items.map((item) => {
              const Icon = item.icon
              const active = isActive(item.path)
              return (
                <Link
                  key={item.key}
                  to={item.path}
                  className={`flex items-center gap-2.5 py-1.5 text-sm transition-colors ${
                    active
                      ? "bg-stone-900 text-white"
                      : "text-stone-700 hover:bg-stone-100"
                  } ${collapsed ? "justify-center px-0" : "px-4"}`}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  {!collapsed && (
                    <span className="flex-1 text-left truncate">{item.label}</span>
                  )}
                </Link>
              )
            })}
          </div>
        ))}
      </nav>

      {/* Footer */}
      {!collapsed && (
        <div className="border-t border-stone-200 p-3">
          <Link
            to="/operations/tools"
            className="flex items-center gap-2 text-xs text-stone-500 hover:text-stone-700 transition-colors"
          >
            <span>← Назад в Hub</span>
          </Link>
        </div>
      )}
    </aside>
  )
}
