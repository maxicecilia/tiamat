import { TabbedPage } from '@/components/TabbedPage'

const DEPLOY_TABS = [
  { to: '/deploys', label: 'Environments', end: true },
  { to: '/deploys/history', label: 'Recent deployments' },
]

/** Deploying, and the record of deploys started here, as tabs of one page. */
export default function DeploysLayout() {
  return <TabbedPage title="Deploys" tabs={DEPLOY_TABS} className="max-w-7xl" />
}
