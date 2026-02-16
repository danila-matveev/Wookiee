"""
API Documentation Analyzer — LLM-powered analysis of WB/Ozon API docs.

Discovers new endpoints, detects deprecated ones,
suggests new data sources for collection.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# Public API documentation URLs
WB_DOCS_URLS = [
    "https://dev.wildberries.ru/openapi/statistics",
    "https://dev.wildberries.ru/openapi/content",
    "https://dev.wildberries.ru/openapi/analytics",
    "https://dev.wildberries.ru/openapi/marketplace",
    "https://dev.wildberries.ru/openapi/adv",
]

OZON_DOCS_URLS = [
    "https://docs.ozon.ru/api/seller/",
]

ANALYSIS_PROMPT = """Ты — дата-инженер, анализирующий API маркетплейса.

Текущая схема БД (таблицы, которые мы заполняем):
{schema_summary}

Текущие API-эндпоинты, которые мы используем:
{current_endpoints}

Документация API:
{api_docs}

Задачи:
1. Найди эндпоинты, данные из которых мы НЕ собираем, но которые могут быть полезны
2. Определи, какие данные могут дополнить нашу аналитику (финансы, продажи, реклама, склады)
3. Предложи новые таблицы или поля для расширения схемы
4. Отметь deprecated эндпоинты среди тех, что мы используем
5. Оцени приоритет каждого предложения (high / medium / low)

Формат ответа — JSON:
{{
    "new_endpoints": [
        {{
            "endpoint": "...",
            "description": "...",
            "data_type": "...",
            "priority": "high|medium|low",
            "suggested_table": "...",
            "fields": ["..."]
        }}
    ],
    "deprecated_warnings": ["..."],
    "schema_suggestions": ["..."],
    "summary": "..."
}}"""

# WB and Ozon endpoints currently in use
WB_CURRENT_ENDPOINTS = [
    "GET /api/v1/supplier/reportDetailByPeriod (abc_date)",
    "GET /api/v1/supplier/sales (sales)",
    "GET /api/v1/supplier/orders (orders)",
    "GET /api/v2/stocks (stocks)",
    "GET /content/v2/get/cards/list (nomenclature)",
    "GET /adv/v2/fullstats (wb_adv)",
]

OZON_CURRENT_ENDPOINTS = [
    "POST /v3/finance/transaction/list (abc_date)",
    "POST /v2/posting/fbo/list (orders)",
    "POST /v3/posting/fbs/list (orders)",
    "POST /v2/analytics/data (analytics)",
    "POST /v2/product/list + /v2/product/info/list (nomenclature)",
    "POST /v3/product/info/stocks (stocks)",
    "POST /v1/performance/statistics/campaign/daily (adv_stats_daily)",
]

DB_SCHEMA_SUMMARY = """
wb.abc_date: date, article, barcode, nm_id, revenue_spp, comis_spp, logist, sebes, reclama, storage, nds, penalty, etc.
wb.orders: date, supplierarticle, nmid, category, brand, barcode, warehousename, regionname, lk
wb.sales: date, supplierarticle, nmid, finishedprice, forpay, barcode, lk
wb.stocks: dateupdate, barcode, warehousename, quantity, quantityfull, lk
wb.nomenclature: vendorcode, nmid, brand, title, photos, dimensions, characteristics
wb.content_analysis: date, vendorcode, title_length, description_length, photo_count, score
wb.wb_adv: date, nmid, advertid, views, clicks, sum, atbs, orders, shks, lk

ozon.abc_date: date, article, sku, price_end, count_end, comission, delivery, sebes, marga, nds, reclama_end, adv_vn, lk
ozon.orders: order_id, in_process_at, offer_id, sku, quantity, price, lk
ozon.returns: operation_date, sku, quantity, return_reason_name, lk
ozon.stocks: dateupdate, sku, warehouse_name, present, reserved, lk
ozon.nomenclature: article, ozon_product_id, name, barcode, marketing_price
ozon.adv_stats_daily: operation_date, id_rk, views, clicks, spend, orders_count, revenue
ozon.ozon_adv_api: operation_date, sku, views, clicks, expense, orders, revenue
"""


class APIDocsAnalyzer:
    """Analyzes marketplace API documentation using LLM."""

    def __init__(self, cache_dir: Path | None = None):
        from agents.ibrahim.config import API_DOCS_CACHE_DIR
        self.cache_dir = cache_dir or API_DOCS_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def analyze(self, llm_client=None) -> dict:
        """Run full API documentation analysis.

        Args:
            llm_client: OpenRouterClient instance.

        Returns:
            dict with analysis results.
        """
        if llm_client is None:
            logger.warning("No LLM client provided, skipping analysis")
            return {"status": "skipped", "reason": "no_llm_client"}

        results = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "wb": None,
            "ozon": None,
        }

        # Analyze WB
        try:
            wb_result = await self._analyze_marketplace(
                llm_client,
                marketplace="wb",
                current_endpoints=WB_CURRENT_ENDPOINTS,
                docs_urls=WB_DOCS_URLS,
            )
            results["wb"] = wb_result
        except Exception as e:
            logger.error("WB API analysis failed: %s", e, exc_info=True)
            results["wb"] = {"error": str(e)}

        # Analyze Ozon
        try:
            ozon_result = await self._analyze_marketplace(
                llm_client,
                marketplace="ozon",
                current_endpoints=OZON_CURRENT_ENDPOINTS,
                docs_urls=OZON_DOCS_URLS,
            )
            results["ozon"] = ozon_result
        except Exception as e:
            logger.error("Ozon API analysis failed: %s", e, exc_info=True)
            results["ozon"] = {"error": str(e)}

        # Save report
        report_path = self.cache_dir / f"analysis_{datetime.now().strftime('%Y%m%d')}.json"
        report_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))
        logger.info("API analysis report saved: %s", report_path)

        return results

    async def _analyze_marketplace(
        self, llm_client, marketplace: str, current_endpoints: list, docs_urls: list
    ) -> dict:
        """Analyze a single marketplace API."""
        prompt = ANALYSIS_PROMPT.format(
            schema_summary=DB_SCHEMA_SUMMARY,
            current_endpoints="\n".join(current_endpoints),
            api_docs=f"Marketplace: {marketplace.upper()}\nDocs URLs: {', '.join(docs_urls)}\n"
                     f"(Analyze based on your knowledge of the {marketplace.upper()} API)",
        )

        response = await llm_client.complete(
            messages=[
                {"role": "system", "content": "Respond in JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4000,
        )

        content = response.get("content", "")
        if not content:
            return {"error": response.get("error", "empty response")}

        # Parse JSON from response
        try:
            # Strip markdown code fences if present
            text = content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Could not parse LLM response as JSON for %s", marketplace)
            return {"raw_response": content}
