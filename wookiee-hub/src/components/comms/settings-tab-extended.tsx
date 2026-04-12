import { useState } from "react"
import { X } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import type { StoreResponseConfig, TonePreset } from "@/types/comms-settings"

interface SettingsTabExtendedProps {
  config: StoreResponseConfig
  onUpdate: (partial: Partial<StoreResponseConfig>) => void
}

const tonePresets = [
  { value: "formal", label: "Формальный" },
  { value: "friendly", label: "Дружелюбный" },
  { value: "neutral", label: "Нейтральный" },
  { value: "playful", label: "Игривый" },
  { value: "wookiee", label: "WOOKIEE" },
  { value: "custom", label: "Кастом" },
] as const

const lengths = [
  { value: "short", label: "Короткий" },
  { value: "medium", label: "Средний" },
  { value: "long", label: "Длинный" },
] as const

export function SettingsTabExtended({ config, onUpdate }: SettingsTabExtendedProps) {
  const [stopWordInput, setStopWordInput] = useState("")

  const addStopWord = (word: string) => {
    const trimmed = word.trim()
    if (!trimmed || config.stopWords.includes(trimmed)) return
    onUpdate({ stopWords: [...config.stopWords, trimmed] })
  }

  const removeStopWord = (index: number) => {
    onUpdate({ stopWords: config.stopWords.filter((_, i) => i !== index) })
  }

  const handleStopWordKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault()
      const value = stopWordInput.replace(/,/g, "").trim()
      if (value) {
        addStopWord(value)
        setStopWordInput("")
      }
    }
    if (e.key === "Backspace" && !stopWordInput && config.stopWords.length > 0) {
      removeStopWord(config.stopWords.length - 1)
    }
  }

  const handleTonePreset = (preset: TonePreset) => {
    onUpdate({
      toneOfVoice: {
        preset,
        custom: preset === "custom" ? config.toneOfVoice.custom : "",
      },
    })
  }

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-sm font-semibold mb-1">Расширенные настройки</h3>
        <p className="text-[12px] text-muted-foreground">Тонкая настройка стиля ответов AI</p>
      </div>

      {/* Salutation */}
      <div>
        <label className="text-[12px] text-muted-foreground block mb-1">Обращение к клиенту</label>
        <Input
          value={config.salutation}
          onChange={(e) => onUpdate({ salutation: e.target.value })}
          placeholder="Привет! Это Wookiee 💛"
        />
      </div>

      {/* Tone of voice */}
      <div>
        <label className="text-[12px] text-muted-foreground block mb-2">Тон общения</label>
        <div className="flex flex-wrap gap-1 p-1 rounded-lg bg-bg-soft w-fit">
          {tonePresets.map((t) => (
            <button
              key={t.value}
              onClick={() => handleTonePreset(t.value)}
              className={cn(
                "px-3 py-1.5 rounded-md text-[13px] font-medium transition-all",
                config.toneOfVoice.preset === t.value
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        {config.toneOfVoice.preset === "wookiee" && (
          <p className="text-[11px] text-muted-foreground mt-2">
            Близкая подруга, которая разбирается в белье. Всегда на «ты». Тёплый, живой, экспертный, честный тон. Без канцеляризмов.
          </p>
        )}
        {config.toneOfVoice.preset === "custom" && (
          <Textarea
            value={config.toneOfVoice.custom}
            onChange={(e) =>
              onUpdate({ toneOfVoice: { preset: "custom", custom: e.target.value } })
            }
            placeholder="Опишите желаемый тон общения..."
            className="mt-2 min-h-[80px] text-[13px]"
          />
        )}
      </div>

      {/* Response length */}
      <div>
        <label className="text-[12px] text-muted-foreground block mb-2">Длина ответа</label>
        <div className="flex gap-1 p-1 rounded-lg bg-bg-soft w-fit">
          {lengths.map((l) => (
            <button
              key={l.value}
              onClick={() => onUpdate({ responseLength: l.value })}
              className={cn(
                "px-3 py-1.5 rounded-md text-[13px] font-medium transition-all",
                config.responseLength === l.value
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>

      {/* Negative handling */}
      <div className="space-y-3">
        <div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={config.negativeHandling.enabled}
              onChange={(e) =>
                onUpdate({
                  negativeHandling: { ...config.negativeHandling, enabled: e.target.checked },
                })
              }
              className="w-4 h-4 rounded border-border accent-accent"
            />
            <span className="text-[13px] font-medium">Работа с негативом</span>
          </label>
          <p className="text-[11px] text-muted-foreground mt-0.5 ml-6">
            Специальная обработка негативных отзывов: сочувствие, решение, перевод в чат
          </p>
        </div>
        {config.negativeHandling.enabled && (
          <>
            <Textarea
              value={config.negativeHandling.prompt}
              onChange={(e) =>
                onUpdate({
                  negativeHandling: { ...config.negativeHandling, prompt: e.target.value },
                })
              }
              placeholder="Инструкция для негативных отзывов..."
              className="min-h-[100px] text-[13px]"
            />
            <div>
              <label className="text-[12px] text-muted-foreground block mb-1">Шаблон CTA</label>
              <Input
                value={config.negativeHandling.ctaTemplate}
                onChange={(e) =>
                  onUpdate({
                    negativeHandling: { ...config.negativeHandling, ctaTemplate: e.target.value },
                  })
                }
                placeholder="Напиши нам в чат заказа — разберёмся и всё исправим."
                className="text-[13px]"
              />
            </div>
          </>
        )}
      </div>

      {/* Stop words */}
      <div>
        <label className="text-[12px] text-muted-foreground block mb-1">Стоп-слова</label>
        <div className="flex flex-wrap items-center gap-1.5 p-2 rounded-lg border border-border min-h-[38px] focus-within:ring-1 focus-within:ring-ring">
          {config.stopWords.map((word, i) => (
            <span
              key={`${word}-${i}`}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-bg-soft text-[12px] font-medium text-foreground"
            >
              {word}
              <button
                onClick={() => removeStopWord(i)}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                <X size={10} />
              </button>
            </span>
          ))}
          <input
            value={stopWordInput}
            onChange={(e) => setStopWordInput(e.target.value)}
            onKeyDown={handleStopWordKeyDown}
            placeholder={config.stopWords.length === 0 ? "скидка, промокод, конкурент" : ""}
            className="flex-1 min-w-[120px] bg-transparent text-[13px] outline-none placeholder:text-muted-foreground"
          />
        </div>
        <p className="text-[11px] text-muted-foreground mt-1">
          Нажмите Enter или запятую для добавления
        </p>
      </div>
    </div>
  )
}
