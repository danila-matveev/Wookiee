#!/usr/bin/env python3
"""
E2E test: OlegAgent generates price analysis reports via LLM.
Requires: z.ai or OpenRouter API key + PostgreSQL connection.

Usage:
    python scripts/test_price_e2e.py
"""
import asyncio
import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"


def _status(ok: bool) -> str:
    return PASS if ok else FAIL


async def test_price_review():
    """E2E: Oleg generates a weekly price review."""
    print("\n=== E2E: Price Review Report ===\n")

    from agents.oleg import config
    from shared.clients.zai_client import ZAIClient
    from agents.oleg.services.oleg_agent import OlegAgent

    # Init LLM client
    if config.OPENROUTER_API_KEY:
        client = ZAIClient(
            api_key=config.OPENROUTER_API_KEY,
            model=config.OPENROUTER_MODEL,
            base_url="https://openrouter.ai/api/v1",
        )
        print(f"  LLM: OpenRouter ({config.OPENROUTER_MODEL})")
    elif config.ZAI_API_KEY:
        client = ZAIClient(api_key=config.ZAI_API_KEY, model=config.OLEG_MODEL)
        print(f"  LLM: z.ai ({config.OLEG_MODEL})")
    else:
        print(f"  [{SKIP}] No API key configured")
        return True

    # Health check
    is_healthy = await client.health_check()
    if not is_healthy:
        print(f"  [{SKIP}] LLM API not available")
        return True

    oleg = OlegAgent(
        zai_client=client,
        playbook_path=config.PLAYBOOK_PATH,
        model=config.OPENROUTER_MODEL if config.OPENROUTER_API_KEY else config.OLEG_MODEL,
    )

    end = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    passed = 0

    # Test 1: Price review report
    print("  Running price review...")
    result = await oleg.analyze(
        user_query="Ценовой обзор за последнюю неделю: эластичность, рекомендации по ценам, тренды",
        params={
            "start_date": start,
            "end_date": end,
            "channels": ["wb", "ozon"],
            "report_type": "price_review",
        },
    )
    ok_summary = bool(result.get('brief_summary'))
    ok_report = bool(result.get('detailed_report'))
    print(f"  [{_status(ok_summary)}] brief_summary: {len(result.get('brief_summary', ''))} chars")
    print(f"  [{_status(ok_report)}] detailed_report: {len(result.get('detailed_report', ''))} chars")

    if result.get('reasoning_steps'):
        price_tools_used = [
            s for s in result['reasoning_steps']
            if any(t in str(s) for t in [
                'get_price_elasticity', 'get_price_recommendation',
                'get_price_trend', 'get_price_margin_correlation',
            ])
        ]
        ok_tools = len(price_tools_used) > 0
        print(f"  [{_status(ok_tools)}] Price tools used: {len(price_tools_used)}")
    else:
        ok_tools = False
        print(f"  [{FAIL}] No reasoning_steps in result")

    cost = result.get('cost_usd', 0)
    iters = result.get('iterations', 0)
    duration = result.get('duration_ms', 0)
    print(f"  Cost: ${cost:.4f}, iterations: {iters}, duration: {duration}ms")

    if ok_summary and ok_report:
        passed += 1

    # Test 2: Price scenario
    print("\n  Running price scenario...")
    result2 = await oleg.analyze(
        user_query="Что будет если поднять цену Wendy на 10% на WB?",
        params={
            "start_date": start,
            "end_date": end,
            "channels": ["wb"],
            "report_type": "price_scenario",
            "models": ["wendy"],
        },
    )
    ok2 = bool(result2.get('brief_summary'))
    print(f"  [{_status(ok2)}] Scenario response: {len(result2.get('brief_summary', ''))} chars")
    if ok2:
        passed += 1

    # Test 3: Elasticity query
    print("\n  Running elasticity query...")
    result3 = await oleg.analyze(
        user_query="Какая эластичность у Ruby на OZON?",
        params={
            "channels": ["ozon"],
            "models": ["ruby"],
        },
    )
    ok3 = bool(result3.get('brief_summary'))
    print(f"  [{_status(ok3)}] Elasticity response: {len(result3.get('brief_summary', ''))} chars")
    if ok3:
        passed += 1

    # Save results
    reports_dir = ROOT / 'reports'
    reports_dir.mkdir(exist_ok=True)
    today = datetime.now().strftime('%Y-%m-%d')

    with open(reports_dir / f'{today}_price_e2e_results.json', 'w') as f:
        json.dump({
            'price_review': {
                'brief_summary': result.get('brief_summary', ''),
                'cost_usd': result.get('cost_usd'),
                'iterations': result.get('iterations'),
                'success': ok_summary and ok_report,
            },
            'scenario': {'success': ok2},
            'elasticity': {'success': ok3},
        }, f, ensure_ascii=False, indent=2)

    print(f"\n  Results saved to reports/{today}_price_e2e_results.json")
    print(f"\nE2E: {passed}/3 passed")
    return passed >= 2


async def main():
    ok = await test_price_review()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    asyncio.run(main())
