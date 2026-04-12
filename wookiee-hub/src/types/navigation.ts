import type { LucideIcon } from "lucide-react"

export interface NavGroup {
  id: string
  icon: LucideIcon
  label: string
  items: NavItem[]
}

export interface NavItem {
  id: string
  label: string
  icon: LucideIcon
  path: string
  badge?: string
}
