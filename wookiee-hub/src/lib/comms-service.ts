import { get, post } from "@/lib/api-client"
import type { Review, AiGenerationResult } from "@/types/comms"
import type { StoreResponseConfig } from "@/types/comms-settings"

function buildSystemPrompt(config: StoreResponseConfig): string {
  const parts: string[] = []

  // Tone instruction
  const toneMap: Record<string, string> = {
    formal: "Отвечайте в официальном, деловом тоне.",
    friendly: "Отвечайте дружелюбно и тепло.",
    neutral: "Отвечайте в нейтральном, сбалансированном тоне.",
    playful: "Отвечайте в лёгком, игривом тоне.",
    wookiee:
      "Ты — голос бренда WOOKIEE. Общаешься как близкая подруга. Всегда на «ты». Тон: тёплый, живой, экспертный, честный. Без канцеляризмов. Эмодзи — скупо (💛, ✨).",
  }
  const tone =
    config.toneOfVoice.preset === "custom"
      ? config.toneOfVoice.custom
      : toneMap[config.toneOfVoice.preset] ?? ""
  if (tone) parts.push(tone)

  // Review prompt from settings
  if (config.reviewPrompt) parts.push(config.reviewPrompt)

  // Signature
  if (config.signatureTemplate.enabled && config.signatureTemplate.template) {
    parts.push(`Подпись: ${config.signatureTemplate.template}`)
  }

  // Stop words
  if (config.stopWords.length > 0) {
    parts.push(`Никогда не используй слова: ${config.stopWords.join(", ")}`)
  }

  // Negative handling
  if (config.negativeHandling.enabled && config.negativeHandling.prompt) {
    parts.push(`При негативном отзыве: ${config.negativeHandling.prompt}`)
    if (config.negativeHandling.ctaTemplate) {
      parts.push(`CTA для негатива: ${config.negativeHandling.ctaTemplate}`)
    }
  }

  return parts.join("\n\n")
}

export const commsService = {
  /** Fetch real reviews from WB/Ozon via backend */
  async fetchReviews(connection: string = "all"): Promise<Review[]> {
    const data = await get<{ reviews: Review[]; total: number }>(
      "/api/comms/reviews",
      { connection }
    )
    return data.reviews
  },

  /** Generate AI response via OpenRouter LLM */
  async generateAiResponse(
    review: Review,
    config: StoreResponseConfig
  ): Promise<AiGenerationResult> {
    const systemPrompt = buildSystemPrompt(config)

    return post<AiGenerationResult>("/api/comms/generate", {
      comment: review.comment,
      rating: review.rating,
      product_name: review.productName,
      source: review.source,
      system_prompt: systemPrompt,
      pros: review.pros || undefined,
      cons: review.cons || undefined,
    })
  },

  /** Publish response (read-only stub) */
  async publishResponse(
    _connectionId: string,
    _reviewId: string,
    _text: string
  ): Promise<{ success: boolean; reason?: string; message?: string }> {
    return post("/api/comms/publish", {})
  },
}
