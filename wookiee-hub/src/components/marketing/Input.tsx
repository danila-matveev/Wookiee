import { forwardRef, InputHTMLAttributes } from "react"

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className = "", ...props }, ref) => (
    <input
      ref={ref}
      className={`w-full border border-stone-200 rounded-md px-2.5 py-1.5 text-sm text-stone-900 focus:outline-none focus:border-stone-900 focus:ring-1 focus:ring-stone-900 bg-white ${className}`}
      {...props}
    />
  )
)
Input.displayName = "Input"
