import type { ApiConnection } from "@/types/integrations"

export const mockConnections: ApiConnection[] = [
  {
    id: "conn-wb-01",
    serviceType: "wildberries",
    name: "WB Основной",
    status: "active",
    lastSyncAt: "2026-03-12T10:30:00Z",
    credentialsMasked: { apiToken: "****..7f3a" },
  },
  {
    id: "conn-ozon-01",
    serviceType: "ozon",
    name: "Ozon Кабинет",
    status: "active",
    lastSyncAt: "2026-03-12T09:45:00Z",
    credentialsMasked: { clientId: "****..2841", apiKey: "****..9bc1" },
  },
]
