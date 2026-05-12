import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Search, Plus, X, Check, ChevronDown, ChevronRight, ChevronLeft,
  MoreHorizontal, Edit3, Trash2, Copy, Save, Archive, Filter, GripVertical,
  Bell, Calendar, Mail, Hash, AtSign, Smile, Paperclip, Send, Reply,
  Sun, Moon, Sparkles, Inbox, MessageSquare, Activity, Zap,
  Package, Layers, FileText, Image as ImageIcon, Camera, Truck,
  AlertCircle, CheckCircle, Info, AlertTriangle, Heart, ThumbsUp,
  Users, User, Clock, ArrowUpRight, ExternalLink, ChevronsRight,
  Tag as TagIcon, Eye, MoreVertical, RefreshCcw, Pin, Star,
  Megaphone, Lightbulb, Box, Settings, ArrowRight, Loader2,
  TrendingUp, TrendingDown, Repeat, BellRing, BellOff
} from 'lucide-react';

/* =========================================================
   WOOKIEE HUB · DESIGN SYSTEM v2 — PATTERNS
   Разделы: Kanban · Calendar · Comments · Notifications ·
            Activity · Inbox · Theme demo
   Связан с wookiee_ds_v2_foundation.jsx (тот же визуальный язык,
   та же palette, тот же ThemeContext-паттерн).
   ========================================================= */

// =========================================================
// THEME (та же логика что в foundation)
// =========================================================

const ThemeContext = React.createContext({ theme: 'light' });
const useTheme = () => React.useContext(ThemeContext);

const cx = (...c) => c.filter(Boolean).join(' ');

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
// SHARED ATOMS (минимально, повтор для самодостаточности)
// =========================================================

function Avatar({ initials, color = 'stone', size = 'md', src, status }) {
  const sizes = { xs: 'w-5 h-5 text-[9px]', sm: 'w-6 h-6 text-[10px]', md: 'w-7 h-7 text-[11px]', lg: 'w-9 h-9 text-xs' };
  const colors = {
    stone: 'bg-gradient-to-br from-stone-700 to-stone-900 dark:from-stone-200 dark:to-stone-400 text-white dark:text-stone-900',
    emerald: 'bg-gradient-to-br from-emerald-500 to-emerald-700 text-white',
    blue: 'bg-gradient-to-br from-blue-500 to-blue-700 text-white',
    amber: 'bg-gradient-to-br from-amber-500 to-amber-700 text-white',
    purple: 'bg-gradient-to-br from-purple-500 to-purple-700 text-white',
    rose: 'bg-gradient-to-br from-rose-500 to-rose-700 text-white',
    teal: 'bg-gradient-to-br from-teal-500 to-teal-700 text-white',
  };
  return (
    <div className="relative inline-block shrink-0">
      <div className={cx('rounded-full flex items-center justify-center font-medium', sizes[size], colors[color])}>
        {initials}
      </div>
      {status && <span className={cx('absolute -bottom-0.5 -right-0.5 w-2 h-2 rounded-full ring-2 ring-white dark:ring-stone-900',
        status === 'online' ? 'bg-emerald-500' : status === 'busy' ? 'bg-amber-500' : 'bg-stone-400')} />}
    </div>
  );
}

function AvatarGroup({ users, max = 3 }) {
  const visible = users.slice(0, max);
  const rest = users.length - max;
  return (
    <div className="flex items-center">
      {visible.map((u, i) => (
        <div key={i} className={cx(i > 0 && '-ml-1.5', 'ring-2 ring-white dark:ring-stone-900 rounded-full')}>
          <Avatar {...u} size="xs" />
        </div>
      ))}
      {rest > 0 && (
        <div className="-ml-1.5 ring-2 ring-white dark:ring-stone-900 rounded-full bg-stone-100 dark:bg-stone-800 w-5 h-5 text-[9px] flex items-center justify-center font-medium text-stone-600 dark:text-stone-300">
          +{rest}
        </div>
      )}
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
    teal: 'bg-teal-50 dark:bg-teal-950/40 text-teal-700 dark:text-teal-300 ring-teal-600/20 dark:ring-teal-500/30',
    gray: 'bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-300 ring-stone-500/20 dark:ring-stone-600/40',
  };
  const dots = { emerald: 'bg-emerald-500', blue: 'bg-blue-500', amber: 'bg-amber-500', red: 'bg-red-500', purple: 'bg-purple-500', teal: 'bg-teal-500', gray: 'bg-stone-400' };
  return (
    <span className={cx('inline-flex items-center gap-1.5 rounded-md ring-1 ring-inset font-medium',
      compact ? 'px-1.5 py-0.5 text-[11px]' : 'px-2 py-0.5 text-xs', variants[variant])}>
      {dot && <span className={cx('w-1.5 h-1.5 rounded-full', dots[variant])} />}
      {Icon && <Icon className="w-3 h-3" />}
      {children}
    </span>
  );
}

function Button({ variant = 'primary', size = 'md', icon: Icon, children, ...props }) {
  const sizes = { sm: 'px-2.5 py-1 text-xs gap-1.5', md: 'px-3 py-1.5 text-sm gap-1.5' };
  const variants = {
    primary: 'bg-stone-900 dark:bg-stone-50 text-white dark:text-stone-900 hover:bg-stone-800 dark:hover:bg-stone-200',
    secondary: 'border border-stone-200 dark:border-stone-700 text-stone-700 dark:text-stone-200 hover:bg-stone-50 dark:hover:bg-stone-800 bg-white dark:bg-stone-900',
    ghost: 'text-stone-700 dark:text-stone-300 hover:bg-stone-100 dark:hover:bg-stone-800',
  };
  return (
    <button {...props} className={cx('inline-flex items-center font-medium rounded-md transition-colors', sizes[size], variants[variant])}>
      {Icon && <Icon className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5'} />}
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

function Section({ title, description, children }) {
  return (
    <section className="mb-12">
      <div className={cx('mb-4 pb-2 border-b', borderD)}>
        <h2 style={{ fontFamily: "'Instrument Serif', serif" }} className={cx('text-2xl', textP)}>{title}</h2>
        {description && <div className={cx('text-sm mt-1', textM)}>{description}</div>}
      </div>
      {children}
    </section>
  );
}

// =========================================================
// MOCK DATA
// =========================================================

const TEAM = {
  danya: { initials: 'ДВ', color: 'stone', name: 'Даня В.' },
  alina: { initials: 'АА', color: 'emerald', name: 'Алина А.' },
  artem: { initials: 'АП', color: 'blue', name: 'Артём П.' },
  nastya: { initials: 'НТ', color: 'rose', name: 'Настя Т.' },
  marina: { initials: 'МК', color: 'purple', name: 'Марина К.' },
  vlad: { initials: 'ВЛ', color: 'amber', name: 'Влад Л.' },
  sasha: { initials: 'СП', color: 'teal', name: 'Саша П.' },
};

// === KANBAN MOCK ===
const KANBAN_INITIAL = {
  columns: [
    { id: 'idea', title: 'Идеи', accent: 'gray', limit: null },
    { id: 'shooting', title: 'Съёмка', accent: 'blue', limit: 5 },
    { id: 'edit', title: 'Монтаж', accent: 'purple', limit: 4 },
    { id: 'review', title: 'Ревью', accent: 'amber', limit: 3 },
    { id: 'published', title: 'Опубликовано', accent: 'emerald', limit: null },
  ],
  cards: [
    { id: 'c1', col: 'idea', title: 'Reels про новую коллекцию Lite', model: 'Vuki', tag: 'Reels', priority: 'high',  due: '15 мая', assignee: 'marina', cover: '#FCA5A5', comments: 3, attachments: 2, completed: 1, total: 4 },
    { id: 'c2', col: 'idea', title: 'TikTok тренд "GRWM" с моделями Vivi',  model: 'Vivi', tag: 'TikTok', priority: 'medium', due: '18 мая', assignee: 'vlad', cover: '#FECACA', comments: 1, attachments: 0, completed: 0, total: 3 },
    { id: 'c3', col: 'idea', title: 'YouTube обзор материалов', model: null, tag: 'YouTube', priority: 'low', due: '25 мая', assignee: 'sasha', cover: null, comments: 0, attachments: 0 },
    { id: 'c4', col: 'shooting', title: 'Лукбук Vesta · черный',  model: 'Vesta', tag: 'Лукбук', priority: 'high', due: '12 мая', assignee: 'marina', cover: '#1C1917', comments: 5, attachments: 8, completed: 2, total: 5 },
    { id: 'c5', col: 'shooting', title: 'Карточки WB · обновление 12 SKU',   model: 'Vuki', tag: 'WB cards', priority: 'high', due: '11 мая', assignee: 'nastya', cover: '#FBBF24', comments: 8, attachments: 3, completed: 4, total: 12 },
    { id: 'c6', col: 'edit', title: 'Reels Vesta · цветокор',     model: 'Vesta', tag: 'Reels', priority: 'medium', due: '14 мая', assignee: 'vlad', cover: null, comments: 2, attachments: 1, completed: 3, total: 5 },
    { id: 'c7', col: 'edit', title: 'YouTube хроно · 4 минуты',    model: null, tag: 'YouTube', priority: 'medium', due: '16 мая', assignee: 'sasha', cover: null, comments: 4, attachments: 1 },
    { id: 'c8', col: 'review', title: 'Reels тренд LITE',                 model: 'Vivi', tag: 'Reels', priority: 'high', due: '13 мая', assignee: 'danya', cover: '#FECACA', comments: 12, attachments: 1 },
    { id: 'c9', col: 'review', title: 'Карточки Ozon · бежевая Vivi',     model: 'Vivi', tag: 'Ozon cards', priority: 'medium', due: '14 мая', assignee: 'nastya', cover: '#FED7AA', comments: 3, attachments: 4 },
    { id: 'c10', col: 'published', title: 'Обзор коллекции Spring 2026', model: null, tag: 'YouTube', priority: 'medium', due: '8 мая', assignee: 'sasha', cover: null, comments: 24, attachments: 1 },
    { id: 'c11', col: 'published', title: 'Reels GRWM · апрельская съёмка', model: 'Vuki', tag: 'Reels', priority: 'low', due: '5 мая', assignee: 'marina', cover: '#FBBF24', comments: 8, attachments: 1 },
  ],
};

// === CALENDAR EVENTS ===
const CALENDAR_EVENTS = [
  { id: 1, date: new Date(2026, 4, 11), title: 'Съёмка Vesta',     time: '10:00', duration: 4, color: 'blue',    assignees: ['marina', 'vlad'] },
  { id: 2, date: new Date(2026, 4, 12), title: 'Промо WB → 30%',   time: '00:00', duration: 24, color: 'amber',   assignees: ['nastya'] },
  { id: 3, date: new Date(2026, 4, 13), title: 'Sync с фабрикой',  time: '14:00', duration: 1, color: 'teal',    assignees: ['danya', 'artem'] },
  { id: 4, date: new Date(2026, 4, 14), title: 'Запуск Vivi/Бежевый', time: '12:00', duration: 1, color: 'emerald', assignees: ['danya', 'alina'] },
  { id: 5, date: new Date(2026, 4, 14), title: 'Reels Vivi', time: '15:00', duration: 2, color: 'purple', assignees: ['vlad'] },
  { id: 6, date: new Date(2026, 4, 15), title: 'Командная встреча', time: '11:00', duration: 1, color: 'gray', assignees: ['danya','alina','artem','nastya'] },
  { id: 7, date: new Date(2026, 4, 18), title: 'Промо Ozon → 25%', time: '00:00', duration: 48, color: 'amber', assignees: ['nastya'] },
  { id: 8, date: new Date(2026, 4, 19), title: 'Лукбук Spring 2', time: '09:00', duration: 6, color: 'blue', assignees: ['marina', 'vlad'] },
  { id: 9, date: new Date(2026, 4, 20), title: 'Поставка от фабрики', time: '08:00', duration: 1, color: 'teal', assignees: ['artem'] },
  { id: 10, date: new Date(2026, 4, 22), title: 'Релиз коллекции Lite', time: '12:00', duration: 1, color: 'emerald', assignees: ['danya'] },
];

// === COMMENTS THREAD ===
const COMMENTS = [
  {
    id: 1, author: 'alina', time: '2 часа назад',
    text: 'Цена Vivi/Бежевый не сходится с тех. характеристикой — там вес 95 г, а в карточке стоит 88 г. @nastya можешь свериться с фабрикой?',
    reactions: [{ emoji: '👀', count: 2 }, { emoji: '🤔', count: 1 }],
    replies: [
      { id: 11, author: 'nastya', time: '1 час назад', text: 'Уточнила — фабрика подтверждает 95 г. Обновлю карточки на WB и Ozon.', reactions: [{ emoji: '🙏', count: 3 }] },
      { id: 12, author: 'alina', time: '54 мин назад', text: 'Спасибо! После обновления отметь @danya — нужно будет согласовать с логистикой по весу к заказу.', reactions: [] },
    ],
  },
  {
    id: 2, author: 'marina', time: 'вчера',
    text: 'Загрузила финальные фото с лукбука Vuki — папка `lookbook-may-2026` в Drive. Готовы к публикации, жду ОК от @danya на пары.',
    attachments: [{ name: 'lookbook-final-12.jpg', size: '4.2 MB', type: 'image' }, { name: 'lookbook-final-13.jpg', size: '3.8 MB', type: 'image' }],
    reactions: [{ emoji: '🔥', count: 4 }, { emoji: '👍', count: 2 }],
    replies: [],
  },
  {
    id: 3, author: 'danya', time: '20 мин назад',
    text: 'Согласовал. Можно публиковать — кадры 02, 04, 07, 09 идут на обложки карточек. Кадр 12 — для коллекции в Instagram.',
    reactions: [{ emoji: '✅', count: 3 }],
    replies: [],
  },
];

// === NOTIFICATIONS ===
const NOTIFICATIONS = [
  { id: 1, group: 'today', type: 'mention',     read: false, time: '5 мин назад',  who: 'alina',  text: 'упомянула тебя в обсуждении модели Vuki', target: 'Vuki/Чёрный → атрибуты' },
  { id: 2, group: 'today', type: 'task',        read: false, time: '1 час назад',  who: 'artem',  text: 'назначил тебе задачу', target: 'Согласовать поставку №12/2 на 4.1т' },
  { id: 3, group: 'today', type: 'status',      read: false, time: '2 часа назад', who: null,     text: 'Vesta/Розовый перешёл в статус', target: 'Не выводится', meta: 'amber' },
  { id: 4, group: 'today', type: 'comment',     read: true,  time: '3 часа назад', who: 'marina', text: 'оставила комментарий в карточке', target: 'Vivi/Бежевый' },
  { id: 5, group: 'yesterday', type: 'system',  read: true,  time: 'вчера 18:00',  who: null,     text: 'Синхронизация WB завершена', target: '142 SKU обновлены, 3 ошибки' },
  { id: 6, group: 'yesterday', type: 'task',    read: true,  time: 'вчера 14:32',  who: 'nastya', text: 'закрыла задачу', target: 'Обновить карточки Ozon · бежевая Vivi' },
  { id: 7, group: 'yesterday', type: 'status',  read: true,  time: 'вчера 11:15',  who: null,     text: 'Запущена модель', target: 'Vivi · 18 артикулов', meta: 'emerald' },
  { id: 8, group: 'earlier', type: 'mention',   read: true,  time: '3 дня назад',  who: 'danya',  text: 'упомянул тебя в задаче', target: 'Релиз коллекции Lite' },
];

// === ACTIVITY FEED ===
const ACTIVITY = [
  { id: 1, time: '10 мин назад',  who: 'alina', action: 'обновила атрибуты',  entity: { kind: 'модель', name: 'Vuki' }, change: { from: 'Не указано', to: 'Хлопок 92% / Эластан 8%' }, field: 'Состав' },
  { id: 2, time: '32 мин назад',  who: 'nastya', action: 'изменила статус',   entity: { kind: 'модель', name: 'Vesta/Розовый' }, change: { from: 'Запуск', to: 'Не выводится' }, field: 'Статус', meta: { from: 'blue', to: 'red' } },
  { id: 3, time: '1 час назад',   who: 'danya', action: 'согласовал',         entity: { kind: 'оффер', name: 'Поставка 12/2' }, change: { from: '8.4 т', to: '4.1 т' }, field: 'Объём' },
  { id: 4, time: '2 часа назад',  who: 'marina', action: 'добавила фото',     entity: { kind: 'цвет', name: 'Vuki/Чёрный' }, count: 12, field: 'Контент' },
  { id: 5, time: '3 часа назад',  who: 'artem', action: 'создал заказ',       entity: { kind: 'заказ', name: '№ 12/3' }, field: 'Заказ' },
  { id: 6, time: 'вчера 16:42',   who: 'alina', action: 'добавила вариацию',  entity: { kind: 'модель', name: 'Vivi' }, change: { to: 'Бежевый' }, field: 'Цвет' },
  { id: 7, time: 'вчера 14:10',   who: 'nastya', action: 'опубликовала',      entity: { kind: 'карточка', name: 'WB · Vuki/Чёрный' }, field: 'Маркетплейс' },
  { id: 8, time: 'вчера 11:08',   who: 'danya', action: 'утвердил',           entity: { kind: 'кампания', name: 'Промо WB май' }, field: 'Маркетинг' },
];

// === INBOX ===
const INBOX_TASKS = [
  { id: 1, type: 'task',     title: 'Согласовать поставку №12/2',           from: 'artem',  due: 'сегодня',   priority: 'high',   read: false, project: 'Производство' },
  { id: 2, type: 'mention',  title: 'Vuki/Чёрный — атрибуты',                from: 'alina',  due: null,        priority: 'medium', read: false, project: 'Каталог' },
  { id: 3, type: 'review',   title: 'Reels тренд LITE — нужно 1 ревью',     from: 'vlad',   due: 'сегодня',   priority: 'medium', read: false, project: 'Контент' },
  { id: 4, type: 'task',     title: 'Обновить карточки на Ozon · 12 SKU',    from: 'danya',  due: '15 мая',    priority: 'medium', read: true,  project: 'Маркетплейс' },
  { id: 5, type: 'comment',  title: 'Vivi/Бежевый — комментарий от Марины',  from: 'marina', due: null,        priority: 'low',    read: true,  project: 'Каталог' },
  { id: 6, type: 'task',     title: 'Подготовить мудборд Spring 2',          from: 'danya',  due: '20 мая',    priority: 'low',    read: true,  project: 'Контент' },
  { id: 7, type: 'system',   title: 'Синхронизация WB · 3 ошибки',           from: null,     due: null,        priority: 'high',   read: true,  project: 'Система' },
];

// =========================================================
// SECTION 1: KANBAN — с реальным DnD
// =========================================================

function KanbanSection() {
  const [state, setState] = useState(KANBAN_INITIAL);
  const [draggingId, setDraggingId] = useState(null);
  const [overCol, setOverCol] = useState(null);
  const [overCardId, setOverCardId] = useState(null);
  const [openCard, setOpenCard] = useState(null);

  const onDragStart = (cardId) => { setDraggingId(cardId); };
  const onDragEnd = () => { setDraggingId(null); setOverCol(null); setOverCardId(null); };
  const onDragOverCol = (e, colId) => { e.preventDefault(); setOverCol(colId); };
  const onDragOverCard = (e, cardId) => { e.preventDefault(); e.stopPropagation(); setOverCardId(cardId); };
  const onDropOnCol = (e, colId) => {
    e.preventDefault();
    if (!draggingId) return;
    setState(s => {
      const card = s.cards.find(c => c.id === draggingId);
      if (!card) return s;
      const others = s.cards.filter(c => c.id !== draggingId);
      const targetIdx = overCardId ? others.findIndex(c => c.id === overCardId) : others.length;
      const updated = { ...card, col: colId };
      const newCards = [...others.slice(0, targetIdx >= 0 ? targetIdx : others.length), updated, ...others.slice(targetIdx >= 0 ? targetIdx : others.length)];
      return { ...s, cards: newCards };
    });
    onDragEnd();
  };

  const cardsBy = (colId) => state.cards.filter(c => c.col === colId);
  const accentBar = { gray: 'bg-stone-300 dark:bg-stone-600', blue: 'bg-blue-500', purple: 'bg-purple-500', amber: 'bg-amber-500', emerald: 'bg-emerald-500' };

  const updateCard = (cardId, patch) => {
    setState(s => ({ ...s, cards: s.cards.map(c => c.id === cardId ? { ...c, ...patch } : c) }));
  };

  return (
    <Section title="Kanban-доска" description="Контент-завод. Перетаскивай карточки между колонками — клик по карточке откроет её детальный вид справа.">
      <div className={cx('rounded-lg p-4 overflow-x-auto', surface)}>
        <div className="flex items-start gap-3 min-w-max">
          {state.columns.map(col => {
            const cards = cardsBy(col.id);
            const isOver = overCol === col.id && draggingId;
            const overflow = col.limit && cards.length > col.limit;
            return (
              <div key={col.id}
                onDragOver={(e) => onDragOverCol(e, col.id)}
                onDrop={(e) => onDropOnCol(e, col.id)}
                onDragLeave={(e) => { if (e.currentTarget === e.target) setOverCol(null); }}
                className={cx('w-72 shrink-0 rounded-lg transition-colors',
                  isOver ? 'bg-stone-100/70 dark:bg-stone-800/60 ring-1 ring-stone-300 dark:ring-stone-600' : surfaceMuted)}>
                <div className={cx('flex items-center gap-2 px-3 py-2.5 border-b', borderD)}>
                  <div className={cx('w-1 h-4 rounded-full', accentBar[col.accent])} />
                  <span className={cx('text-sm font-medium', textP)}>{col.title}</span>
                  <span className={cx('text-xs tabular-nums', textL)}>{cards.length}{col.limit ? `/${col.limit}` : ''}</span>
                  {overflow && <Badge variant="amber" compact>WIP↑</Badge>}
                  <div className="flex-1" />
                  <IconButton icon={Plus} title="Добавить" />
                  <IconButton icon={MoreHorizontal} title="Опции" />
                </div>
                <div className="p-2 space-y-2 min-h-[200px]">
                  {cards.map(card => (
                    <KanbanCard key={card.id} card={card}
                      onDragStart={() => onDragStart(card.id)}
                      onDragEnd={onDragEnd}
                      onDragOver={(e) => onDragOverCard(e, card.id)}
                      onClick={() => setOpenCard(card.id)}
                      isDragging={draggingId === card.id}
                      isOver={overCardId === card.id && draggingId !== card.id} />
                  ))}
                  {cards.length === 0 && (
                    <div className={cx('rounded border border-dashed text-xs italic text-center py-6',
                      isOver ? 'border-stone-400 dark:border-stone-500 ' + textM : 'border-stone-200 dark:border-stone-700 ' + textL)}>
                      {isOver ? '↓ Отпусти здесь' : 'Пусто'}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {openCard && (
        <KanbanCardDetail
          card={state.cards.find(c => c.id === openCard)}
          columns={state.columns}
          onClose={() => setOpenCard(null)}
          onUpdate={(patch) => updateCard(openCard, patch)} />
      )}
    </Section>
  );
}

// === KANBAN CARD DETAIL — drawer справа =====================
function KanbanCardDetail({ card, columns, onClose, onUpdate }) {
  if (!card) return null;
  const a = TEAM[card.assignee];
  const col = columns.find(c => c.id === card.col);
  const tagColor = { 'Reels': 'purple', 'TikTok': 'blue', 'YouTube': 'red', 'Лукбук': 'amber', 'WB cards': 'amber', 'Ozon cards': 'amber' };
  const priorityLabel = { high: 'Высокий', medium: 'Средний', low: 'Низкий' };
  const priorityColor = { high: 'red', medium: 'amber', low: 'gray' };
  const colAccent = { gray: 'gray', blue: 'blue', purple: 'purple', amber: 'amber', emerald: 'emerald' };

  // Mock subtasks
  const subtasks = [
    { id: 1, text: 'Согласовать концепт с Даней', done: card.completed >= 1 },
    { id: 2, text: 'Подготовить мудборд (Drive)', done: card.completed >= 2 },
    { id: 3, text: 'Забронировать студию и моделей', done: card.completed >= 3 },
    { id: 4, text: 'Снять основные планы', done: card.completed >= 4 },
    { id: 5, text: 'Передать в монтаж', done: card.completed >= 5 },
  ].slice(0, card.total || 4);

  // Mock comments
  const cardComments = [
    { id: 1, author: 'alina', time: 'вчера', text: 'Подобрала референсы по освещению, добавила в `lookbook-may-2026`. @marina посмотри стиль 02 и 04 — мне кажется попадает в настроение.' },
    { id: 2, author: 'marina', time: '4 часа назад', text: 'Огонь, беру 02! Бронирую студию @ProSpace на 12 мая 10:00.' },
    { id: 3, author: 'danya', time: '1 час назад', text: 'Согласовано. Сдвиньте на час позже если можно — у меня созвон в 10:00.' },
  ];

  return (
    <div className="fixed inset-0 z-50 bg-stone-900/40 dark:bg-black/60" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        className={cx('absolute right-0 top-0 bottom-0 w-[560px] flex flex-col', surface, 'border-l', borderD)}>
        {/* Cover */}
        {card.cover && <div className="h-2" style={{ background: card.cover }} />}

        {/* Header */}
        <div className={cx('flex items-center justify-between px-5 py-3 border-b', borderD)}>
          <div className="flex items-center gap-2">
            <Badge variant={colAccent[col?.accent] || 'gray'} dot>{col?.title}</Badge>
            {card.tag && <Badge variant={tagColor[card.tag] || 'gray'} compact>{card.tag}</Badge>}
            {card.model && (
              <span className={cx('text-[11px] font-mono inline-flex items-center gap-1 px-1.5 py-0.5 rounded',
                surfaceMuted, textS)}>
                <Hash className="w-2.5 h-2.5" />{card.model}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            <IconButton icon={Star} title="В избранное" />
            <IconButton icon={Copy} title="Дублировать" />
            <IconButton icon={MoreHorizontal} title="Опции" />
            <IconButton icon={X} onClick={onClose} title="Закрыть" />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {/* Title */}
          <div className="px-5 pt-5 pb-3">
            <div className={cx('text-[10px] uppercase tracking-wider mb-1', textL)}>ЗАДАЧА</div>
            <h2 style={{ fontFamily: "'Instrument Serif', serif" }} className={cx('text-2xl leading-tight', textP)}>
              {card.title}
            </h2>
          </div>

          {/* Properties block */}
          <div className={cx('px-5 py-3 border-y', borderD, surfaceMuted)}>
            <div className="grid grid-cols-2 gap-y-2.5 text-sm">
              <PropRow icon={User} label="Автор">
                <Avatar {...TEAM.danya} size="xs" />
                <span className={textS}>{TEAM.danya.name}</span>
              </PropRow>
              <PropRow icon={Users} label="Исполнитель">
                {a && (
                  <button className={cx('inline-flex items-center gap-1.5 rounded-md px-1.5 py-0.5 -ml-1.5', hoverBtn)}>
                    <Avatar {...a} size="xs" />
                    <span className={textS}>{a.name}</span>
                    <ChevronDown className={cx('w-3 h-3', textL)} />
                  </button>
                )}
              </PropRow>
              <PropRow icon={AlertCircle} label="Приоритет">
                <Badge variant={priorityColor[card.priority]} compact dot>{priorityLabel[card.priority]}</Badge>
              </PropRow>
              <PropRow icon={Calendar} label="Дедлайн">
                <span className={cx('text-sm tabular-nums', textS)}>{card.due || '—'}</span>
              </PropRow>
              <PropRow icon={TagIcon} label="Тег канала">
                {card.tag && <Badge variant={tagColor[card.tag] || 'gray'} compact>{card.tag}</Badge>}
              </PropRow>
              <PropRow icon={Layers} label="Колонка">
                <select value={card.col} onChange={(e) => onUpdate({ col: e.target.value })}
                  className={cx('text-sm rounded outline-none border-0 px-1.5 py-0.5 -ml-1.5 cursor-pointer',
                    'bg-transparent', textS, hoverBtn)}>
                  {columns.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
                </select>
              </PropRow>
            </div>
          </div>

          {/* Description */}
          <div className="px-5 py-4">
            <SectionLabel icon={FileText}>Описание</SectionLabel>
            <div className={cx('text-sm leading-relaxed', textS)}>
              Снять серию материалов для коллекции <span className={cx('font-mono text-xs', surfaceMuted, 'px-1 py-0.5 rounded')}>{card.model || 'Spring 2026'}</span>.
              Основные планы — лукбук + 3 Reels на ВК и Instagram. Материалы передать в монтаж до конца недели,
              финальная публикация согласовывается с маркетингом по календарю промо.
            </div>
          </div>

          {/* Subtasks */}
          {subtasks.length > 0 && (
            <div className={cx('px-5 py-4 border-t', borderD)}>
              <div className="flex items-center justify-between mb-2.5">
                <SectionLabel icon={CheckCircle} noMargin>Подзадачи</SectionLabel>
                <span className={cx('text-xs tabular-nums', textL)}>
                  {subtasks.filter(s => s.done).length}/{subtasks.length}
                </span>
              </div>
              <div className="h-1 rounded-full bg-stone-100 dark:bg-stone-800 overflow-hidden mb-3">
                <div className="h-full bg-emerald-500 transition-all"
                  style={{ width: `${(subtasks.filter(s => s.done).length / subtasks.length) * 100}%` }} />
              </div>
              <div className="space-y-1">
                {subtasks.map(s => (
                  <label key={s.id} className={cx('flex items-center gap-2.5 px-2 py-1.5 rounded cursor-pointer', hoverRow)}>
                    <input type="checkbox" checked={s.done} readOnly
                      className="w-3.5 h-3.5 rounded accent-emerald-500" />
                    <span className={cx('text-sm', s.done ? cx(textL, 'line-through') : textS)}>{s.text}</span>
                  </label>
                ))}
              </div>
              <button className={cx('mt-2 inline-flex items-center gap-1 text-xs px-2 py-1 rounded', textM, hoverBtn)}>
                <Plus className="w-3 h-3" />Добавить подзадачу
              </button>
            </div>
          )}

          {/* Attachments */}
          {card.attachments > 0 && (
            <div className={cx('px-5 py-4 border-t', borderD)}>
              <SectionLabel icon={Paperclip}>Вложения · {card.attachments}</SectionLabel>
              <div className="grid grid-cols-3 gap-2">
                {Array.from({ length: Math.min(3, card.attachments) }).map((_, i) => (
                  <div key={i} className={cx('rounded-md p-2 text-center', surfaceMuted, borderD, 'border')}>
                    <div className="aspect-video rounded bg-stone-200 dark:bg-stone-700 mb-1.5 flex items-center justify-center">
                      <ImageIcon className={cx('w-4 h-4', textL)} />
                    </div>
                    <div className={cx('text-[10px] font-mono truncate', textM)}>shot-{i+1}.jpg</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Comments */}
          <div className={cx('px-5 py-4 border-t', borderD)}>
            <SectionLabel icon={MessageSquare}>Комментарии · {cardComments.length}</SectionLabel>
            <div className="space-y-3 mb-3">
              {cardComments.map(c => {
                const ca = TEAM[c.author];
                return (
                  <div key={c.id} className="flex gap-2.5">
                    <Avatar {...ca} size="xs" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-1.5">
                        <span className={cx('text-xs font-medium', textP)}>{ca.name}</span>
                        <span className={cx('text-[10px]', textL)}>{c.time}</span>
                      </div>
                      <div className={cx('text-sm leading-snug mt-0.5', textS)}>
                        {c.text.split(/(@\w+)/g).map((part, i) =>
                          part.startsWith('@')
                            ? <span key={i} className="bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 px-1 rounded text-[11px] font-medium">{part}</span>
                            : part.split(/(`[^`]+`)/g).map((p2, j) => p2.startsWith('`') ? <code key={j} className="font-mono text-[11px] bg-stone-100 dark:bg-stone-800 px-1 py-0.5 rounded">{p2.slice(1, -1)}</code> : p2)
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className={cx('rounded-md border', borderD, 'bg-white dark:bg-stone-900')}>
              <textarea placeholder="Напишите комментарий…" rows={2}
                className={cx('w-full px-3 py-2 text-sm bg-transparent outline-none resize-none', textP, 'placeholder:text-stone-400')} />
              <div className={cx('flex items-center justify-between px-2 py-1.5 border-t', borderD)}>
                <div className="flex items-center gap-0.5">
                  <IconButton icon={AtSign} title="Упомянуть" />
                  <IconButton icon={Paperclip} title="Прикрепить" />
                </div>
                <Button size="sm" icon={Send}>Отправить</Button>
              </div>
            </div>
          </div>

          {/* Activity */}
          <div className={cx('px-5 py-4 border-t', borderD)}>
            <SectionLabel icon={Activity}>История</SectionLabel>
            <div className="space-y-2 text-xs">
              {[
                { who: 'danya', text: 'создал задачу', time: '5 дней назад' },
                { who: 'alina', text: 'добавила вложения', time: '4 дня назад' },
                { who: 'marina', text: 'переместила в Съёмка', time: '2 дня назад' },
                { who: 'vlad', text: 'отметил подзадачу выполненной', time: 'вчера' },
              ].map((a, i) => {
                const w = TEAM[a.who];
                return (
                  <div key={i} className="flex items-center gap-2">
                    <Avatar {...w} size="xs" />
                    <span className={textS}>{w.name} {a.text}</span>
                    <span className={cx('ml-auto', textL)}>{a.time}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className={cx('px-5 py-3 border-t flex items-center justify-between', borderD)}>
          <Button variant="ghost" size="sm" icon={Trash2}>Архивировать</Button>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" icon={ExternalLink}>Открыть полностью</Button>
            <Button size="sm" icon={Save}>Сохранить</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function PropRow({ icon: Icon, label, children }) {
  return (
    <div className="flex items-center gap-2 min-w-0">
      <Icon className={cx('w-3.5 h-3.5 shrink-0', textL)} />
      <span className={cx('text-[11px] uppercase tracking-wider w-20 shrink-0', textM)}>{label}</span>
      <div className="flex items-center gap-1.5 min-w-0">{children}</div>
    </div>
  );
}

function SectionLabel({ icon: Icon, children, noMargin }) {
  return (
    <div className={cx('flex items-center gap-1.5', !noMargin && 'mb-2.5')}>
      <Icon className={cx('w-3.5 h-3.5', textL)} />
      <span className={cx('text-[11px] uppercase tracking-wider font-medium', textM)}>{children}</span>
    </div>
  );
}

function KanbanCard({ card, onDragStart, onDragEnd, onDragOver, onClick, isDragging, isOver }) {
  const tagColor = { 'Reels': 'purple', 'TikTok': 'blue', 'YouTube': 'red', 'Лукбук': 'amber', 'WB cards': 'amber', 'Ozon cards': 'amber' };
  const priorityIcon = { high: <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />, medium: <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />, low: <span className="w-1.5 h-1.5 rounded-full bg-stone-300 dark:bg-stone-600" /> };
  const a = TEAM[card.assignee];

  return (
    <div draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragOver={onDragOver}
      onClick={(e) => { if (!isDragging) onClick?.(); }}
      className={cx('rounded-md p-2.5 cursor-grab active:cursor-grabbing transition-all relative group',
        surface, 'shadow-sm hover:shadow-md hover:-translate-y-0.5',
        isDragging && 'opacity-30 rotate-1 scale-95',
        isOver && 'ring-2 ring-stone-400 dark:ring-stone-500 -translate-y-0.5')}>
      {/* Cover stripe */}
      {card.cover && <div className="h-1 -mx-2.5 -mt-2.5 mb-2 rounded-t-md" style={{ background: card.cover }} />}

      {/* Tag + priority */}
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1.5">
          {priorityIcon[card.priority]}
          {card.tag && <Badge variant={tagColor[card.tag] || 'gray'} compact>{card.tag}</Badge>}
          {card.model && <span className={cx('text-[10px] font-mono', textL)}>{card.model}</span>}
        </div>
        <button className={cx('p-0.5 rounded opacity-0 group-hover:opacity-100', hoverBtn)}>
          <MoreHorizontal className={cx('w-3 h-3', textL)} />
        </button>
      </div>

      {/* Title */}
      <div className={cx('text-sm leading-snug mb-2', textP)}>{card.title}</div>

      {/* Progress bar (subtasks) */}
      {card.total !== undefined && (
        <div className="mb-2">
          <div className="flex items-center justify-between text-[10px] mb-0.5">
            <span className={textM}>Подзадачи</span>
            <span className={cx('tabular-nums', textL)}>{card.completed}/{card.total}</span>
          </div>
          <div className="h-1 rounded-full bg-stone-100 dark:bg-stone-800 overflow-hidden">
            <div className="h-full bg-stone-500 dark:bg-stone-400 transition-all" style={{ width: `${(card.completed/card.total)*100}%` }} />
          </div>
        </div>
      )}

      {/* Footer: meta + assignee */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-[10px]">
          {card.due && (
            <span className={cx('inline-flex items-center gap-1 tabular-nums', textM)}>
              <Calendar className="w-2.5 h-2.5" />{card.due}
            </span>
          )}
          {card.comments > 0 && (
            <span className={cx('inline-flex items-center gap-1 tabular-nums', textM)}>
              <MessageSquare className="w-2.5 h-2.5" />{card.comments}
            </span>
          )}
          {card.attachments > 0 && (
            <span className={cx('inline-flex items-center gap-1 tabular-nums', textM)}>
              <Paperclip className="w-2.5 h-2.5" />{card.attachments}
            </span>
          )}
        </div>
        {a && <Avatar {...a} size="xs" />}
      </div>
    </div>
  );
}

// =========================================================
// SECTION 2: CALENDAR — month + week view
// =========================================================

function CalendarSection() {
  const [view, setView] = useState('month');
  const [cursor, setCursor] = useState(new Date(2026, 4, 1));
  const [events, setEvents] = useState(CALENDAR_EVENTS);
  const [draggingEvent, setDraggingEvent] = useState(null);
  const [openEvent, setOpenEvent] = useState(null);

  const moveEvent = (eventId, newDate, newTime) => {
    setEvents(prev => prev.map(e => {
      if (e.id !== eventId) return e;
      const updated = { ...e };
      if (newDate) updated.date = newDate;
      if (newTime) updated.time = newTime;
      return updated;
    }));
  };

  return (
    <Section title="Calendar" description="Планирование съёмок, релизов, промо и поставок. События перетаскиваются — попробуй перенести съёмку Vesta в другой день.">
      <div className={cx('rounded-lg overflow-hidden', surface)}>
        <CalendarHeader view={view} setView={setView} cursor={cursor} setCursor={setCursor} />
        {view === 'month'
          ? <MonthView cursor={cursor} events={events}
              draggingEvent={draggingEvent} setDraggingEvent={setDraggingEvent}
              moveEvent={moveEvent} onEventClick={setOpenEvent} />
          : <WeekView cursor={cursor} events={events}
              draggingEvent={draggingEvent} setDraggingEvent={setDraggingEvent}
              moveEvent={moveEvent} onEventClick={setOpenEvent} />}
      </div>

      {openEvent && <EventDetailPopover event={events.find(e => e.id === openEvent)} onClose={() => setOpenEvent(null)} />}
    </Section>
  );
}

function CalendarHeader({ view, setView, cursor, setCursor }) {
  const months = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
  return (
    <div className={cx('flex items-center justify-between px-4 py-3 border-b', borderD)}>
      <div className="flex items-center gap-3">
        <Button variant="secondary" size="sm" onClick={() => setCursor(new Date(2026, 4, 10))}>Сегодня</Button>
        <div className="flex items-center gap-0.5">
          <IconButton icon={ChevronLeft} onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))} />
          <IconButton icon={ChevronRight} onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))} />
        </div>
        <div style={{ fontFamily: "'Instrument Serif', serif" }} className={cx('text-2xl', textP)}>
          <em className="italic">{months[cursor.getMonth()]}</em> {cursor.getFullYear()}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <div className={cx('inline-flex items-center gap-1 p-0.5 rounded-md', 'bg-stone-100 dark:bg-stone-800')}>
          {[
            { v: 'month', label: 'Месяц' },
            { v: 'week', label: 'Неделя' },
          ].map(t => (
            <button key={t.v} onClick={() => setView(t.v)}
              className={cx('px-3 py-1 text-xs rounded transition-colors',
                view === t.v ? cx('bg-white dark:bg-stone-900', textP, 'shadow-sm font-medium') : textS)}>
              {t.label}
            </button>
          ))}
        </div>
        <Button icon={Plus} size="sm">Событие</Button>
      </div>
    </div>
  );
}

function MonthView({ cursor, events, draggingEvent, setDraggingEvent, moveEvent, onEventClick }) {
  const days = ['пн','вт','ср','чт','пт','сб','вс'];
  const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
  const startWeekday = (first.getDay() + 6) % 7;
  const lastDay = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0).getDate();
  const today = new Date(2026, 4, 10);
  const cells = [];
  for (let i = 0; i < startWeekday; i++) {
    const d = new Date(cursor.getFullYear(), cursor.getMonth(), -startWeekday + i + 1);
    cells.push({ d, outside: true });
  }
  for (let d = 1; d <= lastDay; d++) cells.push({ d: new Date(cursor.getFullYear(), cursor.getMonth(), d), outside: false });
  while (cells.length % 7 !== 0 || cells.length < 35) {
    const last = cells[cells.length - 1].d;
    cells.push({ d: new Date(last.getFullYear(), last.getMonth(), last.getDate() + 1), outside: true });
    if (cells.length >= 42) break;
  }
  const eventsFor = (d) => events.filter(e => e.date.toDateString() === d.toDateString());
  const colorMap = {
    blue: 'bg-blue-100/70 dark:bg-blue-950/40 text-blue-800 dark:text-blue-300 border-l-2 border-blue-500',
    purple: 'bg-purple-100/70 dark:bg-purple-950/40 text-purple-800 dark:text-purple-300 border-l-2 border-purple-500',
    emerald: 'bg-emerald-100/70 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border-l-2 border-emerald-500',
    amber: 'bg-amber-100/70 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border-l-2 border-amber-500',
    teal: 'bg-teal-100/70 dark:bg-teal-950/40 text-teal-800 dark:text-teal-300 border-l-2 border-teal-500',
    gray: 'bg-stone-100/70 dark:bg-stone-800/60 text-stone-700 dark:text-stone-300 border-l-2 border-stone-400',
  };

  const [dropTarget, setDropTarget] = useState(null);

  return (
    <div>
      <div className={cx('grid grid-cols-7 border-b', borderD)}>
        {days.map(d => (
          <div key={d} className={cx('px-3 py-2 text-[11px] uppercase tracking-wider font-medium text-center', textM)}>{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7" style={{ gridAutoRows: 'minmax(110px, 1fr)' }}>
        {cells.map((cell, i) => {
          const isToday = cell.d.toDateString() === today.toDateString();
          const dayEvents = eventsFor(cell.d);
          const isDropTarget = dropTarget === cell.d.toDateString() && draggingEvent;
          return (
            <div key={i}
              onDragOver={(e) => { e.preventDefault(); setDropTarget(cell.d.toDateString()); }}
              onDragLeave={() => setDropTarget(null)}
              onDrop={(e) => {
                e.preventDefault();
                if (draggingEvent) {
                  moveEvent(draggingEvent, cell.d, null);
                  setDraggingEvent(null); setDropTarget(null);
                }
              }}
              className={cx('border-r border-b p-1.5 min-h-[110px] transition-colors', borderD,
                cell.outside && !isDropTarget && 'bg-stone-50/30 dark:bg-stone-900/30',
                isDropTarget && 'bg-stone-100/70 dark:bg-stone-800/60 ring-1 ring-inset ring-stone-300 dark:ring-stone-600',
                i % 7 === 6 && 'border-r-0')}>
              <div className="flex items-center justify-between mb-1">
                <span className={cx('text-xs tabular-nums inline-flex items-center justify-center w-5 h-5 rounded-full',
                  isToday ? 'bg-stone-900 text-white dark:bg-stone-50 dark:text-stone-900 font-medium'
                  : cell.outside ? textL : textS)}>
                  {cell.d.getDate()}
                </span>
              </div>
              <div className="space-y-0.5">
                {dayEvents.slice(0, 3).map(e => (
                  <div key={e.id}
                    draggable
                    onDragStart={() => setDraggingEvent(e.id)}
                    onDragEnd={() => { setDraggingEvent(null); setDropTarget(null); }}
                    onClick={(ev) => { ev.stopPropagation(); onEventClick(e.id); }}
                    className={cx('px-1.5 py-0.5 rounded text-[10px] cursor-grab active:cursor-grabbing truncate transition-all',
                      colorMap[e.color] || colorMap.gray,
                      draggingEvent === e.id && 'opacity-30')}>
                    <span className="font-mono tabular-nums mr-1">{e.time !== '00:00' && e.time}</span>
                    {e.title}
                  </div>
                ))}
                {dayEvents.length > 3 && (
                  <div className={cx('text-[10px] px-1.5', textL)}>+{dayEvents.length - 3} ещё</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function WeekView({ cursor, events, draggingEvent, setDraggingEvent, moveEvent, onEventClick }) {
  const today = new Date(2026, 4, 10);
  const baseDay = new Date(today);
  const monday = new Date(baseDay); monday.setDate(baseDay.getDate() - ((baseDay.getDay() + 6) % 7));
  const days = Array.from({ length: 7 }, (_, i) => { const d = new Date(monday); d.setDate(monday.getDate() + i); return d; });
  const hours = Array.from({ length: 14 }, (_, i) => i + 8);
  const dayNames = ['пн','вт','ср','чт','пт','сб','вс'];
  const eventsFor = (d) => events.filter(e => e.date.toDateString() === d.toDateString());
  const colorMap = {
    blue: 'bg-blue-100/70 dark:bg-blue-950/40 text-blue-800 dark:text-blue-300 border-l-2 border-blue-500',
    purple: 'bg-purple-100/70 dark:bg-purple-950/40 text-purple-800 dark:text-purple-300 border-l-2 border-purple-500',
    emerald: 'bg-emerald-100/70 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border-l-2 border-emerald-500',
    amber: 'bg-amber-100/70 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border-l-2 border-amber-500',
    teal: 'bg-teal-100/70 dark:bg-teal-950/40 text-teal-800 dark:text-teal-300 border-l-2 border-teal-500',
    gray: 'bg-stone-100/70 dark:bg-stone-800/60 text-stone-700 dark:text-stone-300 border-l-2 border-stone-400',
  };

  const [dropSlot, setDropSlot] = useState(null); // { day, hour }

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[720px]">
        <div className={cx('grid border-b', borderD)} style={{ gridTemplateColumns: '60px repeat(7, 1fr)' }}>
          <div></div>
          {days.map((d, i) => {
            const isToday = d.toDateString() === today.toDateString();
            return (
              <div key={i} className="px-2 py-2 text-center">
                <div className={cx('text-[10px] uppercase tracking-wider', textM)}>{dayNames[i]}</div>
                <div className={cx('text-lg tabular-nums mt-0.5 inline-flex items-center justify-center w-7 h-7 rounded-full',
                  isToday ? 'bg-stone-900 text-white dark:bg-stone-50 dark:text-stone-900 font-medium' : textP)}>
                  {d.getDate()}
                </div>
              </div>
            );
          })}
        </div>

        <div className="relative" style={{ display: 'grid', gridTemplateColumns: '60px repeat(7, 1fr)' }}>
          <div className="col-start-1">
            {hours.map(h => (
              <div key={h} className={cx('h-12 px-2 text-[10px] text-right pt-0.5 tabular-nums border-r', textL, borderD)}>
                {String(h).padStart(2,'0')}:00
              </div>
            ))}
          </div>
          {days.map((d, di) => {
            const dayEvents = eventsFor(d).filter(e => e.time !== '00:00');
            return (
              <div key={di} className={cx('relative', di < 6 && 'border-r ' + borderD)}>
                {hours.map(h => {
                  const isDrop = dropSlot && dropSlot.day === di && dropSlot.hour === h;
                  return (
                    <div key={h}
                      onDragOver={(e) => { e.preventDefault(); setDropSlot({ day: di, hour: h }); }}
                      onDrop={(e) => {
                        e.preventDefault();
                        if (draggingEvent) {
                          moveEvent(draggingEvent, d, `${String(h).padStart(2,'0')}:00`);
                          setDraggingEvent(null); setDropSlot(null);
                        }
                      }}
                      className={cx('h-12 border-b transition-colors', borderD,
                        isDrop && draggingEvent && 'bg-stone-100/60 dark:bg-stone-800/60 ring-1 ring-inset ring-stone-300 dark:ring-stone-600')} />
                  );
                })}
                {dayEvents.map(e => {
                  const [eh, em] = e.time.split(':').map(Number);
                  const top = ((eh - 8) + em / 60) * 48;
                  const height = e.duration * 48 - 2;
                  return (
                    <div key={e.id}
                      draggable
                      onDragStart={() => setDraggingEvent(e.id)}
                      onDragEnd={() => { setDraggingEvent(null); setDropSlot(null); }}
                      onClick={(ev) => { ev.stopPropagation(); onEventClick(e.id); }}
                      className={cx('absolute left-1 right-1 rounded p-1.5 cursor-grab active:cursor-grabbing overflow-hidden transition-all',
                        colorMap[e.color] || colorMap.gray,
                        draggingEvent === e.id && 'opacity-30')}
                      style={{ top, height }}>
                      <div className="text-[11px] font-medium leading-tight truncate">{e.title}</div>
                      <div className="text-[10px] opacity-80 mt-0.5 tabular-nums">{e.time}</div>
                    </div>
                  );
                })}
              </div>
            );
          })}
          <div className="absolute left-[60px] right-0 pointer-events-none z-10"
            style={{ top: ((14 - 8) + 30 / 60) * 48 }}>
            <div className="flex items-center">
              <span className="w-2 h-2 rounded-full bg-rose-500 -ml-1" />
              <div className="flex-1 h-px bg-rose-500" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function EventDetailPopover({ event, onClose }) {
  if (!event) return null;
  const colorMap = {
    blue: 'bg-blue-500', purple: 'bg-purple-500', emerald: 'bg-emerald-500',
    amber: 'bg-amber-500', teal: 'bg-teal-500', gray: 'bg-stone-400',
  };
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-32 bg-stone-900/40 dark:bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        className={cx('w-full max-w-md rounded-lg overflow-hidden', surface)}>
        <div className={cx('h-1', colorMap[event.color])} />
        <div className={cx('px-5 py-4 border-b', borderD)}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className={cx('text-[10px] uppercase tracking-wider mb-1', textL)}>СОБЫТИЕ</div>
              <h3 style={{ fontFamily: "'Instrument Serif', serif" }} className={cx('text-2xl', textP)}>{event.title}</h3>
            </div>
            <IconButton icon={X} onClick={onClose} />
          </div>
          <div className={cx('flex items-center gap-3 mt-3 text-sm', textS)}>
            <span className="inline-flex items-center gap-1.5">
              <Calendar className={cx('w-3.5 h-3.5', textL)} />
              {event.date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', weekday: 'long' })}
            </span>
            <span className="inline-flex items-center gap-1.5 tabular-nums">
              <Clock className={cx('w-3.5 h-3.5', textL)} />
              {event.time} · {event.duration}ч
            </span>
          </div>
        </div>

        <div className="px-5 py-4">
          <div className={cx('text-[11px] uppercase tracking-wider mb-2', textM)}>УЧАСТНИКИ</div>
          <div className="flex items-center gap-2 mb-4">
            {event.assignees.map(a => {
              const u = TEAM[a];
              return (
                <span key={a} className={cx('inline-flex items-center gap-1.5 rounded-md px-2 py-1', surfaceMuted)}>
                  <Avatar {...u} size="xs" />
                  <span className={cx('text-xs', textS)}>{u.name}</span>
                </span>
              );
            })}
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="secondary" icon={Edit3}>Редактировать</Button>
            <Button size="sm" variant="ghost" icon={Trash2}>Удалить</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// =========================================================
// SECTION 3: COMMENTS THREAD
// =========================================================

function CommentsSection() {
  const [text, setText] = useState('');

  return (
    <Section title="Comments thread" description="Под сущностью (моделью / задачей / SKU). Поддержка @-mentions, реакций, вложений, ответов.">
      <div className={cx('rounded-lg max-w-3xl', surface)}>
        <div className={cx('px-5 py-3 border-b flex items-center justify-between', borderD)}>
          <div className="flex items-center gap-2">
            <MessageSquare className={cx('w-4 h-4', textM)} />
            <span className={cx('text-sm font-medium', textP)}>Обсуждение</span>
            <Badge variant="gray" compact>{COMMENTS.length + COMMENTS.reduce((s, c) => s + (c.replies?.length || 0), 0)}</Badge>
          </div>
          <div className="flex items-center gap-1">
            <IconButton icon={Pin} title="Закрепить" />
            <IconButton icon={BellOff} title="Отключить уведомления" />
            <IconButton icon={MoreHorizontal} title="Опции" />
          </div>
        </div>

        <div className="p-5 space-y-5">
          {COMMENTS.map(c => <Comment key={c.id} comment={c} />)}
        </div>

        <div className={cx('p-4 border-t', borderD)}>
          <CommentComposer value={text} onChange={setText} />
        </div>
      </div>
    </Section>
  );
}

function Comment({ comment, indent = false }) {
  const a = TEAM[comment.author];
  return (
    <div className={cx('flex gap-3', indent && 'ml-10 pt-3')}>
      <Avatar {...a} size="sm" />
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2 flex-wrap mb-0.5">
          <span className={cx('text-sm font-medium', textP)}>{a.name}</span>
          <span className={cx('text-[11px]', textL)}>{comment.time}</span>
        </div>
        <div className={cx('text-sm leading-relaxed', textS)}>
          {comment.text.split(/(@\w+)/g).map((part, i) =>
            part.startsWith('@')
              ? <span key={i} className="bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 px-1 py-0.5 rounded text-xs font-medium">{part}</span>
              : part.split(/(`[^`]+`)/g).map((p2, j) => p2.startsWith('`') ? <code key={j} className="font-mono text-xs bg-stone-100 dark:bg-stone-800 px-1 py-0.5 rounded">{p2.slice(1, -1)}</code> : p2)
          )}
        </div>

        {/* Attachments */}
        {comment.attachments?.length > 0 && (
          <div className="flex gap-2 mt-2">
            {comment.attachments.map((att, i) => (
              <div key={i} className={cx('flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs', surfaceMuted)}>
                <ImageIcon className={cx('w-3.5 h-3.5', textM)} />
                <span className={cx('font-mono text-[11px]', textS)}>{att.name}</span>
                <span className={cx('text-[10px]', textL)}>{att.size}</span>
              </div>
            ))}
          </div>
        )}

        {/* Reactions + actions */}
        <div className="flex items-center gap-1 mt-2">
          {comment.reactions?.map((r, i) => (
            <button key={i} className={cx('inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[11px] transition-colors',
              'border', borderD, hoverBtn, textS)}>
              <span>{r.emoji}</span>
              <span className="tabular-nums">{r.count}</span>
            </button>
          ))}
          <button className={cx('p-1 rounded transition-colors opacity-60 hover:opacity-100', hoverBtn)}>
            <Smile className={cx('w-3.5 h-3.5', textM)} />
          </button>
          <span className="mx-1.5 w-px h-3 bg-stone-200 dark:bg-stone-700" />
          <button className={cx('inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded', hoverBtn, textM)}>
            <Reply className="w-3 h-3" />Ответить
          </button>
        </div>

        {/* Replies */}
        {comment.replies?.length > 0 && (
          <div className="mt-3 space-y-3 border-l-2 border-stone-100 dark:border-stone-800 pl-4">
            {comment.replies.map(r => <Comment key={r.id} comment={r} />)}
          </div>
        )}
      </div>
    </div>
  );
}

function CommentComposer({ value, onChange }) {
  return (
    <div className={cx('rounded-md border', borderD, 'bg-white dark:bg-stone-900')}>
      <textarea value={value} onChange={(e) => onChange(e.target.value)}
        placeholder="Напишите комментарий… @ для упоминания, # для ссылки на модель"
        rows={2}
        className={cx('w-full px-3 py-2 text-sm bg-transparent outline-none resize-none', textP, 'placeholder:text-stone-400')} />
      <div className="flex items-center justify-between px-2 py-1.5 border-t border-stone-100 dark:border-stone-800">
        <div className="flex items-center gap-0.5">
          <IconButton icon={AtSign} title="Упомянуть" />
          <IconButton icon={Hash} title="Связать сущность" />
          <IconButton icon={Paperclip} title="Прикрепить" />
          <IconButton icon={Smile} title="Эмодзи" />
        </div>
        <div className="flex items-center gap-2">
          <span className={cx('text-[10px]', textL)}>⌘ ↵ отправить</span>
          <Button size="sm" icon={Send}>Отправить</Button>
        </div>
      </div>
    </div>
  );
}

// =========================================================
// SECTION 4: NOTIFICATIONS PANEL (slide-out)
// =========================================================

function NotificationsSection() {
  const [openPanel, setOpenPanel] = useState(false);

  return (
    <Section title="Notifications" description="Slide-out панель справа. Группировка по дате, фильтры, отметка прочтения.">
      <div className="flex items-center gap-3 mb-4">
        <Button icon={BellRing} onClick={() => setOpenPanel(true)}>
          Открыть панель
          <Badge variant="red" compact>3</Badge>
        </Button>
        <span className={cx('text-xs', textM)}>← клик откроет slide-out справа</span>
      </div>

      {/* Inline preview всегда видимый */}
      <div className={cx('rounded-lg max-w-md', surface)}>
        <div className={cx('px-4 py-3 border-b flex items-center justify-between', borderD)}>
          <span className={cx('text-sm font-medium', textP)}>Уведомления</span>
          <Badge variant="red" compact>3 новых</Badge>
        </div>
        <NotificationsList notifications={NOTIFICATIONS.slice(0, 5)} compact />
      </div>

      {openPanel && <NotificationsPanel onClose={() => setOpenPanel(false)} />}
    </Section>
  );
}

function NotificationsPanel({ onClose }) {
  const [filter, setFilter] = useState('all');
  const filtered = filter === 'unread' ? NOTIFICATIONS.filter(n => !n.read)
    : filter === 'mentions' ? NOTIFICATIONS.filter(n => n.type === 'mention')
    : NOTIFICATIONS;

  return (
    <div className="fixed inset-0 z-50 bg-stone-900/40 dark:bg-black/60" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        className={cx('absolute right-0 top-0 bottom-0 w-[420px] flex flex-col', surface, 'border-l', borderD)}>
        <div className={cx('flex items-center justify-between px-5 py-3.5 border-b', borderD)}>
          <div className="flex items-center gap-2">
            <Bell className={cx('w-4 h-4', textM)} />
            <span className={cx('text-base font-medium', textP)}>Уведомления</span>
            <Badge variant="red" compact>{NOTIFICATIONS.filter(n => !n.read).length}</Badge>
          </div>
          <div className="flex items-center gap-1">
            <IconButton icon={Settings} title="Настройки" />
            <IconButton icon={X} onClick={onClose} title="Закрыть" />
          </div>
        </div>

        <div className={cx('px-5 py-2.5 border-b flex items-center gap-1', borderD)}>
          {[
            { v: 'all', label: 'Все' },
            { v: 'unread', label: 'Непрочитанные' },
            { v: 'mentions', label: 'Упоминания' },
          ].map(f => (
            <button key={f.v} onClick={() => setFilter(f.v)}
              className={cx('px-2.5 py-1 text-xs rounded-md transition-colors',
                filter === f.v ? 'bg-stone-900 text-white dark:bg-stone-50 dark:text-stone-900'
                : cx(textS, hoverBtn))}>
              {f.label}
            </button>
          ))}
          <div className="flex-1" />
          <button className={cx('text-[11px]', textM, 'hover:underline')}>Прочитать все</button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <NotificationsList notifications={filtered} />
        </div>
      </div>
    </div>
  );
}

function NotificationsList({ notifications, compact }) {
  const grouped = notifications.reduce((acc, n) => { (acc[n.group] = acc[n.group] || []).push(n); return acc; }, {});
  const groupLabel = { today: 'Сегодня', yesterday: 'Вчера', earlier: 'Ранее' };
  const typeIcon = {
    mention: <AtSign className="w-3.5 h-3.5 text-blue-500" />,
    task: <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />,
    comment: <MessageSquare className="w-3.5 h-3.5 text-purple-500" />,
    status: <RefreshCcw className="w-3.5 h-3.5 text-amber-500" />,
    system: <Info className="w-3.5 h-3.5 text-stone-400" />,
  };

  return (
    <div>
      {Object.entries(grouped).map(([g, items]) => (
        <div key={g}>
          <div className={cx('px-5 py-1.5 text-[10px] uppercase tracking-wider sticky top-0', textL, surfaceMuted)}>
            {groupLabel[g]}
          </div>
          {items.map(n => {
            const w = n.who ? TEAM[n.who] : null;
            return (
              <div key={n.id} className={cx('px-5 py-3 flex items-start gap-3 cursor-pointer transition-colors',
                hoverRow, !n.read && 'bg-blue-50/30 dark:bg-blue-950/10')}>
                {!n.read && <span className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-1.5 shrink-0" />}
                {n.read && <span className="w-1.5 shrink-0" />}
                <div className="shrink-0 mt-0.5">
                  {w ? <Avatar {...w} size="sm" /> : (
                    <div className={cx('w-6 h-6 rounded-full flex items-center justify-center', surfaceMuted)}>
                      {typeIcon[n.type]}
                    </div>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className={cx('text-sm leading-snug', textS)}>
                    {w && <span className={cx('font-medium', textP)}>{w.name}</span>} {n.text}
                  </div>
                  {n.target && (
                    <div className="mt-1 inline-flex items-center gap-1.5">
                      <span className={cx('text-xs px-2 py-0.5 rounded',
                        n.meta === 'amber' ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300'
                        : n.meta === 'emerald' ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300'
                        : cx(surfaceMuted, textS))}>
                        {n.target}
                      </span>
                    </div>
                  )}
                  <div className={cx('text-[11px] mt-1', textL)}>{n.time}</div>
                </div>
                {!compact && (
                  <button className={cx('p-1 rounded opacity-0 group-hover:opacity-100', hoverBtn)}>
                    <X className={cx('w-3 h-3', textL)} />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

// =========================================================
// SECTION 5: ACTIVITY FEED (Linear-style)
// =========================================================

function ActivitySection() {
  return (
    <Section title="Activity feed" description="Хронология изменений по сущностям. Стиль Linear — кто, что, когда, какой field, было/стало.">
      <div className={cx('rounded-lg max-w-3xl', surface)}>
        <div className={cx('px-5 py-3 border-b flex items-center justify-between', borderD)}>
          <div className="flex items-center gap-2">
            <Activity className={cx('w-4 h-4', textM)} />
            <span className={cx('text-sm font-medium', textP)}>История изменений</span>
          </div>
          <div className="flex items-center gap-1">
            <button className={cx('text-xs px-2.5 py-1 rounded-md', textS, hoverBtn)}>Все типы</button>
            <IconButton icon={Filter} title="Фильтр" />
          </div>
        </div>

        <div className="px-5 py-4 space-y-0">
          {ACTIVITY.map((a, i) => <ActivityItem key={a.id} item={a} isLast={i === ACTIVITY.length - 1} />)}
        </div>
      </div>
    </Section>
  );
}

function ActivityItem({ item, isLast }) {
  const w = TEAM[item.who];
  return (
    <div className="flex gap-3 relative">
      <div className="flex flex-col items-center shrink-0">
        <div className="relative z-10">
          <Avatar {...w} size="sm" />
        </div>
        {!isLast && <div className={cx('w-px flex-1 my-1', 'bg-stone-200 dark:bg-stone-800')} />}
      </div>
      <div className={cx('flex-1 min-w-0 pb-4', !isLast && 'border-b', borderD)}>
        <div className="flex items-baseline gap-1.5 flex-wrap">
          <span className={cx('text-sm font-medium', textP)}>{w.name}</span>
          <span className={cx('text-sm', textM)}>{item.action}</span>
          <span className={cx('text-[10px] uppercase tracking-wider', textL)}>{item.entity.kind}</span>
          <span className={cx('text-sm font-medium', textP)}>{item.entity.name}</span>
        </div>
        {item.change && (
          <div className="mt-1.5 flex items-center gap-2 flex-wrap text-[11px]">
            {item.change.from && (
              <>
                <span className={cx('px-1.5 py-0.5 rounded line-through',
                  item.meta?.from === 'red' ? 'bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400'
                  : cx(surfaceMuted, textL))}>
                  {item.change.from}
                </span>
                <ArrowRight className={cx('w-3 h-3', textL)} />
              </>
            )}
            <span className={cx('px-1.5 py-0.5 rounded font-medium',
              item.meta?.to === 'red' ? 'bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300'
              : item.meta?.to === 'emerald' ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300'
              : cx('bg-stone-100 dark:bg-stone-800', textP))}>
              {item.change.to}
            </span>
          </div>
        )}
        {item.count !== undefined && (
          <div className={cx('mt-1 text-[11px]', textM)}>+{item.count} {item.count === 1 ? 'элемент' : 'элементов'}</div>
        )}
        <div className="flex items-center gap-2 mt-1.5">
          <span className={cx('text-[11px]', textL)}>{item.time}</span>
          {item.field && (
            <Badge variant="gray" compact>
              <Hash className="w-2.5 h-2.5" />{item.field}
            </Badge>
          )}
        </div>
      </div>
    </div>
  );
}

// =========================================================
// SECTION 6: INBOX
// =========================================================

function InboxSection() {
  const [filter, setFilter] = useState('all');
  const filtered = filter === 'unread' ? INBOX_TASKS.filter(t => !t.read)
    : filter === 'high' ? INBOX_TASKS.filter(t => t.priority === 'high')
    : INBOX_TASKS;

  const typeIcon = {
    task: <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />,
    mention: <AtSign className="w-3.5 h-3.5 text-blue-500" />,
    review: <Eye className="w-3.5 h-3.5 text-purple-500" />,
    comment: <MessageSquare className="w-3.5 h-3.5 text-stone-400" />,
    system: <Info className="w-3.5 h-3.5 text-amber-500" />,
  };
  const priorityDot = {
    high: 'bg-rose-500', medium: 'bg-amber-500', low: 'bg-stone-300 dark:bg-stone-600',
  };

  return (
    <Section title="Inbox" description="Объединённый список задач, упоминаний, ревью. Главная страница для каждого члена команды.">
      <div className={cx('rounded-lg overflow-hidden', surface)}>
        <div className={cx('px-5 py-3 border-b flex items-center justify-between', borderD)}>
          <div className="flex items-center gap-2">
            <Inbox className={cx('w-4 h-4', textM)} />
            <span className={cx('text-base font-medium', textP)}>Входящие</span>
            <Badge variant="red" compact>{INBOX_TASKS.filter(t => !t.read).length} новых</Badge>
          </div>
          <Button size="sm" variant="ghost" icon={Check}>Отметить все</Button>
        </div>

        <div className={cx('px-5 py-2 border-b flex items-center gap-2', borderD)}>
          <div className="flex items-center gap-1">
            {[
              { v: 'all', label: 'Все', count: INBOX_TASKS.length },
              { v: 'unread', label: 'Непрочитанные', count: INBOX_TASKS.filter(t => !t.read).length },
              { v: 'high', label: 'Срочные', count: INBOX_TASKS.filter(t => t.priority === 'high').length },
            ].map(f => (
              <button key={f.v} onClick={() => setFilter(f.v)}
                className={cx('px-2.5 py-1 text-xs rounded-md transition-colors flex items-center gap-1.5',
                  filter === f.v ? 'bg-stone-900 text-white dark:bg-stone-50 dark:text-stone-900'
                  : cx(textS, hoverBtn))}>
                {f.label}
                <span className={cx('tabular-nums text-[10px] px-1 rounded',
                  filter === f.v ? 'bg-stone-700 dark:bg-stone-300 dark:text-stone-700' : cx('bg-stone-100 dark:bg-stone-800', textL))}>
                  {f.count}
                </span>
              </button>
            ))}
          </div>
          <div className="flex-1" />
          <IconButton icon={Filter} title="Дополнительные фильтры" />
        </div>

        <div className="divide-y divide-stone-200 dark:divide-stone-800">
          {filtered.map(t => {
            const f = t.from ? TEAM[t.from] : null;
            return (
              <div key={t.id} className={cx('px-5 py-3 flex items-center gap-3 cursor-pointer transition-colors',
                hoverRow, !t.read && 'bg-blue-50/30 dark:bg-blue-950/10')}>
                <span className={cx('w-2 h-2 rounded-full shrink-0', priorityDot[t.priority])} />
                <div className="shrink-0 flex items-center gap-2">
                  <div className={cx('w-6 h-6 rounded-md flex items-center justify-center', surfaceMuted)}>
                    {typeIcon[t.type]}
                  </div>
                  {f && <Avatar {...f} size="sm" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2">
                    <span className={cx('text-sm', !t.read ? cx('font-medium', textP) : textS)}>{t.title}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    {f && <span className={cx('text-[11px]', textM)}>от {f.name}</span>}
                    <span className={cx('text-[11px]', textL)}>·</span>
                    <Badge variant="gray" compact>{t.project}</Badge>
                  </div>
                </div>
                {t.due && (
                  <span className={cx('text-[11px] tabular-nums shrink-0',
                    t.due === 'сегодня' ? 'text-rose-600 dark:text-rose-400 font-medium' : textM)}>
                    {t.due}
                  </span>
                )}
                <button className={cx('p-1 rounded opacity-50 hover:opacity-100', hoverBtn)}>
                  <MoreHorizontal className={cx('w-3.5 h-3.5', textL)} />
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </Section>
  );
}

// =========================================================
// SECTION 7: THEME DEMO — side by side
// =========================================================

function ThemeDemoSection() {
  return (
    <Section title="Theme demo" description="Один и тот же экран бок о бок в светлой и тёмной теме. Так выглядит финальный результат для пользователя.">
      <div className="grid grid-cols-2 gap-4">
        <ThemedCardDemo theme="light" />
        <ThemedCardDemo theme="dark" />
      </div>
    </Section>
  );
}

function ThemedCardDemo({ theme }) {
  // Демо локально — оборачиваем в обёртку с принудительной темой
  return (
    <div className={cx(theme === 'dark' && 'dark')}>
      <div className={cx('rounded-lg overflow-hidden border',
        theme === 'dark' ? 'border-stone-800 bg-stone-950' : 'border-stone-200 bg-white')}>
        <div className={cx('px-4 py-3 border-b flex items-center justify-between',
          theme === 'dark' ? 'border-stone-800' : 'border-stone-200')}>
          <div className="flex items-center gap-2">
            {theme === 'light' ? <Sun className="w-4 h-4 text-stone-400" /> : <Moon className="w-4 h-4 text-stone-500" />}
            <span className={cx('text-[10px] uppercase tracking-wider',
              theme === 'dark' ? 'text-stone-500' : 'text-stone-400')}>{theme}</span>
          </div>
          <Badge variant="emerald" compact dot>В продаже</Badge>
        </div>
        <div className="p-5">
          <div className={cx('text-[10px] uppercase tracking-wider mb-1',
            theme === 'dark' ? 'text-stone-500' : 'text-stone-400')}>МОДЕЛЬ</div>
          <div style={{ fontFamily: "'Instrument Serif', serif" }}
            className={cx('text-2xl mb-3',
              theme === 'dark' ? 'text-stone-50' : 'text-stone-900')}>
            <em className="italic">Vuki</em> · основа коллекции
          </div>
          <div className={cx('text-sm leading-relaxed mb-4',
            theme === 'dark' ? 'text-stone-300' : 'text-stone-700')}>
            Базовая модель Lite. 24 артикула в 4 цветах, размерная линейка S-XL.
            Запущена в феврале, выручка май: 2.84M ₽.
          </div>
          <div className={cx('grid grid-cols-3 gap-3 pt-3 border-t',
            theme === 'dark' ? 'border-stone-800' : 'border-stone-200')}>
            {[
              { l: 'Артикулов', v: '24' },
              { l: 'Маржа', v: '34.2%' },
              { l: 'Рейтинг', v: '4.8' },
            ].map(s => (
              <div key={s.l}>
                <div className={cx('text-[10px] uppercase tracking-wider',
                  theme === 'dark' ? 'text-stone-500' : 'text-stone-400')}>{s.l}</div>
                <div className={cx('text-lg tabular-nums font-medium mt-0.5',
                  theme === 'dark' ? 'text-stone-50' : 'text-stone-900')}>{s.v}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// =========================================================
// APP — sidebar + topbar + theme
// =========================================================

const SECTIONS = [
  { id: 'kanban',   label: 'Kanban',        icon: Layers,        comp: KanbanSection,        group: 'Workflow' },
  { id: 'calendar', label: 'Calendar',      icon: Calendar,      comp: CalendarSection,      group: 'Workflow' },
  { id: 'comments', label: 'Comments',      icon: MessageSquare, comp: CommentsSection,      group: 'Communication' },
  { id: 'notif',    label: 'Notifications', icon: Bell,          comp: NotificationsSection, group: 'Communication' },
  { id: 'inbox',    label: 'Inbox',         icon: Inbox,         comp: InboxSection,         group: 'Communication' },
  { id: 'activity', label: 'Activity feed', icon: Activity,      comp: ActivitySection,      group: 'Communication' },
  { id: 'theme',    label: 'Theme demo',    icon: Sun,           comp: ThemeDemoSection,     group: 'Foundation' },
];

export default function App() {
  const [theme, setTheme] = useState('light');
  const [active, setActive] = useState('kanban');
  const Active = SECTIONS.find(s => s.id === active)?.comp || KanbanSection;
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
          <aside className={cx('w-60 shrink-0 h-screen sticky top-0 overflow-y-auto py-4 border-r', borderD, surfaceMuted)}>
            <div className={cx('px-4 pb-3 mb-2 border-b', borderD)}>
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center">
                  <Sparkles className="w-3.5 h-3.5 text-white" />
                </div>
                <div>
                  <div style={{ fontFamily: "'Instrument Serif', serif" }} className={cx('text-base leading-none', textP)}>
                    <em className="italic">Wookiee</em>
                  </div>
                  <div className={cx('text-[10px] uppercase tracking-wider mt-0.5', textL)}>DS v2 · Patterns</div>
                </div>
              </div>
            </div>

            {Object.entries(grouped).map(([group, items]) => (
              <div key={group} className="mb-3">
                <div className={cx('text-[10px] uppercase tracking-wider px-4 py-1.5', textL)}>{group}</div>
                {items.map(s => (
                  <button key={s.id} onClick={() => setActive(s.id)}
                    className={cx('w-full flex items-center gap-2.5 px-4 py-1.5 text-sm transition-colors',
                      active === s.id ? 'bg-stone-900 dark:bg-stone-50 text-white dark:text-stone-900 font-medium' : cx(textS, hoverBtn))}>
                    <s.icon className="w-3.5 h-3.5" />
                    <span>{s.label}</span>
                  </button>
                ))}
              </div>
            ))}

            <div className={cx('px-4 pt-3 mt-3 border-t', borderD)}>
              <div className={cx('text-[10px] uppercase tracking-wider mb-2', textL)}>Тема</div>
              <button onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
                className={cx('w-full flex items-center justify-between rounded-md px-3 py-1.5 text-sm border', borderD, hoverBtn, textS)}>
                <span className="flex items-center gap-2">
                  {theme === 'light' ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
                  {theme === 'light' ? 'Светлая' : 'Тёмная'}
                </span>
                <span className={cx('text-[10px] font-mono', textL)}>⌘⇧L</span>
              </button>
            </div>
          </aside>

          <main className="flex-1 min-w-0">
            <div className={cx('h-14 px-6 border-b flex items-center justify-between sticky top-0 z-30', borderD, surface)}>
              <div className="flex items-center gap-3">
                <div className={cx('text-[11px] uppercase tracking-wider', textL)}>Wookiee Hub · DS v2</div>
                <ChevronRight className={cx('w-3 h-3', textL)} />
                <div className={cx('text-sm font-medium', textP)}>{SECTIONS.find(s => s.id === active)?.label}</div>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="secondary" size="sm" icon={Eye}>Preview в проде</Button>
                <IconButton icon={theme === 'light' ? Moon : Sun} title="Переключить тему"
                  onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')} />
              </div>
            </div>

            <div className="px-8 py-8 max-w-6xl">
              <div className="mb-8">
                <div className={cx('text-[11px] uppercase tracking-wider mb-1', textL)}>Дизайн-система v2 · Паттерны</div>
                <h1 style={{ fontFamily: "'Instrument Serif', serif" }} className={cx('text-4xl mb-2', textP)}>
                  <em className="italic">{SECTIONS.find(s => s.id === active)?.label}</em>
                </h1>
                <div className={cx('text-sm max-w-2xl', textM)}>
                  Сложные UX-паттерны на mock-данных. Все компоненты адаптированы под светлую и тёмную темы. Kanban работает с реальным drag-n-drop через нативный HTML5 API.
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
