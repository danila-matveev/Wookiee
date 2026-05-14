# W10 — Catalog Management Overhaul: 37 правок в 5 волн

**Дата:** 2026-05-13  
**Ветка:** `feature/catalog-overhaul-w9` (продолжение, без отдельной w10 ветки)  
**Контекст:** W9 цикл задеплоен на prod hub.os.wookiee.shop. Пользователь прислал ~13 скриншотов с новыми багами + явный сигнал тщательно искать аналоги. Проведён полный аудит: 26 пунктов со скринов + 11 найдено фронт-аудитом + 5 найдено DB-аудитом. После дедупа = 37 уникальных.

**Критичные находки от аудита:**

- **W10.42**: фильтр `/colors` возвращает 0/146 потому что `cveta.status_id` указывает на product-статусы (id=8,9,10…), а color-статусы хранятся под id=34,35,36 (`statusy.tip='color'`). **Это и есть тот баг «миллиард раз просил»** — он в данных, а не в коде. Нужна data-fix миграция + FK CHECK.
- **W10.43**: junction `artikuly_skleyki_*` не существует (только `tovary_skleyki_*`). Без него нельзя группировать SKU по артикулу в склейке (W10.23) и показывать склейки в карточке артикула (W10.26).
- **W10.39**: На 9 таблицах висит **дублирующий** аудит (legacy `log_izmeneniya` + новый `audit_trigger_fn`). Каждое изменение пишется в обе таблицы. Снести legacy.

---

## Wave A — Layout, scroll, sort, color, фильтры (14 пунктов, КРИТИЧНО)

### W10.1 — Управление колонками реально применяется к таблице
- **Где:** все 3 реестра (matrix, artikuly, tovary)
- **Что не так:** `useColumnConfig` отдаёт `visibleColumnIds[]` и `columnOrder[]`, но `<th>`/`<td>` строятся из захардкоженного массива → клик в ColumnsManager не меняет DOM
- **Фикс:** строить header/cells через `.filter(c => visibleColumnIds.includes(c.id)).sort((a,b) => order.indexOf(a.id) - order.indexOf(b.id))`. Хранить состояние в localStorage по странице.

### W10.2 + W10.27 — Horizontal scroll
- **Где:** `/artikuly`, `/tovary`, `/skleyki`, `/colors` (на matrix уже есть)
- **Фикс:** обёртка таблицы получает `overflow-x-auto` + `min-w-[NNNpx]` на `<table>`, чтобы при узком вьюпорте появлялся скроллбар вместо ломки лейаута

### W10.3 — Ellipsis в /tovary (статус WB наезжает на OZON-артикул)
- **Где:** все цельные `<td>` в /tovary, /artikuly, /skleyki, /colors
- **Фикс:** обернуть длинный текст в `<CellText>` (уже есть из W9.15) с явным `max-width` на колонке. Усилить `text-ellipsis whitespace-nowrap` поведение.

### W10.4 + W10.29 — SKU сортируются по физической иерархии размеров
- **Где:** `model-card.tsx` TabSKU, `/tovary`, в склейке /skleyki/[id]
- **Что не так:** ряды S/M/L скачут при смене статуса. `getMatrixSortValue` не использует `RAZMER_LADDER` (XS<S<M<L<XL<XXL<3XL...)
- **Фикс:** утилита `compareRazmer(a,b)` на основе `RAZMER_LADDER`; стабильный secondary key — `tovar.created_at` или `barkod`. Сортировка применяется независимо от других фильтров (не сбрасывается при клике на статус).

### W10.5 — Колонка «цвет» в /tovary
- **Что не так:** одинаковые кружки Black/White/Nude визуально не различить
- **Фикс:** ColorSwatch + рядом текст «code + nazvanie» (как в /artikuly). Семейство (`semeystvo_cveta`) можно показать как подпись малым шрифтом.

### W10.20 — Hex-цвета корректно везде (единая утилита)
- **Где:** все компоненты, рендерящие цветовой swatch (matrix, /artikuly, /tovary, /colors, /skleyki, AddArtikulModal, ColorPicker, InlineColorCell, model-card)
- **Фикс:** утилита `colorSwatchStyle(input: string | null): CSSProperties` в `lib/catalog/color-utils.ts`. Нормализует:
  - `#RRGGBB` → используется как есть
  - `RRGGBB` → добавляет `#`
  - `rgb(...)`, `rgba(...)` → как есть
  - `null` или пусто → серый placeholder с диагональной штриховкой
- **Также:** заменить все `style={{backgroundColor: hex}}` или `bg-[#${hex}]` на этот единый helper

### W10.34 — InlineColorCell на dbl-click
- **Что не так:** клик по цветовой ячейке открывает picker (как и InlineTextCell)
- **Фикс:** `onDoubleClick` + hover-индикатор «карандаш» в углу. Single-click ничего не делает (или открывает drawer карточки артикула — см. W10.6).

### W10.16 — Русские крошки (slug → ru-label)
- **Где:** breadcrumbs компонент на всех страницах /catalog/references/*, /catalog/*
- **Фикс:** mapping в `lib/catalog/route-labels.ts`:
  ```ts
  export const ROUTE_LABELS = {
    'matrix': 'Матрица', 'artikuly': 'Артикулы', 'tovary': 'Товары/SKU',
    'skleyki': 'Склейки', 'colors': 'Цвета',
    'references': 'Справочники',
    'brendy': 'Бренды', 'kategorii': 'Категории', 'kollekcii': 'Коллекции',
    'tipy-kollekciy': 'Типы коллекций', 'fabriki': 'Производители',
    'importery': 'Юрлица', 'razmery': 'Размеры',
    'semeystva-cvetov': 'Семейства цветов', 'upakovki': 'Упаковки',
    'kanaly-prodazh': 'Каналы продаж', 'sertifikaty': 'Сертификаты',
    'atributy': 'Атрибуты',
  } as const
  ```
- **Применить** во всех breadcrumb-рендерах + page titles если slug.

### W10.22 — Удалить chip-rows на /matrix
- **Где:** `pages/catalog/matrix.tsx`
- **Что не так:** одновременно есть FilterBar (W9.4 dropdown-чипы) **и** старые чип-ряды `БРЕНДЫ: TELOWAY 19, WOOKIEE 37`, `КАТЕГОРИИ:`, `КОЛЛЕКЦИИ:`, `СТАТУСЫ:`
- **Фикс:** удалить блок старых чипов. Все фильтры остаются в FilterBar. Multi-select внутри dropdown'а (notion-стайл).

### W10.31 — Удалить старые `familyFilter`/`statusFilter` кнопки на /colors
- **Где:** `pages/catalog/colors.tsx`
- **Фикс:** заменить ряд кнопок «Семейство: Все/Трикотаж/Jelly/…» + «Статус: Все/Продаётся/Выводим/Архив» на FilterBar dropdown-чипы.

### W10.28 — ColumnsManager пересчитывает ширину/sort при hide
- **Где:** все таблицы где есть resize + column-manager
- **Фикс:** при изменении `visibleColumnIds` пересоздать `<table>` с новой шириной, чтобы layout не сломался. Использовать `key={visibleColumnIds.join('|')}` для force-rerender или явно пересчитывать template-columns.

### W10.42 — КРИТИЧНО: Миграция cveta.status_id (product → color)
- **Где:** новая миграция `database/migrations/026_fix_cveta_color_status.sql`
- **Что:**
  ```sql
  -- 1. Перенос данных: все cveta.status_id указывающие на product-статусы → color-статусы
  -- Маппинг product → color (id):
  --   8 (Продаётся, product)   → 34 (Продаётся, color)
  --   9 (Выводим, product)     → 35 (Выводим, color)
  --   10 (Архив, product)      → 36 (Архив, color)
  --   (остальные product-id обнулить или маппить по смыслу)
  UPDATE public.cveta SET status_id = 34 WHERE status_id IN (SELECT id FROM statusy WHERE tip='product' AND kod IN ('V_prodazhe','Prodaetsya'));
  UPDATE public.cveta SET status_id = 35 WHERE status_id IN (SELECT id FROM statusy WHERE tip='product' AND kod IN ('Vyvodim'));
  UPDATE public.cveta SET status_id = 36 WHERE status_id IN (SELECT id FROM statusy WHERE tip='product' AND kod IN ('Arhiv'));
  -- остальные → NULL или дефолтный color-статус

  -- 2. FK с CHECK на tip='color'
  -- Postgres не поддерживает CHECK через FK. Альтернатива — триггер:
  CREATE OR REPLACE FUNCTION public.check_cveta_status_tip() RETURNS trigger AS $$
  BEGIN
    IF NEW.status_id IS NOT NULL AND (SELECT tip FROM public.statusy WHERE id = NEW.status_id) != 'color' THEN
      RAISE EXCEPTION 'cveta.status_id must reference statusy.tip = ''color''';
    END IF;
    RETURN NEW;
  END;
  $$ LANGUAGE plpgsql;

  DROP TRIGGER IF EXISTS check_cveta_status_tip_trg ON public.cveta;
  CREATE TRIGGER check_cveta_status_tip_trg
    BEFORE INSERT OR UPDATE OF status_id ON public.cveta
    FOR EACH ROW EXECUTE FUNCTION public.check_cveta_status_tip();
  ```
- **Перед миграцией:** запустить SELECT по `cveta` чтобы увидеть текущее распределение `status_id`.

### W10.21 — Фильтр статусов /colors реально работает (после W10.42)
- **Фикс:** после миграции цвета будут иметь корректные color-status_id, фронт уже работает правильно (`s.tip === 'color'`). Тестировать что: фильтр «Продаётся» → 52 цвета (или сколько есть).

---

## Wave B — Card UX, drawer, защита inline-edit (5 пунктов)

### W10.6 + W10.32 — Drawer карточки артикула
- **Где:** `/artikuly` (сейчас drawer отсутствует) + `/tovary` (для SKU)
- **Фикс:** новый компонент `ArtikulDrawer` по образцу `ModelDrawer` из `model-card.tsx`. Открывается по single-click на строке. Содержит вкладки: Описание, История, Склейки.
- Аналогичный `SkuDrawer` для /tovary.

### W10.7 — Inline-edit на dbl-click
- **Где:** `InlineTextCell`, `InlineSelectCell`, `InlineColorCell`
- **Фикс:** заменить `onClick={enter}` на `onDoubleClick={enter}`. Single-click открывает drawer (W10.6). Добавить hover-индикатор «карандаш» в правом углу ячейки.

### W10.8 — Валидация полей в редакторе артикула/SKU
- **Где:** ArtikulDrawer / SkuDrawer (или модалки редактирования)
- **Фикс:** Zod-схемы (или ручная валидация) для:
  - артикул: `^[\w\-]+\/[\w\-]+$` (модель/цвет)
  - WB-номенклатура: `\d{8,12}`
  - OZON-артикул: непустое
  Ошибки отображаются inline, save кнопка disabled при невалидном вводе.

### W10.17 — Скруглить угол drawer'а модели
- **Где:** `Drawer.tsx` компонент
- **Фикс:** `rounded-l-2xl` на левую сторону drawer'а + `shadow-2xl` для глубины. Backdrop dim.

### W10.38 — Row-click vs inline-edit в /skleyki
- **Где:** `pages/catalog/skleyki.tsx`
- **Фикс:** после введения dbl-click на inline-edit (W10.7) — single-click на строке откроет drawer склейки, конфликт разрешён.

---

## Wave C — Create flow, bulk, атрибуты (4 пункта)

### W10.9 + W10.37 — Создание артикула: цвет + размер вместе
- **Где:** `AddArtikulModal` в `model-card.tsx`
- **Фикс:** добавить секцию «Размеры» (multi-select из `razmery_modeli` модели). При создании:
  - выбранные цвета × выбранные размеры → создаются `artikuly` + `tovary` (SKU) с дефолтным `status_id = 'Zapusk'`
  - prevent дубли (skip если уже существует)
- Показать счётчик «Будет создано N артикулов и M SKU».

### W10.10 — Фильтр палитры по семействам цветов
- **Где:** `ColorPicker` (используется в AddArtikulModal и др.)
- **Фикс:** добавить выпадающий или табы по `semeystva_cvetov` (источник — таблица семейств). При выборе семейства — палитра фильтруется. «Все» по умолчанию.

### W10.11 + W10.33 — Унифицированный BulkActionsBar на /artikuly
- **Где:** `pages/catalog/artikuly.tsx`
- **Что не так:** custom bulk-бар (комментарий `Bulk actions — кастомный бар, т.к. atomic BulkActionsBar не поддерживает`)
- **Фикс:** расширить `BulkActionsBar` чтобы поддерживал артикулы. Добавить операции:
  - смена статуса (множественно)
  - изменение фабрики
  - изменение категории
  - удаление (с подтверждением)
- Использовать тот же UI что в /tovary.

### W10.18 — Multiselect категорий в AddAtributModal
- **Где:** `pages/catalog/references/atributy.tsx` AddAtributModal
- **Фикс:** при создании нового атрибута добавить поле «Категории» — multi-select. После INSERT атрибута сразу INSERT в `kategoriya_atributy` для каждой выбранной категории. В режиме Link — уже работает.

---

## Wave D — Skleyki + history + DB cleanup (11 пунктов)

### W10.43 — КРИТИЧНО: junction artikuly_skleyki_*
- **Где:** новая миграция `database/migrations/027_artikuly_skleyki_junctions.sql`
- **Что:**
  ```sql
  CREATE TABLE public.artikuly_skleyki_wb (
    artikul_id INTEGER NOT NULL REFERENCES public.artikuly(id) ON DELETE CASCADE,
    skleyka_id INTEGER NOT NULL REFERENCES public.skleyki(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (artikul_id, skleyka_id)
  );
  CREATE TABLE public.artikuly_skleyki_ozon (
    artikul_id INTEGER NOT NULL REFERENCES public.artikuly(id) ON DELETE CASCADE,
    skleyka_id INTEGER NOT NULL REFERENCES public.skleyki(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (artikul_id, skleyka_id)
  );
  -- RLS + audit triggers + GRANT
  ```
- **Backfill** из существующих `tovary_skleyki_*`:
  ```sql
  INSERT INTO artikuly_skleyki_wb (artikul_id, skleyka_id)
  SELECT DISTINCT t.artikul_id, ts.skleyka_id
  FROM public.tovary_skleyki_wb ts
  JOIN public.tovary t ON t.id = ts.tovar_id
  WHERE t.artikul_id IS NOT NULL
  ON CONFLICT DO NOTHING;
  -- то же для ozon
  ```

### W10.23 — Группировка по артикулу в /skleyki/[id]
- **Где:** `pages/catalog/skleyki/[id].tsx` или `skleyka-card.tsx`
- **Фикс:** вместо плоского списка SKU — группы по `artikul_id`. Заголовок группы: `Moon/black • 3 SKU (S, M, L)`. Под ним — таблица SKU. Размеры внутри группы отсортированы по `RAZMER_LADDER` (см. W10.4).

### W10.24 — Текст правил склейки
- **Где:** `pages/catalog/skleyki/[id].tsx` справа панель «ПРАВИЛА СКЛЕЙКИ»
- **Фикс:** заменить текущий текст («Один цвет, разные размеры / ИЛИ один размер, разные цвета / До 30 SKU») на:
  > До 30 SKU в одной склейке. Только Wildberries. Один артикул может находиться только в одной активной склейке. Группируется по сезону.

### W10.25 + W10.36 — Реализовать таб «История» склейки
- **Где:** `skleyka-card.tsx` TabHistory
- **Фикс:** SELECT из `audit_log` WHERE `table_name IN ('skleyki', 'tovary_skleyki_wb', 'tovary_skleyki_ozon', 'artikuly_skleyki_wb', 'artikuly_skleyki_ozon')` AND record_id = skleyka.id (или filter по additional FK). Render как в model-card TabHistory.

### W10.26 — Колонка «Склейка» в /artikuly и /tovary
- **Где:** реестры
- **Фикс:** новая колонка показывает имя склейки (или иконку «—» если не в склейке). LEFT JOIN на `artikuly_skleyki_*` (для /artikuly) или `tovary_skleyki_*` (для /tovary). Клик по имени → drawer склейки.

### W10.19 — Секция «Склейки» в карточке модели
- **Где:** `model-card.tsx` (новая секция или вкладка)
- **Фикс:** SELECT всех склеек, в которых есть артикулы модели. Render: список с числом SKU и кнопкой «Открыть».

### W10.12 — Audit_log артикулов/SKU в табе «История» карточки модели
- **Где:** `model-card.tsx` TabHistory
- **Фикс:** расширить SELECT: WHERE `table_name IN ('modeli_osnova','modeli','variacii','artikuly','tovary')` AND record_id связан с моделью (через JOIN или filter по additional FK). Разделить по табам/секциям: Модель / Артикулы / SKU.

### W10.13 — Кнопка «Откатить» из истории
- **Где:** TabHistory компонент
- **Фикс:** для каждой записи `audit_log` с `op = 'UPDATE'` показать кнопку «Откатить». Клик → INSERT новой записи с обратным diff (т.е. update обратно к старому значению). Не UPDATE существующей, а новый изменение — чтобы история была честной.
- Confirm dialog «Откатить изменение от {date}? Поле {col}: {new} → {old}».

### W10.39 — Миграция 026: удалить legacy log_izmeneniya
- **Где:** новая миграция `database/migrations/028_remove_legacy_audit.sql`
- **Что:** DROP TRIGGER `audit_*` (legacy через `log_izmeneniya`) на 9 таблицах: `modeli_osnova, modeli, variacii, artikuly, tovary, cveta, brendy, kollekcii, kategorii, sertifikaty`. Оставить новые `audit_trigger_fn` триггеры.
- **Сохранить** `infra.istoriya_izmeneniy` таблицу и функцию `log_izmeneniya()` — на случай если что-то ещё пишет.

### W10.40 — Audit на 6 справочниках
- **Где:** миграция `028_remove_legacy_audit.sql` (туда же) или `029_audit_on_dictionaries.sql`
- **Что:** добавить `audit_trigger_fn` триггеры на:
  - `atributy`
  - `tipy_kollekciy`
  - `kategoriya_atributy`
  - `cvet_kategoriya`
  - `fabriki`
  - `modeli_osnova_razmery`

### W10.41 — Уточнить RLS на tipy_kollekciy
- **Где:** та же миграция
- **Что:** разделить ALL-политику на INSERT/UPDATE/DELETE с правильными `USING`/`WITH CHECK`.

---

## Wave E — Reference cards (3 пункта)

### W10.14 + W10.15 + W10.35 — Drawer-карточки справочников
- **Где:** все страницы `/catalog/references/*`
- **Фикс:** при клике на запись бренда / категории / коллекции / типа / фабрики — открывается drawer (по образцу ArtikulDrawer/ModelDrawer) с:
  - редактируемыми полями справочника
  - списком привязанных моделей (LEFT JOIN на `modeli_osnova`)
  - возможностью добавить/удалить модель из этой группы (multi-select)
- Особо для `tipy_kollekciy` — список коллекций (`kollekcii.tip_kollekcii_id`)
- Особо для `kategorii` — список атрибутов (через `kategoriya_atributy`)
- Особо для `semeystva_cvetov` — список цветов

---

## Архитектурные решения

1. **Color util** — единая `colorSwatchStyle(hex)` в `lib/catalog/color-utils.ts`, импортируется везде где есть swatch
2. **Drawer pattern** — общий компонент `<Drawer>` с `rounded-l-2xl` для всех карточек (модель/артикул/SKU/склейка/справочники)
3. **Inline-edit** — везде `onDoubleClick`, single-click открывает drawer
4. **Сортировка размеров** — утилита `compareRazmer(a, b)` на основе `RAZMER_LADDER` (XS<S<M<L<XL<XXL<3XL<4XL<5XL…)
5. **Bulk-actions** — единый компонент `BulkActionsBar` с props для всех 3 реестров
6. **Audit history** — только новая система (`audit_log`), legacy `log_izmeneniya` снести
7. **Junction artikuly_skleyki_*** — новые таблицы для группировки по артикулу
8. **Breadcrumbs** — единый mapping `ROUTE_LABELS` для русских названий
9. **Status types** — `cveta.status_id` → только color-статусы, защита триггером

---

## Порядок волн

```
A (14) → B (5) → C (4) → D (11) → E (3) → Verifier → Fix wave → Verifier 2 → Build + rsync + smoke
```

Все волны автономно — пользователь подтвердил в W9 цикле и здесь.
