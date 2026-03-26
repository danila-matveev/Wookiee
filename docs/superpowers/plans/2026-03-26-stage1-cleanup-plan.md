# Stage 1: Cleanup & Consolidation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove dead code, consolidate NotionService and config duplicates, ensure `python -m agents.v3` is the clean single entry point.

**Architecture:** Surgical deletion of unused files + creation of `shared/notion_client.py` merging V2 and V3 Notion implementations + migration of remaining V2 config imports to V3 config.

**Tech Stack:** Python 3.11, httpx, asyncio

---

## File Structure

| Action | File | Responsibility |
|---|---|---|
| **Create** | `shared/notion_client.py` | Unified Notion API client (merged V2 + V3) |
| **Modify** | `agents/v3/delivery/router.py` | Switch import to shared NotionClient |
| **Modify** | `agents/v3/delivery/__init__.py` | Switch re-export to shared NotionClient |
| **Modify** | `agents/v3/prompt_tuner.py` | Switch import to shared NotionClient |
| **Modify** | `agents/finolog_categorizer/app.py` | Switch import to shared NotionClient |
| **Modify** | `agents/finolog_categorizer/notion_publisher.py` | Switch import to shared NotionClient |
| **Modify** | `agents/finolog_categorizer/feedback_reader.py` | Switch import to shared NotionClient |
| **Modify** | `agents/finolog_categorizer/scanner.py` | Switch import to shared NotionClient |
| **Modify** | `scripts/run_price_analysis.py` | Switch import to shared NotionClient |
| **Modify** | `agents/v3/config.py` | Add `get_wb_clients()`, `get_ozon_clients()` |
| **Modify** | `agents/oleg/services/price_tools.py` | Switch config import from oleg → v3 |
| **Delete** | `scripts/manual_report.py` | Dead — replaced by test_v2_bridge.py |
| **Delete** | `scripts/rebuild_reports.py` | Dead — not used |
| **Delete** | `agents/oleg/bot/` (entire dir) | Dead — V2 Telegram bot replaced by V3 app.py |
| **Delete** | `agents/oleg/pipeline/` (entire dir) | Dead — V2 gates replaced by v3/gates.py |
| **Delete** | `agents/oleg/check_scheduler.py` | Dead — V2 utility |
| **Delete** | `agents/oleg/mcp_server.py` | Dead — V2 MCP server not running |
| **Delete** | `agents/oleg/agents/researcher/` (entire dir) | Dead — not called at max_chain_steps=1 |
| **Delete** | `agents/oleg/agents/quality/` (entire dir) | Dead — not in chain |
| **Delete** | `agents/oleg/agents/christina/` (entire dir) | Dead — not in chain |
| **Delete** | `agents/oleg/agents/seo/` (entire dir) | Dead — funnel disabled |
| **Delete** | `agents/oleg/christina_playbook.md` | Dead — agent removed |
| **Delete** | `agents/oleg/seo_playbook.md` | Dead — agent removed |
| **Delete** | `agents/oleg/config.py` | Duplicate — all values exist in v3/config.py |
| **Delete** | `agents/oleg/services/notion_service.py` | Duplicate — merged into shared/notion_client.py |
| **Delete** | `agents/v3/delivery/notion.py` | Duplicate — merged into shared/notion_client.py |
| **Delete** | `tests/oleg/test_formatter.py` | Tests deleted code (bot/formatter.py) |
| **Delete** | `tests/oleg/test_gate_checker.py` | Tests deleted code (pipeline/gate_checker.py) |
| **Delete** | `tests/oleg/test_report_pipeline.py` | Tests deleted code (pipeline/report_pipeline.py) |
| **Delete** | `tests/oleg/test_scheduler.py` | Tests deleted V2 scheduler |
| **Preserve** | `agents/oleg/agents/reporter/` | Active — V2 reporter prompts (best quality) |
| **Preserve** | `agents/oleg/agents/advisor/` | Active — V2 advisor prompts |
| **Preserve** | `agents/oleg/agents/validator/` | Active — V2 validator prompts |
| **Preserve** | `agents/oleg/agents/marketer/` | Active — V2 marketer prompts |
| **Preserve** | `agents/oleg/orchestrator/` | Active — V2 engine core |
| **Preserve** | `agents/oleg/executor/` | Active — ReAct loop |
| **Preserve** | `agents/oleg/services/agent_tools.py` | Active — SQL tools for agents |
| **Preserve** | `agents/oleg/services/price_tools.py` | Active — price analysis tools |
| **Preserve** | `agents/oleg/services/marketing_tools.py` | Active — marketing tools |
| **Preserve** | `agents/oleg/services/funnel_tools.py` | Active — funnel tools |
| **Preserve** | `agents/oleg/services/price_analysis/` | Active — price analysis engine |
| **Preserve** | `agents/oleg/playbook.md` | Active — reporter playbook (119KB) |
| **Preserve** | `agents/oleg/marketing_playbook.md` | Active — marketer playbook (18KB) |

---

### Task 1: Delete dead scripts

**Files:**
- Delete: `scripts/manual_report.py`
- Delete: `scripts/rebuild_reports.py`

- [ ] **Step 1: Delete the files**

```bash
rm scripts/manual_report.py scripts/rebuild_reports.py
```

- [ ] **Step 2: Verify no remaining imports**

```bash
grep -r "manual_report\|rebuild_reports" scripts/ agents/ --include="*.py" -l
```

Expected: no results (or only this plan file)

- [ ] **Step 3: Commit**

```bash
git add scripts/manual_report.py scripts/rebuild_reports.py
git commit -m "chore: delete dead scripts manual_report.py and rebuild_reports.py"
```

---

### Task 2: Delete V2 bot, pipeline, and unused agents

**Files:**
- Delete: `agents/oleg/bot/` (entire directory)
- Delete: `agents/oleg/pipeline/` (entire directory)
- Delete: `agents/oleg/agents/researcher/` (entire directory)
- Delete: `agents/oleg/agents/quality/` (entire directory)
- Delete: `agents/oleg/agents/christina/` (entire directory)
- Delete: `agents/oleg/agents/seo/` (entire directory)
- Delete: `agents/oleg/check_scheduler.py`
- Delete: `agents/oleg/mcp_server.py`
- Delete: `agents/oleg/christina_playbook.md`
- Delete: `agents/oleg/seo_playbook.md`
- Delete: `tests/oleg/test_formatter.py`
- Delete: `tests/oleg/test_gate_checker.py`
- Delete: `tests/oleg/test_report_pipeline.py`
- Delete: `tests/oleg/test_scheduler.py`

- [ ] **Step 1: Delete all V2 bot and pipeline directories**

```bash
rm -rf agents/oleg/bot agents/oleg/pipeline
```

- [ ] **Step 2: Delete unused agent directories**

```bash
rm -rf agents/oleg/agents/researcher agents/oleg/agents/quality agents/oleg/agents/christina agents/oleg/agents/seo
```

- [ ] **Step 3: Delete V2 standalone files**

```bash
rm agents/oleg/check_scheduler.py agents/oleg/mcp_server.py
rm agents/oleg/christina_playbook.md agents/oleg/seo_playbook.md
```

- [ ] **Step 4: Delete orphaned tests**

```bash
rm tests/oleg/test_formatter.py tests/oleg/test_gate_checker.py tests/oleg/test_report_pipeline.py tests/oleg/test_scheduler.py
```

- [ ] **Step 5: Verify V2 engine still imports cleanly**

```bash
python -c "
from agents.oleg.orchestrator.orchestrator import OlegOrchestrator
from agents.oleg.executor.react_loop import execute_react_loop
from agents.oleg.agents.reporter.agent import ReporterAgent
from agents.oleg.agents.advisor.agent import AdvisorAgent
from agents.oleg.agents.validator.agent import ValidatorAgent
from agents.oleg.agents.marketer.agent import MarketerAgent
from agents.oleg.services.agent_tools import TOOL_DEFINITIONS
from agents.oleg.services.price_tools import PRICE_TOOL_DEFINITIONS
print('V2 engine imports OK')
"
```

Expected: `V2 engine imports OK`

- [ ] **Step 6: Commit**

```bash
git add -A agents/oleg/bot agents/oleg/pipeline agents/oleg/agents/researcher agents/oleg/agents/quality agents/oleg/agents/christina agents/oleg/agents/seo agents/oleg/check_scheduler.py agents/oleg/mcp_server.py agents/oleg/christina_playbook.md agents/oleg/seo_playbook.md tests/oleg/test_formatter.py tests/oleg/test_gate_checker.py tests/oleg/test_report_pipeline.py tests/oleg/test_scheduler.py
git commit -m "chore: delete V2 dead code — bot, pipeline, unused agents, orphaned tests"
```

---

### Task 3: Create shared/notion_client.py

**Files:**
- Create: `shared/notion_client.py`

This merges V3 `agents/v3/delivery/notion.py` (concurrency locks, full type map) with V2's public `get_comments()`.

- [ ] **Step 1: Create shared/notion_client.py**

```python
"""
Unified Notion client for Wookiee.

Merges agents/oleg/services/notion_service.py (V2) and
agents/v3/delivery/notion.py (V3) into a single implementation.

Features:
- Per-report-type concurrency locks (from V3)
- Full report type map with 29 entries (from V3)
- Public get_comments() method (from V2, needed by finolog_categorizer)
- Upsert by period + type (shared)
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

from shared.notion_blocks import md_to_notion_blocks, remove_empty_sections

logger = logging.getLogger(__name__)

API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

_MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}

_REPORT_TYPE_MAP: dict[str, tuple[str, str]] = {
    "daily":              ("Ежедневный фин анализ",     "Ежедневный фин анализ"),
    "daily_report":       ("Ежедневный фин анализ",     "Ежедневный фин анализ"),
    "weekly":             ("Еженедельный фин анализ",   "Еженедельный фин анализ"),
    "weekly_report":      ("Еженедельный фин анализ",   "Еженедельный фин анализ"),
    "monthly":            ("Ежемесячный фин анализ",    "Ежемесячный фин анализ"),
    "monthly_report":     ("Ежемесячный фин анализ",    "Ежемесячный фин анализ"),
    "custom":             ("Фин анализ",                "Фин анализ"),
    "marketing_daily":    ("Маркетинговый анализ",      "Ежедневный маркетинговый анализ"),
    "marketing_weekly":   ("Маркетинговый анализ",      "Еженедельный маркетинговый анализ"),
    "marketing_monthly":  ("Маркетинговый анализ",      "Ежемесячный маркетинговый анализ"),
    "marketing_custom":   ("Маркетинговый анализ",      "Маркетинговый анализ"),
    "price_analysis":        ("Ценовой анализ",         "Ценовой анализ"),
    "Ценовой анализ":        ("Ценовой анализ",        "Ценовой анализ"),
    "price_weekly":          ("Ценовой анализ",        "Еженедельный ценовой анализ"),
    "price_monthly":         ("Ценовой анализ",        "Ценовой анализ"),
    "finolog_weekly":        ("Еженедельная сводка ДДС", "Сводка ДДС"),
    "funnel_weekly":         ("funnel_weekly", "Воронка WB (сводный)"),
    "localization_weekly":        ("Анализ логистических расходов", "Анализ логистических расходов"),
    "localization_weekly_report": ("Анализ логистических расходов", "Анализ логистических расходов"),
    "Регрессионный анализ":      ("Регрессионный анализ", "Регрессионный анализ"),
    "Анализ акций":              ("Анализ акций", "Анализ акций"),
    "finolog_categorization":    ("Категоризация операций", "Категоризация операций"),
}


def _format_date_range_ru(start_date: str, end_date: str) -> str:
    """Format date range in Russian: '16-22 февраля 2026' or '28 января — 3 февраля 2026'."""
    try:
        sy, sm, sd = start_date.split("-")
        ey, em, ed = end_date.split("-")
        s_day, s_month, s_year = int(sd), int(sm), int(sy)
        e_day, e_month, e_year = int(ed), int(em), int(ey)

        if start_date == end_date:
            return f"{s_day} {_MONTHS_RU[s_month]} {s_year}"
        elif s_year == e_year and s_month == e_month:
            return f"{s_day}-{e_day} {_MONTHS_RU[s_month]} {s_year}"
        elif s_year == e_year:
            return f"{s_day} {_MONTHS_RU[s_month]} \u2014 {e_day} {_MONTHS_RU[e_month]} {s_year}"
        else:
            return f"{s_day} {_MONTHS_RU[s_month]} {s_year} \u2014 {e_day} {_MONTHS_RU[e_month]} {e_year}"
    except (ValueError, KeyError):
        return f"{start_date} \u2014 {end_date}"


class NotionClient:
    """Unified Notion client — sync reports, comments, feedback."""

    def __init__(self, token: str, database_id: str):
        self.token = token
        self.database_id = database_id
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, report_type: str) -> asyncio.Lock:
        if report_type not in self._locks:
            self._locks[report_type] = asyncio.Lock()
        return self._locks[report_type]

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.database_id)

    async def _request(self, method: str, endpoint: str, payload: dict = None) -> dict:
        url = f"{API_BASE}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.request(method, url, headers=headers, json=payload)
            if resp.status_code >= 400:
                logger.error(f"Notion API {resp.status_code}: {resp.text[:500]}")
                resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def sync_report(
        self,
        start_date: str,
        end_date: str,
        report_md: str,
        *,
        report_type: str = "daily",
        source: str = "Oleg v3 (auto)",
        chain_steps: int = 1,
    ) -> Optional[str]:
        """Sync a report to Notion (upsert by period + type).

        Returns Notion page URL or None on failure.
        """
        if not self.enabled:
            logger.warning("Notion not configured, skipping sync")
            return None

        async with self._get_lock(report_type):
            try:
                _map = _REPORT_TYPE_MAP.get(report_type)
                if _map:
                    notion_label, title_prefix = _map
                else:
                    notion_label, title_prefix = report_type, report_type

                title = f"{title_prefix} за {_format_date_range_ru(start_date, end_date)}"
                report_type = notion_label

                report_md = remove_empty_sections(report_md)
                blocks = md_to_notion_blocks(report_md)

                existing = await self._find_existing_page(start_date, end_date, report_type)

                if existing:
                    page_id = existing["id"]
                    page_url = existing["url"]
                    logger.info(f"Notion: updating existing page {page_id}")

                    await self._delete_page_content(page_id)

                    properties = {
                        "Name": {"title": [{"text": {"content": title}}]},
                        "Статус": {"select": {"name": "Актуальный"}},
                    }
                    if source:
                        properties["Источник"] = {"select": {"name": source}}
                    if report_type:
                        properties["Тип анализа"] = {"select": {"name": report_type}}

                    await self._request("PATCH", f"pages/{page_id}", {"properties": properties})
                    await self._append_blocks(page_id, blocks)

                    logger.info(f"Notion: page updated \u2014 {page_url}")
                    return page_url
                else:
                    logger.info(f"Notion: creating new page for {start_date} \u2014 {end_date}")

                    properties = {
                        "Name": {"title": [{"text": {"content": title}}]},
                        "Период начала": {"date": {"start": start_date}},
                        "Период конца": {"date": {"start": end_date}},
                        "Статус": {"select": {"name": "Актуальный"}},
                    }
                    if source:
                        properties["Источник"] = {"select": {"name": source}}
                    if report_type:
                        properties["Тип анализа"] = {"select": {"name": report_type}}

                    page_payload = {
                        "parent": {"database_id": self.database_id},
                        "properties": properties,
                        "children": blocks[:100],
                    }

                    result = await self._request("POST", "pages", page_payload)
                    page_id = result["id"]
                    page_url = result["url"]

                    if len(blocks) > 100:
                        await self._append_blocks(page_id, blocks[100:])

                    logger.info(f"Notion: page created \u2014 {page_url}")
                    return page_url

            except Exception as e:
                logger.error(f"Notion sync failed: {e}")
                return None

    async def get_comments(self, page_id: str) -> list[dict]:
        """Fetch all comments on a Notion page (paginated).

        Returns list of {"id": ..., "text": "...", "created_time": "..."}.
        """
        if not self.token:
            return []

        comments: list[dict] = []
        start_cursor = None
        try:
            while True:
                endpoint = f"comments?block_id={page_id}&page_size=100"
                if start_cursor:
                    endpoint += f"&start_cursor={start_cursor}"
                result = await self._request("GET", endpoint)
                for c in result.get("results", []):
                    text_parts = []
                    for rt in c.get("rich_text", []):
                        text_parts.append(rt.get("plain_text", ""))
                    comments.append({
                        "id": c.get("id", ""),
                        "text": "".join(text_parts),
                        "created_time": c.get("created_time", ""),
                    })
                if not result.get("has_more"):
                    break
                start_cursor = result.get("next_cursor")
        except Exception as e:
            logger.warning(f"Failed to fetch comments for page {page_id}: {e}")
        return comments

    async def add_comment(self, page_id: str, text: str) -> None:
        """Post a comment on a Notion page."""
        if not self.enabled:
            return
        payload = {
            "parent": {"page_id": page_id},
            "rich_text": [{"type": "text", "text": {"content": text[:2000]}}],
        }
        try:
            await self._request("POST", "comments", payload)
        except Exception as e:
            logger.warning("Failed to add comment to %s: %s", page_id, e)

    async def get_recent_feedback(self, days: int = 7) -> list[dict]:
        """Fetch comments from report pages created in the last N days.

        Returns list of {page_title, page_url, page_id, report_type, comments}.
        Only returns pages that actually have comments.
        """
        if not self.enabled:
            return []

        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        try:
            result = await self._request("POST", f"databases/{self.database_id}/query", {
                "filter": {
                    "property": "Период начала",
                    "date": {"on_or_after": since},
                },
                "sorts": [{"property": "Период начала", "direction": "descending"}],
                "page_size": 20,
            })
        except Exception as e:
            logger.warning(f"Failed to query recent pages: {e}")
            return []

        feedback = []
        for page in result.get("results", []):
            page_id = page["id"]
            page_url = page.get("url", "")

            title_prop = page.get("properties", {}).get("Name", {})
            title_parts = title_prop.get("title", [])
            title = "".join(t.get("plain_text", "") for t in title_parts)

            type_prop = page.get("properties", {}).get("Тип анализа", {})
            type_select = type_prop.get("select", {})
            rtype = type_select.get("name", "") if type_select else ""

            comments = await self.get_comments(page_id)
            if comments:
                feedback.append({
                    "page_title": title,
                    "page_url": page_url,
                    "page_id": page_id,
                    "report_type": rtype,
                    "comments": comments,
                })

        return feedback

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _find_existing_page(
        self, start_date: str, end_date: str, report_type: str = None,
    ) -> Optional[dict]:
        conditions = [
            {"property": "Период начала", "date": {"equals": start_date}},
            {"property": "Период конца", "date": {"equals": end_date}},
        ]
        if report_type:
            conditions.append({"property": "Тип анализа", "select": {"equals": report_type}})
        payload = {"filter": {"and": conditions}}
        try:
            result = await self._request("POST", f"databases/{self.database_id}/query", payload)
            pages = result.get("results", [])
            return pages[0] if pages else None
        except Exception:
            if report_type:
                logger.info("Notion: retrying search without report_type filter (option may not exist yet)")
                return await self._find_existing_page(start_date, end_date, report_type=None)
            raise

    async def _delete_page_content(self, page_id: str) -> None:
        while True:
            result = await self._request("GET", f"blocks/{page_id}/children?page_size=100")
            blocks = result.get("results", [])
            if not blocks:
                break
            logger.info(f"Notion: deleting {len(blocks)} blocks from page {page_id}")
            for block in blocks:
                await self._request("DELETE", f"blocks/{block['id']}")
            if not result.get("has_more"):
                break

    async def _append_blocks(self, page_id: str, blocks: list) -> None:
        for i in range(0, len(blocks), 100):
            batch = blocks[i:i + 100]
            await self._request("PATCH", f"blocks/{page_id}/children", {"children": batch})


# Backward-compatible aliases
NotionService = NotionClient
NotionDelivery = NotionClient
```

- [ ] **Step 2: Verify the new module imports**

```bash
python -c "from shared.notion_client import NotionClient, NotionService, NotionDelivery; print('shared/notion_client.py OK')"
```

Expected: `shared/notion_client.py OK`

- [ ] **Step 3: Commit**

```bash
git add shared/notion_client.py
git commit -m "feat: create shared/notion_client.py — unified Notion client"
```

---

### Task 4: Migrate all NotionService/NotionDelivery imports

**Files:**
- Modify: `agents/v3/delivery/router.py` — line 10
- Modify: `agents/v3/delivery/__init__.py` — line 5
- Modify: `agents/v3/prompt_tuner.py` — line 42
- Modify: `agents/finolog_categorizer/app.py` — find NotionService import
- Modify: `agents/finolog_categorizer/notion_publisher.py` — find NotionService import
- Modify: `agents/finolog_categorizer/feedback_reader.py` — find NotionService import
- Modify: `agents/finolog_categorizer/scanner.py` — line 6 (imports NotionService)
- Modify: `scripts/run_price_analysis.py` — find NotionDelivery import

- [ ] **Step 1: Update agents/v3/delivery/router.py**

Change line 10:
```python
# Before:
from .notion import NotionDelivery
# After:
from shared.notion_client import NotionClient as NotionDelivery
```

- [ ] **Step 2: Update agents/v3/delivery/__init__.py**

Replace entire file:
```python
"""Wookiee v3 delivery layer — Telegram + Notion adapters + router."""

from .router import deliver
from .telegram import send_report, format_report_message
from shared.notion_client import NotionClient as NotionDelivery

__all__ = ["deliver", "send_report", "format_report_message", "NotionDelivery"]
```

- [ ] **Step 3: Update agents/v3/prompt_tuner.py**

Change the lazy import inside `_get_notion()` (around line 42):
```python
# Before:
from agents.v3.delivery.notion import NotionDelivery
# After:
from shared.notion_client import NotionClient as NotionDelivery
```

- [ ] **Step 4: Update agents/finolog_categorizer/app.py**

Change NotionService import:
```python
# Before:
from agents.oleg.services.notion_service import NotionService
# After:
from shared.notion_client import NotionClient as NotionService
```

- [ ] **Step 5: Update agents/finolog_categorizer/notion_publisher.py**

Change NotionService import:
```python
# Before:
from agents.oleg.services.notion_service import NotionService
# After:
from shared.notion_client import NotionClient as NotionService
```

- [ ] **Step 6: Update agents/finolog_categorizer/feedback_reader.py**

Change NotionService import:
```python
# Before:
from agents.oleg.services.notion_service import NotionService
# After:
from shared.notion_client import NotionClient as NotionService
```

- [ ] **Step 7: Update agents/finolog_categorizer/scanner.py**

Change line 6:
```python
# Before:
from agents.oleg.services.notion_service import NotionService
# After:
from shared.notion_client import NotionClient as NotionService
```

- [ ] **Step 8: Update scripts/run_price_analysis.py**

Change the NotionDelivery import:
```python
# Before:
from agents.v3.delivery.notion import NotionDelivery as NotionService
# After:
from shared.notion_client import NotionClient as NotionService
```

- [ ] **Step 9: Verify all imports work**

```bash
python -c "
from agents.v3.delivery import deliver, NotionDelivery
from agents.finolog_categorizer.scanner import CategorizerScanner
print('All Notion imports OK')
"
```

Expected: `All Notion imports OK` (or import error from unrelated missing dep — finolog may need finolog_service)

- [ ] **Step 10: Commit**

```bash
git add agents/v3/delivery/router.py agents/v3/delivery/__init__.py agents/v3/prompt_tuner.py agents/finolog_categorizer/app.py agents/finolog_categorizer/notion_publisher.py agents/finolog_categorizer/feedback_reader.py agents/finolog_categorizer/scanner.py scripts/run_price_analysis.py
git commit -m "refactor: migrate all Notion imports to shared/notion_client.py"
```

---

### Task 5: Delete old Notion implementations

**Files:**
- Delete: `agents/oleg/services/notion_service.py`
- Delete: `agents/v3/delivery/notion.py`

- [ ] **Step 1: Delete old files**

```bash
rm agents/oleg/services/notion_service.py agents/v3/delivery/notion.py
```

- [ ] **Step 2: Verify no remaining imports of old paths**

```bash
grep -r "from agents.oleg.services.notion_service\|from agents.v3.delivery.notion\|from .notion import" agents/ scripts/ --include="*.py"
```

Expected: no results

- [ ] **Step 3: Commit**

```bash
git add agents/oleg/services/notion_service.py agents/v3/delivery/notion.py
git commit -m "chore: delete old NotionService/NotionDelivery — replaced by shared/notion_client.py"
```

---

### Task 6: Migrate oleg/config.py → v3/config.py

**Files:**
- Modify: `agents/v3/config.py` — add `get_wb_clients()` and `get_ozon_clients()`
- Modify: `agents/oleg/services/price_tools.py` — line 639: change import
- Delete: `agents/oleg/config.py`

- [ ] **Step 1: Add marketplace client helpers to v3/config.py**

Add at the end of `agents/v3/config.py` (before any existing closing comment):

```python
# ── Marketplace API clients ───────────────────────────────────────────────────

def get_wb_clients() -> dict:
    """Return dict {cabinet_name: WBClient} for all configured cabinets."""
    from shared.clients.wb_client import WBClient
    clients = {}
    wb_ip = os.getenv("WB_API_KEY_IP", "")
    wb_ooo = os.getenv("WB_API_KEY_OOO", "")
    if wb_ip:
        clients["IP"] = WBClient(api_key=wb_ip, cabinet_name="IP")
    if wb_ooo:
        clients["OOO"] = WBClient(api_key=wb_ooo, cabinet_name="OOO")
    return clients


def get_ozon_clients() -> dict:
    """Return dict {cabinet_name: OzonClient} for all configured cabinets."""
    from shared.clients.ozon_client import OzonClient
    clients = {}
    ozon_id_ip = os.getenv("OZON_CLIENT_ID_IP", "")
    ozon_key_ip = os.getenv("OZON_API_KEY_IP", "")
    ozon_id_ooo = os.getenv("OZON_CLIENT_ID_OOO", "")
    ozon_key_ooo = os.getenv("OZON_API_KEY_OOO", "")
    if ozon_id_ip and ozon_key_ip:
        clients["IP"] = OzonClient(client_id=ozon_id_ip, api_key=ozon_key_ip, cabinet_name="IP")
    if ozon_id_ooo and ozon_key_ooo:
        clients["OOO"] = OzonClient(client_id=ozon_id_ooo, api_key=ozon_key_ooo, cabinet_name="OOO")
    return clients
```

- [ ] **Step 2: Update price_tools.py import**

In `agents/oleg/services/price_tools.py`, change line 639:

```python
# Before:
from agents.oleg import config
# After:
from agents.v3 import config
```

- [ ] **Step 3: Verify price_tools imports work**

```bash
python -c "
from agents.oleg.services.price_tools import PRICE_TOOL_DEFINITIONS
print(f'price_tools OK: {len(PRICE_TOOL_DEFINITIONS)} tools')
"
```

Expected: `price_tools OK: N tools`

- [ ] **Step 4: Check no other files import oleg/config**

```bash
grep -r "from agents.oleg import config\|from agents.oleg.config import\|agents\.oleg\.config" agents/ scripts/ tests/ services/ --include="*.py" -l
```

Expected: no results (all importers were deleted in Tasks 1-2 or migrated here)

- [ ] **Step 5: Delete oleg/config.py**

```bash
rm agents/oleg/config.py
```

- [ ] **Step 6: Commit**

```bash
git add agents/v3/config.py agents/oleg/services/price_tools.py agents/oleg/config.py
git commit -m "refactor: consolidate config — migrate get_wb/ozon_clients to v3, delete oleg/config.py"
```

---

### Task 7: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Import check — all critical modules**

```bash
python -c "
from agents.v3 import orchestrator, config, scheduler
from agents.v3.delivery.router import deliver
from agents.v3.delivery import NotionDelivery
from agents.v3.conductor.conductor import ConductorOrchestrator
from shared.notion_client import NotionClient
from agents.oleg.orchestrator.orchestrator import OlegOrchestrator
from agents.oleg.services.agent_tools import TOOL_DEFINITIONS
from agents.oleg.services.price_tools import PRICE_TOOL_DEFINITIONS
from agents.oleg.services.marketing_tools import MARKETING_TOOL_DEFINITIONS
from agents.oleg.agents.reporter.agent import ReporterAgent
from agents.oleg.agents.advisor.agent import AdvisorAgent
from agents.oleg.agents.validator.agent import ValidatorAgent
from agents.oleg.agents.marketer.agent import MarketerAgent
print('=== ALL IMPORTS OK ===')
"
```

Expected: `=== ALL IMPORTS OK ===`

- [ ] **Step 2: Dry run — scheduler shows all jobs**

```bash
python -m agents.v3 --dry-run
```

Expected: `Wookiee v3 scheduler — 10 job(s) configured` (no errors, no tracebacks)

- [ ] **Step 3: Verify no dangling imports to deleted modules**

```bash
grep -r "from agents.oleg.bot\|from agents.oleg.pipeline\|from agents.oleg.agents.researcher\|from agents.oleg.agents.quality\|from agents.oleg.agents.christina\|from agents.oleg.agents.seo\|from agents.oleg.config\|from agents.oleg.services.notion_service\|from agents.v3.delivery.notion import" agents/ scripts/ services/ shared/ --include="*.py"
```

Expected: no results

- [ ] **Step 4: Run existing tests**

```bash
python -m pytest tests/oleg/ tests/v3/ -x -q 2>&1 | tail -20
```

Expected: tests pass (or skip if DB not available — no import errors)

- [ ] **Step 5: Verify preserved prompts exist**

```bash
python -c "
from pathlib import Path
required = [
    'agents/oleg/agents/reporter/prompts.py',
    'agents/oleg/agents/advisor/prompts.py',
    'agents/oleg/agents/validator/prompts.py',
    'agents/oleg/agents/marketer/prompts.py',
    'agents/oleg/orchestrator/prompts.py',
    'agents/oleg/playbook.md',
    'agents/oleg/marketing_playbook.md',
]
for f in required:
    assert Path(f).exists(), f'MISSING: {f}'
    print(f'  ✓ {f}')
print('All V2 prompts preserved')
"
```

Expected: all 7 files exist

- [ ] **Step 6: Commit verification results (if any fixes needed)**

If all checks pass, no commit needed. If fixes were required, commit them:
```bash
git add -A && git commit -m "fix: resolve issues found during Stage 1 verification"
```
