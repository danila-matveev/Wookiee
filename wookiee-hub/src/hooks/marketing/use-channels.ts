import { useQuery } from '@tanstack/react-query'
import { fetchChannels } from '@/api/marketing/channels'
export function useChannels() {
  return useQuery({ queryKey: ['marketing', 'channels'], queryFn: fetchChannels, staleTime: 10 * 60_000 })
}
