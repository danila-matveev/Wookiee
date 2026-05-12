import * as React from "react"
import { createPortal } from "react-dom"
import { cn } from "@/lib/utils"

export interface ContextMenuItem {
  id?: string
  label: string
  icon?: React.ComponentType<{ className?: string }>
  shortcut?: string
  danger?: boolean
  disabled?: boolean
  onClick?: () => void
  divider?: boolean
}

export interface ContextMenuProps {
  items: ContextMenuItem[]
  children: React.ReactNode
  className?: string
}

interface MenuPosition {
  x: number
  y: number
}

export function ContextMenu({ items, children, className }: ContextMenuProps) {
  const [position, setPosition] = React.useState<MenuPosition | null>(null)
  const menuRef = React.useRef<HTMLDivElement | null>(null)

  const close = React.useCallback(() => setPosition(null), [])

  // Outside click + Esc + scroll closes the menu.
  React.useEffect(() => {
    if (!position) return

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node | null
      if (target && menuRef.current?.contains(target)) return
      close()
    }
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation()
        close()
      }
    }
    document.addEventListener("mousedown", handlePointerDown)
    document.addEventListener("keydown", handleKey)
    window.addEventListener("scroll", close, true)
    window.addEventListener("resize", close)
    return () => {
      document.removeEventListener("mousedown", handlePointerDown)
      document.removeEventListener("keydown", handleKey)
      window.removeEventListener("scroll", close, true)
      window.removeEventListener("resize", close)
    }
  }, [position, close])

  // Clamp the menu inside viewport once it has been measured.
  React.useLayoutEffect(() => {
    if (!position || !menuRef.current) return
    const rect = menuRef.current.getBoundingClientRect()
    const maxX = window.innerWidth - rect.width - 8
    const maxY = window.innerHeight - rect.height - 8
    const clampedX = Math.min(Math.max(8, position.x), Math.max(8, maxX))
    const clampedY = Math.min(Math.max(8, position.y), Math.max(8, maxY))
    if (clampedX !== position.x || clampedY !== position.y) {
      setPosition({ x: clampedX, y: clampedY })
    }
  }, [position])

  const handleContextMenu = (event: React.MouseEvent<HTMLDivElement>) => {
    event.preventDefault()
    setPosition({ x: event.clientX, y: event.clientY })
  }

  return (
    <>
      <div onContextMenu={handleContextMenu} className={className}>
        {children}
      </div>
      {position &&
        createPortal(
          <div
            ref={menuRef}
            role="menu"
            className={cn(
              "fixed flex flex-col min-w-[14rem] p-1",
              "bg-elevated border border-default rounded-md shadow-[var(--shadow-md)]",
            )}
            style={{
              zIndex: "var(--z-overlay)",
              top: position.y,
              left: position.x,
            }}
          >
            {items.map((item, index) => {
              if (item.divider) {
                return (
                  <div
                    key={item.id ?? `divider-${index}`}
                    role="separator"
                    className="h-px my-1 mx-1 bg-[var(--color-border-default)]"
                  />
                )
              }
              const Icon = item.icon
              return (
                <button
                  key={item.id ?? `${item.label}-${index}`}
                  type="button"
                  role="menuitem"
                  disabled={item.disabled}
                  onClick={() => {
                    item.onClick?.()
                    close()
                  }}
                  className={cn(
                    "w-full flex items-center gap-2 px-2.5 py-1.5 text-sm text-left rounded-sm outline-none",
                    "hover:bg-surface-muted focus-visible:bg-surface-muted",
                    item.danger ? "text-danger" : "text-secondary",
                    item.disabled && "opacity-50 cursor-not-allowed",
                  )}
                >
                  {Icon && <Icon className="w-3.5 h-3.5 shrink-0" />}
                  <span className="flex-1 truncate">{item.label}</span>
                  {item.shortcut && (
                    <span className="ml-2 text-[10px] uppercase tracking-wider text-muted font-mono">
                      {item.shortcut}
                    </span>
                  )}
                </button>
              )
            })}
          </div>,
          document.body,
        )}
    </>
  )
}
