"""Market Review — configuration.

All constants for the market review skill:
categories, competitors, our top models, Notion page ID.
"""

# Parent category — overall market dynamics
PARENT_CATEGORY = "Женское белье"

# WB subcategories to monitor (MPStats path format)
CATEGORIES = [
    "Женское белье/Комплекты белья",
    "Женское белье/Бюстгальтеры",
    "Женское белье/Трусы",
    "Женское белье/Боди",
]

# Adjacent categories to watch for expansion opportunities
ADJACENT_CATEGORIES = [
    "Женское белье/Корсеты",
    "Женское белье/Пижамы",
    "Женское белье/Купальники",
    "Спортивное белье",
]

# Historical months to fetch for seasonality analysis (same month in prev years)
SEASONALITY_YEARS_BACK = 2

# Competitors: brand name -> config
# mpstats_path: exact brand name as it appears in MPStats
# segment: pricing segment (for analyst context)
# instagram: Instagram handle (None if no account)
COMPETITORS = {
    # --- Direct competitors (seamless lingerie on marketplaces) ---
    "Birka Art": {"mpstats_path": "Birka Art", "segment": "econom-mid", "instagram": "@birka_art"},
    "Время Цвести": {"mpstats_path": "Время Цвести", "segment": "mid", "instagram": "@vremyazvesti"},
    "SOGU": {"mpstats_path": "SOGU", "segment": "mid-premium", "instagram": "@sogu.shop"},
    "Waistline": {"mpstats_path": "Waistline", "segment": "mid-premium", "instagram": "@waistline_shop"},
    "RIVERENZA": {"mpstats_path": "RIVERENZA", "segment": "econom", "instagram": None},
    "Blizhe": {"mpstats_path": "Blizhe", "segment": "mid", "instagram": None},
    # --- Wider landscape ---
    "Belle You": {"mpstats_path": "Belle You", "segment": "mid-premium", "instagram": "@belleyou.ru"},
    "Bonechka": {"mpstats_path": "Bonechka", "segment": "econom", "instagram": "@bonechka_lingerie"},
    "Lavarice": {"mpstats_path": "Lavarice", "segment": "mid", "instagram": "@lavarice_"},
    "Incanto": {"mpstats_path": "Incanto", "segment": "mid", "instagram": "@incanto_official"},
    "Mark Formelle": {"mpstats_path": "Mark Formelle", "segment": "econom-mid", "instagram": "@markformelle"},
    "VIKKIMO": {"mpstats_path": "VIKKIMO", "segment": "econom", "instagram": "@vikkimo_underwear"},
    "Love Secret": {"mpstats_path": "Love Secret", "segment": "econom", "instagram": "@lovesecret.shop"},
    "MASAR Lingerie": {"mpstats_path": "MASAR Lingerie", "segment": "mid", "instagram": "@masar.lingerie"},
    "Mirey": {"mpstats_path": "Mirey", "segment": "mid", "instagram": "@mirey.su"},
    "Morely": {"mpstats_path": "Morely", "segment": "premium", "instagram": "@morely.ru"},
    "Cecile": {"mpstats_path": "Cecile", "segment": "unknown", "instagram": None},
    "Where Underwear": {"mpstats_path": "Where Underwear", "segment": "unknown", "instagram": None},
}

# Our top models: model name -> {sku: WB nmId, price: текущая цена}
# Source: Notion "Конкуренты WOOKIEE + TELOWAY" (2026-04-07)
OUR_TOP_MODELS = {
    "Wendy": {"skus": [156103915, 257131227], "price": 2283},
    "Audrey": {"skus": [246930819], "price": 2490},
    "Bella": {"skus": [601126751], "price": 2072},
    "Lana": {"skus": [330530049], "price": 1718},
    "Valery": {"skus": [460976746, 460976748], "price": 1075},
    "Ruby": {"skus": [545069124], "price": 1274},
    "Alice": {"skus": [478599286], "price": 1614},
    "Moon": {"skus": [163152029, 175567838], "price": 1099},
    "Joy": {"skus": [545069085], "price": 1165},
    "Vuki": {"skus": [150561673], "price": 628},
    "Eva": {"skus": [460976740], "price": 2197},
}

# Competitor SKUs per model — from Notion "Конкуренты WOOKIEE + TELOWAY"
# Source: https://www.notion.so/33a58a2bd587802bbe1bf512e876409b (2026-04-07)
RIVAL_SKUS = {
    "Wendy": [
        {"sku": 273706094, "brand": "A.V.S", "price": 1315},
        {"sku": 208216913, "brand": "LYS Love YourSelf", "price": 1561},
        {"sku": 191407012, "brand": "WUSHE", "price": 1533},
        {"sku": 273706096, "brand": "A.V.S", "price": 1315},
        {"sku": 418713702, "brand": "BIRKA ART", "price": 1581},
        {"sku": 315091539, "brand": "ВРЕМЯ ЦВЕСТИ", "price": 2495},
        {"sku": 140759083, "brand": "WILDFREE", "price": 1853},
        {"sku": 276603376, "brand": "Secrenti", "price": 727},
        {"sku": 17202715, "brand": "Allusar", "price": 1905},
        {"sku": 9010318, "brand": "Miss X", "price": 1864},
    ],
    "Audrey": [
        {"sku": 436750229, "brand": "MIAUMEA", "price": 697},
        {"sku": 273706096, "brand": "A.V.S", "price": 1315},
        {"sku": 9010318, "brand": "Miss X", "price": 1864},
        {"sku": 273706094, "brand": "A.V.S", "price": 1315},
        {"sku": 276603376, "brand": "Secrenti", "price": 727},
        {"sku": 124764585, "brand": "InShape", "price": 487},
        {"sku": 175119194, "brand": "BODIS", "price": 756},
        {"sku": 124764584, "brand": "InShape", "price": 696},
        {"sku": 208216913, "brand": "LYS Love YourSelf", "price": 1561},
    ],
    "Bella": [
        {"sku": 124764584, "brand": "InShape", "price": 696},
    ],
    "Valery": [
        {"sku": 48835801, "brand": "СВЯТАЯ", "price": 868},
        {"sku": 60245569, "brand": "MIARTLAND", "price": 763},
        {"sku": 122820251, "brand": "Misty Mint Cotton", "price": 276},
        {"sku": 164405739, "brand": "BODIS", "price": 753},
        {"sku": 165873541, "brand": "Empathy!", "price": 704},
        {"sku": 193558689, "brand": "KOSALI", "price": 790},
        {"sku": 203236385, "brand": "MissYourKiss", "price": 1254},
        {"sku": 205631593, "brand": "Reflect beauty.", "price": 662},
        {"sku": 263907245, "brand": "TRIPICANA", "price": 1340},
        {"sku": 275693368, "brand": "DIVINIQUE", "price": 1236},
    ],
    "Ruby": [
        {"sku": 165873541, "brand": "Empathy!", "price": 704},
        {"sku": 55140321, "brand": "Ease Move", "price": 648},
        {"sku": 195638567, "brand": "She's MISTIQUE", "price": 560},
        {"sku": 354924913, "brand": "PONOMARO", "price": 681},
        {"sku": 211022041, "brand": "KariDani", "price": 572},
        {"sku": 256654684, "brand": "DIVINIQUE", "price": 1236},
        {"sku": 105199860, "brand": "BIRKA ART", "price": 609},
        {"sku": 196017305, "brand": "TiTi ToP", "price": 654},
        {"sku": 231833219, "brand": "Reflect beauty.", "price": 522},
        {"sku": 66923558, "brand": "Secrenti", "price": 632},
    ],
    "Alice": [
        {"sku": 263456077, "brand": "Secrenti", "price": 923},
    ],
    "Moon": [
        {"sku": 183752750, "brand": "Ease Move", "price": 650},
    ],
    "Joy": [
        {"sku": 249736425, "brand": "Mama_Shop", "price": 351},
    ],
    "Vuki": [
        {"sku": 196017305, "brand": "TiTi ToP", "price": 654},
        {"sku": 432555013, "brand": "Steemle", "price": 681},
        {"sku": 165873541, "brand": "Empathy!", "price": 704},
        {"sku": 105199860, "brand": "BIRKA ART", "price": 609},
        {"sku": 66923558, "brand": "Secrenti", "price": 632},
        {"sku": 195638567, "brand": "She's MISTIQUE", "price": 560},
        {"sku": 302757043, "brand": "SILK MOOD", "price": 652},
        {"sku": 164405739, "brand": "BODIS", "price": 753},
        {"sku": 157545193, "brand": "ANUTINA", "price": 1163},
    ],
    "Трусы вуки": [
        {"sku": 243426952, "brand": "Fappe", "price": 818},
        {"sku": 176073830, "brand": "CosmoLady", "price": 409},
        {"sku": 221205555, "brand": "FUOSHI", "price": 692},
        {"sku": 196470483, "brand": "Arushanoff", "price": 715},
        {"sku": 169086537, "brand": "KODALIFE", "price": 631},
        {"sku": 144193454, "brand": "LuxuryLace", "price": 557},
        {"sku": 175381762, "brand": "Arushanoff", "price": 715},
        {"sku": 105358704, "brand": "KODALIFE", "price": 631},
        {"sku": 233258527, "brand": "Fappe", "price": 780},
    ],
    "Трусы Белла": [
        {"sku": 124764584, "brand": "InShape", "price": 696},
    ],
}

# Notion target page for publishing
NOTION_PAGE_ID = "2f458a2bd58780648974f98347b2d4d5"

# Competitors for deep WB card analysis (browser research)
WB_CARD_DEEP_ANALYSIS = ["Birka Art", "SOGU", "Waistline", "Belle You"]

# Minimum revenue (RUB) for new items to be included
NEW_ITEMS_MIN_REVENUE = 500_000
