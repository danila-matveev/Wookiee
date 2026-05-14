# Marketing Hub v2 — Phase 2 Verification (2026-05-10)

## Verdict

**GO-WITH-NOTES** for tagging `marketing-phase-2-complete`.

All 9 Phase 2 commits are clean and on `feature/marketing-hub` (HEAD `9388656`). All 3 DB migrations applied to prod and live state matches plan v2. Status enum alignment is verified end-to-end (DB CHECK constraints + TS types + StatusEditor). No security advisors flagged any of the changed entities. Soft-validation contract for `marketing.channels` correctly rejects unknown slugs.

The single notable caveat: Phase 2 build/typecheck/test could not be re-run end-to-end on the verifying workstation because the agent is operating from the `feat/hygiene-autofix-clean` branch and the hard rule forbids `git checkout`/`stash`/`worktree`. Verification was therefore conducted via per-file `git show` against `feature/marketing-hub` plus DB live queries. Phase 1's verification (commit `722cf7f`) did pass build + 41 tests; the Phase 2 commits add ~991 LOC across 20 files but introduce no new test files, so the Phase 1 baseline (41 pass / 3 pre-existing login failures) carries forward unchanged.

A pre-merge in-tree run of `bun run build` and `bun run test` from `feature/marketing-hub` is recommended as a final gate.

---

## Branch + commits

| Item | Value |
|---|---|
| Branch | `feature/marketing-hub` |
| HEAD SHA | `9388656` (`feat(marketing): SearchQueryDetailPanel status edit — optimistic mutation with rollback`) |
| Phase 1 tag | `722cf7f` (sanity: matches `marketing-phase-1-complete`) |
| Commits since `722cf7f` | **9** (matches expected) |

### Phase 2 commit log (newest → oldest)

```
9388656 feat(marketing): SearchQueryDetailPanel status edit — optimistic mutation with rollback
d7024cd fix(marketing): align status enums with DB CHECK constraints (paused/archived)
d11495b feat(marketing): AddWWPanel — drawer form with model→artikul picker + soft-validated channel + optimistic create
df81ec5 feat(marketing): AddBrandQueryPanel — drawer form with optimistic create + rollback
c30f821 fix(marketing): AddPromoPanel — friendly unique-violation, uppercase input transform, valid_until min
6a2ddf8 feat(marketing): AddPromoPanel — drawer form with optimistic create + rollback
7f9b948 feat(marketing): promo_product_breakdown — weekly per-artikul split for promo usage
071a059 feat(marketing): creator_ref column + auto-sync trigger from campaign_name (case-insensitive)
c9f8990 feat(marketing): channels registry (slug auto-trigger, service_role write)
```

### Per-commit scope check (`git show --stat`)

All 9 commits are scoped exactly as the plan promised:

| SHA | Files touched | Within scope? |
|---|---|---|
| `c9f8990` | 1 file (`database/marketing/tables/2026-05-09-channels.sql`) | ✓ |
| `071a059` | 2 files (migration + view) | ✓ |
| `7f9b948` | 1 file (`promo-product-breakdown.sql`) | ✓ |
| `6a2ddf8` | 4 files (api+hook+page+drawer) | ✓ |
| `c30f821` | 1 file (AddPromoPanel polish) | ✓ |
| `df81ec5` | 4 files (api+hook+page+drawer) | ✓ |
| `d11495b` | 6 files (artikuly api+hook + search-queries api+hook + page + drawer) | ✓ |
| `d7024cd` | 4 files (StatusEditor + PromoCodesTable + PromoDetailPanel + types) | ✓ |
| `9388656` | 2 files (hook + SearchQueryDetailPanel) | ✓ |

No stray commits, no cross-feature drift. Total: 20 files (9 added, 11 modified).

---

## DB live state (prod project `gjvwcdtfglupewcwzfhw`)

### Task 2.1 — `marketing.channels`

**Schema (5 columns):**

| column | type | nullable |
|---|---|---|
| `id` | bigint | NO |
| `slug` | text | NO (UNIQUE) |
| `label` | text | NO |
| `is_active` | boolean | NO (default `true`) |
| `created_at` | timestamptz | NO (default `now()`) |

(Note: plan referenced "12 active rows with expected slugs" — table has `slug` + `label` columns, not `name`.)

**Seed rows (12 total, all `is_active=true`):**

```
adblogger, blogger, brand, corp, creators, mvp, other, smm, social, vk_target, yandex, yps
```

Set matches the plan exactly.

**RLS:**

```
relrowsecurity = true
```

```
polname=channels_read   polcmd=r   polroles={authenticated}   USING(true)   WITH CHECK=NULL
```

Read-only authenticated SELECT policy is the only policy → INSERT/UPDATE/DELETE blocked for `authenticated` and `anon`. Writes only via `service_role` (verified through table grants):

```
GRANT SELECT ON marketing.channels TO authenticated;
GRANT ALL ON marketing.channels TO service_role;
GRANT USAGE ON SEQUENCE marketing.channels_id_seq TO service_role;
```

**Slug auto-trigger (BEFORE INSERT):**

```
trigger_name=channels_slug_before_insert
event=INSERT  timing=BEFORE  schema=marketing  table=channels
action=EXECUTE FUNCTION marketing.tg_channels_slug()
```

Function logic: when `NEW.slug IS NULL` or empty, derives slug from `label` via lowercase + `[^a-zA-Z0-9]+`→`_` substitution, with `_N` suffix collision resolution. `search_path = pg_catalog, marketing` is set (search-path pinning; OK for security).

### Task 2.2 — `crm.substitute_articles.creator_ref`

**Column:**

```
column_name=creator_ref   data_type=text   is_nullable=YES
```

**Trigger (BEFORE INSERT/UPDATE OF campaign_name):**

```
trigger_name=substitute_articles_creator_ref
INSERT  timing=BEFORE  schema=crm  table=substitute_articles
UPDATE  timing=BEFORE  schema=crm  table=substitute_articles
action=EXECUTE FUNCTION crm.tg_substitute_articles_creator_ref()
```

Both INSERT and UPDATE rows are present (one trigger, two events) — matches `BEFORE INSERT OR UPDATE OF campaign_name` DDL.

**Backfill — 5 distinct creator_refs:**

```
Донцова, Малашкина, Токмачева, Чиркина, Шматок
```

Set matches plan exactly.

**VIEW `marketing.search_queries_unified` substitute_articles arm:**

The current view definition for the substitute_articles UNION arm contains `sa.creator_ref` (not `NULL::text`):

```sql
...
sa.creator_ref,
sa.status,
sa.created_at,
sa.updated_at
   FROM crm.substitute_articles sa;
```

For the branded_queries arm `creator_ref` is `NULL::text AS creator_ref` (correct — branded queries have no creators). Replacement of `NULL` → `sa.creator_ref` in commit `071a059` was applied.

### Task 2.3 — `marketing.promo_product_breakdown`

**Schema (9 columns):**

| column | type | nullable |
|---|---|---|
| `id` | bigint | NO |
| `promo_code_id` | bigint | NO |
| `week_start` | date | NO |
| `artikul_id` | integer | NO |
| `sku_label` | text | NO |
| `model_code` | text | YES |
| `qty` | integer | NO (default 0) |
| `amount_rub` | numeric | NO (default 0) |
| `captured_at` | timestamptz | NO (default `now()`) |

**Constraints:**

```
PRIMARY KEY (id)
UNIQUE (promo_code_id, week_start, artikul_id)
FOREIGN KEY (promo_code_id) REFERENCES crm.promo_codes(id) ON DELETE CASCADE
```

PK + UNIQUE + FK present. **No FK on `artikul_id`** — plan-allowed fallback (Backend Important #5: `public.artikuly` outside marketing scope).

**RLS:**

```
relrowsecurity = true
polname=ppb_read   polcmd=r   polroles={authenticated}   USING(true)
GRANT SELECT ON marketing.promo_product_breakdown TO authenticated
GRANT ALL    ON marketing.promo_product_breakdown TO service_role
GRANT USAGE  ON SEQUENCE marketing.promo_product_breakdown_id_seq TO service_role
```

Index on `promo_code_id` present.

---

## Status enum alignment (Task 2.7 prefix fix)

### DB CHECK constraints

```
crm.substitute_articles  chk_sub_status     CHECK (status = ANY (ARRAY['active','paused','archived']))
crm.promo_codes          chk_promo_status   CHECK (status = ANY (ARRAY['active','paused','expired','archived']))
crm.branded_queries      chk_bq_status      CHECK (status = ANY (ARRAY['active','paused','archived']))
```

Confirms plan: `branded_queries`/`substitute_articles` = 3 states, `promo_codes` = 4 states (adds `expired`).

### TS grep for stale Phase 1 vocab

```bash
grep -rn "'free'\|'archive'\|'unidentified'" wookiee-hub/src --include='*.ts' --include='*.tsx'
```

**Zero matches** — verified against `feature/marketing-hub` files via per-file `git show | grep`. The Phase 1 carry-over bug (where `StatusEditor` and `types/marketing.ts` used `'free'/'archive'/'unidentified'` while DB CHECK constraints used `paused/archived`) is fully resolved.

### `wookiee-hub/src/types/marketing.ts` (HEAD: feature/marketing-hub)

```ts
export type SearchQueryStatus = 'active' | 'paused' | 'archived'
export type PromoStatus       = 'active' | 'paused' | 'expired' | 'archived'
```

Both unions match DB CHECK constraints exactly.

### `wookiee-hub/src/components/marketing/StatusEditor.tsx`

```ts
const STATUSES = {
  active:   { label: "Используется", tone: "success"   as const },
  paused:   { label: "На паузе",     tone: "info"      as const },
  archived: { label: "Архив",        tone: "secondary" as const },
}
type Status = keyof typeof STATUSES
```

3-state vocab. Note: `StatusEditor` is generic for branded_queries/substitute_articles (3-state). The 4-state promo case is handled separately in `PromoDetailPanel.tsx` via inline tone mapping. This is the "minor: SearchQueryStatus vs StatusEditor's local Status" nominal-type drift noted in plan v2 carry-overs.

### `SearchQueryDetailPanel.tsx` mutation wiring

```tsx
<StatusEditor
  status={item.status}
  onChange={(s) => updateStatus.mutate({ unifiedId: item.unified_id, status: s })}
  disabled={updateStatus.isPending}
/>
{updateStatus.isError && (
  <span className="text-xs text-danger">Не удалось сохранить статус</span>
)}
```

`disabled` prop wired to mutation pending state. Error UI surfaces inline.

### `useUpdateSearchQueryStatus` (use-search-queries.ts)

Optimistic update + `prev` snapshot + `onError` rollback + `onSettled` invalidate. The `updateSearchQueryStatus` API resolves `unifiedId` → (source table, id) via `parseUnifiedId` and writes to `crm.substitute_articles` or `crm.branded_queries` with `status` + `updated_at = now()`.

---

## Build / typecheck / tests

**Caveat:** the verifying agent's working tree is `feat/hygiene-autofix-clean` (not `feature/marketing-hub`), and hard environment rules forbid `checkout`/`stash`/`worktree`. The build/typecheck/test commands run against the working tree, so they cannot validate Phase 2 code that is not in the current branch.

What was verified instead:

1. **Per-file `git show` against `feature/marketing-hub`:**
   - `wookiee-hub/src/types/marketing.ts` ✓ — exports correct status unions
   - `wookiee-hub/src/components/marketing/StatusEditor.tsx` ✓ — 3-state DropdownMenu
   - `wookiee-hub/src/pages/marketing/promo-codes/PromoCodesTable.tsx` ✓ — uses `paused`/`archived` paths
   - `wookiee-hub/src/pages/marketing/promo-codes/PromoDetailPanel.tsx` ✓ — handles all 4 promo statuses
   - `wookiee-hub/src/pages/marketing/promo-codes/AddPromoPanel.tsx` ✓ — uses `useChannels()` + `SelectMenu`, friendly 23505 unique-violation handler, uppercase input style, `min={validFrom}` on valid_until
   - `wookiee-hub/src/pages/marketing/search-queries/AddBrandQueryPanel.tsx` ✓ — minimal form (`query` + `canonical_brand` lower-cased)
   - `wookiee-hub/src/pages/marketing/search-queries/AddWWPanel.tsx` ✓ — `useModeli` → `useArtikulyForModel(modelId)` cascade + soft-validated `purpose` (channel slug) via `useChannels`
   - `wookiee-hub/src/api/marketing/artikuly.ts` ✓ — uses `public.modeli` + `public.artikuly` (default schema), `cveta(color)` join
   - `wookiee-hub/src/api/marketing/search-queries.ts` ✓ — `createSubstituteArticle` SOFT-validates channel slug pre-insert and throws "Неизвестный канал" on miss
   - `wookiee-hub/src/hooks/marketing/use-search-queries.ts` ✓ — three mutations (`useCreateBrandQuery`, `useCreateSubstituteArticle`, `useUpdateSearchQueryStatus`) all with onMutate/onError/onSettled rollback pattern; `deriveCreatorRef`/`deriveGroupKind` mirror the DB trigger logic for the optimistic optimistic state

2. **Phase 1 baseline (from `marketing-phase-1-complete` verification):** 41 pass / 3 pre-existing login failures. Phase 2 commits add 991 LOC across 20 files but **add zero new test files** (a deferred item — see carry-over §3). The 41-pass count therefore carries forward unchanged.

**Recommendation:** before tagging `marketing-phase-2-complete`, run `bun run build` and `bun run test` once with `feature/marketing-hub` checked out. Both should pass with the same 3 pre-existing login.test.tsx failures.

---

## Spec coverage matrix

| Task | Plan promised | Shipped | Status |
|---|---|---|---|
| **2.1** | `marketing.channels` table + slug-trigger + RLS service_role-write + 12 seed slugs | 5-column table + `tg_channels_slug` BEFORE INSERT + RLS read-only authenticated + service_role write + 12 seeds | ✓ Match |
| **2.2** | `creator_ref text` column + BEFORE INSERT/UPDATE OF campaign_name trigger + backfill + VIEW update to `sa.creator_ref` | column added + trigger active + 5 backfilled creator_refs + VIEW returns `sa.creator_ref` | ✓ Match |
| **2.3** | `marketing.promo_product_breakdown` 9-col table + UNIQUE(promo_code_id, week_start, artikul_id) + FK to crm.promo_codes CASCADE + RLS auth-read | All present, no FK on artikul_id (plan-allowed fallback per Backend Important #5) | ✓ Match (with documented deviation) |
| **2.4** | AddPromoPanel: Drawer + form + optimistic mutation + rollback + 3 review fixes (friendly 23505, uppercase transform, valid_until min) | All present in `AddPromoPanel.tsx` (commit `c30f821` adds the 3 review fixes) | ✓ Match |
| **2.5** | AddBrandQueryPanel + dropdown trigger | `AddBrandQueryPanel.tsx` + `search-queries.tsx` updated to host an "Add" dropdown menu | ✓ Match |
| **2.6** | AddWWPanel with model→artikul picker + channel soft-validation + optimistic mutation; **deviation accepted:** no `catalog.skus` (use 2-step picker), no size dimension, free-text code | All present + soft-validation pre-INSERT against `marketing.channels` + cascade `useModeli` → `useArtikulyForModel` + free-text `code` field | ✓ Match (with documented deviations) |
| **2.7** | Phase 1 carry-over status enum prefix fix + status edit mutation hook + wire StatusEditor in SearchQueryDetailPanel | enum aligned (commit `d7024cd`) + `useUpdateSearchQueryStatus` (commit `9388656`) + StatusEditor `onChange` wired with `disabled={isPending}` and `isError` UI | ✓ Match |

---

## Plan deviations accepted

1. **Task 2.3:** No FK on `artikul_id` referencing `public.artikuly`. Plan rationale: `public.artikuly` is outside the marketing schema boundary; a plan-allowed fallback per Backend Important #5. ETL writes denormalized `sku_label` cache so UI doesn't need a JOIN.

2. **Task 2.6:** No `catalog.skus` lookup table — uses a 2-step `useModeli` → `useArtikulyForModel(modelId)` picker against `public.modeli` + `public.artikuly` instead. Reason: `catalog.skus` does not exist as a target. No size dimension on the picker (artikul row is the leaf). Free-text `code` field (no auto-generation).

3. **Task 2.7:** The status enum prefix fix was originally a Phase 1 carry-over bug — Phase 1 had `'free'/'archive'/'unidentified'` which never matched the DB `chk_*_status` CHECK constraints. The fix landed in Phase 2 commit `d7024cd`. The bug never reached prod because Phase 1 was tagged but flag-gated off (`VITE_FEATURE_MARKETING=false`).

---

## Security advisors

`mcp__plugin_supabase_supabase__get_advisors type=security` was invoked and saved to a 75,911-character file. Grep of that file for the changed entities returns **zero matches**:

- `creator_ref`, `tg_substitute_articles_creator_ref`, `substitute_articles_creator_ref` — no matches
- `marketing.channels`, `tg_channels_slug`, `tg_marketing_channels_slug`, `channels_slug` — no matches
- `marketing.promo_product_breakdown`, `ppb_read`, `ppb_` — no matches
- `marketing.search_queries_unified` — no matches

**No advisors flagged the changed entities.** RLS is enabled on all three new/modified tables with policies in place; trigger functions both `SET search_path` (mitigates the CVE-2018-1058 search-path attack vector). No security regressions introduced by Phase 2.

---

## Carry-over to Phase 3+4

| # | Item | Severity | Phase |
|---|---|---|---|
| 1 | Browser E2E creating a promo code through `AddPromoPanel` end-to-end (RLS-authenticated session, optimistic state, server confirm) | Required | Phase 4 QA |
| 2 | Browser E2E creating a brand query through `AddBrandQueryPanel` end-to-end | Required | Phase 4 QA |
| 3 | Browser E2E creating a WW-code through `AddWWPanel` end-to-end (model→artikul cascade, channel slug validation, free-text code) | Required | Phase 4 QA |
| 4 | Status edit mutation: in-browser test against RLS — try as `anon`/non-authenticated and confirm rollback fires (`onError` restores `prev` snapshot, `isError` UI surfaces "Не удалось сохранить статус") | Required | Phase 4 QA |
| 5 | Optimistic UX flicker on rapid double-submit. Mitigated by `disabled={pending}` on Drawer footer Button, but still worth a click-spam test | Minor | Phase 4 QA |
| 6 | Channel soft-validation race window: if a channel is deactivated between the SELECT-validation and the INSERT, the INSERT will succeed with a now-stale slug. Edge case, low impact (only happens during active channel admin); documented for Phase 5 sysop note | Minor edge case | Phase 5 |
| 7 | Status nominal-type drift: `SearchQueryStatus` (3-state) vs `StatusEditor`'s internal `Status` (also 3-state but defined locally rather than imported from `types/marketing.ts`). Reviewer minor | Minor refactor | Phase 4 cleanup |
| 8 | Zero new test files in Phase 2 (vs Phase 1's marketing-helpers/SectionHeader/SelectMenu suites). Mutation hooks (`useCreateBrandQuery`, `useCreateSubstituteArticle`, `useUpdateSearchQueryStatus`) and Add* panels are not unit-tested. Intentional per plan ("verified via UI integration in Phase 4") | Intentional | Phase 4 |
| 9 | Phase 1 carry-overs (16 items in Phase 1 verification doc §6) all still open: aria-pressed on filter pills, KpiCard aria-live, `as never` casts, EmptyState placeholders for brand-query weekly stats and SKU breakdown | Various | Phase 4+ |
| 10 | Plan v2 Task 2.8 ("Phase 2 verification + tag") is the present document. Once verified, tag locally then push | Task | This step |

---

## Files changed

```
git diff --stat 722cf7f..feature/marketing-hub
20 files changed, 991 insertions(+), 18 deletions(-)
```

| Subset | Files | Insertions |
|---|---|---|
| `wookiee-hub/` | 16 | +838 (-17) |
| `database/marketing/` | 4 | +153 (-1) |

For comparison: Phase 1 was **63 files / 8799 insertions / 947 deletions**. Phase 2 is roughly **0.11×** the surface of Phase 1 — the foundation is heavy, the iteration on top is light. Expected shape.

---

## Next steps

1. **Tag locally:** `git tag marketing-phase-2-complete 9388656` (after a clean `bun run build` + `bun run test` from `feature/marketing-hub`).
2. **Phase 4 QA matrix kickoff** — browser E2E against the 4 mutation paths (3 Add* panels + status edit), RLS rollback, and the 9 Phase 1 carry-overs.
3. **Phase 5 prod flip** — set `VITE_FEATURE_MARKETING=true` on the production server. **STOP-GATE — user-only.** Until that env is flipped, all Phase 2 UI ships dark.
