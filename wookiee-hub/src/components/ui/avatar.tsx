import { cn } from "@/lib/utils"

export interface AvatarProps {
  name: string
  src?: string
  size?: "sm" | "md" | "lg"
  className?: string
}

const SIZES = { sm: "size-6 text-xs", md: "size-8 text-sm", lg: "size-10 text-base" }

function initials(name: string): string {
  return name.trim().split(/\s+/).slice(0, 2).map(w => w[0]?.toUpperCase() ?? "").join("")
}

export function Avatar({ name, src, size = "md", className }: AvatarProps) {
  return (
    <span
      data-slot="avatar"
      className={cn(
        "inline-flex items-center justify-center rounded-full overflow-hidden bg-secondary text-secondary-foreground font-medium",
        SIZES[size],
        className,
      )}
    >
      {src
        ? <img src={src} alt={name} className="size-full object-cover" />
        : initials(name)}
    </span>
  )
}
