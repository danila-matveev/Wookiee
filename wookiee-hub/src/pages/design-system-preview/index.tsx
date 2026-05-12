import { useState } from "react"
import {
  Search,
  Plus,
  Trash2,
  Star,
  Settings,
  ChevronRight,
} from "lucide-react"
import { useThemeStore } from "@/stores/theme"
import {
  Avatar,
  AvatarGroup,
  Badge,
  Button,
  Chip,
  ColorSwatch,
  FilterChip,
  IconButton,
  Kbd,
  LevelBadge,
  PermissionGate,
  PriorityBadge,
  ProgressBar,
  Ring,
  Skeleton,
  StatusBadge,
  Tag,
  Tooltip,
} from "@/components/ui-v2/primitives"
import {
  Combobox,
  DatePicker,
  FieldWrap,
  FileUpload,
  MultiSelectField,
  NumberField,
  SelectField,
  TextField,
  TextareaField,
} from "@/components/ui-v2/forms"
import {
  Breadcrumbs,
  PageHeader,
  Stepper,
  Tabs,
} from "@/components/ui-v2/layout"
import {
  CommandPalette,
  Drawer,
  DropdownMenu,
  Modal,
  Popover,
} from "@/components/ui-v2/overlays"
import { Alert, EmptyState, useToast } from "@/components/ui-v2/feedback"

function ThemeToggle() {
  const { theme, toggleTheme } = useThemeStore()
  return (
    <Button variant="secondary" size="sm" onClick={toggleTheme}>
      {theme === "light" ? "→ Тёмная" : "→ Светлая"}
    </Button>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-xs uppercase tracking-wide font-semibold text-label">{title}</h2>
      <div className="bg-elevated border border-default rounded-xl p-5 space-y-4">{children}</div>
    </section>
  )
}

function Row({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-wrap items-center gap-3">{children}</div>
}

export default function DesignSystemPreview() {
  // Form state demo
  const [text, setText] = useState("")
  const [num, setNum] = useState<number | null>(null)
  const [sel, setSel] = useState("")
  const [multi, setMulti] = useState<string[]>(["red", "blue"])
  const [textarea, setTextarea] = useState("")
  const [date, setDate] = useState<Date | null>(null)
  const [combo, setCombo] = useState<string | null>(null)
  const [files, setFiles] = useState<File[] | null>(null)

  // Overlay state demo
  const [modalOpen, setModalOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)

  // Tab state demo
  const [tabUnderline, setTabUnderline] = useState("overview")
  const [tabPills, setTabPills] = useState("monthly")
  const [tabVertical, setTabVertical] = useState("general")

  // Filter chip demo state
  const [filterA, setFilterA] = useState(true)
  const [filterB, setFilterB] = useState(false)

  const toast = useToast()

  const colorOptions = [
    { value: "red", label: "Красный" },
    { value: "blue", label: "Синий" },
    { value: "green", label: "Зелёный" },
    { value: "purple", label: "Фиолетовый" },
    { value: "yellow", label: "Жёлтый" },
  ]

  return (
    <div className="min-h-screen bg-page">
      {/* Sticky toolbar */}
      <header className="sticky top-0 z-20 bg-elevated/95 backdrop-blur border-b border-default">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-xl text-primary">
              <span className="font-serif italic">Wookiee</span>
              <span className="font-sans ml-2 text-muted">Design System v2</span>
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <Kbd>⌘</Kbd>
            <Kbd>K</Kbd>
            <span className="text-xs text-muted">— палитра команд</span>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Page header */}
        <PageHeader
          title="Design System v2"
          description="Каркас компонентов Wookiee Hub. Light + dark через [data-theme] атрибут, семантические токены, никаких dark:bg-stone-900 в JSX."
          icon={<Star className="w-7 h-7 text-accent" />}
          actions={
            <div className="flex gap-2">
              <Button variant="secondary" icon={Settings}>
                Настройки
              </Button>
              <Button variant="primary" icon={Plus}>
                Создать
              </Button>
            </div>
          }
        />

        {/* Breadcrumbs */}
        <Breadcrumbs
          items={[
            { label: "Hub", href: "/" },
            { label: "Дизайн", href: "/design-system-preview" },
            { label: "Preview" },
          ]}
        />

        {/* Primitives — Buttons */}
        <Section title="Buttons">
          <Row>
            <Button variant="primary" size="xs">Primary xs</Button>
            <Button variant="primary" size="sm">Primary sm</Button>
            <Button variant="primary" size="md">Primary md</Button>
            <Button variant="primary" size="lg">Primary lg</Button>
            <Button variant="primary" loading>Loading…</Button>
            <Button variant="primary" disabled>Disabled</Button>
          </Row>
          <Row>
            <Button variant="secondary">Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="danger" icon={Trash2}>Удалить</Button>
            <Button variant="danger-ghost" icon={Trash2}>Danger ghost</Button>
            <Button variant="success">Success</Button>
          </Row>
          <Row>
            <IconButton aria-label="search" icon={Search} />
            <IconButton aria-label="search secondary" icon={Search} variant="secondary" />
            <IconButton aria-label="search primary" icon={Search} variant="primary" />
            <IconButton aria-label="trash" icon={Trash2} variant="danger" />
            <IconButton aria-label="settings active" icon={Settings} active />
          </Row>
          <Row>
            <PermissionGate allowed={false}>
              <Button variant="primary">Без прав</Button>
            </PermissionGate>
            <span className="text-xs text-muted">← hover для tooltip</span>
          </Row>
        </Section>

        {/* Badges + Tags */}
        <Section title="Badges, Tags, Chips, Avatars">
          <Row>
            <Badge>default</Badge>
            <Badge variant="emerald">emerald</Badge>
            <Badge variant="blue">blue</Badge>
            <Badge variant="amber">amber</Badge>
            <Badge variant="red">red</Badge>
            <Badge variant="rose">rose</Badge>
            <Badge variant="purple">purple</Badge>
            <Badge variant="orange">orange</Badge>
            <Badge variant="teal">teal</Badge>
            <Badge variant="indigo">indigo</Badge>
            <Badge variant="emerald" dot>+12.4%</Badge>
            <Badge variant="rose" dot compact>−2.1%</Badge>
          </Row>
          <Row>
            <span className="text-[10px] uppercase tracking-wider text-label mr-2">StatusBadge (statusId)</span>
            <StatusBadge statusId={1} />
            <StatusBadge statusId={2} />
            <StatusBadge statusId={3} />
            <StatusBadge statusId={4} />
            <StatusBadge statusId={5} />
          </Row>
          <Row>
            <span className="text-[10px] uppercase tracking-wider text-label mr-2">LevelBadge (M/V/A/S)</span>
            <LevelBadge level="model" />
            <LevelBadge level="variation" />
            <LevelBadge level="artikul" />
            <LevelBadge level="sku" />
          </Row>
          <Row>
            <span className="text-[10px] uppercase tracking-wider text-label mr-2">PriorityBadge (P0..P3)</span>
            <PriorityBadge level="P0" />
            <PriorityBadge level="P1" />
            <PriorityBadge level="P2" />
            <PriorityBadge level="P3" />
          </Row>
          <Row>
            <span className="text-[10px] uppercase tracking-wider text-label mr-2">Tag</span>
            <Tag>gray</Tag>
            <Tag color="blue">blue</Tag>
            <Tag color="emerald">emerald</Tag>
            <Tag color="purple">purple</Tag>
            <Tag color="orange">orange</Tag>
            <Tag onRemove={() => null}>removable</Tag>
          </Row>
          <Row>
            <span className="text-[10px] uppercase tracking-wider text-label mr-2">Chip (removable)</span>
            <Chip>Vuki</Chip>
            <Chip onRemove={() => null}>Removable</Chip>
            <span className="text-[10px] uppercase tracking-wider text-label mx-2">FilterChip (toggle)</span>
            <FilterChip selected={filterA} onClick={() => setFilterA((v) => !v)}>Filter A</FilterChip>
            <FilterChip selected={filterB} onClick={() => setFilterB((v) => !v)}>Filter B</FilterChip>
          </Row>
          <Row>
            <Avatar name="Даня М" size="sm" color="stone" />
            <Avatar name="Лиля П" size="md" status="online" color="emerald" />
            <Avatar name="Алина К" size="lg" status="busy" color="blue" />
            <Avatar name="Витя Б" size="xl" color="purple" />
            <Avatar name="Маша С" size="md" color="rose" />
            <Avatar name="Костя Т" size="md" color="amber" />
            <AvatarGroup
              size="md"
              max={3}
              users={[
                { name: "Даня М", color: "stone" },
                { name: "Лиля П", color: "emerald" },
                { name: "Алина К", color: "blue" },
                { name: "Витя Б", color: "purple" },
                { name: "Маша С", color: "rose" },
              ]}
            />
          </Row>
          <Row>
            <ColorSwatch hex="#1C1917" label />
            <ColorSwatch hex="#7C3AED" label size={20} />
            <ColorSwatch hex="#16a34a" />
            <ColorSwatch hex="#d97706" size={24} />
            <ColorSwatch hex="#E11D48" size={32} label />
          </Row>
        </Section>

        {/* Progress + Ring + Tooltip + Skeleton */}
        <Section title="Progress, Ring, Tooltip, Skeleton">
          <Row>
            <div className="w-48 space-y-2">
              <ProgressBar value={30} color="stone" />
              <ProgressBar value={70} color="emerald" />
              <ProgressBar value={55} color="blue" />
              <ProgressBar value={92} color="amber" />
              <ProgressBar value={20} color="red" />
            </div>
            <Ring value={0.3} />
            <Ring value={0.7} />
            <Ring value={0.92} />
            <Ring value={70} inputScale="percent" size="md" label={<span>70%</span>} />
            <Tooltip text="Tooltip via text prop">
              <Badge variant="info">hover me</Badge>
            </Tooltip>
            <Tooltip content={<span>ReactNode <strong>content</strong></span>}>
              <Badge variant="purple">hover (node)</Badge>
            </Tooltip>
          </Row>
          <Row>
            <Skeleton className="h-10 w-32" />
            <Skeleton className="h-10 w-64" />
            <Skeleton className="h-10 w-20 rounded-full" />
          </Row>
        </Section>

        {/* Forms */}
        <Section title="Forms">
          <div className="grid md:grid-cols-2 gap-4">
            <TextField
              id="ds-text"
              label="Текст"
              value={text}
              onChange={setText}
              placeholder="Введите…"
              hint="Подсказка под полем"
              prefix={Search}
            />
            <NumberField
              id="ds-num"
              label="Число"
              value={num}
              onChange={setNum}
              suffix={<span className="text-muted text-xs">₽</span>}
            />
            <SelectField
              id="ds-sel"
              label="Один из"
              value={sel}
              onChange={setSel}
              options={colorOptions}
              placeholder="Выбери цвет"
            />
            <MultiSelectField
              id="ds-multi"
              label="Несколько"
              value={multi}
              onChange={setMulti}
              options={colorOptions}
            />
            <TextareaField
              id="ds-area"
              label="Текстовая область"
              value={textarea}
              onChange={setTextarea}
              maxLength={200}
              autoResize
            />
            <DatePicker
              id="ds-date"
              label="Дата"
              value={date}
              onChange={setDate}
            />
            <Combobox
              id="ds-combo"
              label="Комбобокс"
              value={combo}
              onChange={setCombo}
              options={colorOptions}
            />
            <FieldWrap id="ds-error" label="С ошибкой" error="Поле обязательно">
              <TextField id="ds-err-inner" value="" onChange={() => null} error="Поле обязательно" />
            </FieldWrap>
          </div>
          <FileUpload id="ds-file" label="Файлы" value={files} onChange={setFiles} multiple maxSize={5 * 1024 * 1024} />
        </Section>

        {/* Tabs */}
        <Section title="Tabs (underline / pills / vertical)">
          <Tabs
            variant="underline"
            value={tabUnderline}
            onChange={setTabUnderline}
            items={[
              { value: "overview", label: "Обзор" },
              { value: "details", label: "Детали", count: 5 },
              { value: "settings", label: "Настройки" },
            ]}
          />
          <Tabs
            variant="pills"
            value={tabPills}
            onChange={setTabPills}
            items={[
              { value: "daily", label: "День" },
              { value: "weekly", label: "Неделя" },
              { value: "monthly", label: "Месяц" },
            ]}
          />
          <div className="flex gap-6">
            <Tabs
              variant="vertical"
              value={tabVertical}
              onChange={setTabVertical}
              items={[
                { value: "general", label: "Общее" },
                { value: "profile", label: "Профиль" },
                { value: "billing", label: "Биллинг" },
              ]}
            />
            <div className="flex-1 bg-surface-muted rounded-lg p-4 text-sm text-secondary">
              Активная вкладка: <span className="text-primary font-medium">{tabVertical}</span>
            </div>
          </div>
        </Section>

        {/* Stepper */}
        <Section title="Stepper">
          <Stepper
            current={2}
            steps={[
              { label: "Создание" },
              { label: "Заполнение" },
              { label: "Проверка" },
              { label: "Запуск" },
            ]}
          />
        </Section>

        {/* Feedback */}
        <Section title="Alert / EmptyState / Toast">
          <div className="space-y-2">
            <Alert variant="default" title="Default" description="Информационное сообщение." />
            <Alert variant="success" title="Сохранено" description="Изменения применены." />
            <Alert variant="warning" title="Внимание" description="Проверь данные перед публикацией." />
            <Alert variant="danger" title="Ошибка" description="Не удалось загрузить файл." />
            <Alert variant="info" title="К сведению" description="Доступна новая версия." />
          </div>

          <div className="border border-default rounded-lg">
            <EmptyState
              icon={<Search className="w-10 h-10" />}
              title="Ничего не найдено"
              description="Попробуй изменить условия поиска."
              action={<Button variant="primary">Сбросить фильтры</Button>}
            />
          </div>

          <Row>
            <Button variant="secondary" onClick={() => toast.toast("Сохранено", { variant: "success" })}>
              Success toast
            </Button>
            <Button variant="secondary" onClick={() => toast.toast("Ошибка", { variant: "danger", description: "Подробности в консоли" })}>
              Danger toast
            </Button>
            <Button variant="secondary" onClick={() => toast.toast("Внимание", { variant: "warning" })}>
              Warning toast
            </Button>
          </Row>
        </Section>

        {/* Overlays */}
        <Section title="Overlays">
          <Row>
            <Button variant="secondary" onClick={() => setModalOpen(true)}>Modal</Button>
            <Button variant="secondary" onClick={() => setDrawerOpen(true)}>Drawer</Button>
            <Button variant="secondary" onClick={() => setPaletteOpen(true)}>
              Command palette <Kbd>⌘K</Kbd>
            </Button>

            <Popover
              trigger={<Button variant="secondary" icon={ChevronRight}>Popover</Button>}
              placement="bottom"
            >
              <div className="bg-elevated border border-default rounded-lg p-3 shadow-md w-56">
                <p className="text-sm text-secondary">Popover-контент. Закрывается при клике снаружи.</p>
              </div>
            </Popover>

            <DropdownMenu
              trigger={<Button variant="secondary">Dropdown</Button>}
              items={[
                { label: "Открыть", onClick: () => toast.toast("Открыто") },
                { label: "Поделиться", onClick: () => toast.toast("Поделено") },
                { label: "Удалить", danger: true, onClick: () => toast.toast("Удалено", { variant: "danger" }) },
              ]}
            />
          </Row>

          <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="Модальное окно" description="Esc или клик вне — закрывает." size="md">
            <p className="text-sm text-secondary">Контент модала. Закрывается клавишей Escape.</p>
            <div className="flex justify-end gap-2 mt-4">
              <Button variant="ghost" onClick={() => setModalOpen(false)}>Отмена</Button>
              <Button variant="primary" onClick={() => setModalOpen(false)}>Подтвердить</Button>
            </div>
          </Modal>

          <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title="Боковая панель" description="Slide-out справа." side="right" size="md">
            <p className="text-sm text-secondary">Drawer-контент. Можно положить форму, детали, что угодно.</p>
          </Drawer>

          <CommandPalette
            open={paletteOpen}
            onClose={() => setPaletteOpen(false)}
            commands={[
              { id: "home", label: "На главную", group: "Навигация", onSelect: () => toast.toast("→ /") },
              { id: "search", label: "Найти модель", group: "Действия", shortcut: "⌘F", onSelect: () => toast.toast("Поиск") },
              { id: "settings", label: "Настройки", group: "Действия", onSelect: () => toast.toast("Настройки") },
              { id: "logout", label: "Выйти", group: "Аккаунт", onSelect: () => toast.toast("Выход", { variant: "warning" }) },
            ]}
          />
        </Section>

        <div className="text-center text-xs text-muted py-8">
          Design System v2 · Wookiee Hub · 2026
        </div>
      </main>
    </div>
  )
}
