# Wave 3 — QA + Screenshot Diff с MVP

**Цель:** Сквозная end-to-end проверка против MVP-эталона, починка регрессий.
**Параллелизация:** Частично (3 параллельных агента + 1 финальный).
**Зависимость:** Wave 2 полностью замержена в main.

## Архитектура

```
Wave 3:
 ├── C1 — Visual diff agent (Playwright screenshots vs MVP)
 ├── C2 — Functional QA agent (E2E user journeys)
 ├── C3 — Data integrity agent (data flows + RLS + bulk)
 └── C4 — Final fix agent (после 3х QA, исправляет всё найденное)
```

---

## Агент C1 — Visual Diff

### Промпт
```
Ты Wave 3 Agent C1 — визуальная сверка реализованного каталога с MVP-эталоном.

Контекст:
- Эталон: /Users/danilamatveev/Projects/Wookiee/redesign + PIX/wookiee_matrix_mvp_v4.jsx
- Hub URL (dev): http://localhost:5173/catalog
- Используй Playwright MCP

Шаги:
1. Запустить dev сервер Hub в фоне (npm run dev)
2. Создать html-демо MVP — wookiee_matrix_mvp_v4.jsx нужно отрендерить отдельно. Если он работает в Vite — поставить временно на :5174.
3. Для каждой страницы: открыть Hub и MVP в parallel viewports, screenshot, сравнить.

Страницы для сверки:
- /catalog (MatrixView)
- /catalog?model=Vuki (ModelCard, выбрать существующую модель)
- /catalog/articles (Артикулы)
- /catalog/sku (SKU реестр)
- /catalog/colors (ColorsView)
- /catalog?color=AU001 (ColorCard)
- /catalog/skleyki (Skleyki)
- /catalog/skleyki/:id (SkleykaCard)
- /catalog/kategorii / kollekcii / fabriki / importery / razmery
- /catalog/semeystva-cvetov / upakovki / kanaly-prodazh / sertifikaty

Для каждого:
- Снять screenshot Hub (Playwright)
- Снять screenshot MVP
- Сохранить в .planning/catalog-rework/screenshots/
- Сравнить визуально, описать различия

Создать файл .planning/catalog-rework/wave_3_visual_diff.md со списком расхождений.
Категории расхождений:
- BLOCKER (различие критическое: missing column, отсутствует кнопка)
- MAJOR (визуально неверно, но функционально работает)
- MINOR (небольшие отступы, цвета)

Когда готово — отчёт на 300 слов.
```

---

## Агент C2 — Functional QA (E2E user journeys)

### Промпт
```
Ты Wave 3 Agent C2 — E2E user journey тесты каталога.

Используй Playwright MCP для всех тестов.

Сценарии (каждый — отдельный E2E, без падений):

### J1: Создание новой модели
1. Открыть /catalog
2. Кликнуть «+ Создать модель» (если есть)
3. Заполнить kod, nazvanie_etiketka, kategoriya, kollekciya, fabrika
4. Сохранить → редирект на ?model=NEW_KOD
5. Проверить что модель появилась в матрице

### J2: Редактирование модели
1. /catalog?model=Vuki
2. Кликнуть «Редактировать»
3. Изменить description
4. Сохранить
5. Refresh → изменение сохранилось

### J3: Дублирование модели
1. /catalog?model=Vuki
2. Кликнуть «Дублировать»
3. Ввести kod = «Vuki2»
4. Сохранить
5. Проверить что Vuki2 создалась с теми же атрибутами, но БЕЗ вариаций/артикулов/SKU

### J4: Каскадное архивирование
1. /catalog?model=NEW_TEST_MODEL (создать тест-модель + 1 вариация + 1 артикул + 2 SKU)
2. Архивировать модель
3. Проверить:
   - modeli_osnova.status_id = «Архив»
   - modeli у этой модели тоже архив (если в БД есть статус)
   - artikuly у модели → «Выводим»
   - tovary у модели → status_id = «Архив», status_ozon_id = «Архив»

### J5: Bulk изменение статусов
1. /catalog
2. Выделить 3 модели чекбоксами
3. BulkActionsBar → «Изменить статус» → «В продаже»
4. Проверить что все 3 теперь «В продаже»

### J6: Bulk привязка к склейке
1. /catalog/sku
2. Выделить 5 SKU одного цвета, разных размеров
3. BulkActionsBar → «Привязать к склейке» → выбрать существующую
4. Проверить что в /catalog/skleyki/:id появились эти SKU

### J7: Composite search
1. /catalog/sku
2. В search ввести «Audrey/black/S»
3. Должно найти SKU с моделью Audrey, цветом black, размером S

### J8: GroupBy в матрице
1. /catalog
2. GroupBy = «По коллекции»
3. Должны появиться заголовки коллекций, под каждым — модели

### J9: ColumnsManager
1. /catalog/sku
2. Открыть ColumnsManager
3. Выключить «Цена WB», включить «Баркод GS1»
4. Сохранить
5. Перезагрузить страницу — настройки сохранились

### J10: ⌘K CommandPalette
1. Любая страница каталога
2. Нажать ⌘K
3. Ввести «Vuki»
4. Должны появиться: модель Vuki, артикулы Vuki, SKU Vuki
5. Click → переход на нужную страницу/карточку

### J11: Reference CRUD
1. /catalog/upakovki
2. «+ Добавить» → новый
3. Заполнить, сохранить → появился в таблице
4. Edit → изменить, сохранить → обновилось
5. Delete → подтвердить → исчез

### J12: Inline edit статусов
1. /catalog/sku
2. Click по StatusBadge в строке
3. Выбрать другой статус
4. Refresh → сохранилось

Для каждого сценария — pass/fail + описание проблемы.

Создать .planning/catalog-rework/wave_3_functional_qa.md.

Когда готово — отчёт на 400 слов.
```

---

## Агент C3 — Data Integrity

### Промпт
```
Ты Wave 3 Agent C3 — проверка целостности данных и RLS.

Используй mcp__plugin_supabase_supabase для запросов.

### Проверки целостности
1. **statusy** — 6 типов, нет «Новый»
2. **kategorii / kollekcii** — нет дубликатов
3. **modeli_osnova** — все имеют status_id
4. **cveta** — все имеют semeystvo, ≤30 без hex
5. **artikuly** — все имеют cvet_id, kod_modeli, model existence
6. **tovary** — баркоды уникальны в рамках канала, артикулы существуют
7. **sklejki** — junction tables не имеют orphan rows
8. **modeli_osnova_sertifikaty** — все sertifikat_id существуют

### RLS проверка
Для каждой каталоговой таблицы (statusy, kategorii, kollekcii, fabriki, importery, razmery, modeli_osnova, modeli, artikuly, tovary, cveta, semeystva_cvetov, upakovki, kanaly_prodazh, sertifikaty, ui_preferences, sklejki, modeli_osnova_sertifikaty):
- pg_policies должны включать SELECT, INSERT, UPDATE, DELETE для authenticated
- ENABLE ROW LEVEL SECURITY = true

### Bulk операции (через service.ts)
1. bulkUpdateModelStatus(['kod1', 'kod2'], status_id) — оба обновляются
2. bulkUpdateTovaryStatus(['barkod1'], status_id, 'wb') — только статус WB меняется
3. bulkLinkTovaryToSkleyka работает на 30 SKU
4. bulkUnlinkTovaryFromSkleyka работает корректно

### Cascade archive
1. Создать тестовую модель TEST_CASCADE с 1 вариацией, 2 артикулами, 4 SKU
2. archiveModel('TEST_CASCADE')
3. Проверить через SQL:
   - modeli_osnova.status_id = id архивного model-статуса
   - artikuly.status_id = id «Выводим»
   - tovary: status_id, status_ozon_id, status_sayt_id, status_lamoda_id — все «Архив»

Создать .planning/catalog-rework/wave_3_data_integrity.md.

Когда готово — отчёт на 300 слов.
```

---

## Агент C4 — Final Fix

### Промпт
```
Ты Wave 3 Agent C4 — последний агент, исправляющий все найденные регрессии.

Прочитай:
- .planning/catalog-rework/wave_3_visual_diff.md (от C1)
- .planning/catalog-rework/wave_3_functional_qa.md (от C2)
- .planning/catalog-rework/wave_3_data_integrity.md (от C3)

Задача:
1. Сгруппируй все BLOCKER + MAJOR баги
2. Для каждого — определи правильный файл/функцию (читать код, не угадывать)
3. Исправь
4. После каждого исправления — verify через Playwright или SQL

Не затрагивай MINOR (отступы, оттенки) — это финальная полировка после согласования с пользователем.

Не делай рефакторинга «по дороге» — только point fixes.

После всех исправлений:
1. Прогнать ещё раз ключевые сценарии:
   - Колонка статуса в матрице
   - Размерная линейка как chip-pills
   - LevelBadge на полях ModelCard
   - Каскадное архивирование
2. Создать .planning/catalog-rework/wave_3_final_report.md с:
   - Список всех исправленных багов
   - Список оставшихся MINOR (для пользователя на ревью)

Когда готово — git commit «Wave 3 final fixes», push.
```

---

## Verification Wave 3
- [ ] visual diff: все BLOCKER и MAJOR закрыты
- [ ] functional QA: 12/12 сценариев pass
- [ ] data integrity: все RLS-политики на месте, нет orphan rows
- [ ] Колонка «Статус» в матрице — ✅
- [ ] Размерная линейка как chip-pills — ✅
- [ ] LevelBadge на каждом поле ModelCard — ✅
- [ ] Каскадное архивирование работает — ✅
- [ ] CommandPalette ⌘K — ✅
- [ ] Bulk actions работают — ✅
- [ ] Все 9 справочников редактируются — ✅

После Wave 3 → задача передаётся пользователю на финальное ревью.

## Финальный отчёт пользователю

После Wave 3 создать .planning/catalog-rework/FINAL_REPORT.md:
- Что сделано (по фазам)
- Скриншоты до/после
- Список MINOR на финальную полировку
- Что не было сделано и почему
- Предложение демонстрации (npm run dev + browse)
