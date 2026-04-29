# Influencer CRM — P3 Follow-ups

> Backlog отложенных пунктов из аудита Phase 3 (2026-04-28). Не блокировали передачу в P4, но должны быть закрыты до production cutover.

**Источник:** аудит P3 plan vs actual (см. `project_influencer_crm.md` секцию "Phase 3 known issues").
**Статус P3:** DONE на ветке `feat/influencer-crm-p3` (commit `dcf2502`, 71 тест pass на живом Supabase).

---

## FU-1 — Миграция: добавить `note` в `crm.integration_metrics_snapshots`

**Контекст:** API endpoint `POST /integrations/{id}/metrics-snapshots` принимает поле `note` в теле запроса, но в реальной таблице БД эта колонка отсутствует. Сейчас data layer молча дропает значение, в ответе возвращает `source` (default `'manual'`) — контракт сохранён, но фактическое сохранение заметки невозможно.

**Что сделать:**
- [ ] Создать миграцию `database/sku/database/migrations/009_add_metrics_note.sql`:
  ```sql
  ALTER TABLE crm.integration_metrics_snapshots
    ADD COLUMN note text;
  ```
- [ ] Применить через Python wrapper (по паттерну `008_create_influencer_crm.py`)
- [ ] Удалить silent-drop в `shared/data_layer/influencer_crm/metrics.py`
- [ ] Обновить INSERT-запрос на запись `note`
- [ ] Удалить упоминание deviation в `docs/api/INFLUENCER_CRM_API.md` (раздел "Schema deviations")
- [ ] Обновить `project_influencer_crm.md` — снять пункт из known issues

**Критерий готовности:** integration test записывает note и читает его обратно через GET endpoint.

**Effort:** 1-2 часа.

---

## FU-2 — `REFRESH MATERIALIZED VIEW crm.v_blogger_totals` в conftest

**Контекст:** Materialized view `v_blogger_totals` используется на read-path для blogger detail (агрегаты integrations: count, sum cost, weighted CTR/CPM). В тестах MV не рефрешится — данные из тестовых integrations не попадают в MV до cutoff времени refresh-задачи. Сейчас тесты обходят это, не проверяя MV-зависимые поля.

**Что сделать:**
- [ ] В `tests/services/influencer_crm/conftest.py` добавить fixture-уровень cleanup:
  ```python
  @pytest.fixture(autouse=True)
  def _refresh_blogger_totals(db_session):
      yield
      db_session.execute(text("REFRESH MATERIALIZED VIEW crm.v_blogger_totals"))
      db_session.commit()
  ```
  (или ручной refresh в специфичных тестах перед assertion на агрегатах)
- [ ] Добавить тест `test_blogger_detail_aggregates_after_integration_create` — создать integration, refresh MV, проверить, что `integrations_count` и `total_cost` обновились в `GET /bloggers/{id}`
- [ ] Документировать: в проде MV рефрешится cron-ом из P5 (`REFRESH MATERIALIZED VIEW CONCURRENTLY` каждые N минут)

**Критерий готовности:** новый тест PASS, существующие 71 тест не сломаны.

**Effort:** 30 минут.

---

## FU-3 — Codex кросс-моделный review (T23 incomplete)

**Контекст:** В T23 `codex-quality-gate` упал с `ERROR: 'gpt-5.5' model requires a newer version of Codex`. Locally Codex CLI version (0.118.0) не поддерживал нужную модель. T23 завершён только Claude-only review.

**Что сделать:**
- [ ] Обновить Codex CLI: `brew upgrade openai-codex` (или соответствующий способ для текущей установки)
- [ ] Проверить версию: `codex --version` → ≥ той, что поддерживает `gpt-5.5`
- [ ] Запустить из `/tmp/wookiee-crm-p2`:
  ```bash
  /codex:review --base ad035b7 --wait
  ```
  (`ad035b7` — base commit перед началом P3)
- [ ] Сравнить findings с уже исправленными пунктами в commit `dcf2502`
- [ ] Открыть follow-up issues / коммиты для новых критических находок (если есть)

**Критерий готовности:** `0 critical findings` или все критические закрыты в feat/influencer-crm-p3 (или follow-up branch).

**Effort:** 30-60 минут (включая возможные фиксы).

---

## FU-4 — Финальный wrap-commit `chore(crm-api): Phase 3 done`

**Контекст:** Последний коммит на ветке — fix `dcf2502`, не sentinel-коммит. Косметика: помогает в `git log --grep` находить точку завершения P3 для отчётности и для последующего merge в `main`.

**Что сделать:**
- [ ] Из `/tmp/wookiee-crm-p2` на ветке `feat/influencer-crm-p3`:
  ```bash
  git commit --allow-empty -m "chore(crm-api): Phase 3 done

  - 21 endpoints across 9 routers
  - 71 tests pass on live Supabase
  - ruff clean
  - docs/api/INFLUENCER_CRM_API.md is the contract
  - 8 documented schema deviations (see project_influencer_crm.md)
  - Follow-ups tracked in docs/superpowers/plans/2026-04-28-influencer-crm-p3-followups.md
  "
  git push
  ```
- [ ] Опционально: создать tag `crm-p3-done` на этом коммите

**Effort:** 5 минут.

---

## FU-5 — N+1 detail bound: tighten ≤4 → ≤3

**Контекст:** Тест `test_get_integration_detail_n_plus_1_guard` ставит верхнюю границу 4 запроса. Реальная имплементация делает ровно 3 (main + substitute_articles + integration_posts). Slack в 1 запрос — артефакт раннего планирования; пора сжать.

**Что сделать:**
- [ ] В `tests/services/influencer_crm/test_n_plus_1.py` поменять `<= 4` на `<= 3`
- [ ] Запустить весь suite — убедиться, что не нужно объединять подзапросы

**Effort:** 15 минут.

---

## FU-6 — Тест на `marketer_id` filter в `/bloggers`

**Контекст:** В T8 (list_bloggers) реализован фильтр по `marketer_id`, но dedicated test отсутствует. Smoke gap.

**Что сделать:**
- [ ] Добавить в `tests/services/influencer_crm/test_bloggers.py`:
  - Создать 2 bloggers с разными marketer_id
  - `GET /bloggers?marketer_id=...` возвращает только одного

**Effort:** 15 минут.

---

## FU-8 — Денормализовать `blogger_handle` на `/integrations` list

**Контекст (обнаружено в P4 T12):** Фронтовый Kanban показывает карточки интеграций в виде `Блогер #N` вместо `_anna.blog`, потому что `IntegrationOut` (list payload) не содержит `blogger_handle` — он только в detail. Делать batch-fetch блогеров из UI неэффективно (N+1).

**Что сделать:**
- [ ] В `services/influencer_crm/schemas/integration.py` добавить `blogger_handle: str` в `IntegrationOut`.
- [ ] В `shared/data_layer/influencer_crm/integrations.py` SQL-запрос `list_integrations` JOIN с `crm.bloggers` и SELECT `b.display_handle AS blogger_handle`.
- [ ] Обновить тесты (smoke gap — нет проверки на denormalized handle).
- [ ] UI автоматически подхватит — снять `Блогер #${blogger_id}` placeholder в `KanbanCard.tsx`.

**Effort:** 30 минут.

---

## FU-9 — Добавить агрегаты на `/bloggers` list payload

**Контекст (обнаружено в P4 T10):** `BloggerOut` (list) не содержит `channels_count`/`integrations_count` — они только в `BloggerDetailOut`. Таблица блогеров на фронте показывает `—` в этих колонках.

**Что сделать:**
- [ ] В `services/influencer_crm/schemas/blogger.py` добавить `channels_count: int`, `integrations_count: int`, `last_integration_at: date | None` в `BloggerOut`.
- [ ] В `shared/data_layer/influencer_crm/bloggers.py` `list_bloggers` SQL — LEFT JOIN с `crm.v_blogger_totals` MV (есть с P1) или с `(SELECT count(*) FROM crm.blogger_channels WHERE blogger_id = b.id)` подзапросом.
- [ ] Тест: создать блогера с 2 каналами и 5 интеграциями, GET `/bloggers` → проверить counts.

**Effort:** 1 час.

---

## FU-10 — Расширить `/briefs` router

**Контекст (обнаружено в P4 T15):** Сейчас доступны только `POST /briefs`, `POST /briefs/:id/versions`, `GET /briefs/:id/versions`. Отсутствуют:
- `GET /briefs` (list with status filter) — нужен для Kanban-страницы брифов.
- `GET /briefs/:id` (detail с status, blogger, integration_id, current content_md) — нужен для open-existing-brief.
- `PATCH /briefs/:id` (status transitions: draft → on_review → signed → completed) — нужен для перевода стадий.

**Что сделать:**
- [ ] Добавить эндпоинты в `services/influencer_crm/routers/briefs.py`.
- [ ] Расширить `BriefOut` schema полями: `status, blogger_id, integration_id, scheduled_at, budget, updated_at`.
- [ ] Добавить тесты на каждый эндпоинт.
- [ ] UI MSW-моки сменить на real wiring.

**Effort:** 2-3 часа.

---

## FU-11 — `/products/:id` → вернуть `substitute_articles[]` halo

**Контекст (обнаружено в P4 T17):** ProductSliceCard на фронте показывает halo placeholder ("ожидает расширения BFF"), потому что `/products/:id` не возвращает связанные `substitute_articles`. Сейчас они доступны только через отдельный (несуществующий) `/substitute-articles?model_osnova_id=X` фильтр.

**Что сделать:**
- [ ] Расширить `ProductDetailOut` полем `substitute_articles: list[SubstituteArticleOut]`.
- [ ] В data layer добавить subquery/JOIN с `crm.substitute_articles`.
- [ ] UI снимет placeholder.

**Effort:** 30-60 минут.

---

## FU-12 — Добавить `tag_id` фильтр на `/integrations`

**Контекст (обнаружено в P4 T16):** Slices analytics page планировался с фильтром по тегу, но `/integrations` не принимает `tag_id`. Сейчас фильтрация по тегам возможна только через `/bloggers?tag_id=X` → `blogger_id` → `/integrations?blogger_id=...` (N+1).

**Что сделать:**
- [ ] Добавить параметр `tag_id: int | None` в `list_integrations` (data layer + router + schema).
- [ ] SQL: JOIN `crm.bloggers` с `crm.blogger_tags` (junction).
- [ ] UI добавить `tag_id` в `SlicesFilterValue`.

**Effort:** 30 минут.

---

## FU-13 — Channel `rutube` в `PlatformPill` (UI-only)

**Контекст (обнаружено в P4 T12):** `Channel` enum в BFF включает `rutube`, но `services/influencer_crm_ui/src/ui/PlatformPill.tsx` его не поддерживает (нет gradient/label). Карточки RuTube-интеграций отображаются без platform-pill (или с YouTube-стилем как fallback в T14).

**Что сделать:**
- [ ] В `PlatformPill.tsx` добавить `rutube: 'bg-[#000]'` или RuTube-цвет (#000 + красный акцент); label `'RT'`.
- [ ] Чисто визуальная задача, не блокирует функциональность.

**Effort:** 5 минут.

---

## FU-14 — Toast notifications system (UI-only)

**Контекст (отложено в P4 T11/T19):** Mutations в drawer'ах показывают inline-ошибки, но нет глобальных toast'ов для подтверждения "сохранено успешно" или "ошибка сети". Drawers закрываются после успешной мутации — пользователю не очевидно, что произошло.

**Что сделать:**
- [ ] Добавить `react-hot-toast` или собственный лёгкий toast context в `src/ui/Toast.tsx`.
- [ ] Wire через `useUpsertBlogger`, `useUpsertIntegration`, `useCreateBrief`, `useUpdateBriefStatus` — `onSuccess: () => toast.success('...')`, `onError: (e) => toast.error(...)`.

**Effort:** 1-2 часа (с кастомным компонентом — 2 часа; с lib — 30 мин).

---

## FU-15 — Combobox для blogger_id в IntegrationEditDrawer (UI polish)

**Контекст (отложено в P4 T13):** Сейчас `blogger_id` в drawer'е интеграции — numeric input. Это плохой UX: маркетолог должен помнить ID блогера. Нужен searchable combobox.

**Что сделать:**
- [ ] Добавить `cmdk` или `downshift`.
- [ ] Создать `<BloggerCombobox value onChange />` который под капотом использует `useBloggers({ q })` с debounce 300ms.
- [ ] То же для `marketer_id` (использовать `/marketers` если есть, иначе hardcoded список из 5 маркетологов).

**Effort:** 2-3 часа.

---

## FU-16 — Code-splitting (UI build optimization)

**Контекст (обнаружено в P4 T22):** `pnpm build` выдаёт warning "chunk size > 500 KB" — главный bundle 528 KB (gzip 164 KB). Не критично, но при 3G гениальное first-load.

**Что сделать:**
- [ ] В `vite.config.ts` настроить `build.rollupOptions.output.manualChunks`: разделить `vendor-react`, `vendor-tanstack`, `vendor-dnd-kit`, `vendor-headlessui`.
- [ ] Lazy-load каждый route: `const BloggersPage = React.lazy(() => import('./routes/bloggers/BloggersPage'))`.
- [ ] Suspense fallback на route-level.

**Effort:** 1 час.

---

## FU-20 — Color-contrast pass по дизайн-системе (UI a11y)

**Контекст (обнаружено в P4 Gap 1, axe-spec):** axe находит реальные WCAG-нарушения по color-contrast на бренд-цветах прототипа:
- `text-success` (#22C55E) на `bg-success/10` (#E9F9EF) → 2.08:1 (требуется 4.5:1) — Badge
- `text-white` на `bg-primary` (#F97316) → 2.8:1 (требуется 4.5:1) — primary buttons, sidebar active state
- `text-primary-hover` (#EA580C) на `bg-primary-light` (#FFF7ED) → 3.35:1 — FilterPill active state
- `text-primary` (#F97316) на `bg-bg` (#F8FAFC) → 2.67:1 — KPI values на slices/products

В axe-spec правило `color-contrast` сейчас disabled с reference на FU-20. **Не блокирует production**, но при production cutover для b2b-маркетологов с потенциальными accessibility-требованиями стоит провести design pass.

**Что сделать:**
- [ ] Заказать у дизайнера или сгенерировать через `gstack-design-consultation` ревизию палитры с поддержкой WCAG AA на всех контрастах:
  - Тёмные варианты `text-success-strong` / `text-warning-strong` / `text-info-strong` для использования над цветными светлыми bg.
  - Альтернатива: `bg-success-{darker}` (e.g., #15803D) с `text-white` для Badge — нарушает «warm minimalism» прототипа, но WCAG-чистый.
  - Primary button: либо `text-white` на более тёмном `bg-primary-darker` (e.g., #C2410C), либо использование `border + text-primary` инверсии.
- [ ] После замены color tokens — снять `disableRules(['color-contrast'])` в `e2e/golden-a11y.spec.ts` и убедиться что 7/7 routes снова PASS.
- [ ] Прокатать визуально дизайнером — не сломалась ли «refined orange minimalism» эстетика прототипа.

**Effort:** 4-6 часов на дизайн-итерацию + 2 часа на token replacement + verification.

---

## FU-7 — 400 guard для cursor + q combo

**Контекст:** В T8 docstring отмечает "list_bloggers + q + cursor: undefined behavior — use /search". Сейчас комбинация молча возвращает что-то. Лучше явный 400 вместо surprise-результатов.

**Что сделать:**
- [ ] В `services/influencer_crm/routers/bloggers.py` в начале list_bloggers:
  ```python
  if q is not None and cursor is not None:
      raise HTTPException(400, "Use /search for cursor-paginated text queries")
  ```
- [ ] Тест: `GET /bloggers?q=foo&cursor=abc` → 400

**Effort:** 10 минут.

---

## Архитектурный долг (вне follow-ups, но фиксируем)

- **Inversion `shared/data_layer/influencer_crm/` импортирует из `services/influencer_crm/`** — co-design для single-consumer BFF. Если появится второй consumer (например, второй сервис, использующий тот же data layer без FastAPI deps), вынести `schemas/`, `pagination.py` в общее место (`shared/influencer_crm_models/`).
- **pgbouncer + search_path в тестах** — `test_engine_search_path_is_crm_public` flakes на pooled connections. Не блокирует runtime (все SQL schema-qualified `crm.X`), но надо или убрать тест, или переписать против direct DSN.

---

## Где жить этому файлу

- На ветке `refactor/docs-unification` или на `main` (не на `feat/influencer-crm-p3`).
- При merge `feat/influencer-crm-p3` → `main` файл остаётся как живой backlog.
- Закрывать пункты — отдельными PR'ами с reference на FU-N.
