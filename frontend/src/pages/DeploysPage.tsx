import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, GitPullRequest, RefreshCw, Rocket, Tag, TriangleAlert } from 'lucide-react'
import { Fragment, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { CreatePrsDialog } from '@/components/CreatePrsDialog'
import { DeployDialog } from '@/components/DeployDialog'
import { DeployStatus } from '@/components/DeployStatus'
import { PendingChanges } from '@/components/PendingChanges'
import { ReleaseDialog } from '@/components/ReleaseDialog'
import { StarButton, StarredFilter } from '@/components/StarButton'
import { useReleaseSync } from '@/hooks/useReleaseSync'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ACTIVE_STATUSES, api, type DeployTarget, type PendingCheck, type Project } from '@/lib/api'
import { formatDateTime, timeAgo } from '@/lib/time'
import { cn } from '@/lib/utils'

const ownPendingKey = (p: Project) => ['pending', p.id, p.base_branch, p.head_branch]

const ENV_ORDER: Record<string, number> = { dev: 0, staging: 1, demo: 2, prod: 3 }
const envSort = (a: string, b: string) =>
  (ENV_ORDER[a] ?? 1.5) - (ENV_ORDER[b] ?? 1.5) || a.localeCompare(b)

export default function DeploysPage() {
  const qc = useQueryClient()
  const { data: status } = useQuery({ queryKey: ['status'], queryFn: api.status })
  const overview = useQuery({
    queryKey: ['deploys', 'overview'],
    queryFn: api.deployOverview,
    // Poll quickly while something is running, slowly otherwise.
    refetchInterval: (q) =>
      q.state.data?.some((r) => r.targets.some((t) => t.last_deployment && ACTIVE_STATUSES.has(t.last_deployment.status)))
        ? 4000
        : 30000,
  })
  const releaseSync = useReleaseSync()

  const [search, setSearch] = useState('')
  const [team, setTeam] = useState<string | null>(null)
  const [starredOnly, setStarredOnly] = useState(false)
  const [dialog, setDialog] = useState<{ project: Project; target: DeployTarget; key: number } | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [releaseFor, setReleaseFor] = useState<{ project: Project; key: number } | null>(null)
  const [releaseOpen, setReleaseOpen] = useState(false)
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const [prRows, setPrRows] = useState<{ rows: PendingCheck[]; key: number } | null>(null)
  const [prOpen, setPrOpen] = useState(false)


  const rows = useMemo(() => overview.data ?? [], [overview.data])
  const environments = useMemo(
    () => [...new Set(rows.flatMap((r) => r.targets.map((t) => t.environment)))].sort(envSort),
    [rows],
  )
  const teams = useMemo(
    () => [...new Set(rows.flatMap((r) => r.project.teams.map((t) => t.name)))].sort(),
    [rows],
  )
  const activeTeam = team && teams.includes(team) ? team : null
  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return rows.filter(
      (r) =>
        (!starredOnly || r.project.starred) &&
        (!activeTeam || r.project.teams.some((t) => t.name === activeTeam)) &&
        (!q || r.project.repo.toLowerCase().includes(q) || r.project.name.toLowerCase().includes(q)),
    )
  }, [rows, search, activeTeam, starredOnly])

  // Pending commits on each project's own branches (like `check`). Only starred projects
  // are compared on GitHub as the page opens; the rest wait for a refresh.
  const githubReady = status?.github === true
  const ownChecks = useQueries({
    queries: rows.map(({ project: p }) => ({
      queryKey: ownPendingKey(p),
      queryFn: async () =>
        (await api.checkPending({ project_ids: [p.id], base: p.base_branch, head: p.head_branch }))[0],
      enabled: githubReady && p.starred,
      staleTime: 60_000,
    })),
  })
  const pendingBy = new Map(rows.map((r, i) => [r.project.id, ownChecks[i]]))
  const unchecked = filtered.filter((r) => !r.project.starred)
  const checkRest = useMutation({
    // One request for all of them; each result lands in that project's own query.
    mutationFn: (projects: Project[]) => api.checkPending({ project_ids: projects.map((p) => p.id) }),
    onSuccess: (results, projects) => {
      for (const r of results) {
        const p = projects.find((x) => x.id === r.project_id)
        if (p) qc.setQueryData(ownPendingKey(p), r)
      }
    },
    onError: (e) => toast.error(`Could not check branches: ${e.message}`),
  })

  const creatable = filtered
    .map((r) => pendingBy.get(r.project.id)?.data)
    .filter((c): c is PendingCheck => !!c && !c.error && !!c.ahead_by && !c.open_pr_url)
  const openPrs = (rows: PendingCheck[]) => {
    setPrRows({ rows, key: Date.now() })
    setPrOpen(true)
  }
  const toggleRow = (id: number) =>
    setExpanded((s) => {
      const next = new Set(s)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  const columns = 3 + environments.length

  const openDeploy = (project: Project, target: DeployTarget) => {
    setDialog({ project, target, key: Date.now() })
    setDialogOpen(true)
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Environments</h2>
          <p className="text-sm text-muted-foreground">
            Trigger deploy workflows and follow their runs, and see what's waiting to be released. Open a project to
            compare its branches and create the release PR.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {releaseSync.latest?.finished_at && (
            <span className="text-xs text-muted-foreground" title={formatDateTime(releaseSync.latest.finished_at)}>
              Releases updated {timeAgo(releaseSync.latest.finished_at)}
            </span>
          )}
          <Button
            variant="outline"
            onClick={() => checkRest.mutate(unchecked.map((r) => r.project))}
            disabled={!githubReady || checkRest.isPending || unchecked.length === 0}
            title="Compare branches on GitHub for the listed projects that aren't starred (starred ones are checked automatically)"
          >
            <RefreshCw className={cn(checkRest.isPending && 'animate-spin')} />
            {checkRest.isPending ? 'Checking…' : `Check the rest (${unchecked.length})`}
          </Button>
          <Button
            variant="outline"
            onClick={() => openPrs(creatable)}
            disabled={creatable.length === 0}
            title="Open release PRs for every listed project with pending commits on its own branches"
          >
            <GitPullRequest />
            Create PRs{creatable.length ? ` (${creatable.length})` : ''}
          </Button>
          <Button
            variant="outline"
            onClick={() => releaseSync.start()}
            disabled={releaseSync.running || status?.github === false}
          >
            <RefreshCw className={cn(releaseSync.running && 'animate-spin')} />
            {releaseSync.running ? 'Refreshing…' : 'Refresh releases'}
          </Button>
        </div>
      </header>

      {status?.github === false && (
        <div className="flex gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-300">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            <code>GITHUB_TOKEN</code> is not set, so deploys and release refreshes are disabled. Add it to{' '}
            <code>.env</code> and restart Tiamat.
          </span>
        </div>
      )}

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center gap-3">
          <CardTitle className="mr-auto">All projects</CardTitle>
          <div className="flex flex-wrap gap-1">
            <StarredFilter active={starredOnly} onChange={setStarredOnly} />
            {[null, ...teams].map((t) => (
              <button
                key={t ?? 'all'}
                aria-pressed={activeTeam === t}
                onClick={() => setTeam(t)}
                className={cn(
                  'rounded-full border px-3 py-0.5 text-xs',
                  activeTeam === t ? 'bg-primary text-primary-foreground' : 'hover:bg-muted',
                )}
              >
                {t ?? 'all'}
              </button>
            ))}
          </div>
          <Input
            placeholder="Search projects…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-48"
          />
        </CardHeader>
        <CardContent>
          {overview.error ? (
            <p className="text-sm text-destructive">Could not load deploys: {overview.error.message}</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Project</TableHead>
                  <TableHead>Latest release</TableHead>
                  <TableHead>Pending</TableHead>
                  {environments.map((env) => (
                    <TableHead key={env} className="capitalize">
                      {env}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {overview.isLoading &&
                  Array.from({ length: 5 }, (_, i) => (
                    <TableRow key={i}>
                      <TableCell colSpan={3 + Math.max(environments.length, 3)}>
                        <Skeleton className="h-6 w-full" />
                      </TableCell>
                    </TableRow>
                  ))}
                {filtered.map(({ project, latest_release, targets }) => {
                  const isOpen = expanded.has(project.id)
                  const own = pendingBy.get(project.id)
                  const check = own?.data
                  const checking = !!own?.isFetching || (checkRest.isPending && !project.starred)
                  return (
                  <Fragment key={project.id}>
                  <TableRow>
                    <TableCell>
                      <div className="flex items-center gap-1.5 font-medium">
                        <StarButton projectId={project.id} name={project.name} starred={project.starred} />
                        {project.name}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {project.teams.map((t) => t.name).join(', ') || '—'}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                      {latest_release ? (
                        <a
                          href={latest_release.url ?? undefined}
                          target="_blank"
                          rel="noreferrer"
                          className="group flex flex-col"
                          title={formatDateTime(latest_release.published_at)}
                        >
                          <span className="font-mono text-xs group-hover:underline">{latest_release.tag}</span>
                          <span className="text-xs text-muted-foreground">{timeAgo(latest_release.published_at)}</span>
                        </a>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                      {project.workflow_version === 'v1' && (
                        <Button
                          size="icon-xs"
                          variant="ghost"
                          className="ml-auto"
                          title="New release (bump)"
                          aria-label={`New release for ${project.name}`}
                          disabled={status?.github === false}
                          onClick={() => {
                            setReleaseFor({ project, key: Date.now() })
                            setReleaseOpen(true)
                          }}
                        >
                          <Tag />
                        </Button>
                      )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-0.5">
                        <button
                          aria-expanded={isOpen}
                          aria-label={`${isOpen ? 'Hide' : 'Show'} pending changes for ${project.name}`}
                          onClick={() => toggleRow(project.id)}
                          className="flex items-center gap-1 rounded-md px-1 py-0.5 text-xs hover:bg-muted"
                          title={check?.error ?? `${project.base_branch} ← ${project.head_branch}`}
                        >
                          {isOpen ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
                          {checking && !check ? (
                            <span className="text-muted-foreground">Checking…</span>
                          ) : check?.error ? (
                            <span className="text-destructive">Can't compare</span>
                          ) : check?.ahead_by ? (
                            <span className="font-medium tabular-nums">
                              {check.ahead_by} commit{check.ahead_by === 1 ? '' : 's'}
                            </span>
                          ) : check ? (
                            <span className="text-muted-foreground">Up to date</span>
                          ) : (
                            <span className="text-muted-foreground">Not checked</span>
                          )}
                          {check?.open_pr_url && (
                            <GitPullRequest className="size-3 text-muted-foreground" aria-label="PR open" />
                          )}
                        </button>
                        <Button
                          size="icon-xs"
                          variant="ghost"
                          aria-label={`Check pending changes for ${project.name}`}
                          title={check ? 'Check again' : 'Check now'}
                          disabled={!githubReady || checking}
                          onClick={() => own?.refetch()}
                          className="text-muted-foreground"
                        >
                          <RefreshCw className={cn(checking && 'animate-spin')} />
                        </Button>
                      </div>
                    </TableCell>
                    {environments.map((env) => {
                      const target = targets.find((t) => t.environment === env)
                      if (!target) {
                        return (
                          <TableCell key={env} className="text-xs text-muted-foreground">
                            —
                          </TableCell>
                        )
                      }
                      const last = target.last_deployment
                      const running = !!last && ACTIVE_STATUSES.has(last.status)
                      return (
                        <TableCell key={env}>
                          <div className="flex items-center gap-2">
                            <Button
                              size="xs"
                              variant="outline"
                              disabled={running || status?.github === false}
                              onClick={() => openDeploy(project, target)}
                              aria-label={`Deploy ${project.name} to ${env}`}
                            >
                              <Rocket />
                              Deploy
                            </Button>
                            {last &&
                              (last.run_url ? (
                                <a
                                  href={last.run_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="rounded p-0.5 hover:bg-muted"
                                  aria-label={`Open run for ${project.name} ${env} on GitHub`}
                                >
                                  <DeployStatus status={last.status} at={last.created_at} iconOnly />
                                </a>
                              ) : (
                                <DeployStatus status={last.status} at={last.created_at} iconOnly />
                              ))}
                          </div>
                        </TableCell>
                      )
                    })}
                  </TableRow>
                  {isOpen && (
                    <TableRow className="bg-muted/30 hover:bg-muted/30">
                      <TableCell colSpan={columns} className="whitespace-normal">
                        <PendingChanges
                          project={project}
                          githubReady={githubReady}
                          onCreatePr={(row) => openPrs([row])}
                        />
                      </TableCell>
                    </TableRow>
                  )}
                  </Fragment>
                  )
                })}
                {!overview.isLoading && filtered.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={columns} className="text-center text-muted-foreground">
                      No projects match.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {prRows && (
        <CreatePrsDialog
          key={prRows.key}
          open={prOpen}
          onOpenChange={setPrOpen}
          rows={prRows.rows}
          slackConfigured={status?.slack === true}
          onDone={() => {}}
        />
      )}
      {releaseFor && (
        <ReleaseDialog
          key={releaseFor.key}
          open={releaseOpen}
          onOpenChange={setReleaseOpen}
          project={releaseFor.project}
        />
      )}
      {dialog && (
        <DeployDialog
          key={dialog.key}
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          project={dialog.project}
          target={dialog.target}
        />
      )}
    </div>
  )
}
