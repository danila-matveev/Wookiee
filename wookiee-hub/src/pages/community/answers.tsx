import { ReviewsPage } from "@/pages/community/reviews"

/** Ответы — same UI as /community/reviews but landing on the "answered" sub-tab. */
export function AnswersPage() {
  return (
    <ReviewsPage
      initialTab="processed"
      initialProcessedSubTab="answered"
      pageTitle="Ответы"
      pageBreadcrumbs={[
        { label: "Сообщество", to: "/community/reviews" },
        { label: "Ответы", to: "/community/answers" },
      ]}
    />
  )
}
