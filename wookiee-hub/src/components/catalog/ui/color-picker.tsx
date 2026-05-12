// W9.12 — Generic colour palette picker filtered by category.
//
// Two display modes:
//   - mode="multi" (default): checkbox grid, returns Set<number> of selected ids.
//   - mode="single": single-select swatch chip, returns one id.
//
// Both modes filter colours via `useAvailableColors(kategoriyaId)`.
// `excludeIds` lets the caller drop already-used colours (e.g. exclude colours
// already attached to a variation so duplicates are not offered).

import { useMemo } from "react"

import { useAvailableColors } from "@/hooks/use-available-colors"
import { swatchColor } from "@/lib/catalog/color-utils"
import type { CvetRow } from "@/lib/catalog/service"

interface ColorPickerCommonProps {
  /**
   * Filter palette to colours applicable to this category id.
   * `null`/`undefined` → show all colours (no filter).
   */
  categoryId?: number | null
  /** Colour ids to hide (already attached / disabled). */
  excludeIds?: Iterable<number>
  /**
   * Optional caller-side preview for the artikul string built from each colour.
   * Receives a row; returns a short string rendered next to the swatch.
   */
  previewArtikul?: (row: CvetRow) => string
  emptyHint?: string
  loadingHint?: string
  /** Container className override. */
  className?: string
}

interface ColorPickerMultiProps extends ColorPickerCommonProps {
  mode?: "multi"
  selectedIds: Set<number>
  onToggle: (id: number) => void
}

interface ColorPickerSingleProps extends ColorPickerCommonProps {
  mode: "single"
  value: number | null
  onChange: (id: number) => void
}

export type ColorPickerProps = ColorPickerMultiProps | ColorPickerSingleProps

export function ColorPicker(props: ColorPickerProps) {
  const { categoryId, excludeIds, className } = props
  const { colors, isLoading } = useAvailableColors(categoryId ?? null)

  const excludedSet = useMemo(() => new Set(excludeIds ?? []), [excludeIds])
  const visible = useMemo(
    () => colors.filter((c) => !excludedSet.has(c.id)),
    [colors, excludedSet],
  )

  if (isLoading) {
    return (
      <div className="text-sm text-stone-400 italic py-6 text-center">
        {props.loadingHint ?? "Загрузка цветов…"}
      </div>
    )
  }

  if (visible.length === 0) {
    return (
      <div className="text-sm text-stone-400 italic py-6 text-center">
        {props.emptyHint ?? "Нет доступных цветов для этой категории"}
      </div>
    )
  }

  if (props.mode === "single") {
    const { value, onChange, previewArtikul } = props
    return (
      <div className={className ?? "grid grid-cols-2 gap-1.5 max-h-[40vh] overflow-y-auto pr-1"}>
        {visible.map((c) => {
          const checked = value === c.id
          const hex = c.hex ?? swatchColor(c.color_code)
          return (
            <button
              type="button"
              key={c.id}
              onClick={() => onChange(c.id)}
              className={`flex items-center gap-2 px-2 py-1.5 rounded-md border text-sm transition-colors text-left ${
                checked
                  ? "border-stone-900 bg-stone-50"
                  : "border-stone-200 hover:border-stone-400"
              }`}
            >
              <span
                className="inline-block w-4 h-4 rounded ring-1 ring-stone-200 shrink-0"
                style={{ background: hex }}
              />
              <span className="font-mono text-xs text-stone-700 shrink-0">{c.color_code}</span>
              {c.cvet && (
                <span className="text-stone-500 text-xs truncate">{c.cvet}</span>
              )}
              {previewArtikul && (
                <span className="ml-auto font-mono text-[10px] text-stone-400 truncate shrink-0 pl-1">
                  {previewArtikul(c)}
                </span>
              )}
            </button>
          )
        })}
      </div>
    )
  }

  // Multi mode (default).
  const { selectedIds, onToggle, previewArtikul } = props
  return (
    <div className={className ?? "grid grid-cols-2 gap-1.5 max-h-[40vh] overflow-y-auto pr-1"}>
      {visible.map((c) => {
        const checked = selectedIds.has(c.id)
        const hex = c.hex ?? swatchColor(c.color_code)
        return (
          <label
            key={c.id}
            className={`flex items-center gap-2 px-2 py-1.5 rounded-md border cursor-pointer text-sm transition-colors ${
              checked
                ? "border-stone-900 bg-stone-50"
                : "border-stone-200 hover:border-stone-400"
            }`}
          >
            <input
              type="checkbox"
              checked={checked}
              onChange={() => onToggle(c.id)}
              className="shrink-0 accent-stone-900"
            />
            <span
              className="inline-block w-4 h-4 rounded ring-1 ring-stone-200 shrink-0"
              style={{ background: hex }}
            />
            <span className="font-mono text-xs text-stone-700 shrink-0">{c.color_code}</span>
            {c.cvet && (
              <span className="text-stone-500 text-xs truncate">{c.cvet}</span>
            )}
            {previewArtikul && (
              <span className="ml-auto font-mono text-[10px] text-stone-400 truncate shrink-0 pl-1">
                {previewArtikul(c)}
              </span>
            )}
          </label>
        )
      })}
    </div>
  )
}

/**
 * Public re-export for callers that need the underlying visible-colour list
 * (e.g. for "Select all" buttons).
 */
export { useAvailableColors }
