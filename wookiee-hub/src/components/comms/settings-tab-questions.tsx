import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import type { StoreResponseConfig } from "@/types/comms-settings"

interface SettingsTabQuestionsProps {
  config: StoreResponseConfig
  onUpdate: (partial: Partial<StoreResponseConfig>) => void
}

const modes = [
  { value: "disabled", label: "Отключён", desc: "AI не отвечает на вопросы" },
  { value: "semi_auto", label: "Полуавтомат", desc: "AI генерирует черновик, менеджер публикует" },
  { value: "auto", label: "Автомат", desc: "AI отвечает и публикует автоматически" },
] as const

export function SettingsTabQuestions({ config, onUpdate }: SettingsTabQuestionsProps) {
  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-sm font-semibold mb-1">Режим ответов на вопросы</h3>
        <p className="text-[12px] text-muted-foreground mb-4">Как AI обрабатывает вопросы покупателей</p>
      </div>
      <div className="space-y-2">
        {modes.map((mode) => (
          <label
            key={mode.value}
            className={cn(
              "flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
              config.questionMode === mode.value
                ? "border-accent bg-accent-soft"
                : "border-border hover:border-accent-border/50"
            )}
          >
            <input
              type="radio"
              name="questionMode"
              value={mode.value}
              checked={config.questionMode === mode.value}
              onChange={() => onUpdate({ questionMode: mode.value })}
              className="mt-0.5 accent-accent"
            />
            <div>
              <div className="text-[13px] font-medium">{mode.label}</div>
              <div className="text-[12px] text-muted-foreground">{mode.desc}</div>
            </div>
          </label>
        ))}
      </div>

      {/* AI system prompt for questions */}
      {config.questionMode !== "disabled" && (
        <div>
          <label className="text-[12px] text-muted-foreground block mb-1">Инструкция AI для ответов на вопросы</label>
          <Textarea
            value={config.questionPrompt}
            onChange={(e) => onUpdate({ questionPrompt: e.target.value })}
            placeholder="Опишите, как AI должен отвечать на вопросы покупателей..."
            className="min-h-[150px] text-[13px] font-mono"
          />
        </div>
      )}
    </div>
  )
}
