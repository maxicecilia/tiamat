import { BarChart3, Circle, Rocket, Settings } from 'lucide-react'
import { lazy, Suspense } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { ThemeToggle } from '@/components/ThemeToggle'
import { SKINS, useTheme } from '@/lib/theme'
import { cn } from '@/lib/utils'
import DeployHistoryPage from '@/pages/DeployHistoryPage'
import DeploysLayout from '@/pages/DeploysLayout'
import DeploysPage from '@/pages/DeploysPage'
import ProjectsPage from '@/pages/ProjectsPage'
import SettingsPage from '@/pages/SettingsPage'
import TagsPage from '@/pages/TagsPage'
import WorkflowsPage from '@/pages/WorkflowsPage'

// Charts pull in recharts; load that page on demand.
const MetricsPage = lazy(() => import('@/pages/MetricsPage'))

type Head = 'red' | 'white' | 'black' | 'green' | 'blue'

/** Tiamat's five chromatic heads; each area of the dashboard is one of them
 * (shown by the "Tiamat" skin). Green and blue are unclaimed for now. */
const HEADS: Record<Head, { color: string; title: string }> = {
  red: { color: '#f0545a', title: 'the red head' },
  white: { color: '#e4e4ea', title: 'the white head' },
  black: { color: '#8a8a9a', title: 'the black head' },
  green: { color: '#34c975', title: 'the green head' },
  blue: { color: '#4c97ff', title: 'the blue head' },
}

const nav: { to: string; label: string; icon: typeof Rocket; head: Head }[] = [
  { to: '/deploys', label: 'Deploys', icon: Rocket, head: 'red' },
  { to: '/metrics', label: 'Metrics', icon: BarChart3, head: 'white' },
  { to: '/settings', label: 'Settings', icon: Settings, head: 'black' },
]

/** Heads not tied to a feature yet (future integrations such as Jira). */
const UNCLAIMED: Head[] = ['green', 'blue']

export default function App() {
  const { skin } = useTheme()
  const { pathname } = useLocation()
  const head = nav.find((n) => pathname.startsWith(n.to))?.head ?? 'red'
  const tagline = SKINS.find((s) => s.value === skin)?.tagline
  const showHeads = skin === 'tiamat'

  return (
    <div className="flex min-h-svh bg-background text-foreground" data-head={head}>
      <aside className="sticky top-0 flex h-svh w-56 shrink-0 flex-col border-r bg-sidebar px-3 py-4">
        <div className="mb-6 flex items-center gap-2 px-2">
          <img src="/logo.svg" alt="" className="size-8" />
          <div className="leading-tight">
            <span className="block text-lg font-semibold">Tiamat</span>
            {tagline && <span className="block text-[11px] text-muted-foreground">{tagline}</span>}
          </div>
        </div>
        <nav className="flex flex-col gap-1">
          {nav.map(({ to, label, icon: Icon, head: h }) => (
            <NavLink
              key={to}
              to={to}
              title={showHeads ? HEADS[h].title : undefined}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-sidebar-accent',
                  isActive && 'bg-sidebar-accent font-medium',
                )
              }
            >
              <Icon className="size-4 shrink-0" style={showHeads ? { color: HEADS[h].color } : undefined} />
              {label}
            </NavLink>
          ))}
          {showHeads &&
            UNCLAIMED.map((h) => (
              <span
                key={h}
                className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground/60"
                title={`${HEADS[h].title}: not claimed by a feature yet`}
              >
                <Circle className="size-4 shrink-0" style={{ color: HEADS[h].color }} />
                <span className="leading-tight">
                  Unclaimed
                  <span className="block text-[10px]">coming later</span>
                </span>
              </span>
            ))}
        </nav>
        <div className="mt-auto px-2">
          <ThemeToggle />
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-8">
        <Routes>
          <Route path="/" element={<Navigate to="/deploys" replace />} />
          <Route path="/deploys" element={<DeploysLayout />}>
            <Route index element={<DeploysPage />} />
            <Route path="history" element={<DeployHistoryPage />} />
            <Route path="changes" element={<Navigate to="/deploys" replace />} />
          </Route>
          <Route
            path="/metrics"
            element={
              <Suspense fallback={null}>
                <MetricsPage />
              </Suspense>
            }
          />
          <Route path="/settings" element={<SettingsPage />}>
            <Route index element={<Navigate to="/settings/projects" replace />} />
            <Route path="projects" element={<ProjectsPage />} />
            <Route path="workflows" element={<WorkflowsPage />} />
            <Route path="teams" element={<TagsPage />} />
          </Route>
          {/* Old addresses, from before Pending changes joined Deploys and Settings had tabs. */}
          <Route path="/changes" element={<Navigate to="/deploys" replace />} />
          <Route path="/projects" element={<Navigate to="/settings/projects" replace />} />
          <Route path="/workflows" element={<Navigate to="/settings/workflows" replace />} />
          <Route path="/tags" element={<Navigate to="/settings/teams" replace />} />
          <Route path="*" element={<Navigate to="/deploys" replace />} />
        </Routes>
      </main>
    </div>
  )
}
