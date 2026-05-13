import { useEffect, useRef, useState } from "react"
import { getUiPref, setUiPref } from "@/lib/ui-preferences"

/**
 * Persists a "group by" UI preference under (scope, "groupBy") in ui_preferences.
 * On mount: reads the saved value (if any) and updates state.
 * On setValue: updates state immediately and fires-and-forgets the upsert.
 */
export function useGroupByPref<T extends string>(scope: string, defaultValue: T) {
  const [value, setValueState] = useState<T>(defaultValue)
  const loadedRef = useRef(false)

  useEffect(() => {
    if (loadedRef.current) return
    loadedRef.current = true
    getUiPref<T>(scope, "groupBy")
      .then((v) => { if (v) setValueState(v) })
      .catch(() => { /* ignore — fallback to default */ })
  }, [scope])

  const setValue = (next: T) => {
    setValueState(next)
    setUiPref(scope, "groupBy", next).catch(() => { /* non-fatal */ })
  }

  return { value, setValue }
}
