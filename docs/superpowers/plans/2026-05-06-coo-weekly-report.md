# Еженедельный отчёт COO — План реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Цель:** Создать скилл `/coo-report`, который собирает 5 независимых потоков данных параллельно, проверяет их на аномалии и создаёт заполненную страницу в Notion по шаблону COO.

**Архитектура:** Пять изолированных сборщиков (Python-скрипты), каждый пишет JSON в `/tmp/`. Claude запускает их параллельно, читает результаты, проверяет на аномалии, заполняет Notion-шаблон через MCP. Никаких отдельных LLM-вызовов — Claude Code IS the LLM.

**Технологии:** Python 3.10+, `shared/data_layer/` (PostgreSQL), WB API, МойСклад API, Bitrix24 REST API, Notion MCP.

---

## Структура файлов

```
modules/coo-report/
├── collectors/
│   ├── __init__.py          ← пусто, делает папку пакетом
│   ├── finance.py           ← WB+OZON P&L за неделю → /tmp/coo_finance.json
│   ├── models.py            ← метрики по 16 моделям → /tmp/coo_models.json
│   ├── logistics.py         ← склад, оборачиваемость, локализация → /tmp/coo_logistics.json
│   ├── ads.py               ← внешняя реклама по каналам → /tmp/coo_ads.json
│   └── team.py              ← задачи сотрудников из Битрикс → /tmp/coo_team.json
├── config.py                ← даты недели, список моделей, ID Notion, коды статусов
└── SKILL.md                 ← инструкция для Claude

tests/coo_report/
├── __init__.py
├── test_config.py
├── test_finance.py
├── test_models.py
├── test_logistics.py
├── test_ads.py
└── test_team.py
```

---

## Задача 1: Конфигурация и структура модуля

**Файлы:**
- Создать: `modules/coo-report/config.py`
- Создать: `modules/coo-report/collectors/__init__.py`
- Создать: `tests/coo_report/__init__.py`
- Создать: `tests/coo_report/test_config.py`

- [ ] **Шаг 1: Написать тесты для расчёта дат недели**

```python
# tests/coo_report/test_config.py
from datetime import date
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.coo_report.config import get_week_bounds


def test_week_bounds_from_wednesday():
    # Среда 7 мая 2026 → неделя пн 4 мая – вс 10 мая
    current_start, current_end, prev_start, prev_end = get_week_bounds(date(2026, 5, 7))
    assert current_start == date(2026, 5, 4)
    assert current_end == date(2026, 5, 11)   # exclusive
    assert prev_start == date(2026, 4, 27)
    assert prev_end == date(2026, 5, 4)


def test_week_bounds_from_monday():
    current_start, current_end, prev_start, prev_end = get_week_bounds(date(2026, 5, 4))
    assert current_start == date(2026, 5, 4)
    assert prev_start == date(2026, 4, 27)


def test_week_bounds_from_sunday():
    current_start, current_end, prev_start, prev_end = get_week_bounds(date(2026, 5, 3))
    assert current_start == date(2026, 4, 27)
    assert current_end == date(2026, 5, 4)


def test_models_list_has_16_items():
    from modules.coo_report.config import MODELS
    assert len(MODELS) == 16


def test_bitrix_status_covers_key_codes():
    from modules.coo_report.config import BITRIX_STATUS
    assert BITRIX_STATUS["3"] == "Выполнено"
    assert BITRIX_STATUS["2"] == "В работе"
```

- [ ] **Шаг 2: Запустить тесты — убедиться что падают**

```bash
cd /Users/danilamatveev/Projects/Wookiee
python -m pytest tests/coo_report/test_config.py -v
```

Ожидаем: `ModuleNotFoundError: No module named 'modules.coo_report'`

- [ ] **Шаг 3: Создать структуру директорий**

```bash
mkdir -p modules/coo-report/collectors
mkdir -p tests/coo_report
touch modules/coo-report/collectors/__init__.py
touch tests/coo_report/__init__.py
```

Важно: папка называется `coo-report` (через дефис), но Python-импорт использует `coo_report` (через подчёркивание). Это стандарт для модулей в проекте (ср. `modules/bitrix-analytics/` импортируется напрямую без пакета).

Создаём `modules/coo-report/__init__.py` чтобы он работал как пакет при `sys.path.insert`:

```python
# modules/coo-report/__init__.py
# пусто
```

- [ ] **Шаг 4: Написать config.py**

```python
# modules/coo-report/config.py
"""Конфигурация скилла /coo-report."""

from datetime import date, timedelta


NOTION_TEMPLATE_ID = "35658a2bd5878028ad75f1773a0f8593"
NOTION_PARENT_ID = "35658a2bd587803b8ab5fc540e4318e7"

MODELS = [
    "wendy", "vuki", "ruby", "audrey", "charlotte", "moon",
    "set vuki", "joy", "set moon", "lana", "eva", "set ruby",
    "bella", "set bella", "alice", "valery",
]

# ID сотрудников в шаблоне COO (из modules/bitrix-analytics/config.py)
COO_STAFF = {
    1435: "Артём",
    41:   "Светлана",
    11:   "Валерия",
    1057: "Настя",
    2223: "Лиля",
    17:   "Дмитрий",
    19:   "Маша",
    1625: "Алина",
}

# Коды статусов задач Битрикс24
BITRIX_STATUS = {
    "1": "Не начата",
    "2": "В работе",
    "3": "Выполнено",
    "4": "Ожидание",
    "5": "В ожидании",
    "6": "Отложено",
    "7": "Отклонено",
}

BITRIX_DONE_STATUSES = {"3"}
BITRIX_ACTIVE_STATUSES = {"2"}
BITRIX_PENDING_STATUSES = {"1", "4", "5", "6"}


def get_week_bounds(ref_date: date = None) -> tuple[date, date, date, date]:
    """
    Возвращает (current_start, current_end, prev_start, prev_end).

    current_start — понедельник недели, содержащей ref_date.
    current_end   — следующий понедельник (exclusive, для WHERE date < current_end).
    """
    if ref_date is None:
        ref_date = date.today()
    days_since_monday = ref_date.weekday()
    current_start = ref_date - timedelta(days=days_since_monday)
    current_end = current_start + timedelta(days=7)
    prev_start = current_start - timedelta(days=7)
    prev_end = current_start
    return current_start, current_end, prev_start, prev_end
```

- [ ] **Шаг 5: Запустить тесты — убедиться что проходят**

```bash
python -m pytest tests/coo_report/test_config.py -v
```

Ожидаем: 5 PASSED

- [ ] **Шаг 6: Коммит**

```bash
git add modules/coo-report/ tests/coo_report/
git commit -m "feat(coo-report): add module scaffold and config with week bounds"
```

---

## Задача 2: Сборщик финансов (finance.py)

**Файлы:**
- Создать: `modules/coo-report/collectors/finance.py`
- Создать: `tests/coo_report/test_finance.py`

Сборщик вызывает `get_wb_finance()` и `get_ozon_finance()` из `shared/data_layer/finance.py`.

Индексы полей `get_wb_finance()` (кортеж из abc_date):
`[0]`=period, `[1]`=orders_count(abc), `[2]`=sales_count, `[3]`=revenue_before_spp,
`[4]`=revenue_after_spp, `[5]`=adv_internal, `[6]`=adv_external, `[7]`=cost_of_goods,
`[8]`=logistics, `[9]`=storage, `[10]`=commission, `[11]`=spp_amount, `[12]`=nds,
`[13]`=penalty, `[14]`=retention, `[15]`=deduction, `[16]`=margin, `[17]`=returns_revenue

Индексы `get_ozon_finance()`:
`[0]`=period, `[1]`=sales_count, `[2]`=revenue_before_spp, `[3]`=revenue_after_spp,
`[4]`=adv_internal, `[5]`=adv_external, `[6]`=margin, `[7]`=cost_of_goods,
`[8]`=logistics, `[9]`=storage, `[10]`=commission, `[11]`=spp_amount, `[12]`=nds

- [ ] **Шаг 1: Написать тесты**

```python
# tests/coo_report/test_finance.py
from unittest.mock import patch
from datetime import date
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.coo_report.collectors.finance import collect


WB_FINANCE_ROW_CURRENT = (
    'current', 150, 120,     # period, orders_count, sales_count
    5_000_000, 4_200_000,    # revenue_before_spp, revenue_after_spp
    200_000, 80_000,         # adv_internal, adv_external
    1_500_000, 300_000,      # cost_of_goods, logistics
    150_000, 420_000,        # storage, commission
    300_000, 50_000,         # spp_amount, nds
    10_000, 5_000, 3_000,    # penalty, retention, deduction
    820_000,                 # margin
    100_000, 5_100_000,      # returns_revenue, revenue_before_spp_gross
)
WB_ORDERS_ROW_CURRENT = ('current', 155, 5_200_000)

OZON_FINANCE_ROW_CURRENT = (
    'current', 60, 1_800_000, 1_600_000,   # period, sales, rev_before, rev_after
    50_000, 20_000,                         # adv_internal, adv_external
    280_000, 600_000,                       # margin, cost_of_goods
    90_000, 30_000, 160_000,               # logistics, storage, commission
    80_000, 15_000,                         # spp_amount, nds
)
OZON_ORDERS_ROW_CURRENT = ('current', 65, 1_850_000)


@patch('modules.coo_report.collectors.finance.get_ozon_finance')
@patch('modules.coo_report.collectors.finance.get_wb_finance')
def test_collect_returns_required_keys(mock_wb, mock_ozon):
    mock_wb.return_value = ([WB_FINANCE_ROW_CURRENT], [WB_ORDERS_ROW_CURRENT])
    mock_ozon.return_value = ([OZON_FINANCE_ROW_CURRENT], [OZON_ORDERS_ROW_CURRENT])

    result = collect(ref_date=date(2026, 5, 7))

    assert "wb" in result
    assert "ozon" in result
    assert "combined" in result
    assert "period" in result
    assert result["period"]["current_start"] == "2026-05-04"


@patch('modules.coo_report.collectors.finance.get_ozon_finance')
@patch('modules.coo_report.collectors.finance.get_wb_finance')
def test_drr_internal_calculation(mock_wb, mock_ozon):
    mock_wb.return_value = ([WB_FINANCE_ROW_CURRENT], [WB_ORDERS_ROW_CURRENT])
    mock_ozon.return_value = ([OZON_FINANCE_ROW_CURRENT], [OZON_ORDERS_ROW_CURRENT])

    result = collect(ref_date=date(2026, 5, 7))

    # ДРР внутренняя WB: adv_internal / orders_rub * 100 = 200000 / 5200000 * 100
    wb = result["wb"]["current"]
    assert abs(wb["drr_internal_pct"] - 200_000 / 5_200_000 * 100) < 0.01


@patch('modules.coo_report.collectors.finance.get_ozon_finance')
@patch('modules.coo_report.collectors.finance.get_wb_finance')
def test_combined_revenue_is_sum_of_channels(mock_wb, mock_ozon):
    mock_wb.return_value = ([WB_FINANCE_ROW_CURRENT], [WB_ORDERS_ROW_CURRENT])
    mock_ozon.return_value = ([OZON_FINANCE_ROW_CURRENT], [OZON_ORDERS_ROW_CURRENT])

    result = collect(ref_date=date(2026, 5, 7))

    combined = result["combined"]["current"]
    expected_revenue = 4_200_000 + 1_600_000
    assert combined["revenue_after_spp"] == expected_revenue
```

- [ ] **Шаг 2: Запустить тесты — убедиться что падают**

```bash
python -m pytest tests/coo_report/test_finance.py -v
```

Ожидаем: `ModuleNotFoundError: No module named 'modules.coo_report.collectors.finance'`

- [ ] **Шаг 3: Написать finance.py**

```python
# modules/coo-report/collectors/finance.py
"""Сборщик финансовых данных WB+OZON за неделю."""

import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from shared.data_layer.finance import get_wb_finance, get_ozon_finance
from modules.coo_report.config import get_week_bounds

OUTPUT_PATH = Path("/tmp/coo_finance.json")


def _parse_wb_row(row: tuple) -> dict:
    return {
        "orders_count_abc": int(row[1] or 0),
        "sales_count": int(row[2] or 0),
        "revenue_before_spp": float(row[3] or 0),
        "revenue_after_spp": float(row[4] or 0),
        "adv_internal": float(row[5] or 0),
        "adv_external": float(row[6] or 0),
        "cost_of_goods": float(row[7] or 0),
        "logistics": float(row[8] or 0),
        "storage": float(row[9] or 0),
        "commission": float(row[10] or 0),
        "spp_amount": float(row[11] or 0),
        "nds": float(row[12] or 0),
        "penalty": float(row[13] or 0),
        "retention": float(row[14] or 0),
        "deduction": float(row[15] or 0),
        "margin": float(row[16] or 0),
        "returns_revenue": float(row[17] or 0),
    }


def _parse_ozon_row(row: tuple) -> dict:
    return {
        "sales_count": int(row[1] or 0),
        "revenue_before_spp": float(row[2] or 0),
        "revenue_after_spp": float(row[3] or 0),
        "adv_internal": float(row[4] or 0),
        "adv_external": float(row[5] or 0),
        "margin": float(row[6] or 0),
        "cost_of_goods": float(row[7] or 0),
        "logistics": float(row[8] or 0),
        "storage": float(row[9] or 0),
        "commission": float(row[10] or 0),
        "spp_amount": float(row[11] or 0),
        "nds": float(row[12] or 0),
    }


def _add_drr(channel_data: dict, orders_rub: float) -> dict:
    """Добавляет ДРР к данным канала. orders_rub — заказы в рублях из таблицы orders."""
    data = dict(channel_data)
    adv_int = data.get("adv_internal", 0)
    adv_ext = data.get("adv_external", 0)
    if orders_rub > 0:
        data["drr_internal_pct"] = round(adv_int / orders_rub * 100, 2)
        data["drr_external_pct"] = round(adv_ext / orders_rub * 100, 2)
        data["drr_total_pct"] = round((adv_int + adv_ext) / orders_rub * 100, 2)
    else:
        data["drr_internal_pct"] = 0.0
        data["drr_external_pct"] = 0.0
        data["drr_total_pct"] = 0.0
    data["orders_rub"] = orders_rub
    return data


def collect(ref_date: date = None) -> dict:
    current_start, current_end, prev_start, _ = get_week_bounds(ref_date)

    wb_rows, wb_orders_rows = get_wb_finance(current_start, prev_start, current_end)
    ozon_rows, ozon_orders_rows = get_ozon_finance(current_start, prev_start, current_end)

    # WB
    wb_by_period = {row[0]: _parse_wb_row(row) for row in wb_rows}
    wb_orders = {row[0]: {"orders_count": int(row[1] or 0), "orders_rub": float(row[2] or 0)}
                 for row in wb_orders_rows}
    for period, data in wb_by_period.items():
        orders_rub = wb_orders.get(period, {}).get("orders_rub", 0)
        orders_cnt = wb_orders.get(period, {}).get("orders_count", 0)
        data["orders_count"] = orders_cnt
        wb_by_period[period] = _add_drr(data, orders_rub)

    # OZON
    ozon_by_period = {row[0]: _parse_ozon_row(row) for row in ozon_rows}
    ozon_orders = {row[0]: {"orders_count": int(row[1] or 0), "orders_rub": float(row[2] or 0)}
                   for row in ozon_orders_rows}
    for period, data in ozon_by_period.items():
        orders_rub = ozon_orders.get(period, {}).get("orders_rub", 0)
        orders_cnt = ozon_orders.get(period, {}).get("orders_count", 0)
        data["orders_count"] = orders_cnt
        ozon_by_period[period] = _add_drr(data, orders_rub)

    # Объединённые WB+OZON
    combined = {}
    for period in set(list(wb_by_period.keys()) + list(ozon_by_period.keys())):
        wb = wb_by_period.get(period, {})
        oz = ozon_by_period.get(period, {})
        total_orders_rub = wb.get("orders_rub", 0) + oz.get("orders_rub", 0)
        combined_row = {
            "orders_count": wb.get("orders_count", 0) + oz.get("orders_count", 0),
            "sales_count": wb.get("sales_count", 0) + oz.get("sales_count", 0),
            "revenue_after_spp": wb.get("revenue_after_spp", 0) + oz.get("revenue_after_spp", 0),
            "revenue_before_spp": wb.get("revenue_before_spp", 0) + oz.get("revenue_before_spp", 0),
            "adv_internal": wb.get("adv_internal", 0) + oz.get("adv_internal", 0),
            "adv_external": wb.get("adv_external", 0) + oz.get("adv_external", 0),
            "logistics": wb.get("logistics", 0) + oz.get("logistics", 0),
            "storage": wb.get("storage", 0) + oz.get("storage", 0),
            "commission": wb.get("commission", 0) + oz.get("commission", 0),
            "margin": wb.get("margin", 0) + oz.get("margin", 0),
            "spp_amount": wb.get("spp_amount", 0) + oz.get("spp_amount", 0),
        }
        combined[period] = _add_drr(combined_row, total_orders_rub)

    return {
        "wb": wb_by_period,
        "ozon": ozon_by_period,
        "combined": combined,
        "period": {
            "current_start": str(current_start),
            "current_end": str(current_end),
            "prev_start": str(prev_start),
        },
    }


if __name__ == "__main__":
    data = collect()
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Финансы сохранены → {OUTPUT_PATH}")
    current = data.get("combined", {}).get("current", {})
    print(f"  Выручка после СПП: {current.get('revenue_after_spp', 0):,.0f} ₽")
    print(f"  Маржа: {current.get('margin', 0):,.0f} ₽")
    print(f"  ДРР общий: {current.get('drr_total_pct', 0):.1f}%")
```

- [ ] **Шаг 4: Запустить тесты — убедиться что проходят**

```bash
python -m pytest tests/coo_report/test_finance.py -v
```

Ожидаем: 3 PASSED

- [ ] **Шаг 5: Коммит**

```bash
git add modules/coo-report/collectors/finance.py tests/coo_report/test_finance.py
git commit -m "feat(coo-report): add finance collector with DRR calculation"
```

---

## Задача 3: Сборщик метрик по моделям (models.py)

**Файлы:**
- Создать: `modules/coo-report/collectors/models.py`
- Создать: `tests/coo_report/test_models.py`

Объединяет `get_wb_by_model()` и `get_ozon_by_model()`. Индексы обоих:
`[0]`=period, `[1]`=model, `[2]`=sales_count, `[3]`=revenue_before_spp,
`[4]`=adv_internal, `[5]`=adv_external, `[6]`=margin, `[7]`=cost_of_goods

Нужны также заказы по модели для ДРР: `get_wb_orders_by_model()` → `[0]`=period, `[1]`=model, `[2]`=orders_count, `[3]`=orders_rub

- [ ] **Шаг 1: Написать тесты**

```python
# tests/coo_report/test_models.py
from unittest.mock import patch
from datetime import date
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.coo_report.collectors.models import collect

WB_MODEL_ROWS = [
    ('current', 'wendy', 80, 2_000_000, 80_000, 30_000, 400_000, 600_000),
    ('current', 'vuki',  40, 900_000,   30_000, 10_000, 150_000, 270_000),
    ('previous', 'wendy', 70, 1_600_000, 60_000, 20_000, 300_000, 480_000),
]
WB_ORDERS_ROWS = [
    ('current', 'wendy', 85, 2_100_000),
    ('current', 'vuki',  42, 940_000),
    ('previous', 'wendy', 72, 1_650_000),
]
OZON_MODEL_ROWS = [
    ('current', 'wendy', 20, 500_000, 20_000, 5_000, 100_000, 150_000),
]
OZON_ORDERS_ROWS = [
    ('current', 'wendy', 22, 520_000),
]


@patch('modules.coo_report.collectors.models.get_ozon_orders_by_model', return_value=OZON_ORDERS_ROWS)
@patch('modules.coo_report.collectors.models.get_ozon_by_model', return_value=OZON_MODEL_ROWS)
@patch('modules.coo_report.collectors.models.get_wb_orders_by_model', return_value=WB_ORDERS_ROWS)
@patch('modules.coo_report.collectors.models.get_wb_by_model', return_value=WB_MODEL_ROWS)
def test_models_merged_across_channels(mock_wb, mock_wb_ord, mock_oz, mock_oz_ord):
    result = collect(ref_date=date(2026, 5, 7))

    # wendy должна быть объединена WB+OZON
    wendy = result["current"]["wendy"]
    assert wendy["revenue"] == 2_000_000 + 500_000
    assert wendy["margin"] == 400_000 + 100_000


@patch('modules.coo_report.collectors.models.get_ozon_orders_by_model', return_value=OZON_ORDERS_ROWS)
@patch('modules.coo_report.collectors.models.get_ozon_by_model', return_value=OZON_MODEL_ROWS)
@patch('modules.coo_report.collectors.models.get_wb_orders_by_model', return_value=WB_ORDERS_ROWS)
@patch('modules.coo_report.collectors.models.get_wb_by_model', return_value=WB_MODEL_ROWS)
def test_trend_positive_when_revenue_grew(mock_wb, mock_wb_ord, mock_oz, mock_oz_ord):
    result = collect(ref_date=date(2026, 5, 7))

    wendy_curr = result["current"]["wendy"]["revenue"]
    wendy_prev = result["previous"]["wendy"]["revenue"]
    assert wendy_curr > wendy_prev
    assert result["current"]["wendy"]["trend_pct"] > 0


@patch('modules.coo_report.collectors.models.get_ozon_orders_by_model', return_value=[])
@patch('modules.coo_report.collectors.models.get_ozon_by_model', return_value=[])
@patch('modules.coo_report.collectors.models.get_wb_orders_by_model', return_value=WB_ORDERS_ROWS)
@patch('modules.coo_report.collectors.models.get_wb_by_model', return_value=WB_MODEL_ROWS)
def test_drr_calculated_from_orders_rub(mock_wb, mock_wb_ord, mock_oz, mock_oz_ord):
    result = collect(ref_date=date(2026, 5, 7))

    wendy = result["current"]["wendy"]
    # ДРР = (adv_internal + adv_external) / orders_rub * 100
    expected_drr = (80_000 + 30_000) / 2_100_000 * 100
    assert abs(wendy["drr_pct"] - expected_drr) < 0.01
```

- [ ] **Шаг 2: Запустить тесты — убедиться что падают**

```bash
python -m pytest tests/coo_report/test_models.py -v
```

- [ ] **Шаг 3: Написать models.py**

```python
# modules/coo-report/collectors/models.py
"""Сборщик метрик по 16 моделям за неделю (WB + OZON объединены)."""

import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from shared.data_layer.finance import get_wb_by_model, get_ozon_by_model
from shared.data_layer.finance import get_wb_orders_by_model, get_ozon_orders_by_model
from modules.coo_report.config import get_week_bounds, MODELS

OUTPUT_PATH = Path("/tmp/coo_models.json")


def _empty_model() -> dict:
    return {
        "revenue": 0.0, "margin": 0.0, "cost_of_goods": 0.0,
        "adv_internal": 0.0, "adv_external": 0.0,
        "sales_count": 0, "orders_count": 0, "orders_rub": 0.0,
    }


def _aggregate(rows: list, orders_rows: list) -> dict[str, dict]:
    """Агрегирует строки по ключу (period, model) → dict."""
    data: dict[tuple, dict] = {}

    for row in rows:
        period, model = row[0], row[1].lower()
        key = (period, model)
        if key not in data:
            data[key] = _empty_model()
        data[key]["sales_count"] += int(row[2] or 0)
        data[key]["revenue"] += float(row[3] or 0)
        data[key]["adv_internal"] += float(row[4] or 0)
        data[key]["adv_external"] += float(row[5] or 0)
        data[key]["margin"] += float(row[6] or 0)
        data[key]["cost_of_goods"] += float(row[7] or 0)

    for row in orders_rows:
        period, model = row[0], row[1].lower()
        key = (period, model)
        if key not in data:
            data[key] = _empty_model()
        data[key]["orders_count"] += int(row[2] or 0)
        data[key]["orders_rub"] += float(row[3] or 0)

    return data


def collect(ref_date: date = None) -> dict:
    current_start, current_end, prev_start, _ = get_week_bounds(ref_date)

    wb_data = _aggregate(
        get_wb_by_model(current_start, prev_start, current_end),
        get_wb_orders_by_model(current_start, prev_start, current_end),
    )
    ozon_data = _aggregate(
        get_ozon_by_model(current_start, prev_start, current_end),
        get_ozon_orders_by_model(current_start, prev_start, current_end),
    )

    # Объединяем WB + OZON по (period, model)
    all_keys = set(wb_data.keys()) | set(ozon_data.keys())
    merged: dict[tuple, dict] = {}
    for key in all_keys:
        wb = wb_data.get(key, _empty_model())
        oz = ozon_data.get(key, _empty_model())
        merged[key] = {
            "revenue": round(wb["revenue"] + oz["revenue"], 2),
            "margin": round(wb["margin"] + oz["margin"], 2),
            "cost_of_goods": round(wb["cost_of_goods"] + oz["cost_of_goods"], 2),
            "adv_internal": round(wb["adv_internal"] + oz["adv_internal"], 2),
            "adv_external": round(wb["adv_external"] + oz["adv_external"], 2),
            "sales_count": wb["sales_count"] + oz["sales_count"],
            "orders_count": wb["orders_count"] + oz["orders_count"],
            "orders_rub": round(wb["orders_rub"] + oz["orders_rub"], 2),
        }

    # Считаем производные: ДРР %, маржа %, тренд
    by_period: dict[str, dict[str, dict]] = {"current": {}, "previous": {}}
    for (period, model), data in merged.items():
        orders_rub = data["orders_rub"]
        revenue = data["revenue"]
        adv_total = data["adv_internal"] + data["adv_external"]
        data["drr_pct"] = round(adv_total / orders_rub * 100, 2) if orders_rub > 0 else 0.0
        data["drr_rub"] = round(adv_total, 2)
        data["margin_pct"] = round(data["margin"] / revenue * 100, 2) if revenue > 0 else 0.0
        if period in by_period:
            by_period[period][model] = data

    # Тренд: % изменения выручки current vs previous
    for model in list(by_period["current"].keys()):
        curr_rev = by_period["current"][model]["revenue"]
        prev_rev = by_period["previous"].get(model, {}).get("revenue", 0)
        if prev_rev > 0:
            trend = round((curr_rev - prev_rev) / prev_rev * 100, 1)
        else:
            trend = 0.0
        by_period["current"][model]["trend_pct"] = trend

    return {
        "current": by_period["current"],
        "previous": by_period["previous"],
        "period": {
            "current_start": str(current_start),
            "current_end": str(current_end),
            "prev_start": str(prev_start),
        },
    }


if __name__ == "__main__":
    data = collect()
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Модели сохранены → {OUTPUT_PATH}")
    for model, stats in sorted(data["current"].items(), key=lambda x: -x[1]["revenue"]):
        print(f"  {model:15s}  {stats['revenue']:>10,.0f} ₽  маржа {stats['margin_pct']:.1f}%  ДРР {stats['drr_pct']:.1f}%  тренд {stats.get('trend_pct', 0):+.1f}%")
```

- [ ] **Шаг 4: Запустить тесты**

```bash
python -m pytest tests/coo_report/test_models.py -v
```

Ожидаем: 3 PASSED

- [ ] **Шаг 5: Коммит**

```bash
git add modules/coo-report/collectors/models.py tests/coo_report/test_models.py
git commit -m "feat(coo-report): add models collector with WB+OZON merge and trend"
```

---

## Задача 4: Сборщик логистики (logistics.py)

**Файлы:**
- Создать: `modules/coo-report/collectors/logistics.py`
- Создать: `tests/coo_report/test_logistics.py`

Использует `get_wb_turnover_by_model(start_date, end_date)` из `shared/data_layer/inventory.py`.
Возвращает dict `{model: {avg_stock, stock_mp, stock_moysklad, stock_transit, daily_sales, turnover_days, sales_count, revenue, margin}}`.

Индекс локализации берём из `services/wb_localization/run_localization.py`. Запускаем через subprocess с флагом `--dry-run` и парсим stdout — это безопаснее чем импортировать тяжёлые зависимости.

GMROI и ROI — расчётные показатели на основе данных оборачиваемости.

- [ ] **Шаг 1: Написать тесты**

```python
# tests/coo_report/test_logistics.py
from unittest.mock import patch
from datetime import date
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.coo_report.collectors.logistics import collect, calculate_gmroi

TURNOVER_DATA = {
    "wendy": {
        "avg_stock": 500.0, "stock_mp": 500.0, "stock_moysklad": 200.0,
        "stock_transit": 50.0, "daily_sales": 5.5, "turnover_days": 90.9,
        "sales_count": 110, "revenue": 2_200_000.0, "margin": 440_000.0,
        "low_sales": False,
    },
    "vuki": {
        "avg_stock": 200.0, "stock_mp": 200.0, "stock_moysklad": 80.0,
        "stock_transit": 20.0, "daily_sales": 2.0, "turnover_days": 100.0,
        "sales_count": 40, "revenue": 800_000.0, "margin": 160_000.0,
        "low_sales": False,
    },
}


def test_gmroi_calculation():
    # GMROI = (weekly_margin * 52) / (avg_stock * cost_per_unit)
    # cost_per_unit ≈ revenue / sales_count * margin_rate
    # Упрощённо: GMROI = (margin * 52) / (avg_stock * sebes_per_unit)
    # Проверяем что функция возвращает положительное число
    result = calculate_gmroi(weekly_margin=440_000, avg_stock_units=500, cost_per_unit=18_000)
    assert result > 0
    assert isinstance(result, float)


@patch('modules.coo_report.collectors.logistics.get_localization_index', return_value=67.3)
@patch('modules.coo_report.collectors.logistics.get_wb_turnover_by_model', return_value=TURNOVER_DATA)
def test_collect_structure(mock_turnover, mock_loc):
    result = collect(ref_date=date(2026, 5, 7))

    assert "localization_index" in result
    assert result["localization_index"] == 67.3
    assert "models" in result
    assert "wendy" in result["models"]


@patch('modules.coo_report.collectors.logistics.get_localization_index', return_value=67.3)
@patch('modules.coo_report.collectors.logistics.get_wb_turnover_by_model', return_value=TURNOVER_DATA)
def test_turnover_days_preserved(mock_turnover, mock_loc):
    result = collect(ref_date=date(2026, 5, 7))
    assert result["models"]["wendy"]["turnover_days"] == 90.9


@patch('modules.coo_report.collectors.logistics.get_localization_index', return_value=25.0)
@patch('modules.coo_report.collectors.logistics.get_wb_turnover_by_model', return_value=TURNOVER_DATA)
def test_low_localization_flagged(mock_turnover, mock_loc):
    result = collect(ref_date=date(2026, 5, 7))
    assert result["localization_warning"] is True
```

- [ ] **Шаг 2: Запустить тесты — убедиться что падают**

```bash
python -m pytest tests/coo_report/test_logistics.py -v
```

- [ ] **Шаг 3: Написать logistics.py**

```python
# modules/coo-report/collectors/logistics.py
"""Сборщик данных по складу, оборачиваемости и локализации WB."""

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from shared.data_layer.inventory import get_wb_turnover_by_model
from modules.coo_report.config import get_week_bounds

OUTPUT_PATH = Path("/tmp/coo_logistics.json")
LOCALIZATION_SCRIPT = PROJECT_ROOT / "services" / "wb_localization" / "run_localization.py"


def get_localization_index() -> float | None:
    """
    Запускает run_localization.py --dry-run и извлекает индекс локализации из stdout.
    Возвращает float (например 67.3) или None если скрипт упал.

    run_localization.py выводит строку вида:
      Индекс локализации: 67.3%
    """
    try:
        result = subprocess.run(
            [sys.executable, str(LOCALIZATION_SCRIPT), "--dry-run"],
            capture_output=True, text=True, timeout=120,
        )
        for line in result.stdout.splitlines():
            line_lower = line.lower()
            if "локализац" in line_lower and "%" in line:
                # Ищем число перед знаком %
                import re
                match = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
                if match:
                    return float(match.group(1))
    except Exception:
        pass
    return None


def calculate_gmroi(weekly_margin: float, avg_stock_units: float, cost_per_unit: float) -> float:
    """
    GMROI = (годовая маржа) / (средние остатки по себестоимости).
    Годовая маржа = weekly_margin * 52.
    Средние остатки по себестоимости = avg_stock_units * cost_per_unit.
    """
    inventory_cost = avg_stock_units * cost_per_unit
    if inventory_cost <= 0:
        return 0.0
    return round((weekly_margin * 52) / inventory_cost * 100, 1)


def collect(ref_date: date = None) -> dict:
    current_start, current_end, _, _ = get_week_bounds(ref_date)

    turnover = get_wb_turnover_by_model(str(current_start), str(current_end))
    localization = get_localization_index()

    models_data = {}
    for model, data in turnover.items():
        revenue = data.get("revenue", 0)
        sales_count = data.get("sales_count", 1) or 1
        # cost_per_unit: get_wb_turnover_by_model не возвращает себестоимость.
        # Используем оценку: ~40% от выручки. Достаточно для GMROI как ориентировочного показателя.
        cost_per_unit = (revenue / sales_count * 0.4) if sales_count > 0 and revenue > 0 else 0
        gmroi = calculate_gmroi(
            weekly_margin=data.get("margin", 0),
            avg_stock_units=data.get("avg_stock", 0),
            cost_per_unit=cost_per_unit,
        )
        models_data[model] = {
            "turnover_days": data.get("turnover_days", 0),
            "stock_fbo_units": int(data.get("stock_mp", 0)),
            "stock_moysklad_units": int(data.get("stock_moysklad", 0)),
            "stock_transit_units": int(data.get("stock_transit", 0)),
            "daily_sales": data.get("daily_sales", 0),
            "gmroi_pct": gmroi,
            "low_sales": data.get("low_sales", False),
        }

    return {
        "localization_index": localization,
        "localization_warning": (localization is not None and localization < 30),
        "models": models_data,
        "period": {
            "current_start": str(current_start),
            "current_end": str(current_end),
        },
    }


if __name__ == "__main__":
    data = collect()
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    loc = data.get("localization_index")
    print(f"Логистика сохранена → {OUTPUT_PATH}")
    print(f"  Индекс локализации: {loc}%")
    print(f"  Моделей: {len(data['models'])}")
    for model, m in sorted(data["models"].items(), key=lambda x: x[1]["turnover_days"]):
        print(f"  {model:15s}  оборачиваемость {m['turnover_days']:.0f} дн.  FBO {m['stock_fbo_units']} шт")
```

- [ ] **Шаг 4: Запустить тесты**

```bash
python -m pytest tests/coo_report/test_logistics.py -v
```

Ожидаем: 4 PASSED

- [ ] **Шаг 5: Коммит**

```bash
git add modules/coo-report/collectors/logistics.py tests/coo_report/test_logistics.py
git commit -m "feat(coo-report): add logistics collector with GMROI and localization index"
```

---

## Задача 5: Сборщик рекламы (ads.py)

**Файлы:**
- Создать: `modules/coo-report/collectors/ads.py`
- Создать: `tests/coo_report/test_ads.py`

Использует `get_wb_external_ad_breakdown()` и `get_ozon_external_ad_breakdown()` из `shared/data_layer/advertising.py`.

`get_wb_external_ad_breakdown()` возвращает кортежи: `[0]`=period, `[1]`=adv_internal, `[2]`=adv_bloggers, `[3]`=adv_vk, `[4]`=adv_creators, `[5]`=adv_total

`get_ozon_external_ad_breakdown()` возвращает: `[0]`=period, `[1]`=adv_internal, `[2]`=adv_external, `[3]`=adv_vk, `[4]`=adv_total

- [ ] **Шаг 1: Написать тесты**

```python
# tests/coo_report/test_ads.py
from unittest.mock import patch
from datetime import date
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.coo_report.collectors.ads import collect

WB_ADS_ROWS = [
    ('current',  200_000, 80_000, 40_000, 10_000, 330_000),
    ('previous', 180_000, 70_000, 35_000,  8_000, 293_000),
]
OZON_ADS_ROWS = [
    ('current',  50_000, 20_000, 5_000, 75_000),
    ('previous', 45_000, 15_000, 4_000, 64_000),
]
WB_ORDERS = 5_200_000  # заказы WB текущая неделя для ДРР


@patch('modules.coo_report.collectors.ads.get_wb_finance')
@patch('modules.coo_report.collectors.ads.get_ozon_external_ad_breakdown')
@patch('modules.coo_report.collectors.ads.get_wb_external_ad_breakdown')
def test_vk_channel_extracted(mock_wb_ads, mock_oz_ads, mock_wb_fin):
    mock_wb_ads.return_value = WB_ADS_ROWS
    mock_oz_ads.return_value = OZON_ADS_ROWS
    # get_wb_finance нужен для orders_rub (ДРР)
    mock_wb_fin.return_value = ([], [('current', 150, 5_200_000)])

    result = collect(ref_date=date(2026, 5, 7))

    assert "vk" in result["current"]
    assert result["current"]["vk"]["spend_rub"] == 40_000 + 5_000  # WB + OZON


@patch('modules.coo_report.collectors.ads.get_wb_finance')
@patch('modules.coo_report.collectors.ads.get_ozon_external_ad_breakdown')
@patch('modules.coo_report.collectors.ads.get_wb_external_ad_breakdown')
def test_drr_calculated_for_channels(mock_wb_ads, mock_oz_ads, mock_wb_fin):
    mock_wb_ads.return_value = WB_ADS_ROWS
    mock_oz_ads.return_value = OZON_ADS_ROWS
    mock_wb_fin.return_value = ([], [('current', 150, 5_200_000)])

    result = collect(ref_date=date(2026, 5, 7))

    bloggers = result["current"]["bloggers"]
    assert bloggers["drr_pct"] == round(80_000 / 5_200_000 * 100, 2)


@patch('modules.coo_report.collectors.ads.get_wb_finance')
@patch('modules.coo_report.collectors.ads.get_ozon_external_ad_breakdown')
@patch('modules.coo_report.collectors.ads.get_wb_external_ad_breakdown')
def test_manual_channels_flagged(mock_wb_ads, mock_oz_ads, mock_wb_fin):
    mock_wb_ads.return_value = WB_ADS_ROWS
    mock_oz_ads.return_value = OZON_ADS_ROWS
    mock_wb_fin.return_value = ([], [('current', 150, 5_200_000)])

    result = collect(ref_date=date(2026, 5, 7))

    # Яндекс и подрядчик-посевы нельзя рассчитать автоматически
    assert result["manual_fill_required"] == ["yandex", "vk_seeds_contractor"]
```

- [ ] **Шаг 2: Запустить тесты — убедиться что падают**

```bash
python -m pytest tests/coo_report/test_ads.py -v
```

- [ ] **Шаг 3: Написать ads.py**

```python
# modules/coo-report/collectors/ads.py
"""
Сборщик данных по внешней рекламе.

Ограничение БД: ВК и блогеры объединены в группы, гранулярная разбивка
(посевы ВК отдельно от таргета, посевы подрядчик отдельно от блогеров)
недоступна. Яндекс реклама в БД отсутствует.
Каналы, требующие ручного заполнения: yandex, vk_seeds_contractor.
"""

import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from shared.data_layer.advertising import get_wb_external_ad_breakdown, get_ozon_external_ad_breakdown
from shared.data_layer.finance import get_wb_finance
from modules.coo_report.config import get_week_bounds

OUTPUT_PATH = Path("/tmp/coo_ads.json")


def collect(ref_date: date = None) -> dict:
    current_start, current_end, prev_start, _ = get_week_bounds(ref_date)

    wb_rows = get_wb_external_ad_breakdown(current_start, prev_start, current_end)
    ozon_rows = get_ozon_external_ad_breakdown(current_start, prev_start, current_end)
    _, wb_orders_rows = get_wb_finance(current_start, prev_start, current_end)

    # Заказы в рублях для расчёта ДРР
    orders_by_period = {row[0]: float(row[2] or 0) for row in wb_orders_rows}

    # Парсим WB
    wb_by_period: dict[str, dict] = {}
    for row in wb_rows:
        period = row[0]
        wb_by_period[period] = {
            "internal": float(row[1] or 0),
            "bloggers": float(row[2] or 0),
            "vk": float(row[3] or 0),
            "creators": float(row[4] or 0),
        }

    # Парсим OZON
    ozon_by_period: dict[str, dict] = {}
    for row in ozon_rows:
        period = row[0]
        ozon_by_period[period] = {
            "internal": float(row[1] or 0),
            "bloggers": float(row[2] or 0),
            "vk": float(row[3] or 0),
        }

    # Объединяем и рассчитываем ДРР
    result_by_period: dict[str, dict] = {}
    for period in set(list(wb_by_period.keys()) + list(ozon_by_period.keys())):
        wb = wb_by_period.get(period, {})
        oz = ozon_by_period.get(period, {})
        orders_rub = orders_by_period.get(period, 0)

        def drr(spend: float) -> float:
            return round(spend / orders_rub * 100, 2) if orders_rub > 0 else 0.0

        bloggers_spend = wb.get("bloggers", 0) + oz.get("bloggers", 0)
        vk_spend = wb.get("vk", 0) + oz.get("vk", 0)
        creators_spend = wb.get("creators", 0)

        result_by_period[period] = {
            "bloggers": {"spend_rub": bloggers_spend, "drr_pct": drr(bloggers_spend)},
            "vk": {"spend_rub": vk_spend, "drr_pct": drr(vk_spend)},
            "creators": {"spend_rub": creators_spend, "drr_pct": drr(creators_spend)},
            "internal_wb": {"spend_rub": wb.get("internal", 0), "drr_pct": drr(wb.get("internal", 0))},
            "orders_rub": orders_rub,
        }

    return {
        **result_by_period,
        "manual_fill_required": ["yandex", "vk_seeds_contractor"],
        "note": (
            "ВК и блогеры агрегированы в группы. "
            "Разбивка на посевы ВК / посевы подрядчик / таргет — недоступна из БД. "
            "Яндекс — заполнить вручную из рекламного кабинета."
        ),
        "period": {
            "current_start": str(current_start),
            "current_end": str(current_end),
        },
    }


if __name__ == "__main__":
    data = collect()
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Реклама сохранена → {OUTPUT_PATH}")
    for channel, stats in data.get("current", {}).items():
        if isinstance(stats, dict) and "spend_rub" in stats:
            print(f"  {channel:20s}  {stats['spend_rub']:>10,.0f} ₽  ДРР {stats['drr_pct']:.1f}%")
```

- [ ] **Шаг 4: Запустить тесты**

```bash
python -m pytest tests/coo_report/test_ads.py -v
```

Ожидаем: 3 PASSED

- [ ] **Шаг 5: Коммит**

```bash
git add modules/coo-report/collectors/ads.py tests/coo_report/test_ads.py
git commit -m "feat(coo-report): add ads collector with channel split and manual-fill flags"
```

---

## Задача 6: Сборщик команды (team.py)

**Файлы:**
- Создать: `modules/coo-report/collectors/team.py`
- Создать: `tests/coo_report/test_team.py`

Читает `/tmp/bitrix_report_data.json`. Если файл старше 24 часов — запускает `modules/bitrix-analytics/fetch_data.py` через subprocess перед чтением.

Задача считается просроченной если: STATUS не в `BITRIX_DONE_STATUSES` И DEADLINE < сегодня.

- [ ] **Шаг 1: Написать тесты**

```python
# tests/coo_report/test_team.py
import json
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from modules.coo_report.collectors.team import parse_staff_tasks, is_overdue


TODAY = date.today()
PAST_DEADLINE = (TODAY - timedelta(days=3)).strftime("%Y-%m-%dT23:59:59+03:00")
FUTURE_DEADLINE = (TODAY + timedelta(days=3)).strftime("%Y-%m-%dT23:59:59+03:00")

SAMPLE_TASKS = [
    {"ID": "1", "TITLE": "Сделать P&L", "STATUS": "3", "RESPONSIBLE_ID": "1435",
     "DEADLINE": PAST_DEADLINE, "CLOSED_DATE": "2026-05-05T10:00:00+03:00"},
    {"ID": "2", "TITLE": "Проверить WB", "STATUS": "2", "RESPONSIBLE_ID": "1435",
     "DEADLINE": FUTURE_DEADLINE, "CLOSED_DATE": None},
    {"ID": "3", "TITLE": "Просрочена задача", "STATUS": "2", "RESPONSIBLE_ID": "1435",
     "DEADLINE": PAST_DEADLINE, "CLOSED_DATE": None},
    {"ID": "4", "TITLE": "Задача Дмитрия", "STATUS": "2", "RESPONSIBLE_ID": "17",
     "DEADLINE": FUTURE_DEADLINE, "CLOSED_DATE": None},
]

SAMPLE_STAFF = {
    "1435": {"name": "Артем Колчин", "department": "Финансы", "role": "Финансовый менеджер"},
    "17":   {"name": "Дмитрий Дрозд", "department": "Склад / Закупки", "role": "Руководитель склада"},
}


def test_overdue_detection():
    task_overdue = {"STATUS": "2", "DEADLINE": PAST_DEADLINE}
    task_done = {"STATUS": "3", "DEADLINE": PAST_DEADLINE}
    task_future = {"STATUS": "2", "DEADLINE": FUTURE_DEADLINE}

    assert is_overdue(task_overdue) is True
    assert is_overdue(task_done) is False
    assert is_overdue(task_future) is False


def test_parse_counts_correctly():
    result = parse_staff_tasks(SAMPLE_TASKS, SAMPLE_STAFF)

    artem = result[1435]  # Артём Колчин
    assert artem["done"] == 1       # задача STATUS=3
    assert artem["active"] == 1     # задача STATUS=2, дедлайн в будущем (не просрочена)
    assert artem["overdue"] == 1    # задача STATUS=2, дедлайн в прошлом


def test_parse_includes_task_titles_in_done():
    result = parse_staff_tasks(SAMPLE_TASKS, SAMPLE_STAFF)

    artem = result[1435]
    assert any("P&L" in t for t in artem["done_titles"])


def test_parse_staff_isolation():
    result = parse_staff_tasks(SAMPLE_TASKS, SAMPLE_STAFF)

    # Задача Дмитрия не попадает в Артёма
    artem = result[1435]
    dmitry = result[17]
    assert artem["active"] == 1
    assert dmitry["active"] == 1
```

- [ ] **Шаг 2: Запустить тесты — убедиться что падают**

```bash
python -m pytest tests/coo_report/test_team.py -v
```

- [ ] **Шаг 3: Написать team.py**

```python
# modules/coo-report/collectors/team.py
"""Сборщик данных по задачам команды из Битрикс24."""

import json
import subprocess
import sys
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from modules.coo_report.config import COO_STAFF, BITRIX_DONE_STATUSES, BITRIX_ACTIVE_STATUSES

OUTPUT_PATH = Path("/tmp/coo_team.json")
BITRIX_DATA_PATH = Path("/tmp/bitrix_report_data.json")
FETCH_SCRIPT = PROJECT_ROOT / "modules" / "bitrix-analytics" / "fetch_data.py"
MAX_DATA_AGE_HOURS = 24


def is_overdue(task: dict) -> bool:
    """Задача просрочена если: не завершена И дедлайн в прошлом."""
    if task.get("STATUS") in BITRIX_DONE_STATUSES:
        return False
    deadline_str = task.get("DEADLINE", "")
    if not deadline_str:
        return False
    try:
        # Битрикс возвращает ISO 8601 с таймзоной, например 2026-05-07T23:59:59+03:00
        deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
        now = datetime.now(timezone(timedelta(hours=3)))  # UTC+3
        return deadline < now
    except (ValueError, TypeError):
        return False


def _ensure_fresh_data() -> bool:
    """
    Проверяет возраст /tmp/bitrix_report_data.json.
    Если файл старше MAX_DATA_AGE_HOURS или не существует — перезапускает fetch_data.py.
    Возвращает True если данные актуальны, False если пришлось обновить.
    """
    if BITRIX_DATA_PATH.exists():
        age_hours = (datetime.now().timestamp() - BITRIX_DATA_PATH.stat().st_mtime) / 3600
        if age_hours < MAX_DATA_AGE_HOURS:
            return True

    print(f"Данные Битрикс устарели или отсутствуют, обновляю...", file=sys.stderr)
    result = subprocess.run(
        [sys.executable, str(FETCH_SCRIPT), "--days", "7", "--output", str(BITRIX_DATA_PATH)],
        capture_output=True, text=True, timeout=300,
    )
    return result.returncode == 0


def parse_staff_tasks(tasks: list, staff: dict) -> dict[int, dict]:
    """
    Разбирает список задач Битрикс по сотрудникам.

    staff: {str(id): {name, department, role}} — из JSON-файла.
    Возвращает: {int(staff_id): {name, done, active, overdue, done_titles, overdue_titles}}
    """
    result: dict[int, dict] = {}

    for staff_id_str, info in staff.items():
        staff_id = int(staff_id_str)
        if staff_id not in COO_STAFF:
            continue
        result[staff_id] = {
            "name": COO_STAFF[staff_id],
            "full_name": info.get("name", ""),
            "role": info.get("role", ""),
            "done": 0,
            "active": 0,
            "overdue": 0,
            "done_titles": [],
            "overdue_titles": [],
            "active_titles": [],
        }

    for task in tasks:
        try:
            responsible_id = int(task.get("RESPONSIBLE_ID", 0))
        except (ValueError, TypeError):
            continue

        if responsible_id not in result:
            continue

        person = result[responsible_id]
        status = str(task.get("STATUS", ""))
        title = task.get("TITLE", "—")

        if status in BITRIX_DONE_STATUSES:
            person["done"] += 1
            person["done_titles"].append(title)
        elif is_overdue(task):
            person["overdue"] += 1
            person["overdue_titles"].append(title)
        elif status in BITRIX_ACTIVE_STATUSES:
            person["active"] += 1
            person["active_titles"].append(title)

    return result


def collect(ref_date: date = None) -> dict:
    refreshed = _ensure_fresh_data()

    if not BITRIX_DATA_PATH.exists():
        return {
            "error": "Данные Битрикс недоступны — fetch_data.py не запустился",
            "staff": {},
        }

    raw = json.loads(BITRIX_DATA_PATH.read_text(encoding="utf-8"))
    tasks = raw.get("tasks", [])
    staff = raw.get("staff", {})
    period = raw.get("period", {})

    parsed = parse_staff_tasks(tasks, staff)

    return {
        "staff": {str(k): v for k, v in parsed.items()},
        "data_refreshed": not refreshed,
        "bitrix_period": period,
    }


if __name__ == "__main__":
    data = collect()
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Команда сохранена → {OUTPUT_PATH}")
    for uid, info in data.get("staff", {}).items():
        name = info.get("name", uid)
        print(f"  {name:12s}  выполнено {info['done']}  в работе {info['active']}  просрочено {info['overdue']}")
```

- [ ] **Шаг 4: Запустить тесты**

```bash
python -m pytest tests/coo_report/test_team.py -v
```

Ожидаем: 4 PASSED

- [ ] **Шаг 5: Коммит**

```bash
git add modules/coo-report/collectors/team.py tests/coo_report/test_team.py
git commit -m "feat(coo-report): add team collector with overdue detection from Bitrix"
```

---

## Задача 7: SKILL.md — инструкция для Claude

**Файлы:**
- Создать: `modules/coo-report/SKILL.md`
- Создать: `.claude/skills/coo-report` (симлинк или копия SKILL.md — по аналогии с другими скиллами)

- [ ] **Шаг 1: Проверить как подключены другие скиллы**

```bash
ls -la /Users/danilamatveev/Projects/Wookiee/.claude/skills/ | head -5
```

- [ ] **Шаг 2: Написать SKILL.md**

```markdown
# /coo-report — Еженедельный отчёт COO

**Запуск:** `/coo-report`

## Что делает

Собирает данные из 5 источников параллельно, проверяет на аномалии и создаёт
заполненную страницу в Notion по шаблону Елизаветы Литвиновой (COO).

## Шаги выполнения

### Шаг 1 — Запустить все сборщики параллельно

Запускай все 5 команд одновременно в отдельных Bash-вызовах:

```bash
cd /path/to/project && python modules/coo-report/collectors/finance.py
```
```bash
cd /path/to/project && python modules/coo-report/collectors/models.py
```
```bash
cd /path/to/project && python modules/coo-report/collectors/logistics.py
```
```bash
cd /path/to/project && python modules/coo-report/collectors/ads.py
```
```bash
cd /path/to/project && python modules/coo-report/collectors/team.py
```

### Шаг 2 — Проверить аномалии в каждом JSON

Прочитай каждый файл и проверь:

**Стоп (не публиковать, сообщить пользователю):**
- `/tmp/coo_finance.json`: `combined.current.orders_count == 0` → данные не пришли
- `/tmp/coo_finance.json`: `combined.current.drr_total_pct > 100` → ДРР некорректная
- `/tmp/coo_finance.json`: `combined.current.margin < -0.5 * combined.current.revenue_after_spp`

**Предупреждение (публиковать с флагом ⚠️ в ячейке):**
- `/tmp/coo_models.json`: любая модель с `trend_pct > 300` или `trend_pct < -80`
- `/tmp/coo_logistics.json`: `localization_warning == true`
- `/tmp/coo_logistics.json`: любая модель с `turnover_days > 180`
- `/tmp/coo_team.json`: `data_refreshed == false` → данные Битрикс старые

### Шаг 3 — Синтез: заполнить разделы отчёта

На основе прочитанных JSON заполни:

**Раздел 1 (Финансы):** таблица P&L из `/tmp/coo_finance.json`.
- Неделя 1 = previous, Неделя 2 = current
- ДРР от заказов = `drr_total_pct`, внутренняя = `drr_internal_pct`, внешняя = `drr_external_pct`
- Выкуп % — лаговый показатель, пометить "(лаг 3-21 дн.)"

**Раздел 6 (Комплекты):** таблица по 16 моделям из `/tmp/coo_models.json`.
- Тренд: если `trend_pct > 10` → "↑ рост", если `< -10` → "↓ падение", иначе "→ стабильно"
- Статус продаж: выручка > 500K → "Активно", 100-500K → "Умеренно", < 100K → "Слабо"
- Поля "Проблема" и "Действие" — формулируй сам на основе ДРР, маржи и тренда

**Раздел 7 (Реклама):** из `/tmp/coo_ads.json`.
- Каналы bloggers, vk, creators заполни автоматически
- Яндекс и "Посевы подрядчик" — поставь "⚠️ заполнить вручную"

**Раздел 8 (Логистика):** из `/tmp/coo_logistics.json`.
- Индекс локализации: значение + статус (≥65% → 🟢, 50-65% → 🟡, <50% → 🔴)
- Оборачиваемость: значение + статус (<60 дн → 🟢, 60-90 → 🟡, >90 → 🔴)

**Раздел 9 (Сотрудники):** из `/tmp/coo_team.json`.
- "Что выполнено" — первые 2-3 задачи из `done_titles`
- Оценка: нет просрочек → 🟢, 1-2 просрочки → 🟡, 3+ просрочки → 🔴

**Разделы 2-3 (Проблемы и решения):** сформулируй сам на основе всех данных.
- Главная проблема — то, что сильнее всего отклонилось от нормы
- Решение — конкретное действие с ответственным

### Шаг 4 — Создать страницу в Notion

1. Дублируй шаблон `35658a2bd5878028ad75f1773a0f8593` через Notion MCP
2. Переименуй: `Отчётность COO {дата_начала} — {дата_конца}` (из `period.current_start`)
3. Помести в папку `35658a2bd587803b8ab5fc540e4318e7`
4. Заполни все разделы согласно шагу 3
5. Разделы 4, 5, 10, 11, 12 оставь пустыми с текстом "← заполнить вручную"
6. Выведи ссылку на страницу

## Зависимости

- PostgreSQL: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- WB API: `WB_API_KEY_OOO`, `WB_API_KEY_IP`
- МойСклад API: `MOYSKLAD_TOKEN`
- Битрикс24: `Bitrix_rest_api`
- Notion: `NOTION_TOKEN`
```

- [ ] **Шаг 3: Подключить скилл (по аналогии с другими)**

```bash
# Проверяем формат других скиллов, создаём папку
ls /Users/danilamatveev/Projects/Wookiee/.claude/skills/finance-report/
```

Если скиллы — это папки с `SKILL.md`, создать:
```bash
mkdir -p /Users/danilamatveev/Projects/Wookiee/.claude/skills/coo-report
cp modules/coo-report/SKILL.md .claude/skills/coo-report/SKILL.md
```

- [ ] **Шаг 4: Прогнать все тесты модуля**

```bash
python -m pytest tests/coo_report/ -v
```

Ожидаем: все тесты PASSED (15+ штук)

- [ ] **Шаг 5: Финальный коммит**

```bash
git add modules/coo-report/SKILL.md .claude/skills/coo-report/
git commit -m "feat(coo-report): add SKILL.md and register /coo-report skill

Скилл запускает 5 параллельных сборщиков, проверяет аномалии
и создаёт заполненную страницу в Notion по шаблону COO.
Автоматически заполняет разделы 1, 6, 7, 8, 9.
Разделы 4, 5, 10-12 остаются для ручного заполнения Елизаветой."
```

---

## Итоговый прогон

- [ ] **Финальная проверка всех тестов**

```bash
python -m pytest tests/coo_report/ -v --tb=short
```

Ожидаем: 15+ PASSED, 0 FAILED

- [ ] **Проверка что все 5 сборщиков запускаются как скрипты**

```bash
python modules/coo-report/collectors/finance.py
python modules/coo-report/collectors/models.py
python modules/coo-report/collectors/ads.py
```

(logistics и team требуют реальных API-ключей — проверяются вручную)
