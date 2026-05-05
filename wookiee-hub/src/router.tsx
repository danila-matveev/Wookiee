import { createBrowserRouter, Navigate } from "react-router-dom"
import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/auth/protected-route"
import { LoginPage } from "@/pages/auth/login"
import { ToolsPage } from "@/pages/operations/tools"
import { ActivityPage } from "@/pages/operations/activity"
import { ReviewsPage } from "@/pages/community/reviews"
import { QuestionsPage } from "@/pages/community/questions"
import { AnswersPage } from "@/pages/community/answers"
import { AnalyticsPage } from "@/pages/community/analytics"

export const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    element: (
      <ProtectedRoute>
        <AppShell />
      </ProtectedRoute>
    ),
    children: [
      { path: "/",                     element: <Navigate to="/operations/tools" replace /> },
      { path: "/operations",           element: <Navigate to="/operations/tools" replace /> },
      { path: "/operations/tools",     element: <ToolsPage /> },
      { path: "/operations/activity",  element: <ActivityPage /> },
      { path: "/community",            element: <Navigate to="/community/reviews" replace /> },
      { path: "/community/reviews",    element: <ReviewsPage /> },
      { path: "/community/questions",  element: <QuestionsPage /> },
      { path: "/community/answers",    element: <AnswersPage /> },
      { path: "/community/analytics",  element: <AnalyticsPage /> },
    ],
  },
])
