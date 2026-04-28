import { api } from '@/lib/api';

// 4 statuses for the Kanban — sourced from the project plan T15 step 1.
// Real BFF schema (services/influencer_crm/schemas/brief.py) currently exposes
// only `id/title/current_version_id/created_at` and routes for POST + versions.
// Status, list, detail, PATCH endpoints are anticipated BFF gaps — UI is
// designed against the eventual shape and runs end-to-end via MSW today.
export const BRIEF_STATUSES = ['draft', 'on_review', 'signed', 'completed'] as const;

export type BriefStatus = (typeof BRIEF_STATUSES)[number];

export const BRIEF_STATUS_LABELS: Record<BriefStatus, string> = {
  draft: 'Черновик',
  on_review: 'На ревью',
  signed: 'Подписан',
  completed: 'Завершён',
};

export interface BriefOut {
  id: number;
  title: string;
  status: BriefStatus;
  // version number of the current draft (DB column `current_version` is integer).
  current_version: number;
  // FK row-id of the version that backs `current_version`.
  current_version_id: number | null;
  // Optional denormalised metadata the BFF may surface for card display.
  blogger_id?: number | null;
  blogger_handle?: string | null;
  integration_id?: number | null;
  scheduled_at?: string | null;
  budget?: string | null;
  created_at: string | null;
  updated_at?: string | null;
}

export interface BriefVersionOut {
  id: number;
  brief_id: number;
  version: number;
  content_md: string;
  created_at: string | null;
}

export interface BriefDetailOut extends BriefOut {
  content_md: string;
  versions: BriefVersionOut[];
}

export interface BriefsPage {
  items: BriefOut[];
  next_cursor: string | null;
}

export interface BriefListParams {
  status?: BriefStatus;
  blogger_id?: number;
  cursor?: string;
  limit?: number;
}

export function listBriefs(params: BriefListParams = {}): Promise<BriefsPage> {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) search.set(k, String(v));
  }
  const q = search.toString();
  return api.get<BriefsPage>(`/briefs${q ? `?${q}` : ''}`);
}

export function getBrief(id: number): Promise<BriefDetailOut> {
  return api.get<BriefDetailOut>(`/briefs/${id}`);
}

export interface BriefCreateInput {
  title: string;
  content_md: string;
  // Optional metadata; BFF accepts these only if extended in a follow-up.
  blogger_id?: number | null;
  integration_id?: number | null;
}

export function createBrief(body: BriefCreateInput): Promise<BriefOut> {
  return api.post<BriefOut>('/briefs', body);
}

export function addBriefVersion(id: number, content_md: string): Promise<BriefVersionOut> {
  return api.post<BriefVersionOut>(`/briefs/${id}/versions`, { content_md });
}

export interface BriefUpdate {
  title?: string;
  status?: BriefStatus;
  blogger_id?: number | null;
  integration_id?: number | null;
}

export function updateBrief(id: number, body: BriefUpdate): Promise<BriefOut> {
  return api.patch<BriefOut>(`/briefs/${id}`, body);
}

export function updateBriefStatus(id: number, status: BriefStatus): Promise<BriefOut> {
  return updateBrief(id, { status });
}
