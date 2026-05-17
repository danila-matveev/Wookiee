import { ReviewsPage } from "@/pages/community/reviews"

/** Ответы — same UI as /community/reviews but landing on the "answered" sub-tab. */
export function AnswersPage() {
  return (
    <ReviewsPage
      kind="answers"
      initialTab="processed"
      initialProcessedSubTab="answered"
      pageTitle="Ответы"
    />
  )
}
