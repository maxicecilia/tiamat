import { TabbedPage } from '@/components/TabbedPage'

const SETTINGS_TABS = [
  { to: '/settings/projects', label: 'Projects' },
  { to: '/settings/workflows', label: 'Workflows' },
  { to: '/settings/teams', label: 'Teams & tags' },
]

/** Projects, workflow presets and teams/tags, as tabs of one page. */
export default function SettingsPage() {
  return <TabbedPage title="Settings" tabs={SETTINGS_TABS} />
}
