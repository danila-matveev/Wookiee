import { Inbox, Plus, Search } from 'lucide-react';
import { useState } from 'react';
import { Avatar } from '@/ui/Avatar';
import { Badge } from '@/ui/Badge';
import { Button } from '@/ui/Button';
import { EmptyState } from '@/ui/EmptyState';
import { FilterPill } from '@/ui/FilterPill';
import { Input } from '@/ui/Input';
import { KpiCard } from '@/ui/KpiCard';
import { type PlatformChannel, PlatformPill } from '@/ui/PlatformPill';
import { Select } from '@/ui/Select';
import { Skeleton } from '@/ui/Skeleton';
import { Tabs } from '@/ui/Tabs';
import { Textarea } from '@/ui/Textarea';

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-border-strong bg-card p-6 shadow-warm">
      <h2 className="font-display text-lg font-semibold mb-4">{title}</h2>
      <div className="flex flex-wrap items-center gap-3">{children}</div>
    </section>
  );
}

const channels: PlatformChannel[] = ['instagram', 'tiktok', 'youtube', 'telegram', 'vk'];

export function UiCatalog() {
  const [active, setActive] = useState<'all' | 'mine' | 'flagged'>('all');

  return (
    <div className="min-h-dvh bg-bg p-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <header>
          <h1 className="font-display text-2xl font-bold">Wookiee CRM — UI Catalog</h1>
          <p className="text-sm text-muted-fg mt-1">
            Visual smoke test for design-system primitives. Dev-only route.
          </p>
        </header>

        <Section title="Buttons">
          <Button variant="primary">
            <Plus className="size-4" /> Primary
          </Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
          <Button variant="primary" loading>
            Loading
          </Button>
          <Button variant="primary" disabled>
            Disabled
          </Button>
        </Section>

        <Section title="Badges">
          <Badge tone="success">success</Badge>
          <Badge tone="warning">warning</Badge>
          <Badge tone="info">info</Badge>
          <Badge tone="orange">orange</Badge>
          <Badge tone="pink">pink</Badge>
          <Badge tone="secondary">secondary</Badge>
          <Badge tone="danger">danger</Badge>
        </Section>

        <Section title="Avatars">
          <Avatar name="Anna Petrova" size="xs" />
          <Avatar name="Boris Sokolov" size="sm" />
          <Avatar name="Catherine Volkov" size="md" />
          <Avatar name="Dmitry Ivanov" size="lg" />
          <Avatar name="elena.k" size="md" />
          <Avatar name="" size="md" />
        </Section>

        <Section title="Inputs / Select / Textarea">
          <div className="grid w-full grid-cols-1 gap-3 md:grid-cols-3">
            <Input placeholder="Search bloggers" />
            <Select defaultValue="">
              <option value="" disabled>
                Select status
              </option>
              <option value="active">Active</option>
              <option value="paused">Paused</option>
            </Select>
            <Textarea placeholder="Notes…" />
          </div>
        </Section>

        <Section title="Filter Pills">
          <FilterPill active={active === 'all'} onClick={() => setActive('all')}>
            All
          </FilterPill>
          <FilterPill active={active === 'mine'} onClick={() => setActive('mine')}>
            Mine
          </FilterPill>
          <FilterPill active={active === 'flagged'} onClick={() => setActive('flagged')}>
            Flagged
          </FilterPill>
          <FilterPill solid>
            <Search className="size-3.5" /> Solid action
          </FilterPill>
        </Section>

        <Section title="Platform Pills">
          {channels.map((c) => (
            <PlatformPill key={c} channel={c} />
          ))}
        </Section>

        <Section title="Skeletons">
          <div className="flex w-full flex-col gap-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-20 w-full" />
          </div>
        </Section>

        <Section title="KPI Cards">
          <div className="grid w-full grid-cols-1 gap-4 md:grid-cols-4">
            <KpiCard
              title="Active bloggers"
              value="124"
              change={{ label: '+12% MoM', direction: 'pos' }}
            />
            <KpiCard
              title="Pending payouts"
              value="₽842K"
              change={{ label: '-3.4% WoW', direction: 'neg' }}
              accent="pink"
            />
            <KpiCard
              title="Posts this month"
              value="38"
              change={{ label: '0.0%', direction: 'neu' }}
              accent="info"
            />
            <KpiCard title="ROI" value="2.4x" accent="success" hint="Last 30 days" />
          </div>
        </Section>

        <Section title="Tabs">
          <div className="w-full">
            <Tabs
              tabs={[
                {
                  label: 'Overview',
                  count: 24,
                  content: <div className="text-sm text-muted-fg">Overview content</div>,
                },
                {
                  label: 'Activity',
                  count: 7,
                  content: <div className="text-sm text-muted-fg">Activity content</div>,
                },
                {
                  label: 'Files',
                  content: <div className="text-sm text-muted-fg">Files content</div>,
                },
              ]}
            />
          </div>
        </Section>

        <Section title="Empty State">
          <div className="w-full">
            <EmptyState
              icon={<Inbox className="size-10" />}
              title="No bloggers yet"
              description="Add your first blogger to start tracking integrations and payouts."
              action={
                <Button variant="primary">
                  <Plus className="size-4" /> Add blogger
                </Button>
              }
            />
          </div>
        </Section>
      </div>
    </div>
  );
}

export default UiCatalog;
