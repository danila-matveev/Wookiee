import * as React from "react"
import {
  Info as InfoIcon,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Bell,
} from "lucide-react"
import { cn } from "@/lib/utils"

export type AlertVariant = "default" | "success" | "warning" | "danger" | "info"

export interface AlertProps {
  variant?: AlertVariant
  title?: string
  description?: React.ReactNode
  /** Optional icon override. Default uses variant-specific icon. */
  icon?: React.ComponentType<{ className?: string }>
  actions?: React.ReactNode
  children?: React.ReactNode
  className?: string
}

const defaultIcons: Record<AlertVariant, React.ComponentType<{ className?: string }>> = {
  default: Bell,
  success: CheckCircle2,
  warning: AlertTriangle,
  danger: XCircle,
  info: InfoIcon,
}

// Canonical (foundation.jsx:2492-2510) uses `border-X-200` — a thin clean
// line one step darker than `bg-X-50`. With our semantic tokens that maps
// to a 20% opacity of the variant accent (vs the previous 30%, which read
// too soft per the audit).
const variantStyles: Record<AlertVariant, { bg: string; accent: string; border: string }> = {
  default: {
    bg: "bg-surface-muted",
    accent: "text-muted",
    border: "border-default",
  },
  success: {
    bg: "bg-success-soft",
    accent: "text-success",
    border: "border-[color:var(--color-success)]/20",
  },
  warning: {
    bg: "bg-warning-soft",
    accent: "text-warning",
    border: "border-[color:var(--color-warning)]/20",
  },
  danger: {
    bg: "bg-danger-soft",
    accent: "text-danger",
    border: "border-[color:var(--color-danger)]/20",
  },
  info: {
    bg: "bg-info-soft",
    accent: "text-info",
    border: "border-[color:var(--color-info)]/20",
  },
}

export function Alert({
  variant = "default",
  title,
  description,
  icon,
  actions,
  children,
  className,
}: AlertProps) {
  const Icon = icon ?? defaultIcons[variant]
  const styles = variantStyles[variant]
  const body = description ?? children

  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-3 rounded-md p-3 border",
        styles.bg,
        styles.border,
        className,
      )}
    >
      <Icon className={cn("w-4 h-4 mt-0.5 shrink-0", styles.accent)} aria-hidden />
      <div className="flex-1 min-w-0">
        {title && <div className="text-sm font-medium text-primary">{title}</div>}
        {body && (
          <div className={cn("text-xs text-secondary", title && "mt-0.5")}>{body}</div>
        )}
        {actions && <div className="mt-2 flex items-center gap-2">{actions}</div>}
      </div>
    </div>
  )
}
