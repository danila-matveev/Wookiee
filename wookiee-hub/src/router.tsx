import { createBrowserRouter, Navigate } from "react-router-dom"
import { AppShell } from "@/components/layout/app-shell"
import { ReviewsPage } from "@/pages/community/reviews"
import { QuestionsPage } from "@/pages/community/questions"
import { AnswersPage } from "@/pages/community/answers"
import { AnalyticsPage } from "@/pages/community/analytics"
import { SkillsPage } from "@/pages/agents/skills"
import { RunsPage } from "@/pages/agents/runs"

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <Navigate to="/community/reviews" replace /> },
      { path: "/community", element: <Navigate to="/community/reviews" replace /> },
      { path: "/community/reviews", element: <ReviewsPage /> },
      { path: "/community/questions", element: <QuestionsPage /> },
      { path: "/community/answers", element: <AnswersPage /> },
      { path: "/community/analytics", element: <AnalyticsPage /> },
      { path: "/agents", element: <Navigate to="/agents/skills" replace /> },
      { path: "/agents/skills", element: <SkillsPage /> },
      { path: "/agents/runs", element: <RunsPage /> },
    ],
  },
])
