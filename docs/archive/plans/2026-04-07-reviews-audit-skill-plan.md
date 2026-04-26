# Reviews Audit Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `/reviews-audit` Claude Code skill for deep analysis of WB reviews, questions, and chats with brand communication quality assessment.

**Architecture:** SKILL.md orchestrates 7 phases. Python collector script fetches data from WB API + DB → JSON. Claude analyzes text, computes metrics, reads Notion product strategy, synthesizes report, publishes to MD + Notion. Follows the financial-overview skill pattern.

**Tech Stack:** Python (httpx, shared/clients/wb_client.py, shared/data_layer), Supabase MCP, Notion MCP, Claude Code SKILL.md

**Spec:** `docs/superpowers/specs/2026-04-07-reviews-audit-skill-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `shared/clients/wb_client.py` | Modify | Add `get_seller_chats()` method |
| `shared/data_layer/finance.py` | Modify | Add `get_wb_buyouts_returns_by_model()` function |
| `shared/data_layer/__init__.py` | Verify | Confirm new function re-exported via wildcard |
| `scripts/reviews_audit/collect_data.py` | Create | Data collector: WB API + DB → JSON |
| `scripts/reviews_audit/__init__.py` | Create | Package init |
| `.claude/skills/reviews-audit/SKILL.md` | Create | Skill definition with 7-phase workflow |
| `tests/test_reviews_audit_collector.py` | Create | Tests for collector script |
| `tests/test_wb_client_chats.py` | Create | Tests for new WBClient method |

---

### Task 1: Add `get_seller_chats()` to WBClient

**Files:**
- Modify: `shared/clients/wb_client.py`
- Create: `tests/test_wb_client_chats.py`

WBClient currently supports feedbacks and questions but not seller chats. We need to add this method following the existing pattern (pagination via skip/take, retry on 429).

- [ ] **Step 1: Write the failing test**

Create `tests/test_wb_client_chats.py`:

```python
"""Tests for WBClient.get_seller_chats() method."""
import json
from unittest.mock import patch, MagicMock
import pytest

from shared.clients.wb_client import WBClient


@pytest.fixture
def client():
    return WBClient(api_key="test-key", cabinet_name="test")


class TestGetSellerChats:
    """Tests for get_seller_chats method."""

    def test_returns_list(self, client):
        """get_seller_chats should return a list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"chats": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_request", return_value=mock_response):
            result = client.get_seller_chats()
            assert isinstance(result, list)

    def test_returns_chats_from_response(self, client):
        """Should extract chats from API response."""
        chat_data = [
            {
                "chatId": "abc123",
                "createdAt": "2026-01-15T10:00:00Z",
                "messages": [
                    {"text": "Здравствуйте, подскажите размер", "direction": "in"},
                    {"text": "Добрый день! Рекомендуем размер M", "direction": "out"},
                ],
            }
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"chats": chat_data}
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_request", return_value=mock_response):
            result = client.get_seller_chats()
            assert len(result) == 1
            assert result[0]["chatId"] == "abc123"
            assert len(result[0]["messages"]) == 2

    def test_empty_response(self, client):
        """Should return empty list when no chats."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"chats": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_request", return_value=mock_response):
            result = client.get_seller_chats()
            assert result == []

    def test_method_exists(self, client):
        """WBClient should have get_seller_chats method."""
        assert hasattr(client, "get_seller_chats")
        assert callable(client.get_seller_chats)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python -m pytest tests/test_wb_client_chats.py -v
```

Expected: FAIL — `AttributeError: 'WBClient' object has no attribute 'get_seller_chats'`

- [ ] **Step 3: Implement `get_seller_chats()` in WBClient**

Add to `shared/clients/wb_client.py`, after the `get_all_questions()` method:

```python
def get_seller_chats(self, date_from: str | None = None) -> list[dict]:
    """Fetch seller chats from WB API.
    
    Args:
        date_from: ISO date string to filter chats from (e.g. "2026-01-01").
                   If None, fetches all available chats.
    
    Returns:
        List of chat dicts with messages.
    """
    all_chats = []
    offset = 0
    limit = 1000

    while True:
        params = {"offset": offset, "limit": limit}
        if date_from:
            params["dateFrom"] = date_from

        try:
            resp = self._request(
                "GET",
                f"{self.FEEDBACKS_BASE}/api/v1/seller/chats",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"[{self.cabinet_name}] Error fetching seller chats: {e}")
            break

        chats = data.get("chats", [])
        if not chats:
            break

        all_chats.extend(chats)
        logger.info(
            f"[{self.cabinet_name}] Fetched {len(chats)} chats (total: {len(all_chats)})"
        )

        if len(chats) < limit:
            break
        offset += limit
        time.sleep(0.35)

    logger.info(f"[{self.cabinet_name}] Total seller chats fetched: {len(all_chats)}")
    return all_chats
```

Note: `FEEDBACKS_BASE` is already defined in WBClient as `"https://feedbacks-api.wildberries.ru"`. The `_request` method already handles retry logic and 429 backoff. `logger` and `time` are already imported.

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_wb_client_chats.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add shared/clients/wb_client.py tests/test_wb_client_chats.py
git commit -m "feat(wb-client): add get_seller_chats() method for WB Chat API"
```

---

### Task 2: Add buyout/return query to data_layer

**Files:**
- Modify: `shared/data_layer/finance.py`

The data_layer has `get_wb_orders_by_model()` for orders, but no function for buyout/return counts by model. We need this for computing % returns.

- [ ] **Step 1: Write the failing test**

Create test in `tests/test_reviews_audit_collector.py` (we'll add collector tests here too):

```python
"""Tests for reviews audit data collection."""
import pytest
from unittest.mock import patch, MagicMock


class TestGetWbBuyoutsReturnsByModel:
    """Tests for get_wb_buyouts_returns_by_model function."""

    def test_function_exists(self):
        """Function should be importable from data_layer."""
        from shared.data_layer import get_wb_buyouts_returns_by_model
        assert callable(get_wb_buyouts_returns_by_model)

    def test_returns_list(self):
        """Should return a list of tuples."""
        from shared.data_layer import get_wb_buyouts_returns_by_model

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("current", "wendy", 100, 85, 15),
            ("current", "lola", 50, 45, 5),
        ]
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        with patch(
            "shared.data_layer.finance._db_cursor", return_value=mock_cursor
        ):
            result = get_wb_buyouts_returns_by_model(
                "2026-03-01", "2026-02-01", "2026-04-01"
            )
            assert isinstance(result, list)
            assert len(result) == 2
            # period, model, orders_count, buyout_count, return_count
            assert result[0][0] == "current"
            assert result[0][1] == "wendy"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_reviews_audit_collector.py::TestGetWbBuyoutsReturnsByModel -v
```

Expected: FAIL — `ImportError: cannot import name 'get_wb_buyouts_returns_by_model'`

- [ ] **Step 3: Implement the function in `shared/data_layer/finance.py`**

Add after `get_wb_orders_by_model()`:

```python
def get_wb_buyouts_returns_by_model(
    current_start: str, prev_start: str, current_end: str
) -> list[tuple]:
    """Get buyout and return counts by model for WB.

    Uses the orders table to compute:
    - orders_count: total orders
    - buyout_count: orders where isCancel == 0 (not cancelled/returned)
    - return_count: orders where isCancel == 1 (cancelled/returned)

    Args:
        current_start: Start of current period (YYYY-MM-DD)
        prev_start: Start of previous period (YYYY-MM-DD)
        current_end: End of analysis window (YYYY-MM-DD)

    Returns:
        List of (period, model, orders_count, buyout_count, return_count)
    """
    sql = f"""
        SELECT
            CASE WHEN date >= %s THEN 'current' ELSE 'previous' END as period,
            {get_osnova_sql("SPLIT_PART(supplierarticle, '/', 1)")} as model,
            COUNT(*) as orders_count,
            SUM(CASE WHEN iscancel = 0 THEN 1 ELSE 0 END) as buyout_count,
            SUM(CASE WHEN iscancel = 1 THEN 1 ELSE 0 END) as return_count
        FROM orders
        WHERE date >= %s AND date < %s
        GROUP BY 1, 2
        ORDER BY 1, 3 DESC;
    """
    with _db_cursor("wb") as cur:
        cur.execute(sql, (current_start, prev_start, current_end))
        return cur.fetchall()
```

Also add to `__all__` list in the same file:

```python
__all__ = [
    # ... existing exports ...
    "get_wb_buyouts_returns_by_model",
]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_reviews_audit_collector.py::TestGetWbBuyoutsReturnsByModel -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add shared/data_layer/finance.py tests/test_reviews_audit_collector.py
git commit -m "feat(data-layer): add get_wb_buyouts_returns_by_model() for return analysis"
```

---

### Task 3: Create data collector script

**Files:**
- Create: `scripts/reviews_audit/__init__.py`
- Create: `scripts/reviews_audit/collect_data.py`
- Modify: `tests/test_reviews_audit_collector.py`

This script collects all raw data from WB API + DB and saves to JSON for Claude to analyze.

- [ ] **Step 1: Create package init**

Create `scripts/reviews_audit/__init__.py`:

```python
```

(Empty file — just makes it a Python package.)

- [ ] **Step 2: Write the failing test for collector**

Add to `tests/test_reviews_audit_collector.py`:

```python
import json
import os
import tempfile
from datetime import datetime, timedelta


class TestCollectData:
    """Tests for the data collection script."""

    def test_script_importable(self):
        """Collector module should be importable."""
        from scripts.reviews_audit.collect_data import collect_reviews_data
        assert callable(collect_reviews_data)

    def test_output_structure(self):
        """Output JSON should have expected top-level keys."""
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
                    "productDetails": {"nmId": 12345},
                }
            ]
            mock_questions = [
                {
                    "id": "q1",
                    "text": "Какой размер выбрать?",
                    "createdDate": "2026-03-16T10:00:00Z",
                    "answer": {"text": "Рекомендуем M"},
                    "productDetails": {"nmId": 12345},
                }
            ]
            mock_chats = []
            mock_orders = [("current", "wendy", 100, 85, 15)]

            with patch(
                "scripts.reviews_audit.collect_data.WBClient"
            ) as MockClient, patch(
                "scripts.reviews_audit.collect_data.get_wb_buyouts_returns_by_model",
                return_value=mock_orders,
            ):
                instance = MockClient.return_value
                instance.get_all_feedbacks.return_value = mock_feedbacks
                instance.get_all_questions.return_value = mock_questions
                instance.get_seller_chats.return_value = mock_chats

                collect_reviews_data(
                    date_from="2026-03-01",
                    date_to="2026-04-01",
                    output_path=output_path,
                )

            with open(output_path) as f:
                data = json.load(f)

            assert "feedbacks" in data
            assert "questions" in data
            assert "chats" in data
            assert "orders_stats" in data
            assert "metadata" in data
            assert data["metadata"]["date_from"] == "2026-03-01"
            assert data["metadata"]["date_to"] == "2026-04-01"
            assert len(data["feedbacks"]) == 1
            assert len(data["questions"]) == 1
        finally:
            os.unlink(output_path)
```

- [ ] **Step 3: Run test to verify it fails**

```bash
python -m pytest tests/test_reviews_audit_collector.py::TestCollectData -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.reviews_audit.collect_data'`

- [ ] **Step 4: Implement the collector**

Create `scripts/reviews_audit/collect_data.py`:

```python
"""Data collector for reviews audit skill.

Fetches feedbacks, questions, chats from WB API and
orders/buyouts/returns from DB. Saves everything to JSON.

Usage:
    python scripts/reviews_audit/collect_data.py \
        --date-from 2025-04-01 \
        --date-to 2026-04-01 \
        --output /tmp/reviews_audit_data.json
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared.clients.wb_client import WBClient
from shared.config import WB_API_KEY_IP
from shared.data_layer import get_wb_buyouts_returns_by_model

logger = logging.getLogger(__name__)


def _filter_by_date(items: list[dict], date_from: str, date_to: str, date_field: str = "createdDate") -> list[dict]:
    """Filter items by date range."""
    filtered = []
    for item in items:
        created = item.get(date_field, "")
        if not created:
            continue
        # Compare ISO date strings (works for YYYY-MM-DD prefix comparison)
        date_str = created[:10]
        if date_from <= date_str < date_to:
            filtered.append(item)
    return filtered


def collect_reviews_data(
    date_from: str,
    date_to: str,
    output_path: str,
    api_key: str | None = None,
) -> dict:
    """Collect all data for reviews audit.

    Args:
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        output_path: Path to save JSON output
        api_key: WB API key (defaults to WB_API_KEY_IP from config)

    Returns:
        Dict with collected data.
    """
    key = api_key or WB_API_KEY_IP
    client = WBClient(api_key=key, cabinet_name="reviews-audit")

    # 1. Fetch feedbacks
    logger.info("Fetching feedbacks from WB API...")
    all_feedbacks = client.get_all_feedbacks()
    feedbacks = _filter_by_date(all_feedbacks, date_from, date_to)
    logger.info(f"Feedbacks: {len(feedbacks)} in period (of {len(all_feedbacks)} total)")

    # 2. Fetch questions
    logger.info("Fetching questions from WB API...")
    all_questions = client.get_all_questions()
    questions = _filter_by_date(all_questions, date_from, date_to)
    logger.info(f"Questions: {len(questions)} in period (of {len(all_questions)} total)")

    # 3. Fetch seller chats
    logger.info("Fetching seller chats from WB API...")
    all_chats = client.get_seller_chats(date_from=date_from)
    chats = _filter_by_date(all_chats, date_from, date_to, date_field="createdAt")
    logger.info(f"Chats: {len(chats)} in period")

    # 4. Fetch orders/buyouts/returns from DB
    logger.info("Fetching orders/buyouts/returns from DB...")
    try:
        raw_orders = get_wb_buyouts_returns_by_model(
            current_start=date_from,
            prev_start=date_from,  # No previous period comparison needed
            current_end=date_to,
        )
        orders_stats = [
            {
                "period": row[0],
                "model": row[1],
                "orders_count": row[2],
                "buyout_count": row[3],
                "return_count": row[4],
            }
            for row in raw_orders
        ]
    except Exception as e:
        logger.error(f"Failed to fetch orders from DB: {e}")
        orders_stats = []

    # 5. Build output
    result = {
        "metadata": {
            "date_from": date_from,
            "date_to": date_to,
            "collected_at": datetime.now().isoformat(),
            "counts": {
                "feedbacks": len(feedbacks),
                "questions": len(questions),
                "chats": len(chats),
                "models_with_orders": len(orders_stats),
            },
        },
        "feedbacks": feedbacks,
        "questions": questions,
        "chats": chats,
        "orders_stats": orders_stats,
    }

    # 6. Save to JSON
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"Data saved to {output_path}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Collect data for reviews audit")
    parser.add_argument("--date-from", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--date-to", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--output",
        default="/tmp/reviews_audit_data.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    collect_reviews_data(
        date_from=args.date_from,
        date_to=args.date_to,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_reviews_audit_collector.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/reviews_audit/ tests/test_reviews_audit_collector.py
git commit -m "feat(reviews-audit): add data collector script for WB feedbacks/questions/chats"
```

---

### Task 4: Create SKILL.md

**Files:**
- Create: `.claude/skills/reviews-audit/SKILL.md`

This is the main skill file that Claude reads when `/reviews-audit` is invoked. It defines the 7-phase workflow.

- [ ] **Step 1: Create the skill directory**

```bash
mkdir -p /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/.claude/skills/reviews-audit
```

- [ ] **Step 2: Write the SKILL.md**

Create `.claude/skills/reviews-audit/SKILL.md`:

```markdown
---
name: reviews-audit
description: "Глубокий анализ возвратов, отзывов, вопросов и чатов покупателей WB. Оценка коммуникации бренда, кластеризация проблем, gap-анализ позиционирования. Триггеры: reviews-audit, аналитика отзывов, анализ возвратов, аудит отзывов, качество ответов"
---

# Аналитика возвратов и отзывов WOOKIEE (Wildberries)

Глубокий анализ отзывов, вопросов и чатов с покупателями на WB.
Выявление проблемных моделей/артикулов, оценка коммуникации бренда, gap-анализ позиционирования vs восприятия.

Spec: `docs/superpowers/specs/2026-04-07-reviews-audit-skill-design.md`

## Фаза 1: Параметры

Спроси пользователя:

1. **Период анализа:**
   - Последняя неделя
   - Последний месяц
   - Последний квартал
   - Последний год
   - Кастомные даты (YYYY-MM-DD — YYYY-MM-DD)

2. **Фокус** (опционально): конкретная модель или «все»

Вычисли `date_from` и `date_to` на основе выбора.

Определи гранулярность разбивки:
- Год → помесячно (12 точек)
- Квартал → помесячно (3 точки)
- Месяц → понедельно (4-5 точек)
- Неделя → подневно (7 точек)

Сохрани параметры для дальнейших фаз.

## Фаза 2: Сбор данных

Запусти сборщик данных:

```bash
python3 scripts/reviews_audit/collect_data.py \
  --date-from "{{date_from}}" \
  --date-to "{{date_to}}" \
  --output /tmp/reviews_audit_data.json
```

Проверь exit code:
- `0` — успех, продолжай
- Ненулевой — покажи ошибку пользователю, предложи повторить

Прочитай `/tmp/reviews_audit_data.json` и выведи сводку:
- Отзывов: N
- Вопросов: N
- Чатов: N
- Моделей с заказами: N

Если данных мало (<10 отзывов) — предупреди пользователя, что выводы могут быть ненадёжными.

## Фаза 3: Маппинг на товарную матрицу

Для каждого уникального `nmId` из собранных данных определи модель/артикул/цвет.

Используй Supabase MCP (execute_sql):

```sql
SELECT p.nm_id, a.artikul, a.cvet_id, m.name as model_name, mo.name as model_osnova_name
FROM products p
JOIN artikuls a ON a.id = p.artikul_id
JOIN models m ON m.id = a.model_id
JOIN model_osnovas mo ON mo.id = m.model_osnova_id
WHERE p.nm_id IN ({{nm_ids}});
```

Построй маппинг: `nmId → {model_osnova, model, artikul, cvet}`.

Если nmId не найден в матрице — пометь как "неизвестный" и продолжай.

Сгруппируй все отзывы/вопросы/чаты по:
- Уровень 1: model_osnova (базовая модель)
- Уровень 2: artikul (модель + цвет)

## Фаза 4: Цифровой анализ

### 4.1 Метрики по моделям

Для каждой модели посчитай:

| Метрика | Формула |
|---------|---------|
| Заказы (шт) | из orders_stats |
| Выкупы (шт) | из orders_stats |
| Возвраты (шт) | из orders_stats |
| % возвратов | returns / buyouts * 100 |
| Всего отзывов | count feedbacks для модели |
| Средний рейтинг | средневзвешенный по productValuation |
| Зона рейтинга | >=4.7 целевой / 4.5-4.6 приемлемый / <4.5 плохой |

### 4.2 Расчёт «сколько 5★ нужно»

Для моделей с рейтингом <4.7:

```
need_5star = ceil((4.7 * total - sum_stars) / (5 - 4.7))
```

Где `total` = количество отзывов, `sum_stars` = сумма всех оценок.

### 4.3 Динамика

Разбей данные по периодам (адаптивная гранулярность из Фазы 1).
Для каждого подпериода считай те же метрики. Покажи тренд.

### 4.4 Алерты

Алерт срабатывает ТОЛЬКО при статистической значимости (не на единичных случаях):
- Доля проблемной темы выросла >2x между подпериодами
- % возвратов вырос непропорционально к росту заказов
- Рейтинг упал на >=0.2 за период
- Новая тема жалоб появилась (не было → теперь >1%)

**ВАЖНО:** 1 жалоба из 1000 = шум. Не цеплять за единичные случаи.

### 4.5 Drill-down

Если модель в красной зоне (<4.5) или есть алерт → автоматически раскрой до уровня артикула/цвета. Найди конкретного виновника.

## Фаза 5: Текстовый анализ + оценка коммуникации

### 5.1 Анализ текстов

**ВАЖНО: анализируй ТЕКСТ, а не звёзды.** 5★ может быть негативным отзывом, 3★ — позитивным.

Для каждого отзыва/вопроса определи:
- **Тональность** (по тексту): позитивный / нейтральный / негативный / смешанный
- **Кластер проблемы** (если негативный/смешанный):
  - Размерная сетка (маломерит / большемерит)
  - Качество ткани (катышки, растяжение, выцветание)
  - Цвет (не соответствует фото, выцветает при стирке)
  - Упаковка / доставка
  - Посадка / комфорт
  - Соотношение цена/качество
  - Новый кластер (если паттерн повторяется)

**Batch-обработка:** если отзывов >200 — обрабатывай порциями по 100. После каждой порции фиксируй промежуточные результаты (количество по кластерам, примеры цитат). В конце мержи.

Для каждого кластера собери:
- Доля от всех отзывов (%)
- Динамика доли между подпериодами
- Топ-артикулы внутри кластера
- 3-5 показательных цитат

### 5.2 Оценка коммуникации бренда

Для КАЖДОГО отзыва/вопроса с ответом бренда оцени:

| Критерий | Как оцениваем |
|----------|--------------|
| Скорость | Время между createdDate и датой ответа |
| Полнота | Ответ закрывает проблему покупателя? (да/частично/нет) |
| Тон | Эмпатия, профессионализм, без шаблонности (хорошо/средне/плохо) |
| Cross-sell | Есть рекомендация другого артикула/размера? (да/нет) |

Посчитай агрегаты:
- Средняя скорость ответа
- % отзывов/вопросов БЕЗ ответа бренда
- % ответов с хорошей полнотой
- % ответов с cross-sell

### 5.3 Анализ чатов

Для каждого чата определи:
- Закрыл ли бренд боль покупателя
- Была ли отработка возражений/негатива
- Были ли cross-sell рекомендации
- Общая оценка качества поддержки

### 5.4 Рекомендации

По результатам анализа сформируй:
- По каждому кластеру: «как отрабатывать эту боль» (шаблон ответа)
- Cross-sell возможности: «при жалобе на размер рекомендовать артикул X»
- Паттерны для производства: «голубой цвет модели Y — проверить стойкость краски»

## Фаза 6: Продуктовый стратег

Прочитай из Notion базу «Модельный ряд» (через Notion MCP):

Notion-страница: `https://www.notion.so/wookieeshop/WOOKIEE-2f658a2bd58780f7bbc7fab05b0821f0`

Используй `notion-search` или `notion-fetch` для получения базы данных «Модельный ряд».
Нужные поля: `Name` (модель), `Позиционирование` (продуктовый смысл).

### Gap-анализ: задумка vs реальность

Для каждой модели с проблемами из Фаз 4-5:
- **Задумка:** что закладывали (из Notion — поле «Позиционирование»)
- **Реальность:** что говорят покупатели (кластеры и цитаты из Фазы 5)
- **Gap:** конкретное расхождение
- **Рекомендация:** что делать (пересмотреть ткань, скорректировать лекала, обновить карточку)

## Фаза 7: Синтез + публикация

### 7.1 Ревью-цикл (самопроверка)

Перед финализацией проверь:
- [ ] Все цифры имеют контекст (% от чего? из какого периода?)
- [ ] Нет алертов на единичных случаях (<5 случаев = не алерт)
- [ ] Рекомендации конкретные, а не «улучшите качество»
- [ ] Динамика учитывает пропорции к объёму заказов
- [ ] Тональность определена по тексту, а не по звёздам

### 7.2 Формат отчёта

Сформируй отчёт, обязательно включающий:

1. **Executive Summary** — 3-5 ключевых выводов с цифрами
2. **Рейтинговая карта моделей** — таблица: модель / рейтинг / зона / trend / топ-проблема / сколько 5★ нужно
3. **Детальный анализ проблемных моделей** — drill-down до артикула/цвета
4. **Кластеры проблем** — с долями (%), динамикой, цитатами
5. **Оценка коммуникации бренда** — скорость ответа, полнота, tone, % без ответа, cross-sell
6. **Gap-анализ: позиционирование vs восприятие** — по данным из Notion
7. **Actionable рекомендации** — ранжированные по критичности, с «что если» сценариями
8. **Расчёт: сколько 5★ нужно** — для моделей в красной/жёлтой зоне, план действий

### 7.3 Публикация

1. Сохрани MD-отчёт:
   ```
   docs/reports/reviews-audit-{{YYYY-MM-DD}}.md
   ```

2. Опубликуй в Notion:
   ```bash
   python3 -c "
   from scripts.notion_sync import sync_report_to_notion
   sync_report_to_notion(
       start_date='{{date_from}}',
       end_date='{{date_to}}',
       report_md=open('docs/reports/reviews-audit-{{YYYY-MM-DD}}.md').read(),
       source='reviews-audit',
       title='Аудит отзывов {{date_from}} — {{date_to}}'
   )
   "
   ```

3. Покажи пользователю:
   - Путь к MD-файлу
   - URL Notion-страницы
   - Краткую сводку ключевых выводов

## Принципы (ОБЯЗАТЕЛЬНО соблюдать)

1. **Доли, а не абсолюты.** Все метрики относительные. Рост возвратов пропорционально заказам = норма.
2. **Текст > звёзды.** 5★ с претензией = негативный. 3★ с похвалой = позитивный.
3. **Пороги значимости.** 1 жалоба из 1000 = шум. Не алертить.
4. **Динамика долей.** Было 1% → стало 3% = алерт. Было 1% → осталось 1% = норма.
5. **Drill-down при проблеме.** Модель → артикул → цвет. Найти виновника.
6. **Actionable.** Не «улучшите качество», а «проверить стойкость краски голубого Wendy».
7. **GROUP BY с LOWER().** При группировке по артикулам/моделям — всегда LOWER().
```

- [ ] **Step 3: Verify skill is discoverable**

```bash
ls -la /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/.claude/skills/reviews-audit/SKILL.md
```

Expected: File exists with correct permissions.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/reviews-audit/SKILL.md
git commit -m "feat(reviews-audit): add skill definition with 7-phase workflow"
```

---

### Task 5: Integration test — dry run validation

**Files:**
- Modify: `tests/test_reviews_audit_collector.py`

Add integration-level tests to validate the full collector flow.

- [ ] **Step 1: Add integration test for date filtering**

Add to `tests/test_reviews_audit_collector.py`:

```python
class TestFilterByDate:
    """Tests for _filter_by_date helper."""

    def test_filters_within_range(self):
        from scripts.reviews_audit.collect_data import _filter_by_date

        items = [
            {"createdDate": "2026-01-15T10:00:00Z"},
            {"createdDate": "2026-02-15T10:00:00Z"},
            {"createdDate": "2026-03-15T10:00:00Z"},
            {"createdDate": "2026-04-15T10:00:00Z"},
        ]
        result = _filter_by_date(items, "2026-02-01", "2026-04-01")
        assert len(result) == 2
        assert result[0]["createdDate"].startswith("2026-02")
        assert result[1]["createdDate"].startswith("2026-03")

    def test_empty_input(self):
        from scripts.reviews_audit.collect_data import _filter_by_date
        assert _filter_by_date([], "2026-01-01", "2026-12-31") == []

    def test_no_matches(self):
        from scripts.reviews_audit.collect_data import _filter_by_date

        items = [{"createdDate": "2025-01-01T10:00:00Z"}]
        result = _filter_by_date(items, "2026-01-01", "2026-12-31")
        assert result == []

    def test_custom_date_field(self):
        from scripts.reviews_audit.collect_data import _filter_by_date

        items = [{"createdAt": "2026-03-15T10:00:00Z"}]
        result = _filter_by_date(items, "2026-03-01", "2026-04-01", date_field="createdAt")
        assert len(result) == 1

    def test_missing_date_field_skipped(self):
        from scripts.reviews_audit.collect_data import _filter_by_date

        items = [{"text": "no date here"}]
        result = _filter_by_date(items, "2026-01-01", "2026-12-31")
        assert result == []
```

- [ ] **Step 2: Run all tests**

```bash
python -m pytest tests/test_reviews_audit_collector.py tests/test_wb_client_chats.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_reviews_audit_collector.py
git commit -m "test(reviews-audit): add date filtering tests for collector"
```

---

### Task 6: Final verification and cleanup

**Files:**
- All files from previous tasks

- [ ] **Step 1: Run full test suite**

```bash
python -m pytest tests/test_reviews_audit_collector.py tests/test_wb_client_chats.py -v --tb=short
```

Expected: All tests PASS.

- [ ] **Step 2: Verify SKILL.md syntax**

```bash
head -5 /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee/.claude/skills/reviews-audit/SKILL.md
```

Expected: Valid YAML frontmatter with `name: reviews-audit`.

- [ ] **Step 3: Verify collector runs with --help**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python3 scripts/reviews_audit/collect_data.py --help
```

Expected: Shows usage with `--date-from`, `--date-to`, `--output` args.

- [ ] **Step 4: Final commit with all files**

```bash
git status
# Ensure no unstaged changes remain
git log --oneline -5
```

Expected: 4 commits from Tasks 1-5 visible.
