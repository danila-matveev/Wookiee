import { NavLink, Outlet } from "react-router-dom"
import { cn } from "@/lib/utils"
import {
  Database,
  Globe,
  FileText,
  Archive,
  BarChart3,
} from "lucide-react"

const adminNav = [
  { to: "/system/matrix-admin/schema", label: "Схема", icon: Database },
  { to: "/system/matrix-admin/api", label: "API", icon: Globe },
  { to: "/system/matrix-admin/logs", label: "Логи", icon: FileText },
  { to: "/system/matrix-admin/archive", label: "Архив", icon: Archive },
  { to: "/system/matrix-admin/stats", label: "Статистика", icon: BarChart3 },
]

export function MatrixAdminLayout() {
  return (
    <div className="flex h-full">
      <nav className="w-52 border-r bg-muted/30 p-3 space-y-1">
        <h2 className="px-2 mb-3 text-sm font-semibold text-muted-foreground uppercase tracking-wider">
          Admin Panel
        </h2>
        {adminNav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors",
                isActive
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              )
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="flex-1 p-6 overflow-auto">
        <Outlet />
      </div>
    </div>
  )
}
