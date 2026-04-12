// ---------------------------------------------------------------------------
// Supply Planning — API fetchers (Phase 1: returns mock data)
// ---------------------------------------------------------------------------

import type { Entity, SupplyProduct, SupplyOrder, SupplyOrderItem, SupplySettings } from "@/types/supply"
import { getMockProducts, getMockOrders, getMockOrderItems, MOCK_SETTINGS } from "@/data/supply-mock"

// Phase 2 will replace these with real API calls via get() from api-client.ts

export async function fetchSupplyProducts(entity: Entity): Promise<SupplyProduct[]> {
  return getMockProducts(entity)
}

export async function fetchSupplyOrders(entity: Entity): Promise<SupplyOrder[]> {
  return getMockOrders(entity)
}

export async function fetchSupplyOrderItems(entity: Entity): Promise<SupplyOrderItem[]> {
  return getMockOrderItems(entity)
}

export async function fetchSupplySettings(entity: Entity): Promise<SupplySettings> {
  return MOCK_SETTINGS[entity]
}
