import type { ServiceType } from "@/types/integrations"

export type ReviewSource = "review" | "question" | "chat"

export type ReviewStatus = "new" | "ai_generated" | "approved" | "published" | "archived"

export interface Review {
  id: string
  connectionId: string
  serviceType: ServiceType
  source: ReviewSource
  productName: string
  productArticle: string
  productImg: string
  authorName: string
  rating: number
  status: ReviewStatus
  purchaseStatus: string
  pros?: string
  cons?: string
  comment: string
  createdAt: string
  aiDraft?: string
  publishedResponse?: string
  respondedAt?: string
  hasPhoto?: boolean
}

export interface ReviewFilters {
  sources: ReviewSource[]
  statuses: ReviewStatus[]
  ratings: number[]
  connectionIds: string[]
  search: string
  tab: "new" | "processed"
  processedSubTab?: "pending" | "answered" | "archived"
  dateRange?: { from: Date; to: Date }
  hasText?: boolean
  hasPhoto?: boolean
  sortBy: "newest" | "oldest" | "rating_desc" | "rating_asc"
}

export interface CommsDashboardMetrics {
  totalReceived: number
  awaitingPublish: number
  unanswered: number
  unansweredPercent: number
  avgRating: number
  positivePercent: number
}

export interface ReviewChartPoint {
  date: string
  received: number
  responded: number
}

export interface ResponseTimePoint {
  date: string
  avgMinutesReviews: number
  avgMinutesQuestions: number
}

export interface TopProduct {
  name: string
  article: string
  wbArticle?: string
  internalArticle?: string
  reviewCount: number
  avgRating: number
}

export interface StoreBreakdown {
  connectionId: string
  connectionName: string
  serviceType: ServiceType
  reviewCount: number
  avgRating: number
}

export interface AiGenerationResult {
  text: string
  usage: { input_tokens: number; output_tokens: number; cost_usd: number }
  model: string
}
