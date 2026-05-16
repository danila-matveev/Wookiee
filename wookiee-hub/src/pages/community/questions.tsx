import { ReviewsPage } from "@/pages/community/reviews"

/** Вопросы — same UI as /community/reviews but pre-filtered to source="question". */
export function QuestionsPage() {
  return (
    <ReviewsPage
      initialSource="question"
      pageTitle="Вопросы"
      pageBreadcrumbs={[
        { label: "Сообщество", to: "/community/reviews" },
        { label: "Вопросы", to: "/community/questions" },
      ]}
    />
  )
}
