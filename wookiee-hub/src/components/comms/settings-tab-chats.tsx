import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import type { StoreResponseConfig } from "@/types/comms-settings"

interface SettingsTabChatsProps {
  config: StoreResponseConfig
  onUpdate: (partial: Partial<StoreResponseConfig>) => void
}

const modes = [
  { value: "disabled", label: "Отключён", desc: "AI не отвечает в чатах" },
  { value: "semi_auto", label: "Полуавтомат", desc: "AI генерирует черновик, менеджер отправляет" },
  { value: "auto", label: "Автомат", desc: "AI отвечает в чатах автоматически" },
] as const

export function SettingsTabChats({ config, onUpdate }: SettingsTabChatsProps) {
  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-sm font-semibold mb-1">Режим ответов в чатах</h3>
        <p className="text-[12px] text-muted-foreground mb-4">Как AI обрабатывает сообщения в чатах</p>
      </div>
      <div className="space-y-2">
        {modes.map((mode) => (
          <label
            key={mode.value}
            className={cn(
              "flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
              config.chatMode === mode.value
                ? "border-accent bg-accent-soft"
                : "border-border hover:border-accent-border/50"
            )}
          >
            <input
              type="radio"
              name="chatMode"
              value={mode.value}
              checked={config.chatMode === mode.value}
              onChange={() => onUpdate({ chatMode: mode.value })}
              className="mt-0.5 accent-accent"
            />
            <div>
              <div className="text-[13px] font-medium">{mode.label}</div>
              <div className="text-[12px] text-muted-foreground">{mode.desc}</div>
            </div>
          </label>
        ))}
      </div>

      {/* AI system prompt for chats */}
      {config.chatMode !== "disabled" && (
        <div>
          <label className="text-[12px] text-muted-foreground block mb-1">Инструкция AI для чатов</label>
          <Textarea
            value={config.chatPrompt}
            onChange={(e) => onUpdate({ chatPrompt: e.target.value })}
            placeholder="Опишите, как AI должен общаться в чатах..."
            className="min-h-[150px] text-[13px] font-mono"
          />
        </div>
      )}
    </div>
  )
}
