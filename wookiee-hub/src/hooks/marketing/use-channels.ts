import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchChannels } from '@/api/marketing/channels'
export function useChannels() {
  return useQuery({ queryKey: ['marketing', 'channels'], queryFn: fetchChannels, staleTime: 10 * 60_000 })
}

export function useChannelLabelLookup() {
  const { data: channels = [] } = useChannels()
  return useMemo(() => {
    const map = new Map<string, string>()
    for (const ch of channels) {
      map.set(ch.slug, ch.label)
    }
    return (slug: string | null | undefined): string => {
      if (!slug) return '—'
      return map.get(slug) ?? slug
    }
  }, [channels])
}
