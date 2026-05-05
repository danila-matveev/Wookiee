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
    label: "Операции",
    items: [
      { id: "tools",    label: "Каталог инструментов", icon: LayoutGrid, path: "/operations/tools" },
      { id: "activity", label: "История запусков",      icon: Activity,  path: "/operations/activity", badge: "Фаза 2" },
      { id: "health",   label: "Состояние системы",     icon: Clock,     path: "/operations/health",   badge: "Фаза 2" },
    ],
  },
  {
    id: "community",
    icon: MessageSquare,
    label: "Коммуникации",
    items: [
      { id: "reviews",   label: "Отзывы",    icon: Star,         path: "/community/reviews" },
      { id: "questions", label: "Вопросы",   icon: HelpCircle,   path: "/community/questions" },
      { id: "answers",   label: "Ответы",    icon: CheckCircle2, path: "/community/answers" },
      { id: "analytics", label: "Аналитика", icon: BarChart3,    path: "/community/analytics" },
    ],
  },
]
