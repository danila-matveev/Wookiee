import { useState } from "react"
import { Copy, Home, Layers, Save, Sparkles, Star } from "lucide-react"
import { Button, IconButton, StatusBadge } from "@/components/ui-v2/primitives"
import {
  Breadcrumbs,
  PageHeader,
  Stepper,
  Tabs,
} from "@/components/ui-v2/layout"
import { Demo, SubSection } from "../shared"

/**
 * LayoutSection — canonical reference: `foundation.jsx:2148-2210`.
 *
 * We extend the canonical (which shows underline/pill/segmented) with our
 * vertical variant — it's a legitimate addition for settings-style
 * navigation. Sidebar/TopBar demo is our own mini-layout preview so the
 * user can see them in situ.
 */
export function LayoutSection() {
  const [tab1, setTab1] = useState("description")
  const [tab2, setTab2] = useState("month")
  const [tab3, setTab3] = useState("list")
  const [tab4, setTab4] = useState("general")

  return (
    <div className="space-y-12">
      {/* === Tabs === */}
      <SubSection title="Tabs — четыре варианта">
        <Demo title="Underline (основная навигация внутри карточки)" full>
          <Tabs
            value={tab1}
            onChange={setTab1}
            variant="underline"
            items={[
              { value: "description", label: "Описание" },
              { value: "attributes", label: "Атрибуты" },
              { value: "sku", label: "SKU", count: 24 },
              { value: "content", label: "Контент" },
            ]}
          />
        </Demo>

        <Demo title="Pills (переключение временных окон)" full>
          <Tabs
            value={tab2}
            onChange={setTab2}
            variant="pills"
            items={[
              { value: "day", label: "День" },
              { value: "week", label: "Неделя" },
              { value: "month", label: "Месяц" },
              { value: "year", label: "Год" },
            ]}
          />
        </Demo>

        <Demo title="Segmented (переключение форматов отображения)" full>
          <Tabs
            value={tab3}
            onChange={setTab3}
            variant="segmented"
            items={[
              { value: "list", label: "Список" },
              { value: "grid", label: "Сетка" },
              { value: "kanban", label: "Канбан" },
            ]}
          />
        </Demo>

        <Demo title="Vertical (наш extension — для settings-навигации)" full>
          <div className="flex gap-6">
            <Tabs
              value={tab4}
              onChange={setTab4}
              variant="vertical"
              items={[
                { value: "general", label: "Общее" },
                { value: "profile", label: "Профиль" },
                { value: "billing", label: "Биллинг" },
                { value: "team", label: "Команда" },
              ]}
            />
            <div className="flex-1 bg-surface-muted rounded-lg p-4 text-sm text-secondary">
              Активная вкладка:{" "}
              <span className="text-primary font-medium">{tab4}</span>
            </div>
          </div>
        </Demo>
      </SubSection>

      {/* === Breadcrumbs === */}
      <SubSection title="Breadcrumbs">
        <Demo title="Простая иерархия — string[]" full>
          <Breadcrumbs items={["Hub", "Каталог", "Бюстгальтеры", "Vuki"]} />
        </Demo>

        <Demo title="С линками — {label, href?}[]" full>
          <Breadcrumbs
            items={[
              { label: "Hub", href: "/" },
              { label: "Каталог", href: "/catalog" },
              { label: "Бюстгальтеры", href: "/catalog?cat=bra" },
              { label: "Vuki" },
            ]}
          />
        </Demo>
      </SubSection>

      {/* === Stepper === */}
      <SubSection title="Stepper" description="Для wizard'ов и многошаговых форм.">
        <Demo title="Создание модели — 4 шага" full>
          <div className="w-full px-12">
            <Stepper
              current={2}
              steps={[
                { label: "Основа" },
                { label: "Атрибуты" },
                { label: "Артикулы" },
                { label: "Публикация" },
              ]}
            />
          </div>
        </Demo>
      </SubSection>

      {/* === PageHeader === */}
      <SubSection title="PageHeader">
        <Demo title="С breadcrumbs, status, actions" full padded={false}>
          <div className="w-full p-5">
            <PageHeader
              kicker="МОДЕЛЬ"
              title="Vuki — основа коллекции"
              breadcrumbs={["Hub", "Каталог", "Бюстгальтеры"]}
              status={<StatusBadge statusId={1} />}
              icon={<Star className="w-6 h-6 text-accent" />}
              actions={
                <>
                  <Button variant="secondary" icon={Copy} size="sm">
                    Дублировать
                  </Button>
                  <Button icon={Save} size="sm">
                    Сохранить
                  </Button>
                </>
              }
            />
          </div>
        </Demo>
      </SubSection>

      {/* === Sidebar + TopBar mini-layout ===
          NB: production Sidebar primitive is `sticky h-screen` by design.
          The mini-preview rolls its own static layout from semantic tokens so
          the demo card stays contained (the live shell at the page level
          uses the real <Sidebar /> primitive). */}
      <SubSection
        title="Sidebar + TopBar (in situ)"
        description="Мини-превью продакшен-shell'а: брендовый блок, навигация, шапка с действиями."
      >
        <Demo title="Mini layout" full padded={false}>
          <div
            className="w-full bg-page border-t border-default flex overflow-hidden"
            style={{ height: 320 }}
          >
            {/* Mini sidebar — visual clone of <Sidebar /> using semantic tokens. */}
            <aside className="w-48 shrink-0 h-full overflow-y-auto bg-surface-muted border-r border-default flex flex-col">
              <div className="px-4 py-3 border-b border-default">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center">
                    <Sparkles className="w-3 h-3 text-white" />
                  </div>
                  <div>
                    <div className="font-serif italic text-sm text-primary leading-none">
                      Wookiee
                    </div>
                    <div className="text-[9px] uppercase tracking-wider text-label mt-0.5">
                      Hub
                    </div>
                  </div>
                </div>
              </div>
              <nav className="flex-1 min-h-0 overflow-y-auto py-2 px-2 space-y-3">
                <div className="space-y-0.5">
                  <div className="px-2 py-1 text-[10px] uppercase tracking-wider text-label">
                    Основа
                  </div>
                  <button
                    type="button"
                    className="group w-full flex items-center gap-2.5 px-2 h-8 rounded-md text-sm bg-[var(--color-text-primary)] text-[var(--color-surface)] font-medium"
                  >
                    <Home className="w-3.5 h-3.5 shrink-0" />
                    <span className="flex-1 text-left truncate">Главная</span>
                  </button>
                  <button
                    type="button"
                    className="group w-full flex items-center gap-2.5 px-2 h-8 rounded-md text-sm text-secondary hover:bg-surface hover:text-primary"
                  >
                    <Layers className="w-3.5 h-3.5 shrink-0 text-muted" />
                    <span className="flex-1 text-left truncate">Каталог</span>
                    <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[10px] tabular-nums bg-surface text-muted border border-default">
                      37
                    </span>
                  </button>
                </div>
              </nav>
              <div className="shrink-0 px-3 py-3 border-t border-default text-[10px] uppercase tracking-wider text-label">
                v2 · preview
              </div>
            </aside>

            {/* Mini top-bar + main content. */}
            <main className="flex-1 min-w-0 flex flex-col">
              <header className="h-12 px-4 border-b border-default bg-surface flex items-center justify-between gap-4">
                <div className="flex items-center gap-3 min-w-0">
                  <Breadcrumbs
                    items={[
                      { label: "Hub" },
                      { label: "Каталог" },
                      { label: "Vuki" },
                    ]}
                  />
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Button variant="secondary" size="sm">
                    Экспорт
                  </Button>
                  <IconButton aria-label="Настройки" icon={Star} size="sm" />
                </div>
              </header>
              <div className="p-4 text-sm text-secondary flex-1 min-h-0 overflow-y-auto">
                Контент страницы. В продакшене топ-бар + сайдбар —{" "}
                <code className="font-mono text-xs">sticky</code>, основная область
                скроллится самостоятельно.
              </div>
            </main>
          </div>
        </Demo>
      </SubSection>
    </div>
  )
}
