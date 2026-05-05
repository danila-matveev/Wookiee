import {
  MessageSquare,
  LayoutGrid,
  Star,
  HelpCircle,
  CheckCircle2,
  BarChart3,
  Activity,
  Clock,
} from "lucide-react"
import type { NavGroup } from "@/types/navigation"

export const navigationGroups: NavGroup[] = [
  {
    id: "operations",
    icon: LayoutGrid,
    label: "Operations",
    items: [
      { id: "tools",    label: "Tools Catalog", icon: LayoutGrid, path: "/operations/tools",    badge: "47" },
      { id: "activity", label: "Activity Feed",  icon: Activity,  path: "/operations/activity", badge: "Phase 2" },
      { id: "health",   label: "System Health",  icon: Clock,     path: "/operations/health",   badge: "Phase 2" },
    ],
  },
  {
    id: "community",
    icon: MessageSquare,
    label: "Комьюнити",
    items: [
      { id: "reviews",   label: "Отзывы",    icon: Star,         path: "/community/reviews" },
      { id: "questions", label: "Вопросы",   icon: HelpCircle,   path: "/community/questions" },
      { id: "answers",   label: "Ответы",    icon: CheckCircle2, path: "/community/answers" },
      { id: "analytics", label: "Аналитика", icon: BarChart3,    path: "/community/analytics" },
    ],
  },
]
