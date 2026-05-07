# Analytics API

FastAPI-сервис для аналитической панели **Рука на Пульсе (РНП)** в Wookiee Hub.
Отдаёт недельную аналитику по моделям WB: заказы, выкуп, воронка, реклама, маржа.

- **Контейнер:** `analytics_api` (порт 8005, только в Docker network)
- **Внешний URL:** `https://analytics-api.os.wookiee.shop` (через Caddy)
- **Compose-файл:** `deploy/docker-compose.yml`, сервис `analytics-api`
- **Логи:** `docker logs analytics_api`

## Endpoints

| Метод | Путь | Параметры | Возвращает |
|---|---|---|---|
| GET | `/health` | — | `{"status":"ok"}` |
| GET | `/api/rnp/models` | `marketplace=wb` | `{"models": [{"label": "Vuki", "value": "vuki"}, ...]}` |
| GET | `/api/rnp/weeks` | `model`, `date_from`, `date_to`, `marketplace=wb`, `buyout_forecast?` | `{"weeks": [...], "ext_ads_available": bool, ...}` |

Полный пример ответа `/api/rnp/weeks` — см. поля в `aggregate_to_weeks()` в [shared/data_layer/rnp.py](../../shared/data_layer/rnp.py).

## Аутентификация

Поддерживается **два способа** (один из):

1. **Bearer JWT** (для Hub frontend)
   `Authorization: Bearer <supabase_session_token>`
   Если `SUPABASE_JWT_SECRET` задан — проверка подписи HS256, audience=`authenticated`.
   Если не задан — fallback: декод без подписи + проверка `role=authenticated`.

2. **X-Api-Key** (для скриптов и cron)
   `X-Api-Key: $ANALYTICS_API_KEY`

Без обоих заголовков → 403.

## Источники данных

```
GET /api/rnp/weeks?model=vuki&...
        │
        ├─► Supabase modeli (resolve_wb_key) ─► "vuki" → "компбел-ж-бесшов"
        │
        ├─► WB DB (legacy 89.23.119.253) ────► daily rows из abc_date, orders,
        │                                         content_analysis, wb_adv
        │   фильтр: LOWER(SPLIT_PART(article,'/',1)) = wb_key
        │
        └─► Google Sheets ───────────────────► внешняя реклама + блогеры
            ├─ RNP_EXT_ADS_SHEET_ID         (ADS/ADB/EPS — VK SIDS, Яндекс)
            └─ RNP_BLOGGERS_SHEET_ID        (лист "Блогеры" — посевы)
            фильтр: row[model_col].lower().strip() == display_key
```

### Display key vs WB key

**Это критическое разделение.** В разных системах модели названы по-разному:

| Система | Vuki называется | Источник |
|---|---|---|
| Supabase `modeli.kod` | `Vuki` (display label) | продуктовая матрица |
| Supabase `modeli.artikul_modeli` | `компбел-ж-бесшов/` | префикс артикула в WB |
| WB DB `abc_date.article` | `компбел-ж-бесшов/SKU123` | реальные артикулы |
| Google Sheet "Блогеры" col 6 | `Vuki` | ручной ввод маркетологами |

API использует **display key** (`vuki` = `LOWER(MIN(kod))`) как универсальный идентификатор:
- Для WB DB → `resolve_wb_key("vuki")` → `"компбел-ж-бесшов"` → SQL-запрос
- Для Sheets → сравнение `row[model_col].lower() == "vuki"` → matches "Vuki" ✓

Для большинства моделей display key = WB key (например, "wendy" → "wendy"). Для Vuki и Set-моделей с пробелами они различаются.

### Фильтр моделей в дропдауне

В `/api/rnp/models` попадают только модели со статусами:
- `8` — Продается
- `9` — Выводим
- `14` — Запуск

Исключаются: `10` (Архив), `12` (План). Модели с `artikul_modeli IS NULL` пропускаются (например, Charlotte — сейчас не появится в дропдауне, пока не заполнят `artikul_modeli`).

## Конфигурация

`.env` на сервере (`/home/danila/projects/wookiee/.env`):

```dotenv
ANALYTICS_API_KEY=<32-байтный hex>
SUPABASE_JWT_SECRET=<from Supabase Dashboard → Settings → API>
RNP_EXT_ADS_SHEET_ID=1h0NeYw_5Cn7mkI03QxUk_zkvJ7NGV1zFmAtXNW9euSU
RNP_BLOGGERS_SHEET_ID=1Y7uxZnrjHLBntoDLkKJBOt5-lmODRJ5QEkE19QBA8xk
GOOGLE_SERVICE_ACCOUNT_FILE=services/sheets_sync/credentials/google_sa.json
```

WB DB и Supabase кредлы — общие из `.env`, через `shared/data_layer/_connection.py`.

## CORS

Allowlist в `app.py`:
- `https://hub.os.wookiee.shop`
- `http://localhost:5173`, `http://localhost:5174` (dev)

Только `GET` методы.

## Деплой

```bash
# на локалке
git push origin main

# на сервере timeweb
ssh timeweb "cd /home/danila/projects/wookiee && git pull origin main && \
  docker compose -f deploy/docker-compose.yml up -d --build analytics-api"
```

## Тесты

```bash
python3 -m pytest tests/analytics_api/test_rnp_metrics.py -v
```

14 тестов покрывают `_safe_div`, `_week_start`, `_detect_phase`, `aggregate_to_weeks`.

## Воронка vs финансы — два разных счётчика заказов

В API возвращаются **два независимых поля** для количества заказов:

| Поле | Источник | Назначение |
|---|---|---|
| `orders_qty` | `abc_date.count_orders` | Финансы (карточки, выручка, маржа) — деньги |
| `funnel_orders_qty` | `content_analysis.orderscount` | Воронка (CR клик→заказ, CR корзина→заказ) |
| `funnel_buyouts_qty` | `content_analysis.buyoutscount` | Воронка (выкупы) |

**Они могут отличаться на 10–15%** — это нормально:
- `abc_date` — финансовая таблица: учитывает отмены, корректировки, возвраты
- `content_analysis` — карточки товаров: моментный счётчик при оформлении заказа

**Все CR (`cr_card_to_cart`, `cr_cart_to_order`, `cr_total`) считаются intra-source — только из `content_analysis`.** Раньше `cr_total` смешивал источники (`orders_qty` из abc / `clicks_total` из CA), что давало занижение CR на ~12–15%. Исправлено в коммите `2026-05-07`.

Запросы к `content_analysis` фильтруются по `brandname = 'Wookiee'` (включает оба юрлица: ООО ВУКИ и ИП Медведева).

## Известные ограничения и TODO

1. **`SUPABASE_JWT_SECRET` пока не задан** — JWT декодится без проверки подписи (fallback). Безопасно достаточно (проверяется `role=authenticated`), но для прод-уровня нужно добавить секрет из Supabase Dashboard → Settings → API → JWT Secret.

2. **margin_before_ads формула** (TODO в `aggregate_to_weeks`):
   `margin_before_ads_rub = margin_rub + adv_total_rub` — нужно подтвердить с Артёмом, не дублируется ли вычитание Sheets-каналов (`reclama_vn*` уже могут включать их).

3. **Charlotte и другие модели без `artikul_modeli`** — не появятся в дропдауне, пока поле в Supabase не заполнят.

4. **OZON не поддерживается** — Phase 1 только WB. Селектор маркетплейса в UI пока не активен.

5. **Источник данных по блогерам — Google Sheets**, не Supabase CRM.
   На 2026-05-07 в Supabase `crm.integrations` лежит 683 интеграции, но:
   - `total_cost = 0` у 682 (финансы не синкаются ETL-ом)
   - `recommended_models = null` у 669 (модельная атрибуция не заполнена)
   - Когда ETL дозаполнит — переключить `fetch_rnp_sheets_bloggers` на запрос к Supabase.

6. **buyout_pct — лаговый показатель** (3-21 дн. задержка). В UI отображается как информационный, не как причина изменения маржи.

7. **Остаточное расхождение opens vs PowerBI ~20%** — методология DAX отличается от наших SQL-сумм. Принимаем как известное расхождение; внутренне все CR консистентны (intra-source). См. `docs/database/DATA_QUALITY_NOTES.md` п.4.

## Файлы

| Что | Где |
|---|---|
| FastAPI приложение | [app.py](app.py) |
| Слой данных (SQL + Sheets + агрегация) | [shared/data_layer/rnp.py](../../shared/data_layer/rnp.py) |
| Connection factory | [shared/data_layer/_connection.py](../../shared/data_layer/_connection.py) |
| Sheets-клиент | [shared/clients/sheets_client.py](../../shared/clients/sheets_client.py) |
| Тесты | [tests/analytics_api/test_rnp_metrics.py](../../tests/analytics_api/test_rnp_metrics.py) |
| Frontend (см. ниже) | [wookiee-hub/src/pages/analytics/rnp.tsx](../../wookiee-hub/src/pages/analytics/rnp.tsx) |

## Frontend (Wookiee Hub)

| Что | Где |
|---|---|
| Страница `/analytics/rnp` | `wookiee-hub/src/pages/analytics/rnp.tsx` |
| API-клиент | `wookiee-hub/src/api/rnp.ts` |
| Типы | `wookiee-hub/src/types/rnp.ts` |
| Фильтры (модель, период, прогноз выкупа) | `wookiee-hub/src/components/analytics/rnp-filters.tsx` |
| Карточки итогов | `wookiee-hub/src/components/analytics/rnp-summary-cards.tsx` |
| Помощь / методология | `wookiee-hub/src/components/analytics/rnp-help-block.tsx` |
| Вкладки графиков | `wookiee-hub/src/components/analytics/rnp-tabs/` (6 файлов) |

Деплой фронта:

```bash
cd wookiee-hub && npm run build
# ВАЖНО: Caddy bind-маунтит /home/danila/projects/wookiee/wookiee-hub/dist → /srv/hub.
# Rsync идёт в директорию-источник, не в /srv/hub (это путь внутри контейнера).
rsync -az --delete dist/ timeweb:/home/danila/projects/wookiee/wookiee-hub/dist/
```
