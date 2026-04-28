import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppShell } from '@/layout/AppShell';
import { UiCatalog } from '@/routes/__dev/UiCatalog';
import { BloggersPage } from '@/routes/bloggers/BloggersPage';
import { BriefsPage } from '@/routes/briefs/BriefsPage';
import { CalendarPage } from '@/routes/calendar/CalendarPage';
import { IntegrationsKanbanPage } from '@/routes/integrations/IntegrationsKanbanPage';
import { NotFound } from '@/routes/NotFound';
import { ProductsPage } from '@/routes/products/ProductsPage';
import { SearchPage } from '@/routes/search/SearchPage';
import { SlicesPage } from '@/routes/slices/SlicesPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/bloggers" replace /> },
      { path: 'bloggers', element: <BloggersPage /> },
      { path: 'integrations', element: <IntegrationsKanbanPage /> },
      { path: 'calendar', element: <CalendarPage /> },
      { path: 'briefs', element: <BriefsPage /> },
      { path: 'slices', element: <SlicesPage /> },
      { path: 'products', element: <ProductsPage /> },
      { path: 'search', element: <SearchPage /> },
      { path: '*', element: <NotFound /> },
    ],
  },
  { path: '/dev/ui', element: <UiCatalog /> },
]);

export default router;
