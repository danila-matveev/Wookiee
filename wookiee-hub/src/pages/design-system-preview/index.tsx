import { useState } from "react"
import {
  BarChart3,
  Bell,
  Box,
  ChevronRight,
  Copy,
  Download,
  Edit3,
  Layers,
  Moon,
  Palette,
  Sparkles,
  Sun,
  TrendingUp,
} from "lucide-react"
import { useThemeStore } from "@/stores/theme"
import { Button, IconButton, Kbd } from "@/components/ui-v2/primitives"
import { FoundationSection } from "./sections/foundation"
import { AtomsSection } from "./sections/atoms"
import { FormsSection } from "./sections/forms"
import { DataSection } from "./sections/data"
import { ChartsSection } from "./sections/charts"
import { LayoutSection } from "./sections/layout"
import { OverlaysSection } from "./sections/overlays"
import { FeedbackSection } from "./sections/feedback"

/**
 * /design-system-preview — canonical-fidelity showcase shell.
 *
 * Canonical reference: `foundation.jsx:2598-2703` (`SECTIONS` registry +
 * `App()` shell with sidebar nav + sticky topbar). We mirror that contract
 * end-to-end: brand block at sidebar top, grouped navigation, theme block
 * at sidebar footer, sticky header with kicker + active label + actions,
 * main canvas with italic-serif page title and section lede.
 */

const GROUPS = ["Основа", "Данные", "Структура"] as const
type Group = (typeof GROUPS)[number]

interface SectionEntry {
  id: string
  label: string
  lede: string
  icon: React.ComponentType<{ className?: string }>
  Component: React.ComponentType
  group: Group
}

const SECTIONS: readonly SectionEntry[] = [
  {
    id: "foundation",
    label: "Foundation",
    lede: "Базовая палитра, семантические токены, типографика, шкала отступов. Всё, на чём держится остальная DS.",
    icon: Palette,
    Component: FoundationSection,
    group: "Основа",
  },
  {
    id: "atoms",
    label: "Atoms",
    lede: "Кнопки, бейджи, поля ввода, аватары, прогрессы — пиксель-перфектные клоны canonical.",
    icon: Box,
    Component: AtomsSection,
    group: "Основа",
  },
  {
    id: "forms",
    label: "Forms",
    lede: "Базовые и расширенные поля формы с обёрткой FieldWrap и интеграцией LevelBadge.",
    icon: Edit3,
    Component: FormsSection,
    group: "Основа",
  },
  {
    id: "data",
    label: "Data display",
    lede: "Таблицы, KPI-карточки, пагинация, дерево. Появится после Wave 3a.",
    icon: BarChart3,
    Component: DataSection,
    group: "Данные",
  },
  {
    id: "charts",
    label: "Charts",
    lede: "Recharts-обёртки: линии, бары, donut, funnel, heatmap. Появится после Wave 3b.",
    icon: TrendingUp,
    Component: ChartsSection,
    group: "Данные",
  },
  {
    id: "layout",
    label: "Layout",
    lede: "Tabs, Breadcrumbs, Stepper, PageHeader, sidebar/topbar mini-shell.",
    icon: Layers,
    Component: LayoutSection,
    group: "Структура",
  },
  {
    id: "overlays",
    label: "Overlays",
    lede: "Modal, Drawer (filters / detail / bottom), Popover, DropdownMenu, ContextMenu, CommandPalette.",
    icon: Copy,
    Component: OverlaysSection,
    group: "Структура",
  },
  {
    id: "feedback",
    label: "Feedback",
    lede: "Toast (5 + loading), Alert (4 варианта), EmptyState, Skeleton.",
    icon: Bell,
    Component: FeedbackSection,
    group: "Структура",
  },
] as const

export default function DesignSystemPreview() {
  const [activeId, setActiveId] = useState<string>("foundation")
  const { theme, toggleTheme } = useThemeStore()

  const active = SECTIONS.find((s) => s.id === activeId) ?? SECTIONS[0]
  const Active = active.Component

  const grouped: Record<Group, SectionEntry[]> = {
    Основа: [],
    Данные: [],
    Структура: [],
  }
  for (const s of SECTIONS) {
    grouped[s.group].push(s)
  }

  return (
    <div className="min-h-screen bg-page flex">
      {/* ============================================================
       * SIDEBAR — brand + grouped nav + theme block.
       *  We render a custom sticky aside instead of mounting the
       *  shared <Sidebar /> primitive: the production primitive is
       *  `sticky top-0 h-screen` and assumes a global app shell. The
       *  preview is mounted as its own page, so it composes the same
       *  visual contract using the semantic tokens directly.
       * ============================================================ */}
      <aside className="w-60 shrink-0 h-screen sticky top-0 overflow-y-auto bg-surface-muted border-r border-default flex flex-col">
        {/* Brand block */}
        <div className="px-4 py-4 border-b border-default shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center shrink-0">
              <Sparkles className="w-4 h-4 text-white" aria-hidden />
            </div>
            <div className="min-w-0">
              <div className="font-serif italic text-base text-primary leading-none">
                Wookiee
              </div>
              <div className="text-[10px] uppercase tracking-wider text-label mt-1">
                DS v2 · Foundation
              </div>
            </div>
          </div>
        </div>

        {/* Grouped nav */}
        <nav className="flex-1 min-h-0 overflow-y-auto py-3 px-2 space-y-4">
          {GROUPS.map((group) => (
            <div key={group} className="space-y-0.5">
              <div className="px-2 py-1 text-[10px] uppercase tracking-wider text-label">
                {group}
              </div>
              {grouped[group].map((section) => {
                const Icon = section.icon
                const isActive = section.id === activeId
                return (
                  <button
                    key={section.id}
                    type="button"
                    aria-current={isActive ? "page" : undefined}
                    onClick={() => setActiveId(section.id)}
                    className={
                      "group w-full flex items-center gap-2.5 px-2 h-8 rounded-md text-sm transition-colors outline-none " +
                      "focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] focus-visible:ring-offset-1 focus-visible:ring-offset-[var(--color-surface)] " +
                      (isActive
                        ? "bg-[var(--color-text-primary)] text-[var(--color-surface)] font-medium"
                        : "text-secondary hover:bg-surface hover:text-primary")
                    }
                  >
                    <Icon className={"w-3.5 h-3.5 shrink-0 " + (isActive ? "" : "text-muted")} />
                    <span className="flex-1 truncate text-left">{section.label}</span>
                  </button>
                )
              })}
            </div>
          ))}
        </nav>

        {/* Theme block */}
        <div className="shrink-0 px-3 py-3 border-t border-default">
          <div className="text-[10px] uppercase tracking-wider text-label mb-2 px-1">
            Тема
          </div>
          <button
            type="button"
            onClick={toggleTheme}
            className="w-full flex items-center justify-between gap-2 rounded-md px-3 h-8 text-sm border border-default text-secondary hover:bg-surface hover:text-primary transition-colors"
          >
            <span className="flex items-center gap-2">
              {theme === "light" ? (
                <Sun className="w-3.5 h-3.5" />
              ) : (
                <Moon className="w-3.5 h-3.5" />
              )}
              {theme === "light" ? "Светлая" : "Тёмная"}
            </span>
            <Kbd>⌘⇧L</Kbd>
          </button>
        </div>
      </aside>

      {/* ============================================================
       * MAIN — sticky top bar + page header + active section.
       * ============================================================ */}
      <main className="flex-1 min-w-0">
        <header className="sticky top-0 z-20 h-14 px-6 bg-elevated border-b border-default flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-[11px] uppercase tracking-wider text-label shrink-0">
              Wookiee Hub · Design System
            </span>
            <ChevronRight className="w-3 h-3 text-label shrink-0" />
            <span className="text-sm font-medium text-primary truncate">
              {active.label}
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button variant="secondary" size="sm" icon={Download}>
              Экспорт токенов
            </Button>
            <IconButton
              aria-label="Toggle theme"
              icon={theme === "light" ? Moon : Sun}
              onClick={toggleTheme}
              variant="secondary"
            />
          </div>
        </header>

        <div className="px-8 py-8 max-w-6xl">
          <div className="mb-8">
            <div className="text-[11px] uppercase tracking-wider text-label mb-1">
              Дизайн-система v2
            </div>
            <h1 className="font-serif italic text-4xl text-primary mb-2 leading-tight">
              {active.label}
            </h1>
            <p className="text-sm text-muted max-w-2xl">{active.lede}</p>
          </div>

          <Active />

          <footer className="mt-16 pt-6 border-t border-default text-center text-xs text-muted">
            Design System v2 · Wookiee Hub · 2026
          </footer>
        </div>
      </main>
    </div>
  )
}
