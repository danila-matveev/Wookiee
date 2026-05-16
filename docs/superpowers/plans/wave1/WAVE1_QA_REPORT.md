# Wave 1 — QA Report

**Дата:** 2026-05-15
**Branch:** `feat/ds-v2-wave-1-spec`
**Spec:** `docs/superpowers/specs/2026-05-15-hub-ds-v2-wave-1-design.md`
**Plan:** `docs/superpowers/plans/2026-05-15-hub-ds-v2-wave-1.md`

---

## Status: PARTIAL — full Playwright QA blocked, reviewer manual QA required

Полный 38×2 Playwright MCP QA (76 скриншотов) **НЕ выполнен** в этой сессии.

**Причина:** Playwright MCP `mcp-chrome-9994fbd` profile занят параллельной Claude Code сессией (telemost-recorder branch). Это session-level lock — другой сессии нужно отпустить browser instance.

```
Error: Browser is already in use for /Users/danilamatveev/Library/Caches/ms-playwright/mcp-chrome-9994fbd, use --isolated to run multiple instances of the same browser
```

Этот блокер задокументирован, но **не считается blocker для PR open** — все автоматические gates пройдены, full visual QA остаётся для ревьюера до merge.

---

## Automated gates — все PASS

### Bundle (G11)

| Метрика | Значение |
|---|---|
| Baseline `dist/` (pre-Wave 1) | 2932 KB |
| Final `dist/` (post-Wave 1) | 2784 KB |
| **Delta** | **−148 KB** (bundle стал меньше) |
| Threshold (G11) | +250 KB |
| **Status** | ✅ PASS (negative delta) |

Уменьшение объясняется заменой `@fontsource-variable/inter` (Inter Variable) → `@fontsource-variable/dm-sans` (DM Sans Variable) — Phase 3.

### Build

- `npm run build`: ✓ exit 0
- Build time: 3.90s (Vite 7 production)
- Pre-existing warning `index-*.js > 700 KB`: существовал до Wave 1, не блокер

### TypeScript (G10)

- `npm run typecheck` (`tsc -p tsconfig.temp.json --noEmit`): ✓ exit 0
- Pre-existing TS errors (3 in CRM Drawer + marketing Button/Input) исправлены в Task 6.1

### Unit tests

- `npx vitest run`: 31 файл, 126 тестов, **all pass**, 4.85s
- Включает 21 тест на новые primitives (Phase 4) + 3 теста на PageHeader (Task 6.3) + обновлённые login tests (Task 8.x — fix для two-mode UI)

### Curl smoke (dev server)

Минимальный smoke через `curl`:

| Route | HTTP | Размер |
|---|---|---|
| `/login` | 200 | 1220b (SPA shell) |
| `/design-system-preview` | 200 | 1220b |
| `/operations/tools` | 200 | 1220b |

`<div id="root">` + `<script src="/src/main.tsx">` присутствуют — SPA mounts. JS bundle загружается отдельно (Vite dev mode).

---

## Visual QA — TODO для ревьюера

Когда Playwright instance освободится (либо запустить `--isolated` через изменённый MCP config), пройти:

### Полная матрица 38 routes × 2 темы = 76 ячеек

**LOGIN (1):** `/login`

**HUB-SHELL (12):**
- `/`, `/operations/{tools, activity, health}`
- `/community/{reviews, questions, answers, analytics}`
- `/influence/{bloggers, integrations, calendar}`
- `/analytics/rnp`

**PREVIEW (1):** `/design-system-preview`

**CATALOG (22):** `/catalog/matrix`, `/catalog/{colors, artikuly, tovary, skleyki, semeystva-cvetov, upakovki, kanaly-prodazh, sertifikaty, import, __demo__}` + 9 references + 2 redirects

**MARKETING (2, если featureFlags.marketing):** `/marketing/{promo-codes, search-queries}`

Для каждого route:
1. `browser_navigate(url)` → wait 1s
2. `browser_take_screenshot(filename=<route_safe>__<theme>.png)`
3. `browser_console_messages()` → assert errors count == 0
4. Eye-level visual check: DM Sans body, Instrument Serif h1, stone palette (no purple), light/dark visually distinct

### Smoke tests (manual)

- [ ] Theme switch на `/login` → `<html class="dark">` меняется (G3 critical — login вне AppShell)
- [ ] Cold reload `/login` в dark mode → no FOWT visible (G9)
- [ ] Toaster на любой странице: `toast.success('test')` через console → в light выглядит как light, в dark — как dark (G4)
- [ ] `localStorage.clear()` + reload → default light (G2)
- [ ] DnD на `/influence/integrations` Kanban — карточка перетаскивается без console errors
- [ ] `/design-system-preview` — все 11 primitives + extended Button variants + Input в обеих темах

### Известные observations (для проверки)

- **Sidebar primary в dark theme**: `--sidebar-primary: oklch(0.488 0.243 264.376)` (violet) — выбивается из stone-палитры остальной части dark theme. Скопировано из плана буквально. Reviewer: если выглядит как баг → отдельный follow-up commit с заменой на stone-50 (oklch(0.985 0 0)) консистентно с остальным.

- **CRM PageHeader на `/influence/*`**: 3 страницы (bloggers, integrations, calendar) используют CRM PageHeader из `components/crm/layout/PageHeader.tsx`. Per spec G6 и Wave 5 plan — оставлены как есть. Визуально могут не точно match Hub PageHeader. Это ожидаемо.

- **Inline `<kbd>` в catalog-topbar + command-palette**: audit нашёл 3 inline `<kbd>` (top-bar, catalog-topbar, command-palette). План трогает только top-bar. catalog-topbar — out of Wave 1 scope. command-palette — wave 2 candidate.

---

## Migration commits — 33 atomic on `feat/ds-v2-wave-1-spec`

Полный список через `git log --oneline main..feat/ds-v2-wave-1-spec`:

- 3 docs (spec v1, spec v2, plan) — pre-existing
- 2 Phase 1 (audit + bundle baseline)
- 1 Phase 2 (tokens + FOWT)
- 1 Phase 3 (fonts)
- 11 Phase 4 (10 primitives commits + 1 unit-tests smoke)
- 1 Phase 5 (preview)
- 4 Phase 6 (default light, theme sync, PageHeader, TopBar Kbd)
- 12 Phase 7 (Group A: 4, B: 4, C: 4 of which 3 no-op)
- 1 test fix для login.test.tsx (Phase 8)

---

## Blockers / non-blockers

**Blockers:** none. PR может быть открыт.

**Non-blockers (для backlog Wave 2+):**
1. Полный Playwright QA нужно провести вручную / после освобождения instance
2. Sidebar primary dark — verify визуально, возможно нужна замена
3. catalog-topbar + command-palette inline `<kbd>` → Wave 2 cleanup
4. CRM PageHeader unification → Wave 5

---

*Wave 1 QA report v1 · 2026-05-15 · auto-gates passed, visual QA pending Playwright availability*
