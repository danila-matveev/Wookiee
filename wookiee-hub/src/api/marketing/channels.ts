import { supabase } from '@/lib/supabase'
import type { MarketingChannel } from '@/types/marketing'

export async function fetchChannels(): Promise<MarketingChannel[]> {
  const { data, error } = await supabase.schema('marketing').from('channels').select('*').eq('is_active', true).order('label')
  if (error) throw error
  return (data ?? []) as MarketingChannel[]
}
