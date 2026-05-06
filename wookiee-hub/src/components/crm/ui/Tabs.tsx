import { type ReactNode, useId, useState } from 'react';
import { cn } from '@/lib/utils';

export interface TabItem {
  label: string;
  content: ReactNode;
  count?: number;
}

interface TabsProps {
  tabs: TabItem[];
  defaultIndex?: number;
  className?: string;
}

export function Tabs({ tabs, defaultIndex = 0, className }: TabsProps) {
  const [active, setActive] = useState(defaultIndex);
  const baseId = useId();

  return (
    <div className={cn('flex flex-col gap-4', className)}>
      <div role="tablist" className="flex gap-1 border-b border-border px-1">
        {tabs.map((t, i) => {
          const isActive = i === active;
          const tabId = `${baseId}-tab-${t.label}`;
          const panelId = `${baseId}-panel-${t.label}`;
          return (
            <button
              key={t.label}
              id={tabId}
              role="tab"
              type="button"
              aria-selected={isActive}
              aria-controls={panelId}
              tabIndex={isActive ? 0 : -1}
              onClick={() => setActive(i)}
              className={cn(
                'inline-flex items-center gap-1.5 px-3.5 py-2.5 text-sm font-medium -mb-px',
                'border-b-2 transition-colors duration-200 cursor-pointer',
                isActive
                  ? 'text-primary border-primary'
                  : 'text-muted-fg border-transparent hover:text-fg',
              )}
            >
              {t.label}
              {typeof t.count === 'number' && (
                <span
                  className={cn(
                    'rounded-full px-1.5 py-px text-[11px] font-mono font-semibold',
                    isActive ? 'bg-primary-light text-primary-hover' : 'bg-muted text-muted-fg',
                  )}
                >
                  {t.count}
                </span>
              )}
            </button>
          );
        })}
      </div>
      {tabs.map((t, i) => (
        <div
          key={t.label}
          id={`${baseId}-panel-${t.label}`}
          role="tabpanel"
          aria-labelledby={`${baseId}-tab-${t.label}`}
          hidden={i !== active}
        >
          {i === active && t.content}
        </div>
      ))}
    </div>
  );
}

export type { TabsProps };
