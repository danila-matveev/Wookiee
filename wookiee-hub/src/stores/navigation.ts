import { create } from "zustand"

interface NavigationState {
  activeGroup: string | null
  sidebarOpen: boolean
  mobileMenuOpen: boolean
  setActiveGroup: (id: string) => void
  toggleSidebar: () => void
  closeSidebar: () => void
  openMobileMenu: () => void
  closeMobileMenu: () => void
}

export const useNavigationStore = create<NavigationState>((set, get) => ({
  activeGroup: null,
  sidebarOpen: false,
  mobileMenuOpen: false,
  setActiveGroup: (id) => {
    const current = get()
    if (current.activeGroup === id) {
      set({ sidebarOpen: !current.sidebarOpen })
    } else {
      set({ activeGroup: id, sidebarOpen: true })
    }
  },
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  closeSidebar: () => set({ sidebarOpen: false }),
  openMobileMenu: () => set({ mobileMenuOpen: true }),
  closeMobileMenu: () => set({ mobileMenuOpen: false }),
}))
