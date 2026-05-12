import * as React from "react"
import { createPortal } from "react-dom"
import { cn } from "@/lib/utils"

/**
 * Placement:
 * - Cardinal (`top | bottom | left | right`) — centered alignment relative to trigger.
 * - Edge aliases (`bottom-start | bottom-end | top-start | top-end`) — match the
 *   canonical (foundation.jsx:2266-2270) where the panel left- or right-aligns to
 *   the trigger instead of centring (DropdownMenu defaults to `bottom-end`).
 */
export type PopoverPlacement =
  | "top"
  | "bottom"
  | "left"
  | "right"
  | "bottom-start"
  | "bottom-end"
  | "top-start"
  | "top-end"

export interface PopoverProps {
  trigger: React.ReactNode
  children: React.ReactNode
  placement?: PopoverPlacement
  open?: boolean
  defaultOpen?: boolean
  onOpenChange?: (open: boolean) => void
  className?: string
  /** Offset in px between trigger and panel. */
  offset?: number
  /** Close when click happens outside. Default: true. */
  closeOnOutsideClick?: boolean
  /** Close on Esc. Default: true. */
  closeOnEscape?: boolean
}

interface PanelPosition {
  top: number
  left: number
}

function computePosition(
  triggerRect: DOMRect,
  panelRect: DOMRect,
  placement: PopoverPlacement,
  offset: number,
): PanelPosition {
  switch (placement) {
    case "top":
      return {
        top: triggerRect.top - panelRect.height - offset,
        left: triggerRect.left + triggerRect.width / 2 - panelRect.width / 2,
      }
    case "top-start":
      return {
        top: triggerRect.top - panelRect.height - offset,
        left: triggerRect.left,
      }
    case "top-end":
      return {
        top: triggerRect.top - panelRect.height - offset,
        left: triggerRect.right - panelRect.width,
      }
    case "left":
      return {
        top: triggerRect.top + triggerRect.height / 2 - panelRect.height / 2,
        left: triggerRect.left - panelRect.width - offset,
      }
    case "right":
      return {
        top: triggerRect.top + triggerRect.height / 2 - panelRect.height / 2,
        left: triggerRect.right + offset,
      }
    case "bottom-end":
      return {
        top: triggerRect.bottom + offset,
        left: triggerRect.right - panelRect.width,
      }
    case "bottom-start":
    case "bottom":
    default:
      return {
        top: triggerRect.bottom + offset,
        left: triggerRect.left,
      }
  }
}

export function Popover({
  trigger,
  children,
  placement = "bottom",
  open: controlledOpen,
  defaultOpen = false,
  onOpenChange,
  className,
  offset = 6,
  closeOnOutsideClick = true,
  closeOnEscape = true,
}: PopoverProps) {
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(defaultOpen)
  const isControlled = controlledOpen !== undefined
  const open = isControlled ? controlledOpen : uncontrolledOpen

  const setOpen = React.useCallback(
    (next: boolean) => {
      if (!isControlled) setUncontrolledOpen(next)
      onOpenChange?.(next)
    },
    [isControlled, onOpenChange],
  )

  const triggerRef = React.useRef<HTMLSpanElement | null>(null)
  const panelRef = React.useRef<HTMLDivElement | null>(null)
  const [position, setPosition] = React.useState<PanelPosition | null>(null)

  // Position the panel after it mounts and on resize/scroll.
  React.useLayoutEffect(() => {
    if (!open) {
      setPosition(null)
      return
    }
    const update = () => {
      const triggerEl = triggerRef.current
      const panelEl = panelRef.current
      if (!triggerEl || !panelEl) return
      const triggerRect = triggerEl.getBoundingClientRect()
      const panelRect = panelEl.getBoundingClientRect()
      const next = computePosition(triggerRect, panelRect, placement, offset)
      // Clamp into viewport
      const maxLeft = window.innerWidth - panelRect.width - 8
      const maxTop = window.innerHeight - panelRect.height - 8
      next.left = Math.min(Math.max(8, next.left), Math.max(8, maxLeft))
      next.top = Math.min(Math.max(8, next.top), Math.max(8, maxTop))
      setPosition(next)
    }
    update()
    window.addEventListener("resize", update)
    window.addEventListener("scroll", update, true)
    return () => {
      window.removeEventListener("resize", update)
      window.removeEventListener("scroll", update, true)
    }
  }, [open, placement, offset, children])

  // Outside click + Esc.
  React.useEffect(() => {
    if (!open) return

    const handlePointerDown = (event: MouseEvent) => {
      if (!closeOnOutsideClick) return
      const target = event.target as Node | null
      if (!target) return
      if (panelRef.current?.contains(target)) return
      if (triggerRef.current?.contains(target)) return
      setOpen(false)
    }

    const handleKey = (event: KeyboardEvent) => {
      if (closeOnEscape && event.key === "Escape") {
        event.stopPropagation()
        setOpen(false)
      }
    }

    document.addEventListener("mousedown", handlePointerDown)
    document.addEventListener("keydown", handleKey)
    return () => {
      document.removeEventListener("mousedown", handlePointerDown)
      document.removeEventListener("keydown", handleKey)
    }
  }, [open, closeOnOutsideClick, closeOnEscape, setOpen])

  return (
    <>
      <span
        ref={triggerRef}
        onClick={() => setOpen(!open)}
        className="inline-flex"
      >
        {trigger}
      </span>
      {open &&
        createPortal(
          <div
            ref={panelRef}
            role="dialog"
            className={cn(
              "fixed bg-elevated border border-default rounded-md shadow-[var(--shadow-md)] min-w-[12rem] outline-none",
              !position && "opacity-0 pointer-events-none",
              className,
            )}
            style={{
              zIndex: "var(--z-overlay)",
              top: position?.top ?? 0,
              left: position?.left ?? 0,
            }}
          >
            {children}
          </div>,
          document.body,
        )}
    </>
  )
}
