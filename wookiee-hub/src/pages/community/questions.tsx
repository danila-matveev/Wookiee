import { ReviewsPage } from "@/pages/community/reviews"

/** Вопросы — same UI as /community/reviews but pre-filtered to source="question". */
export function QuestionsPage() {
  return (
    <ReviewsPage
      kind="questions"
      initialSource="question"
      pageTitle="Вопросы"
    />
  )
}
