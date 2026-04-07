# Reviews Audit Skill v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `/reviews-audit` skill for deep product analytics — LLM-кластеризация, карточка каждой активной модели, rich Notion-публикация.

**Architecture:** Python collector v2 (два кабинета, расширенные DB-запросы) → SKILL.md v2 (8 фаз с субагентами для LLM-кластеризации и продуктового анализа) → Notion MCP (enhanced markdown с цветами и callout-блоками).

**Tech Stack:** Python (httpx, shared/clients/wb_client.py, shared/data_layer), Supabase MCP, Notion MCP, Claude Code SKILL.md

**Spec:** `docs/superpowers/specs/2026-04-07-reviews-audit-v2-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `shared/data_layer/finance.py` | Modify | Add `get_wb_buyouts_returns_by_artikul()`, `get_wb_buyouts_returns_monthly()` |
| `scripts/reviews_audit/collect_data.py` | Rewrite | v2: two cabinets, dedup, expanded JSON with orders_by_artikul + orders_monthly |
| `.claude/skills/reviews-audit/SKILL.md` | Rewrite | v2: 8 phases, subagents, Notion MCP publishing |
| `tests/test_reviews_audit_collector.py` | Rewrite | v2 tests for new collector + new data_layer functions |

---

### Task 1: Add `get_wb_buyouts_returns_by_artikul()` to data_layer

**Files:**
- Modify: `shared/data_layer/finance.py`
- Modify: `tests/test_reviews_audit_collector.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_reviews_audit_collector.py`:

```python
class TestGetWbBuyoutsReturnsByArtikul:
    """Tests for get_wb_buyouts_returns_by_artikul function."""

    def test_function_exists(self):
        from shared.data_layer import get_wb_buyouts_returns_by_artikul
        assert callable(get_wb_buyouts_returns_by_artikul)

    def test_returns_list(self):
        from shared.data_layer import get_wb_buyouts_returns_by_artikul

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("wendy", "wendy/розовый", 50, 40, 10),
            ("wendy", "wendy/чёрный", 30, 25, 5),
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(
            "shared.data_layer.finance._get_wb_connection", return_value=mock_conn
        ):
            result = get_wb_buyouts_returns_by_artikul("2025-04-07", "2026-04-07")
            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0][0] == "wendy"
            assert result[0][1] == "wendy/розовый"
            assert result[0][2] == 50  # orders
            assert result[0][3] == 40  # buyouts
            assert result[0][4] == 10  # returns
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python3 -m pytest tests/test_reviews_audit_collector.py::TestGetWbBuyoutsReturnsByArtikul -v
```

Expected: FAIL — `ImportError: cannot import name 'get_wb_buyouts_returns_by_artikul'`

- [ ] **Step 3: Implement the function**

Add to `shared/data_layer/finance.py` after `get_wb_buyouts_returns_by_model()`:

```python
def get_wb_buyouts_returns_by_artikul(
    date_from: str, date_to: str
) -> list[tuple]:
    """Get buyout and return counts by artikul (model + color) for WB.

    Args:
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)

    Returns:
        List of (model, artikul, orders_count, buyout_count, return_count)
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    sql = f"""
        SELECT
            {get_osnova_sql("SPLIT_PART(supplierarticle, '/', 1)")} as model,
            LOWER(supplierarticle) as artikul,
            COUNT(*) as orders_count,
            SUM(CASE WHEN iscancel::text IN ('0', 'false') OR iscancel IS NULL THEN 1 ELSE 0 END) as buyout_count,
            SUM(CASE WHEN iscancel::text IN ('1', 'true') THEN 1 ELSE 0 END) as return_count
        FROM orders
        WHERE date >= %s AND date < %s
        GROUP BY 1, 2
        ORDER BY 1, 3 DESC;
    """
    cur.execute(sql, (date_from, date_to))
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results
```

Add `"get_wb_buyouts_returns_by_artikul"` to `__all__` in `shared/data_layer/finance.py`.

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_reviews_audit_collector.py::TestGetWbBuyoutsReturnsByArtikul -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/data_layer/finance.py tests/test_reviews_audit_collector.py
git commit -m "feat(data-layer): add get_wb_buyouts_returns_by_artikul() for drill-down analysis"
```

---

### Task 2: Add `get_wb_buyouts_returns_monthly()` to data_layer

**Files:**
- Modify: `shared/data_layer/finance.py`
- Modify: `tests/test_reviews_audit_collector.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_reviews_audit_collector.py`:

```python
class TestGetWbBuyoutsReturnsMonthly:
    """Tests for get_wb_buyouts_returns_monthly function."""

    def test_function_exists(self):
        from shared.data_layer import get_wb_buyouts_returns_monthly
        assert callable(get_wb_buyouts_returns_monthly)

    def test_returns_list(self):
        from shared.data_layer import get_wb_buyouts_returns_monthly

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("2025-04-01", "wendy", 5000, 3500, 1500),
            ("2025-05-01", "wendy", 5200, 3600, 1600),
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(
            "shared.data_layer.finance._get_wb_connection", return_value=mock_conn
        ):
            result = get_wb_buyouts_returns_monthly("2025-04-07", "2026-04-07")
            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0][0] == "2025-04-01"  # month
            assert result[0][1] == "wendy"  # model
            assert result[0][2] == 5000  # orders
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_reviews_audit_collector.py::TestGetWbBuyoutsReturnsMonthly -v
```

Expected: FAIL — `ImportError: cannot import name 'get_wb_buyouts_returns_monthly'`

- [ ] **Step 3: Implement the function**

Add to `shared/data_layer/finance.py` after `get_wb_buyouts_returns_by_artikul()`:

```python
def get_wb_buyouts_returns_monthly(
    date_from: str, date_to: str
) -> list[tuple]:
    """Get buyout and return counts by month and model for WB.

    Args:
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)

    Returns:
        List of (month, model, orders_count, buyout_count, return_count)
    """
    conn = _get_wb_connection()
    cur = conn.cursor()

    sql = f"""
        SELECT
            DATE_TRUNC('month', date)::date as month,
            {get_osnova_sql("SPLIT_PART(supplierarticle, '/', 1)")} as model,
            COUNT(*) as orders_count,
            SUM(CASE WHEN iscancel::text IN ('0', 'false') OR iscancel IS NULL THEN 1 ELSE 0 END) as buyout_count,
            SUM(CASE WHEN iscancel::text IN ('1', 'true') THEN 1 ELSE 0 END) as return_count
        FROM orders
        WHERE date >= %s AND date < %s
        GROUP BY 1, 2
        ORDER BY 1, 2;
    """
    cur.execute(sql, (date_from, date_to))
    results = cur.fetchall()

    cur.close()
    conn.close()
    return results
```

Add `"get_wb_buyouts_returns_monthly"` to `__all__` in `shared/data_layer/finance.py`.

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_reviews_audit_collector.py::TestGetWbBuyoutsReturnsMonthly -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/data_layer/finance.py tests/test_reviews_audit_collector.py
git commit -m "feat(data-layer): add get_wb_buyouts_returns_monthly() for dynamics analysis"
```

---

### Task 3: Rewrite collect_data.py v2

**Files:**
- Rewrite: `scripts/reviews_audit/collect_data.py`
- Modify: `tests/test_reviews_audit_collector.py`

- [ ] **Step 1: Write the test for v2 collector**

Replace `TestCollectData` class in `tests/test_reviews_audit_collector.py`:

```python
class TestCollectDataV2:
    """Tests for v2 data collection script."""

    def test_script_importable(self):
        from scripts.reviews_audit.collect_data import collect_reviews_data
        assert callable(collect_reviews_data)

    def test_output_structure_v2(self):
        """Output JSON should have v2 keys: orders_by_model, orders_by_artikul, orders_monthly."""
        from scripts.reviews_audit.collect_data import collect_reviews_data

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name

        try:
            mock_feedbacks = [
                {
                    "id": "fb1",
                    "text": "Отличное белье!",
                    "productValuation": 5,
                    "createdDate": "2026-03-15T10:00:00Z",
                    "answer": {"text": "Спасибо!"},
                    "productDetails": {"nmId": 12345, "supplierArticle": "ruby/розовый"},
                    "color": "розовый",
                }
            ]
            mock_questions = [
                {
                    "id": "q1",
                    "text": "Какой размер выбрать?",
                    "createdDate": "2026-03-16T10:00:00Z",
                    "answer": {"text": "Рекомендуем M"},
                    "productDetails": {"nmId": 12345, "supplierArticle": "ruby/розовый"},
                }
            ]
            mock_orders_model = [("current", "ruby", 100, 85, 15)]
            mock_orders_artikul = [("ruby", "ruby/розовый", 60, 50, 10)]
            mock_orders_monthly = [("2026-03-01", "ruby", 100, 85, 15)]

            with patch(
                "scripts.reviews_audit.collect_data.WBClient"
            ) as MockClient, patch(
                "scripts.reviews_audit.collect_data.get_wb_buyouts_returns_by_model",
                return_value=mock_orders_model,
            ), patch(
                "scripts.reviews_audit.collect_data.get_wb_buyouts_returns_by_artikul",
                return_value=mock_orders_artikul,
            ), patch(
                "scripts.reviews_audit.collect_data.get_wb_buyouts_returns_monthly",
                return_value=mock_orders_monthly,
            ):
                instance = MockClient.return_value
                instance.get_all_feedbacks.return_value = mock_feedbacks
                instance.get_all_questions.return_value = mock_questions

                collect_reviews_data(
                    date_from="2026-03-01",
                    date_to="2026-04-01",
                    output_path=output_path,
                )

            with open(output_path) as f:
                data = json.load(f)

            assert "feedbacks" in data
            assert "questions" in data
            assert "orders_by_model" in data
            assert "orders_by_artikul" in data
            assert "orders_monthly" in data
            assert "metadata" in data
            assert data["metadata"]["date_from"] == "2026-03-01"
            assert data["metadata"]["date_to"] == "2026-04-01"
            assert len(data["feedbacks"]) == 1
            assert len(data["questions"]) == 1
            assert len(data["orders_by_artikul"]) == 1
            assert len(data["orders_monthly"]) == 1
        finally:
            os.unlink(output_path)

    def test_deduplication(self):
        """Feedbacks with same id should be deduplicated."""
        from scripts.reviews_audit.collect_data import _deduplicate

        items = [
            {"id": "fb1", "text": "first"},
            {"id": "fb1", "text": "duplicate"},
            {"id": "fb2", "text": "second"},
        ]
        result = _deduplicate(items, key="id")
        assert len(result) == 2
        assert result[0]["id"] == "fb1"
        assert result[1]["id"] == "fb2"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_reviews_audit_collector.py::TestCollectDataV2 -v
```

Expected: FAIL — missing v2 keys, missing `_deduplicate`

- [ ] **Step 3: Rewrite collect_data.py**

Rewrite `scripts/reviews_audit/collect_data.py`:

```python
"""Data collector v2 for reviews audit skill.

Fetches feedbacks, questions from WB API (both cabinets with dedup)
and orders/buyouts/returns from DB. Saves to expanded JSON.

Usage:
    python scripts/reviews_audit/collect_data.py \
        --date-from 2025-04-07 \
        --date-to 2026-04-07 \
        --cabinet both \
        --output /tmp/reviews_audit_data.json
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared.clients.wb_client import WBClient
from shared.data_layer import (
    get_wb_buyouts_returns_by_model,
    get_wb_buyouts_returns_by_artikul,
    get_wb_buyouts_returns_monthly,
)

logger = logging.getLogger(__name__)


def _filter_by_date(
    items: list[dict], date_from: str, date_to: str, date_field: str = "createdDate"
) -> list[dict]:
    """Filter items by date range."""
    filtered = []
    for item in items:
        created = item.get(date_field, "")
        if not created:
            continue
        date_str = created[:10]
        if date_from <= date_str < date_to:
            filtered.append(item)
    return filtered


def _deduplicate(items: list[dict], key: str = "id") -> list[dict]:
    """Remove duplicates by key, keeping first occurrence."""
    seen = set()
    result = []
    for item in items:
        k = item.get(key)
        if k and k not in seen:
            seen.add(k)
            result.append(item)
        elif not k:
            result.append(item)
    return result


def _fetch_from_cabinet(api_key: str, cabinet_name: str, date_from: str) -> tuple[list, list]:
    """Fetch feedbacks + questions from one WB cabinet."""
    client = WBClient(api_key=api_key, cabinet_name=cabinet_name)
    feedbacks = client.get_all_feedbacks()
    questions = client.get_all_questions()
    logger.info(f"[{cabinet_name}] Fetched {len(feedbacks)} feedbacks, {len(questions)} questions")
    return feedbacks, questions


def collect_reviews_data(
    date_from: str,
    date_to: str,
    output_path: str,
    cabinet: str = "both",
    api_key_ip: str | None = None,
    api_key_ooo: str | None = None,
) -> dict:
    """Collect all data for reviews audit v2.

    Args:
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        output_path: Path to save JSON output
        cabinet: 'ip', 'ooo', or 'both'
        api_key_ip: WB API key for IP cabinet
        api_key_ooo: WB API key for OOO cabinet

    Returns:
        Dict with collected data.
    """
    key_ip = api_key_ip or os.getenv("WB_API_KEY_IP", "")
    key_ooo = api_key_ooo or os.getenv("WB_API_KEY_OOO", "")

    all_feedbacks = []
    all_questions = []

    # Fetch from selected cabinets
    if cabinet in ("ip", "both") and key_ip:
        fb, q = _fetch_from_cabinet(key_ip, "IP", date_from)
        all_feedbacks.extend(fb)
        all_questions.extend(q)

    if cabinet in ("ooo", "both") and key_ooo:
        fb, q = _fetch_from_cabinet(key_ooo, "OOO", date_from)
        all_feedbacks.extend(fb)
        all_questions.extend(q)

    # Deduplicate (WB API returns same data for same brand across cabinets)
    all_feedbacks = _deduplicate(all_feedbacks, key="id")
    all_questions = _deduplicate(all_questions, key="id")

    # Filter by date
    feedbacks = _filter_by_date(all_feedbacks, date_from, date_to)
    questions = _filter_by_date(all_questions, date_from, date_to)
    logger.info(f"After dedup + date filter: {len(feedbacks)} feedbacks, {len(questions)} questions")

    # Fetch orders data from DB
    orders_by_model = []
    orders_by_artikul = []
    orders_monthly = []

    try:
        raw = get_wb_buyouts_returns_by_model(
            current_start=date_from, prev_start=date_from, current_end=date_to
        )
        orders_by_model = [
            {"period": r[0], "model": r[1], "orders_count": r[2], "buyout_count": r[3], "return_count": r[4]}
            for r in raw
        ]
    except Exception as e:
        logger.error(f"Failed to fetch orders_by_model: {e}")

    try:
        raw = get_wb_buyouts_returns_by_artikul(date_from=date_from, date_to=date_to)
        orders_by_artikul = [
            {"model": r[0], "artikul": r[1], "orders_count": r[2], "buyout_count": r[3], "return_count": r[4]}
            for r in raw
        ]
    except Exception as e:
        logger.error(f"Failed to fetch orders_by_artikul: {e}")

    try:
        raw = get_wb_buyouts_returns_monthly(date_from=date_from, date_to=date_to)
        orders_monthly = [
            {"month": str(r[0]), "model": r[1], "orders_count": r[2], "buyout_count": r[3], "return_count": r[4]}
            for r in raw
        ]
    except Exception as e:
        logger.error(f"Failed to fetch orders_monthly: {e}")

    # Build output
    result = {
        "metadata": {
            "date_from": date_from,
            "date_to": date_to,
            "cabinet": cabinet,
            "collected_at": datetime.now().isoformat(),
            "counts": {
                "feedbacks": len(feedbacks),
                "questions": len(questions),
                "models_with_orders": len(orders_by_model),
            },
        },
        "feedbacks": feedbacks,
        "questions": questions,
        "orders_by_model": orders_by_model,
        "orders_by_artikul": orders_by_artikul,
        "orders_monthly": orders_monthly,
    }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"Data saved to {output_path}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Collect data for reviews audit v2")
    parser.add_argument("--date-from", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--date-to", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--cabinet", default="both", choices=["ip", "ooo", "both"], help="WB cabinet")
    parser.add_argument("--output", default="/tmp/reviews_audit_data.json", help="Output JSON path")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    collect_reviews_data(
        date_from=args.date_from,
        date_to=args.date_to,
        output_path=args.output,
        cabinet=args.cabinet,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all tests**

```bash
python3 -m pytest tests/test_reviews_audit_collector.py -v
```

Expected: All tests PASS (TestGetWbBuyoutsReturnsByModel, TestGetWbBuyoutsReturnsByArtikul, TestGetWbBuyoutsReturnsMonthly, TestCollectDataV2, TestFilterByDate).

Note: Remove the old `TestCollectData` class if it conflicts with `TestCollectDataV2`.

- [ ] **Step 5: Verify CLI --help**

```bash
python3 scripts/reviews_audit/collect_data.py --help
```

Expected: Shows `--date-from`, `--date-to`, `--cabinet`, `--output`.

- [ ] **Step 6: Commit**

```bash
git add scripts/reviews_audit/collect_data.py tests/test_reviews_audit_collector.py
git commit -m "feat(reviews-audit): rewrite collector v2 — two cabinets, dedup, expanded orders"
```

---

### Task 4: Rewrite SKILL.md v2

**Files:**
- Rewrite: `.claude/skills/reviews-audit/SKILL.md`

This is the main skill file Claude reads when `/reviews-audit` is invoked. It defines the 8-phase workflow with subagent dispatching.

- [ ] **Step 1: Write the SKILL.md v2**

Create `.claude/skills/reviews-audit/SKILL.md` with the full 8-phase workflow. The content is large — here is the complete file:

```markdown
---
name: reviews-audit
description: "Глубокий продуктовый анализ отзывов, вопросов и возвратов WB. LLM-кластеризация, карточка каждой модели, gap-анализ, rich Notion-публикация. Триггеры: reviews-audit, аналитика отзывов, анализ возвратов, аудит отзывов, качество ответов, аудит возвратов"
---

# Аналитика отзывов и возвратов WOOKIEE v2 (Wildberries)

Глубокий продуктовый анализ отзывов, вопросов и возвратов на WB.
Карточка каждой активной модели, LLM-кластеризация всех текстов, gap-анализ позиционирования vs восприятия.

Spec: `docs/superpowers/specs/2026-04-07-reviews-audit-v2-design.md`

## Фаза 1: Параметры

Спроси пользователя:

1. **Период анализа:**
   - Последняя неделя
   - Последний месяц
   - Последний квартал
   - Последний год
   - Кастомные даты (YYYY-MM-DD — YYYY-MM-DD)

2. **Фокус** (опционально): конкретная модель или «все»

3. **Кабинет** (опционально): IP / OOO / оба (дефолт — оба)

Вычисли `date_from` и `date_to` на основе выбора.

Определи гранулярность:
- Год → помесячно (12 точек)
- Квартал → помесячно (3 точки)
- Месяц → понедельно (4-5 точек)
- Неделя → подневно (7 точек)

Определи глубину анализа:

| Период | Карточки моделей | LLM-анализ | Gap-анализ |
|--------|-----------------|-----------|-----------|
| Год | Все активные | Все тексты | Да |
| Квартал | Все активные | Все тексты | Да |
| Месяц | Только с алертами + сводная | Все тексты | Только проблемные |
| Неделя | Только алерты | Все тексты | Нет |

## Фаза 2: Сбор данных

Запусти сборщик:

```bash
python3 scripts/reviews_audit/collect_data.py \
  --date-from "{{date_from}}" \
  --date-to "{{date_to}}" \
  --cabinet "{{cabinet}}" \
  --output /tmp/reviews_audit_data.json
```

Проверь exit code. Прочитай `/tmp/reviews_audit_data.json` и выведи сводку:
- Отзывов: N
- Вопросов: N
- Моделей с заказами: N
- Период: date_from — date_to

Если данных мало (<10 отзывов) — предупреди пользователя.

## Фаза 3: Фильтрация и маппинг

### 3.1 Маппинг nmId → товарная матрица

Собери уникальные `nmId` из feedbacks и questions (`productDetails.nmId`).

Используй Supabase MCP (execute_sql):

```sql
SELECT p.nm_id, a.artikul, a.cvet_id, c.name as cvet_name,
       m.name as model_name, mo.name as model_osnova_name,
       mo.id as model_osnova_id
FROM products p
JOIN artikuls a ON a.id = p.artikul_id
JOIN models m ON m.id = a.model_id
JOIN model_osnovas mo ON mo.id = m.model_osnova_id
LEFT JOIN cvets c ON c.id = a.cvet_id
WHERE p.nm_id IN ({{nm_ids}});
```

Если Supabase MCP не авторизован — fallback: маппинг через `productDetails.supplierArticle` (LOWER, SPLIT по '/').

### 3.2 Статусы моделей

Через Supabase MCP:

```sql
SELECT name, status FROM model_osnovas;
```

Модели со статусом, указывающим на вывод, **исключить из анализа**. Записать: «Исключены выводимые модели: X, Y, Z».

Если Supabase MCP не авторизован — спросить пользователя, какие модели исключить.

### 3.3 Группировка

Сгруппируй все отзывы/вопросы по:
- Уровень 1: model_osnova (базовая модель)
- Уровень 2: artikul (модель + цвет)

## Фаза 4: Цифровой анализ

Для каждой **активной** модели посчитай:

### 4.1 Сводная карточка

| Метрика | Формула |
|---------|---------|
| Рейтинг | средневзвешенный по productValuation |
| Зона | >=4.7 целевой / 4.5-4.6 приемлемый / <4.5 плохой |
| 1★/2★/3★/4★/5★ | распределение |
| Нужно 5★ | ceil((4.7 * total - sum_stars) / 0.3) если <4.7 |
| Заказы | из orders_by_model |
| % возвратов | returns / orders * 100 |
| Отзывов / Вопросов | count для модели |

### 4.2 Помесячная динамика

Для каждой модели — таблица по месяцам:
- Рейтинг
- Кол-во отзывов
- % негативных (1-3★)
- % возвратов (из orders_monthly)

### 4.3 Drill-down по артикулам

Если у модели рейтинг <4.5 ИЛИ % возвратов аномально высок → разбить по артикулам из `orders_by_artikul`, найти конкретный артикул/цвет-виновник.

### 4.4 Алерты (только >5 случаев)

- Рейтинг упал >=0.2 за последние 3 месяца
- % возвратов вырос непропорционально к заказам
- Доля негативных выросла >2x между кварталами

Сохрани результаты Фазы 4 для передачи субагентам.

## Фаза 5: LLM-кластеризация текстов

Запусти **субагент-кластеризатор** (Agent tool, general-purpose).

Передай субагенту:
- Все отзывы с текстом (text, pros, cons — хотя бы одно непустое)
- Файл: `/tmp/reviews_audit_data.json`

**Задача субагента:**

1. Прочитай `/tmp/reviews_audit_data.json`
2. Из каждого отзыва с текстом извлеки: модель (из productDetails.supplierArticle), месяц (из createdDate), текст (text + pros + cons), рейтинг
3. Обрабатывай порциями по 200 отзывов. Для каждого определи:
   - Тональность (по ТЕКСТУ, не по звёздам): позитивный / негативный / смешанный / нейтральный
   - Все проблемы (если есть): конкретные формулировки
   - Все преимущества (если есть): конкретные формулировки
4. После всех порций — агрегируй:
   - **Кластеры проблем** (ВСЕ найденные, не топ-3): название, кол-во, % от всех с текстом, помесячная динамика, топ-модели, 3-5 цитат
   - **Кластеры преимуществ** (ВСЕ найденные): аналогично
   - **per_model**: для каждой модели — её проблемы и преимущества с кол-вом и цитатами
5. Сохрани результат в `/tmp/reviews_audit_clusters.json`

**Формат выхода** (`/tmp/reviews_audit_clusters.json`):
```json
{
  "total_with_text": 5675,
  "problems": [{"cluster": "...", "count": N, "pct": N, "monthly": {...}, "top_models": [...], "quotes": [...]}],
  "advantages": [{"cluster": "...", "count": N, "pct": N, "top_models": [...], "quotes": [...]}],
  "per_model": {
    "ruby": {"problems": [...], "advantages": [...]},
    ...
  }
}
```

Дождись завершения субагента. Прочитай `/tmp/reviews_audit_clusters.json`.

## Фаза 6: Продуктовый анализ по моделям

**Для года/квартала:** запусти параллельные субагенты — по одному на каждую активную модель.
**Для месяца:** только модели с алертами.
**Для недели:** пропустить (только алерты из Фазы 4).

Каждый субагент получает (через prompt):
- Метрики модели из Фазы 4 (рейтинг, динамика, возвраты, drill-down)
- Кластеры модели из Фазы 5 (per_model[model])
- Все тексты вопросов по этой модели (из data.json)

**Задача субагента:** сформировать карточку модели:

```
## {Model Name}

### Сводка
Рейтинг: X.XX (зона) | Отзывов: N | Вопросов: N
Заказов: N | Возвратов: X.X% | Тренд: [растёт/стабилен/падает]

### Динамика рейтинга
[таблица по месяцам]

### Распределение звёзд
[1★: N | 2★: N | 3★: N | 4★: N | 5★: N]

### Возвраты
[% по месяцам, drill-down по артикулам если аномалия]

### Что ценят покупатели
[ВСЕ преимущества с частотностью и цитатами]

### Проблемы
[ВСЕ проблемы с частотностью, динамикой, цитатами]

### Анализ вопросов
[о чём спрашивают, частотность]

### Рекомендации
- Производство: ...
- Карточка товара: ...
- Cross-sell: ...
```

Собери карточки всех моделей.

## Фаза 7: Gap-анализ

Прочитай из Notion базу «Модельный ряд»:

Notion-страница: `https://www.notion.so/wookieeshop/WOOKIEE-2f658a2bd58780f7bbc7fab05b0821f0`

Используй `notion-search` или `notion-fetch` для получения «Модельный ряд».
Нужные поля: `Name` (модель), `Позиционирование` (продуктовый смысл).

**Только для моделей с проблемами** сопоставь:
- Задумка (Notion) vs Реальность (отзывы) → Gap → Рекомендация

## Фаза 8: Синтез + публикация

### 8.1 Самопроверка

- [ ] Все цифры с контекстом (% от чего?)
- [ ] Нет алертов на <5 случаях
- [ ] Рекомендации конкретные
- [ ] Динамика учитывает пропорции к заказам
- [ ] Тональность по тексту, не звёздам
- [ ] Выводимые модели исключены
- [ ] Каждая активная модель имеет карточку (для года/квартала)

### 8.2 MD-файл

Сохрани plain markdown в:
```
docs/reports/reviews-audit-{{YYYY-MM-DD}}.md
```

### 8.3 Notion-публикация (через Notion MCP)

Создай страницу в базе «Аналитические отчёты» через Notion MCP.

**Формат — enhanced markdown по образцу Q4 vs Q1 отчёта:**
- `color="blue_bg"` для шапок таблиц
- `color="green_bg"` для целевых значений
- `color="red_bg"` для проблемных значений
- `color="yellow_bg"` для предупреждений
- Callout-блоки с иконками для Executive Summary
- Toggle-секции для карточек моделей
- Горизонтальные разделители

**Структура страницы:**

```
I. Executive Summary (callout-блоки)
II. Сводная таблица моделей (цветная)
III. Карточки моделей (toggle-секции)
IV. Кластеры проблем (таблицы + алерты)
V. Кластеры преимуществ
VI. Gap-анализ
VII. Actionable-рекомендации (по критичности)
VIII. Методология
```

Покажи пользователю:
- Путь к MD-файлу
- URL Notion-страницы
- Краткую сводку (3-5 выводов)

## Принципы (ОБЯЗАТЕЛЬНО)

1. **Доли, а не абсолюты.** Рост возвратов пропорционально заказам = норма.
2. **Текст > звёзды.** 5★ с претензией = негативный.
3. **Пороги значимости.** <5 случаев = шум.
4. **Динамика долей.** 1% → 3% = алерт.
5. **Drill-down.** Модель → артикул → цвет.
6. **Actionable.** Не «улучшите», а «проверить краску Ruby синий, партия Q1 2026».
7. **GROUP BY с LOWER().** Всегда.
8. **Выводимые — не анализировать.**
```

- [ ] **Step 2: Verify skill file exists**

```bash
ls -la /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/.claude/skills/reviews-audit/SKILL.md
head -3 /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/.claude/skills/reviews-audit/SKILL.md
```

Expected: File exists, frontmatter starts with `---` and `name: reviews-audit`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/reviews-audit/SKILL.md
git commit -m "feat(reviews-audit): rewrite SKILL.md v2 — 8 phases, subagents, Notion MCP"
```

---

### Task 5: Update tests and run full suite

**Files:**
- Modify: `tests/test_reviews_audit_collector.py`

- [ ] **Step 1: Clean up test file**

Remove the old `TestCollectData` class (replaced by `TestCollectDataV2` in Task 3). Ensure all test classes are present:
- `TestGetWbBuyoutsReturnsByModel` (from v1)
- `TestGetWbBuyoutsReturnsByArtikul` (Task 1)
- `TestGetWbBuyoutsReturnsMonthly` (Task 2)
- `TestCollectDataV2` (Task 3)
- `TestFilterByDate` (from v1)

Also add a test for `_deduplicate`:

```python
class TestDeduplicate:
    """Tests for _deduplicate helper."""

    def test_removes_duplicates(self):
        from scripts.reviews_audit.collect_data import _deduplicate

        items = [
            {"id": "a", "text": "first"},
            {"id": "a", "text": "dup"},
            {"id": "b", "text": "second"},
        ]
        result = _deduplicate(items, key="id")
        assert len(result) == 2
        assert result[0]["text"] == "first"

    def test_keeps_items_without_key(self):
        from scripts.reviews_audit.collect_data import _deduplicate

        items = [{"text": "no id"}, {"text": "also no id"}]
        result = _deduplicate(items, key="id")
        assert len(result) == 2

    def test_empty_list(self):
        from scripts.reviews_audit.collect_data import _deduplicate
        assert _deduplicate([], key="id") == []
```

- [ ] **Step 2: Run full test suite**

```bash
python3 -m pytest tests/test_reviews_audit_collector.py tests/test_wb_client_chats.py -v --tb=short
```

Expected: All tests PASS.

- [ ] **Step 3: Verify collector CLI**

```bash
python3 scripts/reviews_audit/collect_data.py --help
```

Expected: Shows `--date-from`, `--date-to`, `--cabinet [ip|ooo|both]`, `--output`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_reviews_audit_collector.py
git commit -m "test(reviews-audit): update tests for v2 collector + dedup + new data_layer functions"
```

---

### Task 6: Final verification

**Files:** All files from Tasks 1-5

- [ ] **Step 1: Run full test suite**

```bash
python3 -m pytest tests/test_reviews_audit_collector.py tests/test_wb_client_chats.py -v --tb=short
```

Expected: All tests PASS.

- [ ] **Step 2: Verify SKILL.md frontmatter**

```bash
head -5 /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/.claude/skills/reviews-audit/SKILL.md
```

Expected: Valid YAML frontmatter with `name: reviews-audit`.

- [ ] **Step 3: Verify collector v2 runs with --help**

```bash
python3 scripts/reviews_audit/collect_data.py --help
```

Expected: Shows v2 args including `--cabinet`.

- [ ] **Step 4: Check all commits**

```bash
git log --oneline -6
```

Expected: 5 commits from Tasks 1-5 visible.
