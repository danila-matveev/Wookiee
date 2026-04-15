import { Sun, Moon } from "lucide-react"

import { cn } from "@/lib/utils"
import { useThemeStore } from "@/stores/theme"

function ThemeToggle() {
  const { theme, toggleTheme } = useThemeStore()
  const isDark = theme === "dark"
  const Icon = isDark ? Sun : Moon

  return (
    <button
      data-slot="theme-toggle"
      onClick={toggleTheme}
      title={isDark ? "Светлая тема" : "Тёмная тема"}
      aria-label={isDark ? "Переключить на светлую тему" : "Переключить на тёмную тему"}
      className={cn(
        "flex items-center justify-center w-11 h-11 rounded-lg transition-colors duration-100 shrink-0",
        "bg-transparent text-text-dim hover:bg-bg-hover hover:text-foreground"
      )}
    >
      <Icon size={20} strokeWidth={1.8} />
    </button>
  )
}

export { ThemeToggle }
