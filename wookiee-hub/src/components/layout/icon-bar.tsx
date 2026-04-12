import { useNavigate } from "react-router-dom"

import { Separator } from "@/components/ui/separator"
import { useNavigationStore } from "@/stores/navigation"
import { navigationGroups } from "@/config/navigation"

import { Logo } from "./logo"
import { IconBarButton } from "./icon-bar-button"
import { ThemeToggle } from "./theme-toggle"
import { UserMenu } from "./user-menu"

function IconBar() {
  const { activeGroup, setActiveGroup } = useNavigationStore()
  const navigate = useNavigate()

  function handleGroupClick(groupId: string) {
    const group = navigationGroups.find((g) => g.id === groupId)
    if (!group) return

    if (group.items.length === 1) {
      // Single-item group: navigate directly, no sidebar
      navigate(group.items[0].path)
      useNavigationStore.setState({ activeGroup: groupId, sidebarOpen: false })
    } else {
      setActiveGroup(groupId)
    }
  }

  return (
    <aside
      data-slot="icon-bar"
      className="fixed left-0 top-0 bottom-0 w-14 bg-icon-bar border-r border-border hidden md:flex flex-col items-center py-3 gap-1 z-50"
    >
      <Logo />
      <Separator className="my-1 w-8" />
      <nav className="flex flex-col items-center gap-1">
        {navigationGroups.map((group) => (
          <IconBarButton
            key={group.id}
            icon={group.icon}
            isActive={activeGroup === group.id}
            onClick={() => handleGroupClick(group.id)}
            tooltip={group.label}
          />
        ))}
      </nav>
      <div className="mt-auto flex flex-col items-center gap-1">
        <ThemeToggle />
        <UserMenu />
      </div>
    </aside>
  )
}

export { IconBar }
