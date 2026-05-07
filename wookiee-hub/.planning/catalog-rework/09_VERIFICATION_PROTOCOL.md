# Verification Protocol — что проверять после каждой фазы

## Общие правила

После КАЖДОЙ фазы (Wave 0, 1, 2, 3) — обязательная серия проверок. Если хоть одна не прошла, **возврат к доработке, НЕ переходить к следующей фазе**.

## Базовые проверки (после каждой фазы)

### B1. TypeScript build
```bash
cd /Users/danilamatveev/Projects/Wookiee/wookiee-hub && npm run build
```
- Должно: 0 ошибок
- Если ошибки — исправить ДО финального коммита фазы

### B2. Lint
```bash
cd /Users/danilamatveev/Projects/Wookiee/wookiee-hub && npm run lint
```
- 0 errors, warnings допустимы (зафиксировать в отчёте)

### B3. Dev server smoke
```bash
cd /Users/danilamatveev/Projects/Wookiee/wookiee-hub && npm run dev
# Через Playwright MCP — открыть localhost:5173, перейти на /catalog
```
- Страница загружается без 500
- Console: 0 errors

### B4. Регрессионный тест
- Открыть страницы каталога: /catalog, /catalog/articles, /catalog/sku, /catalog/colors, /catalog/skleyki
- Все открываются без ошибок (даже если функционал ещё не доделан)

---

## Wave 0 specific

### W0.1 — БД-проверки через mcp__plugin_supabase_supabase__execute_sql

```sql
-- statusy: 6 типов
SELECT tip, count(*) FROM statusy GROUP BY tip;
-- Ожидание: model=7, artikul=3, product=6, sayt=3, color=3, lamoda=1

-- modeli_osnova: 0 без статуса
SELECT count(*) FROM modeli_osnova WHERE status_id IS NULL;
-- Ожидание: 0

-- cveta: семейство заполнено
SELECT semeystvo, count(*) FROM cveta GROUP BY semeystvo;
-- Ожидание: 5 семейств, 0 NULL

-- cveta: hex заполнен
SELECT count(*) FROM cveta WHERE hex IS NULL;
-- Ожидание: ≤30

-- kategorii: нет дубля
SELECT count(*) FROM kategorii WHERE nazvanie IN ('Леггинсы', 'Легинсы');
-- Ожидание: 1 (только «Леггинсы»)

-- Новые таблицы существуют
SELECT to_regclass('semeystva_cvetov'), to_regclass('upakovki'), to_regclass('kanaly_prodazh'), to_regclass('ui_preferences');
-- Ожидание: все 4 not null

-- Seed-данные
SELECT count(*) FROM semeystva_cvetov;  -- 5
SELECT count(*) FROM kanaly_prodazh;    -- 4
SELECT count(*) FROM upakovki;          -- 10
```

### W0.2 — RLS
```sql
SELECT tablename, count(*) AS policies
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('statusy','kategorii','kollekcii','fabriki','importery','razmery',
                    'modeli_osnova','modeli','artikuly','tovary','cveta',
                    'semeystva_cvetov','upakovki','kanaly_prodazh','sertifikaty','ui_preferences')
GROUP BY tablename;
```
- Ожидание: каждая таблица ≥4 политик (SELECT, INSERT, UPDATE, DELETE)

### W0.3 — Backups существуют
```bash
ls -la /Users/danilamatveev/Projects/Wookiee/wookiee-hub/.planning/catalog-rework/backups/wave_0/
```
- 5 файлов *.json

---

## Wave 1 specific

### W1.1 — Файлы существуют
```bash
ls src/components/catalog/ui/
# Ожидание: tooltip.tsx, level-badge.tsx, status-badge.tsx, completeness-ring.tsx,
# fields.tsx, field-wrap.tsx, columns-manager.tsx, ref-modal.tsx, bulk-actions-bar.tsx,
# command-palette.tsx
```

### W1.2 — Demo страница рендерится
- Перейти на /catalog/__demo__ (созданная A3)
- Все atomic UI отображаются корректно
- Playwright screenshot

### W1.3 — Sidebar 14 пунктов
- /catalog → визуально проверить Sidebar
- Каждый пункт имеет счётчик
- Футер с профилем «Данила · CEO»

### W1.4 — TopBar breadcrumb
- /catalog → breadcrumb «Каталог > Матрица»
- /catalog?model=Vuki → «Каталог > Матрица > Vuki»

### W1.5 — ⌘K
- На любой странице нажать ⌘K
- Палитра открывается
- Esc закрывает

### W1.6 — service.ts функции
```bash
grep -E "^export (async )?function" src/lib/catalog/service.ts | wc -l
# Ожидание: ≥30 функций
```

---

## Wave 2 specific

### W2.1 — Колонка «Статус» в матрице
- /catalog → визуально подтвердить столбец «Статус» с StatusBadge

### W2.2 — Размерная линейка chip-pills
- /catalog?model=Vuki → Tab «Описание»
- Размеры отображены как pills (XS S M L XL XXL), не plain text

### W2.3 — LevelBadge на каждом поле ModelCard
- В edit mode каждое поле имеет LevelBadge сбоку

### W2.4 — Дублирование модели работает
- Click «Дублировать», ввод нового kod
- Новая модель появляется в матрице с теми же атрибутами но без вариаций/артикулов

### W2.5 — Каскадное архивирование
- Через service или UI архивировать тестовую модель
- SQL-проверка:
```sql
SELECT m.kod, m.status_id, ms.nazvanie
FROM modeli_osnova m JOIN statusy ms ON ms.id = m.status_id
WHERE m.kod = 'TEST_CASCADE';
-- Ожидание: nazvanie = 'Архив'

SELECT count(*) FROM artikuly WHERE kod_modeli = 'TEST_CASCADE'
  AND status_id != (SELECT id FROM statusy WHERE nazvanie='Выводим' AND tip='artikul');
-- Ожидание: 0

SELECT count(*) FROM tovary t JOIN artikuly a ON a.kod = t.kod_artikula
WHERE a.kod_modeli = 'TEST_CASCADE'
  AND (t.status_id IS NULL OR t.status_id != (SELECT id FROM statusy WHERE nazvanie='Архив' AND tip='product'));
-- Ожидание: 0
```

### W2.6 — Composite search SKU
- /catalog/sku → ввести «Audrey/black/S»
- Должно вернуть SKU модели Audrey, цвета black, размера S

### W2.7 — ColumnsManager с persistence
- /catalog/sku → выключить колонку
- Refresh → колонка остаётся выключенной
- ui_preferences содержит запись scope='sku', key='columns'

### W2.8 — Bulk actions
- Выделить 3 строки → BulkActionsBar появился
- «Изменить статус» → 3 модели изменили статус (SQL-проверка)

### W2.9 — Все справочники редактируются
- /catalog/upakovki → +Добавить → новая запись → отображается
- Edit → изменить → обновлено
- Delete → исчезла

---

## Wave 3 specific

### W3.1 — Visual diff отчёт
- .planning/catalog-rework/wave_3_visual_diff.md существует
- 0 BLOCKER, 0 MAJOR (или объяснение почему остались)

### W3.2 — Functional QA отчёт
- .planning/catalog-rework/wave_3_functional_qa.md существует
- 12/12 сценариев pass

### W3.3 — Data integrity отчёт
- .planning/catalog-rework/wave_3_data_integrity.md существует
- Все RLS-проверки pass
- Cascade archive verified

### W3.4 — Финальный отчёт
- FINAL_REPORT.md существует
- Список MINOR для финального ревью

---

## Что делать при провале проверки

1. Зафиксировать результат проверки в `wave_X_failures.md`
2. Запустить fix-агента (с описанием конкретных проблем)
3. После исправления — повторить проверку
4. Если 3 итерации не помогли — остановиться, эскалировать пользователю с детальным описанием

## Чеклист перед переходом к следующей фазе

- [ ] B1-B4 базовые проверки прошли
- [ ] Все W{N}.X специфичные проверки прошли
- [ ] Создан wave_{N}_report.md
- [ ] Git: коммиты с четкими сообщениями, push в branch
- [ ] PR в main создан, review-friendly
