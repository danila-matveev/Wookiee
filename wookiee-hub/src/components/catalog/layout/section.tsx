import type { ReactNode } from "react"

interface SectionProps {
  label: string
  hint?: string
  children: ReactNode
  action?: ReactNode
}

export function Section({ label, hint, children, action }: SectionProps) {
  return (
    <div className="bg-white rounded-lg border border-stone-200 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-stone-200">
        <div>
          <div className="font-medium text-stone-900 text-sm">{label}</div>
          {hint && <div className="text-xs text-stone-500 mt-0.5">{hint}</div>}
        </div>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </div>
  )
}

interface SidebarBlockProps {
  label: string
  badge?: ReactNode
  action?: ReactNode
  children: ReactNode
}

export function SidebarBlock({ label, badge, action, children }: SidebarBlockProps) {
  return (
    <div className="bg-white rounded-lg border border-stone-200 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-stone-200">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-stone-900">{label}</span>
          {badge}
        </div>
        {action}
      </div>
      <div className="p-4">{children}</div>
    </div>
  )
}
