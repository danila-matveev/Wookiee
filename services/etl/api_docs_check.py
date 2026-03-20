"""API documentation analysis — weekly cron job.

Wraps APIDocsAnalyzer for use from the v3 scheduler.
Not an agent — LLM-assisted script safe to run from cron or CLI.
"""

from __future__ import annotations

import asyncio
import logging

from services.etl.api_docs_analyzer import APIDocsAnalyzer

logger = logging.getLogger(__name__)


async def run_api_docs_check(llm_client=None) -> dict:
    """Run API documentation analysis.

    Args:
        llm_client: OpenRouterClient instance. If None, analysis is skipped.

    Returns:
        dict with analysis results per marketplace.
    """
    analyzer = APIDocsAnalyzer()
    logger.info("Running API documentation analysis")
    return await analyzer.analyze(llm_client=llm_client)


if __name__ == "__main__":
    result = asyncio.run(run_api_docs_check())
    import json
    print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
