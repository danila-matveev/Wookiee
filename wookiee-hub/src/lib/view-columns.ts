// wookiee-hub/src/lib/view-columns.ts
// Column definitions per entity per built-in view (spec/stock/finance/rating)
import type { Column } from "@/components/matrix/data-table"

export type EntityType =
  | "models"
  | "articles"
  | "products"
  | "colors"
  | "factories"
  | "importers"
  | "cards-wb"
  | "cards-ozon"
  | "certs"

export type BuiltInView = "spec" | "stock" | "finance" | "rating"

/** Only models, articles, products support multi-view tabs. Others show spec only. */
export const ENTITY_HAS_VIEWS: Record<EntityType, boolean> = {
  models: true,
  articles: true,
  products: true,
  colors: false,
  factories: false,
  importers: false,
  "cards-wb": false,
  "cards-ozon": false,
  certs: false,
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyColumn = Column<any>

// ── Models ──────────────────────────────────────────────────────────────────

const modelsSpec: AnyColumn[] = [
  { key: "kod", label: "Код", width: 140, type: "text" },
  { key: "kategoriya_name", label: "Категория", width: 160, type: "readonly" },
  { key: "kollekciya_name", label: "Коллекция", width: 160, type: "readonly" },
  { key: "fabrika_name", label: "Фабрика", width: 140, type: "readonly" },
  { key: "material", label: "Материал", width: 200, type: "text" },
  { key: "razmery_modeli", label: "Размеры", width: 120, type: "text" },
  { key: "tip_kollekcii", label: "Тип коллекции", width: 180, type: "readonly" },
  { key: "children_count", label: "Подмодели", width: 100, type: "readonly" },
]

const modelsStock: AnyColumn[] = [
  { key: "kod", label: "Код", width: 140, type: "text" },
  { key: "kategoriya_name", label: "Категория", width: 160, type: "readonly" },
  { key: "children_count", label: "Подмодели", width: 100, type: "readonly" },
  { key: "_stock_wb", label: "Остаток WB", width: 120, type: "readonly" },
  { key: "_stock_ozon", label: "Остаток Ozon", width: 120, type: "readonly" },
  { key: "_stock_transit", label: "В пути", width: 120, type: "readonly" },
  { key: "_days_supply", label: "Дней запаса", width: 120, type: "readonly" },
]

const modelsFinance: AnyColumn[] = [
  { key: "kod", label: "Код", width: 140, type: "text" },
  { key: "kategoriya_name", label: "Категория", width: 160, type: "readonly" },
  { key: "_revenue", label: "Выручка", width: 140, type: "readonly" },
  { key: "_margin", label: "Маржа", width: 120, type: "readonly" },
  { key: "_drr", label: "ДРР", width: 100, type: "readonly" },
  { key: "_orders", label: "Заказы", width: 120, type: "readonly" },
  { key: "_abc", label: "ABC", width: 80, type: "readonly" },
]

const modelsRating: AnyColumn[] = [
  { key: "kod", label: "Код", width: 140, type: "text" },
  { key: "kategoriya_name", label: "Категория", width: 160, type: "readonly" },
  { key: "_rating_wb", label: "Рейтинг WB", width: 120, type: "readonly" },
  { key: "_rating_ozon", label: "Рейтинг Ozon", width: 120, type: "readonly" },
  { key: "_reviews_count", label: "Отзывы", width: 120, type: "readonly" },
  { key: "_avg_score", label: "Ср. оценка", width: 120, type: "readonly" },
]

// ── Articles ────────────────────────────────────────────────────────────────

const articlesSpec: AnyColumn[] = [
  { key: "artikul", label: "Артикул", width: 160, type: "text" },
  { key: "model_name", label: "Модель", width: 140, type: "readonly" },
  { key: "cvet_name", label: "Цвет", width: 140, type: "readonly" },
  { key: "status_name", label: "Статус", width: 120, type: "readonly" },
  { key: "nomenklatura_wb", label: "Номенклатура WB", width: 160, type: "number" },
  { key: "artikul_ozon", label: "Артикул Ozon", width: 140, type: "text" },
  { key: "tovary_count", label: "SKU", width: 80, type: "readonly" },
]

const articlesStock: AnyColumn[] = [
  { key: "artikul", label: "Артикул", width: 160, type: "text" },
  { key: "model_name", label: "Модель", width: 140, type: "readonly" },
  { key: "tovary_count", label: "SKU", width: 80, type: "readonly" },
  { key: "_stock_wb", label: "Остаток WB", width: 120, type: "readonly" },
  { key: "_stock_ozon", label: "Остаток Ozon", width: 120, type: "readonly" },
  { key: "_stock_transit", label: "В пути", width: 120, type: "readonly" },
  { key: "_days_supply", label: "Дней запаса", width: 120, type: "readonly" },
]

const articlesFinance: AnyColumn[] = [
  { key: "artikul", label: "Артикул", width: 160, type: "text" },
  { key: "model_name", label: "Модель", width: 140, type: "readonly" },
  { key: "_revenue", label: "Выручка", width: 140, type: "readonly" },
  { key: "_margin", label: "Маржа", width: 120, type: "readonly" },
  { key: "_drr", label: "ДРР", width: 100, type: "readonly" },
  { key: "_orders", label: "Заказы", width: 120, type: "readonly" },
  { key: "_abc", label: "ABC", width: 80, type: "readonly" },
]

const articlesRating: AnyColumn[] = [
  { key: "artikul", label: "Артикул", width: 160, type: "text" },
  { key: "model_name", label: "Модель", width: 140, type: "readonly" },
  { key: "_rating_wb", label: "Рейтинг WB", width: 120, type: "readonly" },
  { key: "_rating_ozon", label: "Рейтинг Ozon", width: 120, type: "readonly" },
  { key: "_reviews_count", label: "Отзывы", width: 120, type: "readonly" },
  { key: "_avg_score", label: "Ср. оценка", width: 120, type: "readonly" },
]

// ── Products ────────────────────────────────────────────────────────────────

const productsSpec: AnyColumn[] = [
  { key: "barkod", label: "Баркод", width: 160, type: "text" },
  { key: "artikul_name", label: "Артикул", width: 140, type: "readonly" },
  { key: "razmer_name", label: "Размер", width: 100, type: "readonly" },
  { key: "status_name", label: "Статус", width: 120, type: "readonly" },
  { key: "ozon_product_id", label: "Ozon Product ID", width: 140, type: "number" },
  { key: "ozon_fbo_sku_id", label: "Ozon FBO SKU", width: 140, type: "number" },
  { key: "lamoda_seller_sku", label: "Lamoda SKU", width: 140, type: "text" },
  { key: "sku_china_size", label: "SKU China Size", width: 130, type: "text" },
]

const productsStock: AnyColumn[] = [
  { key: "barkod", label: "Баркод", width: 160, type: "text" },
  { key: "artikul_name", label: "Артикул", width: 140, type: "readonly" },
  { key: "razmer_name", label: "Размер", width: 100, type: "readonly" },
  { key: "_stock_wb", label: "Остаток WB", width: 120, type: "readonly" },
  { key: "_stock_ozon", label: "Остаток Ozon", width: 120, type: "readonly" },
  { key: "_stock_transit", label: "В пути", width: 120, type: "readonly" },
  { key: "_days_supply", label: "Дней запаса", width: 120, type: "readonly" },
]

const productsFinance: AnyColumn[] = [
  { key: "barkod", label: "Баркод", width: 160, type: "text" },
  { key: "artikul_name", label: "Артикул", width: 140, type: "readonly" },
  { key: "_revenue", label: "Выручка", width: 140, type: "readonly" },
  { key: "_margin", label: "Маржа", width: 120, type: "readonly" },
  { key: "_drr", label: "ДРР", width: 100, type: "readonly" },
  { key: "_orders", label: "Заказы", width: 120, type: "readonly" },
  { key: "_abc", label: "ABC", width: 80, type: "readonly" },
]

const productsRating: AnyColumn[] = [
  { key: "barkod", label: "Баркод", width: 160, type: "text" },
  { key: "artikul_name", label: "Артикул", width: 140, type: "readonly" },
  { key: "_rating_wb", label: "Рейтинг WB", width: 120, type: "readonly" },
  { key: "_rating_ozon", label: "Рейтинг Ozon", width: 120, type: "readonly" },
  { key: "_reviews_count", label: "Отзывы", width: 120, type: "readonly" },
  { key: "_avg_score", label: "Ср. оценка", width: 120, type: "readonly" },
]

// ── Lookup table ────────────────────────────────────────────────────────────

const VIEW_COLUMNS: Record<string, Record<string, AnyColumn[]>> = {
  models: { spec: modelsSpec, stock: modelsStock, finance: modelsFinance, rating: modelsRating },
  articles: { spec: articlesSpec, stock: articlesStock, finance: articlesFinance, rating: articlesRating },
  products: { spec: productsSpec, stock: productsStock, finance: productsFinance, rating: productsRating },
}

/**
 * Return columns for a given entity + built-in view.
 * Falls back to defaultColumns if entity/view combo is not defined.
 */
export function getViewColumns<T>(
  entity: EntityType,
  view: BuiltInView,
  defaultColumns: Column<T>[],
): Column<T>[] {
  const entityViews = VIEW_COLUMNS[entity]
  if (!entityViews) return defaultColumns
  const cols = entityViews[view]
  if (!cols) return defaultColumns
  return cols as Column<T>[]
}
