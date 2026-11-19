import { NavLink, Outlet } from 'react-router-dom'
import { cn } from '@/lib/utils'

export type PageTab = { to: string; label: string; end?: boolean }

/** A page title over a row of tabs; each tab is a nested route shown in the outlet. */
export function TabbedPage({ title, tabs, className }: { title: string; tabs: PageTab[]; className?: string }) {
  return (
    <div className={cn('mx-auto flex max-w-6xl flex-col gap-6', className)}>
      <header className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <nav aria-label={title} className="flex gap-1 border-b">
          {tabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              className={({ isActive }) =>
                cn(
                  '-mb-px border-b-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground',
                  isActive ? 'border-primary font-medium text-foreground' : 'border-transparent',
                )
              }
            >
              {t.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <Outlet />
    </div>
  )
}
