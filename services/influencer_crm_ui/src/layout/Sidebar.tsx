import {
  Activity,
  Calendar,
  FileText,
  Layers,
  type LucideIcon,
  Users,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { cn } from '@/lib/cn';

interface NavItem {
  to: string;
  icon: LucideIcon;
  label: string;
}

const items: NavItem[] = [
  { to: '/bloggers', icon: Users, label: 'Блогеры' },
  { to: '/integrations', icon: Layers, label: 'Интеграции' },
  { to: '/calendar', icon: Calendar, label: 'Календарь' },
  { to: '/briefs', icon: FileText, label: 'Брифы' },
  { to: '/ops', icon: Activity, label: 'Ops' },
];

export function Sidebar() {
  return (
    <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col gap-6 bg-gradient-to-b from-primary-light to-card px-4 py-6">
      <div className="flex items-center gap-3 px-2">
        <div className="flex size-9 items-center justify-center rounded-md bg-primary text-white font-display font-bold">
          W
        </div>
        <div className="font-display text-lg font-semibold text-fg">Wookiee CRM</div>
      </div>

      <nav aria-label="Главное меню" className="flex flex-col gap-1">
        {items.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                'flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive ? 'bg-primary text-white' : 'text-fg hover:bg-primary-light',
              )
            }
          >
            <Icon className="size-4" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

export default Sidebar;
