# Phase 1: MCP Foundation + Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the monolithic MCP server into domain-specific MCP servers and add agent observability logging to Supabase — the foundation for the entire multi-agent redesign.

**Architecture:** The existing `agents/oleg/mcp_server.py` wraps ~60 tools in one server. We split it into 4 focused MCP servers (`wookiee-data`, `wookiee-price`, `wookiee-marketing`, `wookiee-kb`) plus create the observability schema in Supabase. Each MCP server is a standalone Python process using the `mcp` SDK, wrapping existing functions from `shared/data_layer.py` and service modules.

**Tech Stack:** Python MCP SDK (`mcp`), Supabase (PostgreSQL), existing `shared/data_layer.py`, existing `services/price_analysis/`, existing `services/knowledge_base/`

**Spec:** `docs/superpowers/specs/2026-03-19-multi-agent-redesign.md`

---

## File Structure

### New files to create:

```
mcp_servers/
├── __init__.py
├── common/
│   ├── __init__.py
│   └── server_utils.py          # Shared MCP server utilities (JSON serialization, error handling)
├── wookiee_data/
│   ├── __init__.py
│   └── server.py                # Financial data MCP server (wraps data_layer.py)
├── wookiee_price/
│   ├── __init__.py
│   └── server.py                # Price analysis MCP server (wraps price_analysis/)
├── wookiee_marketing/
│   ├── __init__.py
│   └── server.py                # Marketing + funnel MCP server
├── wookiee_kb/
│   ├── __init__.py
│   └── server.py                # Knowledge base MCP server (wraps knowledge_base/)
└── tests/
    ├── test_wookiee_data.py
    ├── test_wookiee_price.py
    ├── test_wookiee_marketing.py
    └── test_wookiee_kb.py

services/
└── observability/
    ├── __init__.py
    ├── schema.sql               # Supabase migration: agent_registry, agent_runs, orchestrator_runs
    ├── logger.py                # Async fire-and-forget logging to Supabase
    └── version_tracker.py       # MD file hashing and auto-version detection
```

### Files to modify:
- `.claude/settings.local.json` — register MCP servers for Claude Code testing

---

## Task 1: Observability Schema in Supabase

**Files:**
- Create: `services/observability/__init__.py`
- Create: `services/observability/schema.sql`

- [ ] **Step 1: Create observability directory**

```bash
mkdir -p services/observability
touch services/observability/__init__.py
```

- [ ] **Step 2: Write the SQL migration**

Create `services/observability/schema.sql`:

```sql
-- Agent Registry — tracks all agents, their versions, and prompt history
CREATE TABLE IF NOT EXISTS agent_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL,
    agent_type TEXT NOT NULL CHECK (agent_type IN ('orchestrator', 'micro-agent')),
    version TEXT NOT NULL,
    md_file_path TEXT,
    system_prompt TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    mcp_tools TEXT[],
    model_tier TEXT CHECK (model_tier IN ('HEAVY', 'MAIN', 'LIGHT')),
    default_model TEXT,
    description TEXT,
    changelog TEXT,
    created_by TEXT DEFAULT 'auto-detect',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(agent_name, version)
);

CREATE INDEX IF NOT EXISTS idx_agent_registry_name ON agent_registry(agent_name, is_active);
CREATE INDEX IF NOT EXISTS idx_agent_registry_hash ON agent_registry(prompt_hash);

-- Agent Runs — every invocation of every agent
CREATE TABLE IF NOT EXISTS agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL,
    parent_run_id UUID,
    agent_name TEXT NOT NULL,
    agent_type TEXT NOT NULL CHECK (agent_type IN ('orchestrator', 'micro-agent')),
    agent_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('success', 'failed', 'timeout', 'skipped', 'running')),
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,
    error_message TEXT,
    model TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    cost_usd NUMERIC(10,6),
    llm_calls INTEGER,
    tool_calls INTEGER,
    system_prompt_hash TEXT,
    user_input TEXT,
    output_summary TEXT,
    artifact JSONB,
    task_type TEXT,
    trigger TEXT CHECK (trigger IN ('cron', 'user_telegram', 'user_cli', 'orchestrator', 'manual')),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_run_id ON agent_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_agent ON agent_runs(agent_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_version ON agent_runs(agent_name, agent_version);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_date ON agent_runs(started_at DESC);

-- Orchestrator Run Summary — high-level view per pipeline execution
CREATE TABLE IF NOT EXISTS orchestrator_runs (
    run_id UUID PRIMARY KEY,
    orchestrator TEXT NOT NULL,
    orchestrator_version TEXT NOT NULL,
    task_type TEXT NOT NULL,
    trigger TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('success', 'partial', 'failed', 'running')),
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER,
    agents_called INTEGER DEFAULT 0,
    agents_succeeded INTEGER DEFAULT 0,
    agents_failed INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    total_cost_usd NUMERIC(10,6) DEFAULT 0,
    report_format TEXT,
    delivered_to TEXT[],
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_orchestrator_runs_date ON orchestrator_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_orchestrator_runs_status ON orchestrator_runs(status);

-- RLS policies (Supabase requirement per AGENTS.md)
ALTER TABLE agent_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE orchestrator_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_agent_registry" ON agent_registry FOR ALL USING (true);
CREATE POLICY "service_role_all_agent_runs" ON agent_runs FOR ALL USING (true);
CREATE POLICY "service_role_all_orchestrator_runs" ON orchestrator_runs FOR ALL USING (true);
```

- [ ] **Step 3: Apply migration to Supabase**

```bash
# Using Supabase CLI or psql directly
psql "$SUPABASE_DB_URL" -f services/observability/schema.sql
```

Expected: Tables created without errors.

- [ ] **Step 4: Commit**

```bash
git add services/observability/
git commit -m "feat: add observability schema — agent_registry, agent_runs, orchestrator_runs"
```

---

## Task 2: Observability Logger

**Files:**
- Create: `services/observability/logger.py`
- Create: `services/observability/version_tracker.py`

- [ ] **Step 1: Write version tracker**

Create `services/observability/version_tracker.py`:

```python
"""Track agent MD file versions via content hashing."""
import hashlib
from pathlib import Path


def compute_prompt_hash(content: str) -> str:
    """SHA-256 hash of agent prompt content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def load_agent_prompt(md_file_path: str) -> str:
    """Load agent prompt from MD file."""
    path = Path(md_file_path)
    if not path.exists():
        raise FileNotFoundError(f"Agent MD file not found: {md_file_path}")
    return path.read_text(encoding="utf-8")


def get_version_info(md_file_path: str) -> dict:
    """Get version info for an agent MD file.

    Returns dict with: prompt, prompt_hash, md_file_path
    """
    content = load_agent_prompt(md_file_path)
    return {
        "prompt": content,
        "prompt_hash": compute_prompt_hash(content),
        "md_file_path": md_file_path,
    }
```

- [ ] **Step 2: Write async logger**

Create `services/observability/logger.py`:

```python
"""Async fire-and-forget logging for agent runs."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from supabase import create_client

from shared.config import SUPABASE_URL, SUPABASE_SERVICE_KEY

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


def new_run_id() -> str:
    """Generate a new run ID."""
    return str(uuid.uuid4())


async def log_agent_run(
    run_id: str,
    agent_name: str,
    agent_type: str,
    agent_version: str,
    status: str,
    started_at: datetime,
    finished_at: Optional[datetime] = None,
    duration_ms: Optional[int] = None,
    error_message: Optional[str] = None,
    model: Optional[str] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    cost_usd: Optional[float] = None,
    llm_calls: Optional[int] = None,
    tool_calls: Optional[int] = None,
    system_prompt_hash: Optional[str] = None,
    user_input: Optional[str] = None,
    output_summary: Optional[str] = None,
    artifact: Optional[dict] = None,
    task_type: Optional[str] = None,
    trigger: Optional[str] = None,
    parent_run_id: Optional[str] = None,
) -> None:
    """Log an agent run to Supabase. Fire-and-forget — never raises."""
    try:
        row = {
            "run_id": run_id,
            "parent_run_id": parent_run_id,
            "agent_name": agent_name,
            "agent_type": agent_type,
            "agent_version": agent_version,
            "status": status,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat() if finished_at else None,
            "duration_ms": duration_ms,
            "error_message": error_message[:2000] if error_message else None,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost_usd,
            "llm_calls": llm_calls,
            "tool_calls": tool_calls,
            "system_prompt_hash": system_prompt_hash,
            "user_input": user_input[:2000] if user_input else None,
            "output_summary": output_summary[:2000] if output_summary else None,
            "artifact": artifact,
            "task_type": task_type,
            "trigger": trigger,
        }
        # Remove None values
        row = {k: v for k, v in row.items() if v is not None}
        _get_client().table("agent_runs").insert(row).execute()
    except Exception as e:
        logger.warning(f"Failed to log agent run: {e}")


async def log_orchestrator_run(
    run_id: str,
    orchestrator: str,
    orchestrator_version: str,
    task_type: str,
    trigger: str,
    status: str,
    started_at: datetime,
    finished_at: Optional[datetime] = None,
    duration_ms: Optional[int] = None,
    agents_called: int = 0,
    agents_succeeded: int = 0,
    agents_failed: int = 0,
    total_tokens: int = 0,
    total_cost_usd: float = 0.0,
    report_format: Optional[str] = None,
    delivered_to: Optional[list[str]] = None,
) -> None:
    """Log an orchestrator run summary. Fire-and-forget — never raises."""
    try:
        row = {
            "run_id": run_id,
            "orchestrator": orchestrator,
            "orchestrator_version": orchestrator_version,
            "task_type": task_type,
            "trigger": trigger,
            "status": status,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat() if finished_at else None,
            "duration_ms": duration_ms,
            "agents_called": agents_called,
            "agents_succeeded": agents_succeeded,
            "agents_failed": agents_failed,
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost_usd,
            "report_format": report_format,
            "delivered_to": delivered_to,
        }
        row = {k: v for k, v in row.items() if v is not None}
        _get_client().table("orchestrator_runs").insert(row).execute()
    except Exception as e:
        logger.warning(f"Failed to log orchestrator run: {e}")


async def register_agent_version(
    agent_name: str,
    agent_type: str,
    version: str,
    system_prompt: str,
    prompt_hash: str,
    md_file_path: Optional[str] = None,
    mcp_tools: Optional[list[str]] = None,
    model_tier: Optional[str] = None,
    default_model: Optional[str] = None,
    description: Optional[str] = None,
    changelog: Optional[str] = None,
    created_by: str = "auto-detect",
) -> None:
    """Register a new agent version. Skips if version already exists."""
    try:
        existing = (
            _get_client()
            .table("agent_registry")
            .select("id")
            .eq("agent_name", agent_name)
            .eq("version", version)
            .execute()
        )
        if existing.data:
            return  # Already registered

        row = {
            "agent_name": agent_name,
            "agent_type": agent_type,
            "version": version,
            "system_prompt": system_prompt,
            "prompt_hash": prompt_hash,
            "md_file_path": md_file_path,
            "mcp_tools": mcp_tools,
            "model_tier": model_tier,
            "default_model": default_model,
            "description": description,
            "changelog": changelog,
            "created_by": created_by,
        }
        row = {k: v for k, v in row.items() if v is not None}
        _get_client().table("agent_registry").insert(row).execute()
    except Exception as e:
        logger.warning(f"Failed to register agent version: {e}")
```

- [ ] **Step 3: Verify imports work**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python -c "from services.observability.logger import new_run_id; print(new_run_id())"
python -c "from services.observability.version_tracker import compute_prompt_hash; print(compute_prompt_hash('test'))"
```

Expected: UUID printed, hash printed, no import errors.

- [ ] **Step 4: Commit**

```bash
git add services/observability/
git commit -m "feat: add observability logger and version tracker"
```

---

## Task 3: MCP Server Common Utilities

**Files:**
- Create: `mcp_servers/__init__.py`
- Create: `mcp_servers/common/__init__.py`
- Create: `mcp_servers/common/server_utils.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p mcp_servers/common
touch mcp_servers/__init__.py mcp_servers/common/__init__.py
```

- [ ] **Step 2: Write shared utilities**

Create `mcp_servers/common/server_utils.py`:

```python
"""Shared utilities for all Wookiee MCP servers."""
import json
import logging
import sys
from datetime import date, datetime
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


class WookieeJSONEncoder(json.JSONEncoder):
    """JSON encoder handling date, datetime, Decimal types from DB results."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def to_json(data: Any) -> str:
    """Serialize data to JSON string, handling DB types."""
    return json.dumps(data, cls=WookieeJSONEncoder, ensure_ascii=False)


def safe_tool_call(func):
    """Decorator for MCP tool handlers. Catches exceptions, returns JSON error."""
    async def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            # Handle both sync and async functions
            if hasattr(result, "__await__"):
                result = await result
            return to_json(result)
        except Exception as e:
            logger.exception(f"Tool call failed: {func.__name__}")
            return to_json({"error": str(e), "tool": func.__name__})
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def setup_logging(server_name: str) -> None:
    """Configure logging for an MCP server."""
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [{server_name}] %(levelname)s: %(message)s",
        stream=sys.stderr,  # MCP uses stdout for protocol, stderr for logs
    )
```

- [ ] **Step 3: Commit**

```bash
git add mcp_servers/
git commit -m "feat: add MCP server common utilities"
```

---

## Task 4: wookiee-data MCP Server

**Files:**
- Create: `mcp_servers/wookiee_data/__init__.py`
- Create: `mcp_servers/wookiee_data/server.py`

This is the largest MCP server — wraps `shared/data_layer.py` financial queries.

- [ ] **Step 1: Create directory**

```bash
mkdir -p mcp_servers/wookiee_data
touch mcp_servers/wookiee_data/__init__.py
```

- [ ] **Step 2: Write the wookiee-data server**

Create `mcp_servers/wookiee_data/server.py`. This wraps the public `execute_tool()` dispatcher from `agents/oleg/services/agent_tools.py` (all individual handlers are private `_handle_*`).

**Important:** `agent_tools.py` extends `TOOL_DEFINITIONS` with price tools at line 1587 (`TOOL_DEFINITIONS.extend(PRICE_TOOL_DEFINITIONS)`). We must filter those out so wookiee-data only exposes financial data tools, not price tools (those belong to wookiee-price).

```python
"""wookiee-data MCP server — financial analytics tools.

Wraps shared/data_layer.py and agents/oleg/services/agent_tools.py
to expose financial data via MCP protocol.

Run: python -m mcp_servers.wookiee_data.server
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.server import Server
from mcp.server.stdio import stdio_server

from mcp_servers.common.server_utils import setup_logging, to_json
from agents.oleg.services.agent_tools import TOOL_DEFINITIONS, execute_tool
from agents.oleg.services.price_tools import PRICE_TOOL_DEFINITIONS

setup_logging("wookiee-data")

server = Server("wookiee-data")

# Filter out price tools — those belong to wookiee-price server
_PRICE_TOOL_NAMES = {t["function"]["name"] for t in PRICE_TOOL_DEFINITIONS}
_DATA_TOOL_DEFS = [t for t in TOOL_DEFINITIONS if t["function"]["name"] not in _PRICE_TOOL_NAMES]
_DATA_TOOL_NAMES = {t["function"]["name"] for t in _DATA_TOOL_DEFS}


@server.list_tools()
async def list_tools():
    """Return tool definitions in MCP format (data tools only, no price tools)."""
    return [
        {
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "inputSchema": t["function"]["parameters"],
        }
        for t in _DATA_TOOL_DEFS
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Dispatch tool call via execute_tool() dispatcher."""
    if name not in _DATA_TOOL_NAMES:
        return [{"type": "text", "text": to_json({"error": f"Unknown tool: {name}"})}]

    try:
        result = await execute_tool(name, arguments)
        return [{"type": "text", "text": result if isinstance(result, str) else to_json(result)}]
    except Exception as e:
        return [{"type": "text", "text": to_json({"error": str(e), "tool": name})}]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

- [ ] **Step 3: Test server starts without errors**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python -c "from mcp_servers.wookiee_data.server import server; print(f'Server: {server.name}')"
```

Expected: `Server: wookiee-data`

- [ ] **Step 4: Commit**

```bash
git add mcp_servers/wookiee_data/
git commit -m "feat: add wookiee-data MCP server wrapping financial tools"
```

---

## Task 5: wookiee-price MCP Server

**Files:**
- Modify: `agents/oleg/services/price_tools.py` (add `execute_price_tool` dispatcher)
- Create: `mcp_servers/wookiee_price/__init__.py`
- Create: `mcp_servers/wookiee_price/server.py`

- [ ] **Step 1: Create directory**

```bash
mkdir -p mcp_servers/wookiee_price
touch mcp_servers/wookiee_price/__init__.py
```

- [ ] **Step 2: Add `execute_price_tool` dispatcher to `price_tools.py`**

`price_tools.py` has private `_handle_*` functions and an existing `PRICE_TOOL_HANDLERS` dict (line ~1161) mapping tool names to handlers — but no public dispatcher function. Add one at the bottom of `agents/oleg/services/price_tools.py`:

```python
# Add at the end of agents/oleg/services/price_tools.py

async def execute_price_tool(tool_name: str, arguments: dict) -> str:
    """Public dispatcher for price tools. Same pattern as agent_tools.execute_tool."""
    handler = PRICE_TOOL_HANDLERS.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown price tool: {tool_name}"})
    try:
        result = await handler(**arguments)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e), "tool": tool_name})
```

**Note:** `PRICE_TOOL_HANDLERS` already exists in the module — it's an explicit dict mapping tool names to `_handle_*` functions. Do NOT build a new mapping; reuse it directly.

Verify: `python -c "from agents.oleg.services.price_tools import execute_price_tool; print('OK')"`

- [ ] **Step 3: Write the wookiee-price server**

Create `mcp_servers/wookiee_price/server.py` — same pattern as wookiee-data but wrapping price tools from `agents/oleg/services/price_tools.py`:

```python
"""wookiee-price MCP server — price analysis and strategy tools.

Wraps agents/oleg/services/price_tools.py and services/price_analysis/*.

Run: python -m mcp_servers.wookiee_price.server
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.server import Server
from mcp.server.stdio import stdio_server

from mcp_servers.common.server_utils import setup_logging, to_json
from agents.oleg.services.price_tools import PRICE_TOOL_DEFINITIONS, execute_price_tool

setup_logging("wookiee-price")

server = Server("wookiee-price")

# All price tool names from definitions
_PRICE_TOOL_NAMES = {t["function"]["name"] for t in PRICE_TOOL_DEFINITIONS}


@server.list_tools()
async def list_tools():
    return [
        {
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "inputSchema": t["function"]["parameters"],
        }
        for t in PRICE_TOOL_DEFINITIONS
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name not in _PRICE_TOOL_NAMES:
        return [{"type": "text", "text": to_json({"error": f"Unknown tool: {name}"})}]

    try:
        result = await execute_price_tool(name, arguments)
        return [{"type": "text", "text": result if isinstance(result, str) else to_json(result)}]
    except Exception as e:
        return [{"type": "text", "text": to_json({"error": str(e), "tool": name})}]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

- [ ] **Step 4: Test server imports**

```bash
python -c "from mcp_servers.wookiee_price.server import server; print(f'Server: {server.name}')"
```

Expected: `Server: wookiee-price`

- [ ] **Step 5: Commit**

```bash
git add agents/oleg/services/price_tools.py mcp_servers/wookiee_price/
git commit -m "feat: add execute_price_tool dispatcher + wookiee-price MCP server"
```

---

## Task 6: wookiee-marketing MCP Server

**Files:**
- Create: `mcp_servers/wookiee_marketing/__init__.py`
- Create: `mcp_servers/wookiee_marketing/server.py`

- [ ] **Step 1: Create directory**

```bash
mkdir -p mcp_servers/wookiee_marketing
touch mcp_servers/wookiee_marketing/__init__.py
```

- [ ] **Step 2: Write the wookiee-marketing server**

Create `mcp_servers/wookiee_marketing/server.py` — wraps marketing + funnel tools:

```python
"""wookiee-marketing MCP server — marketing funnel and ad analytics.

Wraps agents/oleg/services/marketing_tools.py and funnel_tools.py.

Run: python -m mcp_servers.wookiee_marketing.server
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.server import Server
from mcp.server.stdio import stdio_server

from mcp_servers.common.server_utils import setup_logging, to_json
from agents.oleg.services.marketing_tools import (
    MARKETING_TOOL_DEFINITIONS,
    execute_marketing_tool,
)
from agents.oleg.services.funnel_tools import (
    FUNNEL_TOOL_DEFINITIONS,
    execute_funnel_tool,
)

setup_logging("wookiee-marketing")

server = Server("wookiee-marketing")

_MARKETING_NAMES = {t["function"]["name"] for t in MARKETING_TOOL_DEFINITIONS}
_FUNNEL_NAMES = {t["function"]["name"] for t in FUNNEL_TOOL_DEFINITIONS}
_ALL_DEFS = MARKETING_TOOL_DEFINITIONS + FUNNEL_TOOL_DEFINITIONS


@server.list_tools()
async def list_tools():
    return [
        {
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "inputSchema": t["function"]["parameters"],
        }
        for t in _ALL_DEFS
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name in _MARKETING_NAMES:
            result = await execute_marketing_tool(name, arguments)
        elif name in _FUNNEL_NAMES:
            result = await execute_funnel_tool(name, arguments)
        else:
            return [{"type": "text", "text": to_json({"error": f"Unknown tool: {name}"})}]

        return [{"type": "text", "text": result if isinstance(result, str) else to_json(result)}]
    except Exception as e:
        return [{"type": "text", "text": to_json({"error": str(e), "tool": name})}]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

- [ ] **Step 3: Test server imports**

```bash
python -c "from mcp_servers.wookiee_marketing.server import server; print(f'Server: {server.name}')"
```

Expected: `Server: wookiee-marketing`

- [ ] **Step 4: Commit**

```bash
git add mcp_servers/wookiee_marketing/
git commit -m "feat: add wookiee-marketing MCP server wrapping marketing and funnel tools"
```

---

## Task 7: wookiee-kb MCP Server

**Files:**
- Create: `mcp_servers/wookiee_kb/__init__.py`
- Create: `mcp_servers/wookiee_kb/server.py`

- [ ] **Step 1: Create directory**

```bash
mkdir -p mcp_servers/wookiee_kb
touch mcp_servers/wookiee_kb/__init__.py
```

- [ ] **Step 2: Write the wookiee-kb server**

Create `mcp_servers/wookiee_kb/server.py`:

```python
"""wookiee-kb MCP server — knowledge base search and management.

Wraps services/knowledge_base/ tools.

Run: python -m mcp_servers.wookiee_kb.server
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.server import Server
from mcp.server.stdio import stdio_server

from mcp_servers.common.server_utils import setup_logging, to_json
from services.knowledge_base.tools import (
    KB_SEARCH_TOOL_DEFINITIONS,
    KB_MANAGE_TOOL_DEFINITIONS,
    execute_kb_tool,
)

setup_logging("wookiee-kb")

server = Server("wookiee-kb")

_ALL_DEFS = KB_SEARCH_TOOL_DEFINITIONS + KB_MANAGE_TOOL_DEFINITIONS
_ALL_NAMES = {t["function"]["name"] for t in _ALL_DEFS}


@server.list_tools()
async def list_tools():
    return [
        {
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "inputSchema": t["function"]["parameters"],
        }
        for t in _ALL_DEFS
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name not in _ALL_NAMES:
        return [{"type": "text", "text": to_json({"error": f"Unknown tool: {name}"})}]

    try:
        result = await execute_kb_tool(name, arguments)
        return [{"type": "text", "text": result if isinstance(result, str) else to_json(result)}]
    except Exception as e:
        return [{"type": "text", "text": to_json({"error": str(e), "tool": name})}]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

- [ ] **Step 3: Test server imports**

```bash
python -c "from mcp_servers.wookiee_kb.server import server; print(f'Server: {server.name}')"
```

Expected: `Server: wookiee-kb`

- [ ] **Step 4: Commit**

```bash
git add mcp_servers/wookiee_kb/
git commit -m "feat: add wookiee-kb MCP server wrapping knowledge base tools"
```

---

## Task 8: Register MCP Servers for Claude Code Testing

**Files:**
- Modify: `.claude/settings.local.json`

- [ ] **Step 1: Update Claude Code settings to register all 4 MCP servers**

Update `.claude/settings.local.json`:

```json
{
  "permissions": {
    "allow": []
  },
  "mcpServers": {
    "wookiee-data": {
      "command": "python",
      "args": ["-m", "mcp_servers.wookiee_data.server"],
      "cwd": "/Users/danilamatveev/Desktop/Документы/Cursor/Wookiee"
    },
    "wookiee-price": {
      "command": "python",
      "args": ["-m", "mcp_servers.wookiee_price.server"],
      "cwd": "/Users/danilamatveev/Desktop/Документы/Cursor/Wookiee"
    },
    "wookiee-marketing": {
      "command": "python",
      "args": ["-m", "mcp_servers.wookiee_marketing.server"],
      "cwd": "/Users/danilamatveev/Desktop/Документы/Cursor/Wookiee"
    },
    "wookiee-kb": {
      "command": "python",
      "args": ["-m", "mcp_servers.wookiee_kb.server"],
      "cwd": "/Users/danilamatveev/Desktop/Документы/Cursor/Wookiee"
    }
  }
}
```

- [ ] **Step 2: Restart Claude Code and verify MCP servers appear**

After restarting Claude Code, run:
```
/mcp
```

Expected: All 4 servers listed with their tools.

- [ ] **Step 3: Smoke test — call a tool via Claude Code**

Ask Claude Code: "Use the wookiee-data MCP server to call get_brand_finance for 2026-03-17 to 2026-03-18"

Expected: JSON response with financial data (or graceful error if DB not accessible from local machine).

- [ ] **Step 4: Commit**

```bash
git add .claude/settings.local.json
git commit -m "feat: register 4 MCP servers in Claude Code settings"
```

---

## Task 9: Integration Verification

- [ ] **Step 1: Verify all MCP servers can import and list tools**

```bash
cd /Users/danilamatveev/Desktop/Документы/Cursor/Wookiee
python -c "
from mcp_servers.wookiee_data.server import server as s1
from mcp_servers.wookiee_price.server import server as s2
from mcp_servers.wookiee_marketing.server import server as s3
from mcp_servers.wookiee_kb.server import server as s4
print(f'wookiee-data: {s1.name}')
print(f'wookiee-price: {s2.name}')
print(f'wookiee-marketing: {s3.name}')
print(f'wookiee-kb: {s4.name}')
print('All MCP servers OK')
"
```

Expected: All 4 servers print their names, no import errors.

- [ ] **Step 2: Verify observability schema exists in Supabase**

```bash
python -c "
from supabase import create_client
from shared.config import SUPABASE_URL, SUPABASE_SERVICE_KEY
c = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
for table in ['agent_registry', 'agent_runs', 'orchestrator_runs']:
    r = c.table(table).select('id').limit(1).execute()
    print(f'{table}: OK (accessible)')
"
```

Expected: All 3 tables accessible.

- [ ] **Step 3: Verify logger can write to Supabase**

```bash
python -c "
import asyncio
from services.observability.logger import log_agent_run, new_run_id
from datetime import datetime, timezone

async def test():
    await log_agent_run(
        run_id=new_run_id(),
        agent_name='test-agent',
        agent_type='micro-agent',
        agent_version='0.0.1',
        status='success',
        started_at=datetime.now(timezone.utc),
        task_type='test',
        trigger='manual',
    )
    print('Logger write: OK')

asyncio.run(test())
"
```

Expected: `Logger write: OK`

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: Phase 1 complete — 4 MCP servers + observability foundation"
```

---

## Summary

| Task | What | Files | Est. |
|------|------|-------|------|
| 1 | Observability SQL schema | `services/observability/schema.sql` | 5 min |
| 2 | Logger + version tracker | `services/observability/logger.py`, `version_tracker.py` | 10 min |
| 3 | MCP common utilities | `mcp_servers/common/server_utils.py` | 5 min |
| 4 | wookiee-data server | `mcp_servers/wookiee_data/server.py` | 10 min |
| 5 | wookiee-price server | `mcp_servers/wookiee_price/server.py` | 10 min |
| 6 | wookiee-marketing server | `mcp_servers/wookiee_marketing/server.py` | 10 min |
| 7 | wookiee-kb server | `mcp_servers/wookiee_kb/server.py` | 10 min |
| 8 | Register in Claude Code | `.claude/settings.local.json` | 5 min |
| 9 | Integration verification | Smoke tests | 10 min |

**Phase 1 Acceptance Criteria (from spec):**
- [ ] `wookiee-data` MCP server responds to all 13 tools
- [ ] `wookiee-price` MCP server responds to all 9 tools
- [ ] MCP servers work from Claude Code CLI
- [ ] Observability tables created in Supabase
- [ ] Logger can write test runs to `agent_runs`
