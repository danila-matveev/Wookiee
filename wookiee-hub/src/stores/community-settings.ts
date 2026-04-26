import { create } from "zustand"
import { persist } from "zustand/middleware"
import type { StoreResponseConfig } from "@/types/community-settings"
import { createDefaultConfig, mockCommsSettingsConfigs } from "@/data/community-settings-mock"

interface CommsSettingsState {
  configs: Record<string, StoreResponseConfig>
  getOrCreateConfig: (connectionId: string) => StoreResponseConfig
  updateConfig: (connectionId: string, partial: Partial<StoreResponseConfig>) => void
}

/** Ensure persisted config has all fields from defaults */
function migrateConfig(stored: Partial<StoreResponseConfig>, connectionId: string): StoreResponseConfig {
  const defaults = createDefaultConfig(connectionId)
  return { ...defaults, ...stored, connectionId }
}

export const useCommsSettingsStore = create<CommsSettingsState>()(
  persist(
    (set, get) => ({
      configs: mockCommsSettingsConfigs,
      getOrCreateConfig: (connectionId) => {
        const existing = get().configs[connectionId]
        if (existing) return migrateConfig(existing, connectionId)
        const newConfig = createDefaultConfig(connectionId)
        set((s) => ({
          configs: { ...s.configs, [connectionId]: newConfig },
        }))
        return newConfig
      },
      updateConfig: (connectionId, partial) =>
        set((s) => ({
          configs: {
            ...s.configs,
            [connectionId]: {
              ...createDefaultConfig(connectionId),
              ...s.configs[connectionId],
              ...partial,
              connectionId,
            },
          },
        })),
    }),
    { name: "wookiee-comms-settings" }
  )
)
