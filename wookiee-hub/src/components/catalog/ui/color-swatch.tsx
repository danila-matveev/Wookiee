interface ColorSwatchProps {
  hex: string
  size?: number
}

/**
 * ColorSwatch — небольшой квадратик-превью цвета (non-interactive).
 *
 * Catalog-вариант принимает произвольный `size` (px) и `hex` строкой —
 * ui-v2 `<ColorSwatch>` API (color + ColorSwatchSize sm/md/lg + button)
 * сюда не подходит, поэтому собственная реализация на семантическом
 * border-default.
 */
export function ColorSwatch({ hex, size = 16 }: ColorSwatchProps) {
  return (
    <span
      className="inline-block rounded ring-1 ring-[var(--color-border-default)] shrink-0"
      style={{ background: hex, width: size, height: size }}
    />
  )
}
