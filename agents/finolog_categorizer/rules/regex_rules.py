"""Regex-based rules for matching transaction descriptions."""
from __future__ import annotations

import re

from .description_rules import (
    CAT_FOT_MKT, CAT_FOT_WAREHOUSE, CAT_FOT_MGMT, CAT_BLOGGERS, CAT_SELFBUYS, CAT_ADS_WB, CAT_ADS_OZON, CAT_ADS_EXTERNAL,
    CAT_TAX_VAT, CAT_TAX_PROFIT, CAT_TAX_PAYROLL, CAT_TAX_PROPERTY,
    CAT_ACCOUNTING, CAT_LEGAL, CAT_RKO, CAT_PHOTO, CAT_PROPS,
    CAT_MARKING, CAT_CUSTOMS, CAT_FULFILLMENT,
    CAT_TRANSFER, CAT_PROCUREMENT, CAT_RENT, CAT_SOFTWARE,
    CAT_LOGISTICS_WB, CAT_LOGISTICS_CHINA, CAT_LOGISTICS_OTHER,
    CAT_DIVIDENDS, CAT_WB, CAT_OZON, CAT_SUPPLIES, CAT_SAMPLES,
    CAT_WAREHOUSE_UPKEEP,
)

REGEX_RULES: list[tuple[re.Pattern, int | None, str]] = [
    # Payroll (detect ФОТ context from description)
    (re.compile(r"Заработная плата.*трудовому договору", re.I), None, "payroll_contract"),
    (re.compile(r"Аванс.*трудовому договору", re.I), None, "payroll_advance"),
    (re.compile(r"Перевод зар\.?платы", re.I), CAT_FOT_MGMT, "payroll_transfer"),
    (re.compile(r"KPI", re.I), None, "payroll_kpi"),
    (re.compile(r"Оплата З/?П\s+\w+", re.I), CAT_FOT_MGMT, "payroll_named_generic"),
    # Content / marketing
    (re.compile(r"Услуги (ретуш|контент)", re.I), None, "content_services_regex"),
    (re.compile(r"Размещение у блогер", re.I), CAT_BLOGGERS, "bloggers"),
    (re.compile(r"^Рекламное размещение у блогера", re.I), CAT_BLOGGERS, "bloggers_placement"),
    (re.compile(r"Самовыкуп", re.I), CAT_SELFBUYS, "selfbuys"),
    (re.compile(r"Оплата рекламы\s*(WB|Wildberries)", re.I), CAT_ADS_WB, "ads_wb"),
    (re.compile(r"Оплата рекламы\s*(Озон|Ozon)", re.I), CAT_ADS_OZON, "ads_ozon"),
    (re.compile(r"пополнение рекламного.*ВК|рекламного кабинета ВК", re.I), CAT_ADS_EXTERNAL, "ads_vk_regex"),
    # Taxes (strict anchored)
    (re.compile(r"^Налог.*добавленную стоимость", re.I), CAT_TAX_VAT, "tax_vat"),
    (re.compile(r"^Уплата НДС", re.I), CAT_TAX_VAT, "tax_vat_payment"),
    (re.compile(r"^Налог.*прибыль", re.I), CAT_TAX_PROFIT, "tax_profit"),
    (re.compile(r"^Налог.*имущество", re.I), CAT_TAX_PROPERTY, "tax_property"),
    (re.compile(r"^Налог.*фонд оплаты", re.I), CAT_TAX_PAYROLL, "tax_payroll"),
    # New tax patterns from analysis
    (re.compile(r"^Взносы на обязательное страхование", re.I), CAT_TAX_PAYROLL, "tax_insurance"),
    (re.compile(r"^Уведомление.*фикс.*страхов.*взнос", re.I), CAT_TAX_PAYROLL, "tax_fixed_insurance"),
    (re.compile(r"^Пополнение единого налогового счета \(НДФЛ", re.I), CAT_TAX_PAYROLL, "tax_ndfl"),
    (re.compile(r"^Единый налоговый платеж \(фикс", re.I), CAT_TAX_PAYROLL, "tax_enp_fixed"),
    (re.compile(r"^Единый налоговый платеж \(доплата", re.I), CAT_TAX_PROFIT, "tax_enp_extra"),
    (re.compile(r"^Единый налоговый платеж \(Доп стр", re.I), CAT_TAX_PROFIT, "tax_enp_extra2"),
    (re.compile(r"^Страховые взносы 1%", re.I), CAT_TAX_PROFIT, "tax_1pct"),
    (re.compile(r"^(Налог УСН|Пополнение.*налог УСН|Уведомление.*налоге? УСН|Налог ИП)", re.I), CAT_TAX_PROFIT, "tax_usn"),
    (re.compile(r"^Единый налоговый платеж\(пени\)", re.I), CAT_TAX_PROFIT, "tax_enp_penalties"),
    # Services
    (re.compile(r"Бухгалтерск", re.I), CAT_ACCOUNTING, "accounting"),
    (re.compile(r"Юридическ", re.I), CAT_LEGAL, "legal"),
    (re.compile(r"^Комиссия за", re.I), CAT_RKO, "rko_commission"),
    (re.compile(r"^Оплата стоимости пакета услуг", re.I), CAT_RKO, "rko_package"),
    (re.compile(r"^Ежемес.*комиссия", re.I), CAT_RKO, "rko_monthly"),
    (re.compile(r"^За услугу.*Выписк", re.I), CAT_RKO, "rko_statement"),
    (re.compile(r"РКО|расчетно.*кассов", re.I), CAT_RKO, "rko"),
    (re.compile(r"(Фотограф|фотограф).*фотосъемк", re.I), CAT_PHOTO, "photo_photographer"),
    (re.compile(r"Фотосъемк|фотосесси", re.I), CAT_PHOTO, "photo"),
    (re.compile(r"^Услуги модел", re.I), CAT_PHOTO, "photo_model"),
    (re.compile(r"^Предоплата фотограф", re.I), CAT_PHOTO, "photo_prepay"),
    (re.compile(r"^Реквизит для съемки", re.I), CAT_PROPS, "props_shoot"),
    # Logistics
    (re.compile(r"Маркировка", re.I), CAT_MARKING, "marking"),
    (re.compile(r"Таможен", re.I), CAT_CUSTOMS, "customs"),
    (re.compile(r"Фулфилмент", re.I), CAT_FULFILLMENT, "fulfillment"),
    (re.compile(r"^Логистика до В[Бб]", re.I), CAT_LOGISTICS_WB, "logistics_wb_alt"),
    (re.compile(r"^Доставка до склада В[Бб]", re.I), CAT_LOGISTICS_WB, "logistics_wb_delivery"),
    (re.compile(r"^Доставка товара в офис.*PEK", re.I), CAT_LOGISTICS_CHINA, "logistics_pek"),
    (re.compile(r"СДЭК|СДЕК|CDEK", re.I), CAT_LOGISTICS_OTHER, "logistics_cdek"),
    # Transfers
    (re.compile(r"Перевод собственных средств", re.I), CAT_TRANSFER, "transfer_own"),
    (re.compile(r"Перевод.*на другой счет", re.I), CAT_TRANSFER, "transfer_other"),
    # Procurement — FIXED: negative lookahead to skip card payments
    (re.compile(r"Покупка товар(?!.*Терминал:)", re.I), CAT_PROCUREMENT, "procurement_buy"),
    # Rent / lease
    (re.compile(r"(суб)?аренд.*помещен|ДОГОВОРУ.*АРЕНДЫ", re.I), CAT_RENT, "rent_lease"),
    # SaaS / subscriptions (generic)
    (re.compile(r"Финолог|финолог", re.I), CAT_SOFTWARE, "saas_finolog"),
    (re.compile(r"Аренда кассы|онлайн.?касс", re.I), CAT_SOFTWARE, "saas_cash_register"),
    # OZON
    (re.compile(r"^(ОПЛАТА|Оплата) ЗА ТОВ.*ДОГ.*ИР-", re.I), CAT_OZON, "ozon_invoice_regex"),
    # WB wholesale
    (re.compile(r"^Оплата по договору.*за товар", re.I), CAT_WB, "wb_wholesale"),
    # Dividends
    (re.compile(r"^Выплата дивидендов", re.I), CAT_DIVIDENDS, "dividends_regex"),
    # ── Card payments: unambiguous description hints ──
    # Supplies (clear intent in description)
    (re.compile(r"(Пакет|пакет).*(пвз|ВБ|вб)", re.I), CAT_SUPPLIES, "card_supplies_packet"),
    (re.compile(r"(Скотч|скотч).*(офис|для)", re.I), CAT_SUPPLIES, "card_supplies_scotch"),
    (re.compile(r"(Маркер|маркер).*офис", re.I), CAT_SUPPLIES, "card_supplies_markers"),
    (re.compile(r"(Зарядк|зарядк).*офис", re.I), CAT_SUPPLIES, "card_supplies_charger"),
    (re.compile(r"(Жесткий диск|жесткий диск)", re.I), CAT_SUPPLIES, "card_supplies_hdd"),
    (re.compile(r"Наполнитель для бокса", re.I), CAT_SUPPLIES, "card_supplies_filler"),
    # Samples
    (re.compile(r"(Образц|образц).*(бел|тест|качеств)", re.I), CAT_SAMPLES, "card_samples"),
    (re.compile(r"(Покупка|Закупка) белья для тест", re.I), CAT_SAMPLES, "card_samples_buy"),
    (re.compile(r"^Белье для тест", re.I), CAT_SAMPLES, "card_samples_linen_test"),
    # Warehouse misc
    (re.compile(r"(Стеллаж|стеллаж).*офис", re.I), CAT_WAREHOUSE_UPKEEP, "card_warehouse_shelf"),
    (re.compile(r"(Папки|папки).*документ", re.I), CAT_WAREHOUSE_UPKEEP, "card_warehouse_folders"),
    (re.compile(r"доп (затраты|траты) на вб", re.I), CAT_WAREHOUSE_UPKEEP, "card_warehouse_wb_extra"),
    (re.compile(r"Обратная платная доставка", re.I), CAT_LOGISTICS_OTHER, "card_return_delivery"),
]

PAYROLL_PERSON_MAP: dict[str, int] = {
    "корабец": CAT_FOT_MKT,
    "делова": CAT_FOT_MKT,
    "светлана": CAT_FOT_MKT,
    "мария": CAT_FOT_MKT,
    "агабалян": CAT_FOT_MKT,
    "гасанова": CAT_FOT_MKT,
    "вик": CAT_FOT_MKT,
    "татьяна": CAT_FOT_WAREHOUSE,
    "склад": CAT_FOT_WAREHOUSE,
    "дрозд": CAT_FOT_WAREHOUSE,
    "бахаев": CAT_FOT_WAREHOUSE,
    "жен": CAT_FOT_WAREHOUSE,
    "данил": CAT_FOT_MGMT,
    "полин": CAT_FOT_MGMT,
    "валери": CAT_FOT_MGMT,
    "лер": CAT_FOT_MGMT,
    "матвеев": CAT_FOT_MGMT,
}
