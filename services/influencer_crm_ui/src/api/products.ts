import type { Stage } from '@/api/integrations';
import { api } from '@/lib/api';

// Mirrors services/influencer_crm/schemas/product.py (ProductSliceOut).
// All money fields are decimal strings to preserve precision through JSON.
export interface ProductOut {
  model_osnova_id: number;
  model_name: string;
  integrations_count: number;
  integrations_done: number;
  last_publish_date: string | null; // ISO date
  total_spent: string;
  total_revenue_fact: string;
}

// Mirrors ProductDetailIntegrationOut.
export interface ProductDetailIntegrationOut {
  integration_id: number;
  blogger_handle: string;
  publish_date: string;
  stage: Stage;
  total_cost: string;
  fact_views: number | null;
  fact_orders: number | null;
  fact_revenue: string | null;
}

// ProductDetailOut = ProductOut + integrations[]. The current BFF does NOT
// return substitute_articles or model thumbnails — see T17 deferral note in
// ProductSliceCard. When the BFF is extended these fields will land here.
export interface ProductDetailOut extends ProductOut {
  integrations: ProductDetailIntegrationOut[];
}

export interface ProductsPage {
  items: ProductOut[];
  next_cursor: string | null;
}

export interface ProductListParams {
  cursor?: string;
  limit?: number;
}

export function listProducts(params: ProductListParams = {}): Promise<ProductsPage> {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) search.set(k, String(v));
  }
  const q = search.toString();
  return api.get<ProductsPage>(`/products${q ? `?${q}` : ''}`);
}

export function getProduct(modelOsnovaId: number): Promise<ProductDetailOut> {
  return api.get<ProductDetailOut>(`/products/${modelOsnovaId}`);
}
