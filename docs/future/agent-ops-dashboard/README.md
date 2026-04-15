# Agent Operations Dashboard

> Визуализация работы мульти-агентной системы Oleg v2 внутри Wookiee Hub.

**Статус**: Отложено. Полный план и мокапы готовы. Ждёт реализации.
**Дата создания**: 2026-04-01

---

## Что это

Раздел Wookiee Hub (`/system/agents`) для мониторинга 6 ИИ-агентов: Reporter, Marketer, Funnel, Researcher, Advisor, Validator. Единый экран для утренней проверки — состояние системы за 10 секунд.

**MVP — одна страница Overview** с 8 компонентами:
- 4 KPI-карточки (активные агенты, отчёты, success rate, расход)
- Fleet Table (6 агентов со статусами и circuit breaker)
- Activity Feed (live-лента событий, polling 30с)
- Pipeline Timeline (7-дневный heatmap запусков)
- Circuit Breaker Panel (с кнопкой Reset)
- Cost Breakdown (расходы по агентам за 24ч)
- Alert Banner (sticky при CB Open / critical anomaly)
- Live Indicator (пульс + "обновлено Xс назад")

## Архитектура

```
Backend:  FastAPI внутри процесса Oleg (порт 8091)
          ├── 8 REST endpoints (GET + 1 POST для CB reset)
          ├── Читает: state_store.py (SQLite) + CircuitBreaker (in-memory)
          └── Новая таблица: event_log (unified events, JSON metadata)

Frontend: React + TypeScript + Tailwind + shadcn/ui
          ├── 8 компонентов в src/components/agents/
          ├── Polling 30с (usePollingQuery hook)
          ├── Без Zustand store (независимые хуки)
          └── OKLCH dark theme (консистентно с Hub)
```

## Фазы реализации

| Фаза | Описание | Оценка |
|------|----------|--------|
| **1A** | Backend Foundation — API, schemas, registry, event_log | 1 день |
| **1B** | Frontend Overview — 8 компонентов + страница | 1-2 дня |
| **1C** | Event Integration — log_event() в 5 точках pipeline | 0.5 дня |
| **2** | Interactivity — detail sheets, фильтры, sub-pages | 2 дня |
| **3** | Agent Observability — trace_id, llm_call_log, waterfall | 2-3 дня |
| **4** | Cost Tracker — charts, timeline, cost per report | 1-2 дня |

**MVP (Phases 1A-1C)**: ~3 дня работы.

## Файлы проекта

```
docs/future/agent-ops-dashboard/
├── README.md              ← вы здесь
├── SPEC.md                ← полная спецификация (UI/UX + Implementation Plan)
├── mockups/
│   ├── agent-dashboard-v2.html         ← актуальный мокап (открыть в браузере)
│   ├── agent-dashboard-v2-desktop.png  ← скриншот 1440px
│   └── agent-dashboard-v1.html         ← первая версия (для истории)
└── reviews/
    ├── 01-ux-critic.md          ← UX-review (5.5/10 → учтено в v2)
    ├── 02-product-manager.md    ← Feature Matrix (MVP/v2/backlog)
    ├── 04-designer.md           ← Design System alignment
    ├── 05-developer.md          ← Technical architecture
    └── 06-agent-expert.md       ← Agent observability рекомендации
```

## Как начать реализацию

1. Прочитать `SPEC.md` — единственный source of truth
2. Открыть `mockups/agent-dashboard-v2.html` в браузере — визуальный ориентир
3. Начать с Phase 1A (backend): создать `agents/oleg/api/` и таблицу `event_log`
4. Проверить: `curl http://localhost:8091/api/agents/overview` должен вернуть JSON
5. Перейти к Phase 1B (frontend): 8 компонентов + страница

## Ключевые решения

- **1 таблица** `event_log` вместо 3 отдельных (CB + anomaly = event_type + JSON metadata)
- **Polling 30с** вместо WebSocket/SSE (2-4 запуска/день — достаточно)
- **API внутри Oleg** (порт 8091) — доступ к in-memory CircuitBreaker
- **Без Zustand store** — независимые `usePollingQuery` хуки
- **8 компонентов** в MVP (не 9, не 3 — баланс модульности)

## Зависимости

- Backend: `agents/oleg/storage/state_store.py` (добавить event_log, log_event())
- Backend: `agents/oleg/main.py` (mount FastAPI)
- Backend: nginx на Timeweb (proxy_pass порт 8091)
- Frontend: `wookiee-hub/src/router.tsx` (заменить stub)
- Frontend: `wookiee-hub/src/index.css` (добавить --wk-*-surface токены)

## Контекст

Проект создан по результатам multi-agent review (6 агентов: UX Critic, Product Manager, Team Lead, Frontend Designer, Developer, Agent Systems Expert). Вдохновлён AxionAI Fleet Operations dashboard, адаптирован под реальную архитектуру Wookiee.
