import { useState, useMemo } from "react"
import { Plug } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { useIntegrationsStore } from "@/stores/integrations"
import { useCommsSettingsStore } from "@/stores/comms-settings"
import { getServiceDef } from "@/config/service-registry"
import { SettingsTabReviews } from "@/components/comms/settings-tab-reviews"
import { SettingsTabRecommendations } from "@/components/comms/settings-tab-recommendations"
import { SettingsTabSignature } from "@/components/comms/settings-tab-signature"
import { SettingsTabQuestions } from "@/components/comms/settings-tab-questions"
import { SettingsTabExtended } from "@/components/comms/settings-tab-extended"
import { SettingsTabAiLearning } from "@/components/comms/settings-tab-ai-learning"
import { SettingsTabChats } from "@/components/comms/settings-tab-chats"
import { createDefaultConfig } from "@/data/comms-settings-mock"
import type { StoreResponseConfig } from "@/types/comms-settings"

const tabs = [
  { id: "reviews", label: "Отзывы" },
  { id: "recommendations", label: "Рекомендации" },
  { id: "signature", label: "Подпись" },
  { id: "questions", label: "Вопросы" },
  { id: "extended", label: "Расширенные" },
  { id: "ai-learning", label: "Обучение AI" },
  { id: "chats", label: "Чаты" },
] as const

type TabId = (typeof tabs)[number]["id"]

export function CommsStoreSettingsPage() {
  const allConnections = useIntegrationsStore((s) => s.connections)
  const connections = useMemo(() => allConnections.filter((c) => c.status === "active"), [allConnections])
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>(
    connections[0]?.id ?? ""
  )
  const [activeTab, setActiveTab] = useState<TabId>("reviews")
  const configs = useCommsSettingsStore((s) => s.configs)
  const updateConfig = useCommsSettingsStore((s) => s.updateConfig)

  // Empty state
  if (connections.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] py-10">
        <div className="w-[72px] h-[72px] rounded-2xl bg-accent-soft border border-accent-border flex items-center justify-center mb-4">
          <Plug size={32} className="text-accent" />
        </div>
        <h2 className="text-xl font-bold">Нет подключений</h2>
        <p className="text-sm text-muted-foreground max-w-[380px] text-center leading-relaxed mt-2">
          Для настройки ответов необходимо подключить хотя бы один магазин в разделе Интеграции.
        </p>
        <Button variant="outline" className="mt-4" onClick={() => window.location.href = "/system/integrations"}>
          Перейти в Интеграции
        </Button>
      </div>
    )
  }

  const config = configs[selectedConnectionId] ?? createDefaultConfig(selectedConnectionId)
  const handleUpdate = (partial: Partial<StoreResponseConfig>) => {
    updateConfig(selectedConnectionId, partial)
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-[22px] font-bold">Настройки магазинов</h1>
          <p className="text-[13px] text-muted-foreground mt-0.5">Настройка AI-ответов для каждого подключения</p>
        </div>
        <select
          value={selectedConnectionId}
          onChange={(e) => setSelectedConnectionId(e.target.value)}
          className="h-8 px-3 rounded-lg border border-border bg-card text-sm focus:outline-none focus:ring-1 focus:ring-accent"
        >
          {connections.map((c) => {
            const def = getServiceDef(c.serviceType)
            return (
              <option key={c.id} value={c.id}>
                {def.label} — {c.name}
              </option>
            )
          })}
        </select>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 overflow-x-auto border-b border-border">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "px-3 py-2 text-[13px] font-medium border-b-2 transition-colors -mb-px whitespace-nowrap",
              activeTab === tab.id
                ? "border-accent text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="bg-card border border-border rounded-[10px] p-5">
        {activeTab === "reviews" && <SettingsTabReviews config={config} onUpdate={handleUpdate} />}
        {activeTab === "recommendations" && <SettingsTabRecommendations config={config} onUpdate={handleUpdate} />}
        {activeTab === "signature" && <SettingsTabSignature config={config} onUpdate={handleUpdate} />}
        {activeTab === "questions" && <SettingsTabQuestions config={config} onUpdate={handleUpdate} />}
        {activeTab === "extended" && <SettingsTabExtended config={config} onUpdate={handleUpdate} />}
        {activeTab === "ai-learning" && <SettingsTabAiLearning config={config} onUpdate={handleUpdate} />}
        {activeTab === "chats" && <SettingsTabChats config={config} onUpdate={handleUpdate} />}
      </div>
    </div>
  )
}
