import { useEffect } from "react"
import { X } from "lucide-react"
import { useNavigate, useLocation } from "react-router-dom"
import { cn } from "@/lib/utils"
import { navigationGroups } from "@/config/navigation"

interface MobileMenuProps {
  open: boolean
  onClose: () => void
}

function MobileMenu({ open, onClose }: MobileMenuProps) {
  const navigate = useNavigate()
  const location = useLocation()

  // Lock body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden"
    } else {
      document.body.style.overflow = ""
    }
    return () => {
      document.body.style.overflow = ""
    }
  }, [open])

  if (!open) return null

  function handleItemClick(path: string) {
    navigate(path)
    onClose()
  }

  return (
    <div data-slot="mobile-menu" className="fixed inset-0 z-[100]">
      {/* Overlay */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* Panel */}
      <div className="absolute left-0 top-0 bottom-0 w-[280px] bg-background border-r border-border overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-4 h-12 border-b border-border shrink-0">
          <span className="text-[14px] font-semibold">Меню</span>
          <button
            onClick={onClose}
            aria-label="Закрыть меню"
            className="text-text-dim hover:text-foreground transition-colors p-1 rounded hover:bg-bg-hover"
          >
            <X size={18} />
          </button>
        </div>

        {/* Navigation groups */}
        <div className="py-2">
          {navigationGroups.map((group) => (
            <div key={group.id}>
              <div className="text-[11px] uppercase text-muted-foreground font-semibold px-4 py-2">
                {group.label}
              </div>
              {group.items.map((item) => {
                const Icon = item.icon
                const active = location.pathname === item.path
                return (
                  <button
                    key={item.id}
                    onClick={() => handleItemClick(item.path)}
                    className={cn(
                      "w-full flex items-center gap-2.5 px-4 py-2.5 text-[13px] transition-colors text-left",
                      active
                        ? "bg-accent-soft text-accent font-medium"
                        : "text-foreground hover:bg-bg-hover"
                    )}
                  >
                    <Icon size={16} className="shrink-0" />
                    <span>{item.label}</span>
                    {item.badge && (
                      <span className="ml-auto text-[10px] text-text-dim bg-bg-soft border border-border rounded px-1.5 py-0.5">
                        {item.badge}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export { MobileMenu }
