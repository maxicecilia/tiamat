import { useQuery } from '@tanstack/react-query'
import { CircleCheck, CircleX, Info, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { MonthlyChart } from '@/components/charts/MonthlyChart'
import { StarButton } from '@/components/StarButton'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useReleaseSync } from '@/hooks/useReleaseSync'
import { api, type MetricSummary, parseDate } from '@/lib/api'
import { formatDateTime, timeAgo } from '@/lib/time'
import { cn } from '@/lib/utils'

const RANGES = [3, 6, 12] as const

const fmt = {
  count: (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1)),
  perMonth: (v: number) => v.toFixed(1),
  pct: (v: number) => (v > 0 && v < 10 ? `${v.toFixed(1)}%` : `${Math.round(v)}%`),
  axisPct: (v: number) => `${Math.round(v)}%`,
  axisDays: (v: number) => `${Math.round(v)}d`,
  days: (v: number) => (v < 10 ? `${v.toFixed(1)}d` : `${Math.round(v)}d`),
}

const orDash = (v: number | null | undefined, f: (v: number) => string) => (v == null ? '—' : f(v))

export default function MetricsPage() {
  const [months, setMonths] = useState<number>(6)
  const [team, setTeam] = useState<string | null>(null)
  const { data: status } = useQuery({ queryKey: ['status'], queryFn: api.status })
  const { data: allTeams } = useQuery({ queryKey: ['teams'], queryFn: api.teams })
  const metrics = useQuery({
    queryKey: ['metrics', months, team],
    queryFn: () => api.metrics(months, team),
  })
  const releases = useQuery({
    queryKey: ['metrics', 'releases', months, team],
    queryFn: () => api.releases(months, team, 50),
  })
  const sync = useReleaseSync()

  const m = metrics.data
  const s = m?.summary
  const teams = (allTeams ?? []).filter((t) => t.project_count > 0).map((t) => t.name)
  const noLeadTimes = !!s && s.deploys > 0 && s.lead_time_samples === 0
  const syncedMonths = sync.latest?.details.months
  const since = m
    ? parseDate(m.window_start).toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' })
    : ''

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Metrics</h1>
          <p className="text-sm text-muted-foreground">
            DORA-style metrics from GitHub releases, using the same rules as <code>stats</code>.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {sync.latest?.finished_at && (
            <span className="text-xs text-muted-foreground" title={formatDateTime(sync.latest.finished_at)}>
              Data updated {timeAgo(sync.latest.finished_at)}
            </span>
          )}
          <Button
            variant="outline"
            onClick={() => sync.start(Math.max(months, 6))}
            disabled={sync.running || status?.github === false}
          >
            <RefreshCw className={cn(sync.running && 'animate-spin')} />
            {sync.running ? 'Refreshing…' : 'Refresh data'}
          </Button>
        </div>
      </header>

      {/* Filters: one row above the charts. */}
      <div className="flex flex-wrap items-center gap-3">
        <div role="group" aria-label="Time range" className="flex rounded-md border p-0.5">
          {RANGES.map((r) => (
            <button
              key={r}
              aria-pressed={months === r}
              onClick={() => setMonths(r)}
              className={cn(
                'rounded-sm px-3 py-1 text-xs',
                months === r ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {r} months
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-1" role="group" aria-label="Team">
          {[null, ...teams].map((t) => (
            <button
              key={t ?? 'all'}
              aria-pressed={team === t}
              onClick={() => setTeam(t)}
              className={cn(
                'rounded-full border px-3 py-0.5 text-xs',
                team === t ? 'bg-primary text-primary-foreground' : 'hover:bg-muted',
              )}
            >
              {t ?? 'all teams'}
            </button>
          ))}
        </div>
        {m && <span className="text-xs text-muted-foreground">{m.projects} projects</span>}
      </div>

      {(noLeadTimes || (syncedMonths !== undefined && syncedMonths < months)) && (
        <div className="flex gap-2 rounded-lg border bg-muted/40 p-3 text-sm text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            {noLeadTimes
              ? 'Lead times are not computed yet. '
              : `Release data was last fetched for ${syncedMonths} months. `}
            Use <strong className="text-foreground">Refresh data</strong> to fetch releases and lead times for this
            range.
          </span>
        </div>
      )}

      {metrics.error && (
        <p className="text-sm text-destructive">Could not load metrics: {metrics.error.message}</p>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Tile
          label="Deploys per month"
          value={s && fmt.perMonth(s.deploys_per_month)}
          note={s && `${s.deploys} since ${since} · ${s.deploys_last_30_days} in the last 30 days`}
        />
        <Tile
          label="Change failure rate"
          value={s && orDash(s.change_failure_rate, fmt.pct)}
          note={s && (s.deploys ? `${s.failures} of ${s.deploys} releases marked as failures` : 'No releases')}
        />
        <Tile
          label="Lead time for changes (median)"
          value={s && orDash(s.median_lead_time_days, fmt.days)}
          note={
            s &&
            (s.lead_time_samples
              ? `Average ${fmt.days(s.avg_lead_time_days ?? 0)} over ${s.lead_time_samples} releases`
              : 'Not computed yet')
          }
        />
        <Tile
          label="Tickets per month"
          value={s && fmt.perMonth(s.tickets_per_month)}
          note={s && `${s.tickets} since ${since} · ${s.tickets_last_30_days} in the last 30 days`}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard title="Deploys per month" description="Releases published. The current month is lighter and marked “so far”: it isn't over yet.">
          {m ? (
            <MonthlyChart
              data={m.monthly}
              dataKey="deploys"
              kind="bar"
              format={fmt.count}
              label="deploys"
              detail={(r) => `${r.tickets} tickets`}
            />
          ) : (
            <Skeleton className="h-[200px]" />
          )}
        </ChartCard>
        <ChartCard title="Lead time for changes" description="Median days from the oldest commit to its release.">
          {m ? (
            <MonthlyChart
              data={m.monthly}
              dataKey="median_lead_time_days"
              kind="line"
              format={fmt.days}
              axisFormat={fmt.axisDays}
              label="median"
              detail={(r) => (r.avg_lead_time_days == null ? null : `average ${fmt.days(r.avg_lead_time_days)}`)}
            />
          ) : (
            <Skeleton className="h-[200px]" />
          )}
        </ChartCard>
        <ChartCard title="Change failure rate" description="Share of releases with [hotfix], [rollback], [revert] and similar markers.">
          {m ? (
            <MonthlyChart
              data={m.monthly}
              dataKey="change_failure_rate"
              kind="bar"
              format={fmt.pct}
              axisFormat={fmt.axisPct}
              label="of releases"
              detail={(r) => (r.deploys ? `${r.failures} of ${r.deploys} releases` : 'no releases')}
            />
          ) : (
            <Skeleton className="h-[200px]" />
          )}
        </ChartCard>
      </div>

      {m && m.teams.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Teams</CardTitle>
            <CardDescription>
              A project in several teams counts for each of them. Select a team to focus the page on it.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <SummaryTable
              rows={m.teams.map((t) => ({ ...t, key: t.team, name: t.team, sub: `${t.projects} projects` }))}
              onSelect={(key) => setTeam(key)}
              first="Team"
            />
          </CardContent>
        </Card>
      )}

      {m && (
        <Card>
          <CardHeader>
            <CardTitle>Projects</CardTitle>
          </CardHeader>
          <CardContent>
            <SummaryTable
              rows={m.by_project.map((p) => ({
                ...p,
                key: String(p.project_id),
                sub: p.teams.join(', '),
                starProjectId: p.project_id,
              }))}
              first="Project"
            />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Recent releases</CardTitle>
          <CardDescription>The 50 most recent releases in the range.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Released</TableHead>
                <TableHead>Project</TableHead>
                <TableHead>Release</TableHead>
                <TableHead className="text-right">Lead time</TableHead>
                <TableHead>Outcome</TableHead>
                <TableHead className="text-right">Tickets</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {releases.data?.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="text-xs" title={formatDateTime(r.released_at)}>
                    {timeAgo(r.released_at)}
                  </TableCell>
                  <TableCell className="font-medium">{r.project_name}</TableCell>
                  <TableCell>
                    {r.url ? (
                      <a href={r.url} target="_blank" rel="noreferrer" className="font-mono text-xs hover:underline">
                        {r.tag}
                      </a>
                    ) : (
                      <span className="font-mono text-xs">{r.tag}</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right text-xs tabular-nums">{orDash(r.lead_time_days, fmt.days)}</TableCell>
                  <TableCell>
                    {r.is_failed ? (
                      <span className="inline-flex items-center gap-1 text-xs" style={{ color: 'var(--viz-critical)' }}>
                        <CircleX className="size-3.5" aria-hidden /> Failure marker
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                        <CircleCheck className="size-3.5" aria-hidden /> OK
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right text-xs tabular-nums" title={r.tickets.join(', ')}>
                    {r.tickets.length}
                  </TableCell>
                </TableRow>
              ))}
              {releases.data?.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground">
                    No releases in this range. Use Refresh data to fetch them.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

function Tile({ label, value, note }: { label: string; value: string | undefined; note: string | undefined }) {
  return (
    <Card size="sm">
      <CardContent className="flex flex-col gap-1">
        <p className="text-xs text-muted-foreground">{label}</p>
        {value === undefined ? (
          <Skeleton className="h-8 w-20" />
        ) : (
          <p className="text-3xl font-semibold">{value}</p>
        )}
        <p className="min-h-4 text-xs text-muted-foreground">{note}</p>
      </CardContent>
    </Card>
  )
}

function ChartCard({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

type SummaryRow = MetricSummary & { key: string; name: string; sub: string; starProjectId?: number; starred?: boolean }

function SummaryTable({ rows, onSelect, first }: { rows: SummaryRow[]; onSelect?: (key: string) => void; first: string }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{first}</TableHead>
          <TableHead className="text-right">Deploys / month</TableHead>
          <TableHead className="text-right">Change failure rate</TableHead>
          <TableHead className="text-right">Lead time (median)</TableHead>
          <TableHead className="text-right">Tickets / month</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.key}>
            <TableCell>
              <div className="flex items-center gap-1.5 font-medium">
                {r.starProjectId !== undefined && (
                  <StarButton projectId={r.starProjectId} name={r.name} starred={!!r.starred} />
                )}
                {onSelect ? (
                  <button className="hover:underline" onClick={() => onSelect(r.key)}>
                    {r.name}
                  </button>
                ) : (
                  r.name
                )}
              </div>
              <div className="text-xs text-muted-foreground">{r.sub || '—'}</div>
            </TableCell>
            <TableCell className="text-right tabular-nums">{fmt.perMonth(r.deploys_per_month)}</TableCell>
            <TableCell className="text-right tabular-nums">
              {orDash(r.change_failure_rate, fmt.pct)}
              {r.deploys > 0 && <span className="ml-1 text-xs text-muted-foreground">({r.failures}/{r.deploys})</span>}
            </TableCell>
            <TableCell className="text-right tabular-nums">{orDash(r.median_lead_time_days, fmt.days)}</TableCell>
            <TableCell className="text-right tabular-nums">{fmt.perMonth(r.tickets_per_month)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

