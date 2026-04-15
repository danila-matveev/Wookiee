export type ServiceType = "wildberries" | "ozon"

export type ConnectionStatus = "active" | "inactive" | "error"

export interface ApiConnection {
  id: string
  serviceType: ServiceType
  name: string
  status: ConnectionStatus
  lastSyncAt: string
  credentialsMasked: Record<string, string>
  error?: string
}
