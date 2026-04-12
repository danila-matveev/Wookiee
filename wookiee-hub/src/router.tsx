import { createBrowserRouter, Navigate } from "react-router-dom"
import { AppShell } from "@/components/layout/app-shell"
import { MatrixAdminLayout } from "@/pages/system/matrix-admin-layout"
import { SchemaExplorerPage } from "@/pages/system/schema-explorer-page"
import { ApiExplorerPage } from "@/pages/system/api-explorer-page"
import { AuditLogPage } from "@/pages/system/audit-log-page"
import { ArchiveManagerPage } from "@/pages/system/archive-manager-page"
import { DbStatsPage } from "@/pages/system/db-stats-page"
import { ProductMatrixLayout } from "@/pages/product-matrix"
import { EntityDetailPage } from "@/pages/product-matrix/entity-detail-page"
import {
  WarehousePage,
  FinancePage,
  InfluencerPage,
  UgcPage,
  SmmPage,
  PricingPage,
  EmployeesPage,
  OrgStructurePage,
  KnowledgePage,
  ContractorsPage,
  SettingsPage,
  AgentsPage,
  IntegrationsPage,
} from "@/pages/stubs"
import { AnalyticsPromoPage } from "@/pages/analytics-promo"
import { CommsAnalyticsPage } from "@/pages/comms-analytics"
import { CommsBroadcastsPage } from "@/pages/comms-broadcasts"
import { CommsDashboardPage } from "@/pages/comms-dashboard"
import { CommsReviewsPage } from "@/pages/comms-reviews"
import { CommsStoreSettingsPage } from "@/pages/comms-store-settings"
import { AnalyticsOverviewPage } from "@/pages/analytics-overview"
import { AnalyticsAbcPage } from "@/pages/analytics-abc"
import { AnalyticsUnitPage } from "@/pages/analytics-unit"

import { CatalogPage } from "@/pages/catalog"
import { DashboardPage } from "@/pages/dashboard"
import { DevelopmentPage } from "@/pages/development"
import { ProductionPage } from "@/pages/production"
import { ShipmentsPage } from "@/pages/shipments"
import { SupplyPage } from "@/pages/supply"
import { IdeasPage } from "@/pages/ideas"

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <Navigate to="/dashboard" replace /> },
      { path: "/dashboard", element: <DashboardPage /> },
      // Product
      { path: "/product/catalog", element: <CatalogPage /> },
      { path: "/product/matrix", element: <ProductMatrixLayout /> },
      { path: "/product/matrix/:entity/:id", element: <EntityDetailPage /> },
      { path: "/product/development", element: <DevelopmentPage /> },
      { path: "/product/production", element: <ProductionPage /> },
      // Operations
      { path: "/operations/warehouse", element: <WarehousePage /> },
      { path: "/operations/shipments", element: <ShipmentsPage /> },
      { path: "/operations/supply", element: <SupplyPage /> },
      { path: "/operations/finance", element: <FinancePage /> },
      // Analytics
      { path: "/analytics/overview", element: <AnalyticsOverviewPage /> },
      { path: "/analytics/abc", element: <AnalyticsAbcPage /> },
      { path: "/analytics/promo", element: <AnalyticsPromoPage /> },
      { path: "/analytics/unit", element: <AnalyticsUnitPage /> },
      // Marketing
      { path: "/marketing/influencer", element: <InfluencerPage /> },
      { path: "/marketing/ugc", element: <UgcPage /> },
      { path: "/marketing/smm", element: <SmmPage /> },
      { path: "/marketing/pricing", element: <PricingPage /> },
      // Comms
      { path: "/comms", element: <Navigate to="/comms/dashboard" replace /> },
      { path: "/comms/dashboard", element: <CommsDashboardPage /> },
      { path: "/comms/reviews", element: <CommsReviewsPage /> },
      { path: "/comms/store-settings", element: <CommsStoreSettingsPage /> },
      { path: "/comms/analytics", element: <CommsAnalyticsPage /> },
      { path: "/comms/broadcasts", element: <CommsBroadcastsPage /> },
      // Team
      { path: "/team/employees", element: <EmployeesPage /> },
      { path: "/team/org", element: <OrgStructurePage /> },
      { path: "/team/knowledge", element: <KnowledgePage /> },
      { path: "/team/ideas", element: <IdeasPage /> },
      { path: "/team/contractors", element: <ContractorsPage /> },
      // System
      { path: "/system/settings", element: <SettingsPage /> },
      { path: "/system/agents", element: <AgentsPage /> },
      { path: "/system/integrations", element: <IntegrationsPage /> },
      // Matrix Admin
      {
        path: "/system/matrix-admin",
        element: <MatrixAdminLayout />,
        children: [
          { index: true, element: <Navigate to="/system/matrix-admin/schema" replace /> },
          { path: "schema", element: <SchemaExplorerPage /> },
          { path: "api", element: <ApiExplorerPage /> },
          { path: "logs", element: <AuditLogPage /> },
          { path: "archive", element: <ArchiveManagerPage /> },
          { path: "stats", element: <DbStatsPage /> },
        ],
      },
    ],
  },
])
