# Catalog Rework — Master Index

**Статус:** APPROVED, ожидает запуска
**Создано:** 2026-05-07
**Источник правды для UI:** `/Users/danilamatveev/Projects/Wookiee/redesign + PIX/wookiee_matrix_mvp_v4.jsx` (2044 строки)
**Источник правды для данных:** Google Sheet `19Nbr0kD8JJlwd7OCIMbM9qxucYNjmXnWtwJUgXv0vlg`

## Контекст

Текущая реализация Hub-каталога (`wookiee-hub/src/pages/catalog/*`) сделана поверхностно — есть базовые таблицы, простые модалки CRUD для справочников, SkleykaCard. Но:

- В матрице нет колонки статуса
- Нет инлайн-редактирования полей модели
- Нет каскадного архивирования
- Нет ColumnsManager на реестрах артикулов/SKU
- Нет 3 справочников из MVP (Семейства цветов, Упаковки, Каналы продаж)
- Нет CommandPalette ⌘K
- Нет LevelBadge (метки на каком уровне иерархии редактируется поле)
- Нет шаблонов моделей при создании
- Нет bulk-actions (массовых действий)
- В БД: 56/56 моделей без status_id, 146/146 цветов без semeystvo, нет колонки hex, дубликаты в kategorii/kollekcii

Этот план полностью переписывает каталог в соответствии с MVP-прототипом + чинит данные в БД.

## Файлы плана

| Файл | Содержание |
|------|-----------|
| `00_README.md` | Этот файл — оглавление |
| `01_DATA_AUDIT.md` | Все DQ-проблемы в БД с фактами |
| `02_STATUSES_FROM_SHEET.md` | Реальные статусы извлечённые из Google Sheet |
| `03_GAP_LIST.md` | Полный gap-list MVP → текущая реализация |
| `04_WAVE_0_SYNC.md` | Фаза 0: синхронизация модельных статусов из Sheet |
| `05_WAVE_1_FOUNDATION.md` | Фаза 1: 4 параллельных агента (миграции, atomic UI, layout, service.ts) |
| `06_WAVE_2_PAGES.md` | Фаза 2: 6 параллельных агентов (страницы + карточки) |
| `07_WAVE_3_QA.md` | Фаза 3: end-to-end QA + screenshot diff с MVP |
| `08_EXECUTE.md` | **МАСТЕР-ПРОМПТ для запуска всех фаз** — копировать в новую сессию |
| `09_VERIFICATION_PROTOCOL.md` | Что проверять после каждой фазы |

## Как запустить

В новой сессии Claude Code (если контекст этой переполнен):

```
@/Users/danilamatveev/Projects/Wookiee/wookiee-hub/.planning/catalog-rework/08_EXECUTE.md

Прочитай файл и выполняй пошагово.
```

Или короче:

```
Открой .planning/catalog-rework/08_EXECUTE.md и запускай Wave 0.
```

## Согласование

- ✅ Схема статусов: model/artikul/product/sayt/color (5 типов)
- ✅ Дубликаты kategorii/kollekcii — мердж автоматически
- ✅ Семейства цветов — заполнить миграцией по префиксам
- ✅ Hex для 146 цветов — программный маппинг по русск/англ названию + color picker для уточнения
- ✅ Сертификаты — справочник + ссылка на Drive (не хранить в Storage)
- ✅ Дублирование = шаблоны (только modeli_osnova, без вариаций)
- ✅ Архивирование — каскадное (модель → все вниз)
- ✅ Bulk actions — реализовать (изменить статус, привязать к склейке, экспорт)
- ✅ Inline editing — везде (через editing/draft state)
- ✅ Каналы продаж — все 4 (включая Lamoda) с ColumnsManager-настройкой видимости

## Verification протокол

После КАЖДОЙ фазы:
1. TypeScript check (0 errors)
2. Lint check (0 errors)
3. Phase-specific verifications (см. в каждом файле)
4. Playwright smoke (0 console errors)
5. Если что-то не сошлось → возврат на доработку, НЕ переходить к следующей

После Wave 3 — финальный repo screenshot diff с MVP.
