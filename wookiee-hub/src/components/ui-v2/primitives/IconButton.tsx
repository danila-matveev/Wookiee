import * as React from "react"
import { Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

export type IconButtonVariant =
  | "primary"
  | "secondary"
  | "ghost"
  | "danger"
  | "active"
export type IconButtonSize = "sm" | "md" | "lg"

export interface IconButtonProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  icon: React.ComponentType<{ className?: string }>
  "aria-label": string
  variant?: IconButtonVariant
  size?: IconButtonSize
  loading?: boolean
  active?: boolean
}

// Canonical default = 28×28 via p-1.5 (md). sm = 24×24, lg = 32×32 — extensions.
const sizeStyles: Record<IconButtonSize, string> = {
  sm: "w-6 h-6 rounded-md p-1",
  md: "w-7 h-7 rounded-md p-1.5",
  lg: "w-8 h-8 rounded-md p-1.5",
}

const iconSizeStyles: Record<IconButtonSize, string> = {
  sm: "w-3 h-3",
  md: "w-4 h-4",
  lg: "w-[18px] h-[18px]",
}

const variantStyles: Record<IconButtonVariant, string> = {
  primary:
    "bg-[var(--color-text-primary)] text-[var(--color-surface)] hover:opacity-90 active:opacity-80",
  secondary:
    "bg-surface text-secondary border border-default hover:bg-surface-muted",
  ghost:
    "bg-transparent text-secondary hover:bg-surface-muted",
  danger:
    "bg-transparent text-danger hover:bg-danger-soft",
  active:
    "bg-surface-muted text-primary hover:bg-surface-muted",
}

export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  function IconButton(
    {
      icon: Icon,
      variant = "ghost",
      size = "md",
      loading = false,
      active = false,
      disabled,
      className,
      ...props
    },
    ref,
  ) {
    const isDisabled = disabled || loading
    // `active` boolean overrides variant to the canonical pressed-state look.
    const effectiveVariant: IconButtonVariant = active ? "active" : variant
    return (
      <button
        ref={ref}
        type={props.type ?? "button"}
        disabled={isDisabled}
        aria-pressed={active || undefined}
        className={cn(
          "inline-flex items-center justify-center transition-colors select-none outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-surface)] disabled:opacity-50 disabled:cursor-not-allowed",
          sizeStyles[size],
          variantStyles[effectiveVariant],
          className,
        )}
        {...props}
      >
        {loading ? (
          <Loader2 className={cn(iconSizeStyles[size], "animate-spin")} aria-hidden />
        ) : (
          <Icon className={iconSizeStyles[size]} aria-hidden />
        )}
      </button>
    )
  },
)
