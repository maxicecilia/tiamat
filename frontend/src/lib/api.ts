export type Tag = { id: number; name: string; color: string | null }
export type TagWithCount = Tag & { project_count: number }
export type Team = { id: number; name: string }
export type TeamWithCount = Team & { project_count: number }
export type WorkflowVersion = 'v1' | 'v2'

export type Project = {
  id: number
  repo: string
  name: string
  workflow_version: WorkflowVersion
  base_branch: string
  head_branch: string
  description: string | null
  deploy_environments: string[] | null
  archived: boolean
  starred: boolean
  created_at: string
  updated_at: string
  tags: Tag[]
  teams: Team[]
}

export type ProjectInput = {
  repo: string
  name?: string | null
  teams: string[]
  workflow_version: WorkflowVersion
  base_branch: string
  head_branch: string
  description: string | null
  deploy_environments: string[] | null
  tags: string[]
}

export type WorkflowPreset = {
  id: number
  environment: string
  version: WorkflowVersion
  workflow_file: string
  branch: string | null
  inputs: Record<string, string>
  description: string | null
  lock_branch: boolean
}

export type WorkflowPresetInput = Omit<WorkflowPreset, 'id'>

export type Deployment = {
  id: number
  project_id: number
  project_name: string
  repo: string
  environment: string
  workflow_file: string
  branch: string
  inputs: Record<string, string>
  status: string
  error: string | null
  run_id: number | null
  run_url: string | null
  triggered_by: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export type Release = {
  id: number
  project_id: number
  tag: string
  name: string | null
  url: string | null
  published_at: string
}

export type DeployTarget = {
  environment: string
  preset_id: number
  workflow_file: string
  branch: string
  inputs: Record<string, string>
  description: string | null
  lock_branch: boolean
  last_deployment: Deployment | null
}

export type DeployOverviewRow = {
  project: Project
  latest_release: Release | null
  targets: DeployTarget[]
}

export type SyncRun = {
  id: number
  kind: string
  status: string
  started_at: string
  finished_at: string | null
  details: {
    months?: number
    projects?: number
    added?: number
    lead_times?: number
    errors?: Record<string, string>
  }
}

export const ACTIVE_STATUSES = new Set([
  'dispatching',
  'dispatched',
  'queued',
  'in_progress',
  'waiting',
  'requested',
  'pending',
])

/** API timestamps are UTC; SQLite drops the offset, so add it back before parsing. */
export function parseDate(value: string): Date {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
}

export type MetricSummary = {
  deploys: number
  deploys_per_month: number
  tickets: number
  tickets_per_month: number
  failures: number
  change_failure_rate: number | null
  avg_lead_time_days: number | null
  median_lead_time_days: number | null
  lead_time_samples: number
}

export type MonthlyMetric = {
  month: string
  partial: boolean
  deploys: number
  tickets: number
  failures: number
  change_failure_rate: number | null
  avg_lead_time_days: number | null
  median_lead_time_days: number | null
}

export type Metrics = {
  months: number
  team: string | null
  window_start: string
  generated_at: string
  projects: number
  summary: MetricSummary & { deploys_last_30_days: number; tickets_last_30_days: number }
  monthly: MonthlyMetric[]
  teams: (MetricSummary & { team: string; projects: number })[]
  by_project: (MetricSummary & {
    project_id: number
    name: string
    repo: string
    teams: string[]
    starred: boolean
  })[]
}

export type ReleaseRow = {
  id: number
  project_id: number
  project_name: string
  tag: string
  name: string | null
  url: string | null
  released_at: string
  lead_time_days: number | null
  is_failed: boolean
  tickets: string[]
}

export type PendingCommit = {
  sha: string
  message: string
  author: string | null
  date: string | null
  url: string | null
}

export type PendingCheck = {
  project_id: number
  name: string
  repo: string
  base: string
  head: string
  frontend: boolean
  starred: boolean
  ahead_by: number | null
  behind_by?: number
  compare_url?: string | null
  commits: PendingCommit[]
  open_pr_url: string | null
  error: string | null
}

export type PullRequestResult = {
  project_id: number
  name: string
  repo: string
  base: string
  head: string
  status: 'created' | 'exists' | 'no_changes' | 'error'
  url: string | null
  error: string | null
  ahead_by: number | null
}

export type PullRequestsResponse = {
  results: PullRequestResult[]
  slack: { requested: boolean; configured: boolean; sent: { audience: string; ok: boolean }[] }
}

export type BumpKind = 'major' | 'minor' | 'patch'

export type ReleasePlan = {
  project_id: number
  repo: string
  workflow_version: WorkflowVersion
  managed_by_workflow: boolean
  current: string | null
  current_url: string | null
  current_date: string | null
  parseable: boolean
  candidates: Partial<Record<BumpKind, string>>
  target: string
  unreleased_commits: number | null
}

export type CreatedRelease = {
  recorded: boolean
  tag: string
  previous: string | null
  url: string | null
  draft: boolean
  prerelease: boolean
  target: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = Array.isArray(body.detail)
      ? body.detail.map((d: { msg: string }) => d.msg).join(', ')
      : body.detail
    throw new Error(detail ?? `${res.status} ${res.statusText}`)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
})

export const api = {
  projects: (includeArchived = false) =>
    request<Project[]>(`/projects${includeArchived ? '?include_archived=true' : ''}`),
  createProject: (data: ProjectInput) => request<Project>('/projects', json('POST', data)),
  updateProject: (id: number, data: Partial<ProjectInput> & { archived?: boolean; starred?: boolean }) =>
    request<Project>(`/projects/${id}`, json('PATCH', data)),
  deleteProject: (id: number) => request<void>(`/projects/${id}`, { method: 'DELETE' }),

  teams: () => request<TeamWithCount[]>('/teams'),
  createTeam: (name: string) => request<Team>('/teams', json('POST', { name })),
  renameTeam: (id: number, name: string) => request<Team>(`/teams/${id}`, json('PATCH', { name })),
  deleteTeam: (id: number) => request<void>(`/teams/${id}`, { method: 'DELETE' }),

  tags: () => request<TagWithCount[]>('/tags'),
  createTag: (data: { name: string; color?: string | null }) =>
    request<Tag>('/tags', json('POST', data)),
  updateTag: (id: number, data: { name?: string; color?: string | null }) =>
    request<Tag>(`/tags/${id}`, json('PATCH', data)),
  deleteTag: (id: number) => request<void>(`/tags/${id}`, { method: 'DELETE' }),

  workflowPresets: () => request<WorkflowPreset[]>('/workflow-presets'),
  createPreset: (data: WorkflowPresetInput) =>
    request<WorkflowPreset>('/workflow-presets', json('POST', data)),
  updatePreset: (id: number, data: Partial<WorkflowPresetInput>) =>
    request<WorkflowPreset>(`/workflow-presets/${id}`, json('PATCH', data)),
  deletePreset: (id: number) => request<void>(`/workflow-presets/${id}`, { method: 'DELETE' }),

  status: () => request<{ github: boolean; slack: boolean }>('/status'),
  nextVersion: (projectId: number, target?: string | null) =>
    request<ReleasePlan>(
      `/projects/${projectId}/next-version${target ? `?target=${encodeURIComponent(target)}` : ''}`,
    ),
  createRelease: (
    projectId: number,
    data: {
      bump?: BumpKind | null
      version?: string | null
      expected_current: string | null
      target: string
      name?: string | null
      draft: boolean
      prerelease: boolean
    },
  ) => request<CreatedRelease>(`/projects/${projectId}/releases`, json('POST', data)),
  checkPending: (data: { project_ids?: number[] | null; base?: string | null; head?: string | null } = {}) =>
    request<PendingCheck[]>('/pending', json('POST', data)),
  createPullRequests: (data: {
    targets: { project_id: number; base: string; head: string }[]
    notify_slack: boolean
  }) => request<PullRequestsResponse>('/pull-requests', json('POST', data)),
  deployOverview: () => request<DeployOverviewRow[]>('/deploys/overview'),
  deployments: (limit = 50, filters: { project_id?: number | null; environment?: string | null } = {}) => {
    const q = new URLSearchParams({ limit: String(limit) })
    if (filters.project_id != null) q.set('project_id', String(filters.project_id))
    if (filters.environment) q.set('environment', filters.environment)
    return request<Deployment[]>(`/deployments?${q}`)
  },
  deploy: (data: { project_id: number; environment: string; branch?: string | null }) =>
    request<Deployment>('/deployments', json('POST', data)),
  dismissDeployment: (id: number) =>
    request<Deployment>(`/deployments/${id}/dismiss`, { method: 'POST' }),
  refreshDeployment: (id: number) =>
    request<Deployment>(`/deployments/${id}/refresh`, { method: 'POST' }),
  syncReleases: (months = 6) =>
    request<SyncRun>(`/releases/sync?months=${months}`, { method: 'POST' }),
  metrics: (months: number, team: string | null) =>
    request<Metrics>(`/metrics?months=${months}${team ? `&team=${encodeURIComponent(team)}` : ''}`),
  releases: (months: number, team: string | null, limit = 50) =>
    request<ReleaseRow[]>(
      `/releases?months=${months}&limit=${limit}${team ? `&team=${encodeURIComponent(team)}` : ''}`,
    ),
  latestReleaseSync: () => request<SyncRun | null>('/releases/sync/latest'),
}
