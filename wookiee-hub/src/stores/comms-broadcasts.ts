import { create } from "zustand"
import { persist } from "zustand/middleware"
import type { Broadcast } from "@/types/comms-broadcasts"

interface BroadcastsState {
  broadcasts: Broadcast[]
  addBroadcast: (broadcast: Broadcast) => void
  updateBroadcast: (id: string, partial: Partial<Broadcast>) => void
  deleteBroadcast: (id: string) => void
}

const mockBroadcasts: Broadcast[] = [
  {
    id: "bc-001",
    name: "Рассылка весенняя коллекция",
    connectionId: "conn-wb-01",
    serviceType: "wildberries",
    storeName: "WB Основной",
    recipientCount: 199,
    message:
      "Весенняя коллекция уже в продаже! Скидки до 30% на новые модели. Успейте заказать первыми.",
    status: "sent",
    createdAt: "2026-03-01T10:00:00Z",
    sentAt: "2026-03-02T09:00:00Z",
  },
  {
    id: "bc-002",
    name: "Новинки марта",
    connectionId: "conn-ozon-01",
    serviceType: "ozon",
    storeName: "Ozon Главный",
    recipientCount: 87,
    message:
      "Новые поступления марта! Более 50 новых позиций в каталоге. Бесплатная доставка от 2000 руб.",
    status: "draft",
    createdAt: "2026-03-10T14:30:00Z",
  },
  {
    id: "bc-003",
    name: "Акция 8 марта",
    connectionId: "conn-wb-01",
    serviceType: "wildberries",
    storeName: "WB Основной",
    recipientCount: 156,
    message:
      "С праздником 8 марта! Дарим промокод SPRING15 на скидку 15% на весь ассортимент.",
    status: "scheduled",
    createdAt: "2026-03-05T11:00:00Z",
    scheduledAt: "2026-03-08T08:00:00Z",
  },
]

export const useBroadcastsStore = create<BroadcastsState>()(
  persist(
    (set) => ({
      broadcasts: mockBroadcasts,
      addBroadcast: (broadcast) =>
        set((s) => ({ broadcasts: [broadcast, ...s.broadcasts] })),
      updateBroadcast: (id, partial) =>
        set((s) => ({
          broadcasts: s.broadcasts.map((b) =>
            b.id === id ? { ...b, ...partial } : b
          ),
        })),
      deleteBroadcast: (id) =>
        set((s) => ({ broadcasts: s.broadcasts.filter((b) => b.id !== id) })),
    }),
    { name: "wookiee-comms-broadcasts" }
  )
)
