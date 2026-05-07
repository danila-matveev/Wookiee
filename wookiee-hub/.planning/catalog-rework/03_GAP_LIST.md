# Gap List — MVP `wookiee_matrix_mvp_v4.jsx` → текущая реализация

**Эталон:** `/Users/danilamatveev/Projects/Wookiee/redesign + PIX/wookiee_matrix_mvp_v4.jsx` (2044 строки)
**Текущий код:** `/Users/danilamatveev/Projects/Wookiee/wookiee-hub/src/`

## A. Атомарные UI компоненты

| Компонент | Статус | Файл |
|-----------|--------|------|
| `Tooltip` | ❌ нет | `components/catalog/ui/tooltip.tsx` (создать) |
| `LevelBadge` | ⚠ есть, но не используется | `components/catalog/ui/level-badge.tsx` |
| `StatusBadge` | ✅ есть, проверить стилизацию (pill+ring+dot) | `components/catalog/ui/status-badge.tsx` |
| `CompletenessRing` | ✅ есть, проверить пороги цветов | `components/catalog/ui/completeness-ring.tsx` |
| `TextField/NumberField/SelectField/StringSelectField/MultiSelectField/TextareaField` | ⚠ частично, без `level` props и без `readonly` mode | `components/catalog/ui/fields.tsx` |
| `FieldWrap` | ⚠ есть в matrix.tsx, нужен переиспользуемый | переместить в `components/catalog/ui/` |
| `ColumnsManager` | ❌ нет | создать `components/catalog/ui/columns-manager.tsx` |
| `RefModal` | ⚠ простая, не поддерживает select/file_url | расширить |
| `BulkActionsBar` | ❌ нет | создать `components/catalog/ui/bulk-actions-bar.tsx` |

## B. Layout

| Элемент | Статус | Что не так |
|---------|--------|-----------|
| Sidebar — состав | ⚠ 6 справочников из 8 | Нет «Семейства цветов», «Упаковки», «Каналы продаж» |
| Sidebar — счётчики | ❌ нет | Каждый пункт должен показывать count |
| Sidebar — футер с профилем | ❌ нет | Нужен блок «Данила · CEO» |
| TopBar | ⚠ есть, но без breadcrumb | Динамический breadcrumb «Каталог > Матрица > Vuki» |
| CommandPalette ⌘K | ❌ нет | Поиск по моделям/цветам/баркодам/артикулам OZON/WB |

## C. Матрица (Базовые модели)

| Фича | Статус | Что не так |
|------|--------|-----------|
| Подзаголовок «X моделей · Y вариаций · Z артикулов · W SKU» | ⚠ без вариаций | |
| «Экспорт» кнопка | ❌ нет | |
| Колонка «Статус» в таблице | ❌ ОТСУТСТВУЕТ | первое жалобное замечание пользователя |
| Чекбокс-колонка для bulk | ❌ нет | |
| Status filter chips | ⚠ есть, неполные | Нужны все model-статусы |
| Category filter | ✅ есть | |
| **Collection filter** (новое) | ❌ нет | пользователь явно просил |
| **GroupBy** «Без / По категории / По коллекции / По фабрике / По статусу» | ❌ нет | |
| «Незаполненные» фильтр | ✅ есть | |
| BulkActionsBar внизу | ❌ нет | |
| Tooltip на «·» когда вариаций <2 | ❌ нет | |
| Раскрытие вариаций | ✅ есть, проверить React.Fragment key | |

## D. Артикулы (реестр)

| Фича | Статус | Что не так |
|------|--------|-----------|
| ColumnsManager 11 колонок | ❌ нет | |
| Status filter chips | ❌ нет | |
| Search по WB-номенклатуре + OZON-артикулу | ⚠ только по артикулу/модели/цвету | |

## E. SKU реестр (Tovary)

| Фича | Статус | Что не так |
|------|--------|-----------|
| ColumnsManager 17 колонок | ❌ нет (только channel filter добавлен в прошлой итерации) | |
| GroupBy (none/model/color/size/collection) | ❌ нет | |
| Status group filter (4 опции) | ❌ нет | |
| Channel filter (WB/OZON/Сайт/Lamoda) | ✅ есть (добавлен) | |
| Composite search «Audrey/black/S» | ❌ нет | пользователь явно просил |
| Inline edit статусов | ❌ нет | |
| Bulk «Привязать к склейке» | ❌ нет | |
| Все 4 канала с возможностью настройки колонок | ⚠ статичные колонки | |
| Заголовки групп при groupBy | ❌ нет | |

## F. ModelCard (карточка модели)

| Фича | Статус | Что не так |
|------|--------|-----------|
| `editing` + `draft` state | ❌ нет (кнопки декоративные) | пользователь явно просил editable |
| Header: Сохранить / Отмена в edit mode | ❌ нет | |
| «Дублировать» — реальная функция (создать копию) | ❌ нет | пользователь объяснил: шаблоны для новых моделей |
| «В архив» — каскадное на вариации/артикулы/SKU | ❌ нет | пользователь подтвердил |
| Tab Описание: editable fields | ❌ только read-only | |
| Tab Описание: LevelBadge на каждом поле | ❌ нет | |
| **Размерная линейка как chip-pills** (XS S M L XL XXL) | ❌ просто текст | первое жалобное замечание |
| Tab Атрибуты — для всех 11 категорий | ⚠ только 5 из MVP | расширить ATTRIBUTES_BY_CATEGORY |
| Tab Артикулы: «+Добавить» в шапке | ❌ нет | |
| Tab Артикулы: клик по цвету → ColorCard | ❌ нет | |
| Tab SKU: inline edit статусов | ❌ нет | |
| Tab Контент: Notion-карточка / стратегия / Яндекс.Диск (3 ссылки) | ⚠ только notion_link | |
| Tab Контент: блок Упаковка с подтянутыми габаритами | ❌ нет | |
| Tab Контент: блок Сертификаты | ❌ нет | пользователь подтвердил полноценный справочник |
| Sidebar Заполненность (CompletenessRing 56) | ⚠ есть, но 0.7/0.3 хардкод | |
| Sidebar Вариации с +Добавить и tooltip | ❌ нет +Добавить | пользователь жаловался |
| Sidebar Цвета модели — кликабельные → ColorCard | ❌ нет | |
| Sidebar Метрики с subtitle | ⚠ есть | |

## G. Цвета (ColorsView + ColorCard)

| Фича | Статус | Что не так |
|------|--------|-----------|
| Группировка по семейству с заголовком | ⚠ есть фильтр, но 0 совпадений (semeystvo всё NULL) | требует миграции |
| Колонки Color Code/Цвет RU/Color EN/Ластовица/Использован в | ⚠ часть колонок | |
| Кнопка «Новый цвет» с hex picker | ❌ нет | |
| ColorCard: header big swatch (40px) | ⚠ ColorCard есть, но не такая | |
| ColorCard: «Модели использующие этот цвет» | ❌ нет | |
| ColorCard: «Артикулы (N)» секция | ❌ нет | |
| ColorCard sidebar: HEX 64px swatch | ❌ нет (нет hex колонки) | |
| ColorCard sidebar: «Похожие цвета» | ❌ нет | |

## H. Склейки

| Фича | Статус | Что не так |
|------|--------|-----------|
| Подзаголовок «До 30 SKU в склейке…» | ❌ нет | |
| Колонка «Заполненность» в списке (progress bar + cnt/30) | ❌ нет | |
| SkleykaCard header с прогрессом справа | ⚠ есть, не такой | |
| SKU-таблица с Trash2 unlink | ❌ нет | |
| Sidebar «Правила склейки» (3 чек-пункта) | ❌ нет | |
| Sidebar «Что это даёт?» | ❌ нет | |
| Создание новой склейки | ❌ нет | |

## I. Справочники

| Фича | Статус | Что не так |
|------|--------|-----------|
| Subtitle на каждой странице | ❌ нет | |
| **Категории**: + opisanie, + кол-во моделей | ❌ нет колонок | |
| **Коллекции**: + opisanie, god_zapuska | ❌ нет колонок | |
| **Производители**: rich (gorod, kontakt, email, specializaciya, leadtime) | ❌ нет колонок | |
| **Юрлица**: rich (short, bank, rs, kontakt, telefon) | ❌ нет колонок | |
| **Размеры**: RU / EU / China | ❌ нет колонок | |
| **Семейства цветов** (новая страница) | ❌ нет страницы и таблицы | |
| **Упаковки** (новая страница) | ❌ нет страницы и таблицы | |
| **Каналы продаж** (новая страница) | ❌ нет страницы и таблицы | |
| **Сертификаты** (новая страница) | ❌ нет страницы (хотя таблица есть) | |
| Hover MoreHorizontal на каждой строке (Edit/Delete) | ❌ нет | |
| RefModal с валидацией | ⚠ простая | |

## J. Данные / БД

См. `01_DATA_AUDIT.md`.

## K. Темизация

| Элемент | Статус |
|---------|--------|
| body font 'DM Sans' | ⚠ проверить |
| h1 font 'Instrument Serif' italic | ⚠ есть как class `cat-font-serif`, проверить |
| `accent-color: #1C1917` для checkboxов | ❌ |
| `max-w-7xl mx-auto` центрирование карточек | ⚠ проверить |

## L. Routing & state

| Фича | Статус |
|------|--------|
| Breadcrumb в TopBar динамический | ❌ |
| ⌘K глобальный hotkey | ❌ |
| Esc закрывает модалки/палитру | ⚠ частично |

## Что в коде ХОРОШЕЕ и оставлять

- `useQuery` + `staleTime` на всех fetcherах ✅
- React Router DOM v7 + `useSearchParams` для модальных карточек ✅
- `.catalog-scope` CSS для стилей без поломки тёмной темы Hub ✅
- TanStack Query инвалидация после мутаций ✅
- `fetchSkleykaDetail` с детализацией junction-таблиц ✅
- TovaryTable channel filter (нужно расширить под полную логику MVP) ⚠
- Reference pages CRUD modals (нужно расширить под все справочники) ⚠
