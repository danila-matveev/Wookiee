import { Star } from "lucide-react"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import type { StoreResponseConfig, RatingConfig, ReviewResponseMode } from "@/types/comms-settings"

interface SettingsTabReviewsProps {
  config: StoreResponseConfig
  onUpdate: (partial: Partial<StoreResponseConfig>) => void
}

const ratings = [5, 4, 3, 2, 1] as const

export function SettingsTabReviews({ config, onUpdate }: SettingsTabReviewsProps) {
  const updateRating = (rating: 1 | 2 | 3 | 4 | 5, partial: Partial<RatingConfig>) => {
    onUpdate({
      reviewModes: {
        ...config.reviewModes,
        [rating]: { ...config.reviewModes[rating], ...partial },
      },
    })
  }

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-sm font-semibold mb-1">Режим ответа по рейтингу</h3>
        <p className="text-[12px] text-muted-foreground mb-4">Настройте, как AI отвечает на отзывы с разным рейтингом</p>
      </div>
      <div className="space-y-3">
        {ratings.map((rating) => {
          const rc = config.reviewModes[rating]
          return (
            <div key={rating} className="flex items-center gap-3 p-3 rounded-lg border border-border bg-card">
              <div className="flex items-center gap-1 w-[80px] shrink-0">
                {Array.from({ length: 5 }, (_, i) => (
                  <Star
                    key={i}
                    size={12}
                    className={cn(
                      i < rating ? "text-amber-400 fill-amber-400" : "text-border"
                    )}
                  />
                ))}
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={rc.enabled}
                  onChange={(e) => updateRating(rating, { enabled: e.target.checked })}
                  className="w-4 h-4 rounded border-border accent-accent"
                />
                <span className="text-[13px]">Включён</span>
              </label>
              <select
                value={rc.mode}
                onChange={(e) => updateRating(rating, { mode: e.target.value as ReviewResponseMode })}
                disabled={!rc.enabled}
                className="h-7 px-2 rounded-md border border-border bg-card text-[12px] disabled:opacity-40"
              >
                <option value="semi_auto">Полуавтомат</option>
                <option value="auto">Автомат</option>
              </select>
            </div>
          )
        })}
      </div>

      {/* AI system prompt for reviews */}
      <div>
        <label className="text-[12px] text-muted-foreground block mb-1">Инструкция AI для ответов на отзывы</label>
        <p className="text-[11px] text-muted-foreground mb-2">Системный промпт определяет, как AI классифицирует и отвечает на отзывы</p>
        <Textarea
          value={config.reviewPrompt}
          onChange={(e) => onUpdate({ reviewPrompt: e.target.value })}
          placeholder="Опишите, как AI должен отвечать на отзывы..."
          className="min-h-[200px] text-[13px] font-mono"
        />
      </div>
    </div>
  )
}
