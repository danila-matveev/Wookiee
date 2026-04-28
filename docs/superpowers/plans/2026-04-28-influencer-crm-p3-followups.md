# Influencer CRM — P3 Follow-ups

> Backlog отложенных пунктов из аудита Phase 3 (2026-04-28). Не блокировали передачу в P4, но должны быть закрыты до production cutover.

**Источник:** аудит P3 plan vs actual (см. `project_influencer_crm.md` секцию "Phase 3 known issues").
**Статус P3:** DONE на ветке `feat/influencer-crm-p3` (commit `dcf2502`, 71 тест pass на живом Supabase).

---

## FU-1 — Миграция: добавить `note` в `crm.integration_metrics_snapshots`

**Контекст:** API endpoint `POST /integrations/{id}/metrics-snapshots` принимает поле `note` в теле запроса, но в реальной таблице БД эта колонка отсутствует. Сейчас data layer молча дропает значение, в ответе возвращает `source` (default `'manual'`) — контракт сохранён, но фактическое сохранение заметки невозможно.

**Что сделать:**
- [ ] Создать миграцию `sku_database/database/migrations/009_add_metrics_note.sql`:
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
