import { create } from "zustand"
import { persist } from "zustand/middleware"
import type { ApiConnection, ConnectionStatus, ServiceType } from "@/types/integrations"
import { mockConnections } from "@/data/integrations-mock"

interface IntegrationsState {
  connections: ApiConnection[]
  addConnection: (connection: ApiConnection) => void
  removeConnection: (id: string) => void
  updateConnectionStatus: (id: string, status: ConnectionStatus) => void
  getConnectionsByService: (serviceType: ServiceType) => ApiConnection[]
  getActiveConnections: () => ApiConnection[]
  getConnectionById: (id: string) => ApiConnection | undefined
}

export const useIntegrationsStore = create<IntegrationsState>()(
  persist(
    (set, get) => ({
      connections: mockConnections,
      addConnection: (connection) =>
        set((s) => ({ connections: [...s.connections, connection] })),
      removeConnection: (id) =>
        set((s) => ({ connections: s.connections.filter((c) => c.id !== id) })),
      updateConnectionStatus: (id, status) =>
        set((s) => ({
          connections: s.connections.map((c) =>
            c.id === id ? { ...c, status } : c
          ),
        })),
      getConnectionsByService: (serviceType) =>
        get().connections.filter((c) => c.serviceType === serviceType),
      getActiveConnections: () =>
        get().connections.filter((c) => c.status === "active"),
      getConnectionById: (id) =>
        get().connections.find((c) => c.id === id),
    }),
    { name: "wookiee-integrations" }
  )
)
