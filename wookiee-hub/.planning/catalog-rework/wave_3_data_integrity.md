# Wave 3 — Data Integrity Report

**Дата:** 2026-05-07
**Агент:** Wave 3 C3 — Data Integrity
**Supabase project:** gjvwcdtfglupewcwzfhw
**Метод:** read-only через `mcp__plugin_supabase_supabase__execute_sql`; mutations выполнялись только в bulk- и cascade-тестах с обязательным восстановлением исходного состояния (UPDATE…back / DELETE TEST_*).

---

## 1. Целостность

| # | Check | Expected | Actual | Status |
|---|-------|----------|--------|--------|
| 1.1 | `statusy.tip` распределение | model=7, artikul=3, product=6, sayt=3, color=3, lamoda=1 | model=7, artikul=3, product=6, sayt=3, color=3, lamoda=1 | PASS |
| 1.2 | `statusy WHERE nazvanie='Новый'` | 0 | 0 | PASS |
| 1.3 | Дубли `kategorii.nazvanie` | empty | empty | PASS |
| 1.4 | Дубли `kollekcii.nazvanie` | empty | empty | PASS |
| 1.5 | `modeli_osnova WHERE status_id IS NULL` | 0 | 0 | PASS |
| 1.6 | `cveta WHERE semeystvo IS NULL` | 0 | 0 | PASS |
| 1.7 | `cveta WHERE hex IS NULL` | ≤30 | 2 | PASS |
| 1.8 | `artikuly WHERE cvet_id IS NULL` | 0 (либо явно отмечено) | 4 | **FAIL (minor)** |
| 1.9 | `artikuly` с несуществующим `model_id` | 0 | 0 | PASS |
| 1.10 | `artikuly` с несуществующим `cvet_id` | 0 | 0 | PASS |
| 1.11 | `tovary WHERE artikul_id IS NULL` | 0 | 0 | PASS |
| 1.12 | `tovary` с несуществующим `artikul_id` | 0 | 0 | PASS |
| 1.13 | `modeli` с несуществующим `model_osnova_id` | 0 | 0 | PASS |
| 1.14 | `tovary.barkod` NULL/пусто | 0 | 0 | PASS |
| 1.15 | Дубли `tovary.barkod` | empty | empty | PASS |
| 1.16 | Дубли `tovary.barkod_gs1` | empty | empty | PASS |
| 1.17 | Дубли `tovary.barkod_gs2` | empty | empty | PASS |
| 1.18 | `tovary_skleyki_wb` orphan rows (skleyka) | 0 | 0 | PASS |
| 1.19 | `tovary_skleyki_wb` orphan rows (tovar) | 0 | 0 | PASS |
| 1.20 | `tovary_skleyki_ozon` orphan rows (skleyka) | 0 | 0 | PASS |
| 1.21 | `tovary_skleyki_ozon` orphan rows (tovar) | 0 | 0 | PASS |
| 1.22 | `modeli_osnova_sertifikaty` orphan (sertifikat_id) | 0 | 0 | PASS |
| 1.23 | `modeli_osnova_sertifikaty` orphan (model_osnova_id) | 0 | 0 | PASS |

### 1.8 Подробности — артикулы без `cvet_id`

| id | artikul | model_id | cvet_id | status_id |
|----|---------|----------|---------|-----------|
| 451 | Angelina/white | 38 | NULL | 10 |
| 452 | Angelina/black | 38 | NULL | 10 |
| 453 | Angelina/dark_red | 38 | NULL | 10 |
| 454 | Angelina/nude | 38 | NULL | 10 |

Все 4 относятся к одной модели (Angelina, model_id=38) и имеют статус 10 = `Архив` (product). Не критично для UI каталога: артикулы архивные, но UI ColorCard / matrix фильтр по цвету их пропустит. **Рекомендация для C4**: либо подтянуть `cvet_id` из суффикса `artikul` (`white→13`, `black→2` и т.д. через JOIN на `cveta.color`), либо переключить status на `artikul`-тип «Выводим/Архив» и явно скрыть из активного UI.

---

## 2. RLS

| Table | RLS enabled | Policies | SELECT | INSERT | UPDATE | DELETE | Status |
|-------|-------------|----------|--------|--------|--------|--------|--------|
| artikuly | true | 5 | yes | yes | yes | yes | PASS |
| cveta | true | 5 | yes | yes | yes | yes | PASS |
| fabriki | true | 5 | yes | yes | yes | yes | PASS |
| importery | true | 5 | yes | yes | yes | yes | PASS |
| kanaly_prodazh | true | 5 | yes | yes | yes | yes | PASS |
| kategorii | true | 5 | yes | yes | yes | yes | PASS |
| kollekcii | true | 5 | yes | yes | yes | yes | PASS |
| modeli | true | 5 | yes | yes | yes | yes | PASS |
| modeli_osnova | true | 5 | yes | yes | yes | yes | PASS |
| **modeli_osnova_sertifikaty** | true | **2** | yes | **NO** | **NO** | **NO** | **FAIL** |
| razmery | true | 5 | yes | yes | yes | yes | PASS |
| semeystva_cvetov | true | 5 | yes | yes | yes | yes | PASS |
| sertifikaty | true | 5 | yes | yes | yes | yes | PASS |
| **skleyki_ozon** | true | **2** | yes | **NO** | **NO** | **NO** | **FAIL** |
| **skleyki_wb** | true | **2** | yes | **NO** | **NO** | **NO** | **FAIL** |
| statusy | true | 5 | yes | yes | yes | yes | PASS |
| tovary | true | 5 | yes | yes | yes | yes | PASS |
| **tovary_skleyki_ozon** | true | **2** | yes | **NO** | **NO** | **NO** | **FAIL** |
| **tovary_skleyki_wb** | true | **2** | yes | **NO** | **NO** | **NO** | **FAIL** |
| ui_preferences (public) | true | 5 | yes | yes | yes | yes | PASS |
| upakovki | true | 5 | yes | yes | yes | yes | PASS |

### Структура политик

На «полных» 5-policy таблицах:
- `service_role_full_access_<tbl>` — postgres role, ALL (USING true / WITH CHECK true)
- `authenticated_select_<tbl>` — authenticated, SELECT
- `authenticated_insert_<tbl>` — authenticated, INSERT
- `authenticated_update_<tbl>` — authenticated, UPDATE
- `authenticated_delete_<tbl>` — authenticated, DELETE

На «коротких» 2-policy таблицах (5 шт.):
- `service_role_full_access_<tbl>` — postgres, ALL
- `authenticated_select_<tbl>` — authenticated, SELECT only

### Warning: `hub.ui_preferences`

В схеме `hub` найдена отдельная таблица `ui_preferences` — `relrowsecurity=false`, не каталоговая (не пересекается с `public.ui_preferences`). Не блокер для каталога, но фиксируется как DQ-наблюдение для команды Hub-инфры.

### BLOCKER для UI

5 таблиц без INSERT/UPDATE/DELETE для роли `authenticated`:
1. `modeli_osnova_sertifikaty` — UI ModelCard не сможет привязать/отвязать сертификаты от имени authenticated пользователя (только через service_role).
2. `skleyki_wb` — нельзя создавать/редактировать/удалять склейки WB.
3. `skleyki_ozon` — то же для OZON.
4. `tovary_skleyki_wb` — `bulkLinkTovaryToSkleyka` / `bulkUnlinkTovaryFromSkleyka` упадут на REST API при authenticated-сессии.
5. `tovary_skleyki_ozon` — то же для OZON.

**Рекомендация для C4** (миграция):
```sql
-- Для каждой из 5 таблиц:
CREATE POLICY authenticated_insert_<tbl> ON <tbl> FOR INSERT TO authenticated WITH CHECK (true);
CREATE POLICY authenticated_update_<tbl> ON <tbl> FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY authenticated_delete_<tbl> ON <tbl> FOR DELETE TO authenticated USING (true);
```

---

## 3. Bulk operations test

Все bulk-операции выполнены прямым SQL (не через UI), затем восстановлены до исходного состояния.

### 3.1 bulkUpdateModelStatus

- **Before:** `Vuki.status_id=24` (В продаже), `Audrey.status_id=24`.
- **Action:** `UPDATE modeli_osnova SET status_id=23 WHERE kod IN ('Vuki','Audrey')` → обе строки → 23 (Запуск).
- **Restore:** `UPDATE … SET status_id=24` → обе обратно к 24.
- **Status:** PASS.

### 3.2 bulkUpdateTovaryStatus (только WB канал)

- **Before:** `tovary.id IN (1,2,3)`: status_id=8, status_ozon_id=8, status_sayt_id=10.
- **Action:** `UPDATE tovary SET status_id=9 WHERE id IN (1,2,3)` → status_id→9, status_ozon_id остался 8, status_sayt_id остался 10. Канальная независимость подтверждена.
- **Restore:** `UPDATE … SET status_id=8` → возврат к baseline.
- **Status:** PASS.

### 3.3 bulkLinkTovaryToSkleyka

- **Before:** `tovary_skleyki_wb` count=1442; tovar_id 13/14/15 не связаны со skleyka_id=1.
- **Action:** `INSERT INTO tovary_skleyki_wb (tovar_id, skleyka_id) VALUES (13,1),(14,1),(15,1) ON CONFLICT DO NOTHING` → 3 строки добавлены.
- **Cleanup:** `DELETE FROM tovary_skleyki_wb WHERE skleyka_id=1 AND tovar_id IN (13,14,15)` → 3 строки удалены.
- **After cleanup:** count=1442 (baseline).
- **Status:** PASS.

### 3.4 bulkUnlinkTovaryFromSkleyka

Покрывается обратной частью 3.3 (DELETE). PASS.

> ⚠ **Caveat:** все 4 теста выполнялись через MCP `execute_sql` под service_role. Это означает, что они проверяют корректность SQL-логики, но не проверяют RLS-политики со стороны authenticated. С учётом раздела 2, для junction-таблиц (`tovary_skleyki_*`) **bulk INSERT/DELETE через клиентский Supabase SDK при authenticated-сессии будет заблокирован** до добавления INSERT/DELETE policies — см. рекомендацию выше.

---

## 4. Cascade archive verification

### Setup

```sql
modeli_osnova    kod=TEST_INT_CASCADE         status=24 (В продаже, model)
  └ modeli       kod=TEST_INT_CASCADE_V1      status=24 (model)
      └ artikuly artikul=TEST_INT_CASCADE_V1/c1  status=28 (Продается, artikul)
          ├ tovary barkod=TEST_INT_BC_001    razmer_id=1  status=8/8/30/33
          └ tovary barkod=TEST_INT_BC_002    razmer_id=2  status=8/8/30/33
```

### Cascade applied

```sql
-- 1. modeli_osnova → 26 (Архив, model)
-- 2. modeli (variations) → 26 (model)
-- 3. artikuly → 29 (Выводим, artikul)
-- 4. tovary: status_id=10, status_ozon_id=10, status_sayt_id=32, status_lamoda_id оставлен 33
```

### Verify

| Уровень | Ключ | status_id | Ожидание | Status |
|---------|------|-----------|----------|--------|
| modeli_osnova | TEST_INT_CASCADE | 26 (Архив, model) | 26 | PASS |
| modeli | TEST_INT_CASCADE_V1 | 26 (Архив, model) | 26 | PASS |
| artikuly | TEST_INT_CASCADE_V1/c1 | 29 (Выводим, artikul) | 29 | PASS |
| tovary.wb | TEST_INT_BC_001 | 10 (Архив, product) | 10 | PASS |
| tovary.wb | TEST_INT_BC_002 | 10 | 10 | PASS |
| tovary.ozon | TEST_INT_BC_001 | 10 | 10 | PASS |
| tovary.ozon | TEST_INT_BC_002 | 10 | 10 | PASS |
| tovary.sayt | TEST_INT_BC_001 | 32 (Архив, sayt) | 32 | PASS |
| tovary.sayt | TEST_INT_BC_002 | 32 | 32 | PASS |
| tovary.lamoda | TEST_INT_BC_001 | 33 (Скрыт, lamoda) | (нет архивного lamoda-статуса) | NOTE |
| tovary.lamoda | TEST_INT_BC_002 | 33 | — | NOTE |

### Cleanup

`DELETE FROM tovary/artikuly/modeli/modeli_osnova WHERE kod LIKE 'TEST_INT_%'` → 0 leftover rows.

### Status

PASS — каскадное архивирование работает корректно для уровней `modeli_osnova → modeli → artikuly → tovary` по 3 каналам (WB/OZON/sayt).

### Note: статус Lamoda

В справочнике `statusy` для `tip='lamoda'` существует только 1 запись — `Скрыт` (id=33). Архивного Lamoda-статуса нет, поэтому шаг каскада оставил `status_lamoda_id` без изменений. **Рекомендация для C4**: либо добавить `tip='lamoda', nazvanie='Архив'` в seed, либо в `service.archiveModel` маппить Lamoda на `Скрыт` и зафиксировать это в комментарии кода.

---

## 5. Sanity (post-Wave 0+1+2)

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| `to_regclass('semeystva_cvetov')` | not null | `semeystva_cvetov` | PASS |
| `to_regclass('upakovki')` | not null | `upakovki` | PASS |
| `to_regclass('kanaly_prodazh')` | not null | `kanaly_prodazh` | PASS |
| `to_regclass('ui_preferences')` | not null | `ui_preferences` | PASS |
| `to_regclass('skleyki_wb')` | not null | `skleyki_wb` | PASS |
| `to_regclass('skleyki_ozon')` | not null | `skleyki_ozon` | PASS |
| `to_regclass('tovary_skleyki_wb')` | not null | `tovary_skleyki_wb` | PASS |
| `to_regclass('tovary_skleyki_ozon')` | not null | `tovary_skleyki_ozon` | PASS |
| `to_regclass('modeli_osnova_sertifikaty')` | not null | `modeli_osnova_sertifikaty` | PASS |
| `count(statusy)` | ≥23 | 23 | PASS |
| `count(semeystva_cvetov)` | =5 | 5 | PASS |
| `count(upakovki)` | =10 | 10 | PASS |
| `count(kanaly_prodazh)` | =4 | 4 | PASS |

### Baseline counts (post-test)

| Table | Count |
|-------|-------|
| modeli_osnova | 56 |
| modeli | 75 |
| artikuly | 553 |
| tovary | 1473 |
| cveta | 146 |
| tovary_skleyki_wb | 1442 |
| tovary_skleyki_ozon | 1345 |

Все совпадают с Wave 0 baseline (нет утечки тестовых данных).

---

## 6. Summary

- **Pass:** 49 чеков
  - Целостность: 22/23
  - RLS: 16/21
  - Bulk: 4/4
  - Cascade: 1/1 (с note по Lamoda)
  - Sanity: 13/13
- **Fail:** 6
  - **1.8** `artikuly` — 4 строки с `cvet_id IS NULL` (Angelina/*); minor, архивные.
  - **2.x** RLS — 5 таблиц без INSERT/UPDATE/DELETE policies для `authenticated`: `modeli_osnova_sertifikaty`, `skleyki_wb`, `skleyki_ozon`, `tovary_skleyki_wb`, `tovary_skleyki_ozon`. **BLOCKER** для UI bulk-операций со склейками и сертификатами при authenticated-сессии.
- **Warnings:** 2
  - `hub.ui_preferences` — отдельная таблица в `hub`-схеме с `RLS=false`. Вне scope каталога, фиксируется как DQ-наблюдение.
  - В справочнике `statusy` для `tip='lamoda'` только 1 запись («Скрыт»). При cascade archive Lamoda-статус не меняется. Решить: добавить «Архив» для lamoda в seed или явно маппить на «Скрыт».

### Рекомендации для C4 (приоритет)

1. **BLOCKER — RLS-миграция**: добавить INSERT/UPDATE/DELETE policies для `authenticated` на 5 junction/reference таблиц (см. раздел 2). Это разблокирует bulkLink/Unlink, CRUD склеек и привязку сертификатов в UI.
2. **MAJOR — Lamoda статусы**: добавить `Архив` в `statusy WHERE tip='lamoda'` или зафиксировать маппинг `Архив → Скрыт` в `service.archiveModel`.
3. **MINOR — Angelina cvet_id**: 4 архивных артикула без цвета. Подтянуть `cvet_id` из суффикса (`/white`, `/black`, `/dark_red`, `/nude`) через JOIN с `cveta.color` в одной миграции.
