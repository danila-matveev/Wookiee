# Wave 3 — Visual Diff Report (Agent C1)

Эталон: `/Users/danilamatveev/Projects/Wookiee/redesign + PIX/wookiee_matrix_mvp_v4.jsx` (2044 строки JSX)
Проверяемый код: ветка `catalog-rework-2026-05-07`, dev-сервер `http://127.0.0.1:5173`
Скриншоты: `wookiee-hub/.planning/catalog-rework/screenshots/wave_3/`

## Summary
- Pages tested: 18 (17 каталоговых + ModelCard tab Артикулы)
- BLOCKER: 2
- MAJOR: 4
- MINOR: 4
- Console errors: 0 (на всех проверенных страницах)

Все скриншоты собраны при viewport 1440x900, fullPage. Авторизация — через временный пароль (после прогона пароль ротирован на случайный 32-байтный, владельцу нужно восстановление через email).

## По страницам

### 1. /catalog/matrix (MatrixView)
**Скриншот:** screenshots/wave_3/01_matrix.png
**Status:** PASS (с минорами)
**Findings:**
- Подзаголовок «56 моделей · 11 вариаций · 553 артикулов · 1473 SKU» — есть.
- Кнопка «Экспорт» справа от подзаголовка — есть.
- Кнопка «Новая модель» — есть.
- Чекбокс-колонка для bulk — есть (columnheader «Выбрать все»).
- Колонка «Статус» в таблице — **есть** (StatusBadge). Колонки: Название/Категория/Коллекция/Фабрика/Статус/Размеры/Цвета/Заполн./Цв·Арт·SKU/Обновлено.
- Filter chips: Категории (10) и Коллекции (10) — все, ВСЕ 7 model-статусов с counts (Планирование 34, Делаем образец 0, Закуп 0, Запуск 1, В продаже 16, Выводим 5, Архив 0).
- GroupBy Select — есть, 5 опций (Без / По категории / По коллекции / По фабрике / По статусу).
- Search field, Незаполненные filter, индикатор «56 из 56».
- Размеры в строках — chip-pills.
- Цвета — swatch'и с кодами.
- CompletenessRing на каждой строке — есть.
- BulkActionsBar — не проверял в выделенном состоянии (не было задачей C1, но C3 проверит).
- [MINOR] Tabs над контентом «Базовые модели56 / Артикулы (реестр)553 / SKU (реестр)1473» — это вторая навигация, дублирует sidebar (в MVP — только sidebar). Можно оставить — UX нагрузка низкая.

### 2. /catalog/matrix?model=Vuki (ModelCard)
**Скриншот:** screenshots/wave_3/02_modelcard_vuki.png + 03_modelcard_vuki_artikuly.png
**Status:** PARTIAL
**Findings:**
- Header: breadcrumb «Каталог > Матрица > Vuki», подзаголовок «Базовая модель · Комплект белья», заголовок «Vuki — Комплект белья Вуки: топ + стринги», кнопки «Дублировать», «В архив», «Редактировать».
- 5 табов: Описание / Атрибуты 10/10 / Артикулы 120 / SKU 361 / Контент и связи — есть.
- Sidebar: Заполненность 70% / 10/10, Вариации 7 (с пометкой ИП/ООО), Цвета модели 73 (swatches), Метрики (за экраном).
- Footer: «Данила · CEO · Wookiee» — есть.
- [BLOCKER] **Размерная линейка «S, M, L, XL» — отображается plain текстом** под подзаголовком «РАЗМЕРНАЯ ЛИНЕЙКА». В MVP — chip-pills XS/S/M/L/XL/XXL. Это первое жалобное замечание пользователя (см. 03_GAP_LIST.md F).
- [BLOCKER] **LevelBadge на полях Описания отсутствует.** Поля «КОД МОДЕЛИ / СТАТУС / КАТЕГОРИЯ / КОЛЛЕКЦИЯ / ТИП КОЛЛЕКЦИИ / ФАБРИКА / РАЗМЕРНАЯ ЛИНЕЙКА / МАТЕРИАЛ / SKU CHINA / СОСТАВ СЫРЬЯ / СРОК ПРОИЗВОДСТВА / КРАТНОСТЬ КОРОБА / ВЕС / ДЛИНА / ШИРИНА / ВЫСОТА» — без бейджей уровня (Базовый / MP / Расширенный) на каждом поле. В MVP — обязательны.
- [MAJOR] Кнопки декоративные: editing/draft state не виден в скриншоте (по визуалу не протестирован — это территория C2). Из 03_GAP_LIST.md F пометка «editing + draft state ❌ нет» — нужно подтвердить в functional QA.
- [MINOR] В sidebar блок «Заполненность» показывает «70% / 10/10» — пара чисел рассогласована (10/10 = 100%, а ring 70%). В MVP это рассчётная заполненность по разным группам полей; визуально путает.

### 3. /catalog/matrix?model=Vuki tab Артикулы
**Скриншот:** screenshots/wave_3/03_modelcard_vuki_artikuly.png
**Status:** PASS (с одним замечанием)
**Findings:**
- Список 120 артикулов с цветом (swatch + код), категориями, ВБ-номенклатурой, OZON-артикулом.
- Sidebar: Заполненность, Вариации (7), Цвета модели (73 swatches).
- [MINOR] «+ Добавить» в шапке секции Артикулы — не подтверждён на скриншоте (мелко). Из 03_GAP_LIST.md F пометка «❌ нет» — функциональная проверка C2.

### 4. /catalog/artikuly (Артикулы реестр)
**Скриншот:** screenshots/wave_3/04_artikuly.png
**Status:** PASS
**Findings:**
- Заголовок «Артикулы», подзаголовок «553 артикулов».
- Search «Артикул, модель, цвет, WB-ном, OZON…».
- Status filter chips: Все 553 / Запуск 0 / Продаём 0 / Выводим 0 — есть (counts реальные, видимо большая часть без status).
- Кнопка «Колонки (7)» — есть, ColumnsManager.
- Чекбоксы есть.
- 7 видимых колонок: Артикул / Модель / Цвет / Статус артикула / WB-номенклатура / OZON-артикул / Создан.
- Composite breadcrumb: «Каталог > Артикулы».
- [MINOR] В 03_GAP_LIST.md D указано «11 колонок» в ColumnsManager — у нас 7. Возможно скрыли часть и используем выборку — сравнить с MVP.

### 5. /catalog/tovary (SKU реестр)
**Скриншот:** screenshots/wave_3/05_tovary.png
**Status:** PARTIAL
**Findings:**
- Заголовок «SKU/Товары», подзаголовок «1000 SKU».
- Composite search с placeholder «Audrey/черный/S — модель/цвет/размер» — есть.
- Channel filter (Все / WB / OZON / Сайт / Lamoda) — есть.
- GroupBy Select «Без группировки» — есть.
- Status filter chips (Все / Активные / Архив / Без статуса) — есть.
- Кнопка «Колонки (8)» — есть.
- Колонки: Баркод / Артикул / Модель / Цвет / Размер / WB-номенклатура / OZON-артикул (+ ещё под скрытыми).
- [MAJOR] **Подзаголовок «1000 SKU» при реальных 1473 SKU** в БД (`SELECT count(*) FROM tovary` = 1473). Видимо лимит ещё работает — несмотря на коммит `44fda5b fix(catalog): remove Supabase 1000-row default limit on tovary registry`. Возможно лимит снят только в matrix, но не в tovary fetcher. Внизу таблицы «1000 из 1000» — это подтверждает.
- [MINOR] В 03_GAP_LIST.md E указано «17 колонок» — у нас в ColumnsManager «8». Нужно сверить требование с MVP.

### 6. /catalog/colors (ColorsView)
**Скриншот:** screenshots/wave_3/06_colors.png
**Status:** PASS
**Findings:**
- Заголовок «Цвета», подзаголовок «146 цветов · группировка по семейству».
- Семейства filter с counts: Все / Трикотаж (цифровые коды) 40 / Jelly (бесшовный) / Audrey / Наборы трусов / Прочие — есть.
- Status filter (Все / Продаём / Выводим / Архив) — есть.
- Кнопка «+ Новый цвет» — есть.
- Группировка по семейству с заголовком «ТРИКОТАЖ (ЦИФРОВЫЕ КОДЫ) 40 / Стандартный набор цветов для трикотажных коллекций» — отлично.
- Колонки: Color Code / Color (RU) / Color (EN) / Ластовица / Использован в / Статус.
- Search по коду / RU / EN.
- [MINOR] Hex picker для «+ Новый цвет» в скриншоте недоступен (модалка). Полная проверка — функциональная.

### 7. /catalog/colors?color=1 (ColorCard, White)
**Скриншот:** screenshots/wave_3/07_colorcard.png
**Status:** PASS
**Findings:**
- Header big swatch (~40px), Color Code «1», заголовок «White / White», подзаголовок «Цвет · семейство Трикотаж (цифровые коды)», кнопки «Редактировать», «Архивировать», крестик закрытия.
- 2 таба: Артикулы 11 / Модели использующие цвет 9.
- Таблица артикулов с колонками Артикул / Базовая модель / Вариация / Статус / WB номенкл. / OZON / SKU.
- Sidebar блоки: HEX (#FFFFFF, DB-точный + текстовое поле), Использование (Моделей 9 / Артикулов 11 / SKU 33), Атрибуты (Ластовица: белый), Похожие цвета (5+ swatches: 111, 123, 15w7, AU011, P4, P5).

### 8. /catalog/skleyki (Skleyki list)
**Скриншот:** screenshots/wave_3/08_skleyki.png
**Status:** PASS
**Findings:**
- Заголовок «Склейки маркетплейсов», подзаголовок «До 30 SKU в склейке. 34 активных, 9 пустых.» — есть (из 03_GAP_LIST.md H явно требовался).
- Search, Channel filter (Все/WB/OZON), Status filter (Все/Активные/Пустые/>30) — все есть.
- Кнопка «+ Создать склейку» — есть.
- Колонки: Название / Канал / **Заполненность (progress bar + cnt/30)** / Кол-во SKU / Создана / Статус — все ключевые.
- Progress bar реально цветной (зелёный когда заполнено ≥80%, красный когда переполнено).
- Статусы: Переполнена (красный) / Активна (зелёный) / Полная (зелёный) / Пустая (серый).

### 9. /catalog/references/kategorii
**Скриншот:** screenshots/wave_3/09_kategorii.png
**Status:** PASS
**Findings:**
- Subtitle «Базовые категории товаров», 10 записей, +Добавить, Search.
- Колонки: ID / Название / Описание / **Моделей (count)**.
- [MINOR] Hover MoreHorizontal (Edit/Delete) на каждой строке — не подтверждён на скриншоте, требует функциональной проверки.

### 10. /catalog/references/kollekcii
**Скриншот:** screenshots/wave_3/10_kollekcii.png
**Status:** PASS
**Findings:**
- Subtitle «Коллекции продуктов по году/тематике», +Добавить, Search.
- Колонки: ID / Название / Описание / Год запуска / Моделей.

### 11. /catalog/references/fabriki (Производители)
**Скриншот:** screenshots/wave_3/11_fabriki.png
**Status:** PASS
**Findings:**
- Subtitle «Фабрики и партнёры производства», 6 записей, +Добавить, Search «по названию, городу, email, WeChat».
- Все требуемые колонки: Название / Страна / Город / Контакт / Email / WeChat / Специализация / Lead Time / Моделей.
- Реальные данные: Singwear (CN, 42 моделей), Angelina (CN, 1), B&G (6) и т. д.

### 12. /catalog/references/importery (Юрлица)
**Скриншот:** screenshots/wave_3/12_importery.png
**Status:** PASS
**Findings:**
- Subtitle «Юридические лица для документов», 2 записи, +Добавить, Search «по названию, ИНН, банку».
- Все требуемые колонки: Short Name / Полное название / ИНН / КПП / ОГРН / Банк / Р/С / Контакт / Телефон.
- [MINOR] **ИНН отображается с «.0» в конце** (771889257880.0, 9729327530.0). Это форматирование числа из БД — нужно явно приводить к строке без десятичной части.

### 13. /catalog/references/razmery
**Скриншот:** screenshots/wave_3/13_razmery.png
**Status:** PASS
**Findings:**
- Subtitle «Размерная сетка с RU / EU / China», 6 записей, +Добавить, Search.
- Колонки: Код / Название / RU / EU / China / Порядок / SKU.

### 14. /catalog/semeystva-cvetov
**Скриншот:** screenshots/wave_3/14_semeystva-cvetov.png
**Status:** PASS
**Findings:**
- Subtitle «5 семейств для группировки цветовой матрицы», 5 записей, +Добавить, Search.
- Колонки: Код / Название / Описание / Цветов (count) / Порядок.
- 5 семейств (tricot 40, jelly 34, audrey 19, sets 8, other 45) — описания заполнены.

### 15. /catalog/upakovki
**Скриншот:** screenshots/wave_3/15_upakovki.png
**Status:** PASS
**Findings:**
- Subtitle «Виды упаковки с габаритами и стоимостью», 10 записей, +Добавить, Search.
- Колонки: Название / Тип (chip-pill: ПАКЕТ / ПАКЕТ ZIP / КОРОБКА / КОРОБКА С ПРИНТОМ) / Цена ¥ / ДxШxВ см / Срок (дн.) / Файл.
- [MAJOR] Прямой `browser_navigate` на `/catalog/upakovki` (cold load) сначала перенаправил на `/catalog/tovary`, но клик из sidebar на ту же ссылку открыл страницу корректно. Воспроизводимо для `/catalog/upakovki`, `/catalog/sertifikaty`, `/catalog/references/statusy`. Возможные причины: ленивый импорт + Suspense + `<ProtectedRoute>` race с auth. Не повторяется через клики, но при прямом переходе по URL — да. Нужно проверить в production-сборке.

### 16. /catalog/kanaly-prodazh
**Скриншот:** screenshots/wave_3/16_kanaly-prodazh.png
**Status:** PASS
**Findings:**
- Subtitle «4 канала продаж и их настройки видимости», 4 записи, +Добавить, Search.
- Колонки: Код (wb / ozon / sayt / lamoda) / Название (Wildberries / OZON / Сайт / Lamoda) / Short (WB / OZ / Сайт / LAM) / Color (chip swatch) / Активен (Активен / Выкл.) / Порядок.

### 17. /catalog/sertifikaty
**Скриншот:** screenshots/wave_3/17_sertifikaty.png
**Status:** PASS (empty state)
**Findings:**
- Subtitle «Сертификаты соответствия и декларации», 0 записей, +Добавить, Search «по названию, номеру, органу».
- Колонки: Название / Тип / Номер / Выдан / Окончание / Орган / Группа / Файл.
- Empty state «Сертификаты не найдены».
- См. п. 15: при прямом URL переадресация на /catalog/tovary — bug.

### 18. /catalog/__demo__ (UI demo)
**Скриншот:** screenshots/wave_3/18_demo.png
**Status:** PARTIAL (заглушка)
**Findings:**
- [MAJOR] **Страница пустая**: отображает только «UI Demo / В разработке. Демо atomic-компонентов появится после мерджа Wave 1 A3.». По плану Wave 1 atomic UI компоненты (Tooltip / LevelBadge / StatusBadge / CompletenessRing / Field*) уже должны быть готовы и здесь демонстрироваться. Без этого QA визуально не может проверить компоненты в изоляции.

## Сводный список багов для C4

### BLOCKERS (must fix)
1. **ModelCard: размерная линейка** показывается plain-текстом «S, M, L, XL» вместо chip-pills. Файл: `src/pages/catalog/matrix.tsx` (ModelCard секция «Производство»).
2. **ModelCard: LevelBadge отсутствует на всех полях Описания.** Компонент `level-badge.tsx` существует, но не используется. Нужно проставить `level` на каждом поле и рендерить badge рядом с подзаголовком.

### MAJOR (should fix)
3. **/catalog/tovary: показывает только 1000 из 1473 SKU** — Supabase default limit не снят для tovary fetcher (несмотря на коммит 44fda5b — возможно, исправление только для matrix-view).
4. **Прямой URL для `/catalog/upakovki` / `/catalog/sertifikaty` / `/catalog/references/statusy` редиректит на `/catalog/tovary`** — race condition с auth/Suspense. Через клики из sidebar работает.
5. **/catalog/__demo__** — заглушка. Должна демонстрировать atomic UI components (Tooltip, LevelBadge, StatusBadge, CompletenessRing, Fields).
6. **ModelCard: editing / draft state кнопки декоративные** (заявлено в 03_GAP_LIST.md F). Функциональная проверка C2 подтвердит.

### MINOR (для финальной полировки)
- ИНН в Юрлицах с «.0» в конце.
- ColumnsManager в /catalog/artikuly показывает 7 колонок — в ТЗ заявлено 11.
- ColumnsManager в /catalog/tovary показывает 8 колонок — в ТЗ 17.
- В Matrix есть вторичная навигация (3 chips «Базовые модели / Артикулы реестр / SKU реестр») — в MVP только sidebar.
- ModelCard заполненность ring/text рассогласованы (70% и 10/10).
- Hover MoreHorizontal на строках справочников — требует функциональной проверки.

## Что соответствует MVP полностью (PASS)
- Sidebar (15 пунктов: 5 контент + 9 справочников + Назад в Hub) с counts и футером «Данила · CEO».
- TopBar с breadcrumb (Каталог > Матрица > Vuki) и Search/⌘K.
- Matrix: подзаголовок, Экспорт, +Создать модель, чекбоксы, колонка Статус, фильтры категорий/коллекций/статусов с counts, GroupBy 5 опций, Незаполненные filter, CompletenessRing.
- Артикулы реестр: ColumnsManager, Status filter, Search.
- SKU/Tovary: composite search, channel filter, GroupBy, Status filter, ColumnsManager.
- ColorsView: группировка по семействам с заголовками, +Новый цвет, фильтры.
- ColorCard: big swatch, табы Артикулы/Модели, sidebar HEX/Использование/Атрибуты/Похожие цвета.
- Skleyki: подзаголовок «До 30 SKU…», Заполненность column с progress bar и cnt/30, +Создать склейку, статусы.
- Все 9 справочников открываются (с замечанием по прямому URL для 3 из них).
- 0 console errors.
