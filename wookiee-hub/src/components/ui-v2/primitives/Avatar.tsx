import * as React from "react"
import { cn } from "@/lib/utils"

export type AvatarSize = "xs" | "sm" | "md" | "lg" | "xl"
export type AvatarStatus = "online" | "busy" | "offline"

export interface AvatarProps extends Omit<React.HTMLAttributes<HTMLSpanElement>, "children"> {
  src?: string
  alt?: string
  name?: string
  size?: AvatarSize
  status?: AvatarStatus
}

const sizeStyles: Record<AvatarSize, string> = {
  xs: "w-5 h-5 text-[9px]",
  sm: "w-6 h-6 text-[10px]",
  md: "w-8 h-8 text-xs",
  lg: "w-10 h-10 text-sm",
  xl: "w-12 h-12 text-base",
}

const statusSize: Record<AvatarSize, string> = {
  xs: "w-1.5 h-1.5",
  sm: "w-2 h-2",
  md: "w-2.5 h-2.5",
  lg: "w-3 h-3",
  xl: "w-3.5 h-3.5",
}

const statusColor: Record<AvatarStatus, string> = {
  online: "bg-[var(--color-success)]",
  busy: "bg-[var(--color-warning)]",
  offline: "bg-[var(--color-text-muted)]",
}

function getInitials(name?: string): string {
  if (!name) return "?"
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return "?"
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

export const Avatar = React.forwardRef<HTMLSpanElement, AvatarProps>(function Avatar(
  { src, alt, name, size = "md", status, className, ...props },
  ref,
) {
  const [imgError, setImgError] = React.useState(false)
  const showImage = Boolean(src) && !imgError
  const initials = getInitials(name)

  return (
    <span
      ref={ref}
      className={cn("relative inline-flex shrink-0", sizeStyles[size], className)}
      {...props}
    >
      <span
        className={cn(
          "inline-flex w-full h-full items-center justify-center rounded-full overflow-hidden",
          "bg-surface-muted text-secondary font-medium border border-default",
        )}
        aria-label={alt ?? name ?? "Аватар"}
      >
        {showImage ? (
          <img
            src={src}
            alt={alt ?? name ?? ""}
            onError={() => setImgError(true)}
            className="w-full h-full object-cover"
          />
        ) : (
          <span aria-hidden>{initials}</span>
        )}
      </span>
      {status && (
        <span
          aria-hidden
          className={cn(
            "absolute -bottom-0 -right-0 rounded-full ring-2 ring-[var(--color-surface)]",
            statusSize[size],
            statusColor[status],
          )}
        />
      )}
    </span>
  )
})
