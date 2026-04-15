import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import {
  Command,
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandShortcut,
} from "@/components/ui/command"
import { navigationGroups } from "@/config/navigation"
import { useThemeStore } from "@/stores/theme"
import { Moon, Sun } from "lucide-react"

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const { theme, setTheme } = useThemeStore()

  // Global Cmd+K / Ctrl+K listener
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        setOpen((prev) => !prev)
      }
    }
    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [])

  function handleSelect(path: string) {
    navigate(path)
    setOpen(false)
  }

  return (
    <CommandDialog
      open={open}
      onOpenChange={(value) => setOpen(value)}
      title="Навигация"
      description="Найдите страницу или действие"
    >
      <Command>
        <CommandInput placeholder="Поиск..." />
        <CommandList>
          <CommandEmpty>Ничего не найдено</CommandEmpty>

          {/* Navigation groups */}
          {navigationGroups.map((group) => (
            <CommandGroup key={group.id} heading={group.label}>
              {group.items.map((item) => {
                const Icon = item.icon
                return (
                  <CommandItem
                    key={item.id}
                    onSelect={() => handleSelect(item.path)}
                  >
                    <Icon size={16} />
                    <span>{item.label}</span>
                  </CommandItem>
                )
              })}
            </CommandGroup>
          ))}

          {/* Actions group */}
          <CommandGroup heading="Действия">
            <CommandItem
              onSelect={() => {
                setTheme(theme === "dark" ? "light" : "dark")
                setOpen(false)
              }}
            >
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
              <span>
                {theme === "dark" ? "Светлая тема" : "Тёмная тема"}
              </span>
              <CommandShortcut>⌘T</CommandShortcut>
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>
    </CommandDialog>
  )
}
