import { X } from "lucide-react"

interface FilterChipProps {
  label: string
  values: string[]
  onRemove: () => void
}

export function FilterChip({ label, values, onRemove }: FilterChipProps) {
  const displayValues =
    values.length <= 2
      ? values.join(", ")
      : `${values[0]}, +${values.length - 1}`

  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
      <span className="text-muted-foreground">{label}:</span>
      <span>{displayValues}</span>
      <button
        type="button"
        onClick={onRemove}
        className="ml-0.5 rounded-full p-0.5 hover:bg-primary/20 focus:outline-none"
        aria-label={`Удалить фильтр ${label}`}
      >
        <X className="h-3 w-3" />
      </button>
    </span>
  )
}
