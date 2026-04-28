import { useQuery } from '@tanstack/react-query';
import { getOpsHealth } from '@/api/ops';

// Auto-refresh every 30s — the BFF /ops/health is cheap (5 small queries) and
// the dashboard's whole point is "is everything green right now?".
export function useOpsHealth() {
  return useQuery({
    queryKey: ['ops', 'health'],
    queryFn: getOpsHealth,
    refetchInterval: 30_000,
  });
}
