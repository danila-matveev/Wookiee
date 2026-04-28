import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  addBriefVersion,
  type BriefCreateInput,
  type BriefListParams,
  type BriefOut,
  type BriefStatus,
  type BriefUpdate,
  type BriefVersionOut,
  createBrief,
  getBrief,
  listBriefs,
  updateBrief,
  updateBriefStatus,
} from '@/api/briefs';

export function useBriefs(params: Omit<BriefListParams, 'cursor'> = {}) {
  return useQuery({
    queryKey: ['briefs', params],
    queryFn: () => listBriefs(params),
  });
}

export function useBrief(id: number | undefined) {
  return useQuery({
    queryKey: ['brief', id],
    queryFn: () => getBrief(id as number),
    enabled: typeof id === 'number' && id > 0,
  });
}

export function useCreateBrief() {
  const qc = useQueryClient();
  return useMutation<BriefOut, Error, BriefCreateInput>({
    mutationFn: (body) => createBrief(body),
    onSuccess: (saved) => {
      qc.invalidateQueries({ queryKey: ['briefs'] });
      qc.setQueryData(['brief', saved.id], saved);
    },
  });
}

interface AddVersionVars {
  id: number;
  content_md: string;
}

export function useAddBriefVersion() {
  const qc = useQueryClient();
  return useMutation<BriefVersionOut, Error, AddVersionVars>({
    mutationFn: ({ id, content_md }) => addBriefVersion(id, content_md),
    onSuccess: (_v, vars) => {
      qc.invalidateQueries({ queryKey: ['briefs'] });
      qc.invalidateQueries({ queryKey: ['brief', vars.id] });
    },
  });
}

export interface UpsertBriefArgs {
  id?: number;
  body: BriefCreateInput | BriefUpdate;
}

interface StatusVars {
  id: number;
  status: BriefStatus;
}

export function useUpdateBriefStatus() {
  const qc = useQueryClient();
  return useMutation<BriefOut, Error, StatusVars>({
    mutationFn: ({ id, status }) => updateBriefStatus(id, status),
    onSuccess: (saved) => {
      qc.invalidateQueries({ queryKey: ['briefs'] });
      qc.setQueryData(['brief', saved.id], (old: unknown) =>
        old && typeof old === 'object' ? { ...(old as Record<string, unknown>), ...saved } : saved,
      );
    },
  });
}

// Convenience helper for the editor drawer: also patches metadata via PATCH if needed.
export function useUpdateBrief() {
  const qc = useQueryClient();
  return useMutation<BriefOut, Error, { id: number; body: BriefUpdate }>({
    mutationFn: ({ id, body }) => updateBrief(id, body),
    onSuccess: (saved) => {
      qc.invalidateQueries({ queryKey: ['briefs'] });
      qc.setQueryData(['brief', saved.id], (old: unknown) =>
        old && typeof old === 'object' ? { ...(old as Record<string, unknown>), ...saved } : saved,
      );
    },
  });
}
