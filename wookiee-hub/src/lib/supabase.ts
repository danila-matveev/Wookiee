import { createClient } from "@supabase/supabase-js"

/**
 * Singleton Supabase client for the Hub SPA.
 *
 * Phase 1: instantiated but not actively used — Agents pages render from mock
 * data (see src/data/agents-mock.ts) because RLS policies on `tools` /
 * `tool_runs` require `auth.role() = 'authenticated'` and the Hub has no auth
 * bootstrap yet.
 *
 * Phase 1.5: pair this client with a Supabase Auth flow (magic-link or
 * pre-shared session) and switch agents-service.ts over to real queries.
 */
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? ""
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? ""

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: false,
    autoRefreshToken: false,
  },
})
