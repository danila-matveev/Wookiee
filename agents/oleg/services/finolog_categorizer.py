"""
Finolog auto-categorizer: rule engine + LLM fallback for transaction classification.

Scans new/uncategorized transactions, suggests category + report_date,
stores suggestions for user approval.
"""
from __future__ import annotations

import calendar
import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ── Category IDs ─────────────────────────────────────────────────

CAT_WB = 980528            # Продажи Wildberries
CAT_OZON = 1100877         # Продажи OZON
CAT_WHOLESALE = 1127238    # Оптовые продажи
CAT_RETURN_MKT = 1411425   # Возврат маркетинговых расходов
CAT_RETURN_PAY = 1017419   # Возврат оплаты
CAT_REIMBURSEMENT = 1384800  # Возмещения от клиентов

CAT_FOT_MKT = 980473       # ФОТ Маркетинг
CAT_FOT_WAREHOUSE = 983733 # ФОТ Склад и логистика
CAT_FOT_MGMT = 983734      # ФОТ управление
CAT_HR = 980581             # HR, найм персонала
CAT_TEMP_STAFF = 1296612   # Разовый персонал
CAT_STAFF_OTHER = 1361543  # Прочие расходы на сотрудников
CAT_TRAINING = 997243      # Обучение и развитие сотрудников

CAT_SOFTWARE = 980585       # Программное обеспечение
CAT_IT_DEV = 1296610       # IT разработка
CAT_ACCOUNTING = 1296608   # Бухгалтерские услуги
CAT_LEGAL = 1100876        # Юридические услуги
CAT_CONTRACTORS = 980478   # Подрядчики
CAT_FIN_SERVICES = 1296609 # Фин услуги
CAT_RKO = 980547           # РКО
CAT_PHOTO = 980626         # Проведение фотосъемок
CAT_MKT_SERVICES = 1296611 # Маркетинговые услуги

CAT_LOGISTICS_WB = 983687  # Логистика до WB
CAT_LOGISTICS_OZON = 1100873  # Логистика до Озон
CAT_LOGISTICS_CHINA = 983688  # Логистика из Китая
CAT_LOGISTICS_OTHER = 983692  # Логистика прочая
CAT_MARKING = 1224193      # Маркировка
CAT_CUSTOMS = 1258263      # Таможенные платежи
CAT_FULFILLMENT = 1378535  # Фулфилмент

CAT_PROCUREMENT = 980563   # Закупка товара
CAT_SUPPLIES = 980566      # Закупка расходных материалов
CAT_SAMPLES = 1301315      # Закупка образцов
CAT_PROPS = 1361538        # Закупка реквизита

CAT_BLOGGERS = 980476      # Размещение у блогеров
CAT_ADS_EXTERNAL = 983691  # Оплата внешних рекламных каналов
CAT_ADS_WB = 1100874       # Оплата рекламы WB
CAT_ADS_OZON = 1100875     # Оплата рекламы Озон
CAT_SELFBUYS = 1011584     # Самовыкупы
CAT_BARTER = 1290324       # Бартерные интеграции
CAT_DELIVERY_BLOGGERS = 1245555  # Доставка блогерам/креаторам
CAT_GIFTS_BLOGGERS = 1242155  # Подарки для блогеров
CAT_CONTENT_CREATORS = 1169453  # Услуги контент-креаторов

CAT_RENT = 980475          # Аренда помещения
CAT_WAREHOUSE_UPKEEP = 983689  # Содержание склада

CAT_TAX_VAT = 980465       # НДС
CAT_TAX_PROPERTY = 980467  # Налог на имущество
CAT_TAX_PROFIT = 980468    # Налог на прибыль
CAT_TAX_PAYROLL = 980466   # Налог на ФОТ

CAT_CREDIT_PAY = 980477    # Оплаты по кредитам и займам
CAT_CREDIT_INTEREST = 1127219  # Погашение процентов по кредитам

CAT_TRANSFER = 1           # Перевод между счетами
CAT_UNCLASSIFIED_IN = 3    # Нераспределенные приходы
CAT_UNCLASSIFIED_OUT = 4   # Нераспределенные расходы

CAT_PROFIT_WITHDRAW = 980471  # Вывод прибыли
CAT_DIVIDENDS = 980472     # Выплата дивидендов
CAT_OPS_OTHER = 1369300    # Прочие операционные расходы

# ФОТ categories (need accrual logic)
FOT_CATEGORIES = {
    CAT_FOT_MKT, CAT_FOT_WAREHOUSE, CAT_FOT_MGMT,
    CAT_HR, CAT_TEMP_STAFF, CAT_STAFF_OTHER, CAT_TRAINING,
}

# ── Description rules (exact prefix match, order matters: specific first) ──

DESCRIPTION_RULES: list[tuple[str, int, str]] = [
    # Revenue
    ("Выручка ООО Озон", CAT_OZON, "revenue_ooo_ozon"),
    ("Выручка ИП Озон", CAT_OZON, "revenue_ip_ozon"),
    ("Выручка ООО", CAT_WB, "revenue_ooo_wb"),
    ("Выручка ИП", CAT_WB, "revenue_ip_wb"),
    # Logistics
    ("Логистика до Озон", CAT_LOGISTICS_OZON, "logistics_ozon"),
    ("Логистика до WB", CAT_LOGISTICS_WB, "logistics_wb"),
    ("Логистика из Китая", CAT_LOGISTICS_CHINA, "logistics_china"),
    ("Логистика прочая", CAT_LOGISTICS_OTHER, "logistics_other"),
    # Named payroll
    ("Оплата ЗП Данилы", CAT_FOT_MGMT, "payroll_danila"),
    ("Оплата ЗП Полины", CAT_FOT_MGMT, "payroll_polina"),
    ("Оплата ЗП Леры", CAT_FOT_MGMT, "payroll_lera"),
    # Specific consultants
    ("Оплата за консультационные услуги по разработке продукта", CAT_FOT_MKT, "consult_product"),
    ("Оплата за консультационные услуги по финансовому анализу", CAT_FOT_MGMT, "consult_finance"),
    # SaaS
    ("ChatGPT", CAT_SOFTWARE, "saas_chatgpt"),
    ("Notion AI", CAT_SOFTWARE, "saas_notion"),
    ("Kimi AI", CAT_SOFTWARE, "saas_kimi"),
    ("Midjourney", CAT_SOFTWARE, "saas_midjourney"),
    ("Тех.поддержка", CAT_SOFTWARE, "saas_tech_support"),
    # Content/services
    ("Услуги ретушера", CAT_FOT_MKT, "retoucher"),
    ("Услуги контент-мейкеров", CAT_CONTENT_CREATORS, "content_makers"),
    ("Услуги контент-креаторов", CAT_CONTENT_CREATORS, "content_creators"),
    ("Услуги проверки качества товаров", CAT_FOT_WAREHOUSE, "quality_check"),
    ("Услуги по фулфилменту и логистике", CAT_FOT_WAREHOUSE, "fulfillment_services"),
    # Warehouse / rent
    ("Аренда помещения", CAT_RENT, "rent"),
    ("Содержание склада", CAT_WAREHOUSE_UPKEEP, "warehouse"),
    # Credit
    ("Оплаты по кредитам", CAT_CREDIT_PAY, "credit_payment"),
    ("Погашение процентов", CAT_CREDIT_INTEREST, "credit_interest"),
    # Procurement
    ("Закупка товара", CAT_PROCUREMENT, "procurement"),
    ("Закупка расходных", CAT_SUPPLIES, "supplies"),
    ("Закупка образцов", CAT_SAMPLES, "samples"),
    # Internal transfers
    ("Перевод собственных средств", CAT_TRANSFER, "internal_transfer"),
]

# ── Regex rules (for partial/complex matches) ──

REGEX_RULES: list[tuple[re.Pattern, int | None, str]] = [
    # Payroll (detect ФОТ context from description)
    (re.compile(r"Заработная плата.*трудовому договору", re.I), None, "payroll_contract"),
    (re.compile(r"Аванс.*трудовому договору", re.I), None, "payroll_advance"),
    (re.compile(r"Перевод зар\.?платы", re.I), CAT_FOT_MGMT, "payroll_transfer"),
    (re.compile(r"KPI", re.I), None, "payroll_kpi"),
    (re.compile(r"Оплата ЗП\s+\w+", re.I), CAT_FOT_MGMT, "payroll_named_generic"),
    # Content / marketing
    (re.compile(r"Услуги (ретуш|контент)", re.I), None, "content_services_regex"),
    (re.compile(r"Размещение у блогер", re.I), CAT_BLOGGERS, "bloggers"),
    (re.compile(r"Самовыкуп", re.I), CAT_SELFBUYS, "selfbuys"),
    (re.compile(r"Оплата рекламы\s*(WB|Wildberries)", re.I), CAT_ADS_WB, "ads_wb"),
    (re.compile(r"Оплата рекламы\s*(Озон|Ozon)", re.I), CAT_ADS_OZON, "ads_ozon"),
    # Taxes (strict: must start with "Налог" or be a standalone НДС payment, not just mention "НДС" in invoice text)
    (re.compile(r"^Налог.*добавленную стоимость", re.I), CAT_TAX_VAT, "tax_vat"),
    (re.compile(r"^Уплата НДС", re.I), CAT_TAX_VAT, "tax_vat_payment"),
    (re.compile(r"^Налог.*прибыль", re.I), CAT_TAX_PROFIT, "tax_profit"),
    (re.compile(r"^Налог.*имущество", re.I), CAT_TAX_PROPERTY, "tax_property"),
    (re.compile(r"^Налог.*фонд оплаты", re.I), CAT_TAX_PAYROLL, "tax_payroll"),
    # Services
    (re.compile(r"Бухгалтерск", re.I), CAT_ACCOUNTING, "accounting"),
    (re.compile(r"Юридическ", re.I), CAT_LEGAL, "legal"),
    (re.compile(r"РКО|расчетно.*кассов", re.I), CAT_RKO, "rko"),
    (re.compile(r"Фотосъемк|фотосесси", re.I), CAT_PHOTO, "photo"),
    # Logistics
    (re.compile(r"Маркировка", re.I), CAT_MARKING, "marking"),
    (re.compile(r"Таможен", re.I), CAT_CUSTOMS, "customs"),
    (re.compile(r"Фулфилмент", re.I), CAT_FULFILLMENT, "fulfillment"),
    # Transfers
    (re.compile(r"Перевод собственных средств", re.I), CAT_TRANSFER, "transfer_own"),
    (re.compile(r"Перевод.*на другой счет", re.I), CAT_TRANSFER, "transfer_other"),
    # Procurement
    (re.compile(r"Покупка товар", re.I), CAT_PROCUREMENT, "procurement_buy"),
    # Rent / lease
    (re.compile(r"(суб)?аренд.*помещен|ДОГОВОРУ.*АРЕНДЫ", re.I), CAT_RENT, "rent_lease"),
    # SaaS / subscriptions (generic)
    (re.compile(r"Финолог|финолог", re.I), CAT_SOFTWARE, "saas_finolog"),
    (re.compile(r"Аренда кассы|онлайн.?касс", re.I), CAT_SOFTWARE, "saas_cash_register"),
    (re.compile(r"Taplink|тариф.*Pro", re.I), CAT_SOFTWARE, "saas_taplink"),
]

# Payroll context: detect which ФОТ category based on person's name/role
_PAYROLL_PERSON_MAP: dict[str, int] = {
    "корабец": CAT_FOT_MKT,
    "делова": CAT_FOT_MKT,
    "светлана": CAT_FOT_MKT,
    "мария": CAT_FOT_MKT,
    "татьяна": CAT_FOT_WAREHOUSE,
    "склад": CAT_FOT_WAREHOUSE,
    "данил": CAT_FOT_MGMT,
    "полин": CAT_FOT_MGMT,
    "валери": CAT_FOT_MGMT,
    "лер": CAT_FOT_MGMT,
    "матвеев": CAT_FOT_MGMT,
}


@dataclass
class Suggestion:
    txn_id: int
    txn_date: str
    txn_description: str
    txn_value: float
    txn_contractor_id: int | None
    category_id: int
    report_date: str
    confidence: float
    rule_name: str


@dataclass
class ScanResult:
    already_categorized: int = 0
    already_suggested: int = 0
    suggestions: list[Suggestion] = field(default_factory=list)
    overdue_planned: list[dict] = field(default_factory=list)


def _resolve_payroll_category(description: str) -> int:
    """Determine which ФОТ category based on person name in description."""
    desc_lower = description.lower()
    for keyword, cat_id in _PAYROLL_PERSON_MAP.items():
        if keyword in desc_lower:
            return cat_id
    return CAT_FOT_MGMT  # default


def _last_day_prev_month(d: date) -> date:
    """Return last day of the month before d."""
    first_of_month = d.replace(day=1)
    return first_of_month - timedelta(days=1)


def compute_report_date(txn_date_str: str, category_id: int) -> str:
    """Compute accrual-based report_date for a transaction."""
    try:
        txn_date = date.fromisoformat(txn_date_str[:10])
    except (ValueError, TypeError):
        return txn_date_str[:10]

    # Payroll: report_date = last day of previous month
    if category_id in FOT_CATEGORIES:
        return str(_last_day_prev_month(txn_date))

    # Default: cash-basis (report_date = date)
    return str(txn_date)


def classify(txn: dict, learned_rules: list[dict] = None) -> Optional[Suggestion]:
    """
    Classify a single transaction using rule engine.

    Returns Suggestion or None if cannot classify.
    """
    desc = (txn.get("description") or "").strip()
    txn_id = txn.get("id", 0)
    txn_date = (txn.get("date") or "")[:10]
    txn_value = txn.get("value", 0)
    txn_contractor = txn.get("contractor_id")

    if not desc:
        return None

    # 1. Exact description prefix match
    for prefix, cat_id, rule_name in DESCRIPTION_RULES:
        if desc.startswith(prefix) or desc == prefix:
            report_date = compute_report_date(txn_date, cat_id)
            return Suggestion(
                txn_id=txn_id, txn_date=txn_date, txn_description=desc,
                txn_value=txn_value, txn_contractor_id=txn_contractor,
                category_id=cat_id, report_date=report_date,
                confidence=0.95, rule_name=rule_name,
            )

    # 2. Regex match
    for pattern, cat_id, rule_name in REGEX_RULES:
        if pattern.search(desc):
            # Resolve category for payroll rules that need context
            if cat_id is None:
                if "payroll" in rule_name or "kpi" in rule_name:
                    cat_id = _resolve_payroll_category(desc)
                elif "content" in rule_name:
                    cat_id = CAT_CONTENT_CREATORS
                else:
                    continue  # skip if we can't resolve

            report_date = compute_report_date(txn_date, cat_id)
            return Suggestion(
                txn_id=txn_id, txn_date=txn_date, txn_description=desc,
                txn_value=txn_value, txn_contractor_id=txn_contractor,
                category_id=cat_id, report_date=report_date,
                confidence=0.85, rule_name=rule_name,
            )

    # 3. Learned rules from store
    if learned_rules:
        desc_lower = desc[:50].lower()
        for rule in learned_rules:
            if desc_lower.startswith(rule["pattern"]):
                cat_id = rule["category_id"]
                report_date = compute_report_date(txn_date, cat_id)
                return Suggestion(
                    txn_id=txn_id, txn_date=txn_date, txn_description=desc,
                    txn_value=txn_value, txn_contractor_id=txn_contractor,
                    category_id=cat_id, report_date=report_date,
                    confidence=0.75, rule_name=f"learned:{rule['pattern'][:30]}",
                )

    return None


class FinologCategorizer:
    """Orchestrates daily transaction scanning and categorization."""

    def __init__(self, finolog_service, store=None):
        self.svc = finolog_service
        self.store = store

    async def run_daily_scan(self) -> ScanResult:
        """
        Scan recent + uncategorized transactions, classify each.

        Returns ScanResult with suggestions.
        """
        result = ScanResult()

        # Fetch learned rules
        learned_rules = self.store.get_learned_rules() if self.store else []

        # Fetch categories map for display
        cat_map = await self.svc._get_categories()

        # Fetch recent transactions + uncategorized
        recent = await self.svc.get_recent_transactions(days=2)
        uncategorized = await self.svc.get_uncategorized()

        # Merge and deduplicate by txn_id
        seen_ids: set[int] = set()
        to_process: list[dict] = []
        for txn in recent + uncategorized:
            tid = txn.get("id")
            if tid and tid not in seen_ids:
                seen_ids.add(tid)
                to_process.append(txn)

        logger.info(f"Categorizer: {len(to_process)} transactions to process")

        for txn in to_process:
            cat_id = txn.get("category_id")

            # Skip already categorized (not 3/4)
            if cat_id and cat_id not in (CAT_UNCLASSIFIED_IN, CAT_UNCLASSIFIED_OUT):
                result.already_categorized += 1
                continue

            # Skip if already suggested
            if self.store and self.store.already_suggested(txn["id"]):
                result.already_suggested += 1
                continue

            # Classify
            suggestion = classify(txn, learned_rules)
            if suggestion:
                result.suggestions.append(suggestion)
                # Save to store
                if self.store:
                    self.store.save_suggestion(
                        txn_id=suggestion.txn_id,
                        txn_date=suggestion.txn_date,
                        txn_description=suggestion.txn_description,
                        txn_value=suggestion.txn_value,
                        txn_contractor_id=suggestion.txn_contractor_id,
                        suggested_category_id=suggestion.category_id,
                        suggested_report_date=suggestion.report_date,
                        confidence=suggestion.confidence,
                        rule_name=suggestion.rule_name,
                    )

        # Detect overdue planned
        try:
            overdue = await self.svc.get_overdue_planned()
            result.overdue_planned = overdue
        except Exception as e:
            logger.warning(f"Overdue planned check failed: {e}")

        return result

    def format_scan_summary_html(self, result: ScanResult, cat_map: dict[int, str]) -> str:
        """Format scan result as HTML for Telegram."""
        lines = ["📋 <b>Finolog: сканирование операций</b>", ""]
        lines.append(f"Всего обработано: {result.already_categorized + len(result.suggestions) + result.already_suggested}")
        lines.append(f"✅ Уже категоризировано: {result.already_categorized}")
        if result.already_suggested:
            lines.append(f"⏭ Уже предложено ранее: {result.already_suggested}")
        lines.append(f"🤔 Новых предложений: {len(result.suggestions)}")
        if result.overdue_planned:
            lines.append(f"⏰ Просроченных плановых: {len(result.overdue_planned)}")
        lines.append("")

        # Suggestions detail
        for s in result.suggestions:
            cat_name = cat_map.get(s.category_id, f"#{s.category_id}")
            sign = "+" if s.txn_value > 0 else ""
            lines.append(
                f"💳 <i>{s.txn_description[:60]}</i>\n"
                f"   {sign}{s.txn_value:,.0f} ₽ | {s.txn_date}\n"
                f"   → <b>{cat_name}</b> | report: {s.report_date}\n"
                f"   🎯 {s.confidence:.0%} ({s.rule_name})"
            )
            lines.append("")

        # Overdue
        if result.overdue_planned:
            lines.append("⏰ <b>Просроченные плановые:</b>")
            for t in result.overdue_planned[:10]:
                d = (t.get("date") or "")[:10]
                desc = (t.get("description") or "")[:40]
                val = t.get("value", 0)
                lines.append(f"  • {desc} — план {d}, {val:,.0f} ₽")

        return "\n".join(lines)
