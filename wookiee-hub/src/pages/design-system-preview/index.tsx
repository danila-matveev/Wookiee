import { Badge } from "@/components/ui/badge"
import { StatusBadge } from "@/components/ui/status-badge"
import { LevelBadge } from "@/components/ui/level-badge"
import { Tag } from "@/components/ui/tag"
import { Chip } from "@/components/ui/chip"
import { Avatar } from "@/components/ui/avatar"
import { AvatarGroup } from "@/components/ui/avatar-group"
import { ColorSwatch } from "@/components/ui/color-swatch"
import { Ring } from "@/components/ui/ring"
import { Tooltip, TooltipProvider, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip"
import { Skeleton } from "@/components/ui/skeleton"
import { Kbd } from "@/components/ui/kbd"
import { EmptyState } from "@/components/ui/empty-state"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useThemeStore } from "@/stores/theme"
import { Inbox } from "lucide-react"
import { PageHeader } from "@/components/layout/page-header"
import { useDocumentTitle } from "@/hooks/use-document-title"

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-12">
      <h2 className="text-sm font-medium uppercase tracking-wider text-muted-foreground mb-3">{title}</h2>
      <div className="flex flex-wrap items-center gap-3">{children}</div>
    </section>
  )
}

export function DesignSystemPreview() {
  useDocumentTitle("DS Preview")
  const { theme, toggleTheme } = useThemeStore()

  return (
    <TooltipProvider>
      <div className="max-w-5xl mx-auto px-6 py-10">
        <PageHeader
          kicker="DESIGN SYSTEM"
          title="Preview v2"
          description="Тестбед примитивов DS v2 — Wave 1 Foundation"
          actions={
            <Button onClick={toggleTheme} variant="outline">
              Тема: {theme === "dark" ? "тёмная" : "светлая"}
            </Button>
          }
        />

        <Section title="Badge variants">
          <Badge variant="emerald">emerald</Badge>
          <Badge variant="blue">blue</Badge>
          <Badge variant="amber">amber</Badge>
          <Badge variant="red">red</Badge>
          <Badge variant="purple">purple</Badge>
          <Badge variant="teal">teal</Badge>
          <Badge variant="gray">gray</Badge>
          <Badge variant="emerald" dot>with dot</Badge>
        </Section>

        <Section title="StatusBadge">
          <StatusBadge status="active" />
          <StatusBadge status="draft" />
          <StatusBadge status="review" />
          <StatusBadge status="archived" />
          <StatusBadge status="in_progress" />
          <StatusBadge status="blocked" />
        </Section>

        <Section title="LevelBadge">
          <LevelBadge level="model">Wendy</LevelBadge>
          <LevelBadge level="variation">Black/M</LevelBadge>
          <LevelBadge level="artikul">wendy-001</LevelBadge>
          <LevelBadge level="sku">SKU-123</LevelBadge>
        </Section>

        <Section title="Tag + Chip">
          <Tag>premium</Tag>
          <Tag>limited</Tag>
          <Chip onRemove={() => alert("removed")}>status=active</Chip>
          <Chip>brand=Wookiee</Chip>
        </Section>

        <Section title="Avatar">
          <Avatar name="Иван Петров" size="sm" />
          <Avatar name="Анна Сидорова" size="md" />
          <Avatar name="Елена Иванова" size="lg" />
          <AvatarGroup>
            <Avatar name="A B" />
            <Avatar name="C D" />
            <Avatar name="E F" />
          </AvatarGroup>
        </Section>

        <Section title="ColorSwatch">
          <ColorSwatch color="#FF0000" />
          <ColorSwatch color="#00FF00" />
          <ColorSwatch color="#0000FF" />
          <ColorSwatch color="#FFAA00" size="lg" />
        </Section>

        <Section title="Ring (progress)">
          <Ring value={25} />
          <Ring value={50} />
          <Ring value={75} />
          <Ring value={100} />
        </Section>

        <Section title="Tooltip">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="outline">Hover me</Button>
            </TooltipTrigger>
            <TooltipContent>Tooltip text</TooltipContent>
          </Tooltip>
        </Section>

        <Section title="Skeleton">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-8 w-16 rounded-full" />
        </Section>

        <Section title="Kbd">
          <Kbd>⌘</Kbd>
          <Kbd>K</Kbd>
          <Kbd keys={["⌘", "K"]} />
          <Kbd keys={["Shift", "Enter"]} />
        </Section>

        <Section title="Button variants">
          <Button>default</Button>
          <Button variant="destructive">destructive</Button>
          <Button variant="outline">outline</Button>
          <Button variant="secondary">secondary</Button>
          <Button variant="ghost">ghost</Button>
          <Button variant="link">link</Button>
          <Button variant="success">success</Button>
          <Button variant="danger-ghost">danger-ghost</Button>
        </Section>

        <Section title="Input">
          <Input placeholder="Type here..." className="max-w-xs" />
        </Section>

        <Section title="EmptyState">
          <div className="w-full ring-1 ring-border rounded-lg">
            <EmptyState
              icon={<Inbox className="size-12" />}
              title="Нет данных"
              description="Здесь будет список когда что-то появится"
              action={<Button variant="outline">Создать первый элемент</Button>}
            />
          </div>
        </Section>
      </div>
    </TooltipProvider>
  )
}
