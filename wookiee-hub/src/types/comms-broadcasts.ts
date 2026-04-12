import type { ServiceType } from "./integrations"

export type BroadcastStatus = "draft" | "scheduled" | "sent" | "error"

export interface Broadcast {
  id: string
  name: string
  connectionId: string
  serviceType: ServiceType
  storeName: string
  recipientCount: number
  message: string
  photoUrl?: string
  status: BroadcastStatus
  createdAt: string
  scheduledAt?: string
  sentAt?: string
}
