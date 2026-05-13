import { supabase } from "@/lib/supabase"

// ─── UI preferences (per-user-less, scope+key) ─────────────────────────────

/**
 * Read a UI preference by (scope, key).
 * Returns null if no row exists. Caller is responsible for the type T cast.
 */
export async function getUiPref<T>(scope: string, key: string): Promise<T | null> {
  const { data, error } = await supabase
    .from("ui_preferences")
    .select("value")
    .eq("scope", scope)
    .eq("key", key)
    .maybeSingle()
  if (error) throw new Error(error.message)
  if (!data) return null
  return (data as { value: T | null }).value
}

/** Upsert a UI preference (scope, key) → value (JSONB). */
export async function setUiPref(scope: string, key: string, value: unknown): Promise<void> {
  const { error } = await supabase
    .from("ui_preferences")
    .upsert(
      { scope, key, value, updated_at: new Date().toISOString() },
      { onConflict: "scope,key" },
    )
  if (error) throw new Error(error.message)
}
