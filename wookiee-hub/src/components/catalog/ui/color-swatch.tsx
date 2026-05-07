interface ColorSwatchProps {
  hex: string
  size?: number
}

export function ColorSwatch({ hex, size = 16 }: ColorSwatchProps) {
  return (
    <span
      className="inline-block rounded ring-1 ring-stone-200 shrink-0"
      style={{ background: hex, width: size, height: size }}
    />
  )
}
