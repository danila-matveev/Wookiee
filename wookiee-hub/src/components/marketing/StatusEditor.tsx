import { useState, useRef, useEffect } from "react"
import { Check, ChevronDown } from "lucide-react"
import { Badge } from "./Badge"
import { STATUS_LABELS, STATUS_COLORS, type StatusUI } from "@/types/marketing"

interface StatusEditorProps {
  status: StatusUI
  onChange: (next: StatusUI) => void
}

export function StatusEditor({ status, onChange }: StatusEditorProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [open])

  const keys: StatusUI[] = ["active", "free", "archive"]

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="group flex items-center gap-1.5 px-2 py-1 rounded-md border border-transparent hover:border-stone-200 transition-colors"
      >
        <Badge color={STATUS_COLORS[status]} label={STATUS_LABELS[status]} />
        <ChevronDown className="w-3 h-3 text-stone-300 group-hover:text-stone-500" />
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 z-30 bg-white border border-stone-200 rounded-lg shadow-sm py-1 min-w-[150px]">
          {keys.map((k) => (
            <button
              key={k}
              onClick={() => {
                onChange(k)
                setOpen(false)
              }}
              className={`w-full flex items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-stone-50 transition-colors ${
                k === status ? "bg-stone-50" : ""
              }`}
            >
              <Badge color={STATUS_COLORS[k]} label={STATUS_LABELS[k]} compact />
              {k === status && <Check className="w-3 h-3 text-emerald-600 ml-auto" />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
