// wookiee-hub/src/lib/matrix-api.ts
import { get, post, patch, httpDelete, httpDeleteJson } from "@/lib/api-client"

// ── Types ───────────────────────────────────────────────────────────────────

export interface ModelOsnova {
  id: number
  kod: string
  kategoriya_id: number | null
  kollekciya_id: number | null
  fabrika_id: number | null
  razmery_modeli: string | null
  sku_china: string | null
  upakovka: string | null
  ves_kg: number | null
  dlina_cm: number | null
  shirina_cm: number | null
  vysota_cm: number | null
  kratnost_koroba: number | null
  srok_proizvodstva: string | null
  komplektaciya: string | null
  material: string | null
  sostav_syrya: string | null
  composition: string | null
  tip_kollekcii: string | null
  tnved: string | null
  gruppa_sertifikata: string | null
  nazvanie_etiketka: string | null
  nazvanie_sayt: string | null
  opisanie_sayt: string | null
  tegi: string | null
  notion_link: string | null
  created_at: string | null
  updated_at: string | null
  kategoriya_name: string | null
  kollekciya_name: string | null
  fabrika_name: string | null
  children_count: number | null
}

export interface ModelVariation {
  id: number
  kod: string
  nazvanie: string
  nazvanie_en: string | null
  artikul_modeli: string | null
  model_osnova_id: number | null
  importer_id: number | null
  status_id: number | null
  nabor: boolean
  rossiyskiy_razmer: string | null
  created_at: string | null
  updated_at: string | null
  importer_name: string | null
  status_name: string | null
  artikuly_count: number | null
  tovary_count: number | null
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface LookupItem {
  id: number
  nazvanie: string
}

export interface Artikul {
  id: number
  artikul: string
  model_id: number | null
  cvet_id: number | null
  status_id: number | null
  nomenklatura_wb: number | null
  artikul_ozon: string | null
  created_at: string | null
  updated_at: string | null
  model_name: string | null
  cvet_name: string | null
  status_name: string | null
  tovary_count: number | null
}

export interface Tovar {
  id: number
  barkod: string
  barkod_gs1: string | null
  barkod_gs2: string | null
  barkod_perehod: string | null
  artikul_id: number | null
  razmer_id: number | null
  status_id: number | null
  status_ozon_id: number | null
  ozon_product_id: number | null
  ozon_fbo_sku_id: number | null
  lamoda_seller_sku: string | null
  sku_china_size: string | null
  created_at: string | null
  updated_at: string | null
  artikul_name: string | null
  razmer_name: string | null
  status_name: string | null
  status_ozon_name: string | null
}

export interface Cvet {
  id: number
  color_code: string
  cvet: string | null
  color: string | null
  lastovica: string | null
  status_id: number | null
  created_at: string | null
  updated_at: string | null
  status_name: string | null
  artikuly_count: number | null
}

export interface Fabrika {
  id: number
  nazvanie: string
  strana: string | null
  modeli_count: number | null
}

export interface ImporterEntity {
  id: number
  nazvanie: string
  nazvanie_en: string | null
  inn: string | null
  adres: string | null
  modeli_count: number | null
}

export interface SleykaWB {
  id: number
  nazvanie: string
  importer_id: number | null
  created_at: string | null
  updated_at: string | null
  importer_name: string | null
  tovary_count: number | null
}

export interface SleykaOzon {
  id: number
  nazvanie: string
  importer_id: number | null
  created_at: string | null
  updated_at: string | null
  importer_name: string | null
  tovary_count: number | null
}

export interface Sertifikat {
  id: number
  nazvanie: string
  tip: string | null
  nomer: string | null
  data_vydachi: string | null
  data_okonchaniya: string | null
  organ_sertifikacii: string | null
  file_url: string | null
  gruppa_sertifikata: string | null
  created_at: string | null
  updated_at: string | null
}

export interface SearchResult {
  entity: string
  id: number
  name: string
  match_field: string
  match_text: string
}

export interface SearchResponse {
  results: SearchResult[]
  total: number
  by_entity: Record<string, number>
}

export interface FieldDefinition {
  id: number
  entity_type: string
  field_name: string
  display_name: string
  field_type: string
  config: Record<string, unknown>
  section: string | null
  sort_order: number
  is_system: boolean
  is_visible: boolean
}

export interface ViewConfig {
  columns: string[]
  filters: Array<{ field: string; op: string; value: unknown }>
  sort: Array<{ field: string; dir: string }>
  group_by?: string
}

export interface SavedView {
  id: number
  user_id: number | null
  entity_type: string
  name: string
  config: ViewConfig
  is_default: boolean
  sort_order: number
}

export interface DeleteImpact {
  entity_type: string
  entity_id: number
  entity_name: string
  strategy: string
  children: Record<string, number>
  blocked_by: Record<string, number> | null
  message: string
}

export interface DeleteChallengeResponse {
  requires_confirmation: boolean
  challenge: string
  expected_hash: string
  salt: string
  impact: DeleteImpact
}

export interface DeleteConfirmResponse {
  archived: boolean
  archive_id: number
  expires_at: string | null
}

export interface ArchiveRecord {
  id: number
  original_table: string
  original_id: number
  full_record: Record<string, unknown>
  related_records: Array<{ table: string; id: number; record: Record<string, unknown> }>
  deleted_by: string | null
  deleted_at: string | null
  expires_at: string | null
  restore_available: boolean
}

export interface AuditLogEntry {
  id: number
  timestamp: string | null
  user_email: string | null
  action: string
  entity_type: string | null
  entity_id: number | null
  entity_name: string | null
  changes: Record<string, unknown> | null
}

export interface TableStatsEntry {
  name: string
  count: number
  growth_week: number
  growth_month: number
}

export interface DbStatsResponse {
  tables: TableStatsEntry[]
  total_records: number
}

// ── External Data Types ─────────────────────────────────────────────────────

export interface StockChannel {
  stock_mp: number;
  daily_sales: number;
  turnover_days: number;
  sales_count: number;
  days_in_stock: number;
}

export interface MoySkladStock {
  stock_main: number;
  stock_transit: number;
  total: number;
  snapshot_date: string | null;
  is_stale: boolean;
}

export interface StockResponse {
  entity_type: string;
  entity_id: number;
  entity_name: string;
  period_days: number;
  wb: StockChannel | null;
  ozon: StockChannel | null;
  moysklad: MoySkladStock | null;
  total_stock: number;
  total_turnover_days: number | null;
}

export interface ExpenseItem {
  value: number;
  pct: number;
  delta_value: number | null;
  delta_pct: number | null;
}

export interface DRR {
  total: number;
  internal: number;
  external: number;
}

export interface FinanceChannel {
  revenue_before_spp: number;
  revenue_after_spp: number;
  margin: number;
  margin_pct: number;
  orders_count: number;
  orders_sum: number;
  sales_count: number;
  sales_sum: number;
  avg_check_before_spp: number;
  avg_check_after_spp: number;
  spp_pct: number;
  buyout_pct: number;
  returns_count: number;
  returns_pct: number;
  expenses: Record<string, ExpenseItem>;
  drr: DRR;
}

export interface FinanceDelta {
  revenue_before_spp: number;
  revenue_after_spp: number;
  margin: number;
  margin_pct: number;
  orders_count: number;
  orders_sum: number;
  sales_count: number;
  avg_check_before_spp: number;
  avg_check_after_spp: number;
  spp_pct: number;
  buyout_pct: number;
  returns_count: number;
  returns_pct: number;
  drr_total: number;
  drr_internal: number;
  drr_external: number;
}

export interface FinanceResponse {
  entity_type: string;
  entity_id: number;
  entity_name: string;
  period_start: string;
  period_end: string;
  compare_period_start: string | null;
  compare_period_end: string | null;
  wb: FinanceChannel | null;
  ozon: FinanceChannel | null;
  delta_wb: FinanceDelta | null;
  delta_ozon: FinanceDelta | null;
}

// ── API calls ───────────────────────────────────────────────────────────────

export const matrixApi = {
  // Models osnova
  listModels: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<ModelOsnova>>("/api/matrix/models", params),

  getModel: (id: number) =>
    get<ModelOsnova>(`/api/matrix/models/${id}`),

  createModel: (data: Partial<ModelOsnova>) =>
    post<ModelOsnova>("/api/matrix/models", data),

  updateModel: (id: number, data: Partial<ModelOsnova>) =>
    patch<ModelOsnova>(`/api/matrix/models/${id}`, data),

  // Child models
  listChildren: (osnovaId: number) =>
    get<ModelVariation[]>(`/api/matrix/models/${osnovaId}/children`),

  // Lookups
  getLookup: (table: string) =>
    get<LookupItem[]>(`/api/matrix/lookups/${table}`),

  // Articles
  listArticles: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<Artikul>>("/api/matrix/articles", params),

  getArticle: (id: number) =>
    get<Artikul>(`/api/matrix/articles/${id}`),

  createArticle: (data: Partial<Artikul>) =>
    post<Artikul>("/api/matrix/articles", data),

  updateArticle: (id: number, data: Partial<Artikul>) =>
    patch<Artikul>(`/api/matrix/articles/${id}`, data),

  // Products
  listProducts: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<Tovar>>("/api/matrix/products", params),

  getProduct: (id: number) =>
    get<Tovar>(`/api/matrix/products/${id}`),

  createProduct: (data: Partial<Tovar>) =>
    post<Tovar>("/api/matrix/products", data),

  updateProduct: (id: number, data: Partial<Tovar>) =>
    patch<Tovar>(`/api/matrix/products/${id}`, data),

  // Colors
  listColors: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<Cvet>>("/api/matrix/colors", params),

  updateColor: (id: number, data: Partial<Cvet>) =>
    patch<Cvet>(`/api/matrix/colors/${id}`, data),

  // Factories
  listFactories: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<Fabrika>>("/api/matrix/factories", params),

  updateFactory: (id: number, data: Partial<Fabrika>) =>
    patch<Fabrika>(`/api/matrix/factories/${id}`, data),

  // Importers
  listImporters: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<ImporterEntity>>("/api/matrix/importers", params),

  updateImporter: (id: number, data: Partial<ImporterEntity>) =>
    patch<ImporterEntity>(`/api/matrix/importers/${id}`, data),

  // WB Cards
  listCardsWB: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<SleykaWB>>("/api/matrix/cards-wb", params),

  updateCardWB: (id: number, data: Partial<SleykaWB>) =>
    patch<SleykaWB>(`/api/matrix/cards-wb/${id}`, data),

  // Ozon Cards
  listCardsOzon: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<SleykaOzon>>("/api/matrix/cards-ozon", params),

  updateCardOzon: (id: number, data: Partial<SleykaOzon>) =>
    patch<SleykaOzon>(`/api/matrix/cards-ozon/${id}`, data),

  // Certs
  listCerts: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<Sertifikat>>("/api/matrix/certs", params),

  updateCert: (id: number, data: Partial<Sertifikat>) =>
    patch<Sertifikat>(`/api/matrix/certs/${id}`, data),

  // Search
  search: (q: string, limit?: number) =>
    get<SearchResponse>("/api/matrix/search", { q, limit }),

  // Bulk
  bulkAction: (entityType: string, data: { ids: number[]; action: string; changes?: Record<string, unknown> }) =>
    post<{ updated: number; errors: Array<{ id: number; error: string }> }>(
      `/api/matrix/bulk/${entityType}`, data,
    ),

  // Schema
  listFields: (entityType: string) =>
    get<FieldDefinition[]>(`/api/matrix/schema/${entityType}`),

  createField: (entityType: string, data: Partial<FieldDefinition>) =>
    post<FieldDefinition>(`/api/matrix/schema/${entityType}/fields`, data),

  updateField: (entityType: string, fieldId: number, data: Partial<FieldDefinition>) =>
    patch<FieldDefinition>(`/api/matrix/schema/${entityType}/fields/${fieldId}`, data),

  deleteField: (entityType: string, fieldId: number) =>
    httpDelete(`/api/matrix/schema/${entityType}/fields/${fieldId}`),

  // Views
  listViews: (entityType: string) =>
    get<SavedView[]>("/api/matrix/views", { entity_type: entityType }),

  createView: (data: { entity_type: string; name: string; config: ViewConfig }) =>
    post<SavedView>("/api/matrix/views", data),

  updateView: (viewId: number, data: Partial<SavedView>) =>
    patch<SavedView>(`/api/matrix/views/${viewId}`, data),

  deleteView: (viewId: number) =>
    httpDelete(`/api/matrix/views/${viewId}`),

  // Delete (two-step)
  deleteEntity: (entityType: string, entityId: number) =>
    httpDeleteJson<DeleteChallengeResponse | DeleteConfirmResponse>(
      `/api/matrix/${entityType}/${entityId}`,
    ),

  confirmDelete: (
    entityType: string,
    entityId: number,
    answer: string,
    hash: string,
    salt: string,
  ) =>
    httpDeleteJson<DeleteConfirmResponse>(
      `/api/matrix/${entityType}/${entityId}`,
      {
        "X-Confirm-Challenge": answer,
        "X-Challenge-Hash": hash,
        "X-Challenge-Salt": salt,
      },
    ),

  // Archive
  listArchive: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<ArchiveRecord>>("/api/matrix/archive", params),

  restoreArchive: (archiveId: number) =>
    post<{ restored: boolean; table: string; id: number }>(
      `/api/matrix/archive/${archiveId}/restore`, {},
    ),

  hardDeleteArchive: (archiveId: number) =>
    httpDelete(`/api/matrix/archive/${archiveId}`),

  // Admin
  getAdminHealth: () =>
    get<{ ok: boolean; error?: string }>("/api/matrix/admin/health"),

  listAuditLogs: (params?: Record<string, string | number | undefined>) =>
    get<PaginatedResponse<AuditLogEntry>>("/api/matrix/admin/logs", params),

  getDbStats: () =>
    get<DbStatsResponse>("/api/matrix/admin/stats"),

  // External data
  fetchEntityStock: (entity: string, id: number, period = 30) =>
    get<StockResponse>(`/api/matrix/${entity}/${id}/stock`, { period }),

  fetchEntityFinance: (entity: string, id: number, period = 7, compare = "week") =>
    get<FinanceResponse>(`/api/matrix/${entity}/${id}/finance`, { period, compare }),
}
