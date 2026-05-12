import * as React from "react"
import { cn } from "@/lib/utils"
import { Avatar, type AvatarProps, type AvatarSize } from "./Avatar"

export interface AvatarGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  users: Array<Omit<AvatarProps, "size">>
  max?: number
  size?: AvatarSize
}

const overlapClass: Record<AvatarSize, string> = {
  xs: "-ml-1",
  sm: "-ml-1.5",
  md: "-ml-2",
  lg: "-ml-2.5",
  xl: "-ml-3",
}

const overflowSize: Record<AvatarSize, string> = {
  xs: "w-5 h-5 text-[9px]",
  sm: "w-6 h-6 text-[10px]",
  md: "w-8 h-8 text-xs",
  lg: "w-10 h-10 text-sm",
  xl: "w-12 h-12 text-base",
}

export const AvatarGroup = React.forwardRef<HTMLDivElement, AvatarGroupProps>(
  function AvatarGroup({ users, max = 4, size = "md", className, ...props }, ref) {
    const visible = users.slice(0, max)
    const rest = users.length - max

    return (
      <div ref={ref} className={cn("inline-flex items-center", className)} {...props}>
        {visible.map((user, i) => (
          <span
            key={i}
            className={cn(
              "rounded-full ring-2 ring-[var(--color-surface)]",
              i > 0 && overlapClass[size],
            )}
          >
            <Avatar {...user} size={size} />
          </span>
        ))}
        {rest > 0 && (
          <span
            className={cn(
              "inline-flex items-center justify-center rounded-full font-medium",
              "bg-surface-muted text-secondary border border-default ring-2 ring-[var(--color-surface)]",
              overflowSize[size],
              overlapClass[size],
            )}
            aria-label={`Ещё ${rest}`}
          >
            +{rest}
          </span>
        )}
      </div>
    )
  },
)
