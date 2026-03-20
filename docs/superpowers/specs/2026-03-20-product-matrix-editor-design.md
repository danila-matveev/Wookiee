# Product Matrix Editor — Design Spec

**Date:** 2026-03-20
**Status:** Draft
**Author:** Claude + Danila

## Problem

Управление товарной матрицей бренда Wookiee ведётся в Google Sheets (таблица спецификации). Это создаёт проблемы:
- Нет контроля доступа (все могут редактировать всё)
- Нет аудита изменений (кто и когда поменял цену)
- Нет каскадных проверок (можно удалить модель, не зная что у неё 200 SKU)
- Нет связей между данными (цвета, фабрики, сертификаты — отдельные листы)
- Нет интеграции с финансами, складом, рейтингами

## Solution

Веб-редактор товарной матрицы в Wookiee Hub — Notion-like интерфейс для управления всеми сущностями БД. FastAPI middleware между фронтом и Supabase для бизнес-логики, валидации и аудита.

## Goals

1. Полный CRUD всех сущностей товарной матрицы через веб-интерфейс
2. Notion-like система полей (Text, Number, Select, Relation, File, etc.)
3. Множественные представления данных (Спецификация, Склад, Финансы, Рейтинг)
4. Глобальный поиск по всем полям всех сущностей
5. Безопасное удаление (многофакторная проверка + архив 30 дней)
6. Admin panel для управления схемой БД и мониторинга
7. Расширяемая архитектура для будущих модулей (разработка, задачи, аналитика отзывов)

## Non-Goals

- Замена Google Sheets для финансовых расчётов (это другая система)
- Real-time collaborative editing (один пользователь — одна запись)
- Мобильная версия (desktop-first, адаптивная для планшетов)

---

## Architecture

### System Overview

```
Wookiee Hub (React)
├── Товарная матрица (/product/matrix/*) — для всех пользователей
└── Admin Panel (/system/matrix-admin/*) — только для админов
        │
        ▼
Product Matrix API (FastAPI) — services/product_matrix_api/
        │
        ▼
┌───────────────────────────┐
│ Supabase PostgreSQL       │
│ ├── public schema (товары) │ ← существующие таблицы
│ └── hub schema (UI данные) │ ← новая schema в той же БД
└────────────────────────────┘
```

**Hub данные хранятся как отдельная schema `hub` внутри той же Supabase БД** (не отдельная база). Это позволяет делать cross-schema JOIN'ы (audit_log → entity names) и использовать одно подключение. Разделение на schema даёт логическую изоляцию без накладных расходов на второй connection pool.

### Аутентификация

Используем **Supabase Auth** (email + password, без OAuth на первом этапе):
- Фронт: `@supabase/supabase-js` для login/logout → получает JWT
- FastAPI: валидирует JWT через Supabase JWKS endpoint
- Роль пользователя хранится в `hub.users.role` (viewer/editor/admin)
- `dependencies.py`: `get_current_user()` декодирует JWT, находит пользователя в `hub.users`
- Phase 1: базовая аутентификация (login + role check)
- Phase 6: гранулярные permissions (per-entity, per-field ограничения)

### Принципы

- Фронт **никогда** не обращается к Supabase напрямую для данных — только через FastAPI (Supabase Auth — исключение для login/logout)
- Вся бизнес-логика (валидация, каскады, архивирование) — на бэкенде
- Все мутации логируются в аудит лог
- Существующие triggers на `istoriya_izmeneniy` продолжают работать
- Данные из внешних источников (WB/Ozon stocks, финансы) подтягиваются через бэкенд, не хранятся в товарной матрице

---

## Database Design

### БД 1: postgres (существующая — товарная матрица)

Существующие таблицы без изменений:
- `modeli_osnova` — 22 модели основы (Vuki, Moon, Ruby, Joy, Wendy, Audrey...)
- `modeli` — 40 вариаций по юрлицам (Vuki-ИП, Vuki-ООО, VukiN, VukiN2...)
- `artikuly` — 478 артикулов (модель + цвет)
- `tovary` — 1450 SKU (артикул + размер + баркод)
- `cveta` — 137 цветов
- `fabriki` — фабрики/производители
- `importery` — импортёры (юрлица)
- `skleyki_wb`, `skleyki_ozon` — склейки маркетплейсов
- `tovary_skleyki_wb`, `tovary_skleyki_ozon` — junction tables
- `kategorii`, `kollekcii`, `statusy`, `razmery` — справочники (Select-поля)
- `istoriya_izmeneniy` — аудит изменений (triggers)

### Динамические поля (field_definitions)

Кастомные поля реализуются **через JSONB колонку `custom_fields`** на каждой таблице, а НЕ через ALTER TABLE. Это исключает необходимость DDL-привилегий у FastAPI и сохраняет стабильную schema.

Паттерн:
- Каждая таблица получает колонку `custom_fields JSONB DEFAULT '{}'`
- `field_definitions` хранит метаданные (название, тип, опции) — это реестр, не DDL
- CRUD читает/пишет значения кастомных полей через `custom_fields->>field_name`
- SQLAlchemy модели остаются статичными, кастомные поля обрабатываются generic-кодом
- Ограничения: макс. 50 кастомных полей на сущность, имена — латиница + цифры + `_`

Новые таблицы:

```sql
-- Метаданные кастомных полей (реестр, не DDL)
CREATE TABLE field_definitions (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,      -- 'modeli_osnova', 'artikuly', etc.
    field_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,     -- "Название на сайте"
    field_type VARCHAR(30) NOT NULL         -- text, number, select, multi_select,
        CHECK (field_type IN (              --  file, url, relation, date,
            'text', 'number', 'select',     --  checkbox, formula, rollup
            'multi_select', 'file', 'url',
            'relation', 'date', 'checkbox',
            'formula', 'rollup'
        )),
    config JSONB DEFAULT '{}',             -- тип-специфичная конфигурация:
                                           -- select: {options: ["A","B","C"]}
                                           -- relation: {target_table, target_field}
                                           -- formula: {expression}
                                           -- rollup: {relation_field, aggregation}
    section VARCHAR(100),                  -- группировка: "Основные", "Спецификация"
    sort_order INT DEFAULT 0,
    is_system BOOLEAN DEFAULT FALSE,       -- true = нельзя удалить/переименовать
    is_visible BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(entity_type, field_name)
);

-- Сертификаты (новая сущность)
CREATE TABLE sertifikaty (
    id SERIAL PRIMARY KEY,
    nazvanie VARCHAR(200) NOT NULL,
    tip VARCHAR(100),                      -- "ЕАС Декларация", "Сертификат качества"
    nomer VARCHAR(100),                    -- номер документа
    data_vydachi DATE,
    data_okonchaniya DATE,
    organ_sertifikacii VARCHAR(200),
    file_url TEXT,                          -- ссылка на файл документа
    gruppa_sertifikata VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Связь сертификатов с моделями (many-to-many)
CREATE TABLE modeli_osnova_sertifikaty (
    model_osnova_id INT REFERENCES modeli_osnova(id) ON DELETE CASCADE,
    sertifikat_id INT REFERENCES sertifikaty(id) ON DELETE CASCADE,
    PRIMARY KEY (model_osnova_id, sertifikat_id)
);

-- Архив мягко удалённых записей
CREATE TABLE archive_records (
    id SERIAL PRIMARY KEY,
    original_table VARCHAR(50) NOT NULL,
    original_id INT NOT NULL,
    full_record JSONB NOT NULL,             -- полный snapshot удалённой записи
    related_records JSONB DEFAULT '[]',     -- каскадно удалённые дочерние
    deleted_by VARCHAR(100),
    deleted_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP DEFAULT (NOW() + INTERVAL '30 days'),
    restore_available BOOLEAN DEFAULT TRUE
);

-- RLS для новых таблиц
ALTER TABLE field_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE sertifikaty ENABLE ROW LEVEL SECURITY;
ALTER TABLE modeli_osnova_sertifikaty ENABLE ROW LEVEL SECURITY;
ALTER TABLE archive_records ENABLE ROW LEVEL SECURITY;

-- Политики: postgres (service_role) = full, authenticated = SELECT
CREATE POLICY service_full ON field_definitions FOR ALL TO postgres USING (true) WITH CHECK (true);
CREATE POLICY auth_read ON field_definitions FOR SELECT TO authenticated USING (true);
-- (аналогично для остальных таблиц)
```

### Schema `hub` (новая — данные интерфейса, в той же Supabase БД)

```sql
CREATE SCHEMA hub;

-- Пользователи и роли
CREATE TABLE hub.users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(200) UNIQUE NOT NULL,
    name VARCHAR(200),
    role VARCHAR(20) NOT NULL DEFAULT 'viewer'
        CHECK (role IN ('viewer', 'editor', 'admin')),
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Аудит лог действий в UI
CREATE TABLE hub.audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    user_id INT REFERENCES hub.users(id),
    user_email VARCHAR(200),
    action VARCHAR(30) NOT NULL
        CHECK (action IN (
            'create', 'update', 'delete',
            'bulk_update', 'bulk_delete',
            'restore', 'login', 'export'
        )),
    entity_type VARCHAR(50),               -- 'modeli_osnova', 'cveta', etc.
    entity_id INT,
    entity_name VARCHAR(200),              -- для читаемости лога
    changes JSONB,                         -- {field: {old: X, new: Y}}
    ip_address INET,
    user_agent TEXT,
    request_id UUID,                       -- группировка массовых операций
    metadata JSONB DEFAULT '{}'
);

-- Индексы для быстрого поиска по логам
CREATE INDEX idx_audit_timestamp ON hub.audit_log(timestamp DESC);
CREATE INDEX idx_audit_user ON hub.audit_log(user_id);
CREATE INDEX idx_audit_entity ON hub.audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_action ON hub.audit_log(action);

-- Сохранённые представления таблиц (per user)
CREATE TABLE hub.saved_views (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES hub.users(id),
    entity_type VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    config JSONB NOT NULL,                 -- {
                                           --   columns: ["kod","kategoriya",...],
                                           --   filters: [{field,op,value}],
                                           --   sort: [{field,dir}],
                                           --   groupBy: "kategoriya"
                                           -- }
    is_default BOOLEAN DEFAULT FALSE,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Настройки UI пользователя
CREATE TABLE hub.ui_preferences (
    user_id INT PRIMARY KEY REFERENCES hub.users(id),
    sidebar_collapsed BOOLEAN DEFAULT FALSE,
    theme VARCHAR(10) DEFAULT 'dark',
    column_widths JSONB DEFAULT '{}',      -- {entity: {field: width}}
    sidebar_order JSONB DEFAULT '[]',
    recent_entities JSONB DEFAULT '[]',    -- последние просмотренные записи
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Уведомления — НЕ создаём сейчас, добавим когда понадобится
-- CREATE TABLE hub.notifications (...);
```

---

## Backend API Design

### Структура сервиса

```
services/product_matrix_api/
├── app.py                         — FastAPI app, CORS, error handlers
├── config.py                      — подключения к двум БД Supabase
├── dependencies.py                — auth middleware, role checks
│
├── routes/
│   ├── models.py                  — /api/matrix/models/*
│   ├── articles.py                — /api/matrix/articles/*
│   ├── products.py                — /api/matrix/products/*
│   ├── colors.py                  — /api/matrix/colors/*
│   ├── factories.py               — /api/matrix/factories/*
│   ├── importers.py               — /api/matrix/importers/*
│   ├── cards.py                   — /api/matrix/cards/* (склейки)
│   ├── certs.py                   — /api/matrix/certs/*
│   ├── search.py                  — /api/matrix/search
│   ├── schema.py                  — /api/matrix/schema/* (admin)
│   ├── archive.py                 — /api/matrix/archive/*
│   └── admin.py                   — /api/matrix/admin/* (логи, stats)
│
├── services/
│   ├── crud.py                    — generic CRUD для всех сущностей
│   ├── validation.py              — каскадные проверки
│   ├── archive_service.py         — soft delete + restore + cron cleanup
│   ├── search_service.py          — cross-entity full-text search
│   ├── field_service.py           — управление кастомными полями
│   ├── audit_service.py           — запись в hub.audit_log
│   └── external_data.py           — подтягивание данных из WB/Ozon/финансов
│
└── models/
    ├── schemas.py                 — Pydantic модели (request/response)
    └── database.py                — SQLAlchemy engines для обеих БД
```

### API Endpoints

#### CRUD (одинаковый паттерн для каждой сущности)

```
GET    /api/matrix/{entity}                  — список
  Query params:
    view=spec|stock|finance|rating           — режим представления
    filter[field]=value                      — фильтрация
    sort=field:asc|desc                      — сортировка
    group_by=field                           — группировка
    search=query                             — поиск внутри сущности
    page=1&per_page=50                       — пагинация
    expand=children                          — включить дочерние

GET    /api/matrix/{entity}/{id}             — одна запись
  Query params:
    include=children,colors,certs            — связанные данные

POST   /api/matrix/{entity}                  — создание
  Body: {field: value, ...}
  Response: created record with id

PATCH  /api/matrix/{entity}/{id}             — обновление
  Body: {field: new_value, ...}
  Response: updated record
  Side effect: audit_log entry

DELETE /api/matrix/{entity}/{id}             — мягкое удаление
  Step 1 (без X-Confirm-Challenge):
    Response 428: {
      requires_confirmation: true,
      challenge: "27 × 3",
      expected_hash: "sha256(81+salt)",
      impact: {children: [...counts...], message: "..."}
    }
  Step 2 (с X-Confirm-Challenge: "81"):
    Response 200: {archived: true, expires_at: "..."}
  Side effect: archive_records entry + audit_log

POST   /api/matrix/{entity}/bulk             — массовые операции
  Body: {
    ids: [1, 2, 3],
    action: "update" | "delete",
    changes: {field: new_value}              — для update
  }
```

#### Глобальный поиск

```
GET /api/matrix/search?q=vuki&limit=20

Response: {
  results: [
    {entity: "modeli_osnova", id: 1, name: "Vuki", match_field: "kod", match_text: "Vuki"},
    {entity: "artikuly", id: 15, name: "Vuki/2", match_field: "artikul", match_text: "Vuki/2"},
    {entity: "tovary", id: 101, name: "4670437802315", match_field: "barkod", match_text: "..."},
  ],
  total: 45,
  by_entity: {modeli_osnova: 1, artikuly: 13, tovary: 31}
}
```

Реализация: PostgreSQL full-text search с `tsvector` индексами по ключевым полям каждой таблицы.

#### Управление полями (admin only)

```
GET    /api/matrix/schema/{entity}           — все поля сущности
POST   /api/matrix/schema/{entity}/fields    — создать поле
  Body: {field_name, display_name, field_type, config, section}
  Side effect: INSERT в field_definitions (данные хранятся в JSONB custom_fields)
PATCH  /api/matrix/schema/{entity}/fields/{id}  — обновить поле
DELETE /api/matrix/schema/{entity}/fields/{id}  — удалить поле (с проверкой)
```

#### Архив

```
GET    /api/matrix/archive                   — список удалённых
  Query: entity_type, date_from, date_to
POST   /api/matrix/archive/{id}/restore      — восстановить запись
DELETE /api/matrix/archive/{id}              — удалить навсегда (admin)
```

#### Admin

```
GET    /api/matrix/admin/logs                — аудит лог
  Query: user_id, entity_type, action, date_from, date_to
GET    /api/matrix/admin/stats               — статистика БД
GET    /api/matrix/admin/health              — здоровье подключений
```

### Soft Delete и FK Constraints

**Стратегия:** Удаление = soft delete (перенос snapshot в `archive_records`), НЕ физическое удаление. Это обходит FK constraints — запись остаётся в таблице с `status_id` = "Архив" (id=3 в `statusy`), а полный snapshot сохраняется в `archive_records` для возможности восстановления.

**Миграция FK:** Существующие FK constraints НЕ меняются (нет `ON DELETE CASCADE`). Вместо этого:
1. При "удалении" модели: бэкенд проверяет дочерние записи
2. Если есть активные дочерние — показывает impact и предлагает каскадно архивировать
3. Архивирование = `UPDATE status_id = 3 (Архив)` для всех затронутых записей + snapshot в `archive_records`
4. Восстановление = `UPDATE status_id` обратно + удаление из `archive_records`
5. Физическое удаление (только из admin panel) проходит снизу вверх: сначала tovary, потом artikuly, потом modeli, потом modeli_osnova — чтобы не нарушать FK

**Для справочников (cveta, fabriki)** — нельзя архивировать если есть активные артикулы/модели. Сначала нужно переназначить или архивировать зависимые записи.

```python
# services/validation.py

CASCADE_RULES = {
    "modeli_osnova": {
        "strategy": "cascade_archive",  # архивировать каскадно
        "children": [
            {"table": "modeli", "fk": "model_osnova_id",
             "children": [
                 {"table": "artikuly", "fk": "model_id",
                  "children": [
                      {"table": "tovary", "fk": "artikul_id"}
                  ]}
             ]}
        ]
    },
    "cveta": {
        "strategy": "block_if_active",   # блокировать если есть активные зависимые
        "dependents": [
            {"table": "artikuly", "fk": "cvet_id", "active_check": "status_id != 3"}
        ]
    },
    "fabriki": {
        "strategy": "block_if_active",
        "dependents": [
            {"table": "modeli_osnova", "fk": "fabrika_id", "active_check": "status_id != 3"}
        ]
    }
}

async def check_delete_impact(entity_type: str, entity_id: int) -> DeleteImpact:
    """Рекурсивно считает сколько записей затронет архивирование."""
    ...
```

### Уровни доступа

```python
# dependencies.py

class Role(str, Enum):
    VIEWER = "viewer"    # GET only
    EDITOR = "editor"    # GET + POST + PATCH + DELETE (кроме модели основы)
    ADMIN = "admin"      # всё + admin panel + schema management

def require_role(minimum: Role):
    """FastAPI dependency для проверки роли."""
    async def checker(user = Depends(get_current_user)):
        if user.role_level < minimum.level:
            raise HTTPException(403, "Insufficient permissions")
        return user
    return checker

# Использование:
@router.delete("/models/{id}", dependencies=[Depends(require_role(Role.ADMIN))])
async def delete_model(id: int): ...

@router.patch("/models/{id}", dependencies=[Depends(require_role(Role.EDITOR))])
async def update_model(id: int, body: ModelUpdate): ...
```

---

## Frontend Design

### Технологии

- React 19 + TypeScript (существующий стек wookiee-hub)
- Tailwind CSS + shadcn/ui (существующая дизайн-система)
- Zustand (state management, как в остальном hub)
- Существующий `useApiQuery` hook + `api-client.ts`
- Виртуализация таблиц для 1000+ строк (@tanstack/react-table)

### Роутинг

```
/product/matrix                         → redirect to /product/matrix/models
/product/matrix/models                  → ModelsPage
/product/matrix/articles                → ArticlesPage
/product/matrix/products                → ProductsPage
/product/matrix/colors                  → ColorsPage
/product/matrix/factories               → FactoriesPage
/product/matrix/importers               → ImportersPage
/product/matrix/cards-wb                → CardsWbPage
/product/matrix/cards-ozon              → CardsOzonPage
/product/matrix/certs                   → CertsPage
/product/matrix/:entity/:id             → EntityDetailPage (full page)

/system/matrix-admin                    → redirect to schema
/system/matrix-admin/schema             → SchemaExplorerPage
/system/matrix-admin/api                → ApiExplorerPage
/system/matrix-admin/logs               → AuditLogPage
/system/matrix-admin/archive            → ArchiveManagerPage
/system/matrix-admin/stats              → DbStatsPage
```

### Компоненты

#### Layout

- `MatrixShell` — обёртка: sidebar + main content + detail panel (slide-in)
- `MatrixSidebar` — навигация по сущностям с счётчиками записей
- `MatrixTopbar` — заголовок сущности, кнопка глобального поиска, "Настроить поля"

#### Таблица (DataTable)

Generic компонент `DataTable<T>` — ядро всего интерфейса:

- Принимает: `columns`, `data`, `loading`, `onSort`, `onFilter`, `onRowSelect`, `onCellEdit`
- Sticky header, фиксированная сетка колонок (`table-layout: fixed`)
- Inline editing: клик по ячейке → input/select/datepicker в зависимости от типа поля
- Expand/collapse для вложенных строк (модели основы → подмодели)
- Checkbox selection + MassEditBar
- Виртуализация для больших списков
- "+ Новая запись" строка внизу
- "+" кнопка для добавления колонки

Типы ячеек (`TableCell`):
- `text` → inline text input
- `number` → input[number] с форматированием
- `select` → dropdown (категория, статус, коллекция)
- `multi_select` → multi-dropdown
- `relation` → clickable link → переход к связанной записи
- `rollup` → read-only computed значение (count, sum)
- `file` → thumbnail + upload
- `url` → clickable link
- `date` → date picker
- `checkbox` → toggle
- `formula` → read-only computed

#### Представления (ViewTabs)

Табы сверху таблицы — режимы данных:

| Таб | Показывает | Источник |
|-----|-----------|----------|
| Спецификация | Товарные характеристики (материал, вес, размеры, упаковка) | Supabase |
| Склад | Остатки WB/Ozon, в пути, дней запаса | WB/Ozon API через бэкенд |
| Финансы | Выручка, маржа, DRR, заказы, ABC | pbi_wb/ozon через data_layer |
| Рейтинг | Рейтинг, отзывы, средняя оценка | WB/Ozon API |
| + Создать вид | Кастомный набор колонок + фильтров | hub.saved_views |

#### Detail Panel / Detail Page

Боковая панель (slide-in при клике на строку):
- Summary cards (подмодели, цвета, артикулы, SKU)
- Фото галерея с drag-and-drop загрузкой
- Все поля сущности, организованные по секциям
- Каждое поле с hover-border показывающим что оно editable
- Поля унаследованные с верхнего уровня (модель → артикул) = read-only с пометкой
- Связи (подмодели, цвета, сертификаты) как кликабельные списки
- Кнопка "↗" раскрывает в полную страницу

Полная страница (`/product/matrix/:entity/:id`):
- Те же данные что в панели, но шире
- Табы: Информация / Финансы / Рейтинг / Задачи
- Таб "Информация" = те же поля что в панели
- Таб "Финансы" = графики выручки, маржи, динамика (будущее)
- Таб "Рейтинг" = отзывы, рейтинг по площадкам (будущее)
- Таб "Задачи" = привязанные задачи (будущее)

#### Поиск

`GlobalSearch` (Cmd+K):
- Input с debounce 300ms
- Запрос `GET /api/matrix/search?q=...`
- Результаты группируются по типу сущности
- Клик → переход к записи
- Подсветка совпадений в тексте

#### Удаление

Двухшаговый процесс:
1. `DeleteConfirmDialog` — "Вы уверены? Будут архивированы: 4 подмодели, 52 артикула, 208 SKU"
2. `DeleteChallengeDialog` — "Решите: 27 × 3 = ?" → ввод ответа → DELETE с X-Confirm-Challenge
3. Запись уходит в архив на 30 дней, можно восстановить из admin panel

#### Управление полями

- Кнопка "Настроить поля" → dialog с drag-and-drop списком полей
- Для каждого поля: название, тип, видимость, порядок
- "+ Добавить поле" → выбор типа → название → API создаёт колонку в БД
- Для select-полей: inline-редактирование опций (добавить/удалить/переименовать)

### Admin Panel

- `SchemaExplorer` — таблицы, колонки, типы данных, связи. Визуальное представление структуры БД. Можно добавить/изменить/удалить поля.
- `ApiExplorer` — список всех эндпоинтов с описанием, параметрами, возможностью отправить тестовый запрос и увидеть ответ (мини-Swagger).
- `AuditLogTable` — лог: timestamp, user, action, entity, changes (diff). Фильтры по пользователю, сущности, дате, типу действия.
- `ArchiveManager` — список удалённых записей. Действия: восстановить, удалить навсегда. Показывает expires_at, каскадно удалённые дочерние.
- `DbStatsCards` — метрики: записей в каждой таблице, рост за неделю/месяц.

---

## Вложенность модели основа → подмодели

Модели основы (modeli_osnova) и модели (modeli) объединены в один вид таблицы:

- Каждая строка = модель основа (Vuki, Moon, Ruby...)
- Стрелка expand (▸/▾) у моделей с подмоделями
- Клик → разворачивает вложенные строки подмоделей (Vuki ИП, VukiN ИП, Vuki2 ООО...)
- Модели без подмоделей (Audrey) — плоские, без стрелки
- Вложенные строки показывают: название подмодели, badge юрлица (ИП/ООО), импортёр, статус, count артикулов и SKU
- Поля модели основы (категория, коллекция, фабрика) не дублируются в подмоделях

### Цена по размерам

**Источник ценовых данных:** Цены НЕ хранятся в товарной матрице. Они подтягиваются из внешних источников (WB API, Ozon API, МойСклад) через бэкенд в реальном времени при запросе вида "Финансы". В будущем, если потребуется хранить целевые/рекомендуемые цены — добавим таблицу `target_prices` (model_osnova_id, razmer_id, price, currency).

Для трикотажной коллекции (Vuki, Moon, Ruby, Joy) — цена зависит от размера:
- В detail panel: сетка S/M/L/XL с индивидуальной ценой (read-only, из API)
- В таблице (вид "Финансы"): показывается диапазон "890–1090 ₽"

Для бесшовной коллекции (Wendy, Audrey) — единая цена:
- В detail panel: одно поле "Цена" без разбивки
- Определяется по `tip_kollekcii` модели основы

---

## Deployment

```yaml
# docker-compose.yml — новый сервис
product-matrix-api:
  build: .
  command: uvicorn services.product_matrix_api.app:app --host 0.0.0.0 --port 8002
  env_file: .env
  ports:
    - "8002:8002"
  depends_on:
    - wookiee-oleg  # для shared config
```

Фронтенд: новые роуты в существующем wookiee-hub, деплоится как часть билда.

Vite proxy:
```typescript
// vite.config.ts — добавить
'/api/matrix': { target: 'http://localhost:8002' }
```

---

## Implementation Phases

### Phase 1: Backend Foundation
- FastAPI сервис с подключением к обеим БД
- CRUD эндпоинты для modeli_osnova и modeli
- Аудит лог
- Базовая аутентификация

### Phase 2: Frontend Core
- MatrixShell, MatrixSidebar
- DataTable с inline editing для моделей
- Detail panel
- Вложенность модели основа → подмодели

### Phase 3: All Entities
- CRUD для всех остальных сущностей (артикулы, товары, цвета, фабрики, импортёры, склейки, сертификаты)
- Глобальный поиск
- Mass editing

### Phase 4: Views & Fields
- Табы-представления (Спецификация, Склад, Финансы, Рейтинг)
- Система кастомных полей (field_definitions + UI)
- Saved views

### Phase 5: Safety & Admin
- Двухшаговое удаление с challenge
- Архив удалённых записей
- Admin panel (Schema, API, Logs, Archive, Stats)

### Phase 6: Integration & Polish
- Подтягивание данных из WB/Ozon (склад, финансы, рейтинг)
- Полная страница записи с табами
- Уровни доступа (viewer/editor/admin)
- Export (CSV, Excel)
