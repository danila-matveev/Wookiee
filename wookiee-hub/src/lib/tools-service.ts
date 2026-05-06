import { supabase } from '@/lib/supabase'
import type { OperationsTool } from '@/types/tool'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapRow(row: any): OperationsTool {
  return {
    slug: row.slug,
    name: row.display_name,
    nameRu: row.name_ru ?? null,
    type: row.type,
    category: row.category,
    status: row.status,
    version: row.version ?? null,
    description: row.description ?? null,
    howItWorks: row.how_it_works ?? null,
    runCommand: row.run_command ?? null,
    dataSources: row.data_sources ?? [],
    dependsOn: row.depends_on ?? [],
    outputTargets: row.output_targets ?? [],
    outputDescription: row.output_description ?? null,
    healthCheck: row.health_check ?? null,
    skillMdPath: row.skill_md_path ?? null,
    requiredEnvVars: row.required_env_vars ?? [],
    totalRuns: row.total_runs ?? 0,
    lastRunAt: row.last_run_at ?? null,
    lastStatus: row.last_status ?? null,
    usageExamples: row.usage_examples ?? null,
    docUrl: row.doc_url ?? null,
  }
}

export async function fetchTools(): Promise<OperationsTool[]> {
  const { data, error } = await supabase
    .from('tools')
    .select(
      'slug, display_name, name_ru, type, category, status, version, ' +
      'description, how_it_works, run_command, data_sources, depends_on, ' +
      'output_targets, output_description, health_check, skill_md_path, ' +
      'required_env_vars, total_runs, last_run_at, last_status, ' +
      'usage_examples, doc_url'
    )
    .neq('status', 'archived')
    .eq('show_in_hub', true)

  if (error || !data) {
    console.error('[tools-service] fetchTools error:', error?.message)
    return []
  }

  return data.map(mapRow)
}
