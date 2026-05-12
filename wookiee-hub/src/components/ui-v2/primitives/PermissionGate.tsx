import * as React from "react"
import { cn } from "@/lib/utils"
import { Tooltip } from "./Tooltip"

export interface PermissionGateProps {
  allowed: boolean
  reason?: string
  children: React.ReactElement
  /**
   * When true, render nothing instead of a disabled element when not allowed.
   */
  hideWhenDenied?: boolean
}

const DEFAULT_REASON = "Нет прав, обратитесь к руководителю"

/**
 * Wraps any child element and, when `allowed === false`, marks it as disabled
 * (visually + a11y) and wraps it into a Tooltip with the rejection reason.
 *
 * Usage:
 *   <PermissionGate allowed={canEdit}><Button>Save</Button></PermissionGate>
 */
export function PermissionGate({
  allowed,
  reason = DEFAULT_REASON,
  children,
  hideWhenDenied = false,
}: PermissionGateProps) {
  const child = React.Children.only(children)

  if (allowed) return child

  if (hideWhenDenied) return null

  const existingClassName =
    (child.props as { className?: string }).className ?? ""

  const disabledChild = React.cloneElement(child, {
    disabled: true,
    "aria-disabled": true,
    tabIndex: -1,
    onClick: (e: React.MouseEvent) => {
      e.preventDefault()
      e.stopPropagation()
    },
    className: cn(existingClassName, "cursor-not-allowed opacity-60 pointer-events-none"),
  } as Partial<React.HTMLAttributes<HTMLElement>> & {
    disabled?: boolean
    tabIndex?: number
  })

  return (
    <Tooltip content={reason} position="top">
      <span
        className="inline-flex"
        // The Tooltip needs a focusable/hoverable wrapper because the child
        // itself is pointer-events:none.
        tabIndex={0}
        aria-label={reason}
      >
        {disabledChild}
      </span>
    </Tooltip>
  )
}
