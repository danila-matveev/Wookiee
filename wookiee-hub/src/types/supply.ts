// ---------------------------------------------------------------------------
// Supply Planning — type definitions
// ---------------------------------------------------------------------------

export type Entity = "ooo" | "ip"

export type SupplyOrderStatus = "draft" | "ordered" | "shipped" | "delivered" | "archived"

export interface SupplySettings {
  entity: Entity
  default_return_rate: number   // 0.70 for OOO, 0.75 for IP
  target_coverage_days: number  // 60
  safety_stock_days: number     // 14 (warning threshold)
  critical_stock_days: number   // 7 (critical threshold)
  orders_window_days: number    // 14 — window for daily_orders avg
  default_lead_time_days: number // 30 — order → shipment
  default_transit_days: number   // 75 — shipment → delivery
  default_offset_days: number    // 2
}

export interface SupplyProduct {
  id: string
  artikul: string
  model: string
  model_name: string
  color: string
  color_code: string
  size: string
  barcode: string
  sku_china: string
  kratnost_koroba: number
  ves_kg: number
  importer: Entity
  status: string // "Продается" | "Новый" | etc

  // Computed analytics (from backend)
  daily_orders: number
  conversion_rate: number
  stock_wb: number
  stock_ozon: number
  stock_msk: number
  in_transit: number
  stock_total: number        // wb + ozon + msk (excluding in_transit)
  launch_date: string | null // ISO date
  sufficient_until: string | null // ISO date — current stock depletion
  sufficient_days: number | null  // days from today
}

export interface SupplyOrder {
  id: string
  name: string               // e.g. "Wookiee OOO №12/1"
  entity: Entity
  return_rate: number
  order_date: string         // ISO date
  shipment_date: string      // ISO date
  delivery_date: string      // ISO date
  order_number: string       // e.g. "WK-2026-12"
  offset_days: number
  status: SupplyOrderStatus
  sort_order: number
  notes: string
  created_at: string
  updated_at: string
}

export interface SupplyOrderItem {
  id: string
  supply_order_id: string
  artikul_id: string
  barcode: string            // for matching with SupplyProduct
  quantity: number
}

/** A "block" in the supply chain — one order column in the table */
export interface SupplyBlock {
  order: SupplyOrder
  items: Map<string, number> // barcode → quantity
}

/** Computed result for one product × one block */
export interface SupplyBlockResult {
  order_id: string
  barcode: string
  quantity: number
  sufficient_until: string | null  // ISO date
  sufficient_days: number | null
  alert_level: AlertLevel
}

export type AlertLevel = "ok" | "warning" | "critical"

export interface SupplyAlert {
  product: SupplyProduct
  alert_level: AlertLevel
  sufficient_days: number
  sufficient_until: string
  recommendation: string
  recommended_order_id: string | null
  recommended_qty: number
}

export type SupplyViewMode = "table" | "timeline" | "alerts"
