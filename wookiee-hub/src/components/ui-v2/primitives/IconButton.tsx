import * as React from "react"
import { Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

type IconButtonVariant = "primary" | "secondary" | "ghost" | "destructive"
type IconButtonSize = "sm" | "md" | "lg"

export interface IconButtonProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  icon: React.ComponentType<{ className?: string }>
  "aria-label": string
  variant?: IconButtonVariant
  size?: IconButtonSize
  loading?: boolean
  active?: boolean
}

const sizeStyles: Record<IconButtonSize, string> = {
  sm: "w-7 h-7 rounded-md",
  md: "w-8 h-8 rounded-md",
  lg: "w-10 h-10 rounded-md",
}

const iconSizeStyles: Record<IconButtonSize, string> = {
  sm: "w-3.5 h-3.5",
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
  destructive:
    "bg-transparent text-[var(--color-danger)] hover:bg-danger-soft",
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
    return (
      <button
        ref={ref}
        type={props.type ?? "button"}
        disabled={isDisabled}
        aria-pressed={active || undefined}
        className={cn(
          "inline-flex items-center justify-center transition-colors select-none outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-surface)] disabled:opacity-50 disabled:cursor-not-allowed",
          sizeStyles[size],
          variantStyles[variant],
          active &&
            "bg-[var(--color-text-primary)] text-[var(--color-surface)] hover:opacity-90",
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
