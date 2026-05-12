# DS v2 fidelity drift report

> Audit target: `feat/ds-v2-migration` HEAD on `chore/hygiene-2026-05-09-followup`. Compared file-by-file against `/Users/danilamatveev/Projects/Wookiee/docs/handoff/2026-05-design-system/wookiee_ds_v2_foundation.jsx` (2704 строки), `wookiee_ds_v2_patterns.jsx` (1590 строк) и `DESIGN_SYSTEM.md`.

> Important framing per audit brief: the deliberate divergence — canonical использует Tailwind `dark:` prefix, current использует `data-theme` + semantic utilities — **не считается drift**. Drift фиксируется только когда финальный визуал (цвет, размер, поведение, набор вариантов, типографика) расходится с эталоном.

## Summary

- **Tokens (Layer A):** ⚠️ DRIFT — accent hex и token recipe в `tokens.css` корректны, но `index.css` параллельно держит legacy shadcn-овский `oklch` слой с `--primary` ≈ `#7c3aed` (violet-600), задающий primary через `--primary` для shadcn-компонентов. Семантика двойная — компоненты ui-v2 не используют сам shadcn slot, поэтому фактически рабочая палитра OK, но «брандовый» purple = `accent`, а primary в Button = `text-primary` (stone-900). По DS это корректно (§11: primary = stone-900, не цветной). `--color-border-subtle` отсутствует в спецификации §12, добавлен сверх — не drift, но extension.
- **Primitives (Layer B):** 🔴 КРИТИЧЕСКИЙ DRIFT.
  - `Button` — отсутствуют canonical variants `danger-ghost` и `success`; canonical `size` scale включает `xs` (28px×px-2/py-1), который удалён; canonical отдает `Button` без `iconRight` и без `loading` (loading спин canonical делает только в Toast).
  - `IconButton` — canonical работает в трёх режимах: `default | danger | active | title`; canonical default — ghost stone-700, у нас введён полный variant-набор `primary/secondary/ghost/destructive` + `loading`, что shape-compatible, но `IconButton` canonical размер всегда **p-1.5 → 28×28**, у нас md=32×32 (`w-8 h-8`). Это +4px, видно в плотных тулбарах.
  - `Badge` — палитра разъехалась. Canonical вариаты: `emerald | blue | amber | red | purple | orange | gray`, у нас `default | accent | success | warning | danger | info`. То есть отсутствуют brand-варианты `purple` и `orange`, нет нейтрального `gray`/`amber` под именами стека. Canonical Badge поддерживает `dot` и `compact` props — у нас compact = `size='sm'`, dot props нет. Это означает `<Badge variant="emerald" dot>+12.4%</Badge>` из эталона не компилируется.
  - `StatusBadge` — **полное расхождение модели данных**. Canonical: `<StatusBadge statusId={1..5} />`, маппинг через `STATUS_MAP` (1=В продаже emerald, 2=Запуск blue, 3=Выводим amber, 4=Не выводится red, 5=Архив gray). У нас `<StatusBadge tone="success|warning|danger|info|muted">{children}</StatusBadge>`. Преобразование `statusId → tone` отсутствует, никакого STATUS_MAP в кодовой базе нет.
  - `LevelBadge` — **полное расхождение семантики**. Canonical: `<LevelBadge level="model|variation|artikul|sku" />` → отображает букву (M/V/A/S) с цветами blue/purple/orange/emerald — это маркеры уровня каталога Wookiee (модель/вариация/артикул/SKU). У нас `<LevelBadge level="P0|P1|P2|P3" />` — приоритеты задач. Это другой компонент с тем же именем; согласно DS чеклисту §10 «все формы используют LevelBadge через FieldWrap» (FieldWrap имеет `level` prop в эталоне на стр. 465) — значит во всех формах будет broken.
  - `Chip` — у нас только `selected` boolean (toggle-chip). У canonical chip = removable token (`<Chip onRemove={...}>Vuki</Chip>`), close-button inline. Это два разных UX-паттерна. В preview (`pages/design-system-preview/index.tsx:203`) уже видно `<Tag onRemove>` подменяет canonical Chip — что лишь скрывает проблему.
  - `Avatar` — canonical имеет `color` prop (stone/emerald/blue/amber/purple/rose/teal) + `initials` prop. У нас: `name → getInitials()` (auto), без `color`. Все аватары → один stone-серый. Цветовая дифференциация команды утеряна.
  - `ColorSwatch` — canonical — пассивный `<span>` со swatch + опциональным mono-label, размер задаётся числом `size={16}`. У нас — интерактивный `<button>` с selected/check overlay, размер preset `sm/md/lg`, label выкинут. Это shape-incompatible — DemoTable/CSS-палитры из эталона не отрендерятся.
  - `Tag` — у нас наследует BadgeVariant (default/accent/success/...), canonical: `color: gray|blue|emerald` ограниченный набор + размер `text-[11px] px-1.5 py-0.5` (canonical Tag меньше Badge). У нас Tag === Badge по размеру (`h-5/h-6`).
  - `ProgressBar` — у нас 4 варианта (default/success/warning/danger), canonical 5: добавляется `blue` (info-окраска для нейтрального прогресса). По DS §6 «color (stone/emerald/blue/amber/red)».
  - `Ring` — у нас `value` в шкале 0..100 + `pickVariant` по порогам 85/60/40. Canonical: `value` в шкале 0..1 (`Ring value={0.92}`); пороги тоже 0.85/0.6/0.4; цвета хардкодом hex (#059669, #2563EB, ...). Shape OK, но шкала разная — `<Ring value={0.92}>` из эталона у нас даст 1% заливки.
  - `Tooltip` — canonical text-prop + position top/bottom только. У нас `content` (ReactNode) + position top/bottom/left/right + delay 150ms + portal. Это апгрейд, но `text` prop из эталона не работает. В preview уже видно `<Tooltip content="...">` вместо `text` — переименование.
  - `Kbd` — canonical: `border-stone-200 dark:border-stone-700 bg-stone-50 dark:bg-stone-800 text-[10px] font-mono px-1.5 py-0.5`. У нас: `bg-surface-muted` + shadow `inset 0 -1px 0 border-default` + `h-5 min-w-[1.25rem]`. Добавлен inset shadow — отступление от canonical (canonical Kbd плоский). Минор, но визуально заметен.
  - `Skeleton` — canonical `bg-stone-200 dark:bg-stone-800 rounded`. У нас `bg-surface-muted rounded-md`. Цвет `surface-muted` в dark = `stone-900/60%` — это значительно темнее чем `stone-800`. Скелетоны будут не контрастировать с фоном в dark.
  - `PermissionGate` — не существует в canonical (это локальная придумка для маркера прав). Не drift, но extension вне DS.
- **Forms (Layer C):** 🔴 КРИТИЧЕСКИЙ DRIFT.
  - `FieldWrap` — canonical: `label` row с встроенным `<LevelBadge level={level} />`, `level` принимается prop'ом. У нас: `labelAddon` слот, `level` нет — а так как LevelBadge сменил семантику (см. выше), все каталожные формы потеряют M/V/A/S маркер уровня. По §10 чеклиста это блокер.
  - `TextField` — canonical поддерживает `mono` prop (font-mono text-xs) для технических артикулов; canonical `prefix` может быть строкой ("₽") или иконкой, canonical `suffix` тоже. У нас `mono` нет (надо передавать `inputClassName`), `prefix`/`suffix` только ComponentType (иконки). DS §4 / §6 — для технических значений `mono` обязателен.
  - `NumberField` — `suffix` у нас `ReactNode`, у canonical — строка. Shape совместимо, но canonical suffix-style `text-sm text-stone-400` vs у нас `text-xs text-muted` + `tabular-nums` (отступ при `pr-10`). Differ in size.
  - `SelectField` — canonical: `options: [{id, nazvanie}]`, native `<select>` с lucide ChevronDown оверлеем. У нас: full custom listbox с keyboard nav, searchable mode, опции `{value, label}`. Это значительный апгрейд UX, но shape `{id, nazvanie}` сломан — все WB-связанные SelectField на старом контракте упадут. По DS §6 явно зафиксировано `options [{ id, nazvanie }]`.
  - `MultiSelectField` — canonical: chips-toggles inline (НЕ dropdown) — кнопки в строку, цвет stone-900 при active. У нас: dropdown listbox с поиском + chip-preview сверху. По DS §6: «MultiSelectField — chips-toggles, не dropdown». Это явное нарушение спецификации.
  - `TextareaField` — у нас `autoResize` + maxLength counter. Canonical: simple `rows=3 resize-none` без счётчика. Extension OK, но добавочный `text-[10px] text-muted text-right` counter — отступление от спартанского DS.
  - `DatePicker` — canonical: поддерживает `range` prop (`<DatePicker range>`) с `value = {from, to}`. У нас: только single date. По §6 «single или range» — range отсутствует.
  - `TimePicker` — в canonical есть (foundation.jsx:634). У нас отсутствует целиком.
  - `Combobox` — canonical: trigger button с ChevronsUpDown справа, popover с Input(icon=Search) + listbox. У нас: input всегда активен, ChevronsUpDown + clear X. Это разные паттерны UX (canonical = closed-state button, наш = always-open input).
  - `FileUpload` — canonical: `files` prop массив `[{name, size}]`, drop zone monochrome + список файлов pill-карточек. У нас: `File[]` объекты, drop zone становится `border-accent bg-accent-soft` при drag (violet brand-цвет — допустимо), file size auto-format. Shape: canonical `files`, у нас `value`. По DS §6 fileupload должен показывать «список файлов» — у нас ok.
  - `ColorPicker` — canonical: 9-цветная палитра + hex input. У нас отсутствует целиком.
- **Layout (Layer D):** ⚠️ DRIFT по `Tabs`/`PageHeader`/`Stepper`.
  - `Tabs` — canonical: `underline | pill | segmented`. У нас: `underline | pills | vertical`. ⚠️ `segmented` (форматы отображения list/grid/kanban из DS §6 → Three variants) отсутствует. `vertical` — добавлено сверх. `underline` rendering: canonical у tab badge — `min-w-[18px] h-[18px] px-1 text-[10px] rounded-full` background switches white→stone-900; у нас `CountBadge` использует те же размеры, fine. `pills`: canonical container — `bg-stone-100 dark:bg-stone-800`, активный pill — `bg-white shadow-sm`; у нас — `bg-surface-muted border border-default`, активный — `bg-surface shadow-xs`. Семантика та же, но canonical pills НЕ имеет border контейнера — у нас есть. Visual drift.
  - `Breadcrumbs` — canonical: items: array of strings, последний — `text-primary font-medium`. У нас: items: `[{label, href?}]` с react-router Link. Shape различается. По DS §6 это OK extension, но preview из эталона передаёт `['Hub','Каталог',...]` массивы строк → у нас падает.
  - `Stepper` — у нас `current` index + array `[{label}]`, рисует connector между. Canonical то же. ⚠️ Высота кружков ОДНА — canonical w-7 h-7, у нас w-7 h-7. Соответствие. Connector у canonical `mt-[-16px]` (поднят, чтобы попадал в центр кружка), у нас `mt-3.5 mx-2` — это смещение коннектора на пол-высоты кружка. Визуально проверь — может оказаться сдвинутым.
  - `PageHeader` — 🔴 **серьёзный drift**. Canonical: `kicker (uppercase) + Instrument Serif title text-3xl + breadcrumbs + status badge + actions`. У нас: `icon + Instrument Serif text-4xl title + description (sm) + actions`. Не хватает: `kicker` (UPPERCASE label сверху, например «МОДЕЛЬ»), `breadcrumbs` slot, `status` slot (для StatusBadge рядом с title). Заменены на `icon + description` — это другой компонент. Title-size: canonical `text-3xl`, у нас `text-4xl`. По §4 шкале `text-3xl + Instrument Serif italic` это section-title, `text-4xl` — это страница. У нас зависит от того, какой контекст.
  - `Sidebar` — у нас compositional API (Sidebar.Header/Nav/Section/Item/Footer) + collapsed prop. Canonical: inline компонент в App() (foundation.jsx:2625+) с группами → пунктами → активным `bg-stone-900 text-white`. По §6 «Группы → пункты с иконкой → активный fill stone-900» — у нас активный `bg-[var(--color-text-primary)] text-[var(--color-surface)]` == stone-900 → white → ✅ совпадает. Brand block в canonical: `7×7 rounded bg-gradient-to-br from-purple-500 to-purple-700 + Sparkles icon`. У нас Sidebar.Header — обёртка без brand block. Поэтому когда страница преview рендерит свой собственный header, не использует Sidebar — сравнение неровное.
  - `TopBar` — у нас sticky h-14 с breadcrumbs+actions+children. Canonical: `h-14 px-6 + kicker-style "Wookiee Hub · Design System" UPPERCASE + ChevronRight + active section label + actions (Export tokens button + theme IconButton)`. Шапка эталона построена под состояние preview, у нас TopBar генерик. По §6: «PageHeader — kicker + Instrument Serif title + breadcrumbs + status + actions» — это про PageHeader, не TopBar. Для preview-страницы canonical именно эту смешанную шапку и использует (foundation.jsx:2674).
- **Overlays (Layer E):** ⚠️ умеренный DRIFT.
  - `Modal` — у нас portal, focus-trap, `bg-black/40 backdrop-blur-sm`, sizes sm/md/lg/xl с max-w-sm/lg/2xl/4xl. Canonical: `bg-stone-900/40 dark:bg-black/60` (более тёплый бэкдроп в light, у нас всегда черный 40%). Анимаций нет ни там, ни там. Header layout совпадает. Footer — у canonical inline в children (через footer-prop передаётся ReactNode). У нас footer тоже отдельный prop. ✅.
  - `Drawer` — у нас 4 sides (right/left/top/bottom), у canonical 2 (right/bottom). Right: canonical `w-[420px]`, у нас `md=560px` (preset). У DS §6 эксплицитно: «side='right' (фильтры, детальные карточки) или 'bottom' (bulk-edit)» + Kanban detail drawer — `560px`. То есть `md=560` корректно. Default `w-420` отсутствует. По pattern docs Kanban Detail Drawer: «Открывается справа (560px)» — наш md OK для этого случая.
  - `Popover` — у нас portal-based, computed position (clamped в viewport), placement top/bottom/left/right. Canonical: inline `<div>` с positions `bottom-start/bottom-end/top-start`. Apgrade у нас, не drift по визуалу, но shape `position='bottom-start'` из эталона не работает.
  - `DropdownMenu` — canonical: items with `icon, shortcut, divider, danger`. У нас: same shape + keyboard nav. ✅
  - `ContextMenu` — same shape, у нас portal+clamped. ✅
  - `CommandPalette` — у нас group support + keyboard arrows + дефолтный empty msg. Canonical: results с `type` (UPPERCASE label слева в 16ch колонке) + `label` + `sub` + ArrowRight справа. У нас рендер близкий: leading icon (или 3.5×3.5 space) + label + description + shortcut + ArrowRight. Canonical же делает в первой колонке UPPERCASE «type tag» — у нас аналог `group` секций header. Семантика разная: canonical = метка типа на каждом item, у нас = группировка items в секции с группа-headers. Видимый result в preview-показе будет отличаться.
- **Feedback (Layer F):** ⚠️ умеренный DRIFT.
  - `Toast` — у нас singleton store + ToastProvider portal + 5 вариантов default/success/warning/danger/info с иконками Bell/CheckCircle2/AlertTriangle/XCircle/Info. Canonical: 5 вариантов success/error/info/warning/loading (loading с Loader2 spin). У нас нет `loading` варианта (canonical Toast `variant='loading'` со спиннером — отсутствует). По DS §6 «success/error/info/warning/loading» — drift, надо добавить.
  - `Alert` — у нас 5 вариантов default/success/warning/danger/info с прозрачным `border-[color:var(--color-...)]/30`. Canonical: 4 (info/success/warning/error) с hex-prepared classes `bg-blue-50 border-blue-200 text-blue-900`. По цветовой палитре эквивалентно. ✅
  - `EmptyState` — у нас Inbox-default icon, `text-label` цвет, title `text-sm font-medium`, description `text-xs italic`. Canonical то же (Box-default icon вместо Inbox). По DS §6 «icon + title + description italic + action» — соответствует.
- **Preview page (Layer G):** 🔴 КРИТИЧЕСКИЙ DRIFT (см. ниже).
- **Patterns (Layer H):** 🔴 НЕ РЕАЛИЗОВАНО (см. ниже).

---

## Layer A — tokens.css

| Item | Canonical (§12) | Current (`src/styles/tokens.css` + `src/index.css`) | Drift |
|---|---|---|---|
| `@theme` block | Light: page=stone-50, surface=white, surface-muted=stone-50, elevated=white, text-primary=stone-900, text-secondary=stone-700, text-muted=stone-500, text-label=stone-400, border-default=stone-200, border-strong=stone-300 | tokens.css 23-36: same. ✅ | OK |
| `[data-theme='dark']` | page=stone-950, surface=stone-900, surface-muted=stone-900/40%, elevated=stone-800, text-primary=stone-50, text-secondary=stone-300, text-muted=stone-400, text-label=stone-500, border-default=stone-800, border-strong=stone-700 | tokens.css 104-119: same. Note: `surface-muted = stone-900 / 60%` — спец требует `40%`. **DRIFT** | ⚠️ surface-muted opacity 60% vs 40% (tokens.css:107). Subtle, but mismatched. |
| `border-subtle` | Not in spec §12 | tokens.css:37/120: added | Extension — neutral. |
| Brand accent | `#7C3AED` = violet-600. Spec text says "Purple" but hex matches `violet`. | tokens.css:40: `--color-accent: theme(colors.violet.600)` = #7C3AED. ✅ | OK |
| Brand accent dark | -300 shift per spec §2 | tokens.css:122: `theme(colors.violet.400)` — это -200 shift не -300. DS §2 «семантические цвета сдвигаются в более светлую сторону (-300 оттенок)» → должен быть `violet.300`. | ⚠️ off-by-one tone (400 vs 300). |
| Status `--color-success` light | emerald-600 | tokens.css:46: emerald.600. ✅ |  |
| Status soft light | emerald-50 (DS уровень) | tokens.css:47: `emerald.100` (DS §6 Badge canonical: `bg-emerald-50`). **DRIFT** — Badge soft fill = emerald-100 вместо emerald-50. Светлый фон станет насыщеннее. | ⚠️ |
| Status dark soft | `-950/40` per spec §2 | tokens.css:129: `emerald.900 / 40%` (стало 900 а не 950 + 40%). Спец говорит `-950/40`. | ⚠️ off-by-one tone (900 vs 950). |
| `--color-info` | blue-600 | tokens.css:52: `blue.600`. ✅ |  |
| `--color-warning` | amber-600 | tokens.css:48: `amber.600`. ✅ |  |
| `--color-danger` | rose / red-600 (`#E11D48`) | tokens.css:50: `red.600` = `#dc2626`. **DRIFT**. Spec §2: «Red/Rose #E11D48» — это `rose-600` (`#E11D48`). Tailwind `red-600` = `#DC2626`. У нас потеряно «rose» направление (более тёплый красный). canonical foundation.jsx использует `bg-rose-600`/`text-rose-600`/`bg-rose-50` повсюду для danger. | 🔴 brand danger hex mismatch. |
| Focus ring | spec §10: «Focus — обводка border-stone-900 focus:ring-1 ring-stone-900 (не синяя)» | tokens.css:56: `--color-ring: theme(colors.violet.600)`. **DRIFT**. По DS focus = stone-900, не violet/blue. Brand accent применяется к navigation activity, но фокус полей формы — нейтральный. Forms `_shared.ts:12` тоже использует `--color-ring`. | 🔴 focus ring brand instead of stone — нарушает §10. |
| `--shadow-*` | Not in §12 (DS §11: «никаких теней на статичных карточках, исключение Kanban») | tokens.css:68-72: defined + dark variant. | OK extension. |
| `--duration-*` / `--ease-*` | Not in §12 | tokens.css:75-81: defined. | OK extension. |
| `--breakpoint-*` | sm=768 md=1024 lg=1280 xl=1536 (per DS §10 mobile bullet) | tokens.css:84-87: same. ✅ |  |
| `@theme inline` legacy block in index.css | NOT in spec | index.css:143-263 — full shadcn OKLCH layer with `--primary` ≈ violet-600 in OKLCH. Parallels `tokens.css`. Different naming scheme. | ⚠️ Two truth-sources for tokens coexist. Risk: code reaches into legacy `--primary`/`--accent` instead of `--color-text-primary`/`--color-accent`. Audit confirmed all ui-v2 primitives ссылаются на новый layer (`var(--color-text-primary)`), но caталог/CRM/etc — на legacy. Cleanup pending. |
| `@utility text-primary` etc. | Spec §12 lists semantic utilities | tokens.css:166-227: full set incl. `bg-page bg-surface bg-surface-muted bg-elevated text-primary text-secondary text-muted text-label border-default border-strong border-subtle bg-accent bg-accent-soft text-accent border-accent text-success text-warning text-danger text-info bg-*-soft ring-focus`. ✅ |  |

**Priority for Layer A:**
- 🔴 `--color-danger` = red.600 → must be `rose.600` (Tailwind hex `#E11D48`).
- 🔴 `--color-ring` = violet.600 → must be `stone-900` (use `--color-text-primary` or hex `#1C1917`).
- ⚠️ `surface-muted` dark opacity 60% → 40%.
- ⚠️ dark accent/status soft tone (-200/-900 vs -300/-950).
- ⚠️ status-soft light (-100 vs -50).

---

## Layer B — primitives (per-component)

| Component | Canonical (foundation.jsx line/§) | Current (`src/components/ui-v2/primitives/*.tsx`) | Drift |
|---|---|---|---|
| `Button` | foundation.jsx:177-201. Variants: `primary / secondary / ghost / danger / danger-ghost / success`. Sizes: `xs / sm / md / lg` (xs = `px-2 py-1 text-xs`). Primary = `bg-stone-900 text-white` (dark inversion). | Button.tsx:5-43. Variants: `primary / secondary / ghost / destructive`. Sizes: `sm / md / lg`. Primary uses `var(--color-text-primary)` (=stone-900). ✅ for primary. | 🔴 Missing variants `danger-ghost` and `success`. Missing size `xs` (28px height). `destructive` renamed from `danger`. |
| `IconButton` | foundation.jsx:203-213. Single shape `p-1.5 rounded-md w-4 h-4` icon, props: `active, danger, title`. Sizes — none (always 28×28). | IconButton.tsx:5-80. 4 variants + 3 sizes. Default md = 32×32. | ⚠️ Default size grew from 28→32 (+4px). `danger` flag → `variant='destructive'`. `title` semantics moved to `aria-label`. Visual drift in toolbars. |
| `Input` (base) | foundation.jsx:215-233. Inline, h≈30px (`py-1.5`), border-stone-200, focus border-stone-900 + ring-1 ring-stone-900. Has icon/prefix/suffix/error. | No standalone `Input` primitive — only `inputBase` constants in forms/_shared.ts:8-13 with `h-8`, border-default, focus ring **violet**. | 🔴 Focus ring brand. Height delta minor (h-8 = 32 vs canonical ~30). No standalone Input — every form composes from base, so styles consistent inside forms only. |
| `Checkbox` | foundation.jsx:235-245. `w-3.5 h-3.5 rounded accent-stone-900`. | **Not in `primitives/`** — only used via plain `<input type="checkbox" />` in pages. | 🔴 Missing entirely as DS component. |
| `Radio` | foundation.jsx:247-255. `w-3.5 h-3.5 accent-stone-900`. | **Not in `primitives/`.** | 🔴 Missing. |
| `Toggle` | foundation.jsx:257-269. `w-9 h-5 rounded-full`, `bg-stone-900` on, `bg-stone-200` off; thumb `w-4 h-4` slides 0.5→4. | **Not in `primitives/`.** | 🔴 Missing. DS §5 «Toggle — 20×36px» (i.e. w-9 h-5) explicit requirement. |
| `Slider` | foundation.jsx:271-279. Native range + tabular value display. | **Not in `primitives/`.** | 🔴 Missing. DS §6 lists Slider as atom. |
| `Badge` | foundation.jsx:281-300. Variants: `emerald / blue / amber / red / purple / orange / gray`. Props: `dot, icon, compact`. Base classes: `rounded-md ring-1 ring-inset font-medium px-2 py-0.5 text-xs` (compact `px-1.5 py-0.5 text-[11px]`). | Badge.tsx:4-31. Variants: `default / accent / success / warning / danger / info`. Sizes `sm / md` (h-5 px-1.5 vs h-6 px-2). Border instead of ring-inset. No `dot` prop. | 🔴 Variant rename (color names → semantic names); missing `purple`, `orange`, `amber` direct color choices; no `dot` prop; uses `border` (1px allocates layout space) instead of ring-1 ring-inset (no layout shift). |
| `StatusBadge` | foundation.jsx:302-306, STATUS_MAP at 148-154. Single prop `statusId: 1..5`. Maps to Badge with predefined label+color. | StatusBadge.tsx. Prop `tone` + children. No STATUS_MAP, no statusId. | 🔴 **Complete semantic mismatch.** Migration cannot proceed for каталог/SKU table until STATUS_MAP layer exists. |
| `LevelBadge` | foundation.jsx:308-315. `level: 'model'/'variation'/'artikul'/'sku'` → letter M/V/A/S badge in colors blue/purple/orange/emerald. | LevelBadge.tsx. `level: 'P0'/'P1'/'P2'/'P3'` (priorities) → danger/warning/info/default. | 🔴 **Wrong domain.** Canonical = catalog hierarchy markers (used in FieldWrap). Current = task priorities. Catalog forms cannot render correct level markers. |
| `Chip` | foundation.jsx:317-329. `<span>` token, `bg-stone-100`, with optional onRemove (X icon). Not interactive. | Chip.tsx. `<button>` toggle with `selected` state, no onRemove. Rounded-full pill. | 🔴 **Different paradigm.** Canonical Chip = removable tag. Current Chip = selectable filter pill (which canonical doesn't have at all — those are Tabs `pill` variant or MultiSelect chips). |
| `Avatar` | foundation.jsx:331-350. `initials, color, size, status, src`. `color: stone/emerald/blue/amber/purple/rose` (+`teal` in patterns). Color = gradient `from-X-500 to-X-700 text-white`. | Avatar.tsx. `name, size, status, src`. No `color` prop. Single style: `bg-surface-muted text-secondary border`. | 🔴 No team-color support. All avatars monochrome. DS §6 explicitly lists `color` with 6 options. |
| `AvatarGroup` | foundation.jsx:352-371. `users: [{initials, color}]`, max, size. Overlap via negative ml. | AvatarGroup.tsx. Compatible API but inherits Avatar (no color). | ⚠️ Same as Avatar — `users: [{name}]` only. |
| `ColorSwatch` | foundation.jsx:373-381. Passive `<span>` with `hex` + size (number px) + optional mono label. | ColorSwatch.tsx. Interactive `<button>` with selected/check overlay, size presets sm/md/lg, no label. | 🔴 Shape mismatch. `<ColorSwatch hex="#1C1917" label="#1C1917" />` from canonical doesn't compile. |
| `ProgressBar` | foundation.jsx:383-400. `color: 'stone'/'emerald'/'blue'/'amber'/'red'`. `h-1.5` default, `h-1` compact. | ProgressBar.tsx. `variant: 'default'/'success'/'warning'/'danger'`. Missing `blue` (info) variant. | ⚠️ Missing blue/info variant. Color names changed. |
| `Ring` | foundation.jsx:402-412. `value: 0..1`, `size` number px, color computed from thresholds 0.85/0.6/0.4 (emerald/blue/amber/rose hex). | Ring.tsx. `value: 0..100`, thresholds 85/60/40, variant override option. | 🔴 **Scale mismatch.** Canonical `<Ring value={0.92}>` renders as 0.92% with current code. |
| `Tooltip` | foundation.jsx:414-431. `text: string`, position top/bottom, inline span with hover. `bg-stone-900 text-white text-[11px] px-2 py-1 rounded shadow-sm`. | Tooltip.tsx. `content: ReactNode`, position 4-way, portal, delay=150ms. Style matches. | ⚠️ Prop renamed `text` → `content`. Upgrade in behavior. |
| `Skeleton` | foundation.jsx:433-435. `bg-stone-200 dark:bg-stone-800 rounded`. | Skeleton.tsx. `bg-surface-muted rounded-md`. | ⚠️ In dark, `surface-muted = stone-900/60%` is darker than `stone-800` — low contrast on stone-900 surface. |
| `Kbd` | foundation.jsx:437-444. `border-stone-200/700 bg-stone-50/800 text-[10px] font-mono px-1.5 py-0.5`. Flat. | Kbd.tsx. `bg-surface-muted text-secondary border-default` + `shadow-[inset_0_-1px_0_var(--color-border-default)]` + `min-w-[1.25rem] h-5`. | ⚠️ Added inset shadow (3D effect). Canonical Kbd is flat. |
| `Tag` | foundation.jsx:446-459. `color: 'gray'/'blue'/'emerald'` — small set. `text-[11px] px-1.5 py-0.5 rounded font-medium`. Smaller than Badge. | Tag.tsx. Inherits BadgeVariant (default/accent/success/warning/danger/info), Badge sizes `sm/md`. Same size as Badge. | ⚠️ Tag became Badge twin. Canonical Tag specifically smaller (text-[11px] vs Badge text-xs). |
| `PermissionGate` | Not in canonical. | New component. | Extension, not drift. |

---

## Layer C — forms

| Component | Canonical | Current | Drift |
|---|---|---|---|
| `FieldWrap` | foundation.jsx:465-477. Renders label-row with `<LevelBadge level={level} />` inside. Hint + error below. Props: `label, level, hint, error`. | FieldWrap.tsx. Generic `labelAddon` slot (caller passes element). No `level` prop. | 🔴 Catalog form contract broken — `<FieldWrap level="model">` from canonical references LevelBadge (which itself has wrong semantics). |
| `TextField` | foundation.jsx:479-486. `mono` prop applies `font-mono text-xs`. Wrapped in FieldWrap with `level`. | TextField.tsx. No `mono` prop (caller must use `inputClassName`). | ⚠️ Convenience prop missing — required by DS §10 «Технические значения — font-mono text-xs». |
| `NumberField` | foundation.jsx:488-494. `suffix: '₽'|'%'|'шт'` string. | NumberField.tsx. `suffix: ReactNode` rendered as `text-xs text-muted tabular-nums`. | ⚠️ Suffix style: canonical `text-sm text-stone-400`, current `text-xs text-muted`. Visual drift (xs vs sm). |
| `SelectField` | foundation.jsx:496-512. Native `<select>` with `options: [{id, nazvanie}]`. Lucide ChevronDown overlay. | SelectField.tsx. Custom listbox with `options: [{value, label}]`, searchable mode, keyboard nav. | 🔴 **Option-shape mismatch.** WB-fed options have `{id, nazvanie}` — won't render. Behavioral upgrade good, but contract broken. |
| `MultiSelectField` | foundation.jsx:514-533. **Chips-toggles inline** — array of buttons in a row, active = `bg-stone-900 text-white`. | MultiSelectField.tsx. Dropdown listbox with search + chip preview header. | 🔴 **Wrong UX paradigm.** DS §6 explicitly: «MultiSelectField — chips-toggles, не dropdown». Canonical shows all options as togglable chips at once; current hides them behind dropdown. |
| `TextareaField` | foundation.jsx:535-544. `rows=3`, `resize-none`. Simple. | TextareaField.tsx. Adds `autoResize`, `maxLength` counter. | ⚠️ Extensions OK but counter row creates extra layout. |
| `DatePicker` | foundation.jsx:547-577 + CalendarGrid 579-632. Supports `range` prop (returns `{from, to}`). | DatePicker.tsx. Single date only. | 🔴 No range support. DS §6 «single или range». |
| `TimePicker` | foundation.jsx:634-649. `<select>` with 30-min steps. | **Missing.** | 🔴 Not implemented. |
| `Combobox` | foundation.jsx:651-693. Closed state = button + selected label + ChevronsUpDown; opens to Input+listbox. | Combobox.tsx. Input always rendered as primary control + clear X. | ⚠️ Different UX — canonical = combobox button; current = autocomplete input. |
| `FileUpload` | foundation.jsx:695-725. `files: [{name, size}]` plain objects. Drop zone monochrome (stone-300 / stone-900 on drag). | FileUpload.tsx. Real `File[]`. Drop zone uses `border-accent bg-accent-soft` (violet) on drag. | ⚠️ Drag-active uses brand violet — per §11 anti-pattern «3D-индикаторы, дикий цвет вне brand» — accent IS brand, technically OK, but DS visual is monochrome stone for forms (forms are «холодный спокойный визуал»). |
| `ColorPicker` | foundation.jsx:727-745. 9-color palette + hex Input. | **Missing.** | 🔴 Not implemented. Required by DS §6. |

---

## Layer D — layout

| Component | Canonical | Current | Drift |
|---|---|---|---|
| `Tabs` | foundation.jsx:2039-2090. Variants: `underline / pill / segmented`. | Tabs.tsx. Variants: `underline / pills / vertical`. | 🔴 Missing `segmented`. `vertical` added (extension). `pills` container has extra `border border-default` not in canonical. |
| `Breadcrumbs` | foundation.jsx:2092-2105. `items: string[]`, last = primary+medium. | Breadcrumbs.tsx. `items: [{label, href?}]` w/ react-router Link. | ⚠️ Shape mismatch — string-array contract broken; api upgrade OK. |
| `Stepper` | foundation.jsx:2107-2130. `steps: string[]`, `current: number`. Connector `mt-[-16px]` (centered on circle). | Stepper.tsx. `steps: [{label, status?}]`, `current` index. Connector `mt-3.5 mx-2`. | ⚠️ Shape mismatch + connector position off-center. Visually drift. |
| `PageHeader` | foundation.jsx:2132-2146. Props: `title, kicker, breadcrumbs, status, actions`. Inside `surface` card with `border-b`. Title `text-3xl` Instrument Serif. | PageHeader.tsx. Props: `title, description, actions, icon`. No card wrap. Title `text-4xl` Instrument Serif. | 🔴 Different shape: missing `kicker` (UPPERCASE label), `breadcrumbs` slot, `status` slot. Added `icon` + `description`. Title size +1 step. |
| `Sidebar` | foundation.jsx:2625-2670 inline. Brand block at top: `7×7 rounded bg-gradient-to-br from-purple-500 to-purple-700 + Sparkles icon`. Groups with `text-[10px] uppercase` headers. Active item `bg-stone-900 text-white`. | Sidebar.tsx — compositional API (Sidebar.Header / Nav / Section / Item / Footer). Active item = `bg-[var(--color-text-primary)] text-[var(--color-surface)]` ✅. | ✅ Visually matches when consumer composes correctly. Brand block must be supplied by caller (canonical hard-codes it; current expects Sidebar.Header content from page). Preview doesn't use Sidebar at all — so visual disparity in preview alone. |
| `TopBar` | foundation.jsx:2674-2685. `h-14 px-6` with kicker «Wookiee Hub · Design System» + ChevronRight + active section label + actions. | TopBar.tsx — generic shell with breadcrumbs + children + actions. | ⚠️ TopBar generic, preview composes a different shell. See Layer G. |

---

## Layer E — overlays

| Component | Canonical | Current | Drift |
|---|---|---|---|
| `Modal` | foundation.jsx:2216-2234. Backdrop `bg-stone-900/40 dark:bg-black/60 backdrop-blur-sm`. `pt-24` top-aligned. Sizes sm/md/lg/xl → max-w-sm/lg/2xl/4xl. | Modal.tsx. Backdrop `bg-black/40 backdrop-blur-sm`. `pt-[10vh]`. Same sizes. + focus-trap + portal + escape. | ⚠️ Light-mode backdrop tint different (warm stone-900/40 vs cold black/40). Visual minor. Functional upgrade good. |
| `Drawer` | foundation.jsx:2236-2257. 2 sides (right `w-[420px]`, bottom `h-[60vh]`). | Drawer.tsx. 4 sides + 4 size presets. Right md=560px. | ⚠️ Right default width 420 vs 560. Bottom default h-[60vh] vs h-[55vh] (size=md). Per Kanban detail-drawer pattern (560px) the new default is correct for one use case but smaller for "filters" use case. |
| `Popover` | foundation.jsx:2259-2281. Inline (no portal), 3 positions. Trigger via wrapped span. | Popover.tsx. Portal + computed position + 4 placements + clamped to viewport. | ⚠️ Position prop names diverged (`bottom-start` → `bottom`). Functional upgrade. |
| `DropdownMenu` | foundation.jsx:2283-2301. Items: `{label, icon, shortcut, divider, danger, onClick}`. | DropdownMenu.tsx. Same shape + keyboard. | ✅ |
| `ContextMenu` | foundation.jsx:2303-2333. Right-click sets pos, fixed div. | ContextMenu.tsx. Portal + clamp. | ✅ |
| `CommandPalette` | foundation.jsx:2335-2370. Per-item leading UPPERCASE «type» label (`w-16`), then label + sub, then ArrowRight. No global group headers. | CommandPalette.tsx. Group-headers (section style) + per-item icon + label + description + shortcut + ArrowRight. | ⚠️ Layout different: canonical = «type tag» per row; current = group headers. Both valid, but visual not matching reference. |

---

## Layer F — feedback

| Component | Canonical | Current | Drift |
|---|---|---|---|
| `Toast` | foundation.jsx:2467-2490. 5 variants: `success/error/info/warning/loading`. Loading uses Loader2 + `animate-spin`. | Toast.tsx. 5 variants: `default/success/warning/danger/info`. **No `loading`.** | 🔴 Loading variant missing. `error` renamed `danger`. |
| `Alert` | foundation.jsx:2492-2510. 4 variants info/success/warning/error. `bg-X-50 border-X-200 text-X-900` hardcoded per variant. | Alert.tsx. 5 variants. Uses `bg-X-soft text-X border-[color:X]/30`. | ⚠️ Border opacity 30% vs canonical full-stroke `border-X-200`. Visual slightly softer. |
| `EmptyState` | foundation.jsx:2512-2521. `icon (Box default), title, description, action`. Icon `w-8 h-8 text-stone-400`. | EmptyState.tsx. `icon (Inbox default)`. Same body. | ✅ Default icon differs (Box → Inbox). Per use-case both make sense. |

---

## Layer G — preview page (most important)

### Reference structure (foundation.jsx:2609-2703, App component)

The canonical preview is a **full app shell** with sidebar nav + sticky topbar. Every section is rendered as a separate route inside the SPA via `SECTIONS.find(...)` switch.

Reference renders:

1. **Sidebar (left, w-60, sticky, surface-muted):**
   - Brand block: 7×7 gradient `from-purple-500 to-purple-700` + `Sparkles` icon + Instrument Serif italic «Wookiee» + UPPERCASE kicker «DS v2 · Foundation».
   - Section groups (`text-[10px] uppercase tracking-wider`):
     - Основа: Foundation, Atoms, Forms
     - Данные: Data display, Charts
     - Структура: Layout, Overlays, Feedback
   - Each item: lucide icon `w-3.5 h-3.5` + label. Active = `bg-stone-900 text-white`.
   - Theme block at bottom: «Тема» kicker + button «Светлая/Тёмная» with Sun/Moon icon + `⌘⇧L` kbd.
2. **Top bar (h-14, sticky):**
   - Left: kicker UPPERCASE «Wookiee Hub · Design System» + ChevronRight + active section label (`text-sm font-medium`).
   - Right: secondary Button with Download icon «Экспорт токенов» + IconButton theme toggle (Moon/Sun).
3. **Main content (`px-8 py-8 max-w-6xl`):**
   - Kicker «ДИЗАЙН-СИСТЕМА V2» (uppercase 11px).
   - H1 Instrument Serif `text-4xl` italic of the active section name.
   - Lede paragraph `text-sm text-muted max-w-2xl`.
   - `<Active />` — entire showcase for that section:
     - **Foundation:** Палитра (stone scale 11 cols + semantic 5-col grid), Семантические токены (table 4 cols Token/Light/Dark/Use), Типографика (6 sub-demos for page-title / section-title / body / label / numbers / mono), Spacing (gap-1.5..gap-8 scale).
     - **Atoms:** Кнопки (variants + sizes + icon + IconButton), Базовые поля (Input variants), Селекторы (Checkbox / Radio / Toggle / Slider), Бейджи и теги (StatusBadge / LevelBadge / Badge / Tag / Chip / Kbd), Аватары (sizes / colors / status / group), Прогресс (ProgressBar / Ring / ColorSwatch / Skeleton), Tooltip.
     - **Forms:** Базовые поля (TextField / NumberField / SelectField / MultiSelectField / TextareaField / mono), Расширенные (DatePicker single+range / TimePicker / Combobox / ColorPicker / FileUpload).
     - **Data display:** StatCard 4-col KPI row, DataTable basic + selection + expandable + BulkActionsBar, GroupedTable (Planning pivot), Pagination, TreeView.
     - **Charts:** Line / Area / Bar / Stacked Bar / Stacked Area / P&L combo / Channels stacked / Donut / Gauge / Funnel / Heatmap / Sparkline cards / inline sparkline in table.
     - **Layout:** Tabs (underline + pill + segmented), Breadcrumbs, Stepper, PageHeader.
     - **Overlays:** Modal, Drawer right/bottom, CommandPalette, Popover, Dropdown, ContextMenu.
     - **Feedback:** Toast (4 variants), Alert (4 variants), EmptyState (2), Skeleton loading state.

Total: **8 sections × multiple subsections × ~6 demos per subsection ≈ 150+ Demo blocks**, each in a card with UPPERCASE kicker + optional code label.

### Current structure (`pages/design-system-preview/index.tsx`, 461 lines, single file)

1. Sticky `header` (max-w-7xl mx-auto):
   - H1 «Wookiee Design System v2» (no kicker, no Instrument Serif on whole title — only on word «Wookiee»).
   - Right: ⌘K Kbd + ThemeToggle (Button secondary «→ Тёмная»).
2. `main` (max-w-7xl mx-auto):
   - PageHeader with title «Design System v2», description, Star icon, Settings/Plus action buttons.
   - Breadcrumbs Hub / Дизайн / Preview.
   - Then a flat list of `<Section title=...>` cards with a few demos each:
     - Buttons (1 card, 3 rows)
     - Badges, Tags, Chips, Avatars (1 card, 6 rows)
     - Progress, Ring, Tooltip, Skeleton (1 card, 2 rows)
     - Forms (1 card, 4 grid cells + FileUpload)
     - Tabs (1 card, 3 variants)
     - Stepper (1 card, 1 stepper)
     - Feedback (1 card: 5 alerts + 1 EmptyState + 3 toast buttons)
     - Overlays (1 card: 5 demo triggers + Modal/Drawer/Popover/Dropdown/CommandPalette wired up)
   - Footer caption.

### Missing sections vs canonical

- 🔴 **Sidebar nav** entirely missing — no left rail, no section-switching, all sections on one scroll. Canonical is a SPA-style switcher.
- 🔴 **Foundation section** — entire palette + token-table + typography + spacing demos are not rendered. The brand swatches/stone scale that visually demonstrate DS v2 are absent.
- 🔴 **Data display section** — StatCard, DataTable, GroupedTable, Pagination, TreeView, BulkActionsBar — none. The Pivot/GroupedTable is a major DS component (DS §9) and has zero coverage in preview.
- 🔴 **Charts section** — all 12 chart demos missing. Recharts is in `package.json`, just not used here.
- 🔴 **Layout — PageHeader, Breadcrumbs, Stepper** — partially shown (we render Stepper, Breadcrumbs, PageHeader once at top each), but canonical layout section dedicates a full panel demonstrating each variant. `<Tabs variant="segmented">` cannot be rendered because the variant doesn't exist.
- 🔴 **Atoms — Toggle / Checkbox / Radio / Slider** — missing (no DS primitive exists for them).
- 🔴 **Forms — TimePicker, ColorPicker, DatePicker range** — missing primitives → not in preview.
- 🔴 **Atoms — StatusBadge (5 statusIds), LevelBadge (M/V/A/S)** — wrong semantics → previewed rows show different concept.
- 🔴 **Topbar shape** — canonical kicker + ChevronRight + active-section breadcrumb in topbar; current is flat title.
- 🔴 **Patterns section showcase (Kanban/Calendar/Comments/Notifications/Activity/Inbox/Theme demo)** — not in foundation preview but is referenced from patterns.jsx final App() — see Layer H.

### Gap quantification

| Metric | Canonical | Current |
|---|---|---|
| Section panels | 8 top-level groups (Foundation/Atoms/Forms/Data/Charts/Layout/Overlays/Feedback) | 8 ad-hoc cards (Buttons/Badges/Progress/Forms/Tabs/Stepper/Feedback/Overlays) |
| Demo blocks rendered | ~150+ Demo cards | ~25 inline rows |
| Component variants demonstrated | All (xs/sm/md/lg buttons, 6 button variants, 7 badge colors, 4 levels M/V/A/S, 5 statuses, single+range datepicker, …) | A subset, often incorrect (e.g. LevelBadge P0..P3 instead of M/V/A/S, 4 button variants instead of 6) |
| Lines | 2704 (full) | 461 |
| Sidebar nav | yes | no |
| Charts | yes | no |
| GroupedTable | yes | no |

**Verdict:** preview is approximately **15% of the canonical surface** and is a watered-down grid — not the reference showcase.

---

## Layer H — patterns

`wookiee_ds_v2_patterns.jsx` (1590 lines) defines these production patterns:

1. **Kanban Board** — columns + draggable cards (`@dnd-kit/core` per spec §8), Detail Drawer (560px right), priority dot, assignee avatars, sub-task progress, WIP-limit badge, drag opacity/rotate/scale states.
2. **Calendar** — Month grid (6×7) + Week grid (8:00–21:00 hours). DnD events between days/slots. Event colors: blue (съёмки), purple (Reels), emerald (релизы), amber (промо), teal (поставки), gray (встречи). Centered Event Detail Popover.
3. **Comments thread** — main thread + reply branch with `border-l`. Avatar + author + time + text. `@-mentions` as `bg-blue-50 text-blue-700 badge`. Inline code styled mono. Attachments as pill cards. Reactions as pill-buttons with emoji+count. Composer (textarea + At/Hash/Paperclip/Smile toolbar + Send).
4. **Notifications** — right slide-out (w-420). Header (Bell + red unread badge + Settings + X). Filter chips. Date grouping (Today/Yesterday/Earlier). Per-item blue-dot + author avatar + text + target pill + timestamp. 5 types with icons (mention/task/comment/status/system).
5. **Activity feed** — Linear-style timeline. Vertical line connector. Per-event: avatar + author + action + entity + change badges (from→to with strikethrough old) + timestamp + field-tag.
6. **Inbox** — Tabs (All/Unread/Urgent) + priority dot + type icon (quad-card) + author avatar + title + project chip + due (red «сегодня») + actions.
7. **Theme demo** — side-by-side light/dark frame showing toggle behaviour.

### Current state in repo

None of the seven patterns exist in `src/components/ui-v2/`. Search shows:

- `src/components/influence/integrations/` — has Influencer CRM Kanban-style board (CRM Stages — see Phase 7), uses old shadcn primitives, NOT ui-v2 tokens. Will need full rewrite for DS v2 fidelity.
- `src/components/community/` — community page surfaces, no DS v2 patterns.
- `src/components/operations/` — operations / supply planning UI, but uses old shadcn / Tailwind direct stone classes. No GroupedTable using ui-v2.
- No `Comments`, `Notifications`, `Activity`, `Inbox`, `Calendar` DS v2 components exist.

Wave 3-4 (per migration plan) has not started — this is expected, but worth noting that the patterns file is itself **not preview-able** with current ui-v2 primitives because:

- `Badge` lacks `purple/teal/orange` for event colors and notification type icons.
- `Avatar` lacks `color` for team-coloured comment authors.
- `LevelBadge` (M/V/A/S) needed for tasks/SKUs.
- DnD lib not installed (`@dnd-kit/core` not in `package.json` — confirm).

---

## Priority queue

### P0 — block all reskin work (must fix before any Wave 3 component)

1. **`--color-danger` = `red.600` → `rose.600`** (tokens.css:50, dark variant 132). Brand danger must be `#E11D48`. Affects: all Buttons danger, all Toasts danger, all Alerts danger, all StatusBadge danger.
2. **`--color-ring` = `violet.600` → `stone-900`** (use `var(--color-text-primary)`; tokens.css:56, 138). DS §10 explicitly requires non-blue/non-brand focus. Affects: every Button/IconButton/Chip/Input focus ring across the app.
3. **Rebuild `StatusBadge` API**: re-add canonical `STATUS_MAP` (1=emerald/В продаже, 2=blue/Запуск, 3=amber/Выводим, 4=red/Не выводится, 5=gray/Архив) and `<StatusBadge statusId={1..5}>` shape. Keep `tone` variant as advanced override. Without this, каталог migration cannot reuse canonical code.
4. **Rebuild `LevelBadge`**: switch to canonical `level: 'model'|'variation'|'artikul'|'sku'` → letters M/V/A/S with blue/purple/orange/emerald. Wire into `FieldWrap` as `level` prop. Move current P0..P3 priorities to a separate `PriorityBadge` component.
5. **Add missing `Button` variants `danger-ghost` and `success`** and size `xs` (28px). Rename `destructive` → `danger` for consistency with canonical and DS §6 wording.
6. **Add `Badge` color-variants `purple`, `orange`, `teal`** (variants for brand-/team-/category-coloured tags). Add `dot` prop. Switch from `border` to `ring-1 ring-inset` (no layout-shift).
7. **Restore `MultiSelectField` chips-toggle layout** (inline buttons, not dropdown). Required by DS §6.
8. **Add `Avatar.color` prop** with stone/emerald/blue/amber/purple/rose/teal gradient backgrounds.
9. **Implement missing primitives: `Checkbox`, `Radio`, `Toggle`, `Slider`** (DS §6 atoms — currently zero of these in ui-v2).
10. **Implement missing form fields: `DatePicker range`, `TimePicker`, `ColorPicker`**.
11. **Add `Tabs` variant `segmented`** (list/grid/kanban switcher).
12. **`PageHeader` API rewrite**: support `kicker, breadcrumbs, status` slots; drop `icon`/`description` defaults (or keep behind extension prop). Use `text-3xl` not `text-4xl` for in-card use.
13. **`Toast` variant `loading`** with Loader2 spinner.

### P1 — per-component drift (fix during Wave 3 component-by-component rollout)

- `Ring` value scale 0..1 (canonical) vs 0..100 (current). Decide and document one convention.
- `Chip` paradigm: split into `Chip` (removable) and `FilterChip` (selectable).
- `ColorSwatch` rebuild as passive token-display, not interactive button. Add `hex` prop, accept number `size`, optional `label` (mono).
- `Kbd` remove inset shadow → flat per canonical.
- `Skeleton` color: switch to literal `stone-200/800` instead of `surface-muted` to avoid dark-mode contrast loss.
- `IconButton` default size 28×28 (`p-1.5`), not 32×32.
- `Tag` smaller text-[11px] vs Badge text-xs.
- `SelectField` accept canonical `{id, nazvanie}` option shape in addition to `{value, label}`.
- `Breadcrumbs` accept `string[]` in addition to `[{label, href?}]`.
- `Stepper` connector position `mt-[-16px]` to center on circle row.
- `TextField` `mono` boolean prop.
- `Tooltip` accept `text` prop alias for `content`.
- `Modal` backdrop tint `stone-900/40` in light mode (warmer).
- `Drawer.size` default right→ width 420 (filters) vs 560 (Kanban detail) — split into two presets `filters / detail`.
- `Popover` placement `bottom-start` alias.
- `Status soft tokens` — light to `-50` instead of `-100`; dark to `-950/40` instead of `-900/40`. Accent dark to `violet-300` instead of `violet-400`.
- `surface-muted` dark opacity `40%` not `60%`.

### P2 — preview-page rebuild (cosmetic, not blocking but explicitly demanded)

Replace `pages/design-system-preview/index.tsx` (461 lines) with a faithful port of `foundation.jsx` App() + `patterns.jsx` App() composite:

- Left Sidebar (w-60 sticky) with 3 group sections + Theme block at bottom.
- Top bar (h-14 sticky): kicker «Wookiee Hub · Design System» + ChevronRight + active label + actions (export tokens + theme toggle).
- Main: kicker + Instrument Serif h1 of active section + lede + `<Active />` block.
- 8 sections rendered as their full canonical demos: Foundation / Atoms / Forms / Data display / Charts / Layout / Overlays / Feedback.
- (Stretch) Patterns sections: Kanban / Calendar / Comments / Notifications / Activity / Inbox / Theme demo — add as sections 9-15 when Wave 3 lands them.
- Estimated effort: ~2000 lines (canonical is 2704; some shared scaffolding can be reused).
- This work depends on all P0 fixes landing first — otherwise the showcase will exhibit the very drift it should demonstrate.

---

*End of report. Generated against `feat/ds-v2-migration` snapshot 2026-05-12.*
