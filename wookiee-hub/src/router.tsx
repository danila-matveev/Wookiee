import { createBrowserRouter, Navigate } from "react-router-dom"
import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/auth/protected-route"
import { LoginPage } from "@/pages/auth/login"
import { ToolsPage } from "@/pages/operations/tools"
import { ActivityPage } from "@/pages/operations/activity"
import { HealthPage } from "@/pages/operations/health"
import { ReviewsPage } from "@/pages/community/reviews"
import { QuestionsPage } from "@/pages/community/questions"
import { AnswersPage } from "@/pages/community/answers"
import { AnalyticsPage } from "@/pages/community/analytics"
import { BloggersPage } from "@/pages/influence/bloggers/BloggersPage"
import { IntegrationsKanbanPage } from "@/pages/influence/integrations/IntegrationsKanbanPage"
import { CalendarPage } from "@/pages/influence/calendar/CalendarPage"

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
      { path: "/operations/health",    element: <HealthPage /> },
      { path: "/community",            element: <Navigate to="/community/reviews" replace /> },
      { path: "/community/reviews",    element: <ReviewsPage /> },
      { path: "/community/questions",  element: <QuestionsPage /> },
      { path: "/community/answers",    element: <AnswersPage /> },
      { path: "/community/analytics",  element: <AnalyticsPage /> },
      { path: "/influence",              element: <Navigate to="/influence/bloggers" replace /> },
      { path: "/influence/bloggers",     element: <BloggersPage /> },
      { path: "/influence/integrations", element: <IntegrationsKanbanPage /> },
      { path: "/influence/calendar",     element: <CalendarPage /> },
    ],
  },
])
