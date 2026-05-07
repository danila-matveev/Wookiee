# RNP Analytics API

Backend для аналитической панели **Рука на Пульсе (РНП)** в Wookiee Hub. Недельная аналитика по моделям WB.

> Полная документация сервиса (источники данных, известные ограничения, TODO, файлы фронта/бэка) — в [services/analytics_api/README.md](../../services/analytics_api/README.md).
> Здесь — только endpoint-контракт.

**Base URL (prod):** `https://analytics-api.os.wookiee.shop`
**Base URL (Docker network):** `http://analytics_api:8005`
**Auth:** `Authorization: Bearer <jwt>` (Supabase) **или** `X-Api-Key: <key>`

## Endpoints

| Метод | Путь | Параметры | Возвращает |
|---|---|---|---|
| GET | `/health` | — | `{"status":"ok"}` (без auth) |
| GET | `/api/rnp/models` | `marketplace=wb` | список моделей для дропдауна |
| GET | `/api/rnp/weeks` | см. ниже | недельная аналитика |

### `GET /api/rnp/models`

Возвращает список активных моделей (статусы 8/9/14 в Supabase `modeli`, `artikul_modeli IS NOT NULL`).

```json
{
  "marketplace": "wb",
  "models": [
    {"label": "Alice", "value": "alice"},
    {"label": "Vuki",  "value": "vuki"},
    {"label": "Wendy", "value": "wendy"},
    ...
  ]
}
```

- `label` — отображаемое имя (`MIN(kod)` из modeli)
- `value` — display key (`LOWER(MIN(kod))`), используется как параметр `model` в `/weeks`

### `GET /api/rnp/weeks`

Параметры:

| Параметр | Тип | Обязательный | Описание |
|---|---|---|---|
| `model` | string | да | display key из `/models` (например, `wendy`, `vuki`) |
| `date_from` | date (YYYY-MM-DD) | да | начало периода (выровняется на понедельник) |
| `date_to` | date (YYYY-MM-DD) | да | конец периода (выровняется на воскресенье) |
| `marketplace` | string | нет | `wb` (по умолчанию). Только `wb` поддерживается. |
| `buyout_forecast` | float `[0,1]` | нет | прогноз выкупа для расчёта прогноза маржи. По умолчанию — средний выкуп периода. |

Ограничения:
- Период не более 91 дня (13 недель). 400 если больше.
- `marketplace != wb` → 501.

Ответ:

```json
{
  "model": "vuki",
  "marketplace": "wb",
  "date_from": "2026-03-09",
  "date_to":   "2026-05-10",
  "buyout_forecast_used": 0.6532,
  "ext_ads_available": true,
  "weeks": [
    {
      "week_start": "2026-03-09",
      "week_end":   "2026-03-15",
      "week_label": "09.03–15.03",
      "phase": "norm",
      "orders_qty": 776, "orders_rub": 2_103_000.0, ...
      "buyout_pct": 65.3, "sales_qty": 506, "sales_rub": ...
      "clicks_total": ..., "cart_total": ...,
      "funnel_orders_qty": 685, "funnel_buyouts_qty": 72,
      "cr_total": ..., "cr_card_to_cart": ..., "cr_cart_to_order": ...,
      "adv_total_rub": ..., "drr_total_from_sales": ...
      "adv_internal_rub": ..., "ctr_internal": ..., "romi_internal": ...
      "blogger_rub": 12000.0, "blogger_views": 20500.0, "blogger_orders": 12.0,
      "vk_sids_rub": ..., "sids_contractor_rub": ..., "yandex_contractor_rub": ...,
      "margin_before_ads_rub": ..., "margin_pct": ...,
      "sales_forecast_rub": ..., "margin_forecast_pct": ...
    }
  ]
}
```

Полный список полей — см. `aggregate_to_weeks()` в [shared/data_layer/rnp.py](../../shared/data_layer/rnp.py).

**Важно про заказы:** в ответе два разных счётчика — `orders_qty` (из `abc_date`, для финансов) и `funnel_orders_qty` (из `content_analysis`, для воронки). Они могут различаться на 10–15%. Все CR считаются intra-source — только из `content_analysis`. См. раздел "Воронка vs финансы" в [services/analytics_api/README.md](../../services/analytics_api/README.md).

## Auth

Один из:
- `Authorization: Bearer <token>` — JWT Supabase из `supabase.auth.getSession()`. Если `SUPABASE_JWT_SECRET` задан — проверяется HS256 + `aud=authenticated`. Иначе fallback: декод без подписи + проверка `role=authenticated`.
- `X-Api-Key: <ANALYTICS_API_KEY>` — для скриптов.

Без обоих → 403.

## Ошибки

| Код | Когда |
|---|---|
| 400 | Период > 91 дней |
| 401 | Token expired |
| 403 | Auth header отсутствует / неверен |
| 500 | `ANALYTICS_API_KEY not configured` (при попытке X-Api-Key auth) |
| 501 | `marketplace != wb` |

## Пример запроса (curl)

```bash
curl "https://analytics-api.os.wookiee.shop/api/rnp/weeks?model=wendy&date_from=2026-03-09&date_to=2026-05-10" \
  -H "X-Api-Key: $ANALYTICS_API_KEY"
```

## Связанные документы

- [services/analytics_api/README.md](../../services/analytics_api/README.md) — полная документация сервиса
- [docs/database/DATA_QUALITY_NOTES.md](../database/DATA_QUALITY_NOTES.md) — известные расхождения данных (CRO ~20% vs PowerBI)
- [shared/data_layer/rnp.py](../../shared/data_layer/rnp.py) — слой данных (SQL + Sheets + агрегация)
