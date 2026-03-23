# Requirements: Product Matrix UX Redesign

**Defined:** 2026-03-23
**Core Value:** Централизованное управление товарной матрицей (PIM) для мультиканального fashion-бизнеса — Notion-like интерфейс вместо текущего неработающего редактора.

## v1.0 Requirements

Requirements for UX redesign milestone. Each maps to roadmap phases.

### Foundation

- [ ] **FOUND-01**: Entity registry — единый источник истины для маппинга entity keys (консолидация 4 параллельных entity maps)
- [ ] **FOUND-02**: DetailPanel корректно роутит запросы для всех типов сущностей (не только models)
- [ ] **FOUND-03**: Entity cache с update propagation — после PATCH в panel таблица автоматически обновляется

### Table View

- [ ] **TABLE-01**: Все колонки показывают человекочитаемые названия полей (не технические)
- [ ] **TABLE-02**: Reference fields (категория, фабрика, коллекция) показывают реальные значения, а не "—"
- [ ] **TABLE-03**: Статус отображается как цветной badge (Активный/Архив)
- [ ] **TABLE-04**: Пользователь может сортировать таблицу кликом на заголовок колонки (asc/desc)
- [ ] **TABLE-05**: Пагинация или "load more" вместо фиксированных 200 строк
- [ ] **TABLE-06**: Toggle видимости колонок (показать/скрыть без сохранения view)
- [ ] **TABLE-07**: Архивные строки визуально затемнены (status-based row styling)

### Detail Panel

- [ ] **PANEL-01**: Все поля ModelOsnova (~22 поля) видны в read mode, сгруппированы по секциям (Основные, Размеры, Логистика, Контент)
- [ ] **PANEL-02**: Все поля Artikul видны в read mode
- [ ] **PANEL-03**: Все поля Tovar видны в read mode с read-only маркировкой для marketplace IDs
- [ ] **PANEL-04**: Edit mode — клик по полю открывает редактор с правильным типом input (text, number, select, textarea)
- [ ] **PANEL-05**: Select-поля (категория, коллекция, фабрика, статус, цвет, размер) используют загруженные lookup options из /api/matrix/lookups/*
- [ ] **PANEL-06**: Save/Cancel кнопки с валидацией и оптимистичным обновлением
- [ ] **PANEL-07**: Read-only защита для системных полей (barkod, nomenklatura_wb, ozon_product_id, gs1, gs2)
- [ ] **PANEL-08**: Связанные сущности отображаются как кликабельные ссылки с количеством ("4 артикула" → переход к filtered view)

### CRUD Operations

- [ ] **CRUD-01**: Кнопка "+ Создать" в topbar для создания новой записи текущего типа сущности
- [ ] **CRUD-02**: Форма создания содержит required-поля и lookup select для reference fields

### Filtering & Navigation

- [ ] **FILT-01**: Фильтр по статусу (активные/архивные) в виде dropdown над таблицей
- [ ] **FILT-02**: Фильтр по категории для моделей
- [ ] **FILT-03**: Hierarchy drill-down — клик по модели → показ её артикулов в отфильтрованном виде
- [ ] **FILT-04**: Multi-field filter builder с поддержкой нескольких фильтров одновременно
- [ ] **FILT-05**: Saved views UI — сохранение и загрузка конфигурации колонок и фильтров через backend hub.saved_views

## v2 Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### Performance

- **PERF-01**: Virtual scrolling для 1000+ строк с TanStack Virtual
- **PERF-02**: Stock/finance данные в колонках таблицы через batch fetch

### Advanced UX

- **ADV-01**: Inherited field display — поля родительской сущности в detail panel потомка
- **ADV-02**: Keyboard navigation (Tab/Enter/Escape) в DetailPanel
- **ADV-03**: Quick-edit hover на ячейке таблицы для простых полей
- **ADV-04**: Breadcrumb trail в topbar (Модели > Vuki > Артикулы)

### Bulk Operations

- **BULK-01**: Bulk arbitrary field update через MassEditBar
- **BULK-02**: Bulk archive для выбранных строк

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time collaborative editing | Явный non-goal — single-brand tool, нет multi-user |
| Undo/redo в таблице | Archive/restore + audit log покрывают "oops" case |
| Drag-and-drop row reordering | Нет user-defined sort order; business logic определяет порядок |
| Bulk CSV import | One-time migration task, не recurring UX |
| Gallery/Kanban view | Не маппится на product status lifecycle; table view достаточен |
| Formula fields | Finance data из external service — дублирование создаёт расхождения |
| Notifications/activity feed | Нет user identity system (auth — будущий milestone) |
| Inline table editing для всех полей | Явно отвергнуто в UX-фидбеке — DetailPanel вместо Excel-стиля |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | — | Pending |
| FOUND-02 | — | Pending |
| FOUND-03 | — | Pending |
| TABLE-01 | — | Pending |
| TABLE-02 | — | Pending |
| TABLE-03 | — | Pending |
| TABLE-04 | — | Pending |
| TABLE-05 | — | Pending |
| TABLE-06 | — | Pending |
| TABLE-07 | — | Pending |
| PANEL-01 | — | Pending |
| PANEL-02 | — | Pending |
| PANEL-03 | — | Pending |
| PANEL-04 | — | Pending |
| PANEL-05 | — | Pending |
| PANEL-06 | — | Pending |
| PANEL-07 | — | Pending |
| PANEL-08 | — | Pending |
| CRUD-01 | — | Pending |
| CRUD-02 | — | Pending |
| FILT-01 | — | Pending |
| FILT-02 | — | Pending |
| FILT-03 | — | Pending |
| FILT-04 | — | Pending |
| FILT-05 | — | Pending |

**Coverage:**
- v1 requirements: 25 total
- Mapped to phases: 0
- Unmapped: 25 ⚠️

---
*Requirements defined: 2026-03-23*
*Last updated: 2026-03-23 after initial definition*
