import { createBrowserRouter, Navigate } from "react-router-dom"
import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/auth/protected-route"
import { LoginPage } from "@/pages/auth/login"
import { CatalogLayout } from "@/components/layout/catalog-layout"
import { MatrixPage } from "@/pages/catalog/matrix"
import { ColorsPage } from "@/pages/catalog/colors"
import { SkleykiPage } from "@/pages/catalog/skleyki"
import { KategoriiPage } from "@/pages/catalog/references/kategorii"
import { KollekciiPage } from "@/pages/catalog/references/kollekcii"
import { FabrikiPage } from "@/pages/catalog/references/fabriki"
import { ImporteryPage } from "@/pages/catalog/references/importery"
import { RazmeryPage } from "@/pages/catalog/references/razmery"
import { StatusyPage } from "@/pages/catalog/references/statusy"
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
import { RnpPage } from "@/pages/analytics/rnp"

export const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    element: (
      <ProtectedRoute>
        <CatalogLayout />
      </ProtectedRoute>
    ),
    children: [
      { path: "/catalog",                              element: <Navigate to="/catalog/matrix" replace /> },
      { path: "/catalog/matrix",                      element: <MatrixPage /> },
      { path: "/catalog/colors",                      element: <ColorsPage /> },
      { path: "/catalog/skleyki",                     element: <SkleykiPage /> },
      { path: "/catalog/references",                  element: <Navigate to="/catalog/references/kategorii" replace /> },
      { path: "/catalog/references/kategorii",        element: <KategoriiPage /> },
      { path: "/catalog/references/kollekcii",        element: <KollekciiPage /> },
      { path: "/catalog/references/fabriki",          element: <FabrikiPage /> },
      { path: "/catalog/references/importery",        element: <ImporteryPage /> },
      { path: "/catalog/references/razmery",          element: <RazmeryPage /> },
      { path: "/catalog/references/statusy",          element: <StatusyPage /> },
    ],
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
      { path: "/analytics",              element: <Navigate to="/analytics/rnp" replace /> },
      { path: "/analytics/rnp",          element: <RnpPage /> },
    ],
  },
])
