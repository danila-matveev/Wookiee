import { useState, useMemo, useEffect } from "react"
import { Loader2, AlertCircle } from "lucide-react"
import { ReviewsHeader } from "@/components/community/reviews-header"
import { ReviewsStatusTabs } from "@/components/community/reviews-status-tabs"
import { ReviewListItem } from "@/components/community/review-list-item"
import { ReviewDetail } from "@/components/community/review-detail"
import { useCommsStore } from "@/stores/community"
import type { Review, ReviewSource } from "@/types/community"

function reviewHasText(review: Review): boolean {
  return !!(
    (review.comment && review.comment.trim().length > 0) ||
    (review.pros && review.pros.trim().length > 0) ||
    (review.cons && review.cons.trim().length > 0)
  )
}

function sortReviews(reviews: Review[], sortBy: string): Review[] {
  const sorted = [...reviews]
  switch (sortBy) {
    case "newest":
      return sorted.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    case "oldest":
      return sorted.sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())
    case "rating_desc":
      return sorted.sort((a, b) => b.rating - a.rating)
    case "rating_asc":
      return sorted.sort((a, b) => a.rating - b.rating)
    default:
      return sorted
  }
}

/** Apply common filters (everything except tab/sub-tab) */
function applyCommonFilters(review: Review, filters: ReturnType<typeof useCommsStore.getState>["filters"]): boolean {
  if (filters.sources.length > 0 && !filters.sources.includes(review.source)) return false
  if (filters.statuses.length > 0 && !filters.statuses.includes(review.status)) return false
  if (filters.ratings.length > 0 && !filters.ratings.includes(review.rating)) return false
  if (filters.connectionIds.length > 0 && !filters.connectionIds.includes(review.connectionId)) return false

  if (filters.search) {
    const q = filters.search.toLowerCase()
    const searchable = [review.comment, review.pros, review.cons, review.productName, review.authorName]
      .filter(Boolean).join(" ").toLowerCase()
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

  if (filters.hasText === true && !reviewHasText(review)) return false
  if (filters.hasText === false && reviewHasText(review)) return false
  if (filters.hasPhoto === true && !review.hasPhoto) return false
  if (filters.hasPhoto === false && review.hasPhoto) return false

  return true
}

export interface ReviewsPageProps {
  /** Default source filter on mount (e.g. "question" for /community/questions). */
  initialSource?: ReviewSource | "all"
  /** Default top-level tab on mount ("new" | "processed"). */
  initialTab?: "new" | "processed"
  /** Default sub-tab inside "processed" ("pending" | "answered" | "archived"). */
  initialProcessedSubTab?: "pending" | "answered" | "archived"
}

export function ReviewsPage({
  initialSource = "all",
  initialTab,
  initialProcessedSubTab,
}: ReviewsPageProps = {}) {
  const [activeSource, setActiveSource] = useState<ReviewSource | "all">(initialSource)
  const { reviews, selectedReviewId, setSelectedReview, filters, setFilters, loading, error, fetchReviews, sessionCost } = useCommsStore()

  // Apply initial tab / sub-tab once on mount (if provided as props)
  useEffect(() => {
    const partial: Partial<typeof filters> = {}
    if (initialTab) partial.tab = initialTab
    if (initialProcessedSubTab) partial.processedSubTab = initialProcessedSubTab
    if (Object.keys(partial).length > 0) setFilters(partial)
    // Run once on mount; subsequent prop changes are ignored to avoid fighting user interaction.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Fetch real reviews on mount
  useEffect(() => {
    fetchReviews("all")
  }, [fetchReviews])

  const filteredReviews = useMemo(() => {
    const filtered = reviews.filter((review) => {
      // Tab filter: "new" shows status new only; "processed" shows everything else
      if (filters.tab === "new" && review.status !== "new") return false
      if (filters.tab === "processed") {
        if (review.status === "new") return false
        // Sub-tab: pending=ai_generated/approved, answered=published, archived=archived
        const sub = filters.processedSubTab ?? "pending"
        if (sub === "pending" && !["ai_generated", "approved"].includes(review.status)) return false
        if (sub === "answered" && review.status !== "published") return false
        if (sub === "archived" && review.status !== "archived") return false
      }

      if (!applyCommonFilters(review, filters)) return false

      return true
    })

    return sortReviews(filtered, filters.sortBy)
  }, [reviews, filters])

  // Count reviews by tab/sub-tab (respecting source and connection filters but not tab)
  const counts = useMemo(() => {
    const baseFilter = (r: Review) => {
      if (activeSource !== "all" && r.source !== activeSource) return false
      if (filters.connectionIds.length > 0 && !filters.connectionIds.includes(r.connectionId)) return false
      if (filters.search) {
        const q = filters.search.toLowerCase()
        const searchable = [r.comment, r.pros, r.cons, r.productName, r.authorName]
          .filter(Boolean).join(" ").toLowerCase()
        if (!searchable.includes(q)) return false
      }
      return true
    }

    const base = reviews.filter(baseFilter)

    return {
      new: base.filter((r) => r.status === "new").length,
      processed: base.filter((r) => r.status !== "new").length,
      pending: base.filter((r) => ["ai_generated", "approved"].includes(r.status)).length,
      answered: base.filter((r) => r.status === "published").length,
      archived: base.filter((r) => r.status === "archived").length,
    }
  }, [reviews, activeSource, filters.connectionIds, filters.search])

  // Apply source filter
  useEffect(() => {
    if (activeSource === "all") {
      setFilters({ sources: [] })
    } else {
      setFilters({ sources: [activeSource] })
    }
  }, [activeSource, setFilters])

  // Final displayed list with source applied
  const displayedReviews = useMemo(() => {
    return filteredReviews.filter((r) => {
      if (activeSource !== "all" && r.source !== activeSource) return false
      return true
    })
  }, [filteredReviews, activeSource])

  const selectedReview = reviews.find((r) => r.id === selectedReviewId) ?? null

  return (
    <div className="space-y-3">
      <ReviewsHeader
        activeSource={activeSource}
        onSourceChange={setActiveSource}
      />
      {sessionCost > 0 && (
        <div className="flex justify-end -mt-1">
          <span className="text-[11px] text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
            AI сессия: ${sessionCost.toFixed(4)}
          </span>
        </div>
      )}
      <div className="flex gap-3 h-[calc(100vh-220px)]">
        {/* Left panel -- review list */}
        <div className="w-[380px] shrink-0 flex flex-col bg-card border border-border rounded-[10px] overflow-hidden">
          <ReviewsStatusTabs
            activeTab={filters.tab}
            onTabChange={(tab) => setFilters({ tab })}
            newCount={counts.new}
            processedCount={counts.processed}
            processedSubTab={filters.processedSubTab ?? "pending"}
            onProcessedSubTabChange={(sub) => setFilters({ processedSubTab: sub })}
            pendingCount={counts.pending}
            answeredCount={counts.answered}
            archivedCount={counts.archived}
          />
          <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
            {loading ? (
              <div className="flex items-center justify-center h-32 gap-2 text-muted-foreground">
                <Loader2 size={16} className="animate-spin" />
                <span className="text-[13px]">Загрузка отзывов...</span>
              </div>
            ) : error ? (
              <div className="flex flex-col items-center justify-center h-32 gap-2 text-destructive">
                <AlertCircle size={16} />
                <span className="text-[13px] text-center px-4">{error}</span>
                <button
                  onClick={() => fetchReviews("all")}
                  className="text-[12px] text-primary hover:underline"
                >
                  Повторить
                </button>
              </div>
            ) : displayedReviews.length === 0 ? (
              <div className="flex items-center justify-center h-32 text-[13px] text-muted-foreground">
                Нет отзывов
              </div>
            ) : (
              displayedReviews.map((review) => (
                <ReviewListItem
                  key={review.id}
                  review={review}
                  isSelected={selectedReviewId === review.id}
                  onClick={() => setSelectedReview(review.id)}
                />
              ))
            )}
          </div>
        </div>
        {/* Right panel -- review detail */}
        <div className="flex-1 min-w-0">
          <ReviewDetail review={selectedReview} className="h-full" />
        </div>
      </div>
    </div>
  )
}
