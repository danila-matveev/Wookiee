import * as React from "react"
import { Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "ghost"
  | "danger"
  | "danger-ghost"
  | "success"
export type ButtonSize = "xs" | "sm" | "md" | "lg"

type ButtonOwnProps = {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  icon?: React.ComponentType<{ className?: string }>
  iconRight?: React.ComponentType<{ className?: string }>
}

type PolymorphicProps<E extends React.ElementType> = ButtonOwnProps & {
  as?: E
} & Omit<React.ComponentPropsWithoutRef<E>, keyof ButtonOwnProps | "as">

export type ButtonProps = PolymorphicProps<"button">

const sizeStyles: Record<ButtonSize, string> = {
  xs: "h-7 px-2 text-xs gap-1 rounded-md",
  sm: "h-7 px-2.5 text-xs gap-1.5 rounded-md",
  md: "h-8 px-3 text-sm gap-1.5 rounded-md",
  lg: "h-10 px-4 text-sm gap-2 rounded-md",
}

const iconSizeStyles: Record<ButtonSize, string> = {
  xs: "w-3 h-3",
  sm: "w-3 h-3",
  md: "w-3.5 h-3.5",
  lg: "w-4 h-4",
}

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    "bg-[var(--color-text-primary)] text-[var(--color-surface)] hover:opacity-90 active:opacity-80 disabled:opacity-50",
  secondary:
    "bg-surface text-secondary border border-default hover:bg-surface-muted disabled:opacity-50",
  ghost:
    "bg-transparent text-secondary hover:bg-surface-muted disabled:opacity-50",
  danger:
    "bg-[var(--color-danger)] text-white hover:opacity-90 active:opacity-80 disabled:opacity-50",
  "danger-ghost":
    "bg-transparent text-danger hover:bg-danger-soft disabled:opacity-50",
  success:
    "bg-[var(--color-success)] text-white hover:opacity-90 active:opacity-80 disabled:opacity-50",
}

const baseStyles =
  "inline-flex items-center justify-center font-medium transition-colors select-none outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-surface)] disabled:cursor-not-allowed disabled:pointer-events-none"

const ButtonInner = React.forwardRef<HTMLElement, ButtonProps & { as?: React.ElementType }>(
  function Button(
    {
      as,
      variant = "primary",
      size = "md",
      loading = false,
      disabled,
      icon: Icon,
      iconRight: IconRight,
      className,
      children,
      ...props
    },
    ref,
  ) {
    const Component = (as ?? "button") as React.ElementType
    const isDisabled = disabled || loading
    const iconClass = iconSizeStyles[size]

    return (
      <Component
        ref={ref}
        disabled={Component === "button" ? isDisabled : undefined}
        aria-disabled={isDisabled || undefined}
        className={cn(
          baseStyles,
          sizeStyles[size],
          variantStyles[variant],
          className,
        )}
        {...props}
      >
        {loading ? (
          <Loader2 className={cn(iconClass, "animate-spin")} aria-hidden />
        ) : (
          Icon && <Icon className={iconClass} aria-hidden />
        )}
        {children}
        {!loading && IconRight && <IconRight className={iconClass} aria-hidden />}
      </Component>
    )
  },
)

export const Button = ButtonInner as <E extends React.ElementType = "button">(
  props: PolymorphicProps<E> & { ref?: React.Ref<Element> },
) => React.ReactElement | null
