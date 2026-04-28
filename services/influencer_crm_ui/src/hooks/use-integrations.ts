import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getIntegration,
  type IntegrationListParams,
  type IntegrationOut,
  type IntegrationsPage,
  listIntegrations,
  type Stage,
  updateIntegration,
} from '@/api/integrations';

export function useIntegrations(params: Omit<IntegrationListParams, 'cursor'> = {}) {
  return useQuery({
    queryKey: ['integrations', params],
    queryFn: () => listIntegrations(params),
  });
}

export function useIntegration(id: number | undefined) {
  return useQuery({
    queryKey: ['integration', id],
    queryFn: () => getIntegration(id as number),
    enabled: typeof id === 'number' && id > 0,
  });
}

interface StageVars {
  id: number;
  stage: Stage;
}

interface MutationContext {
  snapshots: Array<[readonly unknown[], IntegrationsPage | undefined]>;
}

export function useUpdateIntegrationStage() {
  const qc = useQueryClient();
  return useMutation<IntegrationOut, Error, StageVars, MutationContext>({
    mutationFn: ({ id, stage }) => updateIntegration(id, { stage }),
    onMutate: async ({ id, stage }) => {
      await qc.cancelQueries({ queryKey: ['integrations'] });
      const snapshots = qc.getQueriesData<IntegrationsPage>({
        queryKey: ['integrations'],
      });
      qc.setQueriesData<IntegrationsPage>({ queryKey: ['integrations'] }, (old) => {
        if (!old) return old;
        return {
          ...old,
          items: old.items.map((it) => (it.id === id ? { ...it, stage } : it)),
        };
      });
      return { snapshots };
    },
    onError: (err, _vars, ctx) => {
      // eslint-disable-next-line no-console
      console.error('updateIntegrationStage failed', err);
      ctx?.snapshots.forEach(([key, data]) => {
        qc.setQueryData(key, data);
      });
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['integrations'] });
    },
  });
}
