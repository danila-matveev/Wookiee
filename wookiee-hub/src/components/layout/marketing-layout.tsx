import { NavLink, Outlet } from "react-router-dom"
import { Percent, Hash } from "lucide-react"

const SUB_NAV = [
  { to: "/marketing/promo-codes", icon: Percent, label: "Промокоды" },
  { to: "/marketing/search-queries", icon: Hash, label: "Поисковые запросы" },
] as const

export function MarketingLayout() {
  return (
    <div data-section="marketing" className="flex h-screen overflow-hidden" style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <aside className="w-44 shrink-0 flex flex-col border-r border-stone-200 bg-white">
        <div className="px-3 py-3 border-b border-stone-100">
          <div className="text-[11px] uppercase tracking-wider text-stone-400 font-medium px-1">
            МАРКЕТИНГ
          </div>
        </div>
        <nav className="flex-1 p-2 space-y-0.5">
          {SUB_NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-[13px] transition-colors ${
                  isActive
                    ? "bg-stone-100 text-stone-900 font-medium"
                    : "text-stone-500 hover:bg-stone-50"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <item.icon className={`w-3.5 h-3.5 ${isActive ? "text-stone-700" : "text-stone-400"}`} />
                  <span className="truncate text-left">{item.label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        <Outlet />
      </main>
    </div>
  )
}
