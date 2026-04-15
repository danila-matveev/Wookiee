import type { ServiceType } from "@/types/integrations"

export interface ServiceDef {
  type: ServiceType
  label: string
  color: string
  icon: string
  credentialFields: string[]
}

export const SERVICE_REGISTRY: Record<ServiceType, ServiceDef> = {
  wildberries: {
    type: "wildberries",
    label: "Wildberries",
    color: "#CB11AB",
    icon: "wildberries",
    credentialFields: ["apiToken"],
  },
  ozon: {
    type: "ozon",
    label: "Ozon",
    color: "#005BFF",
    icon: "ozon",
    credentialFields: ["clientId", "apiKey"],
  },
}

/** Coming soon services (metadata only, not ServiceType) */
export const COMING_SOON_SERVICES = [
  { key: "yandex_market", label: "Yandex Market" },
  { key: "moysklad", label: "МойСклад" },
  { key: "bitrix24", label: "Битрикс24" },
  { key: "finolog", label: "Финолог" },
] as const

export function getServiceDef(type: ServiceType): ServiceDef {
  return SERVICE_REGISTRY[type]
}
