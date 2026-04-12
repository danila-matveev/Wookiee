import { useState, useEffect } from "react"
import { Star, Archive, Sparkles, RefreshCw, Send, Loader2, DollarSign } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { getServiceDef } from "@/config/service-registry"
import { useCommsStore } from "@/stores/comms"
import { useCommsSettingsStore } from "@/stores/comms-settings"
import { commsService } from "@/lib/comms-service"
import type { Review } from "@/types/comms"

interface ReviewDetailProps {
  review: Review | null
  className?: string
}

export function ReviewDetail({ review, className }: ReviewDetailProps) {
  const [isGenerating, setIsGenerating] = useState(false)
  const [isPublishing, setIsPublishing] = useState(false)
  const [draftText, setDraftText] = useState("")
  const [lastCost, setLastCost] = useState<number | null>(null)
  const { setAiDraft, publishResponse, updateReviewStatus, addCost } = useCommsStore()
  const getOrCreateConfig = useCommsSettingsStore((s) => s.getOrCreateConfig)

  // Sync draftText when switching to a different review (must be before early return)
  useEffect(() => {
    if (!review) return
    if (review.aiDraft && review.status !== "published") {
      setDraftText(review.aiDraft)
    } else {
      setDraftText("")
    }
    setLastCost(null)
  }, [review?.id])

  if (!review) {
    return (
      <div className={cn("flex items-center justify-center h-full text-muted-foreground", className)}>
        <div className="text-center">
          <div className="text-4xl mb-3 opacity-30">💬</div>
          <p className="text-sm">Выберите отзыв из списка</p>
        </div>
      </div>
    )
  }

  const def = getServiceDef(review.serviceType)
  const dateStr = new Date(review.createdAt).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  })

  const handleGenerate = async () => {
    setIsGenerating(true)
    try {
      const config = getOrCreateConfig(review.connectionId)
      const result = await commsService.generateAiResponse(review, config)
      setAiDraft(review.id, result.text)
      setDraftText(result.text)
      setLastCost(result.usage.cost_usd)
      addCost(result.usage.cost_usd)
    } finally {
      setIsGenerating(false)
    }
  }

  const handlePublish = async () => {
    const text = draftText || review.aiDraft || ""
    if (!text) return
    setIsPublishing(true)
    try {
      const result = await commsService.publishResponse(review.connectionId, review.id, text)
      if (!result.success) {
        alert(result.message || "Отправка отключена")
        return
      }
      publishResponse(review.id, text)
    } finally {
      setIsPublishing(false)
    }
  }

  const handleArchive = () => {
    updateReviewStatus(review.id, "archived")
  }

  const currentDraft = draftText || review.aiDraft || ""

  return (
    <div className={cn("overflow-y-auto", className)}>
      <div className="space-y-4">
        {/* Product info */}
        <div className="bg-card border border-border rounded-[10px] p-4">
          <div className="flex items-center gap-2 mb-2">
            <span
              className="px-2 py-0.5 rounded text-[11px] font-bold text-white"
              style={{ backgroundColor: def.color }}
            >
              {def.label}
            </span>
            <span className="text-[12px] text-muted-foreground">{review.productArticle}</span>
          </div>
          <h2 className="text-[15px] font-semibold">{review.productName}</h2>
          <p className="text-[12px] text-muted-foreground mt-1">{review.authorName} · {dateStr}</p>
        </div>

        {/* Review content */}
        <div className="bg-card border border-border rounded-[10px] p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {review.rating > 0 && (
                <div className="flex gap-0.5">
                  {[1, 2, 3, 4, 5].map((s) => (
                    <Star
                      key={s}
                      size={14}
                      className={cn(
                        s <= review.rating
                          ? "text-amber-400 fill-amber-400"
                          : "text-border"
                      )}
                    />
                  ))}
                </div>
              )}
              {review.source === "question" && (
                <span className="text-[11px] bg-blue-500/10 text-blue-600 dark:text-blue-400 px-2 py-0.5 rounded-full font-medium">
                  Вопрос
                </span>
              )}
            </div>
            {review.purchaseStatus === "verified" && (
              <span className="text-[11px] text-green-600 dark:text-green-400 font-medium">Покупка подтверждена</span>
            )}
          </div>

          {review.pros && (
            <div>
              <div className="text-[11px] text-muted-foreground font-medium mb-1">Достоинства</div>
              <p className="text-[13px] leading-relaxed">{review.pros}</p>
            </div>
          )}
          {review.cons && (
            <div>
              <div className="text-[11px] text-muted-foreground font-medium mb-1">Недостатки</div>
              <p className="text-[13px] leading-relaxed">{review.cons}</p>
            </div>
          )}
          {review.comment && (
            <div>
              <div className="text-[11px] text-muted-foreground font-medium mb-1">Комментарий</div>
              <p className="text-[13px] leading-relaxed">{review.comment}</p>
            </div>
          )}
        </div>

        {/* Response section */}
        {review.status === "published" && review.publishedResponse ? (
          <div className="bg-accent-soft border border-accent-border rounded-[10px] p-4">
            <div className="text-[11px] text-accent font-semibold mb-2">Опубликованный ответ</div>
            <p className="text-[13px] leading-relaxed">{review.publishedResponse}</p>
            {review.respondedAt && (
              <p className="text-[11px] text-muted-foreground mt-2">
                {new Date(review.respondedAt).toLocaleDateString("ru-RU", { day: "2-digit", month: "long", hour: "2-digit", minute: "2-digit" })}
              </p>
            )}
          </div>
        ) : (
          <div className="bg-card border border-border rounded-[10px] p-4 space-y-3">
            <div className="text-[13px] font-semibold">Ответ</div>

            {!currentDraft && !isGenerating ? (
              <Button onClick={handleGenerate} variant="outline" className="w-full">
                <Sparkles size={14} />
                Сгенерировать ответ
              </Button>
            ) : isGenerating ? (
              <div className="flex items-center justify-center py-6 gap-2 text-muted-foreground">
                <Loader2 size={16} className="animate-spin" />
                <span className="text-[13px]">Генерация ответа...</span>
              </div>
            ) : (
              <>
                <Textarea
                  value={draftText}
                  onChange={(e) => setDraftText(e.target.value)}
                  className="min-h-[100px] text-[13px]"
                />
                {lastCost !== null && (
                  <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                    <DollarSign size={10} />
                    <span>${lastCost.toFixed(4)}</span>
                  </div>
                )}
                <div className="flex gap-2 flex-wrap">
                  <Button variant="outline" size="sm" onClick={handleGenerate} disabled={isGenerating}>
                    <Sparkles size={12} />
                    Улучшить
                  </Button>
                  <Button variant="outline" size="sm" onClick={handleGenerate} disabled={isGenerating}>
                    <RefreshCw size={12} />
                    Перегенерировать
                  </Button>
                  <div className="flex-1" />
                  <Button size="sm" onClick={handlePublish} disabled={isPublishing || !draftText}>
                    {isPublishing ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
                    Опубликовать
                  </Button>
                </div>
              </>
            )}
          </div>
        )}

        {/* Actions */}
        {review.status !== "published" && review.status !== "archived" && (
          <div className="flex justify-end">
            <Button variant="ghost" size="sm" onClick={handleArchive}>
              <Archive size={12} />
              Архивировать
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
