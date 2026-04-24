# Docs Audit — Refactor v3 Phase 1

**Agent:** `audit-docs` (read-only)
**Date:** 2026-04-24
**Scope:** `docs/`, root-level `.md` (README, AGENTS, CLAUDE, CONTRIBUTING, SECURITY), `.planning/`, `.superpowers/`
**Source spec:** `docs/superpowers/specs/2026-04-24-refactor-v3-design.md` §6

---

## 1. Summary

| Bucket | Count |
|---|---|
| Total `.md` files in scope | **279** |
| — `docs/` tree | 188 (including archive, reports, superpowers plans/specs) |
| — root-level `.md` | 5 (README, AGENTS, CLAUDE, CONTRIBUTING, SECURITY) |
| — `.planning/` | 86 (+ superpowers .server-stopped logs) |
| KEEP (minor touch only) | 39 |
| UPDATE (needs non-trivial edits) | 18 |
| ARCHIVE (move to `docs/archive/`) | 38 |
| DELETE (outright remove) | ~140 (bulk: `.planning/archive`, `.planning/milestones`, `.planning/phases`, `.planning/research`, `.superpowers/brainstorm`, stale `docs/future/`, superseded specs) |
| CREATE (new per spec §6) | 26 (1 ONBOARDING + 14 skill docs + 8 service READMEs + 1 agents scaffold README + 1 archive oleg v2 doc + 1 PR template) |
| Broken internal links | **24** distinct broken targets |
| Active mentions of Oleg/Lyudmila/Vasily | **README.md, AGENTS.md, docs/index.md, docs/system.md, docs/architecture.md, docs/PROJECT_MAP.md, docs/QUICKSTART.md, docs/guides/environment-setup.md, docs/agents/README.md, docs/agents/telegram-bot.md, docs/agents/analytics-engine.md, docs/agents/ibrahim.md, docs/agents/mp-localization.md, docs/agents/bitrix-crm.md, docs/agents/wb-sheets-sync-plan.md, docs/adr.md, docs/development-history.md, docs/infrastructure.md, docs/database/*, docs/plans/*, docs/future/agent-ops-dashboard/**, docs/workflows/*.html, docs/superpowers/plans/*, docs/superpowers/specs/*, docs/archive/agents/vasily/**, docs/archive/retired_agents/lyudmila/**, docs/archive/plans/lyudmila-*** (many files — see §8) |

**Verdict headline:** документация тяжело устарела по трём осям: (1) Oleg/Lyudmila/Vasily всё ещё описаны как активные; (2) половина `services/*` путей в картах проекта уже не существует (`services/marketplace_etl/`, `services/vasily_api/`, `services/etl/`, `services/dashboard_api/`, `services/product_matrix_api/`, `services/knowledge_base/` — всё упоминается как активное, физически отсутствует в `services/`); (3) `docs/index.md` не содержит ни одного из 27 актуальных скиллов (`finance-report`, `marketing-report`, `daily-brief`, `funnel-report`, `logistics-report`, `abc-audit`, `market-review`, `analytics-report`, `reviews-audit`, `monthly-plan`, `finolog-dds-report`, `content-search`, `tool-status`, `tool-register`). Требуется полный rewrite `index.md`, `architecture.md`, `README.md`, `AGENTS.md`, `QUICKSTART.md`, `PROJECT_MAP.md`, `system.md` + удаление/архивация всей `docs/agents/*` и `docs/future/agent-ops-dashboard/`.

---

## 2. Target `docs/` structure — diff vs current (tree-diff)

Из spec §6.1:

```
  / (repo root)
  ├── README.md                                 [UPDATE — полностью переписать]
+ ├── ONBOARDING.md                             [NEW]
  ├── AGENTS.md                                 [UPDATE]
  ├── CLAUDE.md                                 [KEEP — маленький, 21 строка]
  ├── CONTRIBUTING.md                           [UPDATE — переписать под PR-workflow v3]
  ├── SECURITY.md                               [UPDATE — таблица секретов частично устарела]
  │
  └── docs/
      ├── index.md                              [UPDATE — полный rewrite: 27 скиллов + 8 сервисов]
      ├── architecture.md                       [UPDATE — убрать vasily_api, marketplace_etl, lyudmila]
      ├── infrastructure.md                     [UPDATE — актуализировать список контейнеров]
      ├── adr.md                                [KEEP — добавить ADR-008 про refactor-v3]
-     ├── PROJECT_MAP.md                        [DELETE — полностью устарел, v2/oleg/vasily centric]
-     ├── QUICKSTART.md                         [DELETE — заменяется на ONBOARDING.md]
-     ├── system.md                             [DELETE — описывает несуществующий Oleg pipeline]
-     ├── TOOLS_CATALOG.md                      [KEEP — автогенерируется из Supabase, в порядке]
-     ├── abc_analysis_playbook.md              [ARCHIVE → docs/archive/]
-     ├── logistics-audit-algorithm-v2.md       [KEEP — актуальная документация /logistics-audit]
-     ├── logistics-audit-methodology-v2.md     [KEEP — актуальная документация /logistics-audit]
-     ├── development-history.md                [UPDATE — обрезать до последних 10 записей per шаблон]
+     ├── skills/                               [NEW dir — один .md на активный скилл]
+     │   ├── finance-report.md                 [NEW]
+     │   ├── marketing-report.md               [NEW]
+     │   ├── daily-brief.md                    [NEW]
+     │   ├── funnel-report.md                  [NEW]
+     │   ├── logistics-report.md               [NEW]
+     │   ├── abc-audit.md                      [NEW]
+     │   ├── market-review.md                  [NEW]
+     │   ├── analytics-report.md               [NEW]
+     │   ├── reviews-audit.md                  [NEW]
+     │   ├── monthly-plan.md                   [NEW]
+     │   ├── finolog-dds-report.md             [NEW]
+     │   ├── content-search.md                 [NEW]
+     │   ├── tool-status.md                    [NEW]
+     │   └── tool-register.md                  [NEW]
+     ├── services/                             [NEW dir — по одному .md на сервис (или ссылка на services/<name>/README.md)]
      ├── agents/                               [DELETE ENTIRE DIR → содержимое stale, заменяется skills/]
-     │   ├── README.md                         [DELETE — описывает 4 несуществующих агента]
-     │   ├── analytics-engine.md               [DELETE — ссылается на agents/oleg/services/price_analysis]
-     │   ├── bitrix-crm.md                     [ARCHIVE]
-     │   ├── ibrahim.md                        [DELETE — агент удалён/архивирован]
-     │   ├── mp-localization.md                [UPDATE → перенести в docs/services/wb_localization.md]
-     │   ├── telegram-bot.md                   [DELETE — Oleg Telegram runtime удалён]
-     │   └── wb-sheets-sync-plan.md            [ARCHIVE — старый план до сервиса]
      ├── database/                             [KEEP — справочник актуален]
      │   ├── DB_METRICS_GUIDE.md               [KEEP]
      │   ├── DB_QUESTIONS_FOR_DEVELOPER.md     [KEEP]
      │   ├── DATABASE_REFERENCE.md             [KEEP]
      │   ├── DATABASE_WORKPLAN.md              [KEEP]
      │   ├── DATA_QUALITY_NOTES.md             [KEEP — критичный живой док]
      │   ├── KTR_SYNC_VERIFICATION.md          [KEEP]
      │   └── rules.md                          [KEEP]
      ├── guides/                               [KEEP в основном]
      │   ├── dod.md                            [KEEP]
      │   ├── environment-setup.md              [UPDATE — убрать vasily_api reqs, добавить wb_logistics_api]
      │   ├── logging.md                        [UPDATE — удалить упоминания Oleg runtime]
      │   ├── agent-principles.md               [KEEP]
      │   └── archiving-and-temp.md             [KEEP]
-     ├── future/                               [DELETE ENTIRE DIR]
-     │   └── agent-ops-dashboard/              [DELETE — Oleg v2 dashboard, мертв]
      ├── scripts/                              [KEEP — документация скриптов]
      │   └── search-queries-sync.md            [KEEP]
      ├── content-kb/                           [KEEP — актуальный сервис]
      │   └── README.md                         [KEEP]
-     ├── plans/                                [MOSTLY ARCHIVE/DELETE]
-     │   ├── ibrahim-deploy-and-etl.md         [DELETE — агент удалён]
-     │   ├── oleg-v2-rebuild.md                [ARCHIVE → docs/archive/plans/]
-     │   ├── 2026-02-25-*.md (3 файла)         [ARCHIVE]
-     │   ├── 2026-04-business-plan*.md (3)     [ARCHIVE → актуальные business плановые отчёты]
-     │   ├── 2026-04-verification*.md (2)      [DELETE — одноразовые]
-     │   ├── MONTHLY-PLAN-PROCESS.md           [KEEP]
-     │   └── MONTHLY-PLAN-TECHNICAL-SPEC.md    [KEEP]
      ├── reports/                              [KEEP — сгенерированные отчёты, живая история]
      ├── workflows/                            [UPDATE — удалить oleg/vasily HTML, держать system-architecture]
-     │   ├── oleg-report-pipeline.html         [DELETE]
-     │   ├── vasily-localization-pipeline.html [DELETE]
-     │   ├── ibrahim-etl-flow.html             [DELETE]
-     │   ├── agent-system-architecture.html    [DELETE — устарело]
-     │   ├── _template.html                    [KEEP]
-     │   ├── wb-logistics-audit-pipeline.html  [KEEP]
-     │   ├── wookiee-reporting-system.html     [KEEP, проверить]
-     │   └── system-architecture.html          [UPDATE — актуализировать]
      ├── templates/                            [KEEP]
      ├── superpowers/                          [KEEP как есть, PURGE stale]
      │   ├── specs/                            [PURGE старые: см. §3]
      │   └── plans/                            [PURGE старые: см. §3]
      └── archive/                              [KEEP — здесь увеличиваем наполнение]
+         └── oleg-v2-architecture.md           [NEW — знаниевый конспект перед удалением agents/oleg]
```

---

## 3. DELETE list

| Путь | Причина |
|---|---|
| `docs/PROJECT_MAP.md` | Полностью устарел: описывает Oleg v2 архитектуру, Vasily API, 4 агента, 3-container Docker, ARCHIVE oleg/playbook.md 115KB. Заменяется новым `docs/index.md` + `README.md`. |
| `docs/QUICKSTART.md` | Ссылается на `services/vasily_api/requirements.txt` (не существует), `python -m agents.oleg` (удаляется). Заменяется `ONBOARDING.md`. |
| `docs/system.md` | Описывает несуществующий Oleg pipeline (7 шагов, ReAct loop, Reporter/Marketer/Funnel/Advisor/Validator агенты). Все ссылки мёртвые после рефакторинга. |
| `docs/agents/README.md` | Перечисляет Oleg+ETL+WB Localization+Analytics Engine с неверными путями (`agents/oleg/services/` и `services/etl/` — второго нет). |
| `docs/agents/analytics-engine.md` | Ссылается на `agents/oleg/services/price_analysis/*` (удаляется вместе с Oleg). |
| `docs/agents/telegram-bot.md` | Oleg Telegram runtime удаляется; файл бесполезен. |
| `docs/agents/ibrahim.md` | Ибрагим агент отсутствует в `agents/` (есть только `agents/oleg/` и `agents/finolog_categorizer/` в spec'е к удалению). |
| `docs/plans/ibrahim-deploy-and-etl.md` | Ибрагим удалён. |
| `docs/plans/2026-04-verification-prompt.md` | Одноразовый промпт для верификации. |
| `docs/plans/2026-04-verification-v2-prompt.md` | Одноразовый промпт. |
| `docs/future/agent-ops-dashboard/` (вся директория — 8 файлов) | Spec §3.2 помечает как «переносится в новый модуль Hub или archive» — reviews/ устарели (Oleg v2 агенты), мокапы не используются. В spec'е явно предлагается archive/delete. |
| `docs/workflows/oleg-report-pipeline.html` | Oleg удаляется. |
| `docs/workflows/vasily-localization-pipeline.html` | Vasily удалён. |
| `docs/workflows/ibrahim-etl-flow.html` | Ибрагим удалён. |
| `docs/workflows/agent-system-architecture.html` | Дубликат system-architecture.html + описывает мёртвую архитектуру. |
| `.planning/archive/v1.0/` (вся дир, ~40 файлов) | Cleanup-v2 §2.6 прямо помечает к удалению. Hub product-matrix устаревший. |
| `.planning/milestones/v2.0-*` (вся дир, ~35 файлов) | Cleanup-v2 §2.6. |
| `.planning/phases/` (вся дир, ~50 файлов) | Дубликаты `.planning/milestones/v2.0-phases/`. Устаревший product-matrix workstream. |
| `.planning/research/` (5 файлов: ARCHITECTURE, FEATURES, PITFALLS, STACK, SUMMARY) | Cleanup-v2 §2.6 помечает к удалению (product-matrix старый research). |
| `.planning/debug/` (4 файла) | Разовые разборы решённых инцидентов (notification-double-send, telegram-conflict-error, logistics-report-not-running, weekly-dds-failure). В `.gitignore` или archive. |
| `.superpowers/brainstorm/` (обе сессии: 34593-1774021019, 41345-1777051151 — HTMLs + server pid/logs) | Cleanup-v2 §2.6 + §3. Кэш brainstorm-сессий. |
| `docs/superpowers/specs/2026-03-19-multi-agent-redesign.md` | Cleanup-v2 §2.6 прямо. V3 LangGraph удалена. |
| `docs/superpowers/specs/2026-03-21-smart-conductor-design.md` | Cleanup-v2 §2.6. |
| `docs/superpowers/specs/2026-03-25-vasily-localization-full-description.md` | Cleanup-v2 §2.6. Vasily удалён. |
| `docs/superpowers/specs/2026-04-03-project-restructuring-design.md` | Superseded by `2026-04-13-project-cleanup-v2-design.md`, тот superseded by `2026-04-24-refactor-v3-design.md`. |
| `docs/superpowers/plans/2026-04-03-project-restructuring.md` | Same reason. |
| `docs/superpowers/plans/2026-03-21-advisor-agent-plan.md`, `-phase2..5-plan.md` (5 файлов) | Advisor agent (часть Oleg v2) удаляется. |
| `docs/superpowers/plans/2026-03-21-product-matrix-*.md` (6 файлов) | product-matrix-editor удалён (`services/product_matrix_api` в spec к удалению). |
| `docs/superpowers/plans/2026-03-20-product-matrix-*.md` (2 файла) | Same. |
| `docs/superpowers/specs/2026-03-20-product-matrix-editor-design.md` | Same. |
| `docs/superpowers/specs/2026-03-21-product-matrix-phase6-design.md` | Same. |
| `docs/superpowers/plans/2026-03-21-advisor-phase2-activation-plan.md`..`phase5-plan.md` | Advisor / Oleg v2. |
| `docs/superpowers/specs/2026-03-21-advisor-*.md` (5 файлов) | Same. |
| `docs/superpowers/plans/2026-03-28-reporter-v4-plan.md` / specs `reporter-v4-design.md` | Reporter — часть Oleg. |
| `docs/superpowers/plans/2026-03-28-notification-spam-fix-plan.md` | Одноразовый fix для Oleg watchdog. |
| `docs/superpowers/plans/2026-03-19-multi-agent-phase1-mcp-and-observability.md` | MCP-серверы удаляются, observability переименовывается. |
| `docs/superpowers/specs/2026-03-21-content-knowledge-base-design.md` | Сервис жив, но early design устарел — в `services/content_kb/README.md` есть актуальная дока. |
| `docs/superpowers/plans/2026-03-21-content-knowledge-base.md` | Same. |
| `docs/superpowers/plans/2026-03-21-trust-envelope-and-cost-tracking.md` + spec | Oleg v2 feature. |
| `docs/superpowers/plans/2026-03-22-telegram-ux-cleanup-plan.md` + spec | Oleg Telegram-runtime удаляется. |
| `docs/superpowers/plans/2026-03-21-smart-conductor-plan.md` | Conductor удалён. |
| `docs/superpowers/plans/2026-03-21-report-templates-stabilization.md` + spec | Oleg templates. |
| `docs/superpowers/plans/2026-03-18-comms-live-api.md` + spec | Неиспользуемый draft (hub модуль Comms trimmed). |
| `docs/superpowers/specs/2026-04-07-sports-research-design.md` | Off-scope, draft. |
| `docs/superpowers/specs/2026-04-07-familia-eval-design.md` + plan `2026-04-07-familia-eval-plan.md` | Одноразовый eval, выполнен. |
| `docs/superpowers/plans/2026-04-06-ozon-mcp-server-plan.md` + spec | MCP-серверы удаляются. |
| `docs/superpowers/plans/2026-04-02-financial-overview-skill.md` + spec | Заменён на finance-report. |

**Bulk count:** ~140 files (включая массовое удаление `.planning/archive/v1.0`, `.planning/milestones/v2.0-*`, `.planning/phases/`, `.planning/research/`).

---

## 4. ARCHIVE list (move to `docs/archive/…`)

| Source → destination | Причина |
|---|---|
| `docs/agents/bitrix-crm.md` → `docs/archive/agents/bitrix-crm.md` | Legacy note, но содержит ссылки для истории. |
| `docs/agents/wb-sheets-sync-plan.md` → `docs/archive/plans/wb-sheets-sync-plan.md` | Старый план до реализации `services/sheets_sync/`. |
| `docs/plans/oleg-v2-rebuild.md` → `docs/archive/plans/oleg-v2-rebuild.md` | Выполнен/устарел. |
| `docs/plans/2026-02-25-dashboard-tz.md` → `docs/archive/plans/` | Dashboard реализован. Cleanup-v2 §2.6. |
| `docs/plans/2026-02-25-db-audit-results.md` → `docs/archive/plans/` | Cleanup-v2 §2.6. |
| `docs/plans/2026-02-25-db-improvement-proposals.md` → `docs/archive/plans/` | Историческая запись. |
| `docs/plans/2026-04-business-plan.md` → `docs/archive/plans/` | Cleanup-v2 §2.6 — «черновик, есть final». |
| `docs/plans/2026-04-business-plan-generated.md` → `docs/archive/plans/` | Промежуточный артефакт. |
| `docs/plans/2026-04-business-plan-final.md` → `docs/archive/plans/` | Выполненный месячный план, место в истории. |
| `docs/abc_analysis_playbook.md` → `docs/archive/` | Заменён `.claude/skills/abc-audit/`. |
| `docs/reports/2026-03-*` (4 файла) → `docs/archive/reports/` | Старше 4 недель. Reports — живая директория, но старые стоит архивировать. *Решение оставлю как KEEP — мало мусора, пусть копится.* |
| `docs/superpowers/plans/2026-04-02-monthly-plan-skill-plan.md` → `docs/archive/plans/` | Выполнен (monthly-plan скилл готов). |
| `docs/superpowers/specs/2026-04-02-monthly-plan-skill-design.md` → `docs/archive/` | Same. |
| `docs/superpowers/plans/2026-04-03-monthly-plan-ux-refactor-plan.md` + spec | Выполнен. |
| `docs/superpowers/plans/2026-03-25-irp-integration-plan.md` + spec `2026-03-25-irp-calculation-spec.md` | IRP встроен в `services/wb_localization`. |
| `docs/superpowers/plans/2026-03-25-logistics-audit-service-plan.md` + spec | Выполнен (services/logistics_audit существует). |
| `docs/superpowers/plans/2026-03-25-logistics-cost-report-plan.md` + spec | Выполнен. |
| `docs/superpowers/plans/2026-04-04-logistics-audit-v2-fixes.md` + spec `2026-04-03-logistics-audit-v2-fix-design.md` | Выполнен. |
| `docs/superpowers/specs/2026-04-07-logistics-audit-ooo-recalculation.md` | Выполнен. |
| `docs/superpowers/plans/2026-04-08-logistics-audit-deliverables.md` + spec | Выполнен. |
| `docs/superpowers/plans/2026-04-06-db-audit-remediation.md` + spec | Выполнен частично, Wave plan живой в памяти пользователя. |
| `docs/superpowers/plans/2026-04-11-database-full-audit-plan.md` + spec | Выполнен. |
| `docs/superpowers/plans/2026-04-12-database-audit-remediation.md` | Выполнен. |
| `docs/superpowers/plans/2026-04-07-product-data-audit.md` + spec | Выполнен (отчёт в `docs/reports/2026-04-07-product-data-audit-report.md`). |
| `docs/superpowers/plans/2026-04-07-sheets-to-supabase-sync.md` + spec | Выполнен. |
| `docs/superpowers/plans/2026-04-07-analytics-report-plan.md`+ `2026-04-07-analytics-report-skill.md` + 3 связанных spec | Выполнен. |
| `docs/superpowers/plans/2026-04-07-reviews-audit-skill-plan.md` + spec | Выполнен. |
| `docs/superpowers/plans/2026-04-07-reviews-audit-v2-plan.md` + spec | Выполнен. |
| `docs/superpowers/plans/2026-04-08-analytics-kb-and-bugfixes.md` | Fixes выполнены, архив. |
| `docs/superpowers/plans/2026-04-08-finance-report-plan.md` + spec `2026-04-08-modular-analytics-v2-design.md` | Finance-report v4 в проде. |
| `docs/superpowers/plans/2026-04-10-marketing-report-plan.md` + spec `2026-04-11-marketing-report-v2-plan.md` | Marketing-report v2 в проде. |
| `docs/superpowers/plans/2026-04-11-abc-audit-plan.md` + spec `2026-04-11-abc-audit-skill-design.md` | ABC-audit v1 в проде. |
| `docs/superpowers/specs/2026-04-11-search-query-analytics-design.md` | Выполнен (`scripts/run_search_queries_sync.py`). |
| `docs/superpowers/plans/2026-04-12-funnel-report-plan.md` + `2026-04-13-funnel-report-ozon.md` + specs | Выполнен (funnel-report v3). |
| `docs/superpowers/plans/2026-04-13-audit-deferred-tasks.md` | Выполнен. |
| `docs/superpowers/plans/2026-04-13-finolog-logistics-skills.md` + spec | Выполнен. |
| `docs/superpowers/plans/2026-04-13-project-cleanup-v2.md` | Superseded `refactor-v3-phase1.md`. |
| `docs/superpowers/specs/2026-04-13-project-cleanup-v2-design.md` | Остаётся source-of-truth для «known garbage» по v3 design'у (§1.3 v3). Условно **KEEP** в specs/ — на v3 на него ссылаются. *Финальное решение за orchestrator'ом.* |
| `docs/superpowers/plans/2026-04-13-tool-registry.md` + spec | Выполнен. |
| `docs/superpowers/plans/2026-04-15-finolog-logistics-v2-fixes.md` | Выполнен. |
| `docs/superpowers/plans/2026-04-15-wb-logistics-optimizer-plan.md` + spec | Завершение в PR #3 refactor. |
| `docs/superpowers/plans/2026-04-15-wb-tariffs-bootstrap-rollout.md` | Выполнен. |
| `docs/superpowers/plans/2026-04-16-localization-service-redesign-plan.md` + `-COMPLETION.md` + spec | Выполнен (2026-04-23, на main). |
| `docs/superpowers/specs/2026-04-17-creative-kb-design.md` | В процессе: PR #3 refactor завершит. Пока KEEP в specs/. |
| `.planning/MILESTONES.md`, `PROJECT.md`, `ROADMAP.md`, `STATE.md` | Артефакты GSD/plan-скиллов, относятся к product-matrix. Архивировать (или DELETE, решит orchestrator). |

---

## 5. UPDATE list

| Путь | Что изменить — bullets |
|---|---|
| `README.md` | — Убрать Lyudmila (L95) и Vasily (L97) как «Активен/В разработке» — они retired/удалены.<br>— Удалить mermaid-диаграммы L42-68, 71-82 (упоминают Lyudmila/Vasily в Active).<br>— Обновить таблицу «AI-агенты» (L92-98): оставить только «Олег» → помечать как ретайрнутый после PR #5, или переписать раздел как «Скиллы» со ссылкой на `.claude/skills/`.<br>— L19-21: удалить ссылку на `agents/oleg/playbooks/` и `scripts/run_oleg_v2_*.py` (последних нет в `scripts/`).<br>— L125-135: дерево проекта — убрать lyudmila, vasily, добавить creative_kb, wb_logistics_api, logistics_audit, content_kb, observability.<br>— L166-195: Entrypoints — убрать `python -m agents.oleg`, `python -m agents.oleg agent`, `python -m services.sheets_sync`, `services.marketplace_etl.scripts.run_daily_sync` (несуществующий путь). Оставить `wb_localization`, `wb_logistics_api`, добавить `python scripts/daily_brief/run.py`.<br>— L213-215: pip-install — `services/wb_logistics_api/requirements.txt` есть, но нет `agents/oleg/requirements.txt` (если его удалить). Переписать под `-r requirements.txt`.<br>— L307-311: Archive-секция — корректна.<br>— Весь блок «Активные AI-агенты/В разработке/Планируемые» (L268-280) заменить на описание скиллов. |
| `AGENTS.md` | — L11: описание Oleg как «multi-agent orchestrator» удалить/переформулировать.<br>— L16: `services/marketplace_etl/` не существует → заменить на актуальные сервисы.<br>— L16: `services/etl/` не существует.<br>— L18: `services/wb_localization/` ok.<br>— L19: `services/ozon_delivery/` — per cleanup-v2 «под вопросом», orchestrator решит.<br>— L21: `scripts/` ok, но нужно актуализировать перечень скриптов.<br>— L63-71: экономика агентов (4 тира: LIGHT/MAIN/HEAVY/FREE) ОК, соответствует `.claude/rules/economics.md`, НО модели `z-ai/glm-4.7-flash`, `z-ai/glm-4.7` в AGENTS.md противоречат `.claude/rules/economics.md` (там gemini-3-flash-preview/claude-sonnet-4-6). Синхронизировать с `.claude/rules/` (source-of-truth).<br>— L73-80: раздел WB MCP — оставить (MCP external Wildberries сохраняется), но убрать упоминание `.mcp.json` локальных MCP.<br>— Добавить ссылку на `ONBOARDING.md`. |
| `CLAUDE.md` | — KEEP в целом (короткий файл). Добавить ссылку на `ONBOARDING.md` и `docs/skills/`. |
| `CONTRIBUTING.md` | — L25-34: дерево проекта — убрать «agents/» (там только retired Oleg после PR #5) → заменить на «scaffold для будущих true-agents».<br>— L40-49: ветки `feature/`, `fix/`, `docs/`, `refactor/` ok, но добавить политику: **все изменения через PR с Codex + Copilot review + auto-merge**.<br>— L62-69: переписать процесс — добавить `/pullrequest` skill pipeline.<br>— L97-115: «Разработка агентов» — удалить секцию (`agents/vasily_agent/` пример не существует), заменить на «Разработка скиллов в `.claude/skills/`». |
| `SECURITY.md` | — L64: ссылка `wookiee_sku_database/README.md` — такой папки нет (есть `sku_database/`). Исправить.<br>— L70-82: таблица секретов — проверить актуальность (Bitrix Webhook, МойСклад, z.ai Key, Google Service Account). Z.AI уже не используется напрямую (OpenRouter).<br>— L75: `ANTHROPIC_API_KEY` — убрать (только через OpenRouter).<br>— L76: `Z_AI_API_KEY` — убрать (legacy).<br>— Добавить `OPENROUTER_API_KEY`, `FINOLOG_API_TOKEN`, `MPSTATS_API_KEY`. |
| `docs/index.md` | **Полный rewrite** — текущий описывает Oleg/Ibrahim/Lyudmila/mp-localization, ни одного актуального скилла. Target: Core + Skills (ссылка на каждый `docs/skills/<name>.md`) + Services (ссылка на каждый `services/<name>/README.md`) + Database + Guides + Archive. |
| `docs/architecture.md` | — L39-43: убрать строки «Олег» и «Ибрагим» (удаляются/удалены).<br>— L48-53: убрать `Marketplace ETL` и `Vasily API` (не существуют), добавить `logistics_audit`, `wb_logistics_api`, `wb_localization`, `content_kb`, `creative_kb`, `observability`.<br>— L57-64: MCP Servers — таблица актуальна (wildberries-ip/ooo), но после удаления локальных MCP добавить примечание.<br>— L72-78: Runtime Entrypoints — убрать `python -m agents.oleg`, `services.marketplace_etl.scripts.run_daily_sync`, `services.sheets_sync.runner`, `services.wb_localization.run_localization` (проверить путь), `uvicorn services.vasily_api.app:app` → заменить на `uvicorn services.wb_logistics_api.app:app`.<br>— L80-84: Deprecated — оставить, добавить `agents/oleg` и `services/marketplace_etl`. |
| `docs/infrastructure.md` | — L42-48: таблица контейнеров — убрать `wookiee_oleg` и `vasily-api` (после PR #5/#4). Оставить `wookiee_sheets_sync` (если сохранится) + добавить `wb-logistics-api` per новому сервису. |
| `docs/adr.md` | — Добавить ADR-008: Refactor v3 Phase 1 — «colleague-ready repo» (основание: `docs/superpowers/specs/2026-04-24-refactor-v3-design.md`). |
| `docs/development-history.md` | — Заголовок говорит «последние 10 записей». Сейчас 10+ записей, самые старые в Архив. Обрезать.<br>— Добавить запись о refactor-v3 после завершения. |
| `docs/guides/environment-setup.md` | — L21: убрать `pip install -r services/vasily_api/requirements.txt`.<br>— L29: убрать `TELEGRAM_BOT_TOKEN`, `BOT_PASSWORD_HASH` (Oleg бот удаляется).<br>— L32: `VASILY_SPREADSHEET_ID` → заменить на актуальные Sheets IDs для wb_localization/wb_logistics_api.<br>— L39: убрать `python3 -m services.wb_localization.run_localization --dry-run` только если путь устарел — проверить.<br>— L46-47: Production Server — ok. |
| `docs/guides/logging.md` | Не читал детально. Пометить как UPDATE — вероятно упоминает Oleg watchdog/telegram alerter. |
| `docs/TOOLS_CATALOG.md` | Автогенерируется. KEEP файл, но перегенерировать после рефакторинга через `scripts/generate_tools_catalog.py`. |
| `docs/database/DATABASE_REFERENCE.md` / `DATABASE_WORKPLAN.md` / `DB_QUESTIONS_FOR_DEVELOPER.md` | KEEP (living docs), но проверить упоминания agents/oleg — если есть, пометить. |
| `docs/database/DB_METRICS_GUIDE.md`, `DATA_QUALITY_NOTES.md` | KEEP, но поиск на 'оleg/vasily' (есть упоминания — см. §8). |
| `docs/logistics-audit-algorithm-v2.md` / `-methodology-v2.md` | KEEP — актуальная дока `/logistics-audit` скилла. Потенциально перенести в `docs/skills/logistics-audit/`. |
| `docs/plans/MONTHLY-PLAN-PROCESS.md` / `MONTHLY-PLAN-TECHNICAL-SPEC.md` | KEEP + UPDATE: проверить на ссылки на Oleg. |
| `docs/scripts/search-queries-sync.md` | KEEP — актуальный. |
| `docs/workflows/system-architecture.html` | UPDATE — упоминает Oleg. |
| `docs/workflows/wookiee-reporting-system.html` | UPDATE — проверить. |

---

## 6. CREATE list (per spec §6)

### 6.1 Root files
| Path | Содержимое (skeleton) |
|---|---|
| `ONBOARDING.md` | spec §6.3 template — onboarding за 30 мин: clone → .env → первая команда → первый PR. |
| `.github/pull_request_template.md` | spec §5.2 template — «Что изменено / Почему / Как проверено». |

### 6.2 `docs/skills/<name>.md` (14 файлов, spec §6.4 template — Назначение / Триггеры / Входные / Выходные / Команды / Связанные / Статус)

| Path | Соответствующий скилл |
|---|---|
| `docs/skills/finance-report.md` | `/finance-report` |
| `docs/skills/marketing-report.md` | `/marketing-report` |
| `docs/skills/daily-brief.md` | `/daily-brief` |
| `docs/skills/funnel-report.md` | `/funnel-report` |
| `docs/skills/logistics-report.md` | `/logistics-report` |
| `docs/skills/abc-audit.md` | `/abc-audit` |
| `docs/skills/market-review.md` | `/market-review` |
| `docs/skills/analytics-report.md` | `/analytics-report` |
| `docs/skills/reviews-audit.md` | `/reviews-audit` |
| `docs/skills/monthly-plan.md` | `/monthly-plan` |
| `docs/skills/finolog-dds-report.md` | `/finolog-dds-report` |
| `docs/skills/content-search.md` | `/content-search` |
| `docs/skills/tool-status.md` | `/tool-status` |
| `docs/skills/tool-register.md` | `/tool-register` |

*Опционально* (semi-auto generation из `.claude/skills/<name>/SKILL.md` + Supabase `tools`): finolog, gws-drive, gws-sheets, workflow-diagram, cloudflare-pub, notebooklm, bitrix-task, bitrix-analytics — глобальные или утилитарные. Orchestrator решит полный перечень.

### 6.3 Module READMEs (в `services/<module>/README.md` — spec §4.2 template)

| Path | Сервис | Примечание |
|---|---|---|
| `services/logistics_audit/README.md` | logistics_audit | Уже существует — проверить актуальность. |
| `services/wb_localization/README.md` | wb_localization | Проверить. |
| `services/wb_logistics_api/README.md` | wb_logistics_api | **NEW — untracked, нужно создать в PR #3.** |
| `services/sheets_sync/README.md` | sheets_sync | Проверить. |
| `services/content_kb/README.md` | content_kb | Проверить. |
| `services/creative_kb/README.md` | creative_kb | **NEW — untracked, нужно создать в PR #3.** |
| `services/observability/README.md` → **после переименования** `services/<new_name>/README.md` | tool_telemetry/run_logger (имя определит orchestrator) | NEW. |
| `services/knowledge_base/README.md` | knowledge_base | Если orchestrator подтвердит «оставляем» — создать. Иначе удалить. |

### 6.4 Agents scaffold
| Path | Содержимое |
|---|---|
| `agents/README.md` | Spec §3.5: «Текущие скиллы — в `.claude/skills/`. Сюда — будущие true-agent реализации». |

### 6.5 Archive knowledge capture
| Path | Содержимое |
|---|---|
| `docs/archive/oleg-v2-architecture.md` | Cleanup-v2 §2.4 + spec §3: перед удалением Oleg — архитектурный конспект (5 ролей, ReAct, Orchestrator, какие аналитические знания были в промптах и куда они перешли). |

### 6.6 Hygiene skill placeholder (spec §7.6)
| Path | Содержимое |
|---|---|
| `.claude/skills/hygiene/README.md` | «Фаза 2 — планируется». |
| `.claude/hygiene-config.yaml` | Placeholder per spec §7.4. |

**Всего CREATE: 26 файлов** (2 root + 14 skills + 8 services + 1 agents + 1 archive + не считая hygiene placeholder, который в `.claude/`, не `docs/`).

---

## 7. Broken links report

Проверены источники: `docs/index.md`, `README.md`, `AGENTS.md`, `docs/architecture.md`, `docs/PROJECT_MAP.md`, `docs/QUICKSTART.md`, `docs/agents/*.md`.

| Source file | Broken target | Проверка |
|---|---|---|
| `README.md:95` | `agents/lyudmila/` | Директория не существует. |
| `README.md:97` | `agents/vasily/` | Директория не существует. |
| `README.md:105` | `services/marketplace_etl/` | Директория не существует. |
| `README.md:179, 225` | `services/marketplace_etl/scripts/run_daily_sync` | Модуля нет. |
| `README.md:21` | `scripts/run_oleg_v2_single.py`, `run_oleg_v2_reports.py` | В `scripts/` отсутствуют. |
| `AGENTS.md:15-16` | `services/marketplace_etl/`, `services/etl/` | Обе не существуют. |
| `AGENTS.md:19` | `services/ozon_delivery/` | Не существует в `services/`. (Под вопросом в spec.) |
| `docs/index.md:19` | `services/etl` (в тексте Active Runtime) | Нет такой директории. |
| `docs/index.md:18` | `agents/telegram-bot.md` | Файл будет удалён (§3). |
| `docs/index.md:19` | `agents/ibrahim.md` | Файл будет удалён (§3). |
| `docs/index.md:20` | `agents/mp-localization.md` | Будет удалён/перенесён (§5). |
| `docs/index.md:21` | `agents/analytics-engine.md` | Будет удалён (§3). |
| `docs/index.md:50` | `workflows/oleg-report-pipeline.html` | Будет удалён (§3). |
| `docs/index.md:51` | `workflows/ibrahim-etl-flow.html` | Будет удалён. |
| `docs/index.md:63` | `plans/2026-02-25-dashboard-tz.md` | Будет архивирован. |
| `docs/QUICKSTART.md:22` | `services/vasily_api/requirements.txt` | Директория не существует. |
| `docs/QUICKSTART.md:37, 39` | `python3 -m agents.oleg` | Модуль будет удалён в PR #5. |
| `docs/QUICKSTART.md:49` | `services.marketplace_etl.scripts.run_daily_sync` | Модуля нет. |
| `docs/architecture.md:52` | `services/vasily_api/` | Директория не существует. |
| `docs/architecture.md:49, 72, 73` | `services/marketplace_etl/` | Не существует. |
| `docs/architecture.md:40-41, 74` | `agents/oleg/`, `agents/ibrahim/` — описаны как «Активен» | `agents/ibrahim/` физически отсутствует. |
| `docs/PROJECT_MAP.md:334-343` | `services/vasily_api/` | Не существует. |
| `docs/PROJECT_MAP.md:261-286` | `agents/ibrahim/` дерево | Не существует. |
| `docs/PROJECT_MAP.md:605-647` | множественные `agents/lyudmila/`, `agents/vasily/` | Не существуют. |
| `docs/agents/analytics-engine.md:5` | `agents/oleg/services/price_analysis/` | Будет удалено с Oleg. |
| `docs/agents/telegram-bot.md:20-22` | `agents/oleg/main.py`, `agents/oleg/handlers/` | Файлы есть сейчас, удаляются в PR #5. |
| `docs/agents/ibrahim.md` (весь) | `agents/ibrahim/**` | Директория отсутствует. |
| `SECURITY.md:64` | `wookiee_sku_database/README.md` | Таких папок нет (есть `sku_database/`). |
| `CONTRIBUTING.md:110-114` | `agents/vasily_agent/` пример | Не существует. |

**Итого уникальных сломанных таргетов после рефакторинга: 24+** (будет ещё больше после физического удаления `agents/oleg/`).

---

## 8. Oleg / Lyudmila / Vasily mentions as ACTIVE

Файлы, где агенты упоминаются **как активные/работающие** (не в archive/context):

| Файл:строка | Упоминание | Verdict |
|---|---|---|
| `README.md:6, 18-21, 50-52, 71-82, 94-98, 125-135, 170-173, 213, 268-274, 309-311` | Oleg (активный), Lyudmila (активный), Vasily (в разработке) | UPDATE — убрать Lyudmila/Vasily, Oleg помечать как retired после PR #5. |
| `AGENTS.md:11` | «agents/oleg — Олег, финансовый AI-агент… активен» | UPDATE. |
| `docs/index.md:18-21` | Oleg, ETL, WB localization, Analytics Engine в Active Runtime | UPDATE (полный rewrite). |
| `docs/architecture.md:40-43, 72-78, 82-84` | Олег, Ибрагим как активные; Vasily только в Deprecated | UPDATE — все агенты в Deprecated/Archive. |
| `docs/PROJECT_MAP.md` | Вся карта вокруг Oleg v2 + Ibrahim + Vasily + Lyudmila | DELETE целиком. |
| `docs/QUICKSTART.md:37, 39` | `python -m agents.oleg` entrypoint | DELETE. |
| `docs/system.md` (весь файл) | Oleg pipeline 7-step, Reporter/Advisor/Validator агенты, Vasily API | DELETE. |
| `docs/agents/README.md:11-14` | Oleg / ETL / WB Localization / Analytics Engine в Active Registry | DELETE. |
| `docs/agents/telegram-bot.md` (весь) | Oleg Telegram runtime | DELETE. |
| `docs/agents/analytics-engine.md:5, 20-22` | `agents/oleg/services/price_analysis/` ссылки | DELETE. |
| `docs/agents/ibrahim.md` (весь) | Ибрагим активен | DELETE. |
| `docs/agents/mp-localization.md` | Сам агент retired, но описывает текущий wb_localization | UPDATE → перенести в `docs/services/wb_localization.md` или в `services/wb_localization/README.md`. |
| `docs/agents/bitrix-crm.md:17-19` | Lyudmila archive (корректно помечено) | ARCHIVE → `docs/archive/agents/`. |
| `docs/agents/wb-sheets-sync-plan.md` | Планы до реализации | ARCHIVE. |
| `docs/adr.md:7-30, 103, 159-164` | ADR-007 narrow runtime (Oleg/Ibrahim/marketplace_etl… как активные) | KEEP (исторические ADR), но добавить ADR-008 про refactor-v3. |
| `docs/development-history.md` | Много записей про Oleg playbook/tools | KEEP как историю, но обрезать до 10 записей. |
| `docs/guides/environment-setup.md:21, 29, 40` | `services/vasily_api/requirements.txt`, `TELEGRAM_BOT_TOKEN`, `wb_localization --dry-run` | UPDATE. |
| `docs/guides/logging.md` | Ожидается упоминание Oleg alerter/watchdog | UPDATE (не читал полностью). |
| `docs/guides/agent-principles.md` | Общие принципы + возможно примеры из Oleg | UPDATE (проверить примеры). |
| `docs/infrastructure.md:46-48` | `wookiee_oleg`, `vasily-api` контейнеры | UPDATE — удалить после PR #5/#4. |
| `docs/plans/ibrahim-deploy-and-etl.md` (весь) | Ибрагим deployment план | DELETE. |
| `docs/plans/oleg-v2-rebuild.md` (весь) | Oleg rebuild | ARCHIVE. |
| `docs/plans/2026-02-25-db-audit-results.md` | Упоминает Oleg как источник данных | ARCHIVE. |
| `docs/plans/2026-02-25-dashboard-tz.md` | Dashboard для Oleg v2 | ARCHIVE. |
| `docs/plans/2026-04-business-plan*.md` (3 файла) | Мб упоминают Oleg | ARCHIVE. |
| `docs/future/agent-ops-dashboard/**` | Oleg v2 dashboard | DELETE (spec §3 flagged). |
| `docs/workflows/oleg-report-pipeline.html` | Oleg | DELETE. |
| `docs/workflows/vasily-localization-pipeline.html` | Vasily | DELETE. |
| `docs/workflows/ibrahim-etl-flow.html` | Ibrahim | DELETE. |
| `docs/workflows/agent-system-architecture.html` | Все 4 агента | DELETE. |
| `docs/workflows/system-architecture.html` | Oleg, Ibrahim | UPDATE (или DELETE + rebuild). |
| `docs/database/DATA_QUALITY_NOTES.md` | Контекстные упоминания Oleg playbook (legit) | KEEP (текст может содержать ссылки «правило для Oleg» — переписать в abstract). |
| `docs/database/DB_METRICS_GUIDE.md` / `DB_QUESTIONS_FOR_DEVELOPER.md` | Контекстные | KEEP + grep на активные ссылки. |
| `docs/archive/agents/lyudmila-bot.md`, `docs/archive/agents/vasily/**`, `docs/archive/retired_agents/lyudmila/**`, `docs/archive/plans/lyudmila-bitrix24-agent-retired.md` | Уже в archive | KEEP as is. |
| `docs/superpowers/plans/*.md` + `docs/superpowers/specs/*.md` | Множественные — см. §3 DELETE / §4 ARCHIVE. | В основном DELETE/ARCHIVE. |
| `docs/reports/2026-04-13_2026-04-19_*.md` | Контекстные (Oleg упомянут) | KEEP — это сохранённые отчёты. |

---

## 9. Notes for orchestrator

1. **Спорные решения — не беру на себя** (spec §2.2 п.5):
   - `docs/archive/reports/` перенос старых reports за март — *оставил KEEP*, но можно архивировать если много.
   - `docs/future/agent-ops-dashboard/` — spec разрешает archive или delete; я выбрал **DELETE** (содержимое reviews/ — критика Oleg v2 агентов, уже неактуально).
   - `services/knowledge_base/` README — создавать или нет зависит от решения orchestrator'а (KEEP или DELETE сервис).
   - `docs/superpowers/specs/2026-04-13-project-cleanup-v2-design.md` — spec v3 к нему явно апеллирует (§1.3 в v3). Оставил KEEP в `specs/`, но это граничный случай.
   - `docs/guides/logging.md` и `docs/guides/agent-principles.md` не прочитаны полностью — пометил UPDATE по предположению. Финализировать orchestrator'у.

2. **Большие риски для линков**:
   - После удаления `docs/agents/` — проверить grep по всему репо (включая `.claude/skills/*/SKILL.md`) на ссылки `docs/agents/*`.
   - После удаления `docs/PROJECT_MAP.md` — проверить ссылки из `README.md`, `CLAUDE.md`, `AGENTS.md` на `PROJECT_MAP.md` (кажется их нет, но надо grep).

3. **Скиллы в `docs/skills/`** — можно автогенерить полу-автоматически из `.claude/skills/<name>/SKILL.md` + строка из Supabase `tools`. Orchestrator может заложить в manifest PR #7: «scripts/generate_skill_docs.py» как отдельный артефакт или inline.

4. **Знания из Oleg (spec §6.2 + cleanup-v2 §2.4)** — в `docs/archive/oleg-v2-architecture.md` стоит сохранить:
   - 5 ролей (Reporter, Marketer, Funnel Analyzer, Validator, Advisor).
   - ReAct loop + circuit breaker + context compression.
   - Orchestrator decision flow (какая цепочка при каком trigger'е).
   - Ссылку на `agents/oleg/playbooks/core.md` и `rules.md` (если эти правила уже перетекли в `.claude/rules/`, указать).

5. **Локаль документации**: текущие документы — русский. `ONBOARDING.md` и новые `docs/skills/*.md` — писать на русском per стиль проекта.

---

**Report to caller:**
- Verdict counts: KEEP 39, UPDATE 18, ARCHIVE 38, DELETE ~140, CREATE 26.
- Broken links: 24+ unique targets (куда 8 совпадают с «несуществующие директории»: `agents/lyudmila/`, `agents/vasily/`, `agents/ibrahim/`, `services/vasily_api/`, `services/marketplace_etl/`, `services/etl/`, `services/product_matrix_api/`, `services/dashboard_api/`).
- Deliverable: `/Users/danilamatveev/Projects/Wookiee/.planning/refactor-audit/docs-audit.md`.
