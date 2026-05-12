import * as React from "react"
import { createPortal } from "react-dom"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

export type ModalSize = "sm" | "md" | "lg" | "xl"

export interface ModalProps {
  open: boolean
  onClose: () => void
  title?: string
  description?: string
  children?: React.ReactNode
  footer?: React.ReactNode
  size?: ModalSize
  className?: string
  closeOnBackdrop?: boolean
  closeOnEscape?: boolean
}

const sizeStyles: Record<ModalSize, string> = {
  sm: "max-w-sm",
  md: "max-w-lg",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
}

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
  className,
  closeOnBackdrop = true,
  closeOnEscape = true,
}: ModalProps) {
  const previousFocusRef = React.useRef<HTMLElement | null>(null)
  const dialogRef = React.useRef<HTMLDivElement | null>(null)

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

    // Move focus into dialog
    window.requestAnimationFrame(() => {
      dialogRef.current?.focus()
    })

    return () => {
      document.removeEventListener("keydown", handleKey)
      document.body.style.overflow = prevOverflow
      previousFocusRef.current?.focus?.()
    }
  }, [open, onClose, closeOnEscape])

  if (!open) return null

  const node = (
    <div
      // Canonical (foundation.jsx:2220) — warm stone-900 tint in light mode, black in dark.
      className="fixed inset-0 flex items-start justify-center pt-[10vh] px-4 bg-stone-900/40 dark:bg-black/60 backdrop-blur-sm"
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
        ref={dialogRef}
        tabIndex={-1}
        className={cn(
          "w-full bg-surface rounded-lg border border-default outline-none",
          "shadow-[var(--shadow-lg)]",
          sizeStyles[size],
          className,
        )}
        onMouseDown={(event) => event.stopPropagation()}
      >
        {(title || description) && (
          <div className="flex items-start justify-between gap-4 px-5 py-3.5 border-b border-default">
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
        <div className="p-5 text-sm text-secondary">{children}</div>
        {footer && (
          <div className="px-5 py-3 border-t border-default flex justify-end gap-2">
            {footer}
          </div>
        )}
      </div>
    </div>
  )

  return createPortal(node, document.body)
}
