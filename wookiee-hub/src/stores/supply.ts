// ---------------------------------------------------------------------------
// Supply Planning — Zustand store
// ---------------------------------------------------------------------------

import { create } from "zustand"
import { persist } from "zustand/middleware"
import { addDays, format } from "date-fns"
import type {
  Entity,
  SupplyViewMode,
  SupplySettings,
  SupplyProduct,
  SupplyOrder,
  SupplyOrderItem,
  SupplyBlock,
} from "@/types/supply"
import {
  MOCK_SETTINGS,
  getMockProducts,
  getMockOrders,
  getMockOrderItems,
} from "@/data/supply-mock"
import { generateNextOrderName } from "@/lib/supply-calc"

// ── State ────────────────────────────────────────────────────────────────────

interface SupplyState {
  // UI state
  entity: Entity
  viewMode: SupplyViewMode
  settingsOpen: boolean

  // Data
  settings: Record<Entity, SupplySettings>
  products: SupplyProduct[]
  orders: SupplyOrder[]
  orderItems: SupplyOrderItem[]

  // Actions — UI
  setEntity: (entity: Entity) => void
  setViewMode: (mode: SupplyViewMode) => void
  setSettingsOpen: (open: boolean) => void

  // Actions — Settings
  updateSettings: (entity: Entity, patch: Partial<SupplySettings>) => void

  // Actions — Orders
  createOrder: (entity: Entity) => SupplyOrder
  updateOrder: (orderId: string, patch: Partial<SupplyOrder>) => void
  deleteOrder: (orderId: string) => void

  // Actions — Items (quantities)
  setItemQuantity: (orderId: string, barcode: string, quantity: number) => void

  // Derived
  getBlocks: () => SupplyBlock[]
  getActiveSettings: () => SupplySettings

  // Init
  loadMockData: (entity: Entity) => void
}

// ── Store ────────────────────────────────────────────────────────────────────

export const useSupplyStore = create<SupplyState>()(
  persist(
    (set, get) => ({
      entity: "ooo",
      viewMode: "table",
      settingsOpen: false,

      settings: { ...MOCK_SETTINGS },
      products: getMockProducts("ooo"),
      orders: getMockOrders("ooo"),
      orderItems: getMockOrderItems("ooo"),

      // ── UI actions ────────────────────────────────────────────────

      setEntity: (entity) => {
        set({ entity })
        get().loadMockData(entity)
      },

      setViewMode: (viewMode) => set({ viewMode }),

      setSettingsOpen: (settingsOpen) => set({ settingsOpen }),

      // ── Settings ──────────────────────────────────────────────────

      updateSettings: (entity, patch) =>
        set((s) => ({
          settings: {
            ...s.settings,
            [entity]: { ...s.settings[entity], ...patch },
          },
        })),

      // ── Orders ────────────────────────────────────────────────────

      createOrder: (entity) => {
        const state = get()
        const settings = state.settings[entity]
        const orderDate = format(new Date(), "yyyy-MM-dd")
        const shipmentDate = format(
          addDays(new Date(), settings.default_lead_time_days),
          "yyyy-MM-dd",
        )
        const deliveryDate = format(
          addDays(
            new Date(),
            settings.default_lead_time_days + settings.default_transit_days,
          ),
          "yyyy-MM-dd",
        )

        const newOrder: SupplyOrder = {
          id: `o-${Date.now()}`,
          name: generateNextOrderName(entity, state.orders),
          entity,
          return_rate: settings.default_return_rate,
          order_date: orderDate,
          shipment_date: shipmentDate,
          delivery_date: deliveryDate,
          order_number: "",
          offset_days: settings.default_offset_days,
          status: "draft",
          sort_order: state.orders.length + 1,
          notes: "",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }

        set((s) => ({ orders: [...s.orders, newOrder] }))
        return newOrder
      },

      updateOrder: (orderId, patch) =>
        set((s) => ({
          orders: s.orders.map((o) =>
            o.id === orderId
              ? { ...o, ...patch, updated_at: new Date().toISOString() }
              : o,
          ),
        })),

      deleteOrder: (orderId) =>
        set((s) => ({
          orders: s.orders.filter((o) => o.id !== orderId),
          orderItems: s.orderItems.filter((i) => i.supply_order_id !== orderId),
        })),

      // ── Items ─────────────────────────────────────────────────────

      setItemQuantity: (orderId, barcode, quantity) =>
        set((s) => {
          const existing = s.orderItems.find(
            (i) => i.supply_order_id === orderId && i.barcode === barcode,
          )
          if (existing) {
            return {
              orderItems: s.orderItems.map((i) =>
                i.id === existing.id ? { ...i, quantity } : i,
              ),
            }
          }
          return {
            orderItems: [
              ...s.orderItems,
              {
                id: `item-${Date.now()}-${barcode}`,
                supply_order_id: orderId,
                artikul_id: "",
                barcode,
                quantity,
              },
            ],
          }
        }),

      // ── Derived ───────────────────────────────────────────────────

      getBlocks: () => {
        const { orders, orderItems } = get()
        return orders
          .filter((o) => o.status !== "archived")
          .sort((a, b) => a.sort_order - b.sort_order)
          .map((order) => {
            const items = new Map<string, number>()
            for (const item of orderItems) {
              if (item.supply_order_id === order.id) {
                items.set(item.barcode, item.quantity)
              }
            }
            return { order, items }
          })
      },

      getActiveSettings: () => {
        const { entity, settings } = get()
        return settings[entity]
      },

      // ── Init ──────────────────────────────────────────────────────

      loadMockData: (entity) =>
        set({
          products: getMockProducts(entity),
          orders: getMockOrders(entity),
          orderItems: getMockOrderItems(entity),
        }),
    }),
    {
      name: "wookiee-supply",
      partialize: (state) => ({
        entity: state.entity,
        viewMode: state.viewMode,
        settings: state.settings,
      }),
    },
  ),
)
