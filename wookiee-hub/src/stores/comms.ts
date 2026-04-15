import { create } from "zustand"
import type { Review, ReviewFilters, ReviewStatus } from "@/types/comms"
import { commsService } from "@/lib/comms-service"

interface CommsState {
  reviews: Review[]
  selectedReviewId: string | null
  filters: ReviewFilters
  loading: boolean
  error: string | null
  sessionCost: number
  setSelectedReview: (id: string | null) => void
  setFilters: (filters: Partial<ReviewFilters>) => void
  updateReviewStatus: (id: string, status: ReviewStatus) => void
  setAiDraft: (id: string, draft: string) => void
  publishResponse: (id: string, response: string) => void
  fetchReviews: (connection?: string) => Promise<void>
  addCost: (amount: number) => void
  getFilteredReviews: () => Review[]
}

export const useCommsStore = create<CommsState>((set, get) => ({
  reviews: [],
  selectedReviewId: null,
  filters: {
    sources: [],
    statuses: [],
    ratings: [],
    connectionIds: [],
    search: "",
    tab: "new",
    processedSubTab: "pending",
    sortBy: "newest",
  },
  loading: false,
  error: null,
  sessionCost: 0,
  setSelectedReview: (id) => set({ selectedReviewId: id }),
  setFilters: (partial) =>
    set((s) => ({ filters: { ...s.filters, ...partial } })),
  updateReviewStatus: (id, status) =>
    set((s) => ({
      reviews: s.reviews.map((r) =>
        r.id === id ? { ...r, status } : r
      ),
    })),
  setAiDraft: (id, draft) =>
    set((s) => ({
      reviews: s.reviews.map((r) =>
        r.id === id ? { ...r, aiDraft: draft, status: "ai_generated" as const } : r
      ),
    })),
  publishResponse: (id, response) =>
    set((s) => ({
      reviews: s.reviews.map((r) =>
        r.id === id
          ? {
              ...r,
              publishedResponse: response,
              status: "published" as const,
              respondedAt: new Date().toISOString(),
            }
          : r
      ),
    })),
  fetchReviews: async (connection = "all") => {
    set({ loading: true, error: null })
    try {
      const reviews = await commsService.fetchReviews(connection)
      set({ reviews, loading: false })
    } catch (e) {
      set({
        error: e instanceof Error ? e.message : "Ошибка загрузки отзывов",
        loading: false,
      })
    }
  },
  addCost: (amount) =>
    set((s) => ({ sessionCost: s.sessionCost + amount })),
  getFilteredReviews: () => {
    const { reviews, filters } = get()
    const filtered = reviews.filter((review) => {
      if (filters.tab === "new" && !["new", "ai_generated", "approved"].includes(review.status)) return false
      if (filters.tab === "processed" && review.status === "new") return false

      if (filters.tab === "processed" && filters.processedSubTab) {
        if (filters.processedSubTab === "pending" && !["ai_generated", "approved"].includes(review.status)) return false
        if (filters.processedSubTab === "answered" && review.status !== "published") return false
        if (filters.processedSubTab === "archived" && review.status !== "archived") return false
      }

      if (filters.sources.length > 0 && !filters.sources.includes(review.source)) return false
      if (filters.statuses.length > 0 && !filters.statuses.includes(review.status)) return false
      if (filters.ratings.length > 0 && !filters.ratings.includes(review.rating)) return false
      if (filters.connectionIds.length > 0 && !filters.connectionIds.includes(review.connectionId)) return false

      if (filters.search) {
        const q = filters.search.toLowerCase()
        const searchable = [
          review.comment,
          review.pros,
          review.cons,
          review.productName,
          review.authorName,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
        if (!searchable.includes(q)) return false
      }

      if (filters.dateRange?.from && filters.dateRange?.to) {
        const created = new Date(review.createdAt)
        const from = new Date(filters.dateRange.from)
        from.setHours(0, 0, 0, 0)
        const to = new Date(filters.dateRange.to)
        to.setHours(23, 59, 59, 999)
        if (created < from || created > to) return false
      }

      if (filters.hasPhoto === true && !review.hasPhoto) return false
      if (filters.hasPhoto === false && review.hasPhoto) return false

      return true
    })

    const sorted = [...filtered]
    switch (filters.sortBy) {
      case "newest":
        sorted.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
        break
      case "oldest":
        sorted.sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())
        break
      case "rating_desc":
        sorted.sort((a, b) => b.rating - a.rating)
        break
      case "rating_asc":
        sorted.sort((a, b) => a.rating - b.rating)
        break
    }
    return sorted
  },
}))
