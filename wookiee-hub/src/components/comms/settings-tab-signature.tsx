import { Textarea } from "@/components/ui/textarea"
import type { StoreResponseConfig } from "@/types/comms-settings"

interface SettingsTabSignatureProps {
  config: StoreResponseConfig
  onUpdate: (partial: Partial<StoreResponseConfig>) => void
}

export function SettingsTabSignature({ config, onUpdate }: SettingsTabSignatureProps) {
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold mb-1">Подпись</h3>
        <p className="text-[12px] text-muted-foreground mb-4">Автоматическая подпись в конце ответа</p>
      </div>
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={config.signatureTemplate.enabled}
          onChange={(e) =>
            onUpdate({
              signatureTemplate: { ...config.signatureTemplate, enabled: e.target.checked },
            })
          }
          className="w-4 h-4 rounded border-border accent-accent"
        />
        <span className="text-[13px]">Включить подпись</span>
      </label>
      <div>
        <label className="text-[12px] text-muted-foreground block mb-1">
          Шаблон (переменные: {"{{brandName}}"}, {"{{storeName}}"})
        </label>
        <Textarea
          value={config.signatureTemplate.template}
          onChange={(e) =>
            onUpdate({
              signatureTemplate: { ...config.signatureTemplate, template: e.target.value },
            })
          }
          disabled={!config.signatureTemplate.enabled}
          placeholder="С уважением, команда {{brandName}}"
          className="min-h-[80px] text-[13px]"
        />
      </div>
    </div>
  )
}
