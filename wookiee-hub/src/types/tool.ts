// wookiee-hub/src/types/tool.ts
export type ToolType = 'skill' | 'service' | 'script' | 'cron'
export type ToolStatus = 'active' | 'deprecated' | 'draft' | 'archived'
export type ToolCategory =
  | 'analytics'
  | 'content'
  | 'publishing'
  | 'infra'
  | 'planning'
  | 'team'

export interface OperationsTool {
  slug: string
  name: string           // mapped from display_name
  nameRu: string | null  // mapped from name_ru
  type: ToolType
  category: ToolCategory
  status: ToolStatus
  version: string | null
  description: string | null
  howItWorks: string | null     // mapped from how_it_works
  runCommand: string | null     // mapped from run_command
  dataSources: string[]         // mapped from data_sources
  dependsOn: string[]           // mapped from depends_on
  outputTargets: string[]       // mapped from output_targets
  outputDescription: string | null // mapped from output_description
  healthCheck: string | null    // mapped from health_check
  skillMdPath: string | null    // mapped from skill_md_path
  requiredEnvVars: string[]     // mapped from required_env_vars
  totalRuns: number
  lastRunAt: string | null      // mapped from last_run_at (ISO string)
  lastStatus: string | null     // mapped from last_status
  usageExamples: string | null  // mapped from usage_examples
  docUrl: string | null         // mapped from doc_url
}

export type ToolCategoryFilter = ToolCategory | 'all'
