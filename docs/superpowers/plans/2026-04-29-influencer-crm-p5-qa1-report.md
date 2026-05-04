# P5 QA1 Local Report (2026-04-29)

QA1 mandatory gate (local portion) for Influencer CRM Phase 5 — Sync & Ops.
This run covers everything that does NOT need a live BFF or user auth:
unit tests, type check, production build, Playwright against MSW mocks, and
a new smoke spec for the /ops dashboard.

Branch: `feat/influencer-crm-p5`. Worktree: `/tmp/wookiee-crm-p5`.
Run host: macOS (darwin 25.3.0). Node: pnpm-managed via repo.

## Vitest

- Result: 24 / 24 passed (14 test files).
- Duration: 2.26 s (transform 1.03 s, setup 2.87 s, import 3.52 s, tests 1.10 s).
- No regressions from /ops additions.

Snippet:

```
RUN  v4.1.5 /private/tmp/wookiee-crm-p5/services/influencer_crm_ui

Test Files  14 passed (14)
     Tests  24 passed (24)
  Duration  2.26s
```

## TypeCheck

- 0 errors / 0 warnings (`tsc -b`).
- Clean exit, no output.

Snippet:

```
> influencer_crm_ui@0.0.1 typecheck
> tsc -b
```

## Build

- Bundle size: 532.14 kB (JS) + 34.92 kB (CSS).
- Gzip: 164.95 kB (JS) + 6.98 kB (CSS).
- HTML: 0.75 kB / gzip 0.40 kB.
- Built in: 245 ms (after `tsc -b`).
- 2130 modules transformed.

Note (informational, not a regression): vite reports the JS chunk is above
500 kB pre-gzip. Gzip is 165 kB which is fine for an internal CRM. P6 can
introduce route-level dynamic imports if we need to chase Lighthouse scores.

Snippet:

```
dist/index.html                   0.75 kB │ gzip:   0.40 kB
dist/assets/index-D5QGp5kY.css   34.92 kB │ gzip:   6.98 kB
dist/assets/index-D1i1ve92.js   532.14 kB │ gzip: 164.95 kB

✓ built in 245ms
```

## Playwright (mock mode)

`PLAYWRIGHT_LIVE_BFF` left UNSET — all requests intercepted via
`page.route('http://api.test/api/**')`.

- Golden paths (pre-existing): 11 / 11 passed in 13.3 s.
  - GP-1 bloggers list + detail expand.
  - GP-2 kanban board.
  - GP-3 search.
  - GP-4 brief edit.
  - 7 a11y golden specs (`/bloggers`, `/integrations`, `/brief/:id`,
    `/calendar`, `/briefs`, `/slices`, `/products`, `/search?q=test`).
- New /ops smoke spec: PASS (806 ms).
- Full suite after addition: 12 / 12 passed in 13.4 s.

The /ops spec mocks `GET /ops/health` inline (Playwright matches routes
last-registered first, so it wins over `mockApi`'s catch-all). It asserts:

- 3 KpiCard labels: "ETL — последний запуск", "Свежесть MV", "Сбои за 24ч".
- Cron table renders 4 `<tbody>` rows with the expected job names.
- Retention section visible with `audit_log > 90 дн.` and `snapshots > 365 дн.`.

Snippet:

```
✓  1 [desktop-chrome] › e2e/golden-ops.spec.ts:14:1 › GP-Ops: /ops dashboard renders KPIs, cron table and retention queue (806ms)

  1 passed (2.2s)
```

Full suite after addition:

```
✓  12 [desktop-chrome] › e2e/golden-a11y.spec.ts:16:3 › a11y: /search?q=test has no critical or serious violations (1.5s)

  12 passed (13.4s)
```

## Open issues

- None blocking. All checks PASS on first attempt — no fixes were applied.
- Informational: dev-server console emits axe color-contrast warnings on
  several routes (existing behaviour, not introduced by P5; the a11y golden
  specs assert only `critical`/`serious` violations and pass clean).

## Conclusion

- **QA1 LOCAL: PASS.**
  - Vitest 24/24, TypeCheck clean, build success, Playwright 12/12 (incl. new /ops spec).
- **QA1 LIVE-BFF portion (gstack-qa, gstack-design-review, dogfood): NOT RUN**
  — requires user auth + a running BFF (uvicorn) hitting Supabase. To be
  executed in a follow-up session with the user present.
