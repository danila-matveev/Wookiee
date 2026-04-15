// ---------------------------------------------------------------------------
// Supply Planning — calculation engine
// Replicates the Google Sheets formulas for supply chain coverage
// ---------------------------------------------------------------------------

import { differenceInCalendarDays, addDays, parseISO, format } from "date-fns"
import type {
  SupplyProduct,
  SupplyBlock,
  SupplyBlockResult,
  SupplySettings,
  AlertLevel,
  SupplyAlert,
} from "@/types/supply"

// ── helpers ──────────────────────────────────────────────────────────────────

function toDate(iso: string | null | undefined): Date | null {
  if (!iso) return null
  return parseISO(iso)
}

function toISO(d: Date): string {
  return format(d, "yyyy-MM-dd")
}

function today(): Date {
  return new Date(new Date().toDateString()) // midnight
}

// ── return factor ────────────────────────────────────────────────────────────

/**
 * Return factor: accounts for returned items becoming sellable again.
 *   return_factor = 1 + (1 - conversion_rate) * return_percentage
 *
 * Example: conversion 64%, returns 70% → 1 + 0.36 × 0.7 = 1.252
 * Meaning: 100 ordered units effectively cover 125 sales.
 */
export function calcReturnFactor(
  conversionRate: number,
  returnRate: number,
): number {
  return 1 + (1 - conversionRate) * returnRate
}

// ── current stock depletion ──────────────────────────────────────────────────

/**
 * When will current stock run out?
 *   sufficient_until = (launch > today ? launch : today) + stock / daily_orders
 */
export function calcCurrentSufficientUntil(
  product: SupplyProduct,
): { date: string | null; days: number | null } {
  if (!product.daily_orders || product.daily_orders <= 0) {
    return { date: null, days: null }
  }

  const now = today()
  const launch = toDate(product.launch_date)
  const start = launch && launch > now ? launch : now
  const daysOfStock = product.stock_total / product.daily_orders
  const depletionDate = addDays(start, Math.round(daysOfStock))

  return {
    date: toISO(depletionDate),
    days: differenceInCalendarDays(depletionDate, now),
  }
}

// ── chain calculation ────────────────────────────────────────────────────────

/**
 * Calculate "sufficient until" for a single block in the supply chain.
 *
 * Logic (mirrors the spreadsheet):
 *   if prev_sufficient_until < delivery_date → gap (stock runs out before delivery)
 *     start = delivery_date
 *   else → overlap (still have stock when delivery arrives)
 *     start = prev_sufficient_until
 *
 *   days_of_supply = quantity / daily_orders * return_factor - offset
 *   sufficient_until = start + days_of_supply
 */
export function calcBlockSufficientUntil(
  quantity: number,
  dailyOrders: number,
  returnFactor: number,
  offsetDays: number,
  deliveryDate: string,
  prevSufficientUntil: string | null,
): { date: string | null; days: number | null } {
  if (!dailyOrders || dailyOrders <= 0) {
    return { date: null, days: null }
  }

  const delivery = toDate(deliveryDate)!
  const prevDate = toDate(prevSufficientUntil)
  const now = today()

  // Start date: max(prev depletion, delivery date)
  const start = !prevDate || prevDate < delivery ? delivery : prevDate

  if (quantity <= 0) {
    // No items ordered in this block → carry forward
    return {
      date: toISO(start),
      days: differenceInCalendarDays(start, now),
    }
  }

  const daysOfSupply =
    (quantity / dailyOrders) * returnFactor - offsetDays
  const sufficientDate = addDays(start, Math.round(daysOfSupply))

  return {
    date: toISO(sufficientDate),
    days: differenceInCalendarDays(sufficientDate, now),
  }
}

/**
 * Compute the full chain of supply blocks for one product.
 * Returns an array of SupplyBlockResult (one per block, in order).
 */
export function calcSupplyChain(
  product: SupplyProduct,
  blocks: SupplyBlock[],
  settings: SupplySettings,
): SupplyBlockResult[] {
  const returnFactor = calcReturnFactor(
    product.conversion_rate,
    settings.default_return_rate,
  )

  // Start from current stock depletion
  let prevSufficientUntil = product.sufficient_until

  const results: SupplyBlockResult[] = []

  for (const block of blocks) {
    const qty = block.items.get(product.barcode) ?? 0
    const { date, days } = calcBlockSufficientUntil(
      qty,
      product.daily_orders,
      returnFactor,
      block.order.offset_days,
      block.order.delivery_date,
      prevSufficientUntil,
    )

    prevSufficientUntil = date

    results.push({
      order_id: block.order.id,
      barcode: product.barcode,
      quantity: qty,
      sufficient_until: date,
      sufficient_days: days,
      alert_level: getAlertLevel(days, settings),
    })
  }

  return results
}

// ── alert level ──────────────────────────────────────────────────────────────

export function getAlertLevel(
  days: number | null,
  settings: SupplySettings,
): AlertLevel {
  if (days === null) return "ok"
  if (days <= settings.critical_stock_days) return "critical"
  if (days <= settings.safety_stock_days) return "warning"
  return "ok"
}

// ── suggested quantity ───────────────────────────────────────────────────────

/**
 * Auto-suggestion for "how many to order" in a block.
 *   suggested = ceil((target_days * daily_orders - available) / return_factor)
 *   rounded up to kratnost_koroba (box multiple)
 */
export function calcSuggestedQty(
  product: SupplyProduct,
  settings: SupplySettings,
  prevSufficientUntil: string | null,
  deliveryDate: string,
): number {
  if (!product.daily_orders || product.daily_orders <= 0) return 0

  const returnFactor = calcReturnFactor(
    product.conversion_rate,
    settings.default_return_rate,
  )

  const delivery = toDate(deliveryDate)!
  const prevDate = toDate(prevSufficientUntil)

  // How many days of stock do we already have past delivery?
  const existingCoverage =
    prevDate && prevDate > delivery
      ? differenceInCalendarDays(prevDate, delivery)
      : 0

  const neededDays = settings.target_coverage_days - existingCoverage
  if (neededDays <= 0) return 0

  const raw = (neededDays * product.daily_orders) / returnFactor
  const rounded = Math.ceil(raw)

  // Round up to box multiple
  const kratnost = product.kratnost_koroba || 1
  return Math.ceil(rounded / kratnost) * kratnost
}

// ── alerts generation ────────────────────────────────────────────────────────

/**
 * Generate alerts for products that will run out of stock soon.
 * Checks the last block's sufficient_until for each product.
 */
export function generateAlerts(
  products: SupplyProduct[],
  blocks: SupplyBlock[],
  settings: SupplySettings,
): SupplyAlert[] {
  const alerts: SupplyAlert[] = []

  for (const product of products) {
    const chain = calcSupplyChain(product, blocks, settings)
    // Find the last block with a result
    const lastResult = chain.length > 0 ? chain[chain.length - 1] : null
    const days = lastResult?.sufficient_days ?? product.sufficient_days
    const until = lastResult?.sufficient_until ?? product.sufficient_until

    if (days === null || until === null) continue

    const level = getAlertLevel(days, settings)
    if (level === "ok") continue

    // Find the last non-archived block for recommendation
    const targetBlock =
      blocks.find((b) => b.order.status !== "archived" && b.order.status !== "delivered") ??
      blocks[blocks.length - 1]

    const suggestedQty = targetBlock
      ? calcSuggestedQty(
          product,
          settings,
          chain.length > 1
            ? chain[chain.length - 2]?.sufficient_until ?? null
            : product.sufficient_until,
          targetBlock.order.delivery_date,
        )
      : 0

    alerts.push({
      product,
      alert_level: level,
      sufficient_days: days,
      sufficient_until: until,
      recommendation: `Заказать ${suggestedQty} шт в ${targetBlock?.order.name ?? "новую поставку"}`,
      recommended_order_id: targetBlock?.order.id ?? null,
      recommended_qty: suggestedQty,
    })
  }

  // Sort: critical first, then warning; within same level — fewest days first
  alerts.sort((a, b) => {
    if (a.alert_level !== b.alert_level) {
      return a.alert_level === "critical" ? -1 : 1
    }
    return a.sufficient_days - b.sufficient_days
  })

  return alerts
}

// ── auto-numbering ───────────────────────────────────────────────────────────

/**
 * Generate the next supply order name/number.
 * Pattern: "Wookiee OOO №MM/N" where MM = month, N = sequence
 */
export function generateNextOrderName(
  entity: "ooo" | "ip",
  existingOrders: { name: string }[],
): string {
  const prefix = entity === "ooo" ? "OOO" : "ИП"
  const now = today()
  const month = String(now.getMonth() + 1).padStart(2, "0")

  // Find max sequence for this month
  const pattern = new RegExp(`№${month}/(\\d+)`)
  let maxSeq = 0
  for (const o of existingOrders) {
    const match = o.name.match(pattern)
    if (match) maxSeq = Math.max(maxSeq, parseInt(match[1], 10))
  }

  return `Wookiee ${prefix} №${month}/${maxSeq + 1}`
}
