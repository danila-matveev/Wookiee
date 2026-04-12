export type ReviewResponseMode = "semi_auto" | "auto"

export interface RatingConfig {
  mode: ReviewResponseMode
  enabled: boolean
}

export type TonePreset = "formal" | "friendly" | "neutral" | "playful" | "wookiee" | "custom"

export interface TrainingFile {
  id: string
  name: string
  size: number
  uploadedAt: string
  status: "processing" | "ready" | "error"
}

export interface ProductModel {
  id: string
  name: string
  nomenclatures: string[]
  description: string
  recommendWith: string[]
  positioning?: string
  notFor?: string[]
}

export type RecommendationSource = "matrix" | "popular" | "manual"

export interface NegativeHandling {
  enabled: boolean
  prompt: string
  ctaTemplate: string
}

export interface StoreResponseConfig {
  connectionId: string

  /** Tab: Отзывы — response mode per rating */
  reviewModes: Record<1 | 2 | 3 | 4 | 5, RatingConfig>

  /** Tab: Рекомендации — product recommendations in responses */
  recommendProducts: {
    enabled: boolean
    maxCount: number
    source: RecommendationSource
    excludeArticles: string[]
  }

  /** Tab: Подпись — signature appended to responses */
  signatureTemplate: {
    enabled: boolean
    template: string
  }

  /** Tab: Вопросы — question auto-response mode */
  questionMode: "disabled" | "semi_auto" | "auto"

  /** Tab: Расширенные — advanced response settings */
  salutation: string
  toneOfVoice: { preset: TonePreset; custom: string }
  responseLength: "short" | "medium" | "long"
  stopWords: string[]
  negativeHandling: NegativeHandling

  /** Tab: Обучение AI — store/brand context for AI */
  storeDescription: string
  brandDescriptions: { name: string; description: string }[]
  productModels: ProductModel[]
  trainingFiles: TrainingFile[]

  /** Tab: Отзывы — AI system prompt for reviews */
  reviewPrompt: string

  /** Tab: Вопросы — AI system prompt for questions */
  questionPrompt: string

  /** Tab: Чаты — chat auto-response mode + AI prompt */
  chatMode: "disabled" | "semi_auto" | "auto"
  chatPrompt: string
}
