import { Fragment, type ReactNode, useState } from 'react';
import type { BloggerOut, BloggerStatus } from '@/api/bloggers';
import { Avatar } from '@/ui/Avatar';
import { Badge, type BadgeProps } from '@/ui/Badge';
import { BloggerExpandedRow } from './BloggerExpandedRow';

const statusTone: Record<BloggerStatus, NonNullable<BadgeProps['tone']>> = {
  active: 'success',
  paused: 'warning',
  in_progress: 'info',
  new: 'secondary',
};

const statusLabel: Record<BloggerStatus, string> = {
  active: 'Активный',
  paused: 'На паузе',
  in_progress: 'В работе',
  new: 'Новый',
};

interface Props {
  bloggers: BloggerOut[];
  onEdit?: (id: number) => void;
}

export function BloggersTable({ bloggers, onEdit }: Props) {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  return (
    <div className="bg-card border border-border-strong rounded-lg shadow-warm overflow-hidden">
      <table className="w-full">
        <caption className="sr-only">
          Список блогеров с их статусом и количеством интеграций
        </caption>
        <thead>
          <tr>
            <Th>Блогер</Th>
            <Th>Статус</Th>
            <Th>Каналы</Th>
            <Th className="text-right">Интеграций</Th>
          </tr>
        </thead>
        <tbody>
          {bloggers.map((b) => {
            const isExpanded = expandedId === b.id;
            const displayName = b.real_name ?? b.display_handle;
            return (
              <Fragment key={b.id}>
                <tr
                  className={`cursor-pointer transition-colors duration-150 ${
                    isExpanded ? 'bg-primary-light' : 'hover:bg-bg-warm'
                  }`}
                  onClick={() => setExpandedId(isExpanded ? null : b.id)}
                  aria-expanded={isExpanded}
                >
                  <td className="px-3.5 py-3">
                    <div className="flex items-center gap-3">
                      <Avatar name={displayName} />
                      <div className="min-w-0">
                        <div className="font-semibold text-sm">{displayName}</div>
                        <div className="text-xs text-muted-fg truncate">@{b.display_handle}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-3.5 py-3">
                    <Badge tone={statusTone[b.status]}>{statusLabel[b.status]}</Badge>
                  </td>
                  <td className="px-3.5 py-3 font-mono text-sm text-muted-fg">—</td>
                  <td className="px-3.5 py-3 font-mono text-sm text-right text-muted-fg">—</td>
                </tr>
                {isExpanded && (
                  <tr>
                    <td colSpan={4} className="bg-bg-warm p-0">
                      <BloggerExpandedRow id={b.id} onEdit={onEdit} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Th({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <th
      className={`bg-muted text-[11.5px] uppercase tracking-wider text-muted-fg font-semibold px-3.5 py-2.5 text-left ${className}`}
    >
      {children}
    </th>
  );
}
