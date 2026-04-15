# Notification Spam Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate all duplicate/spam Telegram notifications from Wookiee v3 scheduler

**Architecture:** Five bugs fixed across 4 files. Startup lock prevents dual-process. Atomic SQLite dedup replaces in-memory set. Rate limiting by error type instead of text hash. Three data-ready messages merged into one combined message.

**Tech Stack:** Python, SQLite, APScheduler, aiogram, fcntl (POSIX flock)

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `agents/v3/app.py` | Modify | Add startup flock to prevent dual-process |
| `agents/v3/conductor/state.py` | Modify | Atomic already_notified via INSERT-then-SELECT |
| `agents/v3/conductor/conductor.py` | Modify | Merge 3 data-ready messages into 1 |
| `agents/v3/delivery/messages.py` | Modify | New `data_ready_combined()` template |
| `agents/v3/monitor.py` | Modify | Rate-limit by error category, not text hash |
| `tests/v3/conductor/test_state.py` | Modify | Test atomic dedup |
| `tests/v3/conductor/test_integration.py` | Modify | Test combined notification |
| `tests/v3/test_monitor.py` | Create | Test rate-limiting by category |

---

### Task 1: Startup Lock — Prevent Dual Process

**Files:**
- Modify: `agents/v3/app.py:53-64`

- [ ] **Step 1: Write the startup lock**

Add flock-based singleton guard at the top of `run()` in `agents/v3/app.py`. Insert after line 60 (`logger.info("Wookiee v3 starting up...")`), before line 62 (`from agents.v3.scheduler import create_scheduler`):

```python
    # ── Singleton lock — prevent dual-process ────────────────────────────
    import fcntl
    lock_path = os.path.join(
        os.path.dirname(config.STATE_DB_PATH) or "agents/v3/data",
        "v3.lock",
    )
    lock_file = open(lock_path, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        logger.fatal(
            "Another Wookiee v3 instance is already running (lock: %s). Exiting.",
            lock_path,
        )
        sys.exit(1)
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    logger.info("Startup lock acquired: %s (pid=%d)", lock_path, os.getpid())
```

Also add `import os` at the top of the file (after `import sys` on line 13).

- [ ] **Step 2: Run tests to verify nothing broke**

Run: `python -m pytest tests/v3/ -x -q`
Expected: All existing tests pass

- [ ] **Step 3: Manual smoke test**

Run: `python -m agents.v3 --dry-run`
Expected: Lists jobs and exits. Lock file created at `agents/v3/data/v3.lock`.

- [ ] **Step 4: Commit**

```bash
git add agents/v3/app.py
git commit -m "fix(v3): add startup flock to prevent dual-process notification spam"
```

---

### Task 2: Atomic Notification Dedup in ConductorState

**Files:**
- Modify: `agents/v3/conductor/state.py:11,129-150`
- Modify: `tests/v3/conductor/test_state.py`

- [ ] **Step 1: Write the test for atomic dedup**

Add to `tests/v3/conductor/test_state.py`:

```python
def test_already_notified_is_atomic(tmp_path):
    """mark_notified + already_notified uses only SQLite, no in-memory set."""
    state = ConductorState(str(tmp_path / "test.db"))
    state.ensure_table()

    # First call: should mark and return True
    assert state.already_notified("2026-03-28") is False
    state.mark_notified("2026-03-28")
    assert state.already_notified("2026-03-28") is True

    # Simulate process restart: new instance, same DB
    state2 = ConductorState(str(tmp_path / "test.db"))
    state2.ensure_table()
    assert state2.already_notified("2026-03-28") is True


def test_already_notified_channel_key(tmp_path):
    """Channel-specific keys (e.g. '2026-03-28:wb') work independently."""
    state = ConductorState(str(tmp_path / "test.db"))
    state.ensure_table()

    state.mark_notified("2026-03-28:wb")
    assert state.already_notified("2026-03-28:wb") is True
    assert state.already_notified("2026-03-28:ozon") is False
    assert state.already_notified("2026-03-28") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/v3/conductor/test_state.py::test_already_notified_is_atomic -v`
Expected: `test_already_notified_is_atomic` PASSES (existing SQLite logic already persists). But this confirms correctness.

- [ ] **Step 3: Remove in-memory `_notified_dates` set**

In `agents/v3/conductor/state.py`, make these changes:

Remove line 11:
```python
        self._notified_dates: set[str] = set()
```

Replace `already_notified` method (lines 129-139):
```python
    def already_notified(self, report_date: str) -> bool:
        """Check if data_ready notification was already sent for this date.

        Uses only SQLite — no in-memory state. Safe across async contexts
        and container restarts.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM conductor_log WHERE date = ? AND status = 'notified' LIMIT 1",
                (report_date,),
            ).fetchone()
        return row is not None
```

Replace `mark_notified` method (lines 141-150):
```python
    def mark_notified(self, report_date: str) -> None:
        """Mark that data_ready notification was sent for this date.

        Atomic INSERT OR IGNORE — safe for concurrent async calls.
        """
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO conductor_log (date, report_type, status, attempts) "
                "VALUES (?, '_notification', 'notified', 0)",
                (report_date,),
            )
```

- [ ] **Step 4: Run all conductor tests**

Run: `python -m pytest tests/v3/conductor/ -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add agents/v3/conductor/state.py tests/v3/conductor/test_state.py
git commit -m "fix(conductor): remove in-memory _notified_dates, use SQLite-only atomic dedup"
```

---

### Task 3: Merge 3 Data-Ready Messages Into 1

**Files:**
- Modify: `agents/v3/delivery/messages.py:16-60`
- Modify: `agents/v3/conductor/conductor.py:166-188`
- Modify: `tests/v3/conductor/test_integration.py`

- [ ] **Step 1: Write test for combined notification**

Add to `tests/v3/conductor/test_integration.py`:

```python
@pytest.mark.asyncio
async def test_single_combined_data_ready_message(full_setup):
    """All data-ready info should arrive as ONE message, not 3 separate ones."""
    s = full_setup
    await data_ready_check(
        gate_checker=s["gate_checker"],
        conductor_state=s["state"],
        telegram_send=s["telegram_send"],
        orchestrator=s["orchestrator"],
        delivery=s["delivery"],
        scheduler=MagicMock(),
        today=date(2026, 3, 19),  # Thursday
    )

    # Count "data ready" messages (messages containing "готовы")
    ready_msgs = [m for m in s["telegram_messages"] if "готовы" in m]
    assert len(ready_msgs) == 1, f"Expected 1 data-ready message, got {len(ready_msgs)}: {ready_msgs}"

    # The single message should contain both WB and OZON
    msg = ready_msgs[0]
    assert "WB" in msg
    assert "OZON" in msg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/v3/conductor/test_integration.py::test_single_combined_data_ready_message -v`
Expected: FAIL — currently sends 3 messages

- [ ] **Step 3: Add `data_ready_combined()` to messages.py**

Add after the existing `channel_data_ready` function (after line 60) in `agents/v3/delivery/messages.py`:

```python


def data_ready_combined(
    date: str,
    channels: list[dict],
    reports: list[str],
) -> str:
    """Combined data-ready notification: all channels + report list in one message.

    Each channel dict has: marketplace, gate_info (with keys: updated_at, orders,
    orders_normal, revenue_ratio, margin_pct).
    """
    lines = [f"✅ Данные за {date} готовы"]
    lines.append("")

    for ch in channels:
        mp = ch["marketplace"].upper()
        gi = ch["gate_info"]
        parts = [f"  {mp}:"]

        orders = gi.get("orders", 0)
        if gi.get("orders_normal", True):
            parts.append(f"заказов {orders}")
        else:
            parts.append(f"⚠️ заказов {orders} (ниже нормы)")

        rev = gi.get("revenue_ratio")
        if rev is not None:
            parts.append(f"выручка {rev:.0f}%")

        margin = gi.get("margin_pct")
        if margin is not None:
            parts.append(f"маржа {margin:.0f}%")

        lines.append(" | ".join(parts))

    if reports:
        lines.append("")
        reports_str = ", ".join(reports)
        lines.append(f"📊 Запускаю: {reports_str}")

    return "\n".join(lines)
```

- [ ] **Step 4: Replace 3-message send with 1 in conductor.py**

Replace lines 166-188 in `agents/v3/conductor/conductor.py` (the "Send per-channel + combined" block):

```python
    # 3. Send combined "data ready" notification (deduplicated)
    yesterday = today - timedelta(days=1)
    day_month = f"{yesterday.day} {_month_name(yesterday.month)}"
    report_date = str(today)

    if not conductor_state.already_notified(report_date):
        channels = []
        for mp, gates in [("wb", wb_gates), ("ozon", ozon_gates)]:
            channels.append({
                "marketplace": mp,
                "gate_info": _extract_gate_info(gates),
            })
        pending_names = [rt.human_name for rt in pending]
        await telegram_send(
            messages.data_ready_combined(day_month, channels, pending_names)
        )
        conductor_state.mark_notified(report_date)
    else:
        logger.debug("data_ready: already notified for %s, skipping message", report_date)
```

- [ ] **Step 5: Run all conductor tests**

Run: `python -m pytest tests/v3/conductor/ -v`
Expected: All tests pass including the new one

- [ ] **Step 6: Commit**

```bash
git add agents/v3/delivery/messages.py agents/v3/conductor/conductor.py tests/v3/conductor/test_integration.py
git commit -m "fix(conductor): merge 3 data-ready notifications into 1 combined message"
```

---

### Task 4: Rate-Limit Error Notifications by Category

**Files:**
- Modify: `agents/v3/monitor.py:19-54`
- Create: `tests/v3/test_monitor.py`

- [ ] **Step 1: Write the test**

Create `tests/v3/test_monitor.py`:

```python
"""Tests for admin notification rate limiting."""
import pytest
import time
from unittest.mock import AsyncMock, patch

from agents.v3.monitor import _send_admin, _recent_messages, _RATE_LIMIT_SEC


@pytest.fixture(autouse=True)
def clear_rate_limit():
    """Clear rate limit state between tests."""
    _recent_messages.clear()
    yield
    _recent_messages.clear()


@pytest.mark.asyncio
async def test_identical_messages_rate_limited():
    """Same text within 5 min window is suppressed."""
    with patch("agents.v3.monitor.config") as mock_config:
        mock_config.TELEGRAM_BOT_TOKEN = "test"
        mock_config.ADMIN_CHAT_ID = "123"

        mock_bot_cls = AsyncMock()
        mock_bot = mock_bot_cls.return_value
        mock_bot.send_message = AsyncMock()
        mock_bot.session.close = AsyncMock()

        with patch("agents.v3.monitor.Bot", mock_bot_cls):
            await _send_admin("test message")
            await _send_admin("test message")

        # Only one send
        assert mock_bot.send_message.call_count == 1


@pytest.mark.asyncio
async def test_different_messages_not_rate_limited():
    """Different text is NOT suppressed."""
    with patch("agents.v3.monitor.config") as mock_config:
        mock_config.TELEGRAM_BOT_TOKEN = "test"
        mock_config.ADMIN_CHAT_ID = "123"

        mock_bot_cls = AsyncMock()
        mock_bot = mock_bot_cls.return_value
        mock_bot.send_message = AsyncMock()
        mock_bot.session.close = AsyncMock()

        with patch("agents.v3.monitor.Bot", mock_bot_cls):
            await _send_admin("message A")
            await _send_admin("message B")

        assert mock_bot.send_message.call_count == 2


@pytest.mark.asyncio
async def test_error_category_rate_limiting():
    """Error messages with same prefix but different details should be suppressed.

    e.g. prompt-tuner errors with different raw_output must be rate-limited together.
    """
    msg1 = "❌ Ошибка «prompt-tuner»:\nError code: 403 - {'error': 'details A'}"
    msg2 = "❌ Ошибка «prompt-tuner»:\nError code: 403 - {'error': 'details B'}"

    with patch("agents.v3.monitor.config") as mock_config:
        mock_config.TELEGRAM_BOT_TOKEN = "test"
        mock_config.ADMIN_CHAT_ID = "123"

        mock_bot_cls = AsyncMock()
        mock_bot = mock_bot_cls.return_value
        mock_bot.send_message = AsyncMock()
        mock_bot.session.close = AsyncMock()

        with patch("agents.v3.monitor.Bot", mock_bot_cls):
            await _send_admin(msg1)
            await _send_admin(msg2)

        # Both have same category "Ошибка «prompt-tuner»" — second suppressed
        assert mock_bot.send_message.call_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/v3/test_monitor.py::test_error_category_rate_limiting -v`
Expected: FAIL — currently uses full text hash, so different details = different hash = both sent

- [ ] **Step 3: Update rate limiting in `_send_admin()`**

Replace lines 32-34 in `agents/v3/monitor.py`:

```python
    # Rate limit — подавляем дубли одинаковых сообщений
    import hashlib
    msg_hash = hashlib.md5(text.encode()).hexdigest()[:12]
```

With:

```python
    # Rate limit — подавляем дубли по категории сообщения.
    # Для ошибок вида "❌ Ошибка «agent-name»:\ndetails..." хешируем только
    # первую строку (тип ошибки), чтобы разные детали не обходили rate-limit.
    import hashlib
    first_line = text.split("\n", 1)[0]
    msg_hash = hashlib.md5(first_line.encode()).hexdigest()[:12]
```

- [ ] **Step 4: Run all monitor tests**

Run: `python -m pytest tests/v3/test_monitor.py -v`
Expected: All 3 tests pass

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/v3/ -x -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add agents/v3/monitor.py tests/v3/test_monitor.py
git commit -m "fix(monitor): rate-limit error notifications by first-line category, not full text"
```

---

### Task 5: Deploy and Verify

**Files:** No code changes — operational task.

- [ ] **Step 1: Check for duplicate processes on server**

```bash
ssh <server> "docker ps | grep oleg"
```

Expected: Only ONE `wookiee_oleg` container. If multiple — kill extras:
```bash
ssh <server> "docker stop <extra_container_id> && docker rm <extra_container_id>"
```

- [ ] **Step 2: Deploy new code**

```bash
ssh <server> "cd /opt/wookiee && git pull && docker compose -f deploy/docker-compose.yml build wookiee-oleg && docker compose -f deploy/docker-compose.yml up -d wookiee-oleg"
```

- [ ] **Step 3: Verify lock file**

```bash
ssh <server> "docker exec wookiee_oleg cat agents/v3/data/v3.lock"
```

Expected: Shows PID of the running process.

- [ ] **Step 4: Verify no duplicate notifications next day**

Monitor Telegram bot for one daily cycle. Expected:
- ONE combined data-ready message (not 3 separate)
- ONE daily report
- No hourly Weekly ДДС spam
- No duplicate prompt-tuner errors

---

## Summary

| Task | Bug Fixed | Impact |
|------|-----------|--------|
| 1 | Dual process → duplicate everything | CRITICAL |
| 2 | In-memory dedup race condition | CRITICAL |
| 3 | 3 messages → 1 combined | UX |
| 4 | prompt-tuner error spam | HIGH |
| 5 | Deploy + verify | Operational |

Total estimated: 5 tasks, ~20 steps.
