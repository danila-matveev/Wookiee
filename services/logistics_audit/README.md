# Аудит логистики WB

Рассчитывает переплату за логистику WB по формуле из Оферты. Сравнивает то, что WB удержал (`delivery_rub`) с расчётной стоимостью логистики и показывает разницу.

## Запуск

```bash
# Полный аудит (генерирует Excel)
python -m services.logistics_audit.runner OOO 2026-01-01 2026-03-23

# Калибровка ИЛ (сравнение с дашбордом WB)
python -m services.logistics_audit.runner OOO 2026-01-01 2026-03-23 --calibrate

# Валидация на эталонных данных Фисанова
python -m services.logistics_audit.validate_fisanov

# Перерасчёт ООО из локальных Excel-файлов (без WB API)
python -m services.logistics_audit.recalculate_ooo

# Перерасчёт: валидация на данных Фисанова
python -m services.logistics_audit.recalculate_ooo --fisanov
```

Аргументы `runner.py`:
- `cabinet` — `OOO` или `IP` (ключ из `.env`: `WB_API_KEY_OOO` / `WB_API_KEY_IP`)
- `date_from`, `date_to` — период аудита (YYYY-MM-DD)
- `--calibrate` — вместо аудита показывает таблицу ИЛ для сравнения с WB

## Структура

```
services/logistics_audit/
├── runner.py                  # Основной пайплайн: fetch → calculate → Excel
├── config.py                  # Загрузка конфига из .env + IL overrides
├── il_overrides.json          # Ручные значения ИЛ по неделям (из дашборда WB)
├── api/
│   ├── wb_reports.py          # reportDetailByPeriod v5
│   ├── wb_tariffs.py          # tariffs/box, tariffs/pallet
│   ├── wb_content.py          # Габариты из карточек товаров
│   ├── wb_warehouse_remains.py # Остатки на складах
│   └── wb_penalties.py        # Штрафы и удержания
├── calculators/
│   ├── logistics_overpayment.py   # Расчёт переплаты по строке
│   ├── tariff_periods.py          # Базовые тарифы по периодам + sub-liter тиры
│   ├── warehouse_coef_resolver.py # 3-tier: фиксация → Supabase → dlv_prc
│   ├── weekly_il_calculator.py    # Индекс локализации по неделям + overrides
│   ├── tariff_calibrator.py       # Калибровка базового тарифа (legacy)
│   ├── localization_resolver.py   # Per-SKU локализация
│   └── dimensions_checker.py      # Проверка габаритов
├── models/
│   ├── audit_config.py        # Конфиг аудита (api_key, даты, КТР)
│   ├── report_row.py          # Строка из reportDetailByPeriod
│   └── tariff_snapshot.py     # Снимок тарифа склада
├── output/
│   ├── excel_generator.py     # Генерация Excel (11 листов)
│   ├── sheet_overpayment_values.py   # Переплата (значения)
│   ├── sheet_overpayment_formulas.py # Переплата (формулы)
│   ├── sheet_svod.py          # СВОД по отчётам
│   ├── sheet_detail.py        # Детализация (все строки)
│   ├── sheet_il.py            # ИЛ по неделям
│   ├── sheet_pivot_by_article.py # По артикулам
│   ├── sheet_logistics_types.py  # Виды логистики
│   ├── sheet_weekly.py        # Еженедельный отчёт
│   ├── sheet_dimensions.py    # Габариты
│   ├── sheet_tariffs_box.py   # Тарифы (короб)
│   └── sheet_tariffs_pallet.py # Тарифы (монопалета)
├── etl/
│   ├── tariff_collector.py    # Daily ETL: WB tariffs → Supabase
│   ├── import_historical_tariffs.py # Исторический импорт Excel → Supabase
│   ├── setup_wb_tariffs.py    # Bootstrap: schema + import + API gap fill
│   └── cron_tariff_collector.sh # Host-level cron wrapper для Timeweb
├── validate_fisanov.py        # Валидация на эталоне ИП Фисанова
├── recalculate_ooo.py         # Перерасчёт ООО из локальных файлов (без API)
├── generate_fisanov_report.py # Генерация отчёта сравнения с Фисановым
└── CHANGELOG-v2-fixes.md      # Описание 5 исправлений v2 + результаты ООО
```

## Формула расчёта

```
Стоимость логистики = (Тариф_1л + (Объём - 1) × Тариф_доп_л) × Коэф_склада × ИЛ
Переплата = WB_удержал - Стоимость_логистики
```

## Ключевые правила (v2)

1. **Только прямая логистика**: "К клиенту при продаже" и "К клиенту при отмене". Возвраты исключены.
2. **Тарифы по периодам**: 33/35/38/46 руб в зависимости от даты заказа. Sub-liter тиры (23-32 руб) для товаров < 1L.
3. **Коэффициент склада**: фиксация (если активна) → Supabase ETL → dlv_prc (fallback).
4. **ИЛ**: расчёт из заказов + ручные overrides из `il_overrides.json`.
5. **Отрицательные строки**: исключаются из итогов и из листа "Переплата по логистике".

## ИЛ калибровка

ИЛ из нашего расчёта (~1.0) отличается от дашборда WB (1.01–1.10 для ООО). Workflow:

1. `--calibrate` — показать таблицу расчётных ИЛ
2. Сравнить с WB: Поставки и заказы → Тарифы → Тарифы складов → Индекс локализации
3. Внести расхождения в `il_overrides.json`
4. Перезапустить аудит

## ETL тарифов складов

```bash
# Полный bootstrap: миграция + исторический импорт + gap-fill через WB API
python -m services.logistics_audit.etl.setup_wb_tariffs

# Только исторический импорт Excel → Supabase
python -m services.logistics_audit.etl.import_historical_tariffs

# Сбор тарифов за сегодня
python -m services.logistics_audit.etl.tariff_collector --cabinet OOO

# Бэкфилл за 30 дней
python -m services.logistics_audit.etl.tariff_collector --backfill 30 --cabinet OOO
```

Bootstrap-поток:
1. `setup_wb_tariffs.py` вызывает миграцию `007_create_wb_tariffs.py`
2. История из `Тарифы на логискику.xlsx` импортируется в `public.wb_tariffs`
3. Разрыв после последней даты Excel дозаполняется через `tariff_collector.py`
4. Повторный запуск безопасен: используется `ON CONFLICT (dt, warehouse_name) DO UPDATE`

Данные сохраняются в Supabase таблицу `public.wb_tariffs` (RLS включён). В таблице хранятся и `delivery_coef`, и `storage_coef`; в текущей формуле аудита используется только `delivery_coef`.

### Cron на сервере

Host-level wrapper для Timeweb: `services/logistics_audit/etl/cron_tariff_collector.sh`

Проверка shell-скрипта:

```bash
bash -n services/logistics_audit/etl/cron_tariff_collector.sh
```

Ручная установка cron на сервере (`ssh timeweb` → `crontab -e`):

```cron
PATH=/usr/local/bin:/usr/bin:/bin
CRON_TZ=Europe/Moscow
0 8 * * * /home/danila/projects/wookiee/services/logistics_audit/etl/cron_tariff_collector.sh
```

Cron запускает ежедневный сбор в 08:00 МСК и пишет логи в `/home/danila/projects/wookiee/logs/wb_tariffs/`.

## Перерасчёт ООО из локальных файлов

`recalculate_ooo.py` пересчитывает аудит ООО из Excel-файлов без обращения к WB API. Показывает декомпозицию по 5 фиксам.

```bash
# Перерасчёт ООО (генерирует Excel + декомпозиция в консоль)
python -m services.logistics_audit.recalculate_ooo

# Валидация алгоритма на данных Фисанова (target: остаток < 1 руб)
python -m services.logistics_audit.recalculate_ooo --fisanov
```

**Входные файлы** (в `services/logistics_audit/`):
- `Аудит логистики 2026-01-01 — 2026-03-23.xlsx` — исходный аудит ООО
- `Тарифы на логискику.xlsx` — коэффициенты складов по датам
- `ИП Фисанов. Проверка логистики ...xlsx` — эталон для валидации

**Выход:** `ООО Wookiee — Перерасчёт логистики (v2).xlsx` (4 листа: Переплата, Сравнение, Декомпозиция, ИЛ).
