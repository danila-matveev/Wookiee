import * as React from "react"
import { createPortal } from "react-dom"
import { cn } from "@/lib/utils"

export type TooltipPosition = "top" | "bottom" | "left" | "right"

export interface TooltipProps {
  content: React.ReactNode
  position?: TooltipPosition
  delay?: number
  disabled?: boolean
  children: React.ReactElement
  className?: string
}

interface Coords {
  top: number
  left: number
}

export function Tooltip({
  content,
  position = "top",
  delay = 150,
  disabled = false,
  children,
  className,
}: TooltipProps) {
  const [open, setOpen] = React.useState(false)
  const [coords, setCoords] = React.useState<Coords>({ top: 0, left: 0 })
  const triggerRef = React.useRef<HTMLElement | null>(null)
  const tooltipRef = React.useRef<HTMLDivElement | null>(null)
  const timerRef = React.useRef<number | null>(null)
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => {
    setMounted(true)
  }, [])

  const computePosition = React.useCallback(() => {
    if (!triggerRef.current || !tooltipRef.current) return
    const tRect = triggerRef.current.getBoundingClientRect()
    const tipRect = tooltipRef.current.getBoundingClientRect()
    const offset = 6
    let top = 0
    let left = 0
    switch (position) {
      case "top":
        top = tRect.top - tipRect.height - offset
        left = tRect.left + tRect.width / 2 - tipRect.width / 2
        break
      case "bottom":
        top = tRect.bottom + offset
        left = tRect.left + tRect.width / 2 - tipRect.width / 2
        break
      case "left":
        top = tRect.top + tRect.height / 2 - tipRect.height / 2
        left = tRect.left - tipRect.width - offset
        break
      case "right":
        top = tRect.top + tRect.height / 2 - tipRect.height / 2
        left = tRect.right + offset
        break
    }
    setCoords({ top: top + window.scrollY, left: left + window.scrollX })
  }, [position])

  React.useLayoutEffect(() => {
    if (open) computePosition()
  }, [open, computePosition])

  React.useEffect(() => {
    if (!open) return
    const handler = () => computePosition()
    window.addEventListener("scroll", handler, true)
    window.addEventListener("resize", handler)
    return () => {
      window.removeEventListener("scroll", handler, true)
      window.removeEventListener("resize", handler)
    }
  }, [open, computePosition])

  const show = () => {
    if (disabled || !content) return
    if (timerRef.current) window.clearTimeout(timerRef.current)
    timerRef.current = window.setTimeout(() => setOpen(true), delay)
  }
  const hide = () => {
    if (timerRef.current) window.clearTimeout(timerRef.current)
    setOpen(false)
  }

  const child = React.Children.only(children) as React.ReactElement<
    React.HTMLAttributes<HTMLElement> & { ref?: React.Ref<HTMLElement> }
  >
  const childProps = child.props
  const setRef = (node: HTMLElement | null) => {
    triggerRef.current = node
    const original = (child as unknown as { ref?: React.Ref<HTMLElement> }).ref
    if (typeof original === "function") original(node)
    else if (original && typeof original === "object")
      (original as React.MutableRefObject<HTMLElement | null>).current = node
  }

  const trigger = React.cloneElement(child, {
    ref: setRef,
    onMouseEnter: (e: React.MouseEvent<HTMLElement>) => {
      childProps.onMouseEnter?.(e)
      show()
    },
    onMouseLeave: (e: React.MouseEvent<HTMLElement>) => {
      childProps.onMouseLeave?.(e)
      hide()
    },
    onFocus: (e: React.FocusEvent<HTMLElement>) => {
      childProps.onFocus?.(e)
      show()
    },
    onBlur: (e: React.FocusEvent<HTMLElement>) => {
      childProps.onBlur?.(e)
      hide()
    },
  } as React.HTMLAttributes<HTMLElement> & { ref?: React.Ref<HTMLElement> })

  return (
    <>
      {trigger}
      {mounted && open && content
        ? createPortal(
            <div
              ref={tooltipRef}
              role="tooltip"
              className={cn(
                "fixed z-[var(--z-toast)] pointer-events-none whitespace-nowrap rounded-md px-2 py-1 text-[11px] font-medium shadow-[var(--shadow-md)]",
                "bg-[var(--color-text-primary)] text-[var(--color-surface)]",
                className,
              )}
              style={{ top: coords.top, left: coords.left, position: "absolute" }}
            >
              {content}
            </div>,
            document.body,
          )
        : null}
    </>
  )
}
