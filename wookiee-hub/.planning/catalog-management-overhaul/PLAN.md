# Wookiee Hub — Catalog Management Overhaul

Создано: 2026-05-11
Статус: ⏳ pending approval
Owner: Danila / PM

## Цель

Превратить wookiee-hub каталог из read-mostly витрины в полноценную CMS, где PM может через UI запустить новый бренд от нуля до SKU без SQL.

**Acceptance test (мерило успеха):**
PM логинится → выбирает бренд **TELOWAY** в фильтре → жмёт «+ Новая модель» → создаёт модель «Atlas» (бренд TELOWAY, категория «Топ», коллекция «Спортивная»), размерная линейка XS-XXL → добавляет цвета black/white/mint_green в палитру → жмёт «Создать артикулы для всех цветов» (3 артикула) → жмёт «Создать SKU для всей размерной линейки» (18 SKU = 3 × 6) → загружает фото модели → привязывает сертификат → выбирает статус «Запуск». Всё за < 5 минут, без единой строки SQL.

**Два бренда (стартовая фикстура):**
- **WOOKIEE** — бельё (комплекты, трусы, боди, бюстгальтеры)
- **TELOWAY** — спортивная одежда (леггинсы, лонгсливы, рашгарды, топы, футболки, велосипедки) — wellness-бренд, запуск 2026

## Состояние сегодня (что есть)

- **Auth + tools**: ✅ работает (`/operations/tools`, magic-link + password)
- **Каталог чтения**: ✅ матрица 56 моделей / 553 артикулов / 1473 SKU
- **CRUD справочников**: ✅ цвета, размеры, юрлица, категории, коллекции, фабрики, упаковки, каналы, сертификаты, семейства цветов
- **Карточка модели**: ⚠️ редактирование атрибутов работает, но создание артикулов / SKU / вариаций — disabled (Wave 3+)
- **Бренд как сущность**: ❌ нет в БД
- **Загрузка файлов**: ❌ нет Storage + только URL-ссылки
- **Audit log**: ❌ нет
- **CSV import**: ❌ нет
- **Хардкоды**: размерная линейка `XS-XXL`, `ATTRIBUTES_BY_CATEGORY` маппинг — в коде

## Архитектурные решения (по 5 вопросам)

1. **Бренд** — отдельная таблица `brendy`. НЕ переименовывать фабрики (фабрика = производитель: Singwear / Angelina / B&G; бренд = маркетинговое имя: WOOKIEE / TELOWAY). При миграции — backfill через категории:
   - Категории 1, 2, 3, 11 (Комплект белья / Трусы / Боди / Бюстгалтер) → **WOOKIEE** (37 моделей)
   - Категории 4, 5, 6, 7, 8, 10 (Леггинсы / Лонгслив / Рашгард / Топ / Футболка / Велосипедки) → **TELOWAY** (19 моделей)
2. **Storage bucket** — `catalog-assets`, private, signed URLs (TTL 1 час), max 10MB, allowed `image/*` + `application/pdf`. RLS: SELECT/INSERT для authenticated, DELETE owner-only.
3. **Bulk-add size** — модалка с чекбоксами выбранных артикулов, по умолчанию все отмечены. Кнопка «Создать N SKU».
4. **Status RPC bug** — фиксим **первым** в W1.0. Колонка статуса в матрице пуста, хотя данные в БД есть. Скорее всего `matrix-list` RPC не возвращает поле. 30 минут.
5. **План** — этот файл. Promпт в новой сессии — короткий, ссылается сюда. Между волнами — обязательное согласование с пользователем.

## Структура — 8 волн

Внутри волны задачи параллельны (через `dispatching-parallel-agents`). Между волнами — последовательно: PR + smoke + согласие пользователя.

---

### Волна 1 — UI Polish + Status Bug (1 день, parallel ×7)

**Цель:** убрать раздражения, починить status bug.

| ID | Задача | File | Acceptance |
|---|---|---|---|
| W1.0 | **Status RPC bug** | RPC `matrix-list` или соответствующая view + `matrix.tsx:1377-1503` | Колонка СТАТУС в матрице показывает badge для всех 56 моделей. Запрос `SELECT status_id FROM matrix-list` возвращает значение. |
| W1.1 | Tooltip viewport clipping | `matrix.tsx:1428` (`<Tooltip>`) | «У модели одна вариация…» не обрезается за сайдбаром. Использовать Radix Popover с `collisionPadding`. |
| W1.2 | Numeric validation | `model-card.tsx` (Срок производства, Кратность, Вес, Длина, Ширина, Высота) | `<input type="number">` + unit-suffix. Ввод «sad» блокируется браузером. |
| W1.3 | Dedup «Атрибуты-отношения» | `model-card.tsx:553` (Описание) — удалить, оставить только 731 (Атрибуты) | Атрибуты только в одном табе. |
| W1.4 | Tags combobox | `model-card.tsx` (поле «Теги») + новый `<TagsCombobox>` | Combobox с автокомплитом существующих тегов + создание нового on-the-fly. |
| W1.5 | Column resize | `<thead>` matrix/artikuly/tovary + SKU реестр | Drag-resize на правом краю `<th>`. Persist в `ui_preferences.column_widths`. |
| W1.6 | Hint tooltips | Все поля-ссылки в `model-card.tsx` (Notion, стратегия, Я.Диск, числовые) | `(?)` иконка с пояснением: «Скопируй URL из Notion» / «Срок в днях» и т.д. |
| W1.7 | Empty cert select fix | `model-card.tsx` (модалка «Привязать сертификат») | Если 0 сертификатов — disable submit + ссылка «Создать сертификат →». |

**После W1:** PR #11 → smoke → согласование W2.

---

### Волна 2 — Hardcodes → DB (2 дня, parallel ×3)

**Цель:** убрать хардкод-маппинги, чтобы новые справочники работали без правки фронтенда.

| ID | Задача | Migration | UI |
|---|---|---|---|
| W2.1 | Размерная линейка модели из БД | Junction `modeli_osnova_razmery (model_id, razmer_id, poryadok)` ИЛИ `razmernye_lineyki` справочник + FK | Удалить `SIZES_LINEUP` хардкод из `model-card.tsx:87`. Чипы рендерятся из `useQuery(fetchSizesForModel)`. |
| W2.2 | Категория ↔ атрибуты из БД | `kategoriya_atributy(kategoriya_id, atribut_key, poryadok)`. Backfill из текущего хардкода `ATTRIBUTES_BY_CATEGORY` в `types/catalog.ts:426-464`. | Таб «Атрибуты» в model-card — рендер контролов по `useQuery(fetchAttributesForCategory)`. |
| W2.3 | `tip_kollekcii` — справочник | `tipy_kollekciy(id, nazvanie)` + `modeli_osnova.tip_kollekcii_id INT FK`. Backfill: GROUP BY текущее текстовое поле → создать справочные записи → переписать FK. | Заменить `<input>` на `<select>` в model-card. Страница `/catalog/references/tipy-kollekciy` с CRUD. Nav-пункт. |

**После W2:** PR #12 → smoke → согласование W3.

---

### Волна 3 — Бренд (2 дня, parallel ×2) — КРИТИЧЕСКИ

**Цель:** ввести бренд как первоклассную сущность.

| ID | Задача |
|---|---|
| W3.1 | **Migration + service.** Таблица `brendy(id, kod, nazvanie, opisanie, logo_url, status_id)`. Фикстура: `('wookiee', 'WOOKIEE', 'Бельё')` + `('teloway', 'TELOWAY', 'Спортивная одежда — wellness-бренд, запуск 2026')`. RLS + GRANT. Колонка `modeli_osnova.brand_id INT FK brendy(id) NOT NULL`. **Backfill через категории**: `UPDATE modeli_osnova SET brand_id = (SELECT id FROM brendy WHERE kod='wookiee') WHERE kategoriya_id IN (1,2,3,11);` + аналогично для TELOWAY на (4,5,6,7,8,10). После backfill добавить NOT NULL. Сервис `fetchBrendy / insertBrend / updateBrend / archiveBrend`. |
| W3.2 | **UI.** Nav-пункт «Бренды» в группе «Справочники». Page `references/brendy.tsx` (CRUD). ModelCard: `<select>` бренда (обязательное поле). Matrix: фильтр по бренду + опц. колонка. Модалка создания модели (W4.1) — обязывает выбрать бренд. |

**После W3:** PR #13 → smoke (создать новый бренд) → согласование W4.

---

### Волна 4 — Article/SKU CRUD (3 дня, parallel ×6) — КРИТИЧЕСКИ

**Цель:** дать PM создавать артикулы, SKU, вариации через UI.

| ID | Задача | File / Service |
|---|---|---|
| W4.1 | Модалка «+ Новая модель» | `matrix.tsx:2063-2123`. Заменить `window.prompt` на `<NewModelModal>`. Поля: kod, brand_id (W3), kategoriya_id, kollekciya_id, tip_kollekcii_id (W2.3), fabrika_id, importer_id (= первая вариация), status_id, razmery[] (W2.1). Транзакция: создать `modeli_osnova` + первую `modeli`. |
| W4.2 | Создание вариации | `model-card.tsx:1351` (disabled). Service `insertVariation(model_osnova_id, importer_id, kod_suffix?)`. Модалка выбора юрлица. |
| W4.3 | Создание артикула | `model-card.tsx:794` (disabled). Service `insertArtikul(modeli_id, cvet_id)`. Auto-генерит `artikul = ${kod}/${color_code}`. Модалка с палитрой цветов + кнопка «Создать для всех цветов модели». |
| W4.4 | Создание + bulk-add SKU | `model-card.tsx:867-940` (TabSKU). Кнопка «+ SKU» + «+ Размер ко всем». Service `insertTovar(artikul_id, razmer_kod)` + `bulkAddSizeToArtikuly(artikul_ids[], razmer_kod)`. **Модалка** — чекбоксы артикулов (по умолчанию все отмечены) + выбор размера. |
| W4.5 | Inline-edit статусов SKU | `model-card.tsx:880-940`. Снять «Wave 3+ TODO». Клик по ячейке `status_wb/status_ozon/status_sayt/status_lamoda` → dropdown статусов (только tip='product'). Service `bulkUpdateTovaryStatus` уже есть. |
| W4.6 | Bulk-change status в реестре артикулов | `artikuly.tsx:306` (alert TODO). `BulkActionsBar` → popover статусов tip='artikul'. Service `bulkUpdateArtikulStatus(ids[], status_id)`. |

**После W4:** PR #14 → smoke (полный flow: бренд → модель → артикул → SKU). **Уже можно запускать «Telovai» в проде.** → согласование W5.

---

### Волна 5 — Image Upload (2 дня, parallel ×4)

**Цель:** загружать фото моделей, фото-семплы цветов, PDF сертификатов. Можно пускать параллельно с W3-W4 (нет общих файлов).

| ID | Задача |
|---|---|
| W5.1 | **Storage setup.** Bucket `catalog-assets` (private, max 10MB, allowed `image/*` + `application/pdf`). RLS policies: SELECT через signed URL, INSERT authenticated, DELETE owner. Helper `getSignedUrl(path, ttl=3600)`. |
| W5.2 | **Фото модели.** Migration: `modeli_osnova.header_image_url TEXT`. `model-card.tsx:1449` — заменить `headerImageUrl` placeholder на `<ImageUploader>`. Drag-drop + paste URL. Превью + удаление. Сохраняет в Storage path, в БД пишет path. |
| W5.3 | **Фото-семпл цвета.** Migration: `colors.image_url TEXT`. `colors.tsx` (`CvetEditModal`) — добавить uploader. Маленькое превью рядом с hex-swatch. |
| W5.4 | **Реальный upload сертификатов.** `sertifikaty.tsx` — `file_url` принимает либо URL, либо upload. Storage path. Viewer открывает в новом табе через signed URL. |

**После W5:** PR #15 → smoke → согласование W6.

---

### Волна 6 — Attrs Registry + Custom Fields (2 дня, parallel ×3)

**Цель:** убрать последний хардкод — список самих атрибутов.

| ID | Задача |
|---|---|
| W6.1 | **Справочник атрибутов.** Migration: `atributy(id, key, label, type, options JSONB, default_value, helper_text)`. Type enum: text/number/textarea/select/multiselect/file_url/url/date/checkbox/pills. Расширить `kategoriya_atributy` (W2.2) на `atribut_id INT FK atributy(id)`. Backfill: создать `atributy` rows из всех уникальных ключей в W2.2-mapping. Page `/catalog/atributy` (CRUD). Nav-пункт. |
| W6.2 | **Custom URL/file fields.** Часть W6.1. PM создаёт атрибут «Ссылка на сертификат на Я.Диске», тип `url` → автоматически появляется в карточке всех моделей выбранной категории. |
| W6.3 | **Унификация контролов (B2).** `model-card.tsx` блок Атрибуты — заменить native `<select>` (Регулировка, Посадка, Вид трусов) на кастомный `<AttributeControl>` с modes: single-select / multi-select / pills. По типу атрибута из W6.1. |

**После W6:** PR #16 → smoke → согласование W7.

---

### Волна 7 — Audit + Import/Export (3 дня, parallel ×3)

**Цель:** трасса изменений + bulk-операции.

| ID | Задача |
|---|---|
| W7.1 | **Audit log.** Migration: `audit_log(id, table_name, row_id, user_id, action, before JSONB, after JSONB, created_at)`. Триггеры на `modeli_osnova / modeli / artikuly / tovary / colors / brendy / kollekcii / kategorii / sertifikaty`. UI: вкладка «История» в model-card — список изменений с дифом «before → after». Service `fetchAuditFor(table, id)`. |
| W7.2 | **CSV import.** Page `/catalog/import`. Wizard в 3 шага: (1) загрузка CSV → (2) preview с маппингом колонок → (3) dry-run с показом invalid rows → confirm. Service: парсер на `papaparse` + `bulkInsert*` RPC. Шаблоны для модель/артикул/SKU. |
| W7.3 | **4× CSV exports.** `matrix.tsx:1613, 2113`, `artikuly.tsx:311`, `tovary.tsx:855` — все alert TODO. Реализовать через `papaparse`. «Экспорт» отдаёт visible columns + applied filters. |

**После W7:** PR #17 → smoke → согласование W8.

---

### Волна 8 — Final Polish (2 дня, parallel ×6)

**Цель:** сортировка, пагинация, drill-downs.

| ID | Задача |
|---|---|
| W8.1 | **Sort.** Все таблицы (matrix/artikuly/tovary/SKU реестр) — клик по `<th>` сортирует. Иконка ↑↓. Persist в `ui_preferences`. |
| W8.2 | **Pagination.** Заменить «Показаны первые 100 из X» на нормальную пагинацию или infinite scroll через `react-virtual`. |
| W8.3 | **Hover-tooltips на сложных колонках.** «Заполн.» — hover показывает список незаполненных полей с весами. «Цв / Арт / SKU» — расшифровка. |
| W8.4 | **Drill-down артикул.** Клик по `Alice/black` в `/catalog/artikuly` → overlay/page с 3 SKU и кнопкой «+ SKU». |
| W8.5 | **Cell inline-edit.** В `/catalog/artikuly` и `/catalog/tovary` — клик по ячейке статуса → inline dropdown без open-edit-save. |
| W8.6 | **Status chips filter verify.** Проверить что чипы в шапке матрицы (Планирование 34 / В продаже 16 / …) фильтруют список. Если нет — починить. |

**После W8:** PR #18 → финальный e2e smoke (полный flow запуска Telovai с нуля). Объявить готовность PM.

---

## Правила исполнения

- **Между волнами**: PR + smoke на проде + явное согласие пользователя на следующую волну. Не запускать W(N+1) пока W(N) не зелёная.
- **Внутри волны**: задачи параллельны через `superpowers:dispatching-parallel-agents`. Конфликты merge — разрешать по мере появления.
- **DDL**: только через `mcp__plugin_supabase_supabase__apply_migration`. Каждую migration сохранять в `database/migrations/`.
- **Браузер для smoke**: Playwright. Если auth ломается — попросить пользователя сгенерить пароль через email reset или `extensions.crypt`.
- **Деплой**: после каждого PR — `cd wookiee-hub && rm -rf dist && npm run build && rsync -avz --delete dist/ timeweb:/home/danila/projects/wookiee/wookiee-hub/dist/`.
- **Backwards compat**: миграции «свободный текст → FK» — с backfill из существующих данных. Не ронять прод.
- **Стоп-условия**: если за 1 час упёрлись в архитектурный вопрос — стоп, эскалировать пользователю. Не выдумывать.

## NOT в скоупе

- WB/OZON API integration (генерация `nomenklatura_wb` / `artikul_ozon` из API). Остаётся ETL вне hub.
- Hard-delete с обходом FK. Только архивация.
- Permissions / role-based UI (admin/editor/viewer). Все авторизованные = full access.
- Mobile-responsive — desktop-first.
- i18n — только русский.

## Затраты времени (оценка)

| Волна | Дней |
|---|---|
| W1 — UI Polish + Status Bug | 1 |
| W2 — Hardcodes → DB | 2 |
| W3 — Бренд | 2 |
| W4 — Article/SKU CRUD | 3 |
| W5 — Image Upload | 2 |
| W6 — Attrs Registry | 2 |
| W7 — Audit + Import/Export | 3 |
| W8 — Final Polish | 2 |
| **Итого** | **17 дней** |

После W4 (день 8) PM может запустить Telovai в продакшн. W5-W8 — наращивание возможностей.

## Открытые вопросы для пользователя

✅ Бренды: WOOKIEE (бельё) + TELOWAY (спорт) — стартовая фикстура утверждена.
✅ Backfill через категории — 37 + 19 = 56 моделей подтверждены.
✅ Фабрики остаются отдельной сущностью (производство ≠ бренд).
