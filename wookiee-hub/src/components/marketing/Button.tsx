import { forwardRef, type ButtonHTMLAttributes } from "react"

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary"
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", className = "", ...props }, ref) => {
    const base = "py-1.5 rounded-md text-sm font-medium disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
    const variants = {
      primary: "bg-stone-900 text-white hover:bg-stone-800 px-3",
      secondary: "border border-stone-200 text-stone-700 hover:bg-stone-50 px-3",
    }
    return <button ref={ref} className={`${base} ${variants[variant]} ${className}`} {...props} />
  }
)
Button.displayName = "Button"
