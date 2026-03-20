"""Schema analysis — weekly cron job.

Wraps SchemaManager for use from the v3 scheduler.
Not an agent — LLM-assisted script safe to run from cron or CLI.
"""

from __future__ import annotations

import asyncio
import logging

from services.etl.schema_manager import SchemaManager

logger = logging.getLogger(__name__)


async def run_schema_check(llm_client=None) -> dict:
    """Run schema analysis: compare managed vs source, propose improvements.

    Args:
        llm_client: OpenRouterClient instance. If None, returns raw schema comparison.

    Returns:
        dict with discrepancies, proposals, and summary.
    """
    manager = SchemaManager()
    logger.info("Running schema analysis")
    return await manager.analyze(llm_client=llm_client)


if __name__ == "__main__":
    result = asyncio.run(run_schema_check())
    import json
    print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
