import { SelectMenu } from "./SelectMenu"

interface GroupByOption<T extends string> {
  value: T
  label: string
}

interface GroupBySelectorProps<T extends string> {
  value: T
  options: readonly GroupByOption<T>[]
  onChange: (v: T) => void
  label?: string
}

export function GroupBySelector<T extends string>({
  value,
  options,
  onChange,
  label = "Группировка",
}: GroupBySelectorProps<T>) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[11px] uppercase tracking-wider text-stone-500">{label}:</span>
      <div className="w-[180px]">
        <SelectMenu
          value={value}
          options={options as unknown as { value: string; label: string }[]}
          onChange={(v) => onChange(v as T)}
        />
      </div>
    </div>
  )
}
