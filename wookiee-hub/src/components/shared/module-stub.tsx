import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

interface ModuleStubProps {
  icon: LucideIcon
  title: string
  description: string
  className?: string
}

export function ModuleStub({ icon: Icon, title, description, className }: ModuleStubProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center min-h-[400px] py-10", className)}>
      <div className="w-[72px] h-[72px] rounded-2xl bg-accent-soft border border-accent-border flex items-center justify-center mb-4">
        <Icon size={32} className="text-accent" />
      </div>
      <h2 className="text-xl font-bold">{title}</h2>
      <p className="text-sm text-muted-foreground max-w-[380px] text-center leading-relaxed mt-2">
        {description}
      </p>
      <span className="mt-3 inline-flex items-center px-3 py-1 rounded-full bg-accent-soft text-accent text-xs font-semibold">
        В разработке
      </span>
    </div>
  )
}
