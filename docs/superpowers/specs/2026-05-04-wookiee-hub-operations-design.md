# Wookiee Hub — Operations Section Design

**Дата:** 2026-05-04  
**Статус:** Approved  
**Фаза:** Phase 1 (каталог + auth) → Phase 2 (телеметрия + activity feed)

---

## Контекст

`wookiee-hub` — существующее React-приложение (`wookiee-hub/`) со стеком React 19 + Tailwind v4 + Radix UI + Zustand + Supabase. Сейчас содержит раздел Community (Reviews, Questions, Answers, Analytics) и заглушки Agents (Skills, Runs).

Задача: добавить раздел **Operations** — командный дашборд всех инструментов системы Wookiee. Community остаётся нетронутым. Раздел Agents (Skills, Runs) убирается, его место занимает Operations.

**Аудитория:** команда (~5 человек), доступ по логину/паролю, без self-registration.

---

## Цели

- Команда видит все 47 тулзов системы с полными описаниями
- Каждый тулз понятен без обращения к разработчику: что делает, как работает, как запустить
- Для скиллов — исходный `.md` файл с промптом прямо в UI
- Для сервисов — как проверить health, что ожидать в логах
- Phase 2: история запусков (успешные/ошибочные), activity feed

---

## Архитектура

### Стек (без изменений)
- **Frontend:** React 19, TypeScript, Tailwind v4, Radix UI, Zustand, React Router v7
- **Backend/DB:** Supabase (существующий проект `gjvwcdtfglupewcwzfhw`)
- **Auth:** Supabase Auth (email + password)
- **Deploy:** существующий wookiee-hub deploy на `hub.wookiee.shop`

### Новые Supabase таблицы (Phase 2)
```sql
-- Phase 2: история запусков
create table tool_runs (
  id uuid primary key default gen_random_uuid(),
  tool_slug text not null references tools(slug),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null check (status in ('running', 'success', 'error')),
  triggered_by text,        -- 'cron' | 'manual' | 'skill'
  output_summary text,      -- краткий результат (1-2 предложения)
  error_message text,
  duration_ms int
);
create index on tool_runs(tool_slug, started_at desc);
```

---

## Навигация (информационная архитектура)

```
/login                          ← авторизация (без signup)
/ → redirect /operations/tools

Topbar: Community | Operations
Sidebar (Operations):
  ├── Tools Catalog [47]         /operations/tools
  ├── Activity Feed [Phase 2]    /operations/activity
  └── System Health [Phase 2]    /operations/health

Sidebar (Community — без изменений):
  ├── Reviews
  ├── Questions
  ├── Answers
  └── Analytics
```

---

## Phase 1: Страницы и компоненты

### `/login` — Авторизация

- Форма email + password
- Supabase Auth `signInWithPassword`
- Нет ссылки на signup
- После логина → redirect `/operations/tools`
- `ProtectedRoute` — обёртка на весь хаб, redirect на `/login` если нет сессии
- **Logout:** кнопка в topbar/user-menu → `supabase.auth.signOut()` → redirect `/login`

**Критичное исправление `supabase.ts`:** текущий клиент создан с `persistSession: false, autoRefreshToken: false` — сессия не переживает перезагрузку страницы. Меняем на `persistSession: true, autoRefreshToken: true`.

### `/operations/tools` — Каталог тулзов (главная страница)

**Header:**
- Заголовок "Tools Catalog"
- Subtitle: "Все инструменты системы Wookiee"

**KPI-карточки (4 штуки):**
- Всего тулзов (из `tools` таблицы)
- Активных (статус `active`)
- Запусков сегодня (Phase 2, пока "—")
- Последний запуск (Phase 2, пока "—")

**Фильтры:**
- Кнопки по категории: Все / Аналитика / Инфраструктура / Контент / Публикация / Команда / Планирование
- Поиск по `name` и `description` (клиентская фильтрация)

**Сетка тулзов:**
- 3 колонки, карточки сгруппированы по категориям
- Каждая карточка содержит:
  - `display_name` (monospace, английский) + `name_ru` (русское название)
  - Статус-точка (зелёная/жёлтая/красная)
  - `description` (2 строки, truncate)
  - Бейдж типа: Скилл / Сервис / Cron / API
  - Время последнего запуска (Phase 2, пока из `tools.last_run_at`)
- Клик → открывает Detail Panel (slide-in справа, не новая страница)

**Данные:** Supabase `tools` таблица, загрузка при mount, кеш в Zustand store.

**Маппинг в сервисном слое:** БД возвращает `display_name` — в `tools-service.ts` явно маппим на `name` для совместимости с существующим типом `Tool`. Без этого маппинга все карточки покажут `undefined`.

**Fallback для `name_ru`:** если поле `null` (до запуска populate-скрипта) — строку с русским названием не рендерим, не показываем placeholder.

### Detail Panel (правый слайд-ин)

Открывается поверх каталога при клике на карточку. Закрывается крестиком или кликом вне панели.

**Общая структура для всех типов:**
1. Заголовок: `name` (monospace) + `name_ru`
2. Бейджи: тип, статус, категория
3. **Что делает** — полное описание из `tools.description`

**Для типа `skill`:**
4. **Как работает** — пошаговое описание из `tools.how_it_works`
5. **Документация скилла** — содержимое `docs/skills/<slug>.md` (19 файлов покрывают все скиллы). Файл fetch-ится из `public/skills/<slug>.md`. Секция рендерится только если файл существует — для типов `service`, `cron`, `script` этот блок не показываем.
6. **Как запустить** — команда из `tools.run_command` (например `/finance-report`)
7. **Зависимости** — из `tools.dependencies` (массив тегов)
8. **Результат** — из `tools.output_description`
9. **История запусков** — Phase 2

**Для типа `service`:**
4. **Как работает** — пошаговое описание
5. **Как проверить** — health-check команда / endpoint из `tools.health_check`
6. **Команда запуска** — из `tools.run_command`
7. **Зависимости**
8. **Результат**
9. **Логи** — ссылка на команду для просмотра логов (`docker logs <container>` или путь к файлу)
10. **История запусков** — Phase 2

**Для типа `cron`:**
4. **Расписание** — cron expression + следующий запуск
5. **Как работает**
6. **Команда**
7. **Зависимости**
8. **История запусков** — Phase 2

---

## Phase 2: Activity Feed + Телеметрия

### Инструментирование скриптов

Все скрипты, имеющие `run_command`, при запуске пишут в `tool_runs`:
```python
# shared/telemetry.py
async def record_run(tool_slug: str, triggered_by: str = "manual"):
    # INSERT into tool_runs, returns run_id
    ...

async def finish_run(run_id: str, status: str, summary: str = None, error: str = None):
    # UPDATE tool_runs SET status, finished_at, output_summary, error_message
    ...
```

Обёртка в `scripts/` через контекстный менеджер:
```python
async with telemetry.run("finance-report", triggered_by="skill"):
    # основная логика
```

### `/operations/activity` — Activity Feed

Хронолента всех запусков:
- Аватар тулза + название
- Статус (success ✅ / error ❌ / running 🔄)
- Время запуска и длительность
- `output_summary` — краткий результат
- Ссылка "Открыть тулз" → detail panel

Данные: Supabase real-time subscription на `tool_runs`, сортировка по `started_at desc`, лимит 100.

### `/operations/health` — System Health

Сводка circuit breakers и состояния сервисов — Phase 2, дизайн отдельно.

---

## Auth детали

- Supabase Auth, таблица `auth.users` (managed by Supabase)
- Пользователей создаём через Supabase Dashboard → Authentication → Users → Invite user
- `ProtectedRoute` компонент проверяет `supabase.auth.getSession()`
- Сессия хранится в localStorage (Supabase default)
- Страница `/login`: форма email + password, кнопка "Войти", без signup ссылки
- При ошибке — показываем "Неверный логин или пароль"

---

## Данные: расширение таблицы `tools`

Реальная схема `tools` (из `scripts/generate_tools_catalog.py`):
`slug`, `display_name`, `type`, `category`, `description`, `how_it_works`, `status`, `version`, `run_command`, `data_sources`, `depends_on`, `output_targets`, `total_runs`, `last_run_at`, `last_status`, `updated_at`.

Поля `how_it_works`, `last_run_at`, `total_runs` уже существуют — не создаём повторно.

Добавляем только недостающие (migration `014_operations_hub.sql`):
```sql
alter table tools
  add column if not exists name_ru text,            -- русское название
  add column if not exists health_check text,       -- команда или URL проверки (для сервисов)
  add column if not exists output_description text, -- подробное описание результата
  add column if not exists skill_md_path text;      -- путь к .md файлу скилла (для type='skill')
```

Заполняем `name_ru` для всех 47 тулзов скриптом `scripts/populate_tools_name_ru.py`, используя данные из `docs/TOOLS_CATALOG.md`. Остальные поля уже частично заполнены.

**Маппинг полей таблицы → UI:**
| UI элемент | Поле таблицы |
|---|---|
| Название (EN) | `display_name` |
| Название (RU) | `name_ru` |
| Тип | `type` |
| Категория | `category` |
| Описание | `description` |
| Как работает (шаги) | `how_it_works` |
| Команда запуска | `run_command` |
| Зависимости | `depends_on` |
| Результат | `output_targets` + `output_description` |
| Последний запуск | `last_run_at`, `last_status`, `total_runs` |
| Health check | `health_check` |
| Промпт файл | `skill_md_path` |

---

## Раздача `.md` файлов скиллов

Для отображения промпта скилла в UI:

**Вариант A (рекомендуется для Phase 1):** Vite `import.meta.glob` — импортируем все `.md` файлы как строки при сборке. Файлы из `docs/skills/` копируются в `wookiee-hub/public/skills/`. Frontend читает `/skills/<slug>.md` через `fetch`.

**Вариант B (Phase 2):** FastAPI endpoint `/api/skills/:slug` читает файл с диска → возвращает содержимое. Нужен backend.

Используем Вариант A для Phase 1 — никакого backend не нужно.

---

## UI/UX

- **Тема:** светлая (light)
- **Цвет акцента:** `#6366f1` (indigo-500) — уже используется в wookiee-hub
- **Шрифт кода:** `ui-monospace` для `slug`/команд
- **Карточки:** border + hover shadow с indigo tint
- **Detail panel:** slide-in справа, ширина 480px, backdrop overlay
- **Фильтры:** pill-кнопки, активная — indigo background
- **Статус точки:** зелёная (`#22c55e`), жёлтая (`#f59e0b`), красная (`#ef4444`)

---

## Файловая структура (новые файлы)

```
wookiee-hub/src/
├── pages/operations/
│   ├── tools.tsx              ← Tools Catalog (главная)
│   ├── activity.tsx           ← Activity Feed (Phase 2, заглушка)
│   └── health.tsx             ← System Health (Phase 2, заглушка)
├── components/operations/
│   ├── tool-card.tsx          ← карточка тулза
│   ├── tool-detail-panel.tsx  ← правый слайд-ин
│   ├── tool-skill-viewer.tsx  ← просмотр .md файла скилла
│   ├── tool-filters.tsx       ← фильтры по категории + поиск
│   └── run-history-table.tsx  ← таблица запусков (Phase 2)
├── stores/operations.ts       ← Zustand store (tools, filters, selected)
├── lib/tools-service.ts       ← Supabase queries для tools
└── pages/auth/
    └── login.tsx              ← страница авторизации

wookiee-hub/public/skills/     ← копии .md файлов скиллов для fetch

database/migrations/
└── 014_operations_hub.sql     ← alter table tools (4 поля) + tool_runs + RLS

shared/telemetry.py            ← Phase 2: запись runs в Supabase
```

---

## Что не входит в Phase 1

- Activity Feed (данных нет — только заглушка в nav)
- System Health / Circuit Breakers
- Запуск тулзов из UI
- Real-time обновления
- Фильтрация по статусу запуска
- Телеметрия (инструментирование скриптов)

---

## Definition of Done (Phase 1)

- [ ] `/login` работает, Supabase Auth, без signup
- [ ] Protected routes — весь хаб закрыт без сессии
- [ ] `/operations/tools` — каталог загружается из Supabase, все 47 тулзов
- [ ] Фильтры по категории и поиск работают на клиенте
- [ ] Клик на карточку → detail panel с полным описанием
- [ ] Для скиллов — `.md` файл промпта отображается в панели
- [ ] Для сервисов — health check и команда логов показаны
- [ ] Community раздел работает без регрессий
- [ ] Деплой на `hub.wookiee.shop`
- [ ] Supabase migration `014_operations_hub.sql` применена (4 новых поля)
- [ ] `name_ru` заполнен для всех 47 тулзов через `scripts/populate_tools_name_ru.py`
- [ ] RLS policy на `tools` — authenticated users могут читать
