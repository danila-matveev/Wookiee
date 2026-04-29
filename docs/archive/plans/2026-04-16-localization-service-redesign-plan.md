# WB Localization Service Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Превратить `services/wb_localization/` в единый модульный сервис с расширенным справочником, градацией сценариев экономики (30–90%) и понедельным прогнозом перестановок на 13 недель.

**Architecture:** Расширение существующего сервиса. Новые калькуляторы в `calculators/` (чистые функции), монолитный `sheets_export.py` (59KB) распиливается на пакет `sheets_export/` по смыслу. История обогащается таблицей `weekly_snapshots` для точного forecast.

**Tech Stack:** Python 3.11, pytest, pandas, gspread, SQLite (история), Google Sheets API v4.

**Spec:** `docs/superpowers/specs/2026-04-16-localization-service-redesign-design.md` (архив, файл удалён)

---

## Выполнение и навигация

Задачи сгруппированы по волнам. Внутри волны задачи независимы и могут выполняться параллельно субагентами. Между волнами — точки синхронизации (коммит + верификация).

- **Волна 1 (подготовка):** Верификация КТР + рефакторинг sheets_export
- **Волна 2 (калькуляторы):** Три независимых калькулятора + расширение history
- **Волна 3 (листы):** Три независимых sheet writer'а
- **Волна 4 (интеграция):** Обновление `run_localization.py`, CLI-флаги, end-to-end проверка

---

## Волна 1 — Подготовка

### Task 1: Верификация коэффициентов КТР

**Files:**
- Read: `services/wb_localization/irp_coefficients.py`
- Read: `tests/wb_localization/test_irp_coefficients.py`
- Create: `docs/database/KTR_SYNC_VERIFICATION.md`

**Context:** Research agent нашёл расхождение между `COEFF_TABLE` и официальной WB таблицей (например, 2.20 vs 2.00 при 0–5%). Но существующий тест `test_irp_coefficients.py` датирован 27.03.2026 и утверждает что текущие значения "updated". Нужно верифицировать прежде чем менять.

- [ ] **Step 1: Прочитать текущий COEFF_TABLE**

```bash
cat services/wb_localization/irp_coefficients.py | head -60
```

Ожидается: 20 строк в COEFF_TABLE формата `(min_loc, max_loc, ktr, krp_pct)`.

- [ ] **Step 2: Прочитать существующие тесты**

```bash
cat tests/wb_localization/test_irp_coefficients.py
```

Ожидается: параметризованные тесты с комментариями типа "был X → стал Y".

- [ ] **Step 3: Создать документ сверки**

Создать `docs/database/KTR_SYNC_VERIFICATION.md` со структурой:

```markdown
# Сверка КТР: код vs WB official

**Дата:** 2026-04-16
**Источники:**
- Код: `services/wb_localization/irp_coefficients.py` (обновлён 27.03.2026)
- WB official: https://seller.wildberries.ru/instructions/ru/ru/material/localization-index

## Таблица сравнения

| Диапазон лок.% | КТР в коде | КТР по WB | Расхождение |
|---|---|---|---|
| 95–100 | 0.50 | 0.50 | — |
| 90–94.99 | 0.60 | 0.60 | — |
| ... (заполнить все 20) | | | |

## Решение

- [ ] Совпадает — никаких изменений
- [ ] Расходится — обновить `COEFF_TABLE` + тесты
- [ ] Требует подтверждения пользователя
```

Заполнить таблицу вручную сверяя каждую строку.

- [ ] **Step 4: Коммит**

```bash
git add docs/database/KTR_SYNC_VERIFICATION.md
git commit -m "docs: add КТР verification report (code vs WB official)"
```

- [ ] **Step 5: Решение о синхронизации**

Если расхождение обнаружено — создать отдельную задачу "Task 1b: Обновление COEFF_TABLE" с изменением значений и тестов. Если совпадает — пропустить, отметить в документе.

**Gate:** Пользователь подтверждает решение прежде чем двигаться дальше.

---

### Task 2: Рефакторинг `sheets_export.py` в пакет `sheets_export/`

**Files:**
- Move: `services/wb_localization/sheets_export.py` → `services/wb_localization/sheets_export/__init__.py`
- Create: `services/wb_localization/sheets_export/formatters.py`
- Create: `services/wb_localization/sheets_export/core_sheets.py`
- Create: `services/wb_localization/sheets_export/analysis_sheets.py`
- Test: `tests/wb_localization/test_sheets_export_refactor.py`

**Context:** Текущий `sheets_export.py` (59KB, ~1100 строк) содержит ~10 методов записи листов + общие форматтеры. Разбиваем на модули по смыслу. Это чистый рефакторинг — поведение не меняется, тесты должны пройти без изменений.

- [ ] **Step 1: Smoke-тест текущего экспорта**

```bash
python -m services.wb_localization.run_localization --cabinet ooo --dry-run 2>&1 | tail -20
```

Сохранить вывод в `/tmp/export_before.log` для сравнения после рефакторинга.

- [ ] **Step 2: Создать файл-структуру пакета**

```bash
mkdir -p services/wb_localization/sheets_export
touch services/wb_localization/sheets_export/__init__.py
touch services/wb_localization/sheets_export/formatters.py
touch services/wb_localization/sheets_export/core_sheets.py
touch services/wb_localization/sheets_export/analysis_sheets.py
```

- [ ] **Step 3: Перенести форматтеры в `formatters.py`**

Из `sheets_export.py` в `sheets_export/formatters.py` переносятся функции (сохранять приватный `_` префикс):
- `_header_fmt`, `_meta_fmt`
- `_col_widths`, `_row_height`
- `_freeze`, `_borders`, `_banding`, `_clear_banding`
- `_num_fmt`, `_bold_col`
- Любые другие helper-функции форматирования

Использовать точное копирование (с `git mv` логикой вручную через copy + delete из старого файла):

```python
# sheets_export/formatters.py
"""Общие форматтеры для всех листов сервиса WB Localization."""
from __future__ import annotations
# ... импорты gspread/google API как в оригинале

def _header_fmt(sheet_id: int, row_idx: int, num_cols: int) -> dict:
    # ... тело функции 1-в-1 из оригинала
    ...
```

- [ ] **Step 4: Перенести core sheet writers в `core_sheets.py`**

В `sheets_export/core_sheets.py` переносятся:
- `_write_moves` → `write_moves`
- `_write_supplies` → `write_supplies`
- `_write_summary` → `write_summary`
- `_write_regions` → `write_regions`
- `_write_top_problems` → `write_top_problems`

Они становятся публичными (без `_`), так как теперь вызываются из `__init__.py`. Импорт форматтеров:

```python
# sheets_export/core_sheets.py
from .formatters import _header_fmt, _col_widths, _freeze, _borders, _banding, _num_fmt, _bold_col
```

- [ ] **Step 5: Перенести analysis sheet writer в `analysis_sheets.py`**

В `sheets_export/analysis_sheets.py`:
- `_write_il_analysis` → `write_il_analysis`
- `_apply_il_formatting` → `_apply_il_formatting` (приватный helper остаётся приватным, используется только тут)

Также перенести `_write_economics_sheet` сюда временно (будет заменён на новый scenario_sheet в задаче 7):
- `_write_economics_sheet` → `write_economics_sheet` (помечен как LEGACY в docstring)

- [ ] **Step 6: Создать фасад `sheets_export/__init__.py`**

```python
# sheets_export/__init__.py
"""Фасад экспорта в Google Sheets. Реэкспортирует публичное API."""
from __future__ import annotations
from typing import Any

from .core_sheets import (
    write_moves,
    write_supplies,
    write_summary,
    write_regions,
    write_top_problems,
)
from .analysis_sheets import (
    write_il_analysis,
    write_economics_sheet,  # legacy, будет заменён
)


def export_to_sheets(payload: dict[str, Any]) -> None:
    """Главная точка входа — координирует запись всех листов.

    Args:
        payload: dict с ключами cabinet, core, il_irp, economics (legacy),
                 scenarios (optional), forecast (optional).
    """
    # Тело функции переносится 1-в-1 из старого sheets_export.py
    # с изменением внутренних вызовов _write_* на write_*
    ...


# Прочее публичное API которое вызывается извне
from .core_sheets import export_dashboard  # если есть
from .analysis_sheets import append_history  # если есть
```

- [ ] **Step 7: Удалить старый `sheets_export.py`**

```bash
rm services/wb_localization/sheets_export.py
```

- [ ] **Step 8: Обновить импорты в `run_localization.py`**

Старый импорт:
```python
from services.wb_localization.sheets_export import export_to_sheets
```

Новый импорт (остался прежним — пакет экспортирует тот же символ):
```python
from services.wb_localization.sheets_export import export_to_sheets
```

Проверить: других импортов из `sheets_export` в кодбазе не должно быть. Запустить:
```bash
grep -rn "from services.wb_localization.sheets_export" --include="*.py"
```

Все импорты должны работать через фасад — старые имена с `_write_*` могут сломаться, но их никто извне не должен использовать.

- [ ] **Step 9: Запустить smoke-тест после рефакторинга**

```bash
python -m services.wb_localization.run_localization --cabinet ooo --dry-run 2>&1 | tail -20 > /tmp/export_after.log
diff /tmp/export_before.log /tmp/export_after.log
```

Ожидается: только различия в timestamp'ах, логика идентична.

- [ ] **Step 10: Прогнать существующие тесты**

```bash
pytest tests/wb_localization/ -v 2>&1 | tail -30
```

Ожидается: все тесты проходят (не было тестов на sheets_export — это рефакторинг).

- [ ] **Step 11: Коммит**

```bash
git add services/wb_localization/sheets_export/ services/wb_localization/run_localization.py
git rm services/wb_localization/sheets_export.py
git commit -m "refactor(wb_localization): split sheets_export.py into package

Разбиение монолита (59KB) на модули по смыслу:
- formatters.py — общие хелперы
- core_sheets.py — Перемещения/Допоставки/Сводка/Регионы/Проблемные SKU
- analysis_sheets.py — ИЛ Анализ + legacy Экономика
- __init__.py — фасад с export_to_sheets()

Поведение не меняется, готовимся к добавлению новых листов."
```

---

## Волна 2 — Калькуляторы

Три независимые задачи + расширение истории. Можно выполнять параллельно.

### Task 3: Калькулятор `reference_builder.py`

**Files:**
- Create: `services/wb_localization/calculators/reference_builder.py`
- Test: `tests/wb_localization/test_reference_builder.py`

**Context:** Строит структурированные данные для расширенного листа «Справочник». Чистая функция — только читает `COEFF_TABLE` и `REDISTRIBUTION_LIMITS`, возвращает dict. Не знает про Sheets.

- [ ] **Step 1: Написать failing-тест — структура вывода**

`tests/wb_localization/test_reference_builder.py`:
```python
"""Тесты reference_builder."""
from services.wb_localization.calculators.reference_builder import build_reference_content


def test_build_reference_structure_has_all_sections():
    result = build_reference_content()
    assert "cover" in result
    assert "formula_block" in result
    assert "il_section" in result
    assert "irp_section" in result
    assert "exceptions" in result
    assert "relocation_section" in result
    assert "sliding_window" in result
    assert "disclaimer" in result


def test_il_section_has_full_ktr_table():
    result = build_reference_content()
    ktr_table = result["il_section"]["table"]
    assert len(ktr_table) == 20  # 20 диапазонов в COEFF_TABLE
    # Проверка структуры первой строки
    first = ktr_table[0]
    assert "min_loc" in first
    assert "max_loc" in first
    assert "ktr" in first
    assert "color" in first  # для раскраски


def test_irp_section_has_krp_table():
    result = build_reference_content()
    krp_table = result["irp_section"]["table"]
    # КРП имеет 13 уникальных значений (0-60 = 0%, остальные уникальны)
    assert len(krp_table) >= 13


def test_relocation_section_has_warehouses():
    result = build_reference_content()
    relocation = result["relocation_section"]
    assert relocation["commission_pct"] == 0.5
    assert relocation["lock_in_days"] == 90
    warehouses = relocation["warehouses"]
    assert len(warehouses) >= 20
    first = warehouses[0]
    assert "name" in first
    assert "limit_per_day" in first


def test_sliding_window_has_weeks_to_threshold():
    result = build_reference_content()
    window = result["sliding_window"]
    weeks = window["weeks_to_threshold"]
    # Примеры: из 40% до 60%, из 50% до 60%, из 55% до 60%
    from_values = [w["from_loc"] for w in weeks]
    assert 40 in from_values
    assert 50 in from_values
    assert 55 in from_values
```

- [ ] **Step 2: Запустить тест — убедиться падает**

```bash
pytest tests/wb_localization/test_reference_builder.py -v
```

Ожидается: FAIL — `ModuleNotFoundError: No module named 'services.wb_localization.calculators.reference_builder'`.

- [ ] **Step 3: Реализовать `reference_builder.py`**

```python
# services/wb_localization/calculators/reference_builder.py
"""Строит структуру данных для листа «Справочник» (пояснительная документация)."""
from __future__ import annotations
from typing import Any

from services.wb_localization.irp_coefficients import (
    COEFF_TABLE,
    REDISTRIBUTION_LIMITS,
)


def _ktr_color(ktr: float) -> str:
    """Цвет строки в таблице КТР по значению множителя."""
    if ktr <= 0.90:
        return "green"
    if ktr <= 1.00:
        return "yellow"
    return "red"


def _weeks_until_threshold(current_loc: float, target: float = 60.0) -> str:
    """Оценка: сколько недель до достижения порога при идеальной локализации в новых неделях.

    Формула: blended(t) = ((13-t)*current + t*100) / 13 >= target
    => t >= (target*13 - 13*current) / (100 - current)
    """
    if current_loc >= target:
        return "порог достигнут"
    t_exact = (target * 13 - 13 * current_loc) / (100 - current_loc)
    import math
    t_ceil = math.ceil(t_exact)
    return f"{t_ceil} недель"


def build_reference_content() -> dict[str, Any]:
    """Собирает структуру данных справочника.

    Returns:
        Словарь с 8 секциями: cover, formula_block, il_section, irp_section,
        exceptions, relocation_section, sliding_window, disclaimer.
    """
    # KTR table
    ktr_table = []
    for min_loc, max_loc, ktr, krp in COEFF_TABLE:
        ktr_table.append({
            "min_loc": min_loc,
            "max_loc": max_loc,
            "ktr": ktr,
            "description": (
                "Скидка" if ktr < 1.0
                else "Базовый" if ktr == 1.0
                else "Штраф"
            ),
            "color": _ktr_color(ktr),
        })

    # KRP table
    krp_table = []
    for min_loc, max_loc, ktr, krp in COEFF_TABLE:
        krp_table.append({
            "min_loc": min_loc,
            "max_loc": max_loc,
            "krp_pct": krp,
            "description": "Нет надбавки" if krp == 0 else f"+{krp:.2f}% к цене",
            "color": "green" if krp == 0 else "red",
        })

    # Warehouses with limits
    warehouses = [
        {"name": name, "limit_per_day": limit}
        for name, limit in sorted(
            REDISTRIBUTION_LIMITS.items(),
            key=lambda x: -x[1],
        )
    ]

    # Weeks to threshold table
    weeks_table = [
        {"from_loc": loc, "to_loc": 60.0, "weeks": _weeks_until_threshold(loc)}
        for loc in [30, 40, 45, 50, 55, 58]
    ]

    return {
        "cover": {
            "title": "📘 СПРАВОЧНИК: ИЛ, ИРП и перестановки",
            "subtitle": "Полная документация по логистике Wildberries",
        },
        "formula_block": {
            "formula": "Логистика = (База × Коэф.склада × ИЛ) + (Цена × ИРП%)",
            "components": [
                {"name": "База", "desc": "Стоимость 1 литра + доп. литры"},
                {"name": "Коэф.склада", "desc": "Индивидуален для каждого склада WB"},
                {"name": "ИЛ", "desc": "Индекс локализации (КТР-множитель, 0.50–2.00)"},
                {"name": "ИРП%", "desc": "Надбавка к цене (0.00–2.50%)"},
            ],
            "example": {
                "price": 1000,
                "volume_liters": 3,
                "base": 74.0,  # 46 + 2*14
                "warehouse_coeff": 1.0,
                "article_loc_pct": 45.0,
                "article_ktr": 1.20,
                "article_krp_pct": 2.05,
                "cabinet_il": 1.05,
                "cabinet_irp_pct": 1.15,
                "volume_part": 77.70,
                "price_part": 11.50,
                "total": 89.20,
            },
        },
        "il_section": {
            "title": "Индекс локализации (ИЛ)",
            "definition": (
                "Локальный заказ = склад отгрузки и адрес доставки "
                "в одном федеральном округе (или объединённой зоне)."
            ),
            "formula": "ИЛ = Σ(заказы_артикула × КТР_артикула) / Всего_заказов",
            "period_note": "Скользящие 13 недель. Обновление — воскресенье→понедельник.",
            "table": ktr_table,
            "example": {
                "loc_pct": 40,
                "ktr": 1.30,
                "meaning": "платите 1.30× базовой логистики = +30%",
            },
        },
        "irp_section": {
            "title": "Индекс распределения продаж (ИРП)",
            "definition": "ИРП оценивает распределение локализации по артикулам.",
            "formula": "ИРП = Σ(заказы_артикула × КРП%_артикула) / Всего_заказов",
            "critical_threshold": {
                "value": 60.0,
                "note": "При локализации 60%+ КРП резко падает с 2.00% до 0.00%",
            },
            "table": krp_table,
            "example": {
                "article_loc": 55,
                "price": 1000,
                "orders_monthly": 500,
                "krp_pct": 2.00,
                "irp_monthly_rub": 10000,
            },
        },
        "exceptions": {
            "categories": ["КГТ", "СГТ", "КБТ", "FBS"],
            "rule_35": (
                "Если исключений > 35% от всех заказов артикула, "
                "ВЕСЬ артикул становится исключением (КРП=0%, не считается в ИЛ/ИРП)."
            ),
            "krp_for_exceptions": 0.0,
        },
        "relocation_section": {
            "title": "Перераспределение товаров (перестановки)",
            "commission_pct": 0.5,
            "lock_in_days": 90,
            "description": (
                "Опт-ин сервис в Конструкторе тарифов. Позволяет вручную перемещать "
                "сток между складами WB. Комиссия +0.5% на ВСЕ продажи, не только "
                "перемещённые. Отключить нельзя раньше 90 дней."
            ),
            "warehouses": warehouses,
            "economics_example": {
                "turnover_monthly": 5_000_000,
                "commission_monthly": 25_000,
                "breakeven": "экономия на логистике > 25 000 ₽/мес",
            },
        },
        "sliding_window": {
            "title": "Скользящее окно 13 недель",
            "explanation": (
                "Индекс считается за 13 последних календарных недель. "
                "Одна неделя идеальной локализации даёт +1/13 к индексу."
            ),
            "formula": "loc_week_t = ((13 - t) × loc_before + t × loc_after) / 13",
            "weeks_to_threshold": weeks_table,
            "call_to_action": (
                "Начинать перестановки надо СЕЙЧАС — эффект отложенный на 2–9 недель."
            ),
        },
        "disclaimer": {
            "title": "Наш расчёт vs WB",
            "note": (
                "Наш расчёт — на календарных днях. WB — на ISO-неделях. "
                "Расхождение ≤ 3 п.п. Точные значения — в ЛК WB."
            ),
        },
    }
```

- [ ] **Step 4: Запустить тест — убедиться проходит**

```bash
pytest tests/wb_localization/test_reference_builder.py -v
```

Ожидается: все 5 тестов PASS.

- [ ] **Step 5: Коммит**

```bash
git add services/wb_localization/calculators/reference_builder.py tests/wb_localization/test_reference_builder.py
git commit -m "feat(wb_localization): add reference_builder calculator

Чистая функция build_reference_content() собирает структурированные
данные для листа «Справочник» из COEFF_TABLE и REDISTRIBUTION_LIMITS.
8 секций: cover, formula_block, il_section, irp_section, exceptions,
relocation_section, sliding_window, disclaimer."
```

---

### Task 4: Калькулятор `scenario_engine.py` (градация 30–90%)

**Files:**
- Create: `services/wb_localization/calculators/scenario_engine.py`
- Test: `tests/wb_localization/test_scenario_engine.py`

**Context:** Считает экономику кабинета при разных уровнях локализации на реальных артикулах. Использует уже посчитанный `il_irp` (output `analyze_il_irp`) и `logistics_costs` (факт по артикулам). Возвращает сценарии + топ-артикулы + экономику перестановок.

- [ ] **Step 1: Написать failing-тесты**

`tests/wb_localization/test_scenario_engine.py`:
```python
"""Тесты scenario_engine."""
import pytest
from services.wb_localization.calculators.scenario_engine import analyze_scenarios


@pytest.fixture
def sample_il_irp():
    """Минимальный il_irp результат с 2 артикулами."""
    return {
        "articles": [
            {
                "article": "wendy/xl",
                "loc_pct": 40.0,
                "ktr": 1.30,
                "krp_pct": 2.10,
                "wb_total": 100,
                "price": 1000.0,
                "irp_per_month": 2100.0,
            },
            {
                "article": "sunny/m",
                "loc_pct": 80.0,
                "ktr": 0.80,
                "krp_pct": 0.00,
                "wb_total": 50,
                "price": 2000.0,
                "irp_per_month": 0.0,
            },
        ],
        "summary": {
            "overall_il": 1.13,
            "total_rf_orders": 150,
        },
    }


@pytest.fixture
def sample_logistics_costs():
    """Фактические расходы на логистику за период (30 дней)."""
    return {
        "wendy/xl": 5200.0,  # 52₽/заказ × 100 заказов
        "sunny/m": 3200.0,   # 64₽/заказ × 50 заказов
    }


def test_analyze_scenarios_returns_all_levels(sample_il_irp, sample_logistics_costs):
    result = analyze_scenarios(
        il_irp=sample_il_irp,
        logistics_costs=sample_logistics_costs,
        turnover_rub=200_000.0,
        period_days=30,
    )
    scenarios = result["scenarios"]
    levels = [s["level_pct"] for s in scenarios]
    assert levels == [30, 40, 50, 60, 70, 80, 90]


def test_scenario_has_required_fields(sample_il_irp, sample_logistics_costs):
    result = analyze_scenarios(
        il_irp=sample_il_irp,
        logistics_costs=sample_logistics_costs,
        turnover_rub=200_000.0,
        period_days=30,
    )
    first = result["scenarios"][0]
    assert "level_pct" in first
    assert "ktr" in first
    assert "krp_pct" in first
    assert "logistics_monthly" in first
    assert "irp_monthly" in first
    assert "total_monthly" in first
    assert "delta_vs_current" in first
    assert "color" in first


def test_60pct_scenario_has_zero_irp(sample_il_irp, sample_logistics_costs):
    """На 60% локализации КРП=0 для всех артикулов."""
    result = analyze_scenarios(
        il_irp=sample_il_irp,
        logistics_costs=sample_logistics_costs,
        turnover_rub=200_000.0,
        period_days=30,
    )
    sc_60 = next(s for s in result["scenarios"] if s["level_pct"] == 60)
    assert sc_60["irp_monthly"] == 0.0


def test_higher_localization_means_lower_total(sample_il_irp, sample_logistics_costs):
    """Чем выше локализация, тем меньше общие расходы (монотонность)."""
    result = analyze_scenarios(
        il_irp=sample_il_irp,
        logistics_costs=sample_logistics_costs,
        turnover_rub=200_000.0,
        period_days=30,
    )
    totals = [s["total_monthly"] for s in result["scenarios"]]
    # 30% → 90% расходы должны падать (с учётом порогов возможны плато)
    assert totals[0] >= totals[-1]  # 30% дороже 90%


def test_top_articles_sorted_by_savings(sample_il_irp, sample_logistics_costs):
    result = analyze_scenarios(
        il_irp=sample_il_irp,
        logistics_costs=sample_logistics_costs,
        turnover_rub=200_000.0,
        period_days=30,
    )
    top = result["top_articles"]
    # Wendy (40%) имеет больший потенциал экономии чем Sunny (80%)
    assert top[0]["article"] == "wendy/xl"
    # Сортировка descending
    savings = [a["savings_if_80_monthly"] for a in top]
    assert savings == sorted(savings, reverse=True)


def test_relocation_economics_calculates_breakeven(sample_il_irp, sample_logistics_costs):
    result = analyze_scenarios(
        il_irp=sample_il_irp,
        logistics_costs=sample_logistics_costs,
        turnover_rub=200_000.0,
        period_days=30,
    )
    econ = result["relocation_economics"]
    # Комиссия = 0.5% от оборота месячного = 200 000 × 0.005 = 1 000
    assert econ["commission_monthly"] == pytest.approx(1000.0, rel=0.01)
    assert econ["lock_in_days"] == 90
    assert "net_benefit_monthly" in econ


def test_current_scenario_matches_current_il(sample_il_irp, sample_logistics_costs):
    result = analyze_scenarios(
        il_irp=sample_il_irp,
        logistics_costs=sample_logistics_costs,
        turnover_rub=200_000.0,
        period_days=30,
    )
    current = result["current_scenario"]
    assert current["label"] == "Сейчас"
    # Current_il из il_irp
    assert "logistics_monthly" in current
    assert "irp_monthly" in current


def test_custom_levels(sample_il_irp, sample_logistics_costs):
    result = analyze_scenarios(
        il_irp=sample_il_irp,
        logistics_costs=sample_logistics_costs,
        turnover_rub=200_000.0,
        period_days=30,
        levels=[50, 75, 95],
    )
    levels = [s["level_pct"] for s in result["scenarios"]]
    assert levels == [50, 75, 95]
```

- [ ] **Step 2: Запустить тесты — убедиться падают**

```bash
pytest tests/wb_localization/test_scenario_engine.py -v
```

Ожидается: FAIL — модуль не существует.

- [ ] **Step 3: Реализовать `scenario_engine.py`**

```python
# services/wb_localization/calculators/scenario_engine.py
"""Сценарный анализ экономики при разных уровнях локализации.

Считает: что было бы с логистикой и ИРП кабинета, если бы локализация
была 30%, 40%, ..., 90% — на реальных артикулах и ценах.
"""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from services.wb_localization.irp_coefficients import get_ktr_krp


DEFAULT_LEVELS = [30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0]
RELOCATION_COMMISSION_PCT = 0.5
RELOCATION_LOCK_IN_DAYS = 90


def _round_rub(value: float) -> float:
    """Округление до копеек (Decimal для точности в деньгах)."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _scenario_color(level_pct: float, current_il_pct: float) -> str:
    """Цвет для строки сценария относительно текущего."""
    if level_pct < current_il_pct:
        return "red"
    if abs(level_pct - current_il_pct) < 0.01:
        return "yellow"
    return "green"


def _calc_scenario(
    level_pct: float,
    articles: list[dict],
    logistics_costs: dict[str, float],
    period_days: int,
) -> dict[str, Any]:
    """Считает метрики кабинета при заданной локализации level_pct."""
    monthly_factor = 30.0 / period_days
    target_ktr, target_krp_pct = get_ktr_krp(level_pct)

    total_logistics = 0.0
    total_irp = 0.0

    for article in articles:
        article_key = article["article"].lower() if isinstance(article["article"], str) else article["article"]
        actual_cost = logistics_costs.get(article_key)
        if actual_cost is None:
            continue

        current_ktr = article["ktr"]
        if current_ktr <= 0:
            continue

        # Обратная инверсия: сколько стоила бы логистика при КТР=1
        base_cost = actual_cost / current_ktr
        new_logistics_period = base_cost * target_ktr
        new_logistics_monthly = new_logistics_period * monthly_factor
        total_logistics += new_logistics_monthly

        price = article.get("price", 0)
        orders = article.get("wb_total", 0)
        if price > 0 and orders > 0:
            daily_orders = orders / period_days
            monthly_orders = daily_orders * 30.0
            new_irp_monthly = price * (target_krp_pct / 100.0) * monthly_orders
            total_irp += new_irp_monthly

    return {
        "logistics_monthly": _round_rub(total_logistics),
        "irp_monthly": _round_rub(total_irp),
        "total_monthly": _round_rub(total_logistics + total_irp),
        "ktr": target_ktr,
        "krp_pct": target_krp_pct,
    }


def _calc_current(
    articles: list[dict],
    logistics_costs: dict[str, float],
    period_days: int,
) -> dict[str, Any]:
    """Считает текущее состояние (per-article реальные КТР/КРП)."""
    monthly_factor = 30.0 / period_days
    total_logistics = 0.0
    total_irp = 0.0

    for article in articles:
        article_key = article["article"].lower() if isinstance(article["article"], str) else article["article"]
        actual_cost = logistics_costs.get(article_key)
        if actual_cost is None:
            continue
        total_logistics += actual_cost * monthly_factor
        total_irp += article.get("irp_per_month", 0.0)

    return {
        "logistics_monthly": _round_rub(total_logistics),
        "irp_monthly": _round_rub(total_irp),
        "total_monthly": _round_rub(total_logistics + total_irp),
    }


def _calc_top_articles(
    articles: list[dict],
    logistics_costs: dict[str, float],
    period_days: int,
    top_n: int = 15,
) -> list[dict[str, Any]]:
    """Топ-N артикулов по потенциалу экономии при переходе на 80% локализации."""
    monthly_factor = 30.0 / period_days
    target_ktr_80, target_krp_80 = get_ktr_krp(80.0)

    rows = []
    for article in articles:
        article_key = article["article"].lower() if isinstance(article["article"], str) else article["article"]
        actual_cost = logistics_costs.get(article_key)
        if actual_cost is None:
            continue
        current_ktr = article["ktr"]
        if current_ktr <= 0:
            continue

        base_cost = actual_cost / current_ktr
        actual_monthly = actual_cost * monthly_factor
        current_irp_monthly = article.get("irp_per_month", 0.0)

        if article.get("loc_pct", 0) >= 80.0:
            opt_ktr = current_ktr
        else:
            opt_ktr = target_ktr_80
        opt_logistics_monthly = base_cost * opt_ktr * monthly_factor
        savings = (actual_monthly + current_irp_monthly) - opt_logistics_monthly

        # Вклад в ИЛ кабинета: (КТР_артикула - 1) × доля заказов
        contribution = (current_ktr - 1.0) * article.get("wb_total", 0)

        rows.append({
            "article": article["article"],
            "loc_pct": article.get("loc_pct", 0.0),
            "ktr": current_ktr,
            "krp_pct": article.get("krp_pct", 0.0),
            "orders_monthly": round(article.get("wb_total", 0) * monthly_factor),
            "logistics_fact_monthly": _round_rub(actual_monthly),
            "irp_current_monthly": _round_rub(current_irp_monthly),
            "contribution_to_il": round(contribution, 1),
            "savings_if_80_monthly": _round_rub(savings),
            "status": _status_for_ktr(current_ktr),
        })

    rows.sort(key=lambda r: r["savings_if_80_monthly"], reverse=True)
    return rows[:top_n]


def _status_for_ktr(ktr: float) -> str:
    if ktr <= 0.90:
        return "🟢 Отличная"
    if ktr <= 1.05:
        return "🟡 Нейтральная"
    if ktr <= 1.30:
        return "🟠 Слабая"
    return "🔴 Критическая"


def analyze_scenarios(
    il_irp: dict[str, Any],
    logistics_costs: dict[str, float],
    turnover_rub: float,
    period_days: int = 30,
    levels: list[float] | None = None,
) -> dict[str, Any]:
    """Считает сценарии экономики при градации уровней локализации.

    Args:
        il_irp: Результат analyze_il_irp() с ключами articles, summary.
        logistics_costs: {article_lower: ₽ за period_days}.
        turnover_rub: Оборот кабинета за period_days (₽).
        period_days: Длительность периода в днях.
        levels: Уровни локализации для сценариев. Дефолт [30, 40, 50, 60, 70, 80, 90].

    Returns:
        Словарь с ключами: period_days, current_il, current_scenario, scenarios,
        top_articles, relocation_economics.
    """
    if levels is None:
        levels = DEFAULT_LEVELS

    articles = il_irp.get("articles", [])
    summary = il_irp.get("summary", {})
    current_il = summary.get("overall_il", 1.0)

    # Конвертация текущего ИЛ (КТР-множитель) в примерную локализацию %
    # Используем обратный поиск по COEFF_TABLE
    current_loc_pct = _ktr_to_loc_pct(current_il)

    scenarios = []
    for level in levels:
        sc = _calc_scenario(level, articles, logistics_costs, period_days)
        sc["level_pct"] = level
        sc["color"] = _scenario_color(level, current_loc_pct)
        scenarios.append(sc)

    current_calc = _calc_current(articles, logistics_costs, period_days)
    current_total = current_calc["total_monthly"]

    # Дельты относительно текущего и худшего
    worst_total = max(s["total_monthly"] for s in scenarios)
    for sc in scenarios:
        sc["delta_vs_current"] = _round_rub(sc["total_monthly"] - current_total)
        sc["delta_vs_worst"] = _round_rub(sc["total_monthly"] - worst_total)

    # Экономика перестановок
    monthly_factor = 30.0 / period_days
    turnover_monthly = turnover_rub * monthly_factor
    commission_monthly = turnover_monthly * (RELOCATION_COMMISSION_PCT / 100.0)

    # Максимум экономии: текущий - сценарий 80%
    sc_80 = next((s for s in scenarios if s["level_pct"] == 80), None)
    max_savings = current_total - sc_80["total_monthly"] if sc_80 else 0.0
    net_benefit = max_savings - commission_monthly

    return {
        "period_days": period_days,
        "current_il": current_il,
        "current_loc_pct": current_loc_pct,
        "current_scenario": {
            "label": "Сейчас",
            **current_calc,
            "level_pct": current_loc_pct,
        },
        "scenarios": scenarios,
        "top_articles": _calc_top_articles(articles, logistics_costs, period_days),
        "relocation_economics": {
            "turnover_monthly": _round_rub(turnover_monthly),
            "commission_monthly": _round_rub(commission_monthly),
            "breakeven_monthly": _round_rub(commission_monthly),
            "max_savings_monthly": _round_rub(max_savings),
            "net_benefit_monthly": _round_rub(net_benefit),
            "lock_in_days": RELOCATION_LOCK_IN_DAYS,
        },
    }


def _ktr_to_loc_pct(ktr_avg: float) -> float:
    """Обратное преобразование: взвешенный КТР → примерный % локализации.

    Использует линейную интерполяцию между границами COEFF_TABLE.
    """
    from services.wb_localization.irp_coefficients import COEFF_TABLE
    # COEFF_TABLE отсортирован по убыванию min_loc (95→0)
    for min_loc, max_loc, ktr, krp in COEFF_TABLE:
        if ktr_avg <= ktr:
            return (min_loc + max_loc) / 2
    return 0.0
```

- [ ] **Step 4: Запустить тесты — убедиться проходят**

```bash
pytest tests/wb_localization/test_scenario_engine.py -v
```

Ожидается: все 9 тестов PASS.

- [ ] **Step 5: Коммит**

```bash
git add services/wb_localization/calculators/scenario_engine.py tests/wb_localization/test_scenario_engine.py
git commit -m "feat(wb_localization): add scenario_engine calculator

Чистая функция analyze_scenarios() считает экономику кабинета
при разных уровнях локализации (30–90% по дефолту) на реальных
артикулах и ценах. Возвращает:
- Сценарии с логистикой/ИРП/итого/дельтами
- Топ-15 артикулов по потенциалу экономии
- Экономику перестановок (комиссия, точка окупаемости, чистая выгода)

Денежные расчёты через Decimal для избежания float-ошибок."
```

---

### Task 5: Расширение `history.py` таблицей `weekly_snapshots`

**Files:**
- Modify: `services/wb_localization/history.py`
- Test: `tests/wb_localization/test_history_weekly.py`

**Context:** Для точного forecast нужны понедельные снапшоты заказов по артикулам × регионам. Добавляем новую таблицу без изменения существующей `reports`. Миграция — автоматическая при инициализации History.

- [ ] **Step 1: Написать failing-тесты**

`tests/wb_localization/test_history_weekly.py`:
```python
"""Тесты weekly_snapshots в history.py."""
import tempfile
from datetime import date
from pathlib import Path

import pytest

from services.wb_localization.history import History


@pytest.fixture
def tmp_history():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_history.db"
        yield History(db_path=db_path)


def test_weekly_snapshots_table_created(tmp_history):
    """При инициализации History создаётся таблица weekly_snapshots."""
    import sqlite3
    conn = sqlite3.connect(tmp_history.db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='weekly_snapshots'"
    )
    assert cursor.fetchone() is not None


def test_save_weekly_snapshots(tmp_history):
    tmp_history.save_weekly_snapshots(
        cabinet="ooo",
        week_start=date(2026, 4, 13),
        snapshots=[
            {"article": "wendy/xl", "region": "Центральный", "local_orders": 50, "nonlocal_orders": 20},
            {"article": "wendy/xl", "region": "Южный", "local_orders": 30, "nonlocal_orders": 10},
        ],
    )
    data = tmp_history.get_weekly_snapshots(cabinet="ooo", weeks_back=1)
    assert len(data) == 2
    assert data[0]["local_orders"] == 50 or data[1]["local_orders"] == 50


def test_save_weekly_snapshots_idempotent(tmp_history):
    """Повторное сохранение той же недели обновляет, не дублирует."""
    tmp_history.save_weekly_snapshots(
        cabinet="ooo",
        week_start=date(2026, 4, 13),
        snapshots=[
            {"article": "wendy/xl", "region": "Центральный", "local_orders": 50, "nonlocal_orders": 20},
        ],
    )
    tmp_history.save_weekly_snapshots(
        cabinet="ooo",
        week_start=date(2026, 4, 13),
        snapshots=[
            {"article": "wendy/xl", "region": "Центральный", "local_orders": 70, "nonlocal_orders": 15},
        ],
    )
    data = tmp_history.get_weekly_snapshots(cabinet="ooo", weeks_back=1)
    assert len(data) == 1
    assert data[0]["local_orders"] == 70  # обновилось


def test_get_weekly_snapshots_by_cabinet(tmp_history):
    """Фильтрация по кабинету."""
    tmp_history.save_weekly_snapshots(
        cabinet="ooo",
        week_start=date(2026, 4, 13),
        snapshots=[{"article": "wendy/xl", "region": "Центральный", "local_orders": 50, "nonlocal_orders": 20}],
    )
    tmp_history.save_weekly_snapshots(
        cabinet="ip",
        week_start=date(2026, 4, 13),
        snapshots=[{"article": "sunny/m", "region": "Южный", "local_orders": 10, "nonlocal_orders": 5}],
    )
    ooo_data = tmp_history.get_weekly_snapshots(cabinet="ooo", weeks_back=1)
    ip_data = tmp_history.get_weekly_snapshots(cabinet="ip", weeks_back=1)
    assert len(ooo_data) == 1
    assert len(ip_data) == 1
    assert ooo_data[0]["article"] == "wendy/xl"
    assert ip_data[0]["article"] == "sunny/m"


def test_weeks_back_limit(tmp_history):
    """get_weekly_snapshots возвращает только последние N недель."""
    for week_offset in range(15):
        tmp_history.save_weekly_snapshots(
            cabinet="ooo",
            week_start=date(2026, 1, 6) if week_offset == 0 else date(2026, 1, 6 + week_offset * 7),
            snapshots=[{"article": "wendy/xl", "region": "Центральный", "local_orders": 10, "nonlocal_orders": 5}],
        )
    data = tmp_history.get_weekly_snapshots(cabinet="ooo", weeks_back=13)
    assert len(data) == 13
```

- [ ] **Step 2: Запустить тесты — убедиться падают**

```bash
pytest tests/wb_localization/test_history_weekly.py -v
```

Ожидается: FAIL — методы `save_weekly_snapshots`, `get_weekly_snapshots` не существуют.

- [ ] **Step 3: Расширить `history.py`**

Добавить в `services/wb_localization/history.py`:

1. В методе `_init_db()` (или аналогичном) — создание новой таблицы:

```python
cursor.execute("""
CREATE TABLE IF NOT EXISTS weekly_snapshots (
    cabinet TEXT NOT NULL,
    week_start DATE NOT NULL,
    article TEXT NOT NULL,
    region TEXT NOT NULL,
    local_orders INTEGER NOT NULL DEFAULT 0,
    nonlocal_orders INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (cabinet, week_start, article, region)
);
""")
cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_weekly_snapshots_cabinet_week
ON weekly_snapshots (cabinet, week_start DESC);
""")
```

2. Добавить методы класса `History`:

```python
def save_weekly_snapshots(
    self,
    cabinet: str,
    week_start: date,
    snapshots: list[dict[str, Any]],
) -> None:
    """Сохраняет понедельные снапшоты локализации.

    Idempotent: UPSERT по (cabinet, week_start, article, region).

    Args:
        cabinet: Идентификатор кабинета.
        week_start: Начало ISO-недели (понедельник).
        snapshots: Список с полями article, region, local_orders, nonlocal_orders.
    """
    conn = self._get_connection()
    try:
        for snap in snapshots:
            conn.execute("""
                INSERT INTO weekly_snapshots
                    (cabinet, week_start, article, region, local_orders, nonlocal_orders, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(cabinet, week_start, article, region)
                DO UPDATE SET
                    local_orders = excluded.local_orders,
                    nonlocal_orders = excluded.nonlocal_orders,
                    updated_at = CURRENT_TIMESTAMP;
            """, (
                cabinet,
                week_start.isoformat(),
                snap["article"],
                snap["region"],
                snap["local_orders"],
                snap["nonlocal_orders"],
            ))
        conn.commit()
    finally:
        conn.close()


def get_weekly_snapshots(
    self,
    cabinet: str,
    weeks_back: int = 13,
) -> list[dict[str, Any]]:
    """Возвращает снапшоты за последние weeks_back недель.

    Args:
        cabinet: Идентификатор кабинета.
        weeks_back: Сколько последних ISO-недель вернуть.

    Returns:
        Список словарей [{cabinet, week_start, article, region, local_orders, nonlocal_orders}].
        Отсортирован по week_start DESC.
    """
    conn = self._get_connection()
    try:
        cursor = conn.execute("""
            SELECT cabinet, week_start, article, region, local_orders, nonlocal_orders
            FROM weekly_snapshots
            WHERE cabinet = ?
              AND week_start IN (
                SELECT DISTINCT week_start FROM weekly_snapshots
                WHERE cabinet = ?
                ORDER BY week_start DESC
                LIMIT ?
              )
            ORDER BY week_start DESC, article, region;
        """, (cabinet, cabinet, weeks_back))
        return [
            {
                "cabinet": row[0],
                "week_start": row[1],
                "article": row[2],
                "region": row[3],
                "local_orders": row[4],
                "nonlocal_orders": row[5],
            }
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()
```

- [ ] **Step 4: Запустить тесты — убедиться проходят**

```bash
pytest tests/wb_localization/test_history_weekly.py -v
```

Ожидается: все 5 тестов PASS.

- [ ] **Step 5: Проверить что старые тесты не сломались**

```bash
pytest tests/wb_localization/test_history_irp.py -v
```

Ожидается: все проходят.

- [ ] **Step 6: Коммит**

```bash
git add services/wb_localization/history.py tests/wb_localization/test_history_weekly.py
git commit -m "feat(wb_localization): add weekly_snapshots table to history

Новая таблица weekly_snapshots для хранения понедельных данных
локализации per-article × region. Нужна для точного forecast'а
индекса локализации на 13 недель вперёд.

- Методы: save_weekly_snapshots() (idempotent UPSERT), get_weekly_snapshots()
- Индекс по (cabinet, week_start DESC)
- Backward-compat: старая таблица reports не затрагивается"
```

---

### Task 6: Калькулятор `relocation_forecaster.py`

**Files:**
- Create: `services/wb_localization/calculators/relocation_forecaster.py`
- Test: `tests/wb_localization/test_relocation_forecaster.py`

**Context:** Самый сложный калькулятор. Строит понедельный прогноз: "если начнём перестановки сегодня с лимитом X%, как будет меняться ИЛ кабинета на 13 недель вперёд". Учитывает инерцию 13-недельного окна по формуле `loc(t) = ((13-t)×old + t×new)/13`.

- [ ] **Step 1: Написать failing-тесты**

`tests/wb_localization/test_relocation_forecaster.py`:
```python
"""Тесты relocation_forecaster."""
import pytest
from services.wb_localization.calculators.relocation_forecaster import (
    simulate_roadmap,
    schedule_movements_by_week,
)


@pytest.fixture
def sample_articles():
    return [
        {
            "article": "wendy/xl",
            "loc_pct": 40.0,
            "ktr": 1.30,
            "krp_pct": 2.10,
            "wb_total": 100,
            "price": 1000.0,
            "stock_total": 500,
        },
        {
            "article": "sunny/m",
            "loc_pct": 80.0,
            "ktr": 0.80,
            "krp_pct": 0.00,
            "wb_total": 50,
            "price": 2000.0,
            "stock_total": 200,
        },
    ]


@pytest.fixture
def sample_movements():
    return [
        {
            "article": "wendy/xl",
            "qty": 120,
            "from_warehouse": "Коледино",
            "to_warehouse": "Екатеринбург",
            "impact_rub": 5000.0,
        },
    ]


@pytest.fixture
def sample_logistics_costs():
    return {"wendy/xl": 5200.0, "sunny/m": 3200.0}


@pytest.fixture
def redistribution_limits():
    return {"Коледино": 100_000, "Екатеринбург": 100_000}


def test_simulate_returns_14_weeks(sample_articles, sample_movements, sample_logistics_costs, redistribution_limits):
    """Прогноз на неделю 0 (старт) + 13 недель = 14 строк."""
    result = simulate_roadmap(
        articles=sample_articles,
        movements=sample_movements,
        logistics_costs=sample_logistics_costs,
        weekly_orders_history=[],
        redistribution_limits=redistribution_limits,
        realistic_limit_pct=0.3,
        period_days=30,
    )
    assert len(result["roadmap"]) == 14


def test_week_0_is_current_state(sample_articles, sample_movements, sample_logistics_costs, redistribution_limits):
    """Неделя 0 = текущее состояние (0 перемещено, 0 экономии)."""
    result = simulate_roadmap(
        articles=sample_articles,
        movements=sample_movements,
        logistics_costs=sample_logistics_costs,
        weekly_orders_history=[],
        redistribution_limits=redistribution_limits,
        realistic_limit_pct=0.3,
        period_days=30,
    )
    week_0 = result["roadmap"][0]
    assert week_0["week"] == 0
    assert week_0["moved_units_cumulative"] == 0
    assert week_0["savings_vs_current"] == 0.0


def test_week_13_shows_full_effect(sample_articles, sample_movements, sample_logistics_costs, redistribution_limits):
    """Неделя 13 = полное выветривание старых данных, максимальный эффект."""
    result = simulate_roadmap(
        articles=sample_articles,
        movements=sample_movements,
        logistics_costs=sample_logistics_costs,
        weekly_orders_history=[],
        redistribution_limits=redistribution_limits,
        realistic_limit_pct=1.0,  # все слоты доступны
        period_days=30,
    )
    week_13 = result["roadmap"][-1]
    # ИЛ должен вырасти (ИЛ — это % локализации, больше = лучше)
    assert week_13["il_forecast"] > result["roadmap"][0]["il_forecast"]


def test_blending_formula(sample_articles, sample_movements, sample_logistics_costs, redistribution_limits):
    """Проверка формулы blending: неделя 7 ≈ среднее между старым и новым."""
    result = simulate_roadmap(
        articles=sample_articles,
        movements=sample_movements,
        logistics_costs=sample_logistics_costs,
        weekly_orders_history=[],
        redistribution_limits=redistribution_limits,
        realistic_limit_pct=1.0,
        period_days=30,
    )
    week_0_il = result["roadmap"][0]["il_forecast"]
    week_7_il = result["roadmap"][7]["il_forecast"]
    week_13_il = result["roadmap"][-1]["il_forecast"]
    # Неделя 7 должна быть между 0 и 13 (монотонный рост)
    assert week_0_il < week_7_il < week_13_il


def test_detects_milestone_60pct(sample_articles, sample_movements, sample_logistics_costs, redistribution_limits):
    """Определение недели пересечения порога 60% (когда КРП→0)."""
    result = simulate_roadmap(
        articles=sample_articles,
        movements=sample_movements,
        logistics_costs=sample_logistics_costs,
        weekly_orders_history=[],
        redistribution_limits=redistribution_limits,
        realistic_limit_pct=1.0,
        period_days=30,
    )
    milestones = result["milestones"]
    assert "week_60pct" in milestones
    # При значительных перестановках с 40% артикулов, порог пересекается
    # (точное значение зависит от долей и весов, оставляем as is)


def test_realistic_limit_pct_affects_schedule(sample_articles, sample_movements, sample_logistics_costs, redistribution_limits):
    """Меньший % лимитов = движение растягивается на больше недель."""
    result_fast = simulate_roadmap(
        articles=sample_articles,
        movements=sample_movements,
        logistics_costs=sample_logistics_costs,
        weekly_orders_history=[],
        redistribution_limits=redistribution_limits,
        realistic_limit_pct=1.0,
        period_days=30,
    )
    result_slow = simulate_roadmap(
        articles=sample_articles,
        movements=sample_movements,
        logistics_costs=sample_logistics_costs,
        weekly_orders_history=[],
        redistribution_limits=redistribution_limits,
        realistic_limit_pct=0.1,
        period_days=30,
    )
    # На неделе 1 быстрый сценарий перенёс больше юнитов
    assert result_fast["roadmap"][1]["moved_units_cumulative"] >= result_slow["roadmap"][1]["moved_units_cumulative"]


def test_schedule_movements_distributes_by_priority():
    """schedule_movements_by_week распределяет по приоритету импакта."""
    movements = [
        {"article": "A", "qty": 1000, "to_warehouse": "Коледино", "impact_rub": 100},  # мало импакта
        {"article": "B", "qty": 1000, "to_warehouse": "Коледино", "impact_rub": 10000},  # много
    ]
    limits = {"Коледино": 500}  # лимит 500/день = 3500/неделю
    schedule = schedule_movements_by_week(movements, limits, realistic_limit_pct=1.0)
    # Артикул B должен идти первым (больший импакт)
    week_0_articles = [m["article"] for m in schedule.get(0, [])]
    assert "B" in week_0_articles
```

- [ ] **Step 2: Запустить тесты — убедиться падают**

```bash
pytest tests/wb_localization/test_relocation_forecaster.py -v
```

Ожидается: FAIL — модуль не существует.

- [ ] **Step 3: Реализовать `relocation_forecaster.py`**

```python
# services/wb_localization/calculators/relocation_forecaster.py
"""Симуляция понедельного прогноза улучшения ИЛ после перестановок.

Ключевая идея: индекс локализации считается за скользящие 13 недель,
поэтому эффект перестановок виден не сразу. На неделе t после старта
эффективная локализация артикула = ((13-t)×loc_before + t×loc_after) / 13.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from services.wb_localization.irp_coefficients import get_ktr_krp


DEFAULT_TARGET_LOCALIZATION = 85.0  # % локализации артикула после переноса
THRESHOLD_60 = 60.0
THRESHOLD_80 = 80.0


def _round_rub(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def schedule_movements_by_week(
    movements: list[dict[str, Any]],
    redistribution_limits: dict[str, int],
    realistic_limit_pct: float = 0.3,
) -> dict[int, list[dict[str, Any]]]:
    """Распределяет перемещения по неделям с учётом capacity складов.

    Жадный алгоритм: сортирует движения по impact_rub DESC, раскладывает
    по неделям пока не исчерпается capacity.

    Args:
        movements: Список движений с полями article, qty, to_warehouse, impact_rub.
        redistribution_limits: {warehouse: units_per_day}.
        realistic_limit_pct: Доля реально доступных слотов (0.0–1.0).

    Returns:
        {week_num: [movement_dict, ...]}
    """
    weekly_capacity = {
        wh: int(limit * 7 * realistic_limit_pct)
        for wh, limit in redistribution_limits.items()
    }

    sorted_movements = sorted(
        movements,
        key=lambda m: m.get("impact_rub", 0),
        reverse=True,
    )

    schedule: dict[int, list[dict[str, Any]]] = defaultdict(list)
    remaining_capacity = {wh: {w: cap for w in range(14)} for wh, cap in weekly_capacity.items()}

    for movement in sorted_movements:
        wh = movement.get("to_warehouse")
        qty = movement.get("qty", 0)
        remaining = qty

        for week in range(14):
            if remaining <= 0:
                break
            if wh not in remaining_capacity:
                # Склад без лимита — считаем его неограниченным в рамках реалистичной оценки
                schedule[week].append({**movement, "qty": remaining})
                remaining = 0
                break
            cap = remaining_capacity[wh].get(week, 0)
            if cap <= 0:
                continue
            take = min(remaining, cap)
            schedule[week].append({**movement, "qty": take})
            remaining_capacity[wh][week] = cap - take
            remaining -= take

    return dict(schedule)


def _moved_to_date(
    schedule: dict[int, list[dict[str, Any]]],
    article: str,
    up_to_week: int,
) -> int:
    total = 0
    for week in range(up_to_week + 1):
        for mv in schedule.get(week, []):
            if mv.get("article") == article:
                total += mv.get("qty", 0)
    return total


def _blended_loc(
    week_num: int,
    loc_before: float,
    loc_after: float,
    move_fraction: float,
) -> float:
    """Формула инерции 13-недельного окна.

    На неделе t:
      effective_new = loc_before × (1 - move_fraction) + loc_after × move_fraction
      blended = ((13 - t) × loc_before + t × effective_new) / 13
    """
    if week_num == 0:
        return loc_before
    effective_new = loc_before * (1 - move_fraction) + loc_after * move_fraction
    old_weeks = 13 - week_num
    new_weeks = week_num
    return (old_weeks * loc_before + new_weeks * effective_new) / 13


def _detect_first_crossing(
    roadmap: list[dict[str, Any]],
    threshold: float,
) -> int | None:
    """Находит номер первой недели, где il_forecast >= threshold."""
    for week in roadmap:
        if week["il_forecast"] >= threshold:
            return week["week"]
    return None


def simulate_roadmap(
    articles: list[dict[str, Any]],
    movements: list[dict[str, Any]],
    logistics_costs: dict[str, float],
    weekly_orders_history: list[dict[str, Any]],
    redistribution_limits: dict[str, int],
    realistic_limit_pct: float = 0.3,
    target_localization: float = DEFAULT_TARGET_LOCALIZATION,
    period_days: int = 30,
    start_date: date | None = None,
) -> dict[str, Any]:
    """Понедельный прогноз ИЛ на 13 недель вперёд.

    Args:
        articles: Артикулы из analyze_il_irp (article, loc_pct, ktr, krp_pct, wb_total, price, stock_total).
        movements: Рекомендованные перестановки из generate_movements_v3.
        logistics_costs: {article_lower: ₽ за period_days}.
        weekly_orders_history: Исторические снапшоты (пока не используется, fallback модель).
        redistribution_limits: Дневные лимиты складов WB.
        realistic_limit_pct: Доля реально доступных слотов.
        target_localization: Локализация артикула после полного переноса (%).
        period_days: Текущий период в днях для перевода в ₽/мес.
        start_date: Дата старта прогноза (для календарных недель).

    Returns:
        {
            "params": {...},
            "roadmap": [14 записей],
            "schedule": {week_num: [movements]},
            "milestones": {"week_60pct": int|None, "week_80pct": int|None},
        }
    """
    if start_date is None:
        start_date = date.today()
    monthly_factor = 30.0 / period_days

    schedule = schedule_movements_by_week(movements, redistribution_limits, realistic_limit_pct)

    # Текущая база расходов по артикулам
    article_map = {a["article"].lower(): a for a in articles}
    base_costs = {}
    for art_lower, art in article_map.items():
        actual = logistics_costs.get(art_lower)
        if actual is not None and art["ktr"] > 0:
            base_costs[art_lower] = actual / art["ktr"]

    # Базовая (текущая) общая цифра для дельт
    current_logistics_monthly = sum(
        logistics_costs.get(a["article"].lower(), 0.0) * monthly_factor
        for a in articles
    )
    current_irp_monthly = sum(
        a.get("price", 0) * (a.get("krp_pct", 0) / 100) * (a.get("wb_total", 0) / period_days * 30)
        for a in articles
    )
    current_total_monthly = current_logistics_monthly + current_irp_monthly

    total_plan_qty = sum(m.get("qty", 0) for m in movements)

    roadmap = []
    for week_num in range(14):
        # Эффективная локализация каждого артикула на эту неделю
        week_logistics = 0.0
        week_irp = 0.0
        weighted_ktr_num = 0.0
        weighted_orders_den = 0

        for art in articles:
            art_lower = art["article"].lower()
            stock = max(art.get("stock_total", 1), 1)
            moved = _moved_to_date(schedule, art["article"], week_num)
            move_fraction = min(moved / stock, 1.0)

            loc_before = art.get("loc_pct", 0.0)
            loc_after = target_localization
            effective_loc = _blended_loc(week_num, loc_before, loc_after, move_fraction)

            new_ktr, new_krp = get_ktr_krp(effective_loc)

            orders = art.get("wb_total", 0)
            weighted_ktr_num += new_ktr * orders
            weighted_orders_den += orders

            base = base_costs.get(art_lower, 0.0)
            week_logistics += base * new_ktr * monthly_factor

            price = art.get("price", 0.0)
            if price > 0 and orders > 0:
                monthly_orders = orders / period_days * 30.0
                week_irp += price * (new_krp / 100.0) * monthly_orders

        # Взвешенный КТР в % локализации
        if weighted_orders_den > 0:
            avg_ktr = weighted_ktr_num / weighted_orders_den
            # Обратное преобразование КТР → примерный % локализации
            il_forecast_pct = _ktr_to_loc_pct(avg_ktr)
        else:
            avg_ktr = 1.0
            il_forecast_pct = 0.0

        cumulative_moved = sum(
            mv.get("qty", 0)
            for w in range(week_num + 1)
            for mv in schedule.get(w, [])
        )
        plan_pct = (cumulative_moved / total_plan_qty * 100) if total_plan_qty > 0 else 0.0

        total_new = week_logistics + week_irp
        savings = current_total_monthly - total_new

        roadmap.append({
            "week": week_num,
            "date": (start_date + timedelta(weeks=week_num)).isoformat(),
            "moved_units_cumulative": cumulative_moved,
            "plan_pct": round(plan_pct, 1),
            "il_forecast": round(il_forecast_pct, 1),
            "ktr_weighted": round(avg_ktr, 3),
            "logistics_monthly": _round_rub(week_logistics),
            "irp_monthly": _round_rub(week_irp),
            "total_monthly": _round_rub(total_new),
            "savings_vs_current": _round_rub(savings),
        })

    # Normalize week 0 savings to 0
    if roadmap:
        roadmap[0]["savings_vs_current"] = 0.0

    milestones = {
        "week_60pct": _detect_first_crossing(roadmap, THRESHOLD_60),
        "week_80pct": _detect_first_crossing(roadmap, THRESHOLD_80),
    }

    return {
        "params": {
            "realistic_limit_pct": realistic_limit_pct,
            "target_localization": target_localization,
            "period_days": period_days,
            "total_plan_qty": total_plan_qty,
            "articles_with_movements": len({m["article"] for m in movements}),
        },
        "roadmap": roadmap,
        "schedule": {str(k): v for k, v in schedule.items()},
        "milestones": milestones,
    }


def _ktr_to_loc_pct(ktr_avg: float) -> float:
    """Обратное преобразование взвешенного КТР → % локализации."""
    from services.wb_localization.irp_coefficients import COEFF_TABLE
    # COEFF_TABLE отсортирована по убыванию min_loc
    # Ищем ближайшую границу
    for min_loc, max_loc, ktr, krp in COEFF_TABLE:
        if ktr_avg <= ktr + 0.001:
            return (min_loc + max_loc) / 2
    return 0.0
```

- [ ] **Step 4: Запустить тесты — убедиться проходят**

```bash
pytest tests/wb_localization/test_relocation_forecaster.py -v
```

Ожидается: все 7 тестов PASS.

- [ ] **Step 5: Коммит**

```bash
git add services/wb_localization/calculators/relocation_forecaster.py tests/wb_localization/test_relocation_forecaster.py
git commit -m "feat(wb_localization): add relocation_forecaster calculator

Понедельный прогноз улучшения ИЛ на 13 недель вперёд с учётом:
- Инерции скользящего окна: loc(t) = ((13-t)×old + t×new)/13
- Реалистичных лимитов складов (параметр realistic_limit_pct, дефолт 0.3)
- Приоритизации перестановок по impact_rub

Возвращает roadmap на 14 строк (неделя 0 + 13 прогноза), schedule
движений по неделям, и milestones (неделя пересечения 60% и 80%).

Денежные расчёты через Decimal."
```

---

## Волна 3 — Листы

Три независимые задачи. Можно выполнять параллельно после Волны 2.

### Task 7: Sheet writer `reference_sheet.py`

**Files:**
- Create: `services/wb_localization/sheets_export/reference_sheet.py`
- Modify: `services/wb_localization/sheets_export/__init__.py` (регистрация)
- Test: `tests/wb_localization/test_reference_sheet.py`

**Context:** Пишет расширенный лист «Справочник» с 8 блоками. Использует `build_reference_content()` для данных и `formatters.py` для стилей.

- [ ] **Step 1: Написать failing-тест — структура и mock gspread**

`tests/wb_localization/test_reference_sheet.py`:
```python
"""Тесты reference_sheet writer."""
from unittest.mock import MagicMock
import pytest
from services.wb_localization.sheets_export.reference_sheet import (
    write_reference_sheet,
    REFERENCE_SHEET_NAME,
)


def test_write_reference_sheet_calls_clear_and_write():
    """Основная проверка: листу делается clear() + update() + форматирование."""
    mock_spreadsheet = MagicMock()
    mock_worksheet = MagicMock()
    mock_worksheet.id = 42
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    from services.wb_localization.calculators.reference_builder import build_reference_content
    content = build_reference_content()

    write_reference_sheet(mock_spreadsheet, content)

    # Проверка что лист очищен
    mock_worksheet.clear.assert_called_once()
    # Проверка что update вызывался (может быть несколько раз)
    assert mock_worksheet.update.call_count >= 1
    # Проверка что batch_update вызывался для форматирования
    assert mock_spreadsheet.batch_update.call_count >= 1


def test_reference_sheet_name_constant():
    assert REFERENCE_SHEET_NAME == "Справочник"


def test_write_reference_creates_sheet_if_missing():
    """Если листа нет — создать."""
    from gspread.exceptions import WorksheetNotFound
    mock_spreadsheet = MagicMock()
    mock_spreadsheet.worksheet.side_effect = WorksheetNotFound()
    new_worksheet = MagicMock()
    new_worksheet.id = 99
    mock_spreadsheet.add_worksheet.return_value = new_worksheet

    from services.wb_localization.calculators.reference_builder import build_reference_content
    content = build_reference_content()

    write_reference_sheet(mock_spreadsheet, content)

    mock_spreadsheet.add_worksheet.assert_called_once()
```

- [ ] **Step 2: Запустить тест — падает**

```bash
pytest tests/wb_localization/test_reference_sheet.py -v
```

Ожидается: FAIL — модуль не существует.

- [ ] **Step 3: Реализовать `reference_sheet.py`**

```python
# services/wb_localization/sheets_export/reference_sheet.py
"""Запись листа «Справочник» (расширенная документация WB)."""
from __future__ import annotations
from typing import Any

from gspread import Spreadsheet
from gspread.exceptions import WorksheetNotFound

from .formatters import (
    _header_fmt,
    _meta_fmt,
    _col_widths,
    _row_height,
    _freeze,
    _borders,
    _banding,
    _clear_banding,
)

REFERENCE_SHEET_NAME = "Справочник"


def _get_or_create_worksheet(spreadsheet: Spreadsheet, name: str, rows: int = 200, cols: int = 10):
    try:
        return spreadsheet.worksheet(name)
    except WorksheetNotFound:
        return spreadsheet.add_worksheet(title=name, rows=rows, cols=cols)


def _color_to_rgb(color: str) -> dict:
    colors = {
        "green": {"red": 0.85, "green": 0.92, "blue": 0.83},
        "yellow": {"red": 0.98, "green": 0.90, "blue": 0.60},
        "red": {"red": 0.96, "green": 0.80, "blue": 0.80},
        "blue_header": {"red": 0.20, "green": 0.25, "blue": 0.45},
    }
    return colors.get(color, {"red": 1.0, "green": 1.0, "blue": 1.0})


def write_reference_sheet(spreadsheet: Spreadsheet, content: dict[str, Any]) -> None:
    """Пишет расширенный лист «Справочник» со всеми 8 блоками.

    Args:
        spreadsheet: gspread Spreadsheet объект.
        content: Результат build_reference_content().
    """
    worksheet = _get_or_create_worksheet(spreadsheet, REFERENCE_SHEET_NAME)
    worksheet.clear()
    _clear_banding(spreadsheet, worksheet.id)

    rows: list[list[Any]] = []
    format_requests: list[dict] = []

    # Блок 1: обложка
    rows.append([content["cover"]["title"]])
    rows.append([content["cover"]["subtitle"]])
    rows.append([])
    rows.append(["Оглавление:"])
    rows.append(["→ 1. Формула логистики (стр. 6)"])
    rows.append(["→ 2. Индекс локализации (стр. 17)"])
    rows.append(["→ 3. Индекс распределения продаж (стр. 47)"])
    rows.append(["→ 4. Исключения (стр. 77)"])
    rows.append(["→ 5. Перестановки (стр. 90)"])
    rows.append(["→ 6. Скользящее окно (стр. 132)"])
    rows.append([])

    # Блок 2: формула
    rows.append(["1. ОСНОВНАЯ ФОРМУЛА ЛОГИСТИКИ"])
    rows.append([])
    rows.append(["Логистика = (База × Коэф.склада × ИЛ) + (Цена × ИРП%)"])
    rows.append([])
    rows.append(["Компонент", "Описание"])
    for c in content["formula_block"]["components"]:
        rows.append([c["name"], c["desc"]])
    rows.append([])
    ex = content["formula_block"]["example"]
    rows.append([f"💡 Пример: цена {ex['price']}₽, объём {ex['volume_liters']}л, лок. {ex['article_loc_pct']}%"])
    rows.append([f"   Объёмная часть: {ex['volume_part']}₽"])
    rows.append([f"   Ценовая часть: {ex['price_part']}₽"])
    rows.append([f"   ИТОГО: {ex['total']}₽"])
    rows.append([])

    # Блок 3: ИЛ
    rows.append(["2. ИНДЕКС ЛОКАЛИЗАЦИИ (ИЛ)"])
    rows.append([])
    rows.append([content["il_section"]["definition"]])
    rows.append([content["il_section"]["formula"]])
    rows.append([content["il_section"]["period_note"]])
    rows.append([])
    rows.append(["Мин. %", "Макс. %", "КТР", "Описание"])
    ktr_start_row = len(rows)
    for row in content["il_section"]["table"]:
        rows.append([row["min_loc"], row["max_loc"], row["ktr"], row["description"]])
    ktr_end_row = len(rows) - 1
    rows.append([])

    # Блок 4: ИРП
    rows.append(["3. ИНДЕКС РАСПРЕДЕЛЕНИЯ ПРОДАЖ (ИРП)"])
    rows.append([])
    rows.append([content["irp_section"]["formula"]])
    rows.append([f"⚠️ КЛЮЧЕВОЙ ПОРОГ: {content['irp_section']['critical_threshold']['value']}%"])
    rows.append([content["irp_section"]["critical_threshold"]["note"]])
    rows.append([])
    rows.append(["Мин. %", "Макс. %", "КРП %", "Описание"])
    krp_start_row = len(rows)
    for row in content["irp_section"]["table"]:
        rows.append([row["min_loc"], row["max_loc"], row["krp_pct"], row["description"]])
    krp_end_row = len(rows) - 1
    rows.append([])

    # Блок 5: исключения
    rows.append(["4. ИСКЛЮЧЕНИЯ"])
    rows.append([])
    rows.append(["Категории-исключения:"])
    for cat in content["exceptions"]["categories"]:
        rows.append([f"  • {cat}"])
    rows.append([])
    rows.append(["⚠️ Правило 35%:"])
    rows.append([content["exceptions"]["rule_35"]])
    rows.append([])

    # Блок 6: перестановки
    rows.append(["5. ПЕРЕСТАНОВКИ (ПЕРЕРАСПРЕДЕЛЕНИЕ)"])
    rows.append([])
    rows.append([content["relocation_section"]["description"]])
    rows.append([])
    rows.append([f"Комиссия: +{content['relocation_section']['commission_pct']}% на все продажи"])
    rows.append([f"Lock-in: {content['relocation_section']['lock_in_days']} дней"])
    rows.append([])
    rows.append(["Склады и дневные лимиты:"])
    rows.append(["Склад", "Лимит шт/день"])
    for wh in content["relocation_section"]["warehouses"][:25]:  # топ-25
        rows.append([wh["name"], wh["limit_per_day"]])
    rows.append([])
    econ = content["relocation_section"]["economics_example"]
    rows.append(["💡 Экономика перестановок:"])
    rows.append([f"  Оборот 5 000 000 ₽/мес → комиссия {econ['commission_monthly']:,.0f} ₽/мес"])
    rows.append([f"  Окупается если: {econ['breakeven']}"])
    rows.append([])

    # Блок 7: скользящее окно
    rows.append(["6. СКОЛЬЗЯЩЕЕ ОКНО 13 НЕДЕЛЬ"])
    rows.append([])
    rows.append([content["sliding_window"]["explanation"]])
    rows.append([content["sliding_window"]["formula"]])
    rows.append([])
    rows.append(["От локализации (%)", "До порога (%)", "Недель"])
    for row in content["sliding_window"]["weeks_to_threshold"]:
        rows.append([row["from_loc"], row["to_loc"], row["weeks"]])
    rows.append([])
    rows.append([f"🚨 {content['sliding_window']['call_to_action']}"])
    rows.append([])

    # Блок 8: disclaimer
    rows.append(["НАШ РАСЧЁТ vs WB"])
    rows.append([content["disclaimer"]["note"]])

    # Запись данных
    max_cols = max(len(r) for r in rows) if rows else 4
    normalized = [r + [""] * (max_cols - len(r)) for r in rows]
    worksheet.update("A1", normalized)

    # Форматирование: заголовки блоков (ищем строки с заглавными буквами)
    block_title_rows = [i for i, r in enumerate(rows) if r and isinstance(r[0], str) and r[0].isupper() and len(r[0]) > 5]

    format_requests.extend(_col_widths(worksheet.id, [
        (0, 180), (1, 180), (2, 120), (3, 280),
    ]))

    for row_idx in block_title_rows:
        format_requests.extend(_row_height(worksheet.id, row_idx, row_idx + 1, 32))
        format_requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": worksheet.id,
                    "startRowIndex": row_idx,
                    "endRowIndex": row_idx + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": max_cols,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": _color_to_rgb("blue_header"),
                        "textFormat": {
                            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                            "bold": True,
                            "fontSize": 13,
                        },
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        })

    # Раскрашиваем строки КТР по цветам
    for i, row_data in enumerate(content["il_section"]["table"]):
        row_idx = ktr_start_row + i
        color = _color_to_rgb(row_data["color"])
        format_requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": worksheet.id,
                    "startRowIndex": row_idx,
                    "endRowIndex": row_idx + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 4,
                },
                "cell": {"userEnteredFormat": {"backgroundColor": color}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        })

    # Раскрашиваем строки КРП
    for i, row_data in enumerate(content["irp_section"]["table"]):
        row_idx = krp_start_row + i
        color = _color_to_rgb(row_data["color"])
        format_requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": worksheet.id,
                    "startRowIndex": row_idx,
                    "endRowIndex": row_idx + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 4,
                },
                "cell": {"userEnteredFormat": {"backgroundColor": color}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        })

    format_requests.extend(_freeze(worksheet.id, 1, 0))

    if format_requests:
        spreadsheet.batch_update({"requests": format_requests})
```

- [ ] **Step 4: Запустить тесты — проходят**

```bash
pytest tests/wb_localization/test_reference_sheet.py -v
```

Ожидается: все 3 теста PASS.

- [ ] **Step 5: Зарегистрировать в `__init__.py`**

Добавить в `sheets_export/__init__.py`:
```python
from .reference_sheet import write_reference_sheet, REFERENCE_SHEET_NAME
```

В функции `export_to_sheets()` — вызвать `write_reference_sheet(spreadsheet, payload["reference"])` если `payload["reference"]` присутствует. Старый inline `_write_reference_sheet` удалить.

- [ ] **Step 6: Коммит**

```bash
git add services/wb_localization/sheets_export/reference_sheet.py services/wb_localization/sheets_export/__init__.py tests/wb_localization/test_reference_sheet.py
git commit -m "feat(wb_localization): add reference_sheet writer

Расширенный лист «Справочник» с 8 тематическими блоками:
обложка, формула логистики, ИЛ, ИРП, исключения, перестановки,
скользящее окно, disclaimer. Раскраска таблиц КТР/КРП по цветам
(зелёный/жёлтый/красный). Заголовки блоков на тёмно-синем фоне."
```

---

### Task 8: Sheet writer `scenario_sheet.py`

**Files:**
- Create: `services/wb_localization/sheets_export/scenario_sheet.py`
- Modify: `services/wb_localization/sheets_export/__init__.py` (регистрация)
- Modify: `services/wb_localization/sheets_export/formatters.py` (добавить SHEET_COLUMN_DOCS)
- Test: `tests/wb_localization/test_scenario_sheet.py`

**Context:** Лист «Экономика сценариев» — заменяет старый 3-сценарный лист. Сводная таблица (7 уровней + anchor), KPI-плитки, топ-15 артикулов, экономика перестановок. У каждой колонки — строка-описание.

- [ ] **Step 1: Добавить словарь SHEET_COLUMN_DOCS в formatters.py**

В конец `sheets_export/formatters.py` добавить:

```python
SHEET_COLUMN_DOCS = {
    "scenarios": {
        "Сценарий": "Уровень локализации и оценка относительно текущего",
        "Целевая лок.%": "Локализация в этом сценарии (30, 40, ..., 90%)",
        "КТР": "Коэффициент логистики для этого уровня (из таблицы WB)",
        "КРП%": "Процент надбавки к цене (0% если ИЛ≥60%)",
        "Логистика ₽/мес": "Объёмная часть логистики при этом уровне ИЛ",
        "ИРП ₽/мес": "Ценовая надбавка: Σ(цена × КРП%) по артикулам",
        "Итого ₽/мес": "Сумма логистики и ИРП за месяц",
        "Δ vs Сейчас": "Разница с текущим состоянием (- = экономия, + = переплата)",
        "Δ vs Худший": "Разница с худшим сценарием (всегда <= 0)",
    },
    "top_articles": {
        "#": "Ранг по потенциалу экономии",
        "Артикул": "Артикул продавца (supplierArticle)",
        "Лок.% сейчас": "Текущая локализация артикула (локальные/всего заказов × 100)",
        "КТР": "Текущий коэффициент логистики артикула",
        "КРП%": "Текущая надбавка к цене в %",
        "Заказов/мес": "Среднемесячный объём заказов",
        "Логистика ₽/мес": "Текущая факт. логистика артикула в месяц",
        "ИРП ₽/мес": "Текущая надбавка артикула в месяц",
        "Вклад в ИЛ": "Вклад артикула во взвеш. ИЛ кабинета (п.п., < 0 = тянет вниз)",
        "Экономия при 80% ₽/мес": "Потенциал экономии если довести до 80% локализации",
        "Статус": "🟢 Отличная / 🟡 Нейтральная / 🟠 Слабая / 🔴 Критическая",
    },
    "roadmap": {
        "Неделя": "Номер недели с начала перестановок, 0 = старт",
        "Дата": "Календарная дата начала этой недели",
        "Перемещено шт (кумулятив)": "Сколько единиц суммарно перенесли к этой неделе",
        "% плана": "% выполнения плана перестановок (кумулятив / всего)",
        "ИЛ прогноз": "Расчётный % локализации с учётом 13-нед. скольз. окна",
        "КТР взвеш.": "Взвешенный КТР по всем артикулам кабинета",
        "Логистика ₽/мес": "Прогноз логистики + ИРП на эту неделю",
        "Экономия vs Сейчас": "Разница с неделей 0 (зелёный = экономим)",
        "Статус": "Вехи: 🎯 порог 60% (КРП→0), 🎯 цель 80% (КТР=0.80)",
    },
    "plan": {
        "#": "Приоритет (1 = самый важный по impact ₽)",
        "Приоритет": "P1 (лок<60%) / P2 (60-75%) / P3 (мониторинг)",
        "Артикул": "Артикул продавца",
        "Размер": "Размер SKU",
        "Лок.% текущая": "Текущая локализация артикула",
        "Откуда (ФО + склад)": "Исходный регион и склад-донор (с избытком)",
        "Куда (ФО + склад)": "Целевой регион и склад-получатель (с дефицитом)",
        "Кол-во шт": "Рекомендуемое количество для перемещения",
        "Импакт на ИЛ (п.п.)": "На сколько вырастет индекс кабинета после переноса",
        "Экономия ₽/мес": "Прогнозная экономия при успешном переносе",
        "Склад-лимит": "✅ хватает capacity / ⚠️ впритык / ❌ не хватает",
        "Неделя старта": "В какую неделю запланировано в schedule",
    },
}


def write_column_descriptions(
    rows: list[list[Any]],
    column_headers: list[str],
    category: str,
) -> list[list[Any]]:
    """Вставляет строку-описание под заголовком таблицы.

    Args:
        rows: Существующие строки.
        column_headers: Заголовки колонок.
        category: Ключ в SHEET_COLUMN_DOCS.

    Returns:
        rows с добавленной строкой описаний.
    """
    docs = SHEET_COLUMN_DOCS.get(category, {})
    desc_row = [docs.get(h, "") for h in column_headers]
    rows.append(desc_row)
    return rows
```

- [ ] **Step 2: Написать failing-тесты**

`tests/wb_localization/test_scenario_sheet.py`:
```python
"""Тесты scenario_sheet writer."""
from unittest.mock import MagicMock
from services.wb_localization.sheets_export.scenario_sheet import (
    write_scenario_sheet,
    scenario_sheet_name,
)


def test_scenario_sheet_name_includes_cabinet():
    assert scenario_sheet_name("ooo") == "Экономика сценариев ooo"


def test_write_scenario_sheet_writes_data():
    mock_spreadsheet = MagicMock()
    mock_worksheet = MagicMock()
    mock_worksheet.id = 42
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    payload = {
        "period_days": 30,
        "current_il": 1.05,
        "current_loc_pct": 55.0,
        "current_scenario": {
            "label": "Сейчас",
            "level_pct": 55.0,
            "logistics_monthly": 126000.0,
            "irp_monthly": 14500.0,
            "total_monthly": 140500.0,
        },
        "scenarios": [
            {
                "level_pct": 30, "ktr": 1.50, "krp_pct": 2.15,
                "logistics_monthly": 180000.0, "irp_monthly": 28500.0,
                "total_monthly": 208500.0, "delta_vs_current": 68000.0,
                "delta_vs_worst": 0.0, "color": "red",
            },
            {
                "level_pct": 80, "ktr": 0.80, "krp_pct": 0.00,
                "logistics_monthly": 96000.0, "irp_monthly": 0.0,
                "total_monthly": 96000.0, "delta_vs_current": -44500.0,
                "delta_vs_worst": -112500.0, "color": "green",
            },
        ],
        "top_articles": [
            {
                "article": "wendy/xl", "loc_pct": 38, "ktr": 1.40, "krp_pct": 2.10,
                "orders_monthly": 520, "logistics_fact_monthly": 32000,
                "irp_current_monthly": 10920, "contribution_to_il": -12.4,
                "savings_if_80_monthly": 21500, "status": "🔴 Критическая",
            },
        ],
        "relocation_economics": {
            "turnover_monthly": 5200000.0,
            "commission_monthly": 26000.0,
            "breakeven_monthly": 26000.0,
            "max_savings_monthly": 44500.0,
            "net_benefit_monthly": 18500.0,
            "lock_in_days": 90,
        },
    }

    write_scenario_sheet(mock_spreadsheet, "ooo", payload)

    mock_worksheet.clear.assert_called_once()
    assert mock_worksheet.update.call_count >= 1
    assert mock_spreadsheet.batch_update.call_count >= 1
```

- [ ] **Step 3: Запустить — падает**

```bash
pytest tests/wb_localization/test_scenario_sheet.py -v
```

- [ ] **Step 4: Реализовать `scenario_sheet.py`**

```python
# services/wb_localization/sheets_export/scenario_sheet.py
"""Запись листа «Экономика сценариев {cabinet}»."""
from __future__ import annotations
from typing import Any

from gspread import Spreadsheet
from gspread.exceptions import WorksheetNotFound

from .formatters import (
    _col_widths,
    _row_height,
    _freeze,
    _borders,
    _banding,
    _clear_banding,
    SHEET_COLUMN_DOCS,
)


def scenario_sheet_name(cabinet: str) -> str:
    return f"Экономика сценариев {cabinet}"


def _get_or_create_worksheet(spreadsheet: Spreadsheet, name: str, rows: int = 100, cols: int = 12):
    try:
        return spreadsheet.worksheet(name)
    except WorksheetNotFound:
        return spreadsheet.add_worksheet(title=name, rows=rows, cols=cols)


def _color_for_scenario(color: str) -> dict:
    return {
        "red": {"red": 0.96, "green": 0.80, "blue": 0.80},
        "yellow": {"red": 0.98, "green": 0.90, "blue": 0.60},
        "green": {"red": 0.85, "green": 0.92, "blue": 0.83},
    }.get(color, {"red": 1, "green": 1, "blue": 1})


def write_scenario_sheet(spreadsheet: Spreadsheet, cabinet: str, payload: dict[str, Any]) -> None:
    """Пишет лист «Экономика сценариев» с градацией 30-90% + топ-артикулы.

    Args:
        spreadsheet: gspread Spreadsheet.
        cabinet: Код кабинета.
        payload: Результат analyze_scenarios().
    """
    worksheet = _get_or_create_worksheet(spreadsheet, scenario_sheet_name(cabinet))
    worksheet.clear()
    _clear_banding(spreadsheet, worksheet.id)

    rows: list[list[Any]] = []
    format_requests: list[dict] = []

    # Паспорт (rows 1-10)
    rows.append(["📊 ЭКОНОМИКА СЦЕНАРИЕВ"])
    rows.append([f"Кабинет: {cabinet}"])
    rows.append([f"Период: {payload['period_days']} дней"])
    rows.append([f"Текущий ИЛ: {payload['current_il']:.2f} (≈ {payload['current_loc_pct']:.1f}% локализации)"])
    rows.append([f"Текущая логистика: {payload['current_scenario']['logistics_monthly']:,.0f} ₽/мес"])
    rows.append([f"Текущая переплата ИРП: {payload['current_scenario']['irp_monthly']:,.0f} ₽/мес"])
    rows.append([f"Итого сейчас: {payload['current_scenario']['total_monthly']:,.0f} ₽/мес"])
    rows.append([])
    rows.append([])
    rows.append([])

    # Сводная таблица (строка 11 = заголовок, 12 = описания, 13+ = данные)
    rows.append(["СРАВНЕНИЕ СЦЕНАРИЕВ ЛОКАЛИЗАЦИИ"])
    rows.append([])

    headers = ["Сценарий", "Целевая лок.%", "КТР", "КРП%", "Логистика ₽/мес", "ИРП ₽/мес", "Итого ₽/мес", "Δ vs Сейчас", "Δ vs Худший"]
    rows.append(headers)
    # Строка-описание
    desc = [SHEET_COLUMN_DOCS["scenarios"].get(h, "") for h in headers]
    rows.append(desc)

    # Строки сценариев + anchor текущего
    all_scenarios = sorted(
        payload["scenarios"] + [{
            **payload["current_scenario"],
            "level_pct": payload["current_loc_pct"],
            "ktr": payload["current_il"],
            "krp_pct": 0.0,  # current_scenario у нас не расщеплён по КРП
            "delta_vs_current": 0.0,
            "delta_vs_worst": 0.0,
            "color": "yellow",
            "label": "Сейчас",
        }],
        key=lambda s: s.get("level_pct", 0),
    )

    scenario_start_row = len(rows)
    for sc in all_scenarios:
        label = sc.get("label", f"{sc['level_pct']:.0f}%")
        rows.append([
            label,
            f"{sc['level_pct']:.0f}%",
            f"{sc.get('ktr', 0):.2f}",
            f"{sc.get('krp_pct', 0):.2f}%",
            round(sc.get("logistics_monthly", 0)),
            round(sc.get("irp_monthly", 0)),
            round(sc.get("total_monthly", 0)),
            round(sc.get("delta_vs_current", 0)),
            round(sc.get("delta_vs_worst", 0)),
        ])
    scenario_end_row = len(rows) - 1
    rows.append([])

    # KPI-плитки (блок 3)
    rows.append(["KPI"])
    rows.append([
        f"Сейчас платите: {payload['current_scenario']['total_monthly']:,.0f} ₽/мес",
        f"Макс. потенциал: {payload['relocation_economics']['max_savings_monthly']:,.0f} ₽/мес",
        f"Чистая выгода: {payload['relocation_economics']['net_benefit_monthly']:,.0f} ₽/мес",
    ])
    rows.append([])

    # Топ-15 артикулов
    rows.append(["ТОП АРТИКУЛОВ ТЯНУЩИХ ИНДЕКС ВНИЗ"])
    rows.append([])
    top_headers = ["#", "Артикул", "Лок.% сейчас", "КТР", "КРП%", "Заказов/мес", "Логистика ₽/мес", "ИРП ₽/мес", "Вклад в ИЛ", "Экономия при 80% ₽/мес", "Статус"]
    rows.append(top_headers)
    rows.append([SHEET_COLUMN_DOCS["top_articles"].get(h, "") for h in top_headers])
    for i, art in enumerate(payload.get("top_articles", []), 1):
        rows.append([
            i,
            art["article"],
            f"{art['loc_pct']:.0f}%",
            f"{art['ktr']:.2f}",
            f"{art['krp_pct']:.2f}%",
            art["orders_monthly"],
            round(art["logistics_fact_monthly"]),
            round(art["irp_current_monthly"]),
            f"{art['contribution_to_il']:+.1f}",
            round(art["savings_if_80_monthly"]),
            art["status"],
        ])
    rows.append([])

    # Экономика перестановок
    rows.append(["ЭКОНОМИКА ПЕРЕСТАНОВОК"])
    rows.append([])
    econ = payload["relocation_economics"]
    rows.append(["Метрика", "Значение", "Описание"])
    rows.append(["Оборот кабинета ₽/мес", f"{econ['turnover_monthly']:,.0f}", "Общая выручка, из данных о заказах"])
    rows.append(["Комиссия (+0.5%)", f"{econ['commission_monthly']:,.0f}", "Платится пока опция включена"])
    rows.append(["Точка окупаемости", f"{econ['breakeven_monthly']:,.0f}", "Экономия должна быть выше"])
    rows.append(["Макс. экономия при 80%", f"{econ['max_savings_monthly']:,.0f}", "Потенциал из сводной таблицы"])
    rows.append([f"ЧИСТАЯ ВЫГОДА", f"{econ['net_benefit_monthly']:,.0f}", "✅ если > 0 — перестановки выгодны"])
    rows.append(["Lock-in период", f"{econ['lock_in_days']} дней", "Нельзя отключить раньше"])

    # Запись
    max_cols = max(len(r) for r in rows) if rows else 9
    normalized = [r + [""] * (max_cols - len(r)) for r in rows]
    worksheet.update("A1", normalized)

    # Форматирование сценариев по цветам
    for i, sc in enumerate(all_scenarios):
        color = _color_for_scenario(sc.get("color", "yellow"))
        row_idx = scenario_start_row + i
        format_requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": worksheet.id,
                    "startRowIndex": row_idx,
                    "endRowIndex": row_idx + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 9,
                },
                "cell": {"userEnteredFormat": {"backgroundColor": color}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        })

    # Колонки ширины
    format_requests.extend(_col_widths(worksheet.id, [
        (0, 140), (1, 100), (2, 80), (3, 80), (4, 140), (5, 140), (6, 140), (7, 120), (8, 120),
    ]))
    # Freeze
    format_requests.extend(_freeze(worksheet.id, 1, 1))

    if format_requests:
        spreadsheet.batch_update({"requests": format_requests})
```

- [ ] **Step 5: Регистрация в `__init__.py` + удаление legacy economics**

В `sheets_export/__init__.py`:
```python
from .scenario_sheet import write_scenario_sheet, scenario_sheet_name
```

В функции `export_to_sheets` — заменить вызов `write_economics_sheet` на `write_scenario_sheet` если `payload["scenarios"]` присутствует. Legacy `write_economics_sheet` из `analysis_sheets.py` удалить.

- [ ] **Step 6: Тесты проходят**

```bash
pytest tests/wb_localization/test_scenario_sheet.py -v
```

- [ ] **Step 7: Коммит**

```bash
git add services/wb_localization/sheets_export/scenario_sheet.py \
         services/wb_localization/sheets_export/__init__.py \
         services/wb_localization/sheets_export/formatters.py \
         services/wb_localization/sheets_export/analysis_sheets.py \
         tests/wb_localization/test_scenario_sheet.py
git commit -m "feat(wb_localization): add scenario_sheet writer

Лист «Экономика сценариев {cabinet}» с градацией 30-90%:
- Паспорт отчёта
- Сводная таблица сценариев + anchor текущего (цветовое кодирование)
- KPI-плитки (сейчас, макс. потенциал, чистая выгода)
- Топ-15 артикулов по потенциалу экономии
- Экономика перестановок (комиссия, окупаемость)

Каждая колонка имеет строку-описание из SHEET_COLUMN_DOCS.
Удалён legacy write_economics_sheet (3-сценарный)."
```

---

### Task 9: Sheet writer `roadmap_sheet.py`

**Files:**
- Create: `services/wb_localization/sheets_export/roadmap_sheet.py`
- Modify: `services/wb_localization/sheets_export/__init__.py` (регистрация)
- Test: `tests/wb_localization/test_roadmap_sheet.py`

**Context:** Лист «Перестановки + Roadmap» — 5 блоков: как работают перестановки, паспорт прогноза, понедельный roadmap (14 строк), график, детальный план перестановок.

- [ ] **Step 1: Failing-тест**

`tests/wb_localization/test_roadmap_sheet.py`:
```python
"""Тесты roadmap_sheet writer."""
from unittest.mock import MagicMock
from services.wb_localization.sheets_export.roadmap_sheet import (
    write_roadmap_sheet,
    roadmap_sheet_name,
)


def test_sheet_name_includes_cabinet():
    assert roadmap_sheet_name("ooo") == "Перестановки Roadmap ooo"


def test_write_roadmap_sheet_writes_14_weeks():
    mock_spreadsheet = MagicMock()
    mock_worksheet = MagicMock()
    mock_worksheet.id = 77
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    payload = {
        "params": {
            "realistic_limit_pct": 0.3,
            "target_localization": 85.0,
            "period_days": 30,
            "total_plan_qty": 4200,
            "articles_with_movements": 23,
        },
        "roadmap": [
            {
                "week": i,
                "date": f"2026-04-{16+i*7:02d}",
                "moved_units_cumulative": i * 300,
                "plan_pct": i * 7.5,
                "il_forecast": 55 + i * 2,
                "ktr_weighted": 1.05 - i * 0.02,
                "logistics_monthly": 140000 - i * 4000,
                "irp_monthly": 14000 - i * 1000,
                "total_monthly": 140500 - i * 3500,
                "savings_vs_current": -i * 3500,
            }
            for i in range(14)
        ],
        "schedule": {str(i): [{"article": f"A{i}", "qty": 300}] for i in range(14)},
        "milestones": {"week_60pct": 4, "week_80pct": 9},
        "movements_plan": [
            {
                "rank": 1, "priority": "P1", "article": "wendy/xl", "size": "XL",
                "loc_pct_current": 38, "from_fd": "Центральный", "to_fd": "Уральский",
                "from_stock_surplus": 420, "to_stock_deficit": 320,
                "qty": 320, "impact_il_pp": 1.6, "savings_monthly": 21500,
                "warehouse_limit_status": "✅", "start_week": 1,
            },
        ],
    }

    write_roadmap_sheet(mock_spreadsheet, "ooo", payload)

    mock_worksheet.clear.assert_called_once()
    assert mock_worksheet.update.call_count >= 1
    assert mock_spreadsheet.batch_update.call_count >= 1
```

- [ ] **Step 2: Тест падает**

```bash
pytest tests/wb_localization/test_roadmap_sheet.py -v
```

- [ ] **Step 3: Реализация `roadmap_sheet.py`**

```python
# services/wb_localization/sheets_export/roadmap_sheet.py
"""Запись листа «Перестановки Roadmap {cabinet}»."""
from __future__ import annotations
from typing import Any

from gspread import Spreadsheet
from gspread.exceptions import WorksheetNotFound

from .formatters import (
    _col_widths,
    _row_height,
    _freeze,
    _borders,
    _banding,
    _clear_banding,
    SHEET_COLUMN_DOCS,
)


def roadmap_sheet_name(cabinet: str) -> str:
    return f"Перестановки Roadmap {cabinet}"


def _get_or_create_worksheet(spreadsheet: Spreadsheet, name: str, rows: int = 200, cols: int = 13):
    try:
        return spreadsheet.worksheet(name)
    except WorksheetNotFound:
        return spreadsheet.add_worksheet(title=name, rows=rows, cols=cols)


def _highlight_color(week_num: int, milestones: dict) -> dict | None:
    w60 = milestones.get("week_60pct")
    w80 = milestones.get("week_80pct")
    if w80 is not None and week_num == w80:
        return {"red": 0.70, "green": 0.88, "blue": 0.70}  # тёмно-зелёный
    if w60 is not None and week_num == w60:
        return {"red": 0.85, "green": 0.92, "blue": 0.83}  # светло-зелёный
    if week_num == 0:
        return {"red": 0.98, "green": 0.90, "blue": 0.60}  # жёлтый (anchor)
    return None


def write_roadmap_sheet(spreadsheet: Spreadsheet, cabinet: str, payload: dict[str, Any]) -> None:
    """Пишет лист «Перестановки + Roadmap» с 5 блоками."""
    worksheet = _get_or_create_worksheet(spreadsheet, roadmap_sheet_name(cabinet))
    worksheet.clear()
    _clear_banding(spreadsheet, worksheet.id)

    rows: list[list[Any]] = []
    format_requests: list[dict] = []

    params = payload.get("params", {})
    milestones = payload.get("milestones", {})

    # Блок 1: объяснение
    rows.append(["🚚 ПЕРЕСТАНОВКИ + ROADMAP"])
    rows.append([f"Кабинет: {cabinet}"])
    rows.append([])
    rows.append(["Перестановки — опт-ин сервис WB. Комиссия +0.5% на все продажи, lock-in 90 дней."])
    rows.append(["Подробнее — см. лист «Справочник» → блок 5."])
    rows.append([])

    # Блок 2: паспорт прогноза
    rows.append(["ПАСПОРТ ПРОГНОЗА"])
    rows.append(["Параметр", "Значение", "Описание"])
    rows.append(["Реалистичный % лимитов", f"{params.get('realistic_limit_pct', 0)*100:.0f}%",
                 "Сколько слотов получаем по факту"])
    rows.append(["Целевая лок. после переноса", f"{params.get('target_localization', 85):.0f}%",
                 "Локализация артикула после успешного перемещения"])
    rows.append(["Артикулов с перестановками", params.get("articles_with_movements", 0),
                 "loc% < 80% и есть заказы"])
    rows.append(["Всего единиц к перемещению", params.get("total_plan_qty", 0),
                 "Суммарный план в шт"])
    w60 = milestones.get("week_60pct")
    w80 = milestones.get("week_80pct")
    rows.append(["Неделя пересечения 60% (КРП→0)", w60 if w60 is not None else "—",
                 "Quick win: КРП обнуляется"])
    rows.append(["Неделя достижения 80% (КТР=0.80)", w80 if w80 is not None else "—",
                 "Максимальная скидка логистики"])
    rows.append([])

    # Блок 3: понедельный roadmap
    rows.append(["ПОНЕДЕЛЬНЫЙ ROADMAP"])
    rows.append([])
    roadmap_headers = ["Неделя", "Дата", "Перемещено шт (кумулятив)", "% плана", "ИЛ прогноз",
                       "КТР взвеш.", "Логистика ₽/мес", "Экономия vs Сейчас", "Статус"]
    rows.append(roadmap_headers)
    rows.append([SHEET_COLUMN_DOCS["roadmap"].get(h, "") for h in roadmap_headers])

    roadmap_start_row = len(rows)
    for week_data in payload["roadmap"]:
        status = ""
        if week_data["week"] == 0:
            status = "🟡 Сейчас"
        elif w80 is not None and week_data["week"] == w80:
            status = "🎯 Цель 80%!"
        elif w60 is not None and week_data["week"] == w60:
            status = "🎯 Порог 60% (КРП→0)"
        else:
            status = "🟢 В процессе" if week_data["savings_vs_current"] < 0 else "🟡"

        rows.append([
            week_data["week"],
            week_data["date"],
            week_data["moved_units_cumulative"],
            f"{week_data['plan_pct']:.1f}%",
            f"{week_data['il_forecast']:.1f}%",
            f"{week_data['ktr_weighted']:.3f}",
            round(week_data["logistics_monthly"]),
            round(week_data["savings_vs_current"]),
            status,
        ])
    roadmap_end_row = len(rows) - 1
    rows.append([])

    # Блок 4: График (reference note - график создаётся через addChart позже)
    rows.append(["ГРАФИК ПРОГНОЗА"])
    rows.append(["(ниже вставляется линейный chart: ИЛ% по неделям + reference lines 60% и 80%)"])
    rows.append([])

    # Блок 5: детальный план
    rows.append(["ДЕТАЛЬНЫЙ ПЛАН ПЕРЕСТАНОВОК"])
    rows.append([])
    plan_headers = ["#", "Приоритет", "Артикул", "Размер", "Лок.% текущая", "Откуда (ФО + склад)",
                    "Куда (ФО + склад)", "Кол-во шт", "Импакт на ИЛ (п.п.)", "Экономия ₽/мес",
                    "Склад-лимит", "Неделя старта"]
    rows.append(plan_headers)
    rows.append([SHEET_COLUMN_DOCS["plan"].get(h, "") for h in plan_headers])

    for item in payload.get("movements_plan", []):
        rows.append([
            item.get("rank", ""),
            item.get("priority", ""),
            item.get("article", ""),
            item.get("size", ""),
            f"{item.get('loc_pct_current', 0):.0f}%",
            f"{item.get('from_fd', '')} (избыток {item.get('from_stock_surplus', 0)})",
            f"{item.get('to_fd', '')} (дефицит {item.get('to_stock_deficit', 0)})",
            item.get("qty", 0),
            f"+{item.get('impact_il_pp', 0):.1f}",
            round(item.get("savings_monthly", 0)),
            item.get("warehouse_limit_status", ""),
            item.get("start_week", 0),
        ])

    # Запись
    max_cols = max(len(r) for r in rows) if rows else 12
    normalized = [r + [""] * (max_cols - len(r)) for r in rows]
    worksheet.update("A1", normalized)

    # Подсветка milestone строк
    for i, week_data in enumerate(payload["roadmap"]):
        color = _highlight_color(week_data["week"], milestones)
        if color:
            row_idx = roadmap_start_row + i
            format_requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": row_idx,
                        "endRowIndex": row_idx + 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": 9,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": color,
                            "textFormat": {"bold": True if week_data["week"] in [w60, w80] else False},
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            })

    format_requests.extend(_col_widths(worksheet.id, [
        (0, 70), (1, 100), (2, 150), (3, 80), (4, 100), (5, 100), (6, 140), (7, 140), (8, 140),
    ]))
    format_requests.extend(_freeze(worksheet.id, 1, 2))

    if format_requests:
        spreadsheet.batch_update({"requests": format_requests})
```

- [ ] **Step 4: Тесты проходят**

```bash
pytest tests/wb_localization/test_roadmap_sheet.py -v
```

- [ ] **Step 5: Регистрация в `__init__.py`**

```python
from .roadmap_sheet import write_roadmap_sheet, roadmap_sheet_name
```

В `export_to_sheets` — вызвать если `payload["forecast"]` присутствует:
```python
if payload.get("forecast"):
    write_roadmap_sheet(spreadsheet, cabinet, payload["forecast"])
```

- [ ] **Step 6: Коммит**

```bash
git add services/wb_localization/sheets_export/roadmap_sheet.py \
         services/wb_localization/sheets_export/__init__.py \
         tests/wb_localization/test_roadmap_sheet.py
git commit -m "feat(wb_localization): add roadmap_sheet writer

Лист «Перестановки Roadmap {cabinet}» с 5 блоками:
- Объяснение механики + ссылка на Справочник
- Паспорт прогноза (параметры симуляции, milestones)
- Понедельный roadmap (14 строк, подсветка недель 60% и 80%)
- Placeholder для chart'а
- Детальный план перестановок с приоритизацией

Каждая колонка имеет строку-описание из SHEET_COLUMN_DOCS."
```

---

## Волна 4 — Интеграция

### Task 10: Обновление `run_localization.py` — интеграция новых шагов

**Files:**
- Modify: `services/wb_localization/run_localization.py`
- Test: `tests/wb_localization/test_run_localization_integration.py`

**Context:** Включить новые калькуляторы в pipeline + передать новые данные в `export_to_sheets`. Добавить сбор `turnover_rub` (оборот кабинета), weekly_snapshots и movement_plan.

- [ ] **Step 1: Найти точку интеграции**

```bash
grep -n "analyze_economics\|analyze_il_irp\|export_to_sheets" services/wb_localization/run_localization.py
```

Определить где вставлять новые вызовы (обычно между `analyze_economics` и `export_to_sheets`).

- [ ] **Step 2: Добавить расчёт turnover**

Найти в `run_localization.py` место где есть `logistics_costs`. Добавить рядом сбор revenue:

```python
# services/wb_localization/run_localization.py
# ... существующий код ...

def _calculate_turnover_from_orders(orders_df) -> float:
    """Суммарная выручка из orders_df за период."""
    if "Цена" in orders_df.columns and "Кол-во" in orders_df.columns:
        return float((orders_df["Цена"] * orders_df["Кол-во"]).sum())
    # Fallback: если orders уже имеют totalPrice
    if "totalPrice" in orders_df.columns:
        return float(orders_df["totalPrice"].sum())
    return 0.0
```

- [ ] **Step 3: Добавить сохранение weekly_snapshots**

После `run_analysis_v3` (где есть df_regions с периодом):

```python
def _extract_weekly_snapshots(df_regions, cabinet: str) -> list[dict]:
    """Агрегирует df_regions в недельные снапшоты (ISO-недели)."""
    import pandas as pd
    from datetime import datetime

    if df_regions.empty:
        return []

    # Добавляем колонку week_start (понедельник ISO-недели)
    if "Дата" in df_regions.columns:
        df_regions = df_regions.copy()
        df_regions["week_start"] = pd.to_datetime(df_regions["Дата"]).dt.to_period("W-MON").dt.start_time

    snapshots = []
    group_cols = ["week_start", "Артикул продавца", "Регион"] if "week_start" in df_regions.columns else ["Артикул продавца", "Регион"]

    for key, group in df_regions.groupby(group_cols):
        week_start = key[0] if "week_start" in group_cols else datetime.now().date()
        article = key[group_cols.index("Артикул продавца")]
        region = key[group_cols.index("Регион")]

        local = int(group["Заказы со склада ВБ локально, шт"].sum())
        nonlocal_ = int(group["Заказы со склада ВБ не локально, шт"].sum())

        snapshots.append({
            "week_start": week_start.date() if hasattr(week_start, "date") else week_start,
            "article": str(article),
            "region": str(region),
            "local_orders": local,
            "nonlocal_orders": nonlocal_,
        })
    return snapshots
```

- [ ] **Step 4: Интегрировать новые калькуляторы**

В функцию `run_for_cabinet()` (или `run_service_report`) добавить после `analyze_economics`:

```python
from services.wb_localization.calculators.reference_builder import build_reference_content
from services.wb_localization.calculators.scenario_engine import analyze_scenarios
from services.wb_localization.calculators.relocation_forecaster import simulate_roadmap
from services.wb_localization.irp_coefficients import REDISTRIBUTION_LIMITS

# ... после analyze_economics ...

# Turnover для сценариев
turnover_rub = _calculate_turnover_from_orders(orders_df)

# Сценарии (градация 30-90%)
scenarios = None
if not args.skip_scenarios:
    scenarios = analyze_scenarios(
        il_irp=il_irp,
        logistics_costs=logistics_costs,
        turnover_rub=turnover_rub,
        period_days=days,
    )

# Forecast (понедельный roadmap)
forecast = None
if not args.skip_forecast:
    # Добавить stock_total к каждому артикулу
    stocks_by_article = df_stocks.groupby("Артикул продавца")["Остатки на текущий день, шт"].sum().to_dict()
    articles_with_stock = [
        {**a, "stock_total": int(stocks_by_article.get(a["article"], 0))}
        for a in il_irp["articles"]
    ]
    # Импакт в ₽ добавляем к каждому movement (если ещё не добавлен)
    movements_with_impact = _enrich_movements_with_impact(core["movements"], il_irp, logistics_costs, days)
    forecast = simulate_roadmap(
        articles=articles_with_stock,
        movements=movements_with_impact,
        logistics_costs=logistics_costs,
        weekly_orders_history=history.get_weekly_snapshots(cabinet_key, weeks_back=13),
        redistribution_limits=REDISTRIBUTION_LIMITS,
        realistic_limit_pct=args.realistic_limit_pct,
        period_days=days,
    )
    # Добавим movements_plan для детального плана
    forecast["movements_plan"] = _build_movements_plan(movements_with_impact, forecast["schedule"])

# Reference — всегда
reference = build_reference_content()

# Сохранение weekly_snapshots
weekly_snapshots = _extract_weekly_snapshots(df_regions, cabinet_key)
if weekly_snapshots:
    from collections import defaultdict
    by_week = defaultdict(list)
    for s in weekly_snapshots:
        by_week[s["week_start"]].append(s)
    for week_start, snaps in by_week.items():
        history.save_weekly_snapshots(cabinet_key, week_start, snaps)

# Экспорт
export_to_sheets({
    "cabinet": cabinet_key,
    "core": core,
    "il_irp": il_irp,
    "economics": economics,  # legacy-совместимость
    "scenarios": scenarios,
    "forecast": forecast,
    "reference": reference,
})
```

И helper-функции:

```python
def _enrich_movements_with_impact(movements, il_irp, logistics_costs, period_days):
    """Добавляет impact_rub к каждому движению для приоритизации в forecast."""
    article_index = {a["article"].lower(): a for a in il_irp["articles"]}
    enriched = []
    for mv in movements:
        art_lower = mv.get("article", "").lower() if isinstance(mv.get("article"), str) else ""
        art = article_index.get(art_lower, {})
        qty = mv.get("qty", 0)
        savings_per_unit = art.get("price", 0) * (art.get("krp_pct", 0) / 100) / max(art.get("wb_total", 1), 1) if art else 0
        impact_rub = qty * savings_per_unit * 30 / period_days
        enriched.append({**mv, "impact_rub": impact_rub})
    return enriched


def _build_movements_plan(movements, schedule):
    """Формирует список для детального плана (блок 5 roadmap_sheet)."""
    plan = []
    # Обратный индекс: какая неделя старта для каждого movement
    week_by_movement = {}
    for week_str, movements_in_week in schedule.items():
        for mv in movements_in_week:
            key = (mv.get("article"), mv.get("to_warehouse"))
            week_by_movement.setdefault(key, int(week_str))

    sorted_movements = sorted(movements, key=lambda m: m.get("impact_rub", 0), reverse=True)
    for rank, mv in enumerate(sorted_movements, 1):
        start_week = week_by_movement.get((mv.get("article"), mv.get("to_warehouse")), 0)
        priority = "P1" if mv.get("impact_rub", 0) > 10000 else "P2" if mv.get("impact_rub", 0) > 1000 else "P3"
        plan.append({
            "rank": rank,
            "priority": priority,
            "article": mv.get("article"),
            "size": mv.get("size", ""),
            "loc_pct_current": mv.get("current_loc_pct", 0),
            "from_fd": mv.get("from_region", ""),
            "to_fd": mv.get("to_region", ""),
            "from_stock_surplus": mv.get("from_surplus", 0),
            "to_stock_deficit": mv.get("to_deficit", 0),
            "qty": mv.get("qty", 0),
            "impact_il_pp": mv.get("impact_il_pp", 0),
            "savings_monthly": mv.get("impact_rub", 0),
            "warehouse_limit_status": "✅",  # упрощение
            "start_week": start_week,
        })
    return plan
```

- [ ] **Step 5: Добавить CLI-флаги**

В начале `run_localization.py` где argparse:

```python
parser.add_argument("--skip-scenarios", action="store_true",
                    help="Пропустить расчёт сценариев (градация 30-90%)")
parser.add_argument("--skip-forecast", action="store_true",
                    help="Пропустить прогноз перестановок (13-недельный roadmap)")
parser.add_argument("--realistic-limit-pct", type=float, default=0.3,
                    help="Доля реально получаемых лимитов складов (0.0–1.0), дефолт 0.3")
parser.add_argument("--only-reference", action="store_true",
                    help="Обновить только лист «Справочник»")
```

Обработку `--only-reference`:
```python
if args.only_reference:
    reference = build_reference_content()
    export_to_sheets({
        "cabinet": cabinet_key,
        "reference": reference,
        # остальные ключи пропущены → фасад пропустит их запись
    })
    return
```

Убедиться что `export_to_sheets` в `__init__.py` гибко обрабатывает отсутствие ключей.

- [ ] **Step 6: Интеграционный тест**

`tests/wb_localization/test_run_localization_integration.py`:

```python
"""Интеграционный smoke-тест run_localization с моками WB API."""
from unittest.mock import patch, MagicMock
import pandas as pd


@patch("services.wb_localization.run_localization.export_to_sheets")
@patch("services.wb_localization.run_localization.fetch_logistics_costs")
@patch("services.wb_localization.run_localization.fetch_own_stock")
@patch("services.wb_localization.run_localization.fetch_wb_data")
def test_run_for_cabinet_calls_export_with_new_keys(
    mock_fetch_wb, mock_fetch_stock, mock_fetch_logistics, mock_export,
):
    # Arrange — минимальные данные
    mock_fetch_wb.return_value = {
        "warehouse_remains": pd.DataFrame([{"Артикул продавца": "wendy/xl", "Склад": "Коледино", "Остатки на текущий день, шт": 100}]),
        "orders": pd.DataFrame([{"Артикул продавца": "wendy/xl", "Склад": "Коледино", "Регион": "Центральный", "Кол-во": 10, "Цена": 1000}]),
        "prices": {"wendy/xl": 1000.0},
    }
    mock_fetch_stock.return_value = {}
    mock_fetch_logistics.return_value = {"wendy/xl": 500.0}

    from services.wb_localization.run_localization import run_for_cabinet

    result = run_for_cabinet("ooo", days=30)

    # Assert — export вызван с новыми ключами
    assert mock_export.called
    call_payload = mock_export.call_args[0][0]
    assert "reference" in call_payload
    # scenarios/forecast могут быть None если отключены, но ключи должны быть
    assert "scenarios" in call_payload
    assert "forecast" in call_payload
```

- [ ] **Step 7: Запустить тест**

```bash
pytest tests/wb_localization/test_run_localization_integration.py -v
```

Ожидается: PASS (возможно с некоторыми skip, если структура данных не совпадает).

- [ ] **Step 8: E2E dry-run**

```bash
python -m services.wb_localization.run_localization --cabinet ooo --dry-run 2>&1 | tail -40
```

Ожидается: все шаги пайплайна проходят без исключений (включая scenarios и forecast).

- [ ] **Step 9: Коммит**

```bash
git add services/wb_localization/run_localization.py \
         tests/wb_localization/test_run_localization_integration.py
git commit -m "feat(wb_localization): integrate scenario + forecast + reference into pipeline

run_for_cabinet() теперь:
- Считает turnover из orders_df
- Сохраняет weekly_snapshots для forecast
- Запускает analyze_scenarios (градация 30-90%)
- Запускает simulate_roadmap (13-нед. прогноз)
- Строит reference_builder для Справочника
- Передаёт всё в export_to_sheets

Новые CLI-флаги: --skip-scenarios, --skip-forecast,
--realistic-limit-pct, --only-reference."
```

---

### Task 11: End-to-end проверка и финализация

**Files:**
- Modify: `docs/agents/mp-localization.md`
- Create: `docs/superpowers/plans/2026-04-16-localization-service-redesign-COMPLETION.md`

**Context:** Последняя проверка — запустить полный пайплайн, проверить что все листы создаются корректно, обновить документацию.

- [ ] **Step 1: Полный запуск на тестовом кабинете**

```bash
python -m services.wb_localization.run_localization --cabinet ooo --days 30 2>&1 | tee /tmp/e2e_final.log
```

Ожидается: успешное завершение без ошибок. В логе видно упоминание "Справочник", "Экономика сценариев", "Перестановки Roadmap".

- [ ] **Step 2: Визуальная проверка в Google Sheets**

Открыть целевой spreadsheet (id из `VASILY_SPREADSHEET_ID`). Проверить:
- Лист «Справочник» имеет 8 блоков, таблицы КТР/КРП раскрашены
- Лист «Экономика сценариев ooo» имеет градацию 30-90% с anchor на текущем
- Лист «Перестановки Roadmap ooo» имеет 14 строк roadmap с подсвеченными milestone'ами

- [ ] **Step 3: Прогнать весь тестовый набор**

```bash
pytest tests/wb_localization/ -v --tb=short 2>&1 | tail -50
```

Ожидается: все тесты PASS (существующие + новые).

- [ ] **Step 4: Обновить `docs/agents/mp-localization.md`**

Добавить секцию:

```markdown
## Расширение 2026-04-16: сценарии + roadmap

Сервис теперь генерирует 3 дополнительных листа:

1. **Справочник** (расширенный) — 8 тематических блоков с полной документацией WB.
2. **Экономика сценариев {cabinet}** — градация 30-90% локализации с топ-15 артикулов.
3. **Перестановки Roadmap {cabinet}** — понедельный прогноз на 13 недель с milestone'ами.

**Новые модули:**
- `calculators/reference_builder.py` — структура справочника
- `calculators/scenario_engine.py` — сценарный анализ (30-90%)
- `calculators/relocation_forecaster.py` — 13-недельный прогноз

**Новые CLI-флаги:**
- `--skip-scenarios` — пропустить сценарный анализ
- `--skip-forecast` — пропустить прогноз перестановок
- `--realistic-limit-pct` — % реально получаемых лимитов (дефолт 0.3)
- `--only-reference` — обновить только Справочник

**История:** таблица `weekly_snapshots` хранит понедельные данные для точного forecast.
```

- [ ] **Step 5: Написать completion doc**

`docs/superpowers/plans/2026-04-16-localization-service-redesign-COMPLETION.md`:

```markdown
# WB Localization Service Redesign — Completion Report

**Дата завершения:** [дата]
**Статус:** ✅ Завершено

## Что сделано

- [x] Task 1: Верификация коэффициентов КТР
- [x] Task 2: Рефакторинг sheets_export.py в пакет
- [x] Task 3: Калькулятор reference_builder
- [x] Task 4: Калькулятор scenario_engine (30-90%)
- [x] Task 5: weekly_snapshots в history.py
- [x] Task 6: Калькулятор relocation_forecaster (13-нед. прогноз)
- [x] Task 7: Sheet writer reference_sheet
- [x] Task 8: Sheet writer scenario_sheet
- [x] Task 9: Sheet writer roadmap_sheet
- [x] Task 10: Интеграция в run_localization.py

## Метрики

- Новых модулей: 7 (3 калькулятора + 3 sheet writer + 1 package refactor)
- Строк кода: ~2500
- Тестов: ~40
- Листов в Google Sheets: 10 (было 8)

## Известные ограничения

- Forecast использует fallback при < 13 недель weekly_snapshots в истории
- Chart в roadmap_sheet — пока placeholder, не создан через addChart API
- Cell notes (hover tooltips) — не реализованы, только строки-описания

## Дальнейшие шаги (backlog)

- Реализовать addChart API в roadmap_sheet
- Cell notes для ключевых ₽-метрик
- Per-article target_localization вместо глобального 85%
- Оптимизация performance (batch API vs cell-by-cell)
```

- [ ] **Step 6: Коммит финализации**

```bash
git add docs/agents/mp-localization.md docs/superpowers/plans/2026-04-16-localization-service-redesign-COMPLETION.md
git commit -m "docs(wb_localization): update service docs + add completion report

Обновлена документация с описанием новых листов (Справочник,
Экономика сценариев, Перестановки Roadmap) и CLI-флагов.
Создан completion report с метриками и известными ограничениями."
```

---

## Сводка плана

| Волна | Задачи | Время (оценка) | Зависимости |
|---|---|---|---|
| Волна 1 | Task 1 (верификация КТР), Task 2 (рефакторинг sheets_export) | 1–2 часа | — |
| Волна 2 | Task 3 (reference_builder), Task 4 (scenario_engine), Task 5 (history weekly), Task 6 (forecaster) | 3–4 часа | Task 2 (formatters доступны) |
| Волна 3 | Task 7 (reference_sheet), Task 8 (scenario_sheet), Task 9 (roadmap_sheet) | 3–4 часа | Волна 2 |
| Волна 4 | Task 10 (интеграция), Task 11 (E2E + docs) | 2–3 часа | Волна 3 |

**Всего:** 9–13 часов работы (при последовательном выполнении). Параллелизация внутри волн может сократить до 5–7 часов.

**Commit cadence:** после каждого step «Коммит» делается отдельный commit. Всего ожидается ~15 коммитов.
