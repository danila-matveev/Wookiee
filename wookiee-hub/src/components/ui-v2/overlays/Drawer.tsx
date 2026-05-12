import * as React from "react"
import { createPortal } from "react-dom"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

export type DrawerSide = "right" | "left" | "top" | "bottom"
/**
 * Drawer size:
 * - `sm | md | lg | xl` — width/height presets (existing).
 * - `filters` — right-side filter sidebar (420px). Canonical default per
 *   foundation.jsx:2239.
 * - `detail` — right-side detail panel (560px). Used for Kanban card
 *   detail, integrations edit (see patterns.jsx).
 */
export type DrawerSize = "sm" | "md" | "lg" | "xl" | "filters" | "detail"

export interface DrawerProps {
  open: boolean
  onClose: () => void
  side?: DrawerSide
  size?: DrawerSize
  title?: string
  description?: string
  children?: React.ReactNode
  footer?: React.ReactNode
  className?: string
  closeOnBackdrop?: boolean
  closeOnEscape?: boolean
}

// Width / height presets per side. Right/left use width; top/bottom use height.
const horizontalSizes: Record<DrawerSize, string> = {
  sm: "w-[360px]",
  md: "w-[560px]",
  lg: "w-[720px]",
  xl: "w-[920px]",
  filters: "w-[420px]",
  detail: "w-[560px]",
}

const verticalSizes: Record<DrawerSize, string> = {
  sm: "h-[35vh]",
  md: "h-[55vh]",
  lg: "h-[75vh]",
  xl: "h-[90vh]",
  // Vertical drawers default to canonical 60vh for both preset aliases.
  filters: "h-[60vh]",
  detail: "h-[60vh]",
}

const sidePosition: Record<DrawerSide, string> = {
  right: "right-0 top-0 bottom-0 border-l",
  left: "left-0 top-0 bottom-0 border-r",
  top: "left-0 right-0 top-0 border-b rounded-b-lg",
  bottom: "left-0 right-0 bottom-0 border-t rounded-t-lg",
}

export function Drawer({
  open,
  onClose,
  side = "right",
  size = "md",
  title,
  description,
  children,
  footer,
  className,
  closeOnBackdrop = true,
  closeOnEscape = true,
}: DrawerProps) {
  const previousFocusRef = React.useRef<HTMLElement | null>(null)
  const drawerRef = React.useRef<HTMLDivElement | null>(null)

  React.useEffect(() => {
    if (!open) return

    previousFocusRef.current = document.activeElement as HTMLElement | null

    const handleKey = (event: KeyboardEvent) => {
      if (closeOnEscape && event.key === "Escape") {
        event.stopPropagation()
        onClose()
      }
    }
    document.addEventListener("keydown", handleKey)

    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"

    window.requestAnimationFrame(() => {
      drawerRef.current?.focus()
    })

    return () => {
      document.removeEventListener("keydown", handleKey)
      document.body.style.overflow = prevOverflow
      previousFocusRef.current?.focus?.()
    }
  }, [open, onClose, closeOnEscape])

  if (!open) return null

  const sizeClass = side === "right" || side === "left" ? horizontalSizes[size] : verticalSizes[size]

  const node = (
    <div
      // Canonical (foundation.jsx:2243) — warm stone-900 tint in light mode.
      className="fixed inset-0 bg-stone-900/40 dark:bg-black/60 backdrop-blur-sm"
      style={{ zIndex: "var(--z-modal)" }}
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onMouseDown={(event) => {
        if (closeOnBackdrop && event.target === event.currentTarget) {
          onClose()
        }
      }}
    >
      <div
        ref={drawerRef}
        tabIndex={-1}
        className={cn(
          "absolute bg-surface border-default outline-none flex flex-col",
          "shadow-[var(--shadow-lg)]",
          sidePosition[side],
          sizeClass,
          (side === "right" || side === "left") && "max-w-full",
          (side === "top" || side === "bottom") && "max-h-full",
          className,
        )}
        onMouseDown={(event) => event.stopPropagation()}
      >
        {(title || description) && (
          <div className="flex items-start justify-between gap-4 px-5 py-3.5 border-b border-default shrink-0">
            <div className="min-w-0">
              {title && (
                <h3 className="text-base font-medium text-primary truncate">{title}</h3>
              )}
              {description && (
                <p className="mt-0.5 text-xs text-muted">{description}</p>
              )}
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Закрыть"
              className="-mr-1 p-1 rounded-md text-muted hover:bg-surface-muted transition-colors"
            >
              <X className="w-4 h-4" aria-hidden />
            </button>
          </div>
        )}
        <div className="flex-1 min-h-0 overflow-y-auto p-5 text-sm text-secondary">
          {children}
        </div>
        {footer && (
          <div className="px-5 py-3 border-t border-default flex justify-end gap-2 shrink-0">
            {footer}
          </div>
        )}
      </div>
    </div>
  )

  return createPortal(node, document.body)
}
