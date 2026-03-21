"""Finolog transaction description prefix rules.

Each entry in DESCRIPTION_RULES is a (prefix, category_id, rule_name) tuple.
The categoriser walks the list top-to-bottom and returns the first match whose
prefix is found at the start of the transaction description.

ORDER MATTERS: more specific prefixes must come before less specific ones
(e.g. "Контур.НДС+" before "Контур.").
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Finolog category-ID constants
# ---------------------------------------------------------------------------

# Revenue
CAT_WB = 980528                    # Продажи Wildberries
CAT_OZON = 1100877                 # Продажи OZON
CAT_WHOLESALE = 1127238            # Оптовые продажи
CAT_RETURN_MKT = 1411425           # Возврат маркетинговых расходов
CAT_RETURN_PAY = 1017419           # Возврат оплаты
CAT_REIMBURSEMENT = 1384800        # Возмещения от клиентов

# Payroll (ФОТ)
CAT_FOT_MKT = 980473               # ФОТ Маркетинг
CAT_FOT_WAREHOUSE = 983733         # ФОТ Склад и логистика
CAT_FOT_MGMT = 983734              # ФОТ управление
CAT_HR = 980581                    # HR, найм персонала
CAT_TEMP_STAFF = 1296612           # Разовый персонал
CAT_STAFF_OTHER = 1361543          # Прочие расходы на сотрудников
CAT_TRAINING = 997243              # Обучение и развитие сотрудников

# Services & SaaS
CAT_SOFTWARE = 980585              # Программное обеспечение
CAT_IT_DEV = 1296610               # IT разработка
CAT_ACCOUNTING = 1296608           # Бухгалтерские услуги
CAT_LEGAL = 1100876                # Юридические услуги
CAT_CONTRACTORS = 980478           # Подрядчики
CAT_FIN_SERVICES = 1296609         # Фин услуги
CAT_RKO = 980547                   # РКО
CAT_PHOTO = 980626                 # Проведение фотосъемок
CAT_MKT_SERVICES = 1296611         # Маркетинговые услуги

# Logistics & fulfilment
CAT_LOGISTICS_WB = 983687          # Логистика до WB
CAT_LOGISTICS_OZON = 1100873       # Логистика до Озон
CAT_LOGISTICS_CHINA = 983688       # Логистика из Китая
CAT_LOGISTICS_OTHER = 983692       # Логистика прочая
CAT_MARKING = 1224193              # Маркировка
CAT_CUSTOMS = 1258263              # Таможенные платежи
CAT_FULFILLMENT = 1378535          # Фулфилмент

# Procurement
CAT_PROCUREMENT = 980563           # Закупка товара
CAT_SUPPLIES = 980566              # Закупка расходных материалов
CAT_SAMPLES = 1301315              # Закупка образцов
CAT_PROPS = 1361538                # Закупка реквизита

# Marketing & advertising
CAT_BLOGGERS = 980476              # Размещение у блогеров
CAT_ADS_EXTERNAL = 983691          # Оплата внешних рекламных каналов
CAT_ADS_WB = 1100874               # Оплата рекламы WB
CAT_ADS_OZON = 1100875             # Оплата рекламы Озон
CAT_SELFBUYS = 1011584             # Самовыкупы
CAT_BARTER = 1290324               # Бартерные интеграции
CAT_DELIVERY_BLOGGERS = 1245555    # Доставка блогерам/креаторам
CAT_GIFTS_BLOGGERS = 1242155       # Подарки для блогеров
CAT_CONTENT_CREATORS = 1169453     # Услуги контент-креаторов

# Office & warehouse
CAT_RENT = 980475                  # Аренда помещения
CAT_WAREHOUSE_UPKEEP = 983689      # Содержание склада

# Taxes
CAT_TAX_VAT = 980465               # НДС
CAT_TAX_PROPERTY = 980467          # Налог на имущество
CAT_TAX_PROFIT = 980468            # Налог на прибыль
CAT_TAX_PAYROLL = 980466           # Налог на ФОТ

# Credit
CAT_CREDIT_PAY = 980477            # Оплаты по кредитам и займам
CAT_CREDIT_INTEREST = 1127219      # Погашение процентов по кредитам

# Transfers & unclassified
CAT_TRANSFER = 1                   # Перевод между счетами
CAT_UNCLASSIFIED_IN = 3            # Нераспределенные приходы
CAT_UNCLASSIFIED_OUT = 4           # Нераспределенные расходы

# Profit & other
CAT_PROFIT_WITHDRAW = 980471       # Вывод прибыли
CAT_DIVIDENDS = 980472             # Выплата дивидендов
CAT_OPS_OTHER = 1369300            # Прочие операционные расходы

# ---------------------------------------------------------------------------
# ФОТ categories set (categories that need accrual logic)
# ---------------------------------------------------------------------------

FOT_CATEGORIES: set[int] = {
    CAT_FOT_MKT,
    CAT_FOT_WAREHOUSE,
    CAT_FOT_MGMT,
    CAT_HR,
    CAT_TEMP_STAFF,
    CAT_STAFF_OTHER,
    CAT_TRAINING,
}

# ---------------------------------------------------------------------------
# Description prefix rules
# ---------------------------------------------------------------------------
# Each tuple: (prefix, category_id, rule_name)
# First match wins — keep more specific prefixes above less specific ones.

DESCRIPTION_RULES: list[tuple[str, int, str]] = [
    # ── Revenue ──────────────────────────────────────────────────────────
    ("Выручка ООО Озон", CAT_OZON, "revenue_ooo_ozon"),
    ("Выручка ИП Озон", CAT_OZON, "revenue_ip_ozon"),
    ("Выручка ООО", CAT_WB, "revenue_ooo_wb"),
    ("Выручка ИП", CAT_WB, "revenue_ip_wb"),

    # ── OZON invoices ────────────────────────────────────────────────────
    ("Оплата за тов. по дог. ИР-", CAT_OZON, "ozon_invoice"),
    ("ОПЛАТА ЗА ТОВ. ПО ДОГ. ИР-", CAT_OZON, "ozon_invoice_upper"),
    ("по договору ИР-", CAT_OZON, "ozon_invoice_contract"),
    ("Платеж по ден.треб.", CAT_OZON, "ozon_payment_req"),

    # ── Logistics ────────────────────────────────────────────────────────
    ("Логистика до Озон", CAT_LOGISTICS_OZON, "logistics_ozon"),
    ("Логистика до WB", CAT_LOGISTICS_WB, "logistics_wb"),
    ("Логистика до ВБ", CAT_LOGISTICS_WB, "logistics_vb"),
    ("Логистика из Китая", CAT_LOGISTICS_CHINA, "logistics_china"),
    ("Логистика прочая", CAT_LOGISTICS_OTHER, "logistics_other"),
    ("Доставка белья блогеру", CAT_LOGISTICS_OTHER, "logistics_blogger_delivery"),
    ("Доставка до склада ВБ", CAT_LOGISTICS_WB, "logistics_wb_delivery"),
    ("Отправка белья СДЕК", CAT_LOGISTICS_OTHER, "logistics_cdek_linen"),

    # ── Named payroll (specific names first) ─────────────────────────────
    ("Оплата З/П Татьяна Владимировна", CAT_FOT_WAREHOUSE, "payroll_tatyana"),
    ("Оплата ЗП Данилы", CAT_FOT_MGMT, "payroll_danila"),
    ("Оплата З/П Данилы", CAT_FOT_MGMT, "payroll_danila2"),
    ("Оплата ЗП Полины", CAT_FOT_MGMT, "payroll_polina"),
    ("Оплата З/П Полины", CAT_FOT_MGMT, "payroll_polina2"),
    ("Оплата З/П Матвеева Валерия", CAT_FOT_MGMT, "payroll_valeriy"),
    ("Оплата ЗП Леры", CAT_FOT_MGMT, "payroll_lera"),

    # ── Consultancy -> ФОТ Маркетинг ────────────────────────────────────
    ("Оплата за консультационные услуги по рекламным кампаниям", CAT_FOT_MKT, "consult_ads"),
    ("Оплата за консультационные услуги по управлению рекламными", CAT_FOT_MKT, "consult_ad_mgmt"),
    ("Оплата за консультационные услуги по разработке продукта", CAT_FOT_MKT, "consult_product"),
    ("Оплата за предоставление консультационных услуг по контент", CAT_FOT_MKT, "consult_content2"),
    ("Оказание консультационных услуг по подбору блогеров", CAT_FOT_MKT, "consult_bloggers"),
    ("Оказание консультационных услуг по подбору и внедрению товарных", CAT_FOT_MKT, "consult_products"),
    ("Оказание консультационных услуг по ведению маркетплейсов", CAT_FOT_MKT, "consult_mp"),
    ("Консультационные услуги по созданию контента", CAT_FOT_MKT, "consult_content"),
    ("За консультационные услуги по маркетингу в социальных сетях", CAT_FOT_MKT, "consult_smm"),

    # ── Consultancy -> ФОТ управление ────────────────────────────────────
    ("Оплата за консультационные услуги по финансовому анализу", CAT_FOT_MGMT, "consult_finance"),
    ("Оказание консультационных услуг по удаленному ассистированию", CAT_FOT_MGMT, "consult_assistant"),
    ("Оплата за консультационные услуги по разработке регламентов", CAT_FOT_MGMT, "consult_regs"),

    # ── Content / services ───────────────────────────────────────────────
    ("Услуги контент-креатора по созданию видео", CAT_CONTENT_CREATORS, "content_creator_video"),
    ("Услуги контент-мейкера по созданию видео", CAT_CONTENT_CREATORS, "content_maker_video"),
    ("Услуги контент-мейкеров", CAT_CONTENT_CREATORS, "content_makers"),
    ("Услуги контент-креаторов", CAT_CONTENT_CREATORS, "content_creators"),
    ("Услуги ретушера", CAT_FOT_MKT, "retoucher"),
    ("Услуги проверки качества товаров", CAT_FOT_WAREHOUSE, "quality_check"),
    ("Услуги по фулфилменту и логистике", CAT_FOT_WAREHOUSE, "fulfillment_services"),
    ("Услуги маркировки товаров", CAT_TEMP_STAFF, "temp_marking"),
    ("Услуги копирайтера", CAT_CONTRACTORS, "contractors_copy"),
    ("Услуги фотографа", CAT_PHOTO, "photo_photographer"),

    # ── SaaS / Software (specific first) ─────────────────────────────────
    ("ChatGPT", CAT_SOFTWARE, "saas_chatgpt"),
    ("Notion AI", CAT_SOFTWARE, "saas_notion"),
    ("Оплата Notion", CAT_SOFTWARE, "saas_notion_pay"),
    ("Kimi AI", CAT_SOFTWARE, "saas_kimi"),
    ("Midjourney", CAT_SOFTWARE, "saas_midjourney"),
    ("Тех.поддержка", CAT_SOFTWARE, "saas_tech_support"),
    ("Canva 1 мес", CAT_SOFTWARE, "saas_canva"),
    ("Мой склад на 12 месяцев", CAT_SOFTWARE, "saas_moysklad"),
    ("Контур.НДС+", CAT_SOFTWARE, "saas_kontur_nds"),
    ("Контур.", CAT_SOFTWARE, "saas_kontur"),
    ("Диадок ООО на 12 месяцев", CAT_SOFTWARE, "saas_diadok"),
    ("Достависта пополнение счета", CAT_SOFTWARE, "saas_dostavista"),
    ("Оплата системы Квант", CAT_SOFTWARE, "saas_quant"),
    ("Taplink тариф Pro", CAT_SOFTWARE, "saas_taplink"),

    # ── Supplies ─────────────────────────────────────────────────────────
    ("Паллеты в офис", CAT_SUPPLIES, "supplies_pallets"),
    ("Коробки в офис", CAT_SUPPLIES, "supplies_boxes"),
    ("Скотч в офис", CAT_SUPPLIES, "supplies_scotch"),
    ("Стрейч пленка", CAT_SUPPLIES, "supplies_stretch"),
    ("Закупка расходных материалов", CAT_SUPPLIES, "supplies_generic"),
    ("Закупка расходных", CAT_SUPPLIES, "supplies"),

    # ── Procurement ──────────────────────────────────────────────────────
    ("Закупка товара", CAT_PROCUREMENT, "procurement"),
    ("Закупка образцов", CAT_SAMPLES, "samples"),

    # ── Warehouse / rent ─────────────────────────────────────────────────
    ("Аренда помещения", CAT_RENT, "rent"),
    ("Содержание склада", CAT_WAREHOUSE_UPKEEP, "warehouse"),
    ("Аренда фотостудии", CAT_PHOTO, "photo_studio_rent"),

    # ── Credit ───────────────────────────────────────────────────────────
    ("Оплаты по кредитам", CAT_CREDIT_PAY, "credit_payment"),
    ("Погашение процентов", CAT_CREDIT_INTEREST, "credit_interest"),

    # ── RKO (bank fees) ──────────────────────────────────────────────────
    ("Оплата лицензионного вознаграждения за использование базовой лицензии", CAT_RKO, "rko_license"),
    ("Ежемесячное обслуживание системы ДБО", CAT_RKO, "rko_dbo"),

    # ── Internal transfers ───────────────────────────────────────────────
    ("Перевод собственных средств", CAT_TRANSFER, "internal_transfer"),

    # ── IT development ───────────────────────────────────────────────────
    ("Внедрение дашборда Power BI", CAT_IT_DEV, "it_powerbi"),
    ("Оплата счета по работе интегратора", CAT_IT_DEV, "it_integrator"),
    ("Оплата за таблицы Гугл", CAT_IT_DEV, "it_google_sheets"),

    # ── Подрядчики ───────────────────────────────────────────────────────
    ("Продление сертификатов", CAT_CONTRACTORS, "contractors_certs"),
    ("Оплата фин. директору", CAT_CONTRACTORS, "contractors_fin_dir"),

    # ── Ads / marketing ──────────────────────────────────────────────────
    ("Пополнение рекламного кабинета ВК", CAT_ADS_EXTERNAL, "ads_vk"),

    # ── Dividends ────────────────────────────────────────────────────────
    ("Выплата дивидендов", CAT_DIVIDENDS, "dividends"),

    # ── Temp staff ───────────────────────────────────────────────────────
    ("Разовый персонал", CAT_TEMP_STAFF, "temp_staff"),
    ("Вывоз мусора", CAT_TEMP_STAFF, "temp_trash"),
]
