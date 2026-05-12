import { useState } from "react"
import { useLocation, Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import {
  Package,
  Palette,
  Tag,
  Boxes,
  Layers,
  FolderTree,
  BookOpen,
  Bookmark,
  Building2,
  Briefcase,
  Ruler,
  Sparkles,
  Box,
  Tv,
  ShieldCheck,
  SlidersHorizontal,
  Upload,
  ChevronsLeft,
  Settings,
} from "lucide-react"
import { fetchCatalogCounts, type CatalogCounts } from "@/lib/catalog/service"

interface SidebarItem {
  key: string
  icon: React.ElementType
  label: string
  path: string
  countKey?: keyof CatalogCounts
}

interface SidebarGroup {
  title: string
  items: SidebarItem[]
}

const GROUPS: SidebarGroup[] = [
  {
    title: "Контент",
    items: [
      { key: "matrix",   icon: Package,  label: "Базовые модели", path: "/catalog/matrix",   countKey: "models" },
      { key: "colors",   icon: Palette,  label: "Цвета",           path: "/catalog/colors",   countKey: "colors" },
      { key: "artikuly", icon: Tag,      label: "Артикулы",        path: "/catalog/artikuly", countKey: "artikuly" },
      { key: "tovary",   icon: Boxes,    label: "Товары/SKU",      path: "/catalog/tovary",   countKey: "tovary" },
      { key: "skleyki",  icon: Layers,   label: "Склейки",         path: "/catalog/skleyki",  countKey: "skleyki" },
    ],
  },
  {
    title: "Справочники",
    items: [
      { key: "brendy",           icon: Bookmark,    label: "Бренды",           path: "/catalog/references/brendy",            countKey: "brendy" },
      { key: "kategorii",        icon: FolderTree,  label: "Категории",        path: "/catalog/references/kategorii",         countKey: "kategorii" },
      { key: "kollekcii",        icon: BookOpen,    label: "Коллекции",        path: "/catalog/references/kollekcii",         countKey: "kollekcii" },
      { key: "tipy-kollekciy",   icon: Layers,      label: "Типы коллекций",   path: "/catalog/references/tipy-kollekciy",    countKey: "tipy_kollekciy" },
      { key: "fabriki",          icon: Building2,   label: "Производители",    path: "/catalog/references/fabriki",           countKey: "fabriki" },
      { key: "importery",        icon: Briefcase,   label: "Юрлица",           path: "/catalog/references/importery",         countKey: "importery" },
      { key: "razmery",          icon: Ruler,       label: "Размеры",          path: "/catalog/references/razmery",           countKey: "razmery" },
      { key: "semeystva-cvetov", icon: Sparkles,    label: "Семейства цветов", path: "/catalog/semeystva-cvetov",             countKey: "semeystva_cvetov" },
      { key: "upakovki",         icon: Box,         label: "Упаковки",         path: "/catalog/upakovki",                     countKey: "upakovki" },
      { key: "kanaly-prodazh",   icon: Tv,          label: "Каналы продаж",    path: "/catalog/kanaly-prodazh",               countKey: "kanaly_prodazh" },
      { key: "sertifikaty",      icon: ShieldCheck, label: "Сертификаты",      path: "/catalog/sertifikaty",                  countKey: "sertifikaty" },
      { key: "atributy",         icon: SlidersHorizontal, label: "Атрибуты",   path: "/catalog/references/atributy",          countKey: "atributy" },
    ],
  },
  {
    title: "Операции",
    items: [
      { key: "import", icon: Upload, label: "Импорт CSV", path: "/catalog/import" },
    ],
  },
]

function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—"
  return String(value)
}

export function CatalogSidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const { pathname } = useLocation()

  const { data: counts } = useQuery({
    queryKey: ["catalog", "counts"],
    queryFn: fetchCatalogCounts,
    staleTime: 60_000,
  })

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
              className="cat-font-serif text-lg leading-none italic text-stone-900"
            >
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
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className="text-stone-400 hover:text-stone-700 -mr-1 shrink-0"
          aria-label={collapsed ? "Развернуть боковую панель" : "Свернуть боковую панель"}
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
              const count = item.countKey ? counts?.[item.countKey] : undefined
              return (
                <Link
                  key={item.key}
                  to={item.path}
                  className={`flex items-center gap-2.5 py-1.5 text-sm transition-colors ${
                    active
                      ? "bg-stone-100 text-stone-900 font-medium"
                      : "text-stone-700 hover:bg-stone-100/60"
                  } ${collapsed ? "justify-center px-0" : "px-4"}`}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  {!collapsed && (
                    <>
                      <span className="flex-1 text-left truncate">{item.label}</span>
                      {item.countKey && (
                        <span
                          className={`text-[10px] tabular-nums ${
                            active ? "text-stone-500" : "text-stone-400"
                          }`}
                        >
                          {formatCount(count)}
                        </span>
                      )}
                    </>
                  )}
                </Link>
              )
            })}
          </div>
        ))}
      </nav>

      {/* Footer — profile */}
      {!collapsed && (
        <div className="border-t border-stone-200 p-3 space-y-2">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-stone-700 to-stone-900 text-white flex items-center justify-center text-[11px] font-medium">
              Д
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-stone-900 truncate">Данила</div>
              <div className="text-[10px] text-stone-500">CEO · Wookiee</div>
            </div>
            <Settings className="w-3.5 h-3.5 text-stone-400" />
          </div>
          <Link
            to="/operations/tools"
            className="flex items-center gap-2 text-[11px] text-stone-500 hover:text-stone-700 transition-colors"
          >
            <span>← Назад в Hub</span>
          </Link>
        </div>
      )}
    </aside>
  )
}
