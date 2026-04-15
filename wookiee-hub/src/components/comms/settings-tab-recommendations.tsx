import { X } from "lucide-react"
import { useState } from "react"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import type { RecommendationSource, StoreResponseConfig } from "@/types/comms-settings"

interface SettingsTabRecommendationsProps {
  config: StoreResponseConfig
  onUpdate: (partial: Partial<StoreResponseConfig>) => void
}

const SOURCE_OPTIONS: { value: RecommendationSource; label: string }[] = [
  { value: "matrix", label: "Из товарной матрицы" },
  { value: "popular", label: "Популярные товары" },
  { value: "manual", label: "Вручную" },
]

export function SettingsTabRecommendations({ config, onUpdate }: SettingsTabRecommendationsProps) {
  const [newExclude, setNewExclude] = useState("")

  const updateRecommend = (patch: Partial<StoreResponseConfig["recommendProducts"]>) => {
    onUpdate({ recommendProducts: { ...config.recommendProducts, ...patch } })
  }

  const addExcludeArticle = () => {
    const value = newExclude.trim()
    if (!value || config.recommendProducts.excludeArticles.includes(value)) return
    updateRecommend({ excludeArticles: [...config.recommendProducts.excludeArticles, value] })
    setNewExclude("")
  }

  const removeExcludeArticle = (article: string) => {
    updateRecommend({
      excludeArticles: config.recommendProducts.excludeArticles.filter((a) => a !== article),
    })
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold mb-1">Рекомендации товаров</h3>
        <p className="text-[12px] text-muted-foreground mb-4">
          AI может рекомендовать другие товары в ответе на отзыв
        </p>
      </div>

      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={config.recommendProducts.enabled}
          onChange={(e) => updateRecommend({ enabled: e.target.checked })}
          className="w-4 h-4 rounded border-border accent-accent"
        />
        <span className="text-[13px]">Включить рекомендации</span>
      </label>

      {/* Source selection */}
      <div>
        <label className="text-[12px] text-muted-foreground block mb-2">Источник рекомендаций</label>
        <div className="space-y-1.5">
          {SOURCE_OPTIONS.map((opt) => (
            <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="rec-source"
                value={opt.value}
                checked={config.recommendProducts.source === opt.value}
                onChange={() => updateRecommend({ source: opt.value })}
                disabled={!config.recommendProducts.enabled}
                className="w-3.5 h-3.5 accent-accent"
              />
              <span
                className={cn(
                  "text-[13px]",
                  !config.recommendProducts.enabled && "opacity-40"
                )}
              >
                {opt.label}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Max count */}
      <div>
        <label className="text-[12px] text-muted-foreground block mb-1">Максимум рекомендаций</label>
        <input
          type="number"
          min={1}
          max={10}
          value={config.recommendProducts.maxCount}
          onChange={(e) => updateRecommend({ maxCount: Number(e.target.value) })}
          disabled={!config.recommendProducts.enabled}
          className="h-8 w-20 px-2 rounded-lg border border-border bg-card text-sm disabled:opacity-40"
        />
      </div>

      {/* Exclude articles */}
      <div>
        <label className="text-[12px] text-muted-foreground block mb-1">
          Исключить артикулы из рекомендаций
        </label>
        <div className="flex flex-wrap gap-1 mb-1.5">
          {config.recommendProducts.excludeArticles.map((article) => (
            <span
              key={article}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-muted text-[11px]"
            >
              {article}
              <button
                type="button"
                onClick={() => removeExcludeArticle(article)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X size={10} />
              </button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <Input
            value={newExclude}
            onChange={(e) => setNewExclude(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault()
                addExcludeArticle()
              }
            }}
            placeholder="Артикул..."
            disabled={!config.recommendProducts.enabled}
            className="h-7 text-[12px] max-w-[180px]"
          />
        </div>
      </div>

      {/* Manual recommendation text (shown only for "manual" source) */}
      {config.recommendProducts.source === "manual" && (
        <div>
          <label className="text-[12px] text-muted-foreground block mb-1">
            Текст рекомендации (вручную)
          </label>
          <Textarea
            placeholder="Также рекомендуем обратить внимание на..."
            disabled={!config.recommendProducts.enabled}
            className="min-h-[80px] text-[13px] disabled:opacity-40"
          />
        </div>
      )}
    </div>
  )
}
