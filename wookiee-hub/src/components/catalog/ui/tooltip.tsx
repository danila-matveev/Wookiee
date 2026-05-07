import type { ReactNode } from "react"

interface TooltipProps {
  text: string
  children: ReactNode
}

export function Tooltip({ text, children }: TooltipProps) {
  return (
    <span className="group relative inline-flex">
      {children}
      <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1.5 px-2 py-1 bg-stone-900 text-white text-[11px] rounded whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
        {text}
      </span>
    </span>
  )
}
