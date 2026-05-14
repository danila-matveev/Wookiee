# W9 — Журнал исполнения (append-only)

Каждое значимое событие фиксируется здесь.

## 2026-05-12 — Подготовка

- Базовая ветка: `feature/catalog-overhaul-w9` создана из `origin/main` (HEAD `bfcc6dc` — `fix(telemost): UX batch 1`).
- ТЗ: `W9-FIXES-TZ.md`, оркестратор: `W9-ORCHESTRATOR.md`.
- Untracked posix-файлы из marketing/telemost направлений намеренно не включены в ветку.
- Первый push: `3a92faf0ca3234c367a203beeff1df2d15586bec` — это safety-point. Любой `git reset --hard` возвращаем к нему.

## 2026-05-12 — BLOCKER: нет инструмента для параллельного диспатча суб-агентов

В текущей сессии Claude Code нет инструмента `Task` / `Agent` / любого аналога, который позволил бы оркестратору запустить `Agent({ isolation: "worktree", subagent_type: "general-purpose" })` параллельно. Доступны только `EnterWorktree`/`ExitWorktree` для переключения текущей сессии — но это последовательно и в одной сессии.

Это означает, что план оркестратора (4 параллельных агента в Волне A, 7 в Волне B, и т.д.) не может быть выполнен здесь.

Возможные альтернативы — на усмотрение пользователя:
1. Я сам, последовательно, в этой сессии прохожу W9.1 → W9.20 через прямые правки + worktree-переключения (медленно, но без потери качества).
2. Пользователь запускает отдельные сессии Claude Code для каждой волны, передавая им prompt-шаблоны из оркестратора.
3. Сменить план на "одна большая ветка, один проход, без волн" — но тогда контекст сессии может не выдержать 20 пунктов сразу.

Оркестратор остановлен до решения пользователя.

## 2026-05-12 — Решение: главный агент дёргает Agent сам

Sub-orchestrator (`general-purpose`) не видел deferred-tool `Agent`. Главный агент сессии — видит и имеет к нему доступ. Поэтому волны запускаются прямо из главной сессии.

## 2026-05-12 — Волна A завершена

Все 4 агента отработали в изолированных worktree.

| Agent | Задача | SHA (worktree) | SHA (cherry-pick) | Артефакты |
|-------|--------|----------------|--------------------|-----------|
| A1 | W9.1 audit GRANT/RLS | `29e54ed` | `1ed868e` | migration 024_audit_grants (applied) |
| A2 | W9.2 + W9.3 status-cols + поиск | `3d1f581` | `a461aec` | matrix/artikuly/tovary + service + use-debounced-value |
| A3 | W9.8 размеры | `0005ee8` | `379c0d9` | model-utils + tests + service + matrix |
| A4 | W9.12 палитра по категории | `8b0339f` | `863a75a` | migration 025_cvet_kategoriya (applied) + ColorPicker + hook |

**DB-миграции:**
- `024_audit_grants` — applied в Supabase `gjvwcdtfglupewcwzfhw`. Snimaet permission denied на `infra.istoriya_izmeneniy` (это была реальная таблица — `infra.`, не `public.`). Также фикс для второго аудит-лога `public.audit_log` (миг 023 выдала только SELECT).
- `025_cvet_kategoriya` — applied. Создана m2m-таблица `cvet_kategoriya(cvet_id, kategoriya_id)`. Backward-compat: пустой rowset = цвет универсальный.

**Ключевые находки:**
- В БД два аудит-механизма: legacy `public.log_izmeneniya` → `infra.istoriya_izmeneniy` (FIX W9.1) + новый `public.audit_trigger_fn` → `public.audit_log` (мигр 023). Оба пишутся. Архитектурный вопрос на потом — оставлять ли legacy.
- В `modeli_osnova` есть CSV-поле `razmery_modeli` — источник истины для размеров. Junction `modeli_osnova_razmery` рассинхронизирован, его в W9.20 надо или backfill'ить, или депрекейтить.
- StatusBadge ломался для status_id > 7 (legacy lookup `CATALOG_STATUSES` знал только tip=model/product). А2 пробросил `resolveStatus` через CellContext с lookup'ом по живому `statusy`. В W9.17 это надо унифицировать в общий компонент.
- В `cvet_kategoriya` пока 0 строк → фактически фильтр Charlotte→body не активен. Нужен бэкфилл (вручную через colors-edit UI или скриптом).

**TSC + build на главной ветке:** clean (pre-existing pre-W7 проблемы исправились `npm install`).

**Cherry-pick порядок:** A1 → A3 → A4 → A2 (без конфликтов, auto-merge service.ts и matrix.tsx).

