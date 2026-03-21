"""
Finolog Service — weekly cash flow summary (balances + forecast + cash gap detection).

Fetches data from Finolog API, builds Markdown report for Notion
and brief HTML summary for Telegram.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional, Union

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.finolog.ru/v1"

COMPANY_NAMES = {
    81654: "ИП Медведева П.В.",
    81655: 'ООО «ВУКИ»',
}
COMPANY_ORDER = [81654, 81655]

# Account name → purpose classification
_PURPOSE_ORDER = [
    "operating", "funds_tax", "funds_nds", "funds_payroll",
    "funds_reserve", "funds_growth", "funds_other", "usd", "personal",
]
_PURPOSE_LABELS = {
    "operating": "Операционные",
    "funds_tax": "Фонд Налоги",
    "funds_nds": "Фонд НДС",
    "funds_payroll": "Фонд ФОТ",
    "funds_reserve": "НЗ / Резервы",
    "funds_growth": "Фонд развития",
    "funds_other": "Фонды прочие",
    "usd": "Валюта (USD)",
    "personal": "Личные",
}

CATEGORY_GROUPS = {
    "Выручка": [
        "Продажи Wildberries", "Продажи OZON", "Оптовые продажи",
        "Возврат маркетинговых расходов", "Возврат оплаты", "Возмещения от клиентов",
    ],
    "Закупки": [
        "Закупка товара", "Закупка расходных материалов",
        "Закупка образцов", "Закупка реквизита",
    ],
    "Логистика": [
        "Логистика до WB", "Логистика до Озон", "Логистика из Китая",
        "Логистика прочая", "Маркировка", "Таможенные платежи", "Фулфилмент",
    ],
    "Маркетинг": [
        "Размещение у блогеров", "Оплата внешних рекламных каналов",
        "Оплата рекламы WB", "Оплата рекламы Озон", "Самовыкупы",
        "Бартерные интеграции", "Доставка блогерам/креаторам",
        "Подарки для блогеров", "Маркетинговые услуги", "Услуги контент-креаторов",
    ],
    "Налоги": [
        "Налог на добавленную стоимость", "Налог на имущество",
        "Налог на прибыль", "Налог на фонд оплаты труда",
    ],
    "ФОТ": [
        "ФОТ Маркетинг", "ФОТ Склад и логистика", "ФОТ управление",
        "HR, найм персонала", "Разовый персонал",
        "Прочие расходы на сотрудников", "Обучение и развитие сотрудников",
    ],
    "Склад": ["Содержание склада", "Аренда помещения"],
    "Услуги": [
        "IT разработка", "Бухгалтерские услуги", "Юридические услуги",
        "Проведение фотосъемок", "Программное обеспечение",
        "Подрядчики", "Фин услуги", "РКО",
    ],
    "Кредиты": [
        "Оплаты по кредитам и займам",
        "Погашение процентов по кредитам и займам",
    ],
}

# Reverse lookup: category name → group name
_CAT_TO_GROUP: dict[str, str] = {}
for _grp, _cats in CATEGORY_GROUPS.items():
    for _c in _cats:
        _CAT_TO_GROUP[_c] = _grp

_MONTH_NAMES_RU = {
    1: "янв", 2: "фев", 3: "мар", 4: "апр", 5: "май", 6: "июн",
    7: "июл", 8: "авг", 9: "сен", 10: "окт", 11: "ноя", 12: "дек",
}
_MONTH_NAMES_RU_FULL = {
    1: "январе", 2: "феврале", 3: "марте", 4: "апреле", 5: "мае", 6: "июне",
    7: "июле", 8: "августе", 9: "сентябре", 10: "октябре", 11: "ноябре", 12: "декабре",
}


def _classify_account(name: str) -> str:
    n = name.lower()
    if "ндс" in n or "фонд ндс" in n:
        return "funds_nds"
    if "налог" in n:
        return "funds_tax"
    if "фот" in n:
        return "funds_payroll"
    if "фонд нз" in n or "резерв" in n:
        return "funds_reserve"
    if "фонд развит" in n or "реинвест" in n:
        return "funds_growth"
    if "фонд" in n:
        return "funds_other"
    if "совместный" in n:
        return "personal"
    if "$" in n or "фридом" in n:
        return "usd"
    return "operating"


def _fmt_rub(v: float) -> str:
    return f"{v:,.0f}".replace(",", " ")


def _fmt_k(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:,.1f}М".replace(",", " ")
    if abs(v) >= 1_000:
        return f"{v / 1_000:,.0f}К".replace(",", " ")
    return f"{v:,.0f}".replace(",", " ")


class FinologService:
    """Async service for Finolog weekly cash flow reports."""

    def __init__(self, api_key: str, biz_id: int = 48556):
        self.api_key = api_key
        self.biz_id = biz_id
        self._headers = {"Api-Token": api_key, "Content-Type": "application/json"}

    async def _get(self, path: str, params: dict = None) -> list | dict:
        async with httpx.AsyncClient(timeout=30, headers=self._headers) as client:
            resp = await client.get(f"{API_BASE}{path}", params=params)
            resp.raise_for_status()
            return resp.json()

    async def _get_accounts(self) -> list[dict]:
        return await self._get(f"/biz/{self.biz_id}/account")

    async def _get_categories(self) -> dict[int, str]:
        cats = await self._get(f"/biz/{self.biz_id}/category")
        return {c["id"]: c["name"] for c in cats}

    async def _get_transactions_month(self, year: int, month: int) -> list[dict]:
        first_day = date(year, month, 1)
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)

        all_txns = []
        page = 1
        while True:
            data = await self._get(f"/biz/{self.biz_id}/transaction", params={
                "report_date_from": str(first_day),
                "report_date_to": str(last_day),
                "per_page": 200,
                "page": page,
            })
            if not data:
                break
            all_txns.extend(data)
            if len(data) < 200:
                break
            page += 1
        return all_txns

    # ── Balances ─────────────────────────────────────────────────

    async def _build_balances(self) -> dict:
        accounts = await self._get_accounts()
        data: dict = {}
        for a in accounts:
            if a.get("is_closed"):
                continue
            summary = a.get("summary", [])
            bal = summary[0].get("balance", 0) if summary else 0
            base_bal = summary[0].get("base_balance", 0) if summary else 0
            cid = a.get("company_id")
            cur_id = a.get("currency_id")
            name = a["name"]
            purpose = _classify_account(name)

            if cid not in data:
                data[cid] = {}
            if purpose not in data[cid]:
                data[cid][purpose] = []

            data[cid][purpose].append({
                "name": name,
                "balance": bal,
                "base_balance": base_bal,
                "currency": "USD" if cur_id == 4 else "RUB",
            })
        return data

    # ── Forecast ─────────────────────────────────────────────────

    async def _build_forecast(self, current_balance_rub: float, months: int = 6) -> list[dict]:
        cat_map = await self._get_categories()
        today = date.today()
        forecast = []

        for i in range(months):
            m = today.month + i
            y = today.year + (m - 1) // 12
            m = ((m - 1) % 12) + 1

            txns = await self._get_transactions_month(y, m)

            group_totals: dict[str, float] = {}
            income_total = 0.0
            expense_total = 0.0

            for t in txns:
                amount = t.get("value", 0) or 0
                cat_id = t.get("category_id")
                cat_name = cat_map.get(cat_id, "Прочие")
                group = _CAT_TO_GROUP.get(cat_name, "Прочие")

                if group not in group_totals:
                    group_totals[group] = 0.0
                group_totals[group] += amount

                if amount > 0:
                    income_total += amount
                else:
                    expense_total += amount

            net = income_total + expense_total
            current_balance_rub += net

            forecast.append({
                "year": y,
                "month": m,
                "label": f"{_MONTH_NAMES_RU[m]} {y}",
                "income": income_total,
                "expense": expense_total,
                "net": net,
                "balance": current_balance_rub,
                "groups": group_totals,
            })

        return forecast

    # ── Main entry point ─────────────────────────────────────────

    async def build_weekly_summary(
        self,
        cash_gap_threshold: float = 1_000_000,
    ) -> tuple[str, str]:
        """
        Build weekly summary.

        Returns (report_md, brief_html):
        - report_md: full Markdown for Notion
        - brief_html: short HTML for Telegram
        """
        today = date.today()
        balances = await self._build_balances()

        # Compute totals
        company_totals: dict[int, dict] = {}
        grand_free = 0.0
        grand_funds = 0.0
        grand_personal = 0.0
        grand_total_base = 0.0

        for cid in COMPANY_ORDER:
            accs = balances.get(cid, {})
            comp_total = 0.0
            comp_free = 0.0
            comp_funds = 0.0
            comp_personal = 0.0

            for purpose in _PURPOSE_ORDER:
                items = accs.get(purpose, [])
                cat_base = sum(i["base_balance"] for i in items)
                comp_total += cat_base
                if purpose == "operating":
                    comp_free += cat_base
                elif purpose in ("personal", "usd"):
                    comp_personal += cat_base
                else:
                    comp_funds += cat_base

            company_totals[cid] = {
                "total": comp_total,
                "free": comp_free,
                "funds": comp_funds,
                "personal": comp_personal,
            }
            grand_free += comp_free
            grand_funds += comp_funds
            grand_personal += comp_personal
            grand_total_base += comp_total

        # Forecast
        forecast = await self._build_forecast(grand_total_base, months=6)

        # Cash gap detection
        cash_gaps = []
        for f in forecast:
            if f["balance"] < cash_gap_threshold:
                cash_gaps.append(f)

        # ── Build Markdown (Notion) ──────────────────────────────

        md_lines = [f"# Сводка ДДС на {today.strftime('%d.%m.%Y')}", ""]
        md_lines.append("## Текущие остатки")
        md_lines.append("")

        for cid in COMPANY_ORDER:
            cname = COMPANY_NAMES.get(cid, f"Company {cid}")
            ct = company_totals.get(cid, {})
            md_lines.append(f"### {cname} — {_fmt_rub(ct.get('total', 0))} ₽")
            md_lines.append("")
            md_lines.append("| Назначение | Счёт | Баланс |")
            md_lines.append("|---|---|---|")

            accs = balances.get(cid, {})
            for purpose in _PURPOSE_ORDER:
                items = accs.get(purpose, [])
                if not items:
                    continue
                label = _PURPOSE_LABELS.get(purpose, purpose)
                for item in sorted(items, key=lambda x: x["base_balance"], reverse=True):
                    bal_str = f"{_fmt_rub(item['balance'])} {item['currency']}"
                    md_lines.append(f"| {label} | {item['name']} | {bal_str} |")
            md_lines.append("")

        md_lines.append("---")
        md_lines.append("")
        md_lines.append(f"**Свободные деньги (операционные):** {_fmt_rub(grand_free)} ₽")
        md_lines.append(f"**Зарезервировано в фондах:** {_fmt_rub(grand_funds)} ₽")
        md_lines.append(f"**Личные + валюта:** {_fmt_rub(grand_personal)} ₽")
        md_lines.append(f"**Всего:** {_fmt_rub(grand_total_base)} ₽")
        md_lines.append("")

        # Forecast table
        md_lines.append("## Прогноз по месяцам")
        md_lines.append("")
        md_lines.append("| Месяц | Приход | Расход | Сальдо | Баланс |")
        md_lines.append("|---|---|---|---|---|")
        for f in forecast:
            sign = "+" if f["net"] >= 0 else ""
            md_lines.append(
                f"| {f['label']} | {_fmt_rub(f['income'])} | {_fmt_rub(f['expense'])} "
                f"| {sign}{_fmt_rub(f['net'])} | {_fmt_rub(f['balance'])} |"
            )
        md_lines.append("")

        # Group detail table
        all_groups = list(CATEGORY_GROUPS.keys()) + ["Прочие"]
        md_lines.append("### Детализация по группам")
        md_lines.append("")
        header = "| Группа | " + " | ".join(f["label"] for f in forecast) + " |"
        sep = "|---|" + "|".join(["---"] * len(forecast)) + "|"
        md_lines.append(header)
        md_lines.append(sep)
        for grp in all_groups:
            vals = []
            has_data = False
            for f in forecast:
                v = f["groups"].get(grp, 0)
                if v != 0:
                    has_data = True
                sign = "+" if v > 0 else ""
                vals.append(f"{sign}{_fmt_k(v)}")
            if has_data:
                md_lines.append(f"| {grp} | " + " | ".join(vals) + " |")
        md_lines.append("")

        # Cash gap
        md_lines.append("## Кассовый разрыв")
        md_lines.append("")
        if not cash_gaps:
            md_lines.append("Кассовый разрыв не прогнозируется на горизонте 6 месяцев.")
        else:
            for g in cash_gaps:
                deficit = cash_gap_threshold - g["balance"]
                month_name = _MONTH_NAMES_RU_FULL[g["month"]]
                md_lines.append(
                    f"**ВНИМАНИЕ: кассовый разрыв в {month_name} {g['year']}!** "
                    f"Прогноз: {_fmt_rub(g['balance'])} ₽ (дефицит {_fmt_rub(deficit)} ₽)"
                )
        md_lines.append("")

        report_md = "\n".join(md_lines)

        # ── Build brief HTML (Telegram) ──────────────────────────

        html = [f"💰 <b>ДДС — сводка на {today.strftime('%d.%m.%Y')}</b>", ""]
        for cid in COMPANY_ORDER:
            cname = COMPANY_NAMES.get(cid, f"Company {cid}")
            ct = company_totals.get(cid, {})
            html.append(f"<b>{cname}</b>  {_fmt_rub(ct.get('total', 0))} ₽")
        html.append("")
        html.append(f"Свободные:  {_fmt_rub(grand_free)} ₽")
        html.append(f"Фонды:      {_fmt_rub(grand_funds)} ₽")
        html.append(f"<b>Всего:      {_fmt_rub(grand_total_base)} ₽</b>")
        html.append("")

        # Forecast one-liner
        html.append("<b>Прогноз баланса:</b>")
        forecast_parts = []
        for f in forecast:
            forecast_parts.append(f"{_MONTH_NAMES_RU[f['month']]} → {_fmt_k(f['balance'])}")
        html.append("  |  ".join(forecast_parts))
        html.append("")

        # Cash gap
        if not cash_gaps:
            html.append("✅ Кассовый разрыв не прогнозируется")
        else:
            for g in cash_gaps:
                deficit = cash_gap_threshold - g["balance"]
                month_name = _MONTH_NAMES_RU_FULL[g["month"]]
                html.append(
                    f"🚨 <b>Кассовый разрыв в {month_name} {g['year']}!</b>\n"
                    f"Прогноз: {_fmt_rub(g['balance'])} ₽ (дефицит {_fmt_rub(deficit)} ₽)"
                )

        brief_html = "\n".join(html)

        return report_md, brief_html

    # ── Transaction helpers (for categorizer) ────────────────────

    async def get_recent_transactions(self, days: int = 2) -> list[dict]:
        """Fetch transactions from the last N days (by report_date), paginated."""
        d_from = date.today() - timedelta(days=days)
        all_txns: list[dict] = []
        page = 1
        while True:
            data = await self._get(f"/biz/{self.biz_id}/transaction", params={
                "report_date_from": str(d_from),
                "report_date_to": str(date.today()),
                "per_page": 200,
                "page": page,
            })
            if not data:
                break
            all_txns.extend(data)
            if len(data) < 200:
                break
            page += 1
        return all_txns

    async def get_uncategorized(self) -> list[dict]:
        """Fetch transactions with category 3 or 4 (Нераспределенные)."""
        results: list[dict] = []
        for cat_id in (3, 4):
            page = 1
            while True:
                data = await self._get(f"/biz/{self.biz_id}/transaction", params={
                    "category_id": cat_id,
                    "per_page": 200,
                    "page": page,
                })
                if not data:
                    break
                results.extend(data)
                if len(data) < 200:
                    break
                page += 1
        return results

    async def get_overdue_planned(self) -> list[dict]:
        """Fetch planned transactions with date < today (overdue)."""
        today = date.today()
        all_txns: list[dict] = []
        page = 1
        while True:
            data = await self._get(f"/biz/{self.biz_id}/transaction", params={
                "report_date_from": str(today - timedelta(days=90)),
                "report_date_to": str(today - timedelta(days=1)),
                "status": "planned",
                "per_page": 200,
                "page": page,
            })
            if not data:
                break
            all_txns.extend(data)
            if len(data) < 200:
                break
            page += 1
        return all_txns

    async def get_contractors(self) -> dict[int, str]:
        """Fetch contractor ID → name mapping."""
        all_contractors: list[dict] = []
        page = 1
        while True:
            data = await self._get(f"/biz/{self.biz_id}/contractor", params={
                "per_page": 200,
                "page": page,
            })
            if not data:
                break
            all_contractors.extend(data)
            if len(data) < 200:
                break
            page += 1
        return {c["id"]: c.get("name", "") for c in all_contractors}

    async def update_transaction(self, txn_id: int, updates: dict) -> dict:
        """PUT /v1/biz/{biz_id}/transaction/{txn_id} — update fields."""
        async with httpx.AsyncClient(timeout=30, headers=self._headers) as client:
            resp = await client.put(
                f"{API_BASE}/biz/{self.biz_id}/transaction/{txn_id}",
                json=updates,
            )
            resp.raise_for_status()
            return resp.json()
