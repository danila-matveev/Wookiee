import * as React from "react"
import { Link } from "react-router-dom"
import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

/* ─────────────────────────────────────────────────────────────
 * <Sidebar>
 *   <Sidebar.Header>…brand / logo / workspace switcher…</Sidebar.Header>
 *   <Sidebar.Nav>
 *     <Sidebar.Section title="Основа">
 *       <Sidebar.Item icon={Home} href="/" label="Главная" active />
 *       <Sidebar.Item icon={Box} href="/catalog" label="Каталог" />
 *     </Sidebar.Section>
 *   </Sidebar.Nav>
 *   <Sidebar.Footer>…user block / theme toggle…</Sidebar.Footer>
 * </Sidebar>
 * ──────────────────────────────────────────────────────────── */

interface SidebarContextValue {
  collapsed: boolean
}

const SidebarContext = React.createContext<SidebarContextValue>({
  collapsed: false,
})

export interface SidebarProps extends React.HTMLAttributes<HTMLElement> {
  collapsed?: boolean
}

interface SidebarRootProps extends SidebarProps {
  children?: React.ReactNode
}

const SidebarRoot = React.forwardRef<HTMLElement, SidebarRootProps>(
  function SidebarRoot(
    { collapsed = false, className, children, ...rest },
    ref,
  ) {
    return (
      <SidebarContext.Provider value={{ collapsed }}>
        <aside
          ref={ref}
          data-collapsed={collapsed || undefined}
          className={cn(
            "shrink-0 h-screen sticky top-0 overflow-hidden flex flex-col",
            "border-r border-default bg-surface-muted",
            "transition-[width] duration-200 ease-out",
            collapsed ? "w-16" : "w-60",
            className,
          )}
          {...rest}
        >
          {children}
        </aside>
      </SidebarContext.Provider>
    )
  },
)

/* ─── Header ─────────────────────────────────────────────── */

export interface SidebarHeaderProps
  extends React.HTMLAttributes<HTMLDivElement> {}

const SidebarHeader = React.forwardRef<HTMLDivElement, SidebarHeaderProps>(
  function SidebarHeader({ className, children, ...rest }, ref) {
    return (
      <div
        ref={ref}
        className={cn(
          "px-4 py-3 border-b border-default shrink-0",
          className,
        )}
        {...rest}
      >
        {children}
      </div>
    )
  },
)

/* ─── Nav (scroll body) ──────────────────────────────────── */

export interface SidebarNavProps
  extends React.HTMLAttributes<HTMLElement> {}

const SidebarNav = React.forwardRef<HTMLElement, SidebarNavProps>(
  function SidebarNav({ className, children, ...rest }, ref) {
    return (
      <nav
        ref={ref}
        className={cn(
          "flex-1 min-h-0 overflow-y-auto py-2 px-2 space-y-3",
          className,
        )}
        {...rest}
      >
        {children}
      </nav>
    )
  },
)

/* ─── Section (group of items) ───────────────────────────── */

export interface SidebarSectionProps
  extends React.HTMLAttributes<HTMLDivElement> {
  title?: string
}

const SidebarSection = React.forwardRef<HTMLDivElement, SidebarSectionProps>(
  function SidebarSection({ title, className, children, ...rest }, ref) {
    const { collapsed } = React.useContext(SidebarContext)
    return (
      <div ref={ref} className={cn("space-y-0.5", className)} {...rest}>
        {title && !collapsed && (
          <div className="px-2 py-1 text-[10px] uppercase tracking-wider text-label">
            {title}
          </div>
        )}
        {children}
      </div>
    )
  },
)

/* ─── Item ──────────────────────────────────────────────── */

export interface SidebarItemProps {
  icon?: LucideIcon
  label: string
  href?: string
  onClick?: () => void
  active?: boolean
  count?: number
  disabled?: boolean
  className?: string
}

const SidebarItem = React.forwardRef<HTMLElement, SidebarItemProps>(
  function SidebarItem(
    { icon: Icon, label, href, onClick, active, count, disabled, className },
    ref,
  ) {
    const { collapsed } = React.useContext(SidebarContext)

    const content = (
      <>
        {Icon && (
          <Icon
            className={cn(
              "w-3.5 h-3.5 shrink-0",
              active ? "" : "text-muted",
            )}
            aria-hidden
          />
        )}
        {!collapsed && (
          <>
            <span className="flex-1 truncate">{label}</span>
            {typeof count === "number" && (
              <span
                className={cn(
                  "inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full",
                  "text-[10px] tabular-nums",
                  active
                    ? "bg-[var(--color-surface)]/15 text-[var(--color-accent-text)]"
                    : "bg-surface text-muted border border-default",
                )}
              >
                {count}
              </span>
            )}
          </>
        )}
      </>
    )

    const classes = cn(
      "group w-full flex items-center gap-2.5 px-2 h-8 rounded-md text-sm",
      "transition-colors outline-none",
      "focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] focus-visible:ring-offset-1 focus-visible:ring-offset-[var(--color-surface)]",
      active
        ? "bg-[var(--color-text-primary)] text-[var(--color-surface)] font-medium"
        : "text-secondary hover:bg-surface hover:text-primary",
      disabled && "opacity-50 cursor-not-allowed pointer-events-none",
      collapsed && "justify-center px-0",
      className,
    )

    if (href && !disabled) {
      return (
        <Link
          ref={ref as React.Ref<HTMLAnchorElement>}
          to={href}
          aria-current={active ? "page" : undefined}
          title={collapsed ? label : undefined}
          className={classes}
          onClick={onClick}
        >
          {content}
        </Link>
      )
    }

    return (
      <button
        ref={ref as React.Ref<HTMLButtonElement>}
        type="button"
        onClick={onClick}
        disabled={disabled}
        aria-current={active ? "page" : undefined}
        title={collapsed ? label : undefined}
        className={classes}
      >
        {content}
      </button>
    )
  },
)

/* ─── Footer ─────────────────────────────────────────────── */

export interface SidebarFooterProps
  extends React.HTMLAttributes<HTMLDivElement> {}

const SidebarFooter = React.forwardRef<HTMLDivElement, SidebarFooterProps>(
  function SidebarFooter({ className, children, ...rest }, ref) {
    return (
      <div
        ref={ref}
        className={cn(
          "shrink-0 px-3 py-3 border-t border-default",
          className,
        )}
        {...rest}
      >
        {children}
      </div>
    )
  },
)

/* ─── Compositional export ───────────────────────────────── */

type SidebarComponent = typeof SidebarRoot & {
  Header: typeof SidebarHeader
  Nav: typeof SidebarNav
  Section: typeof SidebarSection
  Item: typeof SidebarItem
  Footer: typeof SidebarFooter
}

export const Sidebar = SidebarRoot as SidebarComponent
Sidebar.Header = SidebarHeader
Sidebar.Nav = SidebarNav
Sidebar.Section = SidebarSection
Sidebar.Item = SidebarItem
Sidebar.Footer = SidebarFooter
