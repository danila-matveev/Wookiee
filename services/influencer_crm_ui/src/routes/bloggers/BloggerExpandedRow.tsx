import type { BloggerChannelOut, BloggerDetailOut } from '@/api/bloggers';
import { useBlogger } from '@/hooks/use-bloggers';
import { Avatar } from '@/ui/Avatar';
import { Badge, type BadgeProps } from '@/ui/Badge';
import { Skeleton } from '@/ui/Skeleton';

const statusTone: Record<BloggerDetailOut['status'], NonNullable<BadgeProps['tone']>> = {
  active: 'success',
  paused: 'warning',
  in_progress: 'info',
  new: 'secondary',
};

const statusLabel: Record<BloggerDetailOut['status'], string> = {
  active: 'Активный',
  paused: 'На паузе',
  in_progress: 'В работе',
  new: 'Новый',
};

export function BloggerExpandedRow({ id }: { id: number }) {
  const { data, isLoading, error } = useBlogger(id);

  if (isLoading) {
    return (
      <div className="p-6">
        <Skeleton className="h-24" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 text-sm text-danger">
        Не удалось загрузить блогера:{' '}
        {error instanceof Error ? error.message : 'неизвестная ошибка'}
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="grid grid-cols-[320px_1fr] gap-6 p-6">
      <ProfileCard blogger={data} />
      <ChannelsList channels={data.channels} totalIntegrations={data.integrations_count} />
    </div>
  );
}

function ProfileCard({ blogger }: { blogger: BloggerDetailOut }) {
  const displayName = blogger.real_name ?? blogger.display_handle;
  const meta: { label: string; value: string }[] = [];
  if (blogger.contact_phone) meta.push({ label: 'Телефон', value: blogger.contact_phone });
  if (blogger.contact_email) meta.push({ label: 'Email', value: blogger.contact_email });
  if (blogger.contact_tg) meta.push({ label: 'Telegram', value: blogger.contact_tg });
  if (blogger.notes) meta.push({ label: 'Заметки', value: blogger.notes });

  return (
    <div className="flex flex-col items-start gap-3 rounded-lg border border-border bg-card p-5 shadow-warm">
      <Avatar name={displayName} size="lg" />
      <div className="min-w-0">
        <div className="font-display text-lg font-semibold text-fg">{displayName}</div>
        <div className="text-sm text-muted-fg">@{blogger.display_handle}</div>
      </div>
      <Badge tone={statusTone[blogger.status]}>{statusLabel[blogger.status]}</Badge>
      {meta.length > 0 && (
        <dl className="mt-2 grid w-full grid-cols-[max-content_1fr] gap-x-3 gap-y-1.5 text-xs">
          {meta.map((m) => (
            <div key={m.label} className="contents">
              <dt className="text-muted-fg">{m.label}</dt>
              <dd className="text-fg break-words">{m.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}

function ChannelsList({
  channels,
  totalIntegrations,
}: {
  channels: BloggerChannelOut[];
  totalIntegrations: number;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-sm font-semibold uppercase tracking-wider text-muted-fg">
          Каналы
        </h3>
        <span className="text-xs text-muted-fg">Интеграций всего: {totalIntegrations}</span>
      </div>
      {channels.length === 0 ? (
        <div className="rounded-md border border-dashed border-border bg-card px-4 py-6 text-center text-sm text-muted-fg">
          Каналов пока нет.
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {channels.map((c) => (
            <li
              key={c.id}
              className="flex items-center justify-between rounded-md border border-border bg-card px-3 py-2 text-sm shadow-warm"
            >
              <div className="flex items-center gap-2">
                <Badge tone="info">{c.channel}</Badge>
                <span className="font-medium text-fg">@{c.handle}</span>
              </div>
              {c.url && (
                <a
                  href={c.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-primary hover:text-primary-hover"
                >
                  Открыть
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
