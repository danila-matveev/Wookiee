import {
  MessageSquare,
  LayoutGrid,
  Star,
  HelpCircle,
  CheckCircle2,
  BarChart3,
  Activity,
  Clock,
  Users2,
  Kanban,
  CalendarDays,
  TrendingUp,
  Package,
  Palette,
  Layers,
  BookOpen,
  Tag,
  Boxes,
  FolderTree,
  Building2,
  Briefcase,
  Ruler,
  Sparkles,
  Box,
  Tv,
  ShieldCheck,
} from "lucide-react"
import type { NavGroup } from "@/types/navigation"

export const navigationGroups: NavGroup[] = [
  {
    id: "catalog",
    icon: Package,
    label: "Каталог",
    items: [
      // Контент (5)
      { id: "catalog-matrix",   label: "Базовые модели", icon: Package, path: "/catalog/matrix"   },
      { id: "catalog-colors",   label: "Цвета",          icon: Palette, path: "/catalog/colors"   },
      { id: "catalog-artikuly", label: "Артикулы",       icon: Tag,     path: "/catalog/artikuly" },
      { id: "catalog-tovary",   label: "Товары/SKU",     icon: Boxes,   path: "/catalog/tovary"   },
      { id: "catalog-skleyki",  label: "Склейки",        icon: Layers,  path: "/catalog/skleyki"  },
      // Справочники (9)
      { id: "ref-kategorii",        label: "Категории",        icon: FolderTree,  path: "/catalog/references/kategorii" },
      { id: "ref-kollekcii",        label: "Коллекции",        icon: BookOpen,    path: "/catalog/references/kollekcii" },
      { id: "ref-fabriki",          label: "Производители",    icon: Building2,   path: "/catalog/references/fabriki"   },
      { id: "ref-importery",        label: "Юрлица",           icon: Briefcase,   path: "/catalog/references/importery" },
      { id: "ref-razmery",          label: "Размеры",          icon: Ruler,       path: "/catalog/references/razmery"   },
      { id: "ref-semeystva-cvetov", label: "Семейства цветов", icon: Sparkles,    path: "/catalog/semeystva-cvetov"     },
      { id: "ref-upakovki",         label: "Упаковки",         icon: Box,         path: "/catalog/upakovki"             },
      { id: "ref-kanaly-prodazh",   label: "Каналы продаж",    icon: Tv,          path: "/catalog/kanaly-prodazh"       },
      { id: "ref-sertifikaty",      label: "Сертификаты",      icon: ShieldCheck, path: "/catalog/sertifikaty"          },
    ],
  },
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
  {
    id: "influence",
    icon: Users2,
    label: "Influence CRM",
    items: [
      { id: "bloggers",     label: "Блогеры",    icon: Users2,       path: "/influence/bloggers" },
      { id: "integrations", label: "Интеграции", icon: Kanban,       path: "/influence/integrations" },
      { id: "calendar",     label: "Календарь",  icon: CalendarDays, path: "/influence/calendar" },
    ],
  },
  {
    id: "analytics",
    icon: TrendingUp,
    label: "Аналитика",
    items: [
      { id: "rnp", label: "Рука на пульсе", icon: Activity, path: "/analytics/rnp" },
    ],
  },
]
