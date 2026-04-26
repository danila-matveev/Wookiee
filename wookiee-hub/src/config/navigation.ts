import {
  MessageSquare,
  Bot,
  Star,
  HelpCircle,
  CheckCircle2,
  BarChart3,
  LayoutGrid,
  ScrollText,
} from "lucide-react"
import type { NavGroup } from "@/types/navigation"

export const navigationGroups: NavGroup[] = [
  {
    id: "community",
    icon: MessageSquare,
    label: "Комьюнити",
    items: [
      { id: "reviews", label: "Отзывы", icon: Star, path: "/community/reviews" },
      { id: "questions", label: "Вопросы", icon: HelpCircle, path: "/community/questions" },
      { id: "answers", label: "Ответы", icon: CheckCircle2, path: "/community/answers" },
      { id: "analytics", label: "Аналитика", icon: BarChart3, path: "/community/analytics" },
    ],
  },
  {
    id: "agents",
    icon: Bot,
    label: "Агенты",
    items: [
      { id: "skills", label: "Табло скиллов", icon: LayoutGrid, path: "/agents/skills" },
      { id: "runs", label: "История запусков", icon: ScrollText, path: "/agents/runs" },
    ],
  },
]
