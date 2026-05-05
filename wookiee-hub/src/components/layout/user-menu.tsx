import { User, Settings, LogOut } from "lucide-react"
import { useNavigate } from "react-router-dom"

import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu"
import { supabase } from "@/lib/supabase"

function UserMenu() {
  const navigate = useNavigate()

  async function handleLogout() {
    await supabase.auth.signOut()
    navigate("/login")
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        data-slot="user-menu-trigger"
        className="flex items-center justify-center w-8 h-8 rounded-full bg-accent-soft text-accent text-[11px] font-semibold shrink-0 cursor-pointer select-none hover:opacity-80 transition-opacity"
      >
        ДМ
      </DropdownMenuTrigger>
      <DropdownMenuContent side="right" sideOffset={8} align="end">
        <DropdownMenuItem>
          <User size={14} />
          Профиль
        </DropdownMenuItem>
        <DropdownMenuItem>
          <Settings size={14} />
          Настройки
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onSelect={handleLogout}>
          <LogOut size={14} />
          Выход
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export { UserMenu }
