import { Suspense, lazy } from "react"
import { createBrowserRouter, Navigate } from "react-router-dom"
import { AppShell } from "@/components/layout/app-shell"
import { ProtectedRoute } from "@/components/auth/protected-route"
import { LoginPage } from "@/pages/auth/login"
import { CatalogLayout } from "@/components/layout/catalog-layout"
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
import { featureFlags } from "@/lib/feature-flags"

// Lazy-load all catalog pages — they live in an isolated `.catalog-scope`
// and load their own data; no need to ship them in the main bundle.
const MatrixPage = lazy(() =>
  import("@/pages/catalog/matrix").then((m) => ({ default: m.MatrixPage })),
)
const ColorsPage = lazy(() =>
  import("@/pages/catalog/colors").then((m) => ({ default: m.ColorsPage })),
)
const ArtikulyPage = lazy(() =>
  import("@/pages/catalog/artikuly").then((m) => ({ default: m.ArtikulyPage })),
)
const TovaryPage = lazy(() =>
  import("@/pages/catalog/tovary").then((m) => ({ default: m.TovaryPage })),
)
const SkleykiPage = lazy(() =>
  import("@/pages/catalog/skleyki").then((m) => ({ default: m.SkleykiPage })),
)
const KategoriiPage = lazy(() =>
  import("@/pages/catalog/references/kategorii").then((m) => ({ default: m.KategoriiPage })),
)
const KollekciiPage = lazy(() =>
  import("@/pages/catalog/references/kollekcii").then((m) => ({ default: m.KollekciiPage })),
)
const TipyKollekciyPage = lazy(() =>
  import("@/pages/catalog/references/tipy-kollekciy").then((m) => ({ default: m.TipyKollekciyPage })),
)
const FabrikiPage = lazy(() =>
  import("@/pages/catalog/references/fabriki").then((m) => ({ default: m.FabrikiPage })),
)
const ImporteryPage = lazy(() =>
  import("@/pages/catalog/references/importery").then((m) => ({ default: m.ImporteryPage })),
)
const RazmeryPage = lazy(() =>
  import("@/pages/catalog/references/razmery").then((m) => ({ default: m.RazmeryPage })),
)
const StatusyPage = lazy(() =>
  import("@/pages/catalog/references/statusy").then((m) => ({ default: m.StatusyPage })),
)
const SemeystvaCvetovPage = lazy(() =>
  import("@/pages/catalog/semeystva-cvetov").then((m) => ({ default: m.SemeystvaCvetovPage })),
)
const UpakovkiPage = lazy(() =>
  import("@/pages/catalog/upakovki").then((m) => ({ default: m.UpakovkiPage })),
)
const KanalyProdazhPage = lazy(() =>
  import("@/pages/catalog/kanaly-prodazh").then((m) => ({ default: m.KanalyProdazhPage })),
)
const SertifikatyPage = lazy(() =>
  import("@/pages/catalog/sertifikaty").then((m) => ({ default: m.SertifikatyPage })),
)
const DemoPage = lazy(() =>
  import("@/pages/catalog/__demo__").then((m) => ({ default: m.DemoPage })),
)

const PromoCodesPage = lazy(() =>
  import("@/pages/marketing/promo-codes").then((m) => ({ default: m.PromoCodesPage })),
)
const SearchQueriesPage = lazy(() =>
  import("@/pages/marketing/search-queries").then((m) => ({ default: m.SearchQueriesPage })),
)

function CatalogFallback() {
  return (
    <div className="px-6 py-8 text-sm text-stone-400">Загрузка…</div>
  )
}

function withFallback(node: React.ReactNode) {
  return <Suspense fallback={<CatalogFallback />}>{node}</Suspense>
}

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
      { path: "/catalog/matrix",                       element: withFallback(<MatrixPage />) },
      { path: "/catalog/colors",                       element: withFallback(<ColorsPage />) },
      { path: "/catalog/artikuly",                     element: withFallback(<ArtikulyPage />) },
      { path: "/catalog/tovary",                       element: withFallback(<TovaryPage />) },
      { path: "/catalog/skleyki",                      element: withFallback(<SkleykiPage />) },
      { path: "/catalog/semeystva-cvetov",             element: withFallback(<SemeystvaCvetovPage />) },
      { path: "/catalog/upakovki",                     element: withFallback(<UpakovkiPage />) },
      { path: "/catalog/kanaly-prodazh",               element: withFallback(<KanalyProdazhPage />) },
      { path: "/catalog/sertifikaty",                  element: withFallback(<SertifikatyPage />) },
      { path: "/catalog/__demo__",                     element: withFallback(<DemoPage />) },
      { path: "/catalog/references",                   element: <Navigate to="/catalog/references/kategorii" replace /> },
      { path: "/catalog/references/kategorii",         element: withFallback(<KategoriiPage />) },
      { path: "/catalog/references/kollekcii",         element: withFallback(<KollekciiPage />) },
      { path: "/catalog/references/tipy-kollekciy",    element: withFallback(<TipyKollekciyPage />) },
      { path: "/catalog/references/fabriki",           element: withFallback(<FabrikiPage />) },
      { path: "/catalog/references/importery",         element: withFallback(<ImporteryPage />) },
      { path: "/catalog/references/razmery",           element: withFallback(<RazmeryPage />) },
      { path: "/catalog/references/statusy",           element: withFallback(<StatusyPage />) },
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
      ...(featureFlags.marketing
        ? [
            { path: "/marketing",                element: <Navigate to="/marketing/promo-codes" replace /> },
            { path: "/marketing/promo-codes",    element: withFallback(<PromoCodesPage />) },
            { path: "/marketing/search-queries", element: withFallback(<SearchQueriesPage />) },
          ]
        : []),
    ],
  },
])
