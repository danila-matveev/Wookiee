import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area, PieChart, Pie, Cell,
  RadialBarChart, RadialBar, FunnelChart, Funnel, LabelList, ComposedChart,
  XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, Legend, ResponsiveContainer
} from 'recharts';
import {
  Search, Plus, X, Check, ChevronDown, ChevronRight, ChevronLeft, ChevronUp,
  MoreHorizontal, Edit3, Trash2, Copy, Save, Archive, Download, Upload,
  Settings, User, Bell, Calendar, Mail, Filter, Sliders,
  Info, AlertCircle, AlertTriangle, CheckCircle, XCircle, HelpCircle,
  ArrowRight, ArrowLeft, ArrowUp, ArrowDown, ArrowUpRight, ExternalLink,
  Eye, EyeOff, Lock, Unlock, Star, Heart, Bookmark, Sun, Moon,
  Package, Layers, Palette, Building2, Briefcase, FolderTree, BookOpen,
  Hash, FileText, BarChart3, Box, Zap, Sparkles, Clock, GripVertical,
  TrendingUp, TrendingDown, Loader2, RotateCcw, Command, Inbox,
  ChevronsUpDown, FolderOpen, Folder, File, Tag as TagIcon, Type
} from 'lucide-react';

/* =========================================================
   WOOKIEE HUB · DESIGN SYSTEM v2 — FOUNDATION
   Разделы: Foundation · Atoms · Forms · Data · Charts ·
            Layout · Overlays · Feedback
   ⇄ Patterns (Kanban, Calendar, Activity, Comments,
     Notifications, Inbox, Theme demo) — отдельный файл.
   ========================================================= */

// =========================================================
// THEME — light/dark через class strategy
// =========================================================

const ThemeContext = React.createContext({ theme: 'light', toggle: () => {} });

function useTheme() { return React.useContext(ThemeContext); }

// Цвета для рекартов / SVG где нельзя tailwind dark:
// Палитра взята из rnp_dashboard — спокойная, узнаваемая, держит характер DS
const chartTokens = {
  light: {
    grid: '#F5F5F4', axis: '#A8A29E', tooltip_bg: '#FFFFFF', tooltip_border: '#E7E5E4',
    primary: '#1C1917', secondary: '#44403C', tertiary: '#A8A29E',
    pos: '#059669', neg: '#E11D48', warn: '#D97706', info: '#2563EB',
    // Полноцветная палитра для multi-series — 8 цветов в едином тоне (saturation ~70%)
    palette: {
      ink:    '#1C1917', // основной — тёмный
      blue:   '#2563EB', // канал 1
      purple: '#7C3AED', // канал 2
      teal:   '#0D9488', // канал 3
      emerald:'#059669', // позитив / выручка
      amber:  '#D97706', // канал 4 / комиссии
      rose:   '#E11D48', // негатив / возвраты
      indigo: '#4F46E5', // канал 5
    },
    // Контекстные миксы для конкретных типов отчётов
    pnl: { revenue: '#1C1917', margin: '#059669', logistics: '#0D9488', commission: '#D97706', marketing: '#7C3AED' },
    channels: { internal: '#1C1917', yandex: '#2563EB', vk: '#7C3AED', seedVk: '#0D9488', seedAg: '#D97706', bloggers: '#E11D48' },
  },
  dark: {
    grid: '#292524', axis: '#78716C', tooltip_bg: '#1C1917', tooltip_border: '#292524',
    primary: '#FAFAF9', secondary: '#D6D3D1', tertiary: '#78716C',
    pos: '#34D399', neg: '#FB7185', warn: '#FBBF24', info: '#60A5FA',
    palette: {
      ink:    '#FAFAF9',
      blue:   '#60A5FA',
      purple: '#A78BFA',
      teal:   '#5EEAD4',
      emerald:'#34D399',
      amber:  '#FBBF24',
      rose:   '#FB7185',
      indigo: '#818CF8',
    },
    pnl: { revenue: '#FAFAF9', margin: '#34D399', logistics: '#5EEAD4', commission: '#FBBF24', marketing: '#A78BFA' },
    channels: { internal: '#FAFAF9', yandex: '#60A5FA', vk: '#A78BFA', seedVk: '#5EEAD4', seedAg: '#FBBF24', bloggers: '#FB7185' },
  },
};

// =========================================================
// MOCK DATA
// =========================================================

const lineData = [
  { m: 'Янв', a: 12, b: 8, c: 15 }, { m: 'Фев', a: 19, b: 12, c: 18 },
  { m: 'Мар', a: 15, b: 10, c: 22 }, { m: 'Апр', a: 27, b: 18, c: 26 },
  { m: 'Май', a: 32, b: 20, c: 31 }, { m: 'Июн', a: 28, b: 24, c: 35 },
  { m: 'Июл', a: 38, b: 28, c: 39 }, { m: 'Авг', a: 42, b: 30, c: 44 },
];
const barData = [
  { name: 'Vuki', val: 142, prev: 110 }, { name: 'Vivi', val: 98, prev: 120 },
  { name: 'Vesta', val: 76, prev: 88 }, { name: 'Vera', val: 64, prev: 52 },
  { name: 'Vita', val: 48, prev: 60 }, { name: 'Volna', val: 32, prev: 28 },
];
const stackedData = [
  { m: 'Янв', wb: 4.2, ozon: 1.8, sayt: 0.9 },
  { m: 'Фев', wb: 5.1, ozon: 2.4, sayt: 1.1 },
  { m: 'Мар', wb: 4.8, ozon: 2.7, sayt: 1.4 },
  { m: 'Апр', wb: 6.2, ozon: 3.1, sayt: 1.6 },
  { m: 'Май', wb: 7.4, ozon: 3.8, sayt: 1.9 },
  { m: 'Июн', wb: 6.9, ozon: 4.2, sayt: 2.1 },
];
// P&L: 5 серий — выручка / маржа / логистика / комиссии / маркетинг
const pnlData = [
  { m: 'Янв', revenue: 4.82, margin: 1.35, logistics: 0.43, commission: 1.06, marketing: 0.62 },
  { m: 'Фев', revenue: 5.61, margin: 1.62, logistics: 0.51, commission: 1.23, marketing: 0.71 },
  { m: 'Мар', revenue: 5.18, margin: 1.41, logistics: 0.47, commission: 1.14, marketing: 0.84 },
  { m: 'Апр', revenue: 6.74, margin: 2.02, logistics: 0.61, commission: 1.48, marketing: 0.92 },
  { m: 'Май', revenue: 7.92, margin: 2.51, logistics: 0.71, commission: 1.74, marketing: 1.08 },
  { m: 'Июн', revenue: 7.34, margin: 2.18, logistics: 0.66, commission: 1.61, marketing: 0.98 },
  { m: 'Июл', revenue: 8.42, margin: 2.69, logistics: 0.76, commission: 1.85, marketing: 1.21 },
  { m: 'Авг', revenue: 9.12, margin: 3.02, logistics: 0.82, commission: 2.01, marketing: 1.32 },
];
// Маркетинг по каналам — 6 каналов, stacked bar
const channelsData = [
  { m: 'Янв', internal: 280, yandex: 145, vk: 92,  seedVk: 48, seedAg: 32, bloggers: 25 },
  { m: 'Фев', internal: 312, yandex: 168, vk: 108, seedVk: 56, seedAg: 38, bloggers: 28 },
  { m: 'Мар', internal: 295, yandex: 182, vk: 124, seedVk: 64, seedAg: 41, bloggers: 84 },
  { m: 'Апр', internal: 348, yandex: 201, vk: 142, seedVk: 71, seedAg: 48, bloggers: 112 },
  { m: 'Май', internal: 412, yandex: 234, vk: 168, seedVk: 89, seedAg: 56, bloggers: 128 },
  { m: 'Июн', internal: 392, yandex: 218, vk: 156, seedVk: 78, seedAg: 52, bloggers: 96 },
];
// Combo data — выручка + маржа% (одна линия, одна полоса)
const comboData = pnlData.map(d => ({ ...d, marginPct: (d.margin / d.revenue * 100).toFixed(1) * 1 }));
const donutData = [
  { name: 'WB', value: 64 }, { name: 'Ozon', value: 22 },
  { name: 'Сайт', value: 11 }, { name: 'Lamoda', value: 3 },
];
const funnelData = [
  { name: 'Просмотры', value: 18420 }, { name: 'В корзину', value: 3210 },
  { name: 'Оформление', value: 980 }, { name: 'Оплачено', value: 642 },
];
const heatmapData = (() => {
  const days = []; const start = new Date(2026, 0, 1);
  for (let i = 0; i < 168; i++) {
    const d = new Date(start); d.setDate(d.getDate() + i);
    days.push({ date: d, value: Math.floor(Math.random() * 12) });
  }
  return days;
})();
const tableRows = [
  { id: 1, sku: 'VUK-BLK-S', model: 'Vuki', color: 'Чёрный', size: 'S', status: 1, stock: 142, price: 2890 },
  { id: 2, sku: 'VUK-BLK-M', model: 'Vuki', color: 'Чёрный', size: 'M', status: 1, stock: 98, price: 2890 },
  { id: 3, sku: 'VUK-BLK-L', model: 'Vuki', color: 'Чёрный', size: 'L', status: 3, stock: 12, price: 2890 },
  { id: 4, sku: 'VIV-BEI-S', model: 'Vivi', color: 'Бежевый', size: 'S', status: 1, stock: 56, price: 3190 },
  { id: 5, sku: 'VIV-BEI-M', model: 'Vivi', color: 'Бежевый', size: 'M', status: 2, stock: 0, price: 3190 },
  { id: 6, sku: 'VES-PNK-S', model: 'Vesta', color: 'Розовый', size: 'S', status: 4, stock: 0, price: 2590 },
  { id: 7, sku: 'VES-PNK-M', model: 'Vesta', color: 'Розовый', size: 'M', status: 5, stock: 0, price: 2590 },
];

const STATUS_MAP = {
  1: { label: 'В продаже', color: 'emerald' },
  2: { label: 'Запуск', color: 'blue' },
  3: { label: 'Выводим', color: 'amber' },
  4: { label: 'Не выводится', color: 'red' },
  5: { label: 'Архив', color: 'gray' },
};

// =========================================================
// PRIMITIVE HELPERS
// =========================================================

const cx = (...c) => c.filter(Boolean).join(' ');

// Surface — карточка/секция. Адаптивные tailwind classes
const surface = 'bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800';
const surfaceMuted = 'bg-stone-50/60 dark:bg-stone-900/40';
const textP = 'text-stone-900 dark:text-stone-50';
const textS = 'text-stone-700 dark:text-stone-300';
const textM = 'text-stone-500 dark:text-stone-400';
const textL = 'text-stone-400 dark:text-stone-500';
const borderD = 'border-stone-200 dark:border-stone-800';
const hoverRow = 'hover:bg-stone-50/60 dark:hover:bg-stone-800/40';
const hoverBtn = 'hover:bg-stone-100 dark:hover:bg-stone-800';

// =========================================================
// ATOMS
// =========================================================

function Button({ variant = 'primary', size = 'md', icon: Icon, children, disabled, ...props }) {
  const sizes = {
    xs: 'px-2 py-1 text-xs gap-1',
    sm: 'px-2.5 py-1 text-xs gap-1.5',
    md: 'px-3 py-1.5 text-sm gap-1.5',
    lg: 'px-4 py-2 text-sm gap-2',
  };
  const variants = {
    primary: 'bg-stone-900 dark:bg-stone-50 text-white dark:text-stone-900 hover:bg-stone-800 dark:hover:bg-stone-200',
    secondary: 'border border-stone-200 dark:border-stone-700 text-stone-700 dark:text-stone-200 hover:bg-stone-50 dark:hover:bg-stone-800 bg-white dark:bg-stone-900',
    ghost: 'text-stone-700 dark:text-stone-300 hover:bg-stone-100 dark:hover:bg-stone-800',
    danger: 'bg-rose-600 text-white hover:bg-rose-700',
    'danger-ghost': 'text-rose-700 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40',
    success: 'bg-emerald-600 text-white hover:bg-emerald-700',
  };
  const iconSizes = { xs: 'w-3 h-3', sm: 'w-3 h-3', md: 'w-3.5 h-3.5', lg: 'w-4 h-4' };
  return (
    <button disabled={disabled} {...props}
      className={cx('inline-flex items-center font-medium rounded-md transition-colors',
        sizes[size], variants[variant], disabled && 'opacity-50 cursor-not-allowed')}>
      {Icon && <Icon className={iconSizes[size]} />}
      {children}
    </button>
  );
}

function IconButton({ icon: Icon, onClick, danger, active, title }) {
  return (
    <button onClick={onClick} title={title}
      className={cx('p-1.5 rounded-md transition-colors',
        active ? 'bg-stone-900 text-white dark:bg-stone-50 dark:text-stone-900'
        : danger ? 'text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40'
        : cx(textS, hoverBtn))}>
      <Icon className="w-4 h-4" />
    </button>
  );
}

function Input({ icon: Icon, error, prefix, suffix, className, ...props }) {
  return (
    <div className="relative w-full">
      {Icon && <Icon className={cx('w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2', textL)} />}
      {prefix && <span className={cx('absolute left-2.5 top-1/2 -translate-y-1/2 text-sm', textL)}>{prefix}</span>}
      <input {...props}
        className={cx(
          'w-full text-sm rounded-md outline-none transition-colors',
          'bg-white dark:bg-stone-900',
          'border', error ? 'border-rose-400 focus:border-rose-500'
            : 'border-stone-200 dark:border-stone-700 focus:border-stone-900 dark:focus:border-stone-300 focus:ring-1 focus:ring-stone-900 dark:focus:ring-stone-300',
          textP, 'placeholder:text-stone-400 dark:placeholder:text-stone-500',
          Icon || prefix ? 'pl-8' : 'pl-2.5',
          suffix ? 'pr-8' : 'pr-2.5', 'py-1.5', className
        )} />
      {suffix && <span className={cx('absolute right-2.5 top-1/2 -translate-y-1/2 text-sm', textL)}>{suffix}</span>}
    </div>
  );
}

function Checkbox({ checked, onChange, label, indeterminate }) {
  const ref = useRef(null);
  useEffect(() => { if (ref.current) ref.current.indeterminate = !!indeterminate; }, [indeterminate]);
  return (
    <label className={cx('inline-flex items-center gap-2 cursor-pointer text-sm', textS)}>
      <input ref={ref} type="checkbox" checked={!!checked} onChange={(e) => onChange?.(e.target.checked)}
        className="w-3.5 h-3.5 rounded accent-stone-900 dark:accent-stone-50" />
      {label && <span>{label}</span>}
    </label>
  );
}

function Radio({ checked, onChange, label }) {
  return (
    <label className={cx('inline-flex items-center gap-2 cursor-pointer text-sm', textS)}>
      <input type="radio" checked={!!checked} onChange={() => onChange?.()}
        className="w-3.5 h-3.5 accent-stone-900 dark:accent-stone-50" />
      {label && <span>{label}</span>}
    </label>
  );
}

function Toggle({ on, onChange, label, disabled }) {
  return (
    <label className={cx('inline-flex items-center gap-2 cursor-pointer select-none', disabled && 'opacity-50')}>
      <button type="button" disabled={disabled} onClick={() => onChange?.(!on)}
        className={cx('relative w-9 h-5 rounded-full transition-colors',
          on ? 'bg-stone-900 dark:bg-stone-50' : 'bg-stone-200 dark:bg-stone-700')}>
        <span className={cx('absolute top-0.5 w-4 h-4 rounded-full transition-all',
          on ? 'left-4 bg-white dark:bg-stone-900' : 'left-0.5 bg-white')} />
      </button>
      {label && <span className={cx('text-sm', textS)}>{label}</span>}
    </label>
  );
}

function Slider({ value, onChange, min = 0, max = 100, suffix = '' }) {
  return (
    <div className="flex items-center gap-3 w-full">
      <input type="range" min={min} max={max} value={value} onChange={(e) => onChange?.(+e.target.value)}
        className="flex-1 accent-stone-900 dark:accent-stone-50" />
      <span className={cx('text-sm tabular-nums w-12 text-right', textS)}>{value}{suffix}</span>
    </div>
  );
}

function Badge({ variant = 'gray', children, dot, icon: Icon, compact }) {
  const variants = {
    emerald: 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 ring-emerald-600/20 dark:ring-emerald-500/30',
    blue: 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 ring-blue-600/20 dark:ring-blue-500/30',
    amber: 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 ring-amber-600/20 dark:ring-amber-500/30',
    red: 'bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 ring-red-600/20 dark:ring-red-500/30',
    purple: 'bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 ring-purple-600/20 dark:ring-purple-500/30',
    orange: 'bg-orange-50 dark:bg-orange-950/40 text-orange-700 dark:text-orange-300 ring-orange-600/20 dark:ring-orange-500/30',
    gray: 'bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-300 ring-stone-500/20 dark:ring-stone-600/40',
  };
  const dots = { emerald: 'bg-emerald-500', blue: 'bg-blue-500', amber: 'bg-amber-500', red: 'bg-red-500', purple: 'bg-purple-500', orange: 'bg-orange-500', gray: 'bg-stone-400' };
  return (
    <span className={cx('inline-flex items-center gap-1.5 rounded-md ring-1 ring-inset font-medium',
      compact ? 'px-1.5 py-0.5 text-[11px]' : 'px-2 py-0.5 text-xs', variants[variant])}>
      {dot && <span className={cx('w-1.5 h-1.5 rounded-full', dots[variant])} />}
      {Icon && <Icon className="w-3 h-3" />}
      {children}
    </span>
  );
}

function StatusBadge({ statusId, compact }) {
  const s = STATUS_MAP[statusId];
  if (!s) return null;
  return <Badge variant={s.color} dot compact={compact}>{s.label}</Badge>;
}

function LevelBadge({ level }) {
  const map = {
    model: { c: 'blue', l: 'M' }, variation: { c: 'purple', l: 'V' },
    artikul: { c: 'orange', l: 'A' }, sku: { c: 'emerald', l: 'S' },
  };
  const m = map[level]; if (!m) return null;
  return <Badge variant={m.c} compact>{m.l}</Badge>;
}

function Chip({ children, onRemove, color = 'gray' }) {
  return (
    <span className={cx('inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs',
      'bg-stone-100 dark:bg-stone-800', textS)}>
      {children}
      {onRemove && (
        <button onClick={onRemove} className={cx('rounded p-0.5', hoverBtn)}>
          <X className="w-3 h-3" />
        </button>
      )}
    </span>
  );
}

function Avatar({ initials, color = 'stone', size = 'md', src, status }) {
  const sizes = { xs: 'w-5 h-5 text-[9px]', sm: 'w-6 h-6 text-[10px]', md: 'w-8 h-8 text-xs', lg: 'w-10 h-10 text-sm' };
  const colors = {
    stone: 'bg-gradient-to-br from-stone-700 to-stone-900 dark:from-stone-200 dark:to-stone-400 text-white dark:text-stone-900',
    emerald: 'bg-gradient-to-br from-emerald-500 to-emerald-700 text-white',
    blue: 'bg-gradient-to-br from-blue-500 to-blue-700 text-white',
    amber: 'bg-gradient-to-br from-amber-500 to-amber-700 text-white',
    purple: 'bg-gradient-to-br from-purple-500 to-purple-700 text-white',
    rose: 'bg-gradient-to-br from-rose-500 to-rose-700 text-white',
  };
  return (
    <div className="relative inline-block shrink-0">
      <div className={cx('rounded-full flex items-center justify-center font-medium', sizes[size], colors[color])}>
        {src ? <img src={src} className="w-full h-full rounded-full object-cover" alt="" /> : initials}
      </div>
      {status && <span className={cx('absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full ring-2 ring-white dark:ring-stone-900',
        status === 'online' ? 'bg-emerald-500' : status === 'busy' ? 'bg-amber-500' : 'bg-stone-400')} />}
    </div>
  );
}

function AvatarGroup({ users, max = 4, size = 'md' }) {
  const visible = users.slice(0, max); const rest = users.length - max;
  const sizes = { sm: '-ml-1.5', md: '-ml-2', lg: '-ml-2.5' };
  return (
    <div className="flex items-center">
      {visible.map((u, i) => (
        <div key={i} className={cx(i > 0 && sizes[size], 'ring-2 ring-white dark:ring-stone-900 rounded-full')}>
          <Avatar {...u} size={size} />
        </div>
      ))}
      {rest > 0 && (
        <div className={cx(sizes[size], 'ring-2 ring-white dark:ring-stone-900 rounded-full',
          'bg-stone-100 dark:bg-stone-800', textS, 'flex items-center justify-center font-medium',
          size === 'sm' ? 'w-6 h-6 text-[10px]' : size === 'lg' ? 'w-10 h-10 text-sm' : 'w-8 h-8 text-xs')}>
          +{rest}
        </div>
      )}
    </div>
  );
}

function ColorSwatch({ hex, size = 16, label }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="rounded ring-1 ring-stone-200 dark:ring-stone-700 inline-block"
        style={{ width: size, height: size, background: hex }} />
      {label && <span className={cx('text-xs font-mono', textM)}>{label}</span>}
    </span>
  );
}

function ProgressBar({ value, color = 'stone', label, compact }) {
  const colors = {
    stone: 'bg-stone-900 dark:bg-stone-50',
    emerald: 'bg-emerald-500', blue: 'bg-blue-500',
    amber: 'bg-amber-500', red: 'bg-rose-500',
  };
  return (
    <div className="w-full">
      {label && <div className="flex justify-between mb-1">
        <span className={cx('text-xs', textS)}>{label}</span>
        <span className={cx('text-xs tabular-nums', textM)}>{value}%</span>
      </div>}
      <div className={cx('w-full rounded-full bg-stone-100 dark:bg-stone-800 overflow-hidden', compact ? 'h-1' : 'h-1.5')}>
        <div className={cx('h-full transition-all', colors[color])} style={{ width: `${Math.min(100, value)}%` }} />
      </div>
    </div>
  );
}

function Ring({ value, size = 32, color }) {
  const c = color || (value >= 0.85 ? '#059669' : value >= 0.6 ? '#2563EB' : value >= 0.4 ? '#D97706' : '#E11D48');
  const r = (size - 4) / 2; const C = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} className="-rotate-90">
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="currentColor" strokeWidth="2" className="text-stone-200 dark:text-stone-800" />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={c} strokeWidth="2"
        strokeDasharray={C} strokeDashoffset={C * (1 - value)} strokeLinecap="round" />
    </svg>
  );
}

function Tooltip({ text, position = 'top', children }) {
  const [show, setShow] = useState(false);
  const pos = {
    top: 'bottom-full mb-1.5 left-1/2 -translate-x-1/2',
    bottom: 'top-full mt-1.5 left-1/2 -translate-x-1/2',
  };
  return (
    <span className="relative inline-block" onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <span className={cx('absolute z-50 whitespace-nowrap px-2 py-1 text-[11px] rounded shadow-sm',
          'bg-stone-900 dark:bg-stone-100 text-white dark:text-stone-900', pos[position])}>
          {text}
        </span>
      )}
    </span>
  );
}

function Skeleton({ className = 'h-4 w-32' }) {
  return <div className={cx('rounded bg-stone-200 dark:bg-stone-800 animate-pulse', className)} />;
}

function Kbd({ children }) {
  return (
    <kbd className={cx('inline-flex items-center px-1.5 py-0.5 text-[10px] font-mono rounded border',
      'border-stone-200 dark:border-stone-700 bg-stone-50 dark:bg-stone-800', textS)}>
      {children}
    </kbd>
  );
}

function Tag({ children, color = 'gray', icon: Icon, onClick }) {
  return (
    <span onClick={onClick}
      className={cx('inline-flex items-center gap-1 px-1.5 py-0.5 text-[11px] rounded font-medium',
        onClick && 'cursor-pointer',
        color === 'gray' ? cx('bg-stone-100 dark:bg-stone-800', textS) :
        color === 'blue' ? 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300' :
        color === 'emerald' ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300' :
        cx('bg-stone-100 dark:bg-stone-800', textS))}>
      {Icon && <Icon className="w-2.5 h-2.5" />}
      {children}
    </span>
  );
}

// =========================================================
// FORMS — fields
// =========================================================

function FieldWrap({ label, level, hint, children, error }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className={cx('text-[11px] uppercase tracking-wider font-medium', textM)}>{label}</span>
        {level && <LevelBadge level={level} />}
      </div>
      {children}
      {hint && <div className={cx('text-[10px]', textL)}>{hint}</div>}
      {error && <div className="text-[10px] text-rose-600 dark:text-rose-400">{error}</div>}
    </div>
  );
}

function TextField({ label, level, value, onChange, mono, hint, error, ...props }) {
  return (
    <FieldWrap label={label} level={level} hint={hint} error={error}>
      <Input value={value || ''} onChange={(e) => onChange?.(e.target.value)}
        className={mono ? 'font-mono text-xs' : ''} {...props} />
    </FieldWrap>
  );
}

function NumberField({ label, level, value, onChange, suffix, hint }) {
  return (
    <FieldWrap label={label} level={level} hint={hint}>
      <Input type="number" value={value ?? ''} onChange={(e) => onChange?.(+e.target.value)} suffix={suffix} />
    </FieldWrap>
  );
}

function SelectField({ label, level, value, onChange, options = [], placeholder = 'Выберите…' }) {
  return (
    <FieldWrap label={label} level={level}>
      <div className="relative">
        <select value={value ?? ''} onChange={(e) => onChange?.(e.target.value)}
          className={cx('w-full text-sm rounded-md outline-none transition-colors appearance-none',
            'bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-700',
            'focus:border-stone-900 dark:focus:border-stone-300',
            textP, 'pl-2.5 pr-8 py-1.5')}>
          <option value="">{placeholder}</option>
          {options.map(o => <option key={o.id ?? o.value} value={o.id ?? o.value}>{o.nazvanie ?? o.label}</option>)}
        </select>
        <ChevronDown className={cx('w-3.5 h-3.5 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none', textL)} />
      </div>
    </FieldWrap>
  );
}

function MultiSelectField({ label, level, value = [], onChange, options = [] }) {
  const toggle = (v) => onChange?.(value.includes(v) ? value.filter(x => x !== v) : [...value, v]);
  return (
    <FieldWrap label={label} level={level}>
      <div className="flex flex-wrap gap-1.5">
        {options.map(o => {
          const active = value.includes(o.value ?? o);
          return (
            <button key={o.value ?? o} onClick={() => toggle(o.value ?? o)}
              className={cx('px-2.5 py-1 text-xs rounded-md transition-colors',
                active ? 'bg-stone-900 text-white dark:bg-stone-50 dark:text-stone-900'
                : cx('bg-stone-100 dark:bg-stone-800', textS, hoverBtn))}>
              {o.label ?? o}
            </button>
          );
        })}
      </div>
    </FieldWrap>
  );
}

function TextareaField({ label, level, value, onChange, rows = 3, hint }) {
  return (
    <FieldWrap label={label} level={level} hint={hint}>
      <textarea value={value || ''} onChange={(e) => onChange?.(e.target.value)} rows={rows}
        className={cx('w-full text-sm rounded-md outline-none transition-colors px-2.5 py-1.5 resize-none',
          'bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-700',
          'focus:border-stone-900 dark:focus:border-stone-300', textP)} />
    </FieldWrap>
  );
}

// === DatePicker ============================================
function DatePicker({ label, value, onChange, range }) {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState(value || new Date(2026, 4, 10));
  const ref = useRef(null);
  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', h); return () => document.removeEventListener('mousedown', h);
  }, []);
  const fmt = (d) => d ? `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${d.getFullYear()}` : '';
  const display = range
    ? `${fmt(value?.from)}${value?.to ? ' — ' + fmt(value.to) : ''}`
    : fmt(value);
  return (
    <FieldWrap label={label}>
      <div ref={ref} className="relative">
        <button onClick={() => setOpen(!open)}
          className={cx('w-full text-sm text-left rounded-md transition-colors px-2.5 py-1.5',
            'bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-700',
            'flex items-center justify-between', textP)}>
          <span className={display ? '' : textL}>{display || 'Выберите дату'}</span>
          <Calendar className={cx('w-3.5 h-3.5', textL)} />
        </button>
        {open && (
          <div className={cx('absolute z-50 mt-1 left-0 rounded-lg shadow-sm p-3 w-72', surface)}>
            <CalendarGrid view={view} setView={setView} value={value} onChange={(d) => { onChange?.(d); !range && setOpen(false); }} range={range} />
          </div>
        )}
      </div>
    </FieldWrap>
  );
}

function CalendarGrid({ view, setView, value, onChange, range }) {
  const months = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
  const days = ['пн','вт','ср','чт','пт','сб','вс'];
  const first = new Date(view.getFullYear(), view.getMonth(), 1);
  const startWeekday = (first.getDay() + 6) % 7;
  const lastDay = new Date(view.getFullYear(), view.getMonth() + 1, 0).getDate();
  const today = new Date();
  const cells = [];
  for (let i = 0; i < startWeekday; i++) cells.push(null);
  for (let d = 1; d <= lastDay; d++) cells.push(new Date(view.getFullYear(), view.getMonth(), d));
  while (cells.length % 7) cells.push(null);
  const isSame = (a, b) => a && b && a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  const inRange = (d) => range && value?.from && value?.to && d >= value.from && d <= value.to;

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <button onClick={() => setView(new Date(view.getFullYear(), view.getMonth() - 1, 1))} className={cx('p-1 rounded', hoverBtn)}>
          <ChevronLeft className={cx('w-3.5 h-3.5', textM)} />
        </button>
        <span className={cx('text-sm font-medium', textP)}>{months[view.getMonth()]} {view.getFullYear()}</span>
        <button onClick={() => setView(new Date(view.getFullYear(), view.getMonth() + 1, 1))} className={cx('p-1 rounded', hoverBtn)}>
          <ChevronRight className={cx('w-3.5 h-3.5', textM)} />
        </button>
      </div>
      <div className="grid grid-cols-7 gap-0.5 mb-1">
        {days.map(d => <div key={d} className={cx('text-center text-[10px] uppercase tracking-wider py-1', textL)}>{d}</div>)}
      </div>
      <div className="grid grid-cols-7 gap-0.5">
        {cells.map((d, i) => {
          if (!d) return <div key={i} />;
          const isToday = isSame(d, today);
          const isSelected = range ? (isSame(d, value?.from) || isSame(d, value?.to)) : isSame(d, value);
          const isInRange = inRange(d);
          return (
            <button key={i} onClick={() => {
              if (range) {
                if (!value?.from || (value.from && value.to)) onChange?.({ from: d, to: null });
                else onChange?.(d < value.from ? { from: d, to: value.from } : { from: value.from, to: d });
              } else onChange?.(d);
            }}
              className={cx('aspect-square text-xs rounded transition-colors tabular-nums',
                isSelected ? 'bg-stone-900 text-white dark:bg-stone-50 dark:text-stone-900 font-medium'
                : isInRange ? 'bg-stone-200 dark:bg-stone-700' + ' ' + textP
                : isToday ? 'ring-1 ring-stone-300 dark:ring-stone-600 ' + textP
                : cx(textS, hoverBtn))}>
              {d.getDate()}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function TimePicker({ label, value, onChange }) {
  const opts = []; for (let h = 0; h < 24; h++) for (const m of [0, 30]) opts.push(`${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`);
  return (
    <FieldWrap label={label}>
      <div className="relative">
        <select value={value || ''} onChange={(e) => onChange?.(e.target.value)}
          className={cx('w-full text-sm rounded-md outline-none px-2.5 py-1.5 appearance-none',
            'bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-700', textP)}>
          <option value="">—</option>
          {opts.map(o => <option key={o}>{o}</option>)}
        </select>
        <Clock className={cx('w-3.5 h-3.5 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none', textL)} />
      </div>
    </FieldWrap>
  );
}

function Combobox({ label, value, onChange, options = [], placeholder = 'Поиск…' }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const ref = useRef(null);
  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', h); return () => document.removeEventListener('mousedown', h);
  }, []);
  const filtered = options.filter(o => (o.label || o).toLowerCase().includes(q.toLowerCase()));
  const selected = options.find(o => (o.value ?? o) === value);
  return (
    <FieldWrap label={label}>
      <div ref={ref} className="relative">
        <button onClick={() => setOpen(!open)}
          className={cx('w-full text-sm text-left rounded-md px-2.5 py-1.5 flex items-center justify-between',
            'bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-700', textP)}>
          <span className={selected ? '' : textL}>{selected?.label || selected || 'Не выбрано'}</span>
          <ChevronsUpDown className={cx('w-3.5 h-3.5', textL)} />
        </button>
        {open && (
          <div className={cx('absolute z-50 mt-1 left-0 right-0 rounded-lg shadow-sm overflow-hidden', surface)}>
            <div className={cx('p-2 border-b', borderD)}>
              <Input icon={Search} value={q} onChange={(e) => setQ(e.target.value)} placeholder={placeholder} autoFocus />
            </div>
            <div className="max-h-48 overflow-y-auto">
              {filtered.length === 0 && <div className={cx('px-3 py-2 text-sm italic', textL)}>Ничего не найдено</div>}
              {filtered.map(o => {
                const v = o.value ?? o; const lbl = o.label ?? o;
                return (
                  <button key={v} onClick={() => { onChange?.(v); setOpen(false); setQ(''); }}
                    className={cx('w-full px-3 py-1.5 text-sm text-left flex items-center justify-between', hoverRow, textS)}>
                    {lbl}
                    {v === value && <Check className="w-3.5 h-3.5" />}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </FieldWrap>
  );
}

function FileUpload({ label, files = [], onChange }) {
  const [drag, setDrag] = useState(false);
  return (
    <FieldWrap label={label}>
      <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); onChange?.([...files, ...Array.from(e.dataTransfer.files).map(f => ({ name: f.name, size: f.size }))]); }}
        className={cx('rounded-lg border-2 border-dashed transition-colors p-5 text-center',
          drag ? 'border-stone-900 dark:border-stone-300 bg-stone-50 dark:bg-stone-800/50' : 'border-stone-300 dark:border-stone-700')}>
        <Upload className={cx('w-5 h-5 mx-auto mb-1.5', textM)} />
        <div className={cx('text-sm', textS)}>Перетащите файлы или <button className="underline">выберите</button></div>
        <div className={cx('text-[10px] mt-1', textL)}>PNG, JPG, PDF до 10MB</div>
      </div>
      {files.length > 0 && (
        <div className="space-y-1 mt-2">
          {files.map((f, i) => (
            <div key={i} className={cx('flex items-center justify-between px-2 py-1 rounded text-xs', surfaceMuted)}>
              <span className={cx('flex items-center gap-1.5', textS)}>
                <File className="w-3 h-3" />
                <span className="font-mono text-[11px]">{f.name}</span>
              </span>
              <button onClick={() => onChange?.(files.filter((_, j) => j !== i))} className={cx('p-0.5 rounded', hoverBtn)}>
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}
    </FieldWrap>
  );
}

function ColorPicker({ label, value, onChange }) {
  const palette = ['#1C1917', '#FAFAF9', '#FCA5A5', '#FCD34D', '#86EFAC', '#93C5FD', '#C4B5FD', '#FDA4AF', '#A8A29E'];
  return (
    <FieldWrap label={label}>
      <div className="flex items-center gap-2">
        <div className="flex flex-wrap gap-1.5 flex-1">
          {palette.map(c => (
            <button key={c} onClick={() => onChange?.(c)}
              className={cx('w-6 h-6 rounded ring-1 transition-transform',
                value === c ? 'ring-2 ring-offset-2 ring-stone-900 dark:ring-stone-50 dark:ring-offset-stone-900' : 'ring-stone-200 dark:ring-stone-700 hover:scale-110')}
              style={{ background: c }} />
          ))}
        </div>
        <Input value={value || ''} onChange={(e) => onChange?.(e.target.value)} placeholder="#000000"
          className="w-24 font-mono text-xs" />
      </div>
    </FieldWrap>
  );
}

// =========================================================
// DEMO HELPERS
// =========================================================

function Section({ title, description, children, columns = 1 }) {
  return (
    <section className="mb-12">
      <div className={cx('mb-4 pb-2 border-b', borderD)}>
        <h2 style={{ fontFamily: "'Instrument Serif', serif" }} className={cx('text-2xl', textP)}>{title}</h2>
        {description && <div className={cx('text-sm mt-1', textM)}>{description}</div>}
      </div>
      <div className={cx('grid gap-4', columns === 2 ? 'grid-cols-2' : columns === 3 ? 'grid-cols-3' : '')}>
        {children}
      </div>
    </section>
  );
}

function Demo({ label, code, children, full, padded = true }) {
  return (
    <div className={cx('rounded-lg', surface, full && 'col-span-full')}>
      <div className={cx('px-4 py-2 border-b flex items-center justify-between', borderD)}>
        <span className={cx('text-[11px] uppercase tracking-wider font-medium', textM)}>{label}</span>
        {code && <code className={cx('text-[10px] font-mono', textL)}>{code}</code>}
      </div>
      <div className={cx(padded ? 'p-5' : '', 'flex flex-wrap items-start gap-3')}>{children}</div>
    </div>
  );
}

function SubLabel({ children }) {
  return <div className={cx('text-[11px] uppercase tracking-wider font-medium mb-1.5', textM)}>{children}</div>;
}

// =========================================================
// SECTION 1: FOUNDATION (palette, typography, spacing)
// =========================================================

function Foundation() {
  const stones = [
    { c: '50', hex: '#FAFAF9' }, { c: '100', hex: '#F5F5F4' }, { c: '200', hex: '#E7E5E4' },
    { c: '300', hex: '#D6D3D1' }, { c: '400', hex: '#A8A29E' }, { c: '500', hex: '#78716C' },
    { c: '600', hex: '#57534E' }, { c: '700', hex: '#44403C' }, { c: '800', hex: '#292524' },
    { c: '900', hex: '#1C1917' }, { c: '950', hex: '#0C0A09' },
  ];
  const semantic = [
    { name: 'Emerald', hex: '#059669', use: 'success / в продаже' },
    { name: 'Blue', hex: '#2563EB', use: 'info / запуск' },
    { name: 'Amber', hex: '#D97706', use: 'warning / выводим' },
    { name: 'Red / Rose', hex: '#E11D48', use: 'error / не выводится' },
    { name: 'Purple', hex: '#7C3AED', use: 'brand accent (logo, активный nav)' },
  ];
  const tokens = [
    { tk: 'surface', light: 'white', dark: 'stone-900', use: 'фон карточек' },
    { tk: 'page', light: 'stone-50/40', dark: 'stone-950', use: 'фон страницы' },
    { tk: 'surface-muted', light: 'stone-50/60', dark: 'stone-900/40', use: 'sidebar, hover' },
    { tk: 'text-primary', light: 'stone-900', dark: 'stone-50', use: 'основной текст' },
    { tk: 'text-secondary', light: 'stone-700', dark: 'stone-300', use: 'вторичный текст' },
    { tk: 'text-muted', light: 'stone-500', dark: 'stone-400', use: 'подписи' },
    { tk: 'text-label', light: 'stone-400', dark: 'stone-500', use: 'лейблы UPPERCASE' },
    { tk: 'border', light: 'stone-200', dark: 'stone-800', use: 'обводки карточек' },
    { tk: 'border-strong', light: 'stone-300', dark: 'stone-700', use: 'усиленные обводки' },
  ];
  return (
    <>
      <Section title="Цветовая палитра" description="Базовая — Tailwind stone. Никаких gray/slate/zinc/neutral.">
        <Demo label="Stone scale" code="bg-stone-{50..950}" full>
          <div className="grid grid-cols-11 gap-1.5 w-full">
            {stones.map(s => (
              <div key={s.c} className="text-center">
                <div className="w-full aspect-square rounded ring-1 ring-stone-200 dark:ring-stone-700 mb-1" style={{ background: s.hex }} />
                <div className={cx('text-[10px] tabular-nums', textS)}>{s.c}</div>
                <div className={cx('text-[9px] font-mono', textL)}>{s.hex}</div>
              </div>
            ))}
          </div>
        </Demo>
        <Demo label="Семантические цвета" code="<Badge variant=...>" full>
          <div className="grid grid-cols-5 gap-3 w-full">
            {semantic.map(s => (
              <div key={s.name} className={cx('p-3 rounded-md', surfaceMuted)}>
                <div className="w-full h-12 rounded mb-2" style={{ background: s.hex }} />
                <div className={cx('text-xs font-medium', textP)}>{s.name}</div>
                <div className={cx('text-[10px] font-mono', textL)}>{s.hex}</div>
                <div className={cx('text-[10px] mt-1', textM)}>{s.use}</div>
              </div>
            ))}
          </div>
        </Demo>
      </Section>

      <Section title="Семантические токены" description="Через CSS-переменные (или dark: префиксы). НЕ хардкодим stone-* в компонентах напрямую.">
        <Demo label="Surface, text, border" full>
          <div className={cx('w-full rounded-lg border overflow-hidden', borderD)}>
            <table className="w-full text-sm">
              <thead className={cx('text-[11px] uppercase tracking-wider', textM, surfaceMuted)}>
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Токен</th>
                  <th className="px-3 py-2 text-left font-medium">Light</th>
                  <th className="px-3 py-2 text-left font-medium">Dark</th>
                  <th className="px-3 py-2 text-left font-medium">Применение</th>
                </tr>
              </thead>
              <tbody>
                {tokens.map(t => (
                  <tr key={t.tk} className={cx('border-t', borderD)}>
                    <td className="px-3 py-2"><code className="font-mono text-xs">{t.tk}</code></td>
                    <td className={cx('px-3 py-2 font-mono text-xs', textS)}>{t.light}</td>
                    <td className={cx('px-3 py-2 font-mono text-xs', textS)}>{t.dark}</td>
                    <td className={cx('px-3 py-2 text-xs', textM)}>{t.use}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Demo>
      </Section>

      <Section title="Типографика" description="DM Sans (UI) + Instrument Serif (заголовки страниц, italic для бренда).">
        <Demo label="Шрифты" full>
          <div className="space-y-4 w-full">
            <div>
              <SubLabel>Page title — Instrument Serif</SubLabel>
              <div style={{ fontFamily: "'Instrument Serif', serif" }} className={cx('text-3xl', textP)}>
                <em className="italic">Wookiee</em> Hub · Каталог
              </div>
            </div>
            <div>
              <SubLabel>Section title — DM Sans 500</SubLabel>
              <div className={cx('text-base font-medium', textP)}>Атрибуты модели</div>
            </div>
            <div>
              <SubLabel>Body — DM Sans 400 14px</SubLabel>
              <div className={cx('text-sm', textP)}>Линейка размеров: S — M — L — XL. Базовая модель Vuki — основа коллекции Lite, продаётся через WB и Ozon.</div>
            </div>
            <div>
              <SubLabel>Label uppercase — DM Sans 11px tracking-wider</SubLabel>
              <div className={cx('text-[11px] uppercase tracking-wider', textM)}>СТАТУС МОДЕЛИ</div>
            </div>
            <div>
              <SubLabel>Numbers — tabular-nums</SubLabel>
              <div className={cx('text-2xl tabular-nums', textP)}>1 248,00 ₽</div>
            </div>
            <div>
              <SubLabel>Mono — font-mono для технических значений</SubLabel>
              <div className="text-xs font-mono" style={{ color: 'inherit' }}>VUK-BLK-S · 4607177384962 · gjvwcdtfg</div>
            </div>
          </div>
        </Demo>
      </Section>

      <Section title="Spacing" description="База — 4px. Основной набор отступов.">
        <Demo label="Scale" full>
          <div className="space-y-2 w-full">
            {[
              { tk: 'gap-1.5', px: 6 }, { tk: 'gap-2', px: 8 }, { tk: 'gap-3', px: 12 },
              { tk: 'gap-4', px: 16 }, { tk: 'gap-6', px: 24 }, { tk: 'gap-8', px: 32 },
            ].map(s => (
              <div key={s.tk} className="flex items-center gap-3">
                <code className="font-mono text-xs w-20">{s.tk}</code>
                <div className="bg-stone-900 dark:bg-stone-50" style={{ width: s.px, height: 8 }} />
                <span className={cx('text-xs tabular-nums', textM)}>{s.px}px</span>
              </div>
            ))}
          </div>
        </Demo>
      </Section>
    </>
  );
}

// =========================================================
// SECTION 2: ATOMS
// =========================================================

function AtomsSection() {
  const [check1, setCheck1] = useState(true);
  const [check2, setCheck2] = useState(false);
  const [radio, setRadio] = useState('a');
  const [tg, setTg] = useState(true);
  const [sl, setSl] = useState(45);

  return (
    <>
      <Section title="Кнопки" description="Иерархия: primary → secondary → ghost. Danger варианты для деструктивных действий." columns={2}>
        <Demo label="Варианты" code="<Button variant=...>">
          <Button>Сохранить</Button>
          <Button variant="secondary">Отмена</Button>
          <Button variant="ghost">Подробнее</Button>
          <Button variant="danger">Удалить</Button>
          <Button variant="danger-ghost">Удалить</Button>
          <Button variant="success">Подтвердить</Button>
        </Demo>
        <Demo label="Размеры" code="size='xs|sm|md|lg'">
          <Button size="xs">XS</Button>
          <Button size="sm">SM</Button>
          <Button size="md">MD</Button>
          <Button size="lg">LG</Button>
        </Demo>
        <Demo label="С иконкой" code="icon={Plus}">
          <Button icon={Plus}>Добавить</Button>
          <Button variant="secondary" icon={Edit3}>Редактировать</Button>
          <Button variant="ghost" icon={Download}>Экспорт</Button>
        </Demo>
        <Demo label="Только иконка">
          <IconButton icon={Edit3} title="Редактировать" />
          <IconButton icon={Trash2} danger title="Удалить" />
          <IconButton icon={Settings} title="Настройки" />
          <IconButton icon={Bell} active title="Активна" />
        </Demo>
      </Section>

      <Section title="Базовые поля" description="Высота 32px, focus chrome — обводка цвета primary." columns={2}>
        <Demo label="Input" code="<Input />">
          <Input placeholder="Введите текст…" />
        </Demo>
        <Demo label="С иконкой" code="icon={Search}">
          <Input icon={Search} placeholder="Поиск…" />
        </Demo>
        <Demo label="С префиксом" code="prefix='₽'">
          <Input prefix="₽" suffix="за шт" placeholder="0" />
        </Demo>
        <Demo label="Mono input">
          <Input className="font-mono text-xs" defaultValue="VUK-BLK-S-2026" />
        </Demo>
        <Demo label="Error">
          <Input error placeholder="Обязательное поле" defaultValue="" />
        </Demo>
        <Demo label="Disabled">
          <Input disabled defaultValue="Read-only" />
        </Demo>
      </Section>

      <Section title="Селекторы" columns={2}>
        <Demo label="Checkbox">
          <div className="flex flex-col gap-2">
            <Checkbox checked={check1} onChange={setCheck1} label="Доступно к продаже" />
            <Checkbox checked={check2} onChange={setCheck2} label="Подарочная упаковка" />
            <Checkbox indeterminate label="Все размеры (частично)" />
          </div>
        </Demo>
        <Demo label="Radio">
          <div className="flex flex-col gap-2">
            <Radio checked={radio === 'a'} onChange={() => setRadio('a')} label="WB" />
            <Radio checked={radio === 'b'} onChange={() => setRadio('b')} label="Ozon" />
            <Radio checked={radio === 'c'} onChange={() => setRadio('c')} label="Сайт" />
          </div>
        </Demo>
        <Demo label="Toggle">
          <div className="flex flex-col gap-2">
            <Toggle on={tg} onChange={setTg} label="Уведомления" />
            <Toggle on={false} label="Тёмная тема" />
            <Toggle on={true} disabled label="Disabled (on)" />
          </div>
        </Demo>
        <Demo label="Slider">
          <Slider value={sl} onChange={setSl} suffix="%" />
        </Demo>
      </Section>

      <Section title="Бейджи и теги" columns={2}>
        <Demo label="StatusBadge" code="STATUS_MAP[id]">
          {[1,2,3,4,5].map(id => <StatusBadge key={id} statusId={id} />)}
        </Demo>
        <Demo label="LevelBadge" code="<LevelBadge level=...>">
          <LevelBadge level="model" />
          <LevelBadge level="variation" />
          <LevelBadge level="artikul" />
          <LevelBadge level="sku" />
        </Demo>
        <Demo label="Цветовые варианты">
          <Badge variant="emerald" dot>+12.4%</Badge>
          <Badge variant="red" dot>-3.2%</Badge>
          <Badge variant="blue" icon={Info}>Новое</Badge>
          <Badge variant="amber" icon={AlertTriangle}>Внимание</Badge>
        </Demo>
        <Demo label="Tag">
          <Tag>Default</Tag>
          <Tag color="blue" icon={Hash}>collection</Tag>
          <Tag color="emerald">SKU</Tag>
        </Demo>
        <Demo label="Chip">
          <Chip onRemove={() => {}}>Vuki</Chip>
          <Chip onRemove={() => {}}>Чёрный</Chip>
          <Chip>Без удаления</Chip>
        </Demo>
        <Demo label="Kbd">
          <Kbd>⌘</Kbd>
          <Kbd>K</Kbd>
          <span className={cx('text-xs', textM)}>открыть поиск</span>
        </Demo>
      </Section>

      <Section title="Аватары" columns={2}>
        <Demo label="Размеры">
          <Avatar initials="ДВ" size="xs" />
          <Avatar initials="ДВ" size="sm" />
          <Avatar initials="ДВ" size="md" />
          <Avatar initials="ДВ" size="lg" />
        </Demo>
        <Demo label="Цвета">
          <Avatar initials="ДВ" color="stone" />
          <Avatar initials="АА" color="emerald" />
          <Avatar initials="МК" color="blue" />
          <Avatar initials="СП" color="purple" />
          <Avatar initials="НТ" color="rose" />
        </Demo>
        <Demo label="Со статусом">
          <Avatar initials="ДВ" status="online" />
          <Avatar initials="АА" color="emerald" status="busy" />
          <Avatar initials="МК" color="blue" status="offline" />
        </Demo>
        <Demo label="AvatarGroup">
          <AvatarGroup users={[
            { initials: 'ДВ', color: 'stone' }, { initials: 'АА', color: 'emerald' },
            { initials: 'МК', color: 'blue' }, { initials: 'СП', color: 'purple' },
            { initials: 'НТ', color: 'rose' }, { initials: 'РЛ', color: 'amber' },
          ]} max={4} />
        </Demo>
      </Section>

      <Section title="Прогресс и состояния" columns={2}>
        <Demo label="ProgressBar">
          <div className="space-y-2 w-full">
            <ProgressBar value={85} color="emerald" label="Заполненность модели" />
            <ProgressBar value={60} color="blue" label="Прогресс" />
            <ProgressBar value={40} color="amber" label="Внимание" />
            <ProgressBar value={20} color="red" label="Критично" />
          </div>
        </Demo>
        <Demo label="Ring (CompletenessRing)">
          <div className="flex items-center gap-3">
            <Ring value={0.92} size={32} /><span className={cx('text-xs tabular-nums', textS)}>92%</span>
            <Ring value={0.65} size={32} /><span className={cx('text-xs tabular-nums', textS)}>65%</span>
            <Ring value={0.42} size={32} /><span className={cx('text-xs tabular-nums', textS)}>42%</span>
            <Ring value={0.18} size={32} /><span className={cx('text-xs tabular-nums', textS)}>18%</span>
          </div>
        </Demo>
        <Demo label="ColorSwatch">
          <ColorSwatch hex="#1C1917" label="#1C1917" />
          <ColorSwatch hex="#E11D48" label="rose-600" />
          <ColorSwatch hex="#059669" label="emerald-600" />
        </Demo>
        <Demo label="Skeleton">
          <div className="space-y-2 w-full">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-4 w-64" />
            <Skeleton className="h-3 w-32" />
          </div>
        </Demo>
      </Section>

      <Section title="Tooltip">
        <Demo label="Hover для тултипа" full>
          <div className="flex items-center gap-4">
            <Tooltip text="Стандартный тултип"><Button variant="secondary">Hover me</Button></Tooltip>
            <Tooltip text="С иконкой"><HelpCircle className={cx('w-4 h-4', textM)} /></Tooltip>
            <Tooltip text="Снизу" position="bottom"><Button variant="ghost">Нижний</Button></Tooltip>
          </div>
        </Demo>
      </Section>
    </>
  );
}

// =========================================================
// SECTION 3: FORMS
// =========================================================

function FormsSection() {
  const [text, setText] = useState('Vuki');
  const [num, setNum] = useState(2890);
  const [sel, setSel] = useState('1');
  const [multi, setMulti] = useState(['S', 'M']);
  const [date, setDate] = useState(new Date(2026, 4, 10));
  const [range, setRange] = useState({ from: new Date(2026, 4, 5), to: new Date(2026, 4, 15) });
  const [time, setTime] = useState('10:30');
  const [combo, setCombo] = useState('vuki');
  const [color, setColor] = useState('#1C1917');
  const [files, setFiles] = useState([{ name: 'tech-sheet-v3.pdf', size: 1248 }]);
  const [textarea, setTextarea] = useState('');

  return (
    <>
      <Section title="Базовые поля формы" description="С обёрткой <FieldWrap> — лейбл uppercase + LevelBadge + опциональный hint." columns={2}>
        <Demo label="TextField">
          <div className="w-full"><TextField label="Название модели" level="model" value={text} onChange={setText} hint="Уникальное в рамках бренда" /></div>
        </Demo>
        <Demo label="NumberField с suffix">
          <div className="w-full"><NumberField label="Цена розничная" level="sku" value={num} onChange={setNum} suffix="₽" /></div>
        </Demo>
        <Demo label="SelectField">
          <div className="w-full"><SelectField label="Категория" level="model" value={sel} onChange={setSel}
            options={[{ id: '1', nazvanie: 'Бюстгальтер' }, { id: '2', nazvanie: 'Трусы' }, { id: '3', nazvanie: 'Комплект' }]} /></div>
        </Demo>
        <Demo label="MultiSelectField (chips)">
          <div className="w-full"><MultiSelectField label="Размерная линейка" level="artikul" value={multi} onChange={setMulti}
            options={[{ value: 'XS', label: 'XS' }, { value: 'S', label: 'S' }, { value: 'M', label: 'M' }, { value: 'L', label: 'L' }, { value: 'XL', label: 'XL' }]} /></div>
        </Demo>
        <Demo label="TextareaField">
          <div className="w-full"><TextareaField label="Описание" value={textarea} onChange={setTextarea} /></div>
        </Demo>
        <Demo label="Mono TextField">
          <div className="w-full"><TextField label="Артикул WB" level="sku" mono defaultValue="WB-12847562" /></div>
        </Demo>
      </Section>

      <Section title="Расширенные поля" description="Date, Time, Combobox, FileUpload, ColorPicker." columns={2}>
        <Demo label="DatePicker (single)">
          <div className="w-full"><DatePicker label="Дата запуска" value={date} onChange={setDate} /></div>
        </Demo>
        <Demo label="DatePicker (range)">
          <div className="w-full"><DatePicker label="Период промо" value={range} onChange={setRange} range /></div>
        </Demo>
        <Demo label="TimePicker">
          <div className="w-full"><TimePicker label="Время съёмки" value={time} onChange={setTime} /></div>
        </Demo>
        <Demo label="Combobox">
          <div className="w-full"><Combobox label="Модель" value={combo} onChange={setCombo}
            options={[
              { value: 'vuki', label: 'Vuki' }, { value: 'vivi', label: 'Vivi' },
              { value: 'vesta', label: 'Vesta' }, { value: 'vera', label: 'Vera' },
              { value: 'vita', label: 'Vita' }, { value: 'volna', label: 'Volna' },
            ]} /></div>
        </Demo>
        <Demo label="ColorPicker">
          <div className="w-full"><ColorPicker label="Цвет товара" value={color} onChange={setColor} /></div>
        </Demo>
        <Demo label="FileUpload">
          <div className="w-full"><FileUpload label="Технические документы" files={files} onChange={setFiles} /></div>
        </Demo>
      </Section>
    </>
  );
}

// =========================================================
// SECTION 4: DATA DISPLAY
// =========================================================

function DataTable({ rows = tableRows, columns, selectable, expandable }) {
  const [selected, setSelected] = useState([]);
  const [expanded, setExpanded] = useState(null);
  const cols = columns || [
    { key: 'sku', label: 'SKU', mono: true, w: 'w-32' },
    { key: 'model', label: 'Модель' },
    { key: 'color', label: 'Цвет' },
    { key: 'size', label: 'Размер', center: true, w: 'w-16' },
    { key: 'status', label: 'Статус', render: (r) => <StatusBadge statusId={r.status} compact /> },
    { key: 'stock', label: 'Остаток', right: true, render: (r) => (
        <span className={cx('tabular-nums', r.stock === 0 ? 'text-rose-600 dark:text-rose-400' : r.stock < 30 ? 'text-amber-600 dark:text-amber-400' : textP)}>
          {r.stock}
        </span>
      ) },
    { key: 'price', label: 'Цена', right: true, render: (r) => <span className="tabular-nums">{r.price.toLocaleString('ru-RU')} ₽</span> },
  ];
  const allSelected = selected.length === rows.length;
  const some = selected.length > 0 && selected.length < rows.length;

  return (
    <div className={cx('rounded-lg overflow-hidden', surface)}>
      <table className="w-full text-sm">
        <thead className={cx(surfaceMuted, 'border-b', borderD)}>
          <tr className={cx('text-left text-[11px] uppercase tracking-wider', textM)}>
            {selectable && <th className="px-3 py-2.5 w-8">
              <Checkbox checked={allSelected} indeterminate={some}
                onChange={(v) => setSelected(v ? rows.map(r => r.id) : [])} />
            </th>}
            {expandable && <th className="w-8"></th>}
            {cols.map(c => (
              <th key={c.key} className={cx('px-3 py-2.5 font-medium', c.w, c.right && 'text-right', c.center && 'text-center')}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <React.Fragment key={r.id}>
              <tr className={cx('border-b last:border-0', borderD, hoverRow)}>
                {selectable && <td className="px-3 py-2.5">
                  <Checkbox checked={selected.includes(r.id)}
                    onChange={(v) => setSelected(v ? [...selected, r.id] : selected.filter(x => x !== r.id))} />
                </td>}
                {expandable && <td className="px-1">
                  <button onClick={() => setExpanded(expanded === r.id ? null : r.id)} className={cx('p-1 rounded', hoverBtn)}>
                    <ChevronRight className={cx('w-3.5 h-3.5 transition-transform', textM, expanded === r.id && 'rotate-90')} />
                  </button>
                </td>}
                {cols.map(c => (
                  <td key={c.key} className={cx('px-3 py-2.5', c.right && 'text-right', c.center && 'text-center', c.mono && 'font-mono text-xs', textS)}>
                    {c.render ? c.render(r) : r[c.key]}
                  </td>
                ))}
              </tr>
              {expandable && expanded === r.id && (
                <tr className={surfaceMuted}>
                  <td colSpan={cols.length + (selectable ? 1 : 0) + 1} className="px-6 py-3">
                    <div className={cx('text-xs', textM)}>Раскрытие: история изменений, ссылки, метаданные…</div>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Pagination({ page, total, onChange }) {
  return (
    <div className={cx('flex items-center gap-1 text-sm', textS)}>
      <button onClick={() => onChange(Math.max(1, page - 1))} disabled={page === 1}
        className={cx('p-1.5 rounded disabled:opacity-30', hoverBtn)}>
        <ChevronLeft className="w-3.5 h-3.5" />
      </button>
      {[1, 2, 3, '…', total - 1, total].map((p, i) => (
        p === '…' ? <span key={i} className={cx('px-2', textL)}>…</span>
        : <button key={i} onClick={() => onChange(p)}
            className={cx('w-7 h-7 rounded text-xs tabular-nums',
              page === p ? 'bg-stone-900 text-white dark:bg-stone-50 dark:text-stone-900' : hoverBtn)}>
            {p}
          </button>
      ))}
      <button onClick={() => onChange(Math.min(total, page + 1))} disabled={page === total}
        className={cx('p-1.5 rounded disabled:opacity-30', hoverBtn)}>
        <ChevronRight className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

function StatCard({ label, value, trend, sub, icon: Icon }) {
  return (
    <div className={cx('rounded-lg p-4', surface)}>
      <div className="flex items-start justify-between mb-2">
        <span className={cx('text-[11px] uppercase tracking-wider font-medium', textM)}>{label}</span>
        {Icon && <Icon className={cx('w-3.5 h-3.5', textL)} />}
      </div>
      <div className={cx('text-2xl tabular-nums font-medium', textP)}>{value}</div>
      <div className="flex items-center gap-2 mt-1.5">
        {trend && (
          <Badge variant={trend > 0 ? 'emerald' : 'red'} compact>
            {trend > 0 ? '↑' : '↓'} {Math.abs(trend)}%
          </Badge>
        )}
        {sub && <span className={cx('text-[11px]', textM)}>{sub}</span>}
      </div>
    </div>
  );
}

function TreeView({ items, level = 0 }) {
  return (
    <div>
      {items.map((it, i) => <TreeNode key={i} item={it} level={level} />)}
    </div>
  );
}

function TreeNode({ item, level }) {
  const [open, setOpen] = useState(level < 1);
  const has = item.children?.length > 0;
  return (
    <div>
      <div className={cx('flex items-center gap-1.5 px-2 py-1 rounded text-sm cursor-pointer', hoverRow, textS)}
        style={{ paddingLeft: 8 + level * 16 }}
        onClick={() => has && setOpen(!open)}>
        {has ? (
          <ChevronRight className={cx('w-3 h-3 transition-transform', textL, open && 'rotate-90')} />
        ) : <span className="w-3" />}
        {has ? <FolderOpen className={cx('w-3.5 h-3.5', textL)} /> : <File className={cx('w-3.5 h-3.5', textL)} />}
        <span>{item.label}</span>
        {item.count !== undefined && <span className={cx('ml-auto text-[10px] tabular-nums', textL)}>{item.count}</span>}
      </div>
      {has && open && <TreeView items={item.children} level={level + 1} />}
    </div>
  );
}

function BulkActionsBar({ count, onClear }) {
  if (!count) return null;
  return (
    <div className={cx('flex items-center justify-between px-4 py-2.5 rounded-md', surface)}>
      <div className="flex items-center gap-3">
        <span className={cx('text-sm font-medium', textP)}>Выбрано: <span className="tabular-nums">{count}</span></span>
        <span className={cx('w-px h-4', borderD, 'bg-stone-200 dark:bg-stone-700')} />
        <Button variant="secondary" size="sm" icon={Edit3}>Изменить статус</Button>
        <Button variant="secondary" size="sm" icon={Archive}>Архивировать</Button>
        <Button variant="danger-ghost" size="sm" icon={Trash2}>Удалить</Button>
      </div>
      <button onClick={onClear} className={cx('text-xs', textM, 'hover:underline')}>Очистить</button>
    </div>
  );
}

function DataSection() {
  const [page, setPage] = useState(2);
  const tree = [
    { label: 'Каталог', count: 4, children: [
      { label: 'Бюстгальтеры', count: 18, children: [
        { label: 'Bralette', count: 6 },
        { label: 'Push-up', count: 8 },
        { label: 'Невидимки', count: 4 },
      ]},
      { label: 'Трусы', count: 24 },
      { label: 'Комплекты', count: 12 },
    ]},
  ];

  return (
    <>
      <Section title="StatCard / KPI">
        <Demo label="KPI ряд" full padded={false}>
          <div className="grid grid-cols-4 gap-3 w-full p-5">
            <StatCard label="Выручка месяц" value="4.82M ₽" trend={12.4} sub="vs прошлый" icon={TrendingUp} />
            <StatCard label="Заказов" value="2 156" trend={8.2} sub="vs прошлый" icon={Package} />
            <StatCard label="Маржа" value="34.2%" trend={-2.1} sub="vs прошлый" icon={TrendingDown} />
            <StatCard label="Активных SKU" value="1 248" sub="из 1 386" icon={Layers} />
          </div>
        </Demo>
      </Section>

      <Section title="DataTable" description="Со sticky-header, выбором рядов, expandable rows.">
        <Demo label="Базовая" full padded={false}>
          <div className="w-full p-5">
            <DataTable />
          </div>
        </Demo>
        <Demo label="С selection + expandable" full padded={false}>
          <div className="w-full p-5 space-y-3">
            <DataTable selectable expandable />
            <BulkActionsBar count={2} onClear={() => {}} />
          </div>
        </Demo>
      </Section>

      <Section title="GroupedTable · pivot-style" description="Многоуровневые заголовки + группировка с агрегацией. Паттерн из «Планирование поставок».">
        <Demo label="Планирование поставок" full padded={false}>
          <div className="w-full p-5">
            <GroupedTable />
          </div>
        </Demo>
      </Section>

      <Section title="Pagination" columns={2}>
        <Demo label="Pagination">
          <Pagination page={page} total={12} onChange={setPage} />
        </Demo>
        <Demo label="«Показано» footer">
          <div className={cx('text-xs', textM)}>Показаны первые <span className={cx('tabular-nums font-medium', textP)}>50</span> из <span className="tabular-nums">1 248</span> записей</div>
        </Demo>
      </Section>

      <Section title="TreeView">
        <Demo label="Вложенные категории" full padded={false}>
          <div className="p-3 w-full"><TreeView items={tree} /></div>
        </Demo>
      </Section>
    </>
  );
}

// === GROUPED TABLE — pivot-style как в Planning =============
function GroupedTable() {
  const groups = [
    { key: 'joy-red', model: 'Joy', color: 'Красный', hex: '#9F1239', status: 1, count: 4,
      stats: { perDay: 8.3, stock: 1197, days: 195 },
      items: [
        { sku: '463045827067', size: 'XL', price: 32.91, perDay: 3.32, stock: 13,  days: 4,   prev: 19,  toOrder: 0 },
        { sku: '463045827064', size: 'M',  price: 35.70, perDay: 1.66, stock: 93,  days: 56,  prev: 115, toOrder: 0 },
        { sku: '463045827065', size: 'L',  price: 21.26, perDay: 1.97, stock: 359, days: 182, prev: 238, toOrder: 0 },
        { sku: '463045827063', size: 'S',  price: 20.24, perDay: 1.36, stock: 732, days: 538, prev: 201, toOrder: 0 },
      ]},
    { key: 'joy-black', model: 'Joy', color: 'Чёрный', hex: '#1C1917', status: 3, count: 4,
      stats: { perDay: 11.0, stock: 1949, days: 232 },
      items: [
        { sku: '463045827049', size: 'L',  price: 12.96, perDay: 2.15, stock: 14,  days: 7,   prev: 377, toOrder: 0 },
        { sku: '463045827046', size: 'S',  price: 34.07, perDay: 3.95, stock: 319, days: 81,  prev: 494, toOrder: 0 },
        { sku: '463045827047', size: 'M',  price: 17.17, perDay: 3.51, stock: 747, days: 213, prev: 307, toOrder: 0 },
        { sku: '463045827050', size: 'XL', price: 30.38, perDay: 1.39, stock: 869, days: 625, prev: 479, toOrder: 0 },
      ]},
    { key: 'moon-brown', model: 'Moon2', color: 'Тёмно-коричневый', hex: '#3F2A1D', status: 1, count: 3,
      stats: { perDay: 8.0, stock: 966, days: 962 },
      items: [
        { sku: '463045827112', size: 'M',  price: 32.10, perDay: 3.82, stock: 32,  days: 8,    prev: 600, toOrder: 0 },
        { sku: '463045827113', size: 'L',  price: 13.28, perDay: 3.91, stock: 46,  days: 12,   prev: 122, toOrder: 0 },
        { sku: '463045827110', size: 'S',  price: 23.07, perDay: 0.31, stock: 888, days: 999,  prev: 312, toOrder: 0 },
      ]},
  ];
  const [collapsed, setCollapsed] = useState(new Set());
  const toggle = (k) => setCollapsed(p => { const n = new Set(p); n.has(k) ? n.delete(k) : n.add(k); return n; });
  const daysClass = (d) => d < 30 ? 'bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300'
    : d < 60 ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300'
    : d > 365 ? 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300'
    : 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300';

  return (
    <div className={cx('rounded-lg overflow-hidden', surface)}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm" style={{ minWidth: 1100 }}>
          <thead>
            {/* Row 1 — group columns */}
            <tr className={cx('border-b', borderD, surfaceMuted)}>
              <th colSpan={7} className={cx('px-3 py-2 text-left text-[10px] uppercase tracking-wider font-medium', textL)}>Товар</th>
              <th colSpan={3} className={cx('px-3 py-2 text-left text-[10px] uppercase tracking-wider font-medium border-l', textL, borderD)}>Аналитика продаж</th>
              <th colSpan={3} className={cx('px-3 py-2 text-left text-[10px] uppercase tracking-wider font-medium border-l', textL, borderD)}>
                <div className="flex items-center justify-between">
                  <span>Заказ № 12/1</span>
                  <Badge variant="emerald" compact dot>Прибыло</Badge>
                </div>
              </th>
            </tr>
            {/* Row 2 — column headers */}
            <tr className={cx('border-b', borderD)}>
              <th className="w-6"></th>
              <th className={cx('px-3 py-2 text-left text-[10px] uppercase tracking-wider font-medium', textM)}>Артикул</th>
              <th className={cx('px-3 py-2 text-left text-[10px] uppercase tracking-wider font-medium w-10', textM)}>Р.</th>
              <th className={cx('px-3 py-2 text-left text-[10px] uppercase tracking-wider font-medium', textM)}>Модель</th>
              <th className="w-5"></th>
              <th className={cx('px-3 py-2 text-left text-[10px] uppercase tracking-wider font-medium', textM)}>Цвет</th>
              <th className={cx('px-3 py-2 text-right text-[10px] uppercase tracking-wider font-medium', textM)}>Цена</th>
              <th className={cx('px-3 py-2 text-right text-[10px] uppercase tracking-wider font-medium border-l', textM, borderD)}>
                <span className="inline-flex items-center gap-1">Заказ/д <ArrowUp className="w-2.5 h-2.5" /></span>
              </th>
              <th className={cx('px-3 py-2 text-right text-[10px] uppercase tracking-wider font-medium', textM)}>Наличие</th>
              <th className={cx('px-3 py-2 text-right text-[10px] uppercase tracking-wider font-medium', textM)}>Хватит дн</th>
              <th className={cx('px-3 py-2 text-right text-[10px] uppercase tracking-wider font-medium border-l', textM, borderD)}>Прибыло</th>
              <th className={cx('px-3 py-2 text-right text-[10px] uppercase tracking-wider font-medium bg-blue-50/30 dark:bg-blue-950/20 text-blue-600 dark:text-blue-400')}>К заказу</th>
              <th className={cx('px-3 py-2 text-right text-[10px] uppercase tracking-wider font-medium', textM)}>Хватит</th>
            </tr>
          </thead>
          <tbody>
            {groups.map(g => {
              const isCollapsed = collapsed.has(g.key);
              return (
                <React.Fragment key={g.key}>
                  {/* Group row */}
                  <tr className={cx('border-b cursor-pointer select-none', borderD, surfaceMuted, hoverRow)}
                    onClick={() => toggle(g.key)}>
                    <td className="px-3 py-2">
                      {isCollapsed
                        ? <ChevronRight className={cx('w-3.5 h-3.5', textL)} />
                        : <ChevronDown className={cx('w-3.5 h-3.5', textL)} />}
                    </td>
                    <td colSpan={2} className={cx('px-3 py-2 text-xs font-medium', textP)}>
                      {g.model}/{g.color} <span className={cx('font-normal ml-1', textL)}>({g.count})</span>
                    </td>
                    <td className={cx('px-3 py-2 text-sm', textS)}>{g.model}</td>
                    <td className="px-3 py-2"><ColorSwatch hex={g.hex} /></td>
                    <td className={cx('px-3 py-2 text-sm', textS)}>{g.color}</td>
                    <td></td>
                    <td className={cx('px-3 py-2 text-right text-xs tabular-nums border-l font-medium', textP, borderD)}>{g.stats.perDay.toFixed(1)}</td>
                    <td className={cx('px-3 py-2 text-right text-xs tabular-nums font-medium', textP)}>{g.stats.stock.toLocaleString('ru-RU')}</td>
                    <td className="px-3 py-2 text-right">
                      <span className={cx('inline-flex items-center justify-center px-2 py-0.5 rounded text-xs tabular-nums font-medium min-w-[40px]', daysClass(g.stats.days))}>
                        {g.stats.days > 999 ? '999+' : g.stats.days}
                      </span>
                    </td>
                    <td className={cx('px-3 py-2 text-right text-xs tabular-nums border-l', textP, borderD)}>
                      {g.items.reduce((s, i) => s + i.prev, 0)}
                    </td>
                    <td className="px-3 py-2 text-right">—</td>
                    <td className="px-3 py-2 text-right">—</td>
                  </tr>
                  {/* Group items */}
                  {!isCollapsed && g.items.map(it => (
                    <tr key={it.sku} className={cx('border-b last:border-0', borderD, hoverRow)}>
                      <td></td>
                      <td className={cx('px-3 py-2 font-mono text-[11px]', textS)}>{it.sku}</td>
                      <td className={cx('px-3 py-2 text-xs', textS)}>{it.size}</td>
                      <td colSpan={2} className={cx('px-3 py-2 text-xs', textL)}>SET ru009+ru008</td>
                      <td></td>
                      <td className={cx('px-3 py-2 text-right text-xs tabular-nums', textS)}>{it.price.toFixed(2)}</td>
                      <td className={cx('px-3 py-2 text-right text-xs tabular-nums border-l', textS, borderD)}>{it.perDay.toFixed(2)}</td>
                      <td className={cx('px-3 py-2 text-right text-xs tabular-nums', textS)}>{it.stock}</td>
                      <td className="px-3 py-2 text-right">
                        <span className={cx('inline-flex items-center justify-center px-1.5 py-0.5 rounded text-[11px] tabular-nums min-w-[36px]', daysClass(it.days))}>
                          {it.days > 999 ? '999+' : it.days}
                        </span>
                      </td>
                      <td className={cx('px-3 py-2 text-right text-xs tabular-nums border-l', textS, borderD)}>{it.prev}</td>
                      <td className="px-3 py-2 text-right">
                        <input type="number" defaultValue={0}
                          className={cx('w-16 text-right text-xs tabular-nums px-1.5 py-0.5 rounded outline-none transition-colors',
                            'bg-blue-50/30 dark:bg-blue-950/20 border border-blue-200/40 dark:border-blue-700/40',
                            'focus:bg-white dark:focus:bg-stone-900 focus:border-blue-400', textP)} />
                      </td>
                      <td className={cx('px-3 py-2 text-right text-xs tabular-nums', textL)}>—</td>
                    </tr>
                  ))}
                </React.Fragment>
              );
            })}
          </tbody>
          <tfoot>
            <tr className={cx('border-t', borderD, 'bg-stone-100/60 dark:bg-stone-800/40')}>
              <td colSpan={7} className={cx('px-3 py-2.5 text-xs font-medium', textP)}>ИТОГО · 11 артикулов</td>
              <td className={cx('px-3 py-2.5 text-right text-xs tabular-nums font-medium border-l', textP, borderD)}>27.3</td>
              <td className={cx('px-3 py-2.5 text-right text-xs tabular-nums font-medium', textP)}>4 112</td>
              <td className="px-3 py-2.5"></td>
              <td className={cx('px-3 py-2.5 text-right text-xs tabular-nums font-medium border-l', textP, borderD)}>3 264</td>
              <td className={cx('px-3 py-2.5 text-right text-xs tabular-nums font-medium', textP)}>0</td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

// =========================================================
// SECTION 5: CHARTS — light + dark
// =========================================================

function ChartCard({ title, action, hint, children, full }) {
  return (
    <div className={cx('rounded-lg p-5', surface, full && 'col-span-full')}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className={cx('text-sm font-medium', textP)}>{title}</div>
          {hint && <div className={cx('text-[11px] mt-0.5', textM)}>{hint}</div>}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

function CT({ tk }) {
  return (
    <div style={{
      background: tk.tooltip_bg, border: `1px solid ${tk.tooltip_border}`,
      borderRadius: 6, padding: '6px 10px', fontSize: 11, color: tk.primary,
      boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
    }} />
  );
}

function makeRichTooltip(tk, opts = {}) {
  return ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    const total = opts.showTotal ? payload.reduce((s, p) => s + (p.value || 0), 0) : null;
    const fmtVal = (v) => {
      if (typeof v !== 'number') return v;
      if (Math.abs(v) >= 1000) return v.toLocaleString('ru-RU', { maximumFractionDigits: 1 });
      if (Math.abs(v) < 10) return v.toFixed(2);
      return Math.round(v);
    };
    return (
      <div style={{
        background: tk.tooltip_bg, border: `1px solid ${tk.tooltip_border}`,
        borderRadius: 8, padding: '8px 12px', fontSize: 11, color: tk.primary,
        boxShadow: '0 4px 12px rgba(0,0,0,0.08)', minWidth: 160,
        fontFamily: "'DM Sans', system-ui, sans-serif",
      }}>
        {label && <div style={{ fontWeight: 600, marginBottom: 6, fontSize: 12, paddingBottom: 4, borderBottom: `1px solid ${tk.grid}` }}>{label}</div>}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {payload.map((p, i) => {
            const pct = opts.showPercent && total !== null ? ((p.value / total) * 100).toFixed(1) :
                       opts.showPercent ? p.payload?.value : null;
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'space-between' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: p.color || p.fill }} />
                  <span style={{ color: tk.tertiary }}>{p.name || p.dataKey}</span>
                </span>
                <span style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 500 }}>
                  {fmtVal(p.value)}
                  {opts.showPercent && pct && <span style={{ color: tk.tertiary, marginLeft: 4 }}>({pct}%)</span>}
                </span>
              </div>
            );
          })}
          {total !== null && (
            <div style={{
              display: 'flex', justifyContent: 'space-between',
              marginTop: 4, paddingTop: 4, borderTop: `1px solid ${tk.grid}`,
              color: tk.tertiary, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em',
            }}>
              <span>Итого</span>
              <span style={{ fontVariantNumeric: 'tabular-nums', color: tk.primary, fontWeight: 600 }}>{fmtVal(total)}</span>
            </div>
          )}
        </div>
      </div>
    );
  };
}

function ChartsSection() {
  const { theme } = useTheme();
  const tk = chartTokens[theme];
  const Tt = makeRichTooltip(tk);
  const TtMulti = makeRichTooltip(tk, { showTotal: true });
  const TtPercent = makeRichTooltip(tk, { showPercent: true });

  return (
    <>
      {/* === MULTI-SERIES LINE — 5 серий разными цветами === */}
      <Section title="Multi-series · P&L разрез" description="Несколько метрик на одном графике. При hover — все значения за выбранную точку.">
        <ChartCard title="Выручка, маржа, расходы по месяцам" hint="6 каналов · ₽ млн" full
          action={<Tabs value="6m" onChange={() => {}} variant="segmented" items={[
            { value: '1m', label: '1М' }, { value: '3m', label: '3М' },
            { value: '6m', label: '6М' }, { value: '1y', label: '1Г' },
          ]} />}>
          <div className="flex items-center gap-4 mb-3 text-xs flex-wrap">
            <Legend dot={tk.pnl.revenue} label="Выручка" />
            <Legend dot={tk.pnl.margin} label="Маржинальная прибыль" />
            <Legend dot={tk.pnl.logistics} label="Логистика" />
            <Legend dot={tk.pnl.commission} label="Комиссии МП" />
            <Legend dot={tk.pnl.marketing} label="Маркетинг" />
          </div>
          <div className="h-64">
            <ResponsiveContainer>
              <LineChart data={pnlData} margin={{ top: 5, right: 10, bottom: 0, left: -15 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={tk.grid} vertical={false} />
                <XAxis dataKey="m" stroke={tk.axis} fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke={tk.axis} fontSize={11} tickLine={false} axisLine={false}
                  tickFormatter={(v) => `${v}M`} />
                <RTooltip content={Tt} cursor={{ stroke: tk.axis, strokeWidth: 1, strokeDasharray: '3 3' }} />
                <Line type="monotone" dataKey="revenue" name="Выручка" stroke={tk.pnl.revenue} strokeWidth={2.5} dot={{ r: 3, strokeWidth: 0, fill: tk.pnl.revenue }} activeDot={{ r: 5, strokeWidth: 2, stroke: tk.tooltip_bg, fill: tk.pnl.revenue }} />
                <Line type="monotone" dataKey="margin" name="Маржа" stroke={tk.pnl.margin} strokeWidth={2} dot={{ r: 2.5, strokeWidth: 0, fill: tk.pnl.margin }} activeDot={{ r: 4, strokeWidth: 2, stroke: tk.tooltip_bg, fill: tk.pnl.margin }} />
                <Line type="monotone" dataKey="logistics" name="Логистика" stroke={tk.pnl.logistics} strokeWidth={1.5} dot={{ r: 2, strokeWidth: 0, fill: tk.pnl.logistics }} activeDot={{ r: 4, strokeWidth: 2, stroke: tk.tooltip_bg, fill: tk.pnl.logistics }} />
                <Line type="monotone" dataKey="commission" name="Комиссии" stroke={tk.pnl.commission} strokeWidth={1.5} dot={{ r: 2, strokeWidth: 0, fill: tk.pnl.commission }} activeDot={{ r: 4, strokeWidth: 2, stroke: tk.tooltip_bg, fill: tk.pnl.commission }} />
                <Line type="monotone" dataKey="marketing" name="Маркетинг" stroke={tk.pnl.marketing} strokeWidth={1.5} dot={{ r: 2, strokeWidth: 0, fill: tk.pnl.marketing }} activeDot={{ r: 4, strokeWidth: 2, stroke: tk.tooltip_bg, fill: tk.pnl.marketing }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
      </Section>

      {/* === STACKED BAR — каналы маркетинга === */}
      <Section title="Stacked Bar · Структура расходов" description="Бюджет маркетинга по каналам, разложенный на доли.">
        <ChartCard title="Бюджет маркетинга по каналам" hint="6 каналов · тыс. ₽" full
          action={<Tabs value="abs" onChange={() => {}} variant="pill" items={[
            { value: 'abs', label: 'Абс' }, { value: 'pct', label: '%' },
          ]} />}>
          <div className="flex items-center gap-4 mb-3 text-xs flex-wrap">
            <Legend dot={tk.channels.internal} label="Внутренняя WB" />
            <Legend dot={tk.channels.yandex} label="Яндекс" />
            <Legend dot={tk.channels.vk} label="ВК" />
            <Legend dot={tk.channels.seedVk} label="Посевы ВК" />
            <Legend dot={tk.channels.seedAg} label="Посевы (агентство)" />
            <Legend dot={tk.channels.bloggers} label="Блогеры" />
          </div>
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={channelsData} margin={{ top: 5, right: 10, bottom: 0, left: -15 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={tk.grid} vertical={false} />
                <XAxis dataKey="m" stroke={tk.axis} fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke={tk.axis} fontSize={11} tickLine={false} axisLine={false}
                  tickFormatter={(v) => `${v}к`} />
                <RTooltip content={TtMulti} cursor={{ fill: theme === 'dark' ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }} />
                <Bar dataKey="internal"  name="Внутренняя WB"  stackId="a" fill={tk.channels.internal} />
                <Bar dataKey="yandex"    name="Яндекс"          stackId="a" fill={tk.channels.yandex} />
                <Bar dataKey="vk"        name="ВК"              stackId="a" fill={tk.channels.vk} />
                <Bar dataKey="seedVk"    name="Посевы ВК"       stackId="a" fill={tk.channels.seedVk} />
                <Bar dataKey="seedAg"    name="Посевы агентство" stackId="a" fill={tk.channels.seedAg} />
                <Bar dataKey="bloggers"  name="Блогеры"         stackId="a" fill={tk.channels.bloggers} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
      </Section>

      {/* === COMBO CHART — Bar + Line === */}
      <Section title="Combo · Bar + Line" description="Две оси: бары для абсолютных значений, линия для процента.">
        <ChartCard title="Выручка и маржинальность" hint="Выручка ₽ млн (бары) · Маржа % (линия)" full>
          <div className="flex items-center gap-4 mb-3 text-xs">
            <Legend dot={tk.pnl.revenue} label="Выручка, ₽ млн" />
            <Legend dot={tk.pnl.margin} label="Маржа, %" line />
          </div>
          <div className="h-64">
            <ResponsiveContainer>
              <ComposedChart data={comboData} margin={{ top: 5, right: 10, bottom: 0, left: -15 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={tk.grid} vertical={false} />
                <XAxis dataKey="m" stroke={tk.axis} fontSize={11} tickLine={false} axisLine={false} />
                <YAxis yAxisId="left" stroke={tk.axis} fontSize={11} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}M`} />
                <YAxis yAxisId="right" orientation="right" stroke={tk.axis} fontSize={11} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}%`} />
                <RTooltip content={Tt} cursor={{ fill: theme === 'dark' ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }} />
                <Bar yAxisId="left" dataKey="revenue" name="Выручка" fill={tk.pnl.revenue} radius={[3, 3, 0, 0]} maxBarSize={32} />
                <Line yAxisId="right" type="monotone" dataKey="marginPct" name="Маржа %" stroke={tk.pnl.margin} strokeWidth={2.5} dot={{ r: 4, strokeWidth: 2, stroke: tk.tooltip_bg, fill: tk.pnl.margin }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
      </Section>

      {/* === LINE / AREA / BAR / STACKED AREA === */}
      <Section title="Базовые типы" columns={2}>
        <ChartCard title="Продажи по каналам" hint="WB · Ozon · Сайт">
          <div className="flex items-center gap-3 mb-2 text-[11px]">
            <Legend dot={tk.palette.ink} label="WB" />
            <Legend dot={tk.palette.blue} label="Ozon" />
            <Legend dot={tk.palette.emerald} label="Сайт" />
          </div>
          <div className="h-44">
            <ResponsiveContainer>
              <LineChart data={lineData} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={tk.grid} vertical={false} />
                <XAxis dataKey="m" stroke={tk.axis} fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke={tk.axis} fontSize={11} tickLine={false} axisLine={false} />
                <RTooltip content={Tt} cursor={{ stroke: tk.axis, strokeWidth: 1, strokeDasharray: '3 3' }} />
                <Line type="monotone" dataKey="a" name="WB" stroke={tk.palette.ink} strokeWidth={2} dot={{ r: 3, strokeWidth: 0, fill: tk.palette.ink }} />
                <Line type="monotone" dataKey="b" name="Ozon" stroke={tk.palette.blue} strokeWidth={1.5} dot={{ r: 2.5, strokeWidth: 0, fill: tk.palette.blue }} />
                <Line type="monotone" dataKey="c" name="Сайт" stroke={tk.palette.emerald} strokeWidth={1.5} dot={{ r: 2.5, strokeWidth: 0, fill: tk.palette.emerald }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard title="Топ моделей по выручке" hint="₽ тыс · период август">
          <div className="h-44">
            <ResponsiveContainer>
              <BarChart data={barData} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={tk.grid} vertical={false} />
                <XAxis dataKey="name" stroke={tk.axis} fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke={tk.axis} fontSize={11} tickLine={false} axisLine={false} />
                <RTooltip content={Tt} cursor={{ fill: theme === 'dark' ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }} />
                <Bar dataKey="val" name="Выручка" radius={[4, 4, 0, 0]}>
                  {barData.map((_, i) => <Cell key={i} fill={[tk.palette.ink, tk.palette.blue, tk.palette.purple, tk.palette.teal, tk.palette.amber, tk.palette.rose][i]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard title="Динамика по каналам" hint="Stacked area">
          <div className="h-44">
            <ResponsiveContainer>
              <AreaChart data={stackedData} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={tk.grid} vertical={false} />
                <XAxis dataKey="m" stroke={tk.axis} fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke={tk.axis} fontSize={11} tickLine={false} axisLine={false} />
                <RTooltip content={TtMulti} />
                <Area type="monotone" dataKey="wb"   name="WB"   stackId="1" stroke={tk.palette.ink}     fill={tk.palette.ink}     fillOpacity={0.7} />
                <Area type="monotone" dataKey="ozon" name="Ozon" stackId="1" stroke={tk.palette.blue}    fill={tk.palette.blue}    fillOpacity={0.7} />
                <Area type="monotone" dataKey="sayt" name="Сайт" stackId="1" stroke={tk.palette.emerald} fill={tk.palette.emerald} fillOpacity={0.7} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard title="Прогноз на август" hint="С доверительным интервалом">
          <div className="h-44">
            <ResponsiveContainer>
              <AreaChart data={lineData} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={tk.grid} vertical={false} />
                <XAxis dataKey="m" stroke={tk.axis} fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke={tk.axis} fontSize={11} tickLine={false} axisLine={false} />
                <RTooltip content={Tt} />
                <Area type="monotone" dataKey="a" stroke={tk.palette.purple} fill={tk.palette.purple} fillOpacity={0.12} strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
      </Section>

      {/* === DOUGHNUT, GAUGE, FUNNEL === */}
      <Section title="Доли · Цели · Воронки" columns={3}>
        <ChartCard title="Каналы продаж" hint="Доли в обороте">
          <div className="h-40 relative">
            <ResponsiveContainer>
              <PieChart>
                <Pie data={donutData} dataKey="value" innerRadius={42} outerRadius={64} paddingAngle={2}>
                  {donutData.map((_, i) => <Cell key={i} fill={[tk.palette.ink, tk.palette.blue, tk.palette.emerald, tk.palette.amber][i]} />)}
                </Pie>
                <RTooltip content={TtPercent} />
              </PieChart>
            </ResponsiveContainer>
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="text-center">
                <div className={cx('text-[10px] uppercase tracking-wider', textL)}>Всего</div>
                <div className={cx('text-base tabular-nums font-medium', textP)}>4.82M</div>
              </div>
            </div>
          </div>
          <div className="space-y-1 mt-2">
            {donutData.map((d, i) => (
              <div key={d.name} className="flex items-center justify-between text-[11px]">
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-sm" style={{ background: [tk.palette.ink, tk.palette.blue, tk.palette.emerald, tk.palette.amber][i] }} />
                  <span className={textS}>{d.name}</span>
                </span>
                <span className={cx('tabular-nums', textM)}>{d.value}%</span>
              </div>
            ))}
          </div>
        </ChartCard>

        <ChartCard title="Цель квартала" hint="64% от плана 5M ₽">
          <div className="h-40 relative">
            <ResponsiveContainer>
              <RadialBarChart innerRadius="65%" outerRadius="95%" startAngle={180} endAngle={0}
                data={[{ name: 'val', value: 64, fill: tk.palette.purple }]}>
                <RadialBar dataKey="value" background={{ fill: tk.grid }} cornerRadius={6} />
              </RadialBarChart>
            </ResponsiveContainer>
            <div className="absolute inset-x-0 bottom-6 text-center pointer-events-none">
              <div className={cx('text-2xl tabular-nums font-medium', textP)}>64<span className={cx('text-base', textM)}>%</span></div>
              <div className={cx('text-[10px] uppercase tracking-wider', textL)}>3.2M из 5M ₽</div>
            </div>
          </div>
        </ChartCard>

        <ChartCard title="Воронка покупки" hint="WB · август 2026">
          <div className="space-y-1.5">
            {funnelData.map((f, i) => {
              const max = funnelData[0].value;
              const w = (f.value / max) * 100;
              const colors = [tk.palette.purple, tk.palette.blue, tk.palette.emerald, tk.palette.ink];
              return (
                <div key={f.name}>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className={textS}>{f.name}</span>
                    <span className={cx('tabular-nums', textM)}>{f.value.toLocaleString('ru-RU')}</span>
                  </div>
                  <div className="h-7 rounded bg-stone-100 dark:bg-stone-800 overflow-hidden relative">
                    <div className="h-full transition-all" style={{ width: `${w}%`, background: colors[i] }} />
                  </div>
                  {i < funnelData.length - 1 && (
                    <div className={cx('text-[10px] mt-0.5 text-right tabular-nums', textL)}>
                      → {((funnelData[i+1].value / f.value) * 100).toFixed(1)}%
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </ChartCard>
      </Section>

      {/* === CALENDAR HEATMAP === */}
      <Section title="Calendar Heatmap" description="Активность по дням за период.">
        <ChartCard title="Активность контент-завода" hint="Публикации в день · 24 недели" full>
          <CalendarHeatmap data={heatmapData} tk={tk} />
        </ChartCard>
      </Section>

      {/* === SPARKLINE KPI ROW === */}
      <Section title="Sparklines · KPI cards" description="Компактные графики для инлайн-индикаторов в карточках.">
        <Demo label="Sparkline KPI ряд" full padded={false}>
          <div className="grid grid-cols-4 gap-3 w-full p-5">
            <SparkCard label="WB GMV"    value="2.94M" trend={14.2} data={lineData.map(d => d.a)} tk={tk} color={tk.palette.ink} />
            <SparkCard label="Ozon GMV"  value="1.18M" trend={-2.4} data={lineData.map(d => d.b)} tk={tk} color={tk.palette.blue} />
            <SparkCard label="Сайт GMV"  value="0.71M" trend={28.1} data={lineData.map(d => d.c)} tk={tk} color={tk.palette.emerald} />
            <SparkCard label="Возвраты"  value="3.2%"  trend={-0.8} data={[12,11,10,9,8,7,6,5]}    tk={tk} color={tk.palette.rose} positive />
          </div>
        </Demo>
        <Demo label="Inline sparkline в строке таблицы" full padded={false}>
          <div className={cx('w-full p-5')}>
            <div className={cx('rounded-lg overflow-hidden', surface)}>
              <table className="w-full text-sm">
                <thead className={cx(surfaceMuted, 'border-b', borderD)}>
                  <tr className={cx('text-left text-[11px] uppercase tracking-wider', textM)}>
                    <th className="px-3 py-2 font-medium">Модель</th>
                    <th className="px-3 py-2 font-medium text-right">Выручка</th>
                    <th className="px-3 py-2 font-medium text-center w-24">Тренд 8м</th>
                    <th className="px-3 py-2 font-medium text-right w-20">Δ</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { name: 'Vuki',  rev: '2.84M', data: [12, 19, 15, 27, 32, 28, 38, 42], delta: 14.2, color: tk.palette.ink },
                    { name: 'Vivi',  rev: '1.92M', data: [18, 16, 22, 21, 19, 24, 28, 26], delta: 8.1, color: tk.palette.blue },
                    { name: 'Vesta', rev: '0.78M', data: [22, 18, 14, 12, 11, 9, 8, 7],    delta: -28.4, color: tk.palette.rose },
                    { name: 'Vera',  rev: '0.64M', data: [8, 10, 14, 18, 22, 24, 26, 32],  delta: 42.1, color: tk.palette.emerald },
                  ].map(r => (
                    <tr key={r.name} className={cx('border-b last:border-0', borderD, hoverRow)}>
                      <td className={cx('px-3 py-2 font-medium', textP)}>{r.name}</td>
                      <td className={cx('px-3 py-2 text-right tabular-nums', textS)}>{r.rev}</td>
                      <td className="px-3 py-2">
                        <div className="h-6 w-24 mx-auto">
                          <ResponsiveContainer>
                            <LineChart data={r.data.map((v, i) => ({ i, v }))}>
                              <Line type="monotone" dataKey="v" stroke={r.color} strokeWidth={1.5} dot={false} />
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                      </td>
                      <td className="px-3 py-2 text-right">
                        <Badge variant={r.delta > 0 ? 'emerald' : 'red'} compact>
                          {r.delta > 0 ? '+' : ''}{r.delta}%
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </Demo>
      </Section>
    </>
  );
}

function Legend({ dot, label, line }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {line ? (
        <span className="w-3 h-0.5 rounded" style={{ background: dot }} />
      ) : (
        <span className="w-2 h-2 rounded-sm" style={{ background: dot }} />
      )}
      <span className={textS}>{label}</span>
    </span>
  );
}

function CalendarHeatmap({ data, tk }) {
  const weeks = useMemo(() => {
    const w = []; for (let i = 0; i < data.length; i += 7) w.push(data.slice(i, i + 7));
    return w;
  }, [data]);
  const max = Math.max(...data.map(d => d.value));
  const colorFor = (v) => {
    if (v === 0) return tk.grid;
    const intensity = v / max;
    if (intensity > 0.75) return tk.primary;
    if (intensity > 0.5) return tk.secondary;
    if (intensity > 0.25) return tk.tertiary;
    return tk.grid;
  };
  const days = ['пн', '', 'ср', '', 'пт', '', ''];
  return (
    <div className="flex gap-2 items-start overflow-x-auto">
      <div className="flex flex-col gap-[3px] pt-3">
        {days.map((d, i) => <div key={i} className="h-3 text-[9px] flex items-center" style={{ color: tk.tertiary }}>{d}</div>)}
      </div>
      <div className="flex gap-[3px]">
        {weeks.map((w, i) => (
          <div key={i} className="flex flex-col gap-[3px]">
            {i % 4 === 0 && <div className="h-3 text-[9px]" style={{ color: tk.tertiary }}>
              {w[0]?.date.toLocaleDateString('ru-RU', { month: 'short' })}
            </div>}
            {i % 4 !== 0 && <div className="h-3" />}
            {w.map((d, j) => (
              <Tooltip key={j} text={`${d.date.toLocaleDateString('ru-RU')} · ${d.value} публ.`}>
                <div className="w-3 h-3 rounded-[2px]" style={{ background: colorFor(d.value) }} />
              </Tooltip>
            ))}
          </div>
        ))}
      </div>
      <div className="flex items-center gap-1.5 ml-auto pt-3">
        <span className="text-[10px]" style={{ color: tk.tertiary }}>меньше</span>
        {[tk.grid, tk.tertiary, tk.secondary, tk.primary].map((c, i) => (
          <div key={i} className="w-3 h-3 rounded-[2px]" style={{ background: c }} />
        ))}
        <span className="text-[10px]" style={{ color: tk.tertiary }}>больше</span>
      </div>
    </div>
  );
}

function SparkCard({ label, value, trend, data, tk, color, negative, positive }) {
  const isGood = positive ? trend < 0 : trend > 0;
  const c = color || (isGood ? tk.pos : tk.neg);
  return (
    <div className={cx('rounded-lg p-4', surface)}>
      <div className={cx('text-[11px] uppercase tracking-wider font-medium mb-1.5', textM)}>{label}</div>
      <div className="flex items-end justify-between gap-3">
        <div className="min-w-0">
          <div className={cx('text-2xl tabular-nums font-medium leading-none', textP)}>{value}</div>
          <div className="mt-1.5">
            <Badge variant={isGood ? 'emerald' : 'red'} compact>
              {trend > 0 ? '+' : ''}{trend}%
            </Badge>
          </div>
        </div>
        <div className="h-10 w-20 shrink-0">
          <ResponsiveContainer>
            <LineChart data={data.map((v, i) => ({ i, v }))} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
              <Line type="monotone" dataKey="v" stroke={c} strokeWidth={1.75} dot={false}
                isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

// =========================================================
// SECTION 6: LAYOUT (Tabs, Breadcrumbs, Stepper)
// =========================================================

function Tabs({ value, onChange, items, variant = 'underline' }) {
  if (variant === 'underline') {
    return (
      <div className={cx('flex items-center gap-1 border-b', borderD)}>
        {items.map(it => (
          <button key={it.value} onClick={() => onChange(it.value)}
            className={cx('px-3 py-2 text-sm transition-colors relative -mb-px border-b-2',
              value === it.value
                ? cx('border-stone-900 dark:border-stone-50', textP, 'font-medium')
                : cx('border-transparent', textS, 'hover:text-stone-900 dark:hover:text-stone-50'))}>
            {it.label}
            {it.badge !== undefined && (
              <span className={cx('ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] rounded-full tabular-nums',
                value === it.value ? 'bg-stone-900 text-white dark:bg-stone-50 dark:text-stone-900' : 'bg-stone-100 dark:bg-stone-800')}>
                {it.badge}
              </span>
            )}
          </button>
        ))}
      </div>
    );
  }
  if (variant === 'pill') {
    return (
      <div className={cx('inline-flex items-center gap-1 p-0.5 rounded-md', 'bg-stone-100 dark:bg-stone-800')}>
        {items.map(it => (
          <button key={it.value} onClick={() => onChange(it.value)}
            className={cx('px-3 py-1 text-xs rounded transition-colors',
              value === it.value
                ? cx('bg-white dark:bg-stone-900', textP, 'shadow-sm font-medium')
                : textS)}>
            {it.label}
          </button>
        ))}
      </div>
    );
  }
  // segmented
  return (
    <div className={cx('inline-flex items-center rounded-md border overflow-hidden', borderD)}>
      {items.map((it, i) => (
        <button key={it.value} onClick={() => onChange(it.value)}
          className={cx('px-3 py-1.5 text-xs transition-colors', i > 0 && 'border-l ' + borderD,
            value === it.value
              ? 'bg-stone-900 text-white dark:bg-stone-50 dark:text-stone-900'
              : cx('bg-white dark:bg-stone-900', textS, hoverBtn))}>
          {it.label}
        </button>
      ))}
    </div>
  );
}

function Breadcrumbs({ items }) {
  return (
    <nav className="flex items-center gap-1.5 text-sm">
      {items.map((it, i) => (
        <React.Fragment key={i}>
          {i > 0 && <ChevronRight className={cx('w-3 h-3', textL)} />}
          <a className={cx(i === items.length - 1 ? cx(textP, 'font-medium') : textM, 'hover:underline')}>
            {it}
          </a>
        </React.Fragment>
      ))}
    </nav>
  );
}

function Stepper({ steps, current }) {
  return (
    <div className="flex items-center w-full">
      {steps.map((s, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <React.Fragment key={i}>
            <div className="flex flex-col items-center gap-1.5">
              <div className={cx('w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium tabular-nums transition-colors',
                done ? 'bg-stone-900 text-white dark:bg-stone-50 dark:text-stone-900'
                : active ? cx('ring-2 ring-stone-900 dark:ring-stone-50', textP, 'bg-white dark:bg-stone-900')
                : cx('bg-stone-100 dark:bg-stone-800', textM))}>
                {done ? <Check className="w-3.5 h-3.5" /> : i + 1}
              </div>
              <span className={cx('text-[11px]', active ? cx(textP, 'font-medium') : textM)}>{s}</span>
            </div>
            {i < steps.length - 1 && <div className={cx('flex-1 h-px mt-[-16px]', done ? 'bg-stone-900 dark:bg-stone-50' : 'bg-stone-200 dark:bg-stone-700')} />}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function PageHeader({ title, kicker, breadcrumbs, actions, status }) {
  return (
    <div className={cx('px-6 py-4 border-b', borderD, surface)}>
      {breadcrumbs && <div className="mb-1.5"><Breadcrumbs items={breadcrumbs} /></div>}
      {kicker && <div className={cx('text-[11px] uppercase tracking-wider mb-0.5', textL)}>{kicker}</div>}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 style={{ fontFamily: "'Instrument Serif', serif" }} className={cx('text-3xl', textP)}>{title}</h1>
          {status}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}

function LayoutSection() {
  const [tab1, setTab1] = useState('description');
  const [tab2, setTab2] = useState('day');
  const [tab3, setTab3] = useState('list');

  return (
    <>
      <Section title="Tabs — три варианта">
        <Demo label="Underline (для основной навигации внутри карточки)" full>
          <Tabs value={tab1} onChange={setTab1} variant="underline" items={[
            { value: 'description', label: 'Описание' },
            { value: 'attributes', label: 'Атрибуты' },
            { value: 'sku', label: 'SKU', badge: 24 },
            { value: 'content', label: 'Контент' },
          ]} />
        </Demo>
        <Demo label="Pill (для переключения вьюх)" full>
          <Tabs value={tab2} onChange={setTab2} variant="pill" items={[
            { value: 'day', label: 'День' }, { value: 'week', label: 'Неделя' },
            { value: 'month', label: 'Месяц' }, { value: 'year', label: 'Год' },
          ]} />
        </Demo>
        <Demo label="Segmented (для переключения форматов отображения)" full>
          <Tabs value={tab3} onChange={setTab3} variant="segmented" items={[
            { value: 'list', label: 'Список' }, { value: 'grid', label: 'Сетка' },
            { value: 'kanban', label: 'Канбан' },
          ]} />
        </Demo>
      </Section>

      <Section title="Breadcrumbs">
        <Demo label="Иерархия" full>
          <Breadcrumbs items={['Hub', 'Каталог', 'Бюстгальтеры', 'Vuki']} />
        </Demo>
      </Section>

      <Section title="Stepper" description="Для wizard'ов и многошаговых форм.">
        <Demo label="Создание модели — 4 шага" full>
          <div className="w-full px-12">
            <Stepper steps={['Основа', 'Атрибуты', 'Артикулы', 'Публикация']} current={2} />
          </div>
        </Demo>
      </Section>

      <Section title="PageHeader">
        <Demo label="С breadcrumbs, status, actions" full padded={false}>
          <div className="w-full">
            <PageHeader
              kicker="МОДЕЛЬ"
              title="Vuki — основа коллекции"
              breadcrumbs={['Hub', 'Каталог', 'Бюстгальтеры']}
              status={<StatusBadge statusId={1} />}
              actions={<>
                <Button variant="secondary" icon={Copy} size="sm">Дублировать</Button>
                <Button icon={Save} size="sm">Сохранить</Button>
              </>}
            />
          </div>
        </Demo>
      </Section>
    </>
  );
}

// =========================================================
// SECTION 7: OVERLAYS
// =========================================================

function Modal({ open, onClose, title, children, footer, size = 'md' }) {
  if (!open) return null;
  const sizes = { sm: 'max-w-sm', md: 'max-w-lg', lg: 'max-w-2xl', xl: 'max-w-4xl' };
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 bg-stone-900/40 dark:bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        className={cx('w-full', sizes[size], 'rounded-lg shadow-xl', surface)}>
        <div className={cx('flex items-center justify-between px-5 py-3.5 border-b', borderD)}>
          <h3 className={cx('text-base font-medium', textP)}>{title}</h3>
          <button onClick={onClose} className={cx('p-1 rounded', hoverBtn)}>
            <X className={cx('w-4 h-4', textM)} />
          </button>
        </div>
        <div className="p-5">{children}</div>
        {footer && <div className={cx('px-5 py-3 border-t flex justify-end gap-2', borderD)}>{footer}</div>}
      </div>
    </div>
  );
}

function Drawer({ open, onClose, title, children, footer, side = 'right' }) {
  if (!open) return null;
  const sides = {
    right: 'right-0 top-0 bottom-0 w-[420px] border-l',
    bottom: 'left-0 right-0 bottom-0 h-[60vh] border-t rounded-t-lg',
  };
  return (
    <div className="fixed inset-0 z-50 bg-stone-900/40 dark:bg-black/60" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        className={cx('absolute', sides[side], surface, borderD)}>
        <div className={cx('flex items-center justify-between px-5 py-3.5 border-b', borderD)}>
          <h3 className={cx('text-base font-medium', textP)}>{title}</h3>
          <button onClick={onClose} className={cx('p-1 rounded', hoverBtn)}>
            <X className={cx('w-4 h-4', textM)} />
          </button>
        </div>
        <div className="p-5 overflow-y-auto" style={{ maxHeight: 'calc(100% - 110px)' }}>{children}</div>
        {footer && <div className={cx('absolute bottom-0 left-0 right-0 px-5 py-3 border-t flex justify-end gap-2', borderD, surface)}>{footer}</div>}
      </div>
    </div>
  );
}

function Popover({ trigger, children, position = 'bottom-start' }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', h); return () => document.removeEventListener('mousedown', h);
  }, []);
  const positions = {
    'bottom-start': 'top-full left-0 mt-1.5',
    'bottom-end': 'top-full right-0 mt-1.5',
    'top-start': 'bottom-full left-0 mb-1.5',
  };
  return (
    <div ref={ref} className="relative inline-block">
      <span onClick={() => setOpen(!open)}>{trigger}</span>
      {open && (
        <div className={cx('absolute z-40 rounded-lg shadow-sm min-w-48', surface, positions[position])}>
          {children}
        </div>
      )}
    </div>
  );
}

function DropdownMenu({ items, trigger }) {
  return (
    <Popover trigger={trigger} position="bottom-end">
      <div className="py-1">
        {items.map((it, i) => it.divider ? (
          <div key={i} className={cx('h-px my-1 mx-2', 'bg-stone-200 dark:bg-stone-800')} />
        ) : (
          <button key={i} onClick={it.onClick}
            className={cx('w-full flex items-center gap-2 px-3 py-1.5 text-sm text-left',
              hoverRow, it.danger ? 'text-rose-600 dark:text-rose-400' : textS)}>
            {it.icon && <it.icon className="w-3.5 h-3.5" />}
            <span className="flex-1">{it.label}</span>
            {it.shortcut && <Kbd>{it.shortcut}</Kbd>}
          </button>
        ))}
      </div>
    </Popover>
  );
}

function ContextMenu({ items, children }) {
  const [pos, setPos] = useState(null);
  const ref = useRef(null);
  useEffect(() => {
    const h = () => setPos(null);
    document.addEventListener('click', h); return () => document.removeEventListener('click', h);
  }, []);
  return (
    <>
      <div ref={ref} onContextMenu={(e) => { e.preventDefault(); setPos({ x: e.clientX, y: e.clientY }); }}>
        {children}
      </div>
      {pos && (
        <div className={cx('fixed z-50 rounded-lg shadow-sm min-w-48 py-1', surface)}
          style={{ left: pos.x, top: pos.y }}>
          {items.map((it, i) => it.divider ? (
            <div key={i} className={cx('h-px my-1 mx-2', 'bg-stone-200 dark:bg-stone-800')} />
          ) : (
            <button key={i} onClick={() => { it.onClick?.(); setPos(null); }}
              className={cx('w-full flex items-center gap-2 px-3 py-1.5 text-sm text-left',
                hoverRow, it.danger ? 'text-rose-600 dark:text-rose-400' : textS)}>
              {it.icon && <it.icon className="w-3.5 h-3.5" />}
              <span className="flex-1">{it.label}</span>
              {it.shortcut && <Kbd>{it.shortcut}</Kbd>}
            </button>
          ))}
        </div>
      )}
    </>
  );
}

function CommandPalette({ open, onClose }) {
  const [q, setQ] = useState('');
  if (!open) return null;
  const results = [
    { type: 'МОДЕЛЬ', label: 'Vuki — основа коллекции', sub: 'Бюстгальтер · 24 артикула' },
    { type: 'МОДЕЛЬ', label: 'Vivi — Push-up', sub: 'Бюстгальтер · 18 артикулов' },
    { type: 'ЦВЕТ', label: 'Чёрный', sub: '#1C1917 · 142 SKU' },
    { type: 'СТРАНИЦА', label: 'Аналитика → Продажи', sub: '/analytics/sales' },
  ];
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh] bg-stone-900/40 dark:bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        className={cx('w-full max-w-xl rounded-xl shadow-2xl overflow-hidden', surface)}>
        <div className={cx('flex items-center gap-2 px-3.5 py-3 border-b', borderD)}>
          <Search className={cx('w-4 h-4', textL)} />
          <input autoFocus value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Поиск по моделям, цветам, страницам…"
            className={cx('flex-1 bg-transparent outline-none text-sm', textP, 'placeholder:text-stone-400')} />
          <Kbd>esc</Kbd>
        </div>
        <div className="max-h-96 overflow-y-auto">
          {results.map((r, i) => (
            <button key={i} className={cx('w-full px-3.5 py-2.5 flex items-center gap-3 text-left', hoverRow)}>
              <span className={cx('text-[10px] uppercase tracking-wider w-16', textL)}>{r.type}</span>
              <div className="flex-1">
                <div className={cx('text-sm', textP)}>{r.label}</div>
                <div className={cx('text-xs', textM)}>{r.sub}</div>
              </div>
              <ArrowRight className={cx('w-3.5 h-3.5', textL)} />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function OverlaysSection() {
  const [m1, setM1] = useState(false);
  const [d1, setD1] = useState(false);
  const [d2, setD2] = useState(false);
  const [cmd, setCmd] = useState(false);

  return (
    <>
      <Section title="Modal" columns={2}>
        <Demo label="Открыть модалку">
          <Button onClick={() => setM1(true)}>Удалить модель</Button>
          <Modal open={m1} onClose={() => setM1(false)} title="Удаление модели"
            footer={<>
              <Button variant="secondary" onClick={() => setM1(false)}>Отмена</Button>
              <Button variant="danger" onClick={() => setM1(false)}>Удалить</Button>
            </>}>
            <div className={cx('text-sm', textS)}>
              Модель <span className="font-mono text-xs">Vuki</span> и все её 24 артикула будут перемещены в архив.
              Это действие можно отменить в течение 7 дней.
            </div>
          </Modal>
        </Demo>
        <Demo label="CommandPalette (⌘K)">
          <Button variant="secondary" icon={Command} onClick={() => setCmd(true)}>Открыть поиск</Button>
          <CommandPalette open={cmd} onClose={() => setCmd(false)} />
        </Demo>
      </Section>

      <Section title="Drawer / Sheet" columns={2}>
        <Demo label="Right Drawer">
          <Button variant="secondary" onClick={() => setD1(true)}>Открыть справа</Button>
          <Drawer open={d1} onClose={() => setD1(false)} title="Фильтры"
            footer={<>
              <Button variant="ghost" size="sm">Сбросить</Button>
              <Button size="sm" onClick={() => setD1(false)}>Применить</Button>
            </>}>
            <div className="space-y-4">
              <SelectField label="Категория" options={[{ id: '1', nazvanie: 'Бюстгальтер' }]} />
              <MultiSelectField label="Размеры" value={['S','M']} options={['XS','S','M','L','XL']} />
              <DatePicker label="Период" range />
            </div>
          </Drawer>
        </Demo>
        <Demo label="Bottom Sheet">
          <Button variant="secondary" onClick={() => setD2(true)}>Открыть снизу</Button>
          <Drawer open={d2} onClose={() => setD2(false)} title="Bulk-редактирование" side="bottom">
            <div className="space-y-4">
              <SelectField label="Изменить статус для 12 SKU" options={[{ id: '1', nazvanie: 'В продаже' }]} />
              <TextField label="Комментарий" />
            </div>
          </Drawer>
        </Demo>
      </Section>

      <Section title="Popover, Dropdown, Context menu" columns={3}>
        <Demo label="Popover">
          <Popover trigger={<Button variant="secondary" icon={Filter}>Фильтр</Button>}>
            <div className="p-3 space-y-2 w-56">
              <Checkbox checked label="В продаже" />
              <Checkbox label="Запуск" />
              <Checkbox label="Архив" />
            </div>
          </Popover>
        </Demo>
        <Demo label="Dropdown menu">
          <DropdownMenu trigger={<Button variant="secondary" icon={MoreHorizontal} />}
            items={[
              { label: 'Редактировать', icon: Edit3, shortcut: 'E' },
              { label: 'Дублировать', icon: Copy },
              { label: 'Экспорт', icon: Download },
              { divider: true },
              { label: 'Удалить', icon: Trash2, danger: true, shortcut: 'D' },
            ]} />
        </Demo>
        <Demo label="Context menu (right-click)">
          <ContextMenu items={[
            { label: 'Открыть', icon: ExternalLink },
            { label: 'Скопировать ссылку', icon: Copy },
            { divider: true },
            { label: 'Удалить', icon: Trash2, danger: true },
          ]}>
            <div className={cx('px-4 py-3 rounded-md text-sm cursor-pointer', surfaceMuted, textS)}>
              Кликни правой кнопкой
            </div>
          </ContextMenu>
        </Demo>
      </Section>
    </>
  );
}

// =========================================================
// SECTION 8: FEEDBACK (Toast, Alert, Empty, Loading)
// =========================================================

function Toast({ variant = 'info', title, message, onClose }) {
  const variants = {
    success: { icon: CheckCircle, c: 'text-emerald-500' },
    error: { icon: XCircle, c: 'text-rose-500' },
    info: { icon: Info, c: 'text-blue-500' },
    warning: { icon: AlertTriangle, c: 'text-amber-500' },
    loading: { icon: Loader2, c: 'text-stone-400 animate-spin' },
  };
  const v = variants[variant];
  return (
    <div className={cx('rounded-md shadow-sm flex items-start gap-3 p-3 min-w-72 max-w-sm', surface)}>
      <v.icon className={cx('w-4 h-4 mt-0.5 shrink-0', v.c)} />
      <div className="flex-1 min-w-0">
        {title && <div className={cx('text-sm font-medium', textP)}>{title}</div>}
        {message && <div className={cx('text-xs mt-0.5', textM)}>{message}</div>}
      </div>
      {onClose && (
        <button onClick={onClose} className={cx('p-0.5 rounded', hoverBtn)}>
          <X className={cx('w-3 h-3', textL)} />
        </button>
      )}
    </div>
  );
}

function Alert({ variant = 'info', title, children, action }) {
  const variants = {
    info: { bg: 'bg-blue-50 dark:bg-blue-950/40', border: 'border-blue-200 dark:border-blue-800', text: 'text-blue-900 dark:text-blue-200', icon: Info, iconC: 'text-blue-500' },
    success: { bg: 'bg-emerald-50 dark:bg-emerald-950/40', border: 'border-emerald-200 dark:border-emerald-800', text: 'text-emerald-900 dark:text-emerald-200', icon: CheckCircle, iconC: 'text-emerald-500' },
    warning: { bg: 'bg-amber-50 dark:bg-amber-950/40', border: 'border-amber-200 dark:border-amber-800', text: 'text-amber-900 dark:text-amber-200', icon: AlertTriangle, iconC: 'text-amber-500' },
    error: { bg: 'bg-rose-50 dark:bg-rose-950/40', border: 'border-rose-200 dark:border-rose-800', text: 'text-rose-900 dark:text-rose-200', icon: AlertCircle, iconC: 'text-rose-500' },
  };
  const v = variants[variant];
  return (
    <div className={cx('rounded-md p-3 border flex items-start gap-3', v.bg, v.border)}>
      <v.icon className={cx('w-4 h-4 mt-0.5 shrink-0', v.iconC)} />
      <div className="flex-1">
        {title && <div className={cx('text-sm font-medium', v.text)}>{title}</div>}
        <div className={cx('text-xs mt-0.5', v.text, 'opacity-80')}>{children}</div>
      </div>
      {action}
    </div>
  );
}

function EmptyState({ icon: Icon = Box, title, description, action }) {
  return (
    <div className="text-center py-10">
      <Icon className={cx('w-8 h-8 mx-auto mb-3', textL)} />
      <div className={cx('text-sm font-medium mb-1', textP)}>{title}</div>
      {description && <div className={cx('text-xs italic mb-3 max-w-sm mx-auto', textM)}>{description}</div>}
      {action}
    </div>
  );
}

function FeedbackSection() {
  return (
    <>
      <Section title="Toast notifications" description="Появляются в нижнем правом углу. Auto-dismiss 4-5 сек." columns={2}>
        <Demo label="Success">
          <Toast variant="success" title="Сохранено" message="Vuki: 24 артикула обновлены" onClose={() => {}} />
        </Demo>
        <Demo label="Error">
          <Toast variant="error" title="Ошибка отправки" message="WB API: 503 Service Unavailable" onClose={() => {}} />
        </Demo>
        <Demo label="Info">
          <Toast variant="info" title="Синхронизация" message="Получены данные за последний час" onClose={() => {}} />
        </Demo>
        <Demo label="Loading">
          <Toast variant="loading" title="Загружаем фото…" message="3 из 12" />
        </Demo>
      </Section>

      <Section title="Inline alerts" description="Внутри карточек, для контекстных сообщений." columns={2}>
        <Demo label="Info">
          <Alert variant="info" title="Подсказка">Заполненность модели влияет на возможность публикации на маркетплейсах.</Alert>
        </Demo>
        <Demo label="Success">
          <Alert variant="success" title="Опубликовано">Модель Vuki синхронизирована с WB и Ozon.</Alert>
        </Demo>
        <Demo label="Warning">
          <Alert variant="warning" title="Низкие остатки">12 SKU имеют остаток меньше 20 штук.</Alert>
        </Demo>
        <Demo label="Error">
          <Alert variant="error" title="Ошибка валидации">Цена розничная не может быть меньше себестоимости.</Alert>
        </Demo>
      </Section>

      <Section title="Empty states" columns={2}>
        <Demo label="Пустой список" full padded={false}>
          <div className="w-full"><EmptyState
            icon={Inbox}
            title="Нет уведомлений"
            description="Когда что-то изменится в каталоге или появится новая задача — увидишь здесь."
            action={<Button size="sm" variant="secondary">Настроить</Button>} /></div>
        </Demo>
        <Demo label="Не нашли результаты" full padded={false}>
          <div className="w-full"><EmptyState
            icon={Search}
            title="Ничего не найдено"
            description="Попробуй другой запрос или сбрось фильтры."
            action={<Button size="sm" variant="ghost">Сбросить</Button>} /></div>
        </Demo>
      </Section>

      <Section title="Loading states">
        <Demo label="Skeleton" full>
          <div className="w-full space-y-3">
            <div className={cx('rounded-lg p-4', surface)}>
              <div className="flex items-center gap-3 mb-3">
                <Skeleton className="w-10 h-10 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-3 w-32" />
                  <Skeleton className="h-2.5 w-20" />
                </div>
              </div>
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-3/4 mt-2" />
            </div>
          </div>
        </Demo>
      </Section>
    </>
  );
}

// =========================================================
// APP — sidebar nav + topbar with theme toggle
// =========================================================

const SECTIONS = [
  { id: 'foundation', label: 'Foundation', icon: Palette, comp: Foundation, group: 'Основа' },
  { id: 'atoms', label: 'Atoms', icon: Box, comp: AtomsSection, group: 'Основа' },
  { id: 'forms', label: 'Forms', icon: Edit3, comp: FormsSection, group: 'Основа' },
  { id: 'data', label: 'Data display', icon: BarChart3, comp: DataSection, group: 'Данные' },
  { id: 'charts', label: 'Charts', icon: TrendingUp, comp: ChartsSection, group: 'Данные' },
  { id: 'layout', label: 'Layout', icon: Layers, comp: LayoutSection, group: 'Структура' },
  { id: 'overlays', label: 'Overlays', icon: Copy, comp: OverlaysSection, group: 'Структура' },
  { id: 'feedback', label: 'Feedback', icon: Bell, comp: FeedbackSection, group: 'Структура' },
];

export default function App() {
  const [theme, setTheme] = useState('light');
  const [active, setActive] = useState('foundation');
  const Active = SECTIONS.find(s => s.id === active)?.comp || Foundation;
  const grouped = SECTIONS.reduce((a, s) => { (a[s.group] = a[s.group] || []).push(s); return a; }, {});

  return (
    <ThemeContext.Provider value={{ theme, toggle: () => setTheme(theme === 'light' ? 'dark' : 'light') }}>
      <div className={theme === 'dark' ? 'dark' : ''}>
        <style>{`
          @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Instrument+Serif:ital@0;1&display=swap');
          html, body { font-family: 'DM Sans', system-ui, sans-serif; }
          input[type=checkbox], input[type=radio] { accent-color: #1C1917; }
          .dark input[type=checkbox], .dark input[type=radio] { accent-color: #FAFAF9; }
        `}</style>
        <div className="min-h-screen bg-stone-50/40 dark:bg-stone-950 text-stone-900 dark:text-stone-50 antialiased flex">
          {/* SIDEBAR */}
          <aside className={cx('w-60 shrink-0 h-screen sticky top-0 overflow-y-auto py-4',
            'border-r', borderD, surfaceMuted)}>
            <div className="px-4 pb-3 mb-2 border-b border-stone-200 dark:border-stone-800">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-7 h-7 rounded bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center">
                  <Sparkles className="w-3.5 h-3.5 text-white" />
                </div>
                <div>
                  <div style={{ fontFamily: "'Instrument Serif', serif" }} className={cx('text-base leading-none', textP)}>
                    <em className="italic">Wookiee</em>
                  </div>
                  <div className={cx('text-[10px] uppercase tracking-wider mt-0.5', textL)}>DS v2 · Foundation</div>
                </div>
              </div>
            </div>

            {Object.entries(grouped).map(([group, items]) => (
              <div key={group} className="mb-3">
                <div className={cx('text-[10px] uppercase tracking-wider px-4 py-1.5', textL)}>{group}</div>
                {items.map(s => (
                  <button key={s.id} onClick={() => setActive(s.id)}
                    className={cx('w-full flex items-center gap-2.5 px-4 py-1.5 text-sm transition-colors',
                      active === s.id
                        ? cx('bg-stone-900 dark:bg-stone-50 text-white dark:text-stone-900 font-medium')
                        : cx(textS, hoverBtn))}>
                    <s.icon className="w-3.5 h-3.5" />
                    <span>{s.label}</span>
                  </button>
                ))}
              </div>
            ))}

            <div className="px-4 pt-3 mt-3 border-t border-stone-200 dark:border-stone-800">
              <div className={cx('text-[10px] uppercase tracking-wider mb-2', textL)}>Тема</div>
              <button onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
                className={cx('w-full flex items-center justify-between rounded-md px-3 py-1.5 text-sm border',
                  borderD, hoverBtn, textS)}>
                <span className="flex items-center gap-2">
                  {theme === 'light' ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
                  {theme === 'light' ? 'Светлая' : 'Тёмная'}
                </span>
                <span className={cx('text-[10px] font-mono', textL)}>⌘⇧L</span>
              </button>
            </div>
          </aside>

          {/* MAIN */}
          <main className="flex-1 min-w-0">
            <div className={cx('h-14 px-6 border-b flex items-center justify-between sticky top-0 z-30', borderD, surface)}>
              <div className="flex items-center gap-3">
                <div className={cx('text-[11px] uppercase tracking-wider', textL)}>Wookiee Hub · Design System</div>
                <ChevronRight className={cx('w-3 h-3', textL)} />
                <div className={cx('text-sm font-medium', textP)}>{SECTIONS.find(s => s.id === active)?.label}</div>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="secondary" size="sm" icon={Download}>Экспорт токенов</Button>
                <IconButton icon={theme === 'light' ? Moon : Sun} title="Переключить тему"
                  onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')} />
              </div>
            </div>

            <div className="px-8 py-8 max-w-6xl">
              <div className="mb-8">
                <div className={cx('text-[11px] uppercase tracking-wider mb-1', textL)}>Дизайн-система v2</div>
                <h1 style={{ fontFamily: "'Instrument Serif', serif" }} className={cx('text-4xl mb-2', textP)}>
                  <em className="italic">{SECTIONS.find(s => s.id === active)?.label}</em>
                </h1>
                <div className={cx('text-sm max-w-2xl', textM)}>
                  Все компоненты — копи-пастабельные, адаптированы под светлую и тёмную темы через Tailwind <code className="font-mono text-xs">dark:</code> префиксы. Переключи тему вверху справа, чтобы увидеть оба варианта.
                </div>
              </div>
              <Active />
            </div>
          </main>
        </div>
      </div>
    </ThemeContext.Provider>
  );
}
