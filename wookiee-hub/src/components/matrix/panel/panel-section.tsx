import * as React from "react"
import { Collapsible } from "@base-ui/react/collapsible"
import { ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"

interface PanelSectionProps {
  title: string
  children: React.ReactNode
  defaultOpen?: boolean
  className?: string
}

export function PanelSection({
  title,
  children,
  defaultOpen = true,
  className,
}: PanelSectionProps) {
  return (
    <Collapsible.Root defaultOpen={defaultOpen} className={cn("border-b border-border last:border-b-0", className)}>
      <Collapsible.Trigger className="flex w-full items-center justify-between px-4 py-2.5 hover:bg-accent/30 transition-colors cursor-pointer group">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {title}
        </span>
        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground transition-transform duration-200 group-data-[panel-open]:rotate-0 rotate-[-90deg]" />
      </Collapsible.Trigger>
      <Collapsible.Panel className="overflow-hidden">
        <div className="px-4 pb-3 pt-0.5 space-y-0.5">
          {children}
        </div>
      </Collapsible.Panel>
    </Collapsible.Root>
  )
}
