-- Wookiee Database Schema
-- Two-schema architecture: wb (Wildberries) + ozon (Ozon)
-- Source: DATABASE_REFERENCE.md + information_schema queries to source DB
-- Note: Source DB has NO PK/UNIQUE constraints; we define our own for UPSERT

-- ============================================================
-- SCHEMAS
-- ============================================================

CREATE SCHEMA IF NOT EXISTS wb;
CREATE SCHEMA IF NOT EXISTS ozon;

-- ============================================================
-- WB TABLES
-- ============================================================

-- WB abc_date: main financial table (94+ fields)
-- Unique key: (date, article, barcode, lk)
CREATE TABLE IF NOT EXISTS wb.abc_date (
    -- Identifiers
    date                    DATE NOT NULL,
    period                  VARCHAR(20),
    dateto                  TEXT,
    lk                      TEXT NOT NULL,
    article                 TEXT NOT NULL,
    ts_name                 TEXT,
    barcode                 TEXT NOT NULL DEFAULT '',
    nm_id                   BIGINT,
    mp                      TEXT DEFAULT 'wb',
    dateupdate              TIMESTAMP DEFAULT NOW(),

    -- Revenue & Sales
    revenue_spp             NUMERIC DEFAULT 0,  -- Revenue BEFORE SPP (seller price)
    revenue                 NUMERIC DEFAULT 0,  -- Revenue AFTER SPP (buyer price)
    buyouts_spp             NUMERIC DEFAULT 0,
    buyouts                 NUMERIC DEFAULT 0,
    revenue_return_spp      NUMERIC DEFAULT 0,
    revenue_return          NUMERIC DEFAULT 0,
    full_counts             INTEGER DEFAULT 0,  -- Sales count (buyouts)
    count_orders            INTEGER DEFAULT 0,
    count_return            NUMERIC DEFAULT 0,
    count_cancell           INTEGER DEFAULT 0,
    counts_sam              NUMERIC DEFAULT 0,
    returns                 NUMERIC DEFAULT 0,
    spp                     NUMERIC DEFAULT 0,  -- Marketplace discount (RUB)
    conversion              NUMERIC DEFAULT 0,
    average_check           NUMERIC DEFAULT 0,
    retail_price            NUMERIC DEFAULT 0,
    price_rozn              NUMERIC DEFAULT 0,
    sale_sum                NUMERIC DEFAULT 0,

    -- Core Expenses (used in 11-component margin formula)
    comis_spp               NUMERIC DEFAULT 0,  -- Commission BEFORE SPP
    comis                   NUMERIC DEFAULT 0,  -- Commission AFTER SPP
    logist                  NUMERIC DEFAULT 0,
    sebes                   NUMERIC DEFAULT 0,  -- Cost price (from Google Sheets)
    reclama                 NUMERIC DEFAULT 0,  -- Internal advertising
    reclama_vn              NUMERIC DEFAULT 0,  -- External advertising (total)
    storage                 NUMERIC DEFAULT 0,
    nds                     NUMERIC DEFAULT 0,  -- VAT
    penalty                 NUMERIC DEFAULT 0,
    retention               NUMERIC DEFAULT 0,
    deduction               NUMERIC DEFAULT 0,
    nalog                   NUMERIC DEFAULT 0,  -- Tax (USN)

    -- Advertising detail
    reclama_vn_vk           NUMERIC DEFAULT 0,
    reclama_vn_creators     NUMERIC DEFAULT 0,
    advert                  NUMERIC DEFAULT 0,
    marketing               NUMERIC DEFAULT 0,

    -- Self-purchases expenses
    comis_sam               NUMERIC DEFAULT 0,
    logist_sam              NUMERIC DEFAULT 0,
    sebes_sam               NUMERIC DEFAULT 0,
    sebes_return            NUMERIC DEFAULT 0,

    -- Margin
    marga                   NUMERIC DEFAULT 0,
    marga_union             NUMERIC DEFAULT 0,  -- Final margin = marga_union - nds
    proverka                NUMERIC DEFAULT 0,
    proverka2               NUMERIC DEFAULT 0,

    -- Union fields
    comis_union             NUMERIC DEFAULT 0,
    logist_union            NUMERIC DEFAULT 0,
    logist_union_prod       NUMERIC DEFAULT 0,
    logist_union_return     NUMERIC DEFAULT 0,
    storage_union           NUMERIC DEFAULT 0,
    over_logist             NUMERIC DEFAULT 0,
    over_logist_union       NUMERIC DEFAULT 0,
    penalty_union           NUMERIC DEFAULT 0,
    dop_penalty             NUMERIC DEFAULT 0,
    retention_union         NUMERIC DEFAULT 0,
    inspection              NUMERIC DEFAULT 0,
    inspection_union        NUMERIC DEFAULT 0,

    -- Logistics detail
    logis_return_rub        NUMERIC DEFAULT 0,
    logis_cancell_rub       NUMERIC DEFAULT 0,
    rebill_logistic_cost    NUMERIC DEFAULT 0,

    -- Fulfillment
    no_vozvratny_fulfil     NUMERIC DEFAULT 0,
    prod_fulfil             NUMERIC DEFAULT 0,
    fulfilment_sam          NUMERIC DEFAULT 0,
    fulfilment_returns      NUMERIC DEFAULT 0,

    -- External logistics
    no_vozvratny_vhesh_logist NUMERIC DEFAULT 0,
    prod_vnehs_logist       NUMERIC DEFAULT 0,
    vnesh_logist_sam        NUMERIC DEFAULT 0,
    vnesh_logist_returns    NUMERIC DEFAULT 0,

    -- Packaging
    vozvratny_upakov        NUMERIC DEFAULT 0,
    prod_upakov             NUMERIC DEFAULT 0,
    upakovka_sam            NUMERIC DEFAULT 0,
    upakovka_returns        NUMERIC DEFAULT 0,

    -- Mirror
    vozvratny_zerkalo       NUMERIC DEFAULT 0,
    prod_zercalo            NUMERIC DEFAULT 0,
    zercalo_sam             NUMERIC DEFAULT 0,
    zercalo_returns         NUMERIC DEFAULT 0,

    -- Other financial
    surcharges              NUMERIC DEFAULT 0,
    compens_comis           NUMERIC DEFAULT 0,
    sebes_kompens           NUMERIC DEFAULT 0,
    acquiring               NUMERIC DEFAULT 0,
    acquiring_fee           NUMERIC DEFAULT 0,
    cross                   NUMERIC DEFAULT 0,
    bank                    NUMERIC DEFAULT 0,
    service                 NUMERIC DEFAULT 0,
    count_self              NUMERIC DEFAULT 0,
    inkasator_count         NUMERIC DEFAULT 0,
    kompens_counts          NUMERIC DEFAULT 0,
    count_otkl              NUMERIC DEFAULT 0,
    kiz                     NUMERIC DEFAULT 0,
    other_deductions        NUMERIC DEFAULT 0,
    subsribe                NUMERIC DEFAULT 0,
    bonus_pay               NUMERIC DEFAULT 0,

    -- Additional income/expenses
    revenue_dop_defect      NUMERIC DEFAULT 0,
    rashod_dop_defect       NUMERIC DEFAULT 0,
    revenue_dop_loss        NUMERIC DEFAULT 0,
    rashod_dop_loss         NUMERIC DEFAULT 0,
    additional_payment      INTEGER DEFAULT 0,
    rashod_additional_payment NUMERIC DEFAULT 0,
    postup_wb_all           NUMERIC DEFAULT 0,
    loan                    NUMERIC DEFAULT 0,
    cashback_amount         NUMERIC DEFAULT 0,
    cashback_c_c            NUMERIC DEFAULT 0,

    CONSTRAINT wb_abc_date_ukey UNIQUE (date, article, barcode, lk)
);

-- WB orders (31 fields)
CREATE TABLE IF NOT EXISTS wb.orders (
    date                    TIMESTAMP,
    lastchangedate          TIMESTAMP,
    supplierarticle         TEXT,
    techsize                TEXT,
    barcode                 TEXT,
    totalprice              NUMERIC,
    discountpercent         NUMERIC,
    spp                     NUMERIC,
    finishedprice           NUMERIC,
    pricewithdisc           NUMERIC,
    warehousename           TEXT,
    oblast                  TEXT,
    region                  TEXT,
    regionname              TEXT,
    country                 TEXT,
    nmid                    BIGINT,
    subject                 TEXT,
    category                TEXT,
    brand                   TEXT,
    iscancel                TEXT,
    cancel_dt               TIMESTAMP,
    gnumber                 TEXT,
    gnumberid               TEXT,
    sticker                 TEXT,
    srid                    TEXT,
    ordertype               TEXT,
    lk                      TEXT,
    wb_claster              TEXT,
    wb_claster_to           TEXT,
    warehousetype           TEXT,
    dateupdate              TIMESTAMP DEFAULT NOW(),

    CONSTRAINT wb_orders_ukey UNIQUE (srid, lk)
);

-- WB sales (32 fields)
CREATE TABLE IF NOT EXISTS wb.sales (
    date                    TIMESTAMP,
    lastchangedate          TIMESTAMP,
    supplierarticle         TEXT,
    techsize                TEXT,
    barcode                 TEXT,
    totalprice              NUMERIC,
    discountpercent         INTEGER,
    spp                     NUMERIC,
    forpay                  NUMERIC,
    finishedprice           NUMERIC,
    pricewithdisc           NUMERIC,
    warehousename           TEXT,
    countryname             TEXT,
    oblastokrugname         TEXT,
    regionname              TEXT,
    nmid                    BIGINT,
    subject                 TEXT,
    category                TEXT,
    brand                   TEXT,
    isstorno                INTEGER,
    gnumber                 TEXT,
    saleid                  TEXT,
    srid                    TEXT,
    lk                      TEXT,
    paymentsaleamount       NUMERIC,
    dateupdate              TIMESTAMP DEFAULT NOW(),

    CONSTRAINT wb_sales_ukey UNIQUE (srid, lk)
);

-- WB stocks (21 fields from source DB query)
CREATE TABLE IF NOT EXISTS wb.stocks (
    lastchangedate          TIMESTAMP,
    supplierarticle         TEXT,
    techsize                TEXT,
    barcode                 TEXT,
    quantity                INTEGER,
    issupply                TEXT,
    isrealization           TEXT,
    quantityfull            INTEGER,
    warehousename           TEXT,
    nmid                    BIGINT,
    subject                 TEXT,
    category                TEXT,
    daysonsite              INTEGER,
    brand                   TEXT,
    sccode                  TEXT,
    price                   NUMERIC,
    discount                NUMERIC,
    dateupdate              DATE DEFAULT CURRENT_DATE,
    lk                      TEXT,
    wh                      TEXT,
    tip                     TEXT,

    CONSTRAINT wb_stocks_ukey UNIQUE (dateupdate, barcode, warehousename, lk)
);

-- WB nomenclature (19 fields)
CREATE TABLE IF NOT EXISTS wb.nomenclature (
    vendorcode              TEXT,
    nmid                    BIGINT,
    brand                   TEXT,
    object                  TEXT,
    title                   TEXT,
    barcod                  TEXT,
    colors                  TEXT,
    techsize                TEXT,
    chrtid                  TEXT,
    imtid                   TEXT,
    video                   TEXT,
    tags                    TEXT,
    description             TEXT,
    link_card               TEXT,
    mediafiles              TEXT,
    lk                      TEXT,
    createdat               DATE,
    updateat                DATE,
    dateupdate              TIMESTAMP DEFAULT NOW(),

    CONSTRAINT wb_nomenclature_ukey UNIQUE (nmid, barcod, lk)
);

-- WB content_analysis (12 fields)
CREATE TABLE IF NOT EXISTS wb.content_analysis (
    date                    DATE NOT NULL,
    vendorcode              TEXT,
    nmid                    BIGINT,
    opencardcount           INTEGER DEFAULT 0,
    addtocartcount          INTEGER DEFAULT 0,
    orderscount             INTEGER DEFAULT 0,
    buyoutscount            INTEGER DEFAULT 0,
    addtocartpercent        NUMERIC DEFAULT 0,
    carttoorderpercent      NUMERIC DEFAULT 0,
    buyoutspercent          NUMERIC DEFAULT 0,
    addtowishlist           INTEGER DEFAULT 0,
    lk                      TEXT,

    CONSTRAINT wb_content_analysis_ukey UNIQUE (date, nmid, lk)
);

-- WB wb_adv (17 fields)
CREATE TABLE IF NOT EXISTS wb.wb_adv (
    date                    DATE NOT NULL,
    nmid                    BIGINT,
    views                   INTEGER DEFAULT 0,
    clicks                  INTEGER DEFAULT 0,
    sum                     NUMERIC DEFAULT 0,
    atbs                    INTEGER DEFAULT 0,
    orders                  INTEGER DEFAULT 0,
    ctr                     NUMERIC DEFAULT 0,
    cpc                     NUMERIC DEFAULT 0,
    cr                      NUMERIC DEFAULT 0,
    frq                     NUMERIC DEFAULT 0,
    shks                    INTEGER DEFAULT 0,
    unique_users            INTEGER DEFAULT 0,
    canceled                INTEGER DEFAULT 0,
    advertid                INTEGER,
    name_rk                 TEXT,
    lk                      TEXT,

    CONSTRAINT wb_wb_adv_ukey UNIQUE (date, nmid, advertid, lk)
);

-- ============================================================
-- OZON TABLES
-- ============================================================

-- OZON abc_date: main financial table (72 fields)
CREATE TABLE IF NOT EXISTS ozon.abc_date (
    -- Identifiers
    date                    DATE NOT NULL,
    period                  VARCHAR(20),
    lk                      TEXT NOT NULL,
    article                 TEXT NOT NULL,
    sku                     TEXT,
    product_id              TEXT,
    mp                      TEXT DEFAULT 'ozon',
    date_update             TIMESTAMP DEFAULT NOW(),

    -- Revenue & Sales
    price_end               NUMERIC DEFAULT 0,      -- Revenue BEFORE SPP (final)
    price_end_spp           NUMERIC DEFAULT 0,      -- Revenue AFTER SPP
    buyouts_end             NUMERIC DEFAULT 0,
    buyouts_spp             NUMERIC DEFAULT 0,
    return_end              NUMERIC DEFAULT 0,
    return_end_spp          NUMERIC DEFAULT 0,
    count_end               NUMERIC DEFAULT 0,      -- Sales count (net of returns)
    count_return            NUMERIC DEFAULT 0,
    cancell_end             NUMERIC DEFAULT 0,
    count_sam               NUMERIC DEFAULT 0,
    spp                     NUMERIC DEFAULT 0,      -- Marketplace discount (RUB)

    -- Core Expenses
    comission_end           NUMERIC DEFAULT 0,      -- Commission BEFORE SPP
    comission_end_spp       NUMERIC DEFAULT 0,      -- Commission AFTER SPP
    logist_end              NUMERIC DEFAULT 0,
    storage_end             NUMERIC DEFAULT 0,
    sebes_end               NUMERIC DEFAULT 0,
    reclama_end             NUMERIC DEFAULT 0,      -- Internal advertising
    bank_end                NUMERIC DEFAULT 0,      -- Acquiring
    nalog_end               NUMERIC DEFAULT 0,      -- Tax (USN)
    nds                     NUMERIC DEFAULT 0,      -- VAT
    cross_end               NUMERIC DEFAULT 0,      -- Cross-docking

    -- External advertising
    adv_vn                  NUMERIC DEFAULT 0,      -- External advertising (total)
    adv_vn_vk               NUMERIC DEFAULT 0,
    adv_vn_creators         NUMERIC DEFAULT 0,

    -- Margin
    marga                   NUMERIC DEFAULT 0,      -- Intermediate margin; final = marga - nds

    -- Ozon services
    service_end             NUMERIC DEFAULT 0,
    service_bonus           NUMERIC DEFAULT 0,
    service_kor             NUMERIC DEFAULT 0,
    service_util            NUMERIC DEFAULT 0,
    service_izlish          NUMERIC DEFAULT 0,
    service_defect          NUMERIC DEFAULT 0,
    service_otziv           NUMERIC DEFAULT 0,
    service_izlish_opozn    NUMERIC DEFAULT 0,
    service_rassilka        NUMERIC DEFAULT 0,
    service_premium         NUMERIC DEFAULT 0,
    service_viplat          NUMERIC DEFAULT 0,
    service_grafic          NUMERIC DEFAULT 0,
    service_bron            NUMERIC DEFAULT 0,
    service_defect_sklad    NUMERIC DEFAULT 0,
    service_loss            NUMERIC DEFAULT 0,
    service_uslov_otgruz    NUMERIC DEFAULT 0,
    service_new             NUMERIC DEFAULT 0,
    service_fbo             NUMERIC DEFAULT 0,
    service_compens         NUMERIC DEFAULT 0,
    service_brand           NUMERIC DEFAULT 0,

    -- Buyout components
    buyouts_ss              NUMERIC DEFAULT 0,
    buyouts_logist          NUMERIC DEFAULT 0,
    buyouts_comission       NUMERIC DEFAULT 0,
    buyouts_bank            NUMERIC DEFAULT 0,

    -- Compensations
    sebes_kompens           NUMERIC DEFAULT 0,
    sebes_util              NUMERIC DEFAULT 0,
    pretenzia               NUMERIC DEFAULT 0,
    other_compensation      NUMERIC DEFAULT 0,
    other_services          NUMERIC DEFAULT 0,
    error                   NUMERIC DEFAULT 0,

    -- Delivery
    drop_off                NUMERIC DEFAULT 0,
    transfer_delivery       NUMERIC DEFAULT 0,
    realfbs                 NUMERIC DEFAULT 0,

    -- EAES
    eaes_count              NUMERIC DEFAULT 0,
    eaes                    NUMERIC DEFAULT 0,
    eaes_spp                NUMERIC DEFAULT 0,
    sebes_eaes              NUMERIC DEFAULT 0,
    eaes_nds                NUMERIC DEFAULT 0,

    -- Other
    zvezdny_tovar           NUMERIC DEFAULT 0,

    CONSTRAINT ozon_abc_date_ukey UNIQUE (date, article, lk)
);

-- OZON orders (23 fields)
CREATE TABLE IF NOT EXISTS ozon.orders (
    order_id                BIGINT,
    posting_number          TEXT,
    order_number            TEXT,
    product_id              TEXT,
    sku                     TEXT,
    offer_id                TEXT,
    delivery_schema         TEXT,
    status                  TEXT,
    price                   NUMERIC,
    quantity                INTEGER,
    commission_amount       NUMERIC,
    in_process_at           TIMESTAMP,
    dateupdate              TIMESTAMP DEFAULT NOW(),
    warehouse_id            TEXT,
    warehouse_name          TEXT,
    cluster_to              TEXT,
    cluster_from            TEXT,
    lk                      TEXT,
    is_express              TEXT,
    ozon_claster            TEXT,
    ozon_claster_to         TEXT,
    city                    TEXT,
    region                  TEXT,

    CONSTRAINT ozon_orders_ukey UNIQUE (order_id, sku, lk)
);

-- OZON returns (27 fields)
CREATE TABLE IF NOT EXISTS ozon.returns (
    operation_id            TEXT,
    operation_type          TEXT,
    operation_date          DATE,
    operation_type_name     TEXT,
    posting_number          TEXT,
    order_date              TIMESTAMP,
    sku                     TEXT,
    product_id              TEXT,
    name                    TEXT,
    lk                      TEXT,
    delivery_schema         TEXT,
    type                    TEXT,
    amount                  NUMERIC,
    delivery_charge         NUMERIC,
    return_delivery_charge  NUMERIC,
    accruals_for_sale       NUMERIC,
    sale_commission         NUMERIC,
    marketplaceserviceitemdirectflowlogistic     NUMERIC,
    marketplaceserviceitemreturnflowlogistic     NUMERIC,
    marketplaceserviceitemdelivtocustomer        NUMERIC,
    marketplaceserviceitemdirectflowtrans        NUMERIC,
    marketplaceserviceitemfulfillment            NUMERIC,
    marketplaceserviceitemreturnafterdelivtocustomer NUMERIC,
    marketplaceserviceitemreturnnotdelivtocustomer   NUMERIC,
    marketplaceserviceitemreturnpartgoodscustomer    NUMERIC,

    CONSTRAINT ozon_returns_ukey UNIQUE (operation_id, sku, lk)
);

-- OZON stocks (11 fields from source DB query)
CREATE TABLE IF NOT EXISTS ozon.stocks (
    offer_id                TEXT,
    product_id              TEXT,
    sku                     TEXT,
    delivery_schema         TEXT,
    stockspresent           INTEGER,
    stocksreserved          INTEGER,
    dateupdate              DATE DEFAULT CURRENT_DATE,
    warehouse_id            TEXT,
    warehouse_name          TEXT,
    lk                      TEXT,
    promised_amount         NUMERIC,

    CONSTRAINT ozon_stocks_ukey UNIQUE (dateupdate, sku, warehouse_id, delivery_schema, lk)
);

-- OZON nomenclature (19 fields)
CREATE TABLE IF NOT EXISTS ozon.nomenclature (
    article                 TEXT,
    ozon_product_id         TEXT,
    fbo_ozon_sku_id         TEXT,
    fbs_ozon_sku_id         TEXT,
    barcode                 TEXT,
    category                TEXT,
    status                  TEXT,
    current_price_including_discount NUMERIC,
    price_before_discount   NUMERIC,
    premium_price           NUMERIC,
    market_price            NUMERIC,
    product_volume_l        NUMERIC,
    volumetric_weight_kg    NUMERIC,
    primary_image           TEXT,
    lk                      TEXT,
    brand                   TEXT,
    name_tovar              TEXT,
    dateupdate              TIMESTAMP DEFAULT NOW(),
    createdat               DATE,

    CONSTRAINT ozon_nomenclature_ukey UNIQUE (article, ozon_product_id, lk)
);

-- OZON adv_stats_daily (9 fields)
CREATE TABLE IF NOT EXISTS ozon.adv_stats_daily (
    id_rk                   BIGINT,
    title                   TEXT,
    operation_date          DATE NOT NULL,
    views                   INTEGER DEFAULT 0,
    clicks                  INTEGER DEFAULT 0,
    orders_count            INTEGER DEFAULT 0,
    orders_amount           NUMERIC DEFAULT 0,
    rk_expense              NUMERIC DEFAULT 0,
    avg_bid                 NUMERIC DEFAULT 0,

    CONSTRAINT ozon_adv_stats_daily_ukey UNIQUE (id_rk, operation_date)
);

-- OZON ozon_adv_api (11 fields)
CREATE TABLE IF NOT EXISTS ozon.ozon_adv_api (
    sku                     TEXT,
    operation_date          DATE NOT NULL,
    clicks                  INTEGER DEFAULT 0,
    to_cart                 INTEGER DEFAULT 0,
    orders                  INTEGER DEFAULT 0,
    cpc                     INTEGER DEFAULT 0,
    ctr                     NUMERIC DEFAULT 0,
    sum_rev                 NUMERIC DEFAULT 0,
    id_rk                   TEXT,
    orders_model            INTEGER DEFAULT 0,
    revenu_model            NUMERIC DEFAULT 0,

    CONSTRAINT ozon_adv_api_ukey UNIQUE (sku, operation_date, id_rk)
);
