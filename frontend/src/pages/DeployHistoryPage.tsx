import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ExternalLink } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { DeployStatus } from '@/components/DeployStatus'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ACTIVE_STATUSES, api } from '@/lib/api'
import { duration, formatDateTime, timeAgo } from '@/lib/time'
import { cn } from '@/lib/utils'

const ALL_PROJECTS = 'All projects'
const ENV_ORDER: Record<string, number> = { dev: 0, staging: 1, demo: 2, prod: 3 }

/** Deploys triggered from the dashboard, newest first. */
export default function DeployHistoryPage() {
  const qc = useQueryClient()
  const [projectName, setProjectName] = useState(ALL_PROJECTS)
  const [environment, setEnvironment] = useState<string | null>(null)

  const { data: projects } = useQuery({ queryKey: ['projects', { archived: false }], queryFn: () => api.projects() })
  const { data: presets } = useQuery({ queryKey: ['workflow-presets'], queryFn: api.workflowPresets })
  // Starred first, like everywhere else.
  const projectNames = useMemo(
    () =>
      [...(projects ?? [])]
        .sort((a, b) => Number(b.starred) - Number(a.starred) || a.name.localeCompare(b.name))
        .map((p) => p.name),
    [projects],
  )
  const environments = useMemo(
    () =>
      [...new Set((presets ?? []).map((p) => p.environment))].sort(
        (a, b) => (ENV_ORDER[a] ?? 1.5) - (ENV_ORDER[b] ?? 1.5) || a.localeCompare(b),
      ),
    [presets],
  )
  const projectId = projects?.find((p) => p.name === projectName)?.id ?? null
  const filtered = projectId !== null || environment !== null

  // Filtered on the server, so the 100 most recent are the most recent matching ones.
  const history = useQuery({
    queryKey: ['deploys', 'history', projectId, environment],
    queryFn: () => api.deployments(100, { project_id: projectId, environment }),
    refetchInterval: (q) => (q.state.data?.some((d) => ACTIVE_STATUSES.has(d.status)) ? 4000 : 30000),
  })

  const dismiss = useMutation({
    mutationFn: api.dismissDeployment,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['deploys'] }),
    onError: (e) => toast.error(e.message),
  })

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start gap-3">
          <div className="mr-auto">
            <CardTitle>Recent deployments</CardTitle>
            <CardDescription>Deploys triggered from this dashboard, newest first.</CardDescription>
          </div>
          <Select value={projectName} onValueChange={(v) => setProjectName(v ?? ALL_PROJECTS)}>
            <SelectTrigger className="w-48" aria-label="Project">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_PROJECTS}>{ALL_PROJECTS}</SelectItem>
              {projectNames.map((n) => (
                <SelectItem key={n} value={n}>
                  {n}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="flex flex-wrap gap-1 self-center" role="group" aria-label="Environment">
            {[null, ...environments].map((env) => (
              <button
                key={env ?? 'all'}
                aria-pressed={environment === env}
                onClick={() => setEnvironment(env)}
                className={cn(
                  'rounded-full border px-3 py-0.5 text-xs capitalize',
                  environment === env ? 'bg-primary text-primary-foreground' : 'hover:bg-muted',
                )}
              >
                {env ?? 'all'}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>When</TableHead>
              <TableHead>Project</TableHead>
              <TableHead>Environment</TableHead>
              <TableHead>Branch</TableHead>
              <TableHead>By</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead className="w-24" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {history.data?.map((d) => (
              <TableRow key={d.id}>
                <TableCell className="text-xs" title={formatDateTime(d.created_at)}>
                  {timeAgo(d.created_at)}
                </TableCell>
                <TableCell className="font-medium">{d.project_name}</TableCell>
                <TableCell className="capitalize">{d.environment}</TableCell>
                <TableCell className="font-mono text-xs">{d.branch}</TableCell>
                <TableCell className="text-xs text-muted-foreground">{d.triggered_by ?? '—'}</TableCell>
                <TableCell className="whitespace-normal">
                  <DeployStatus status={d.status} />
                  {d.error && <p className="max-w-xs text-xs text-muted-foreground">{d.error}</p>}
                </TableCell>
                <TableCell className="text-xs tabular-nums text-muted-foreground">
                  {d.started_at ? duration(d.started_at, d.finished_at) : '—'}
                </TableCell>
                <TableCell className="flex items-center justify-end gap-2">
                  {ACTIVE_STATUSES.has(d.status) && (
                    <Button
                      size="xs"
                      variant="ghost"
                      title="Stop tracking this deploy (it does not cancel the GitHub run)"
                      onClick={() => dismiss.mutate(d.id)}
                      disabled={dismiss.isPending}
                    >
                      Dismiss
                    </Button>
                  )}
                  {d.run_url && (
                    <a
                      href={d.run_url}
                      target="_blank"
                      rel="noreferrer"
                      aria-label={`Open run for ${d.project_name} ${d.environment} on GitHub`}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      <ExternalLink className="size-4" />
                    </a>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {history.data?.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} className="text-center text-muted-foreground">
                  {filtered ? 'No deploys match these filters.' : 'No deploys yet. Start one from the Environments tab.'}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
