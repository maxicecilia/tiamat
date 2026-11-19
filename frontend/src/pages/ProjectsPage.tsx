import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Archive, ArchiveRestore, MoreHorizontal, Pencil, Plus, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { ProjectSheet } from '@/components/ProjectSheet'
import { StarButton, StarredFilter } from '@/components/StarButton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { api, type Project } from '@/lib/api'
import { cn } from '@/lib/utils'

export default function ProjectsPage() {
  const qc = useQueryClient()
  const [showArchived, setShowArchived] = useState(false)
  const { data: projects, isLoading, error } = useQuery({
    queryKey: ['projects', { archived: showArchived }],
    queryFn: () => api.projects(showArchived),
  })
  const [search, setSearch] = useState('')
  const [team, setTeam] = useState<string | null>(null)
  const [starredOnly, setStarredOnly] = useState(false)
  const [editing, setEditing] = useState<Project | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [sheetKey, setSheetKey] = useState(0)
  const [deleting, setDeleting] = useState<Project | null>(null)

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['projects'] })
    qc.invalidateQueries({ queryKey: ['tags'] })
    qc.invalidateQueries({ queryKey: ['teams'] })
    qc.invalidateQueries({ queryKey: ['deploys'] })
  }
  const archive = useMutation({
    mutationFn: (p: Project) => api.updateProject(p.id, { archived: !p.archived }),
    onSuccess: (p) => {
      refresh()
      toast.success(p.archived ? `Archived ${p.name}` : `Restored ${p.name}`)
    },
    onError: (e) => toast.error(e.message),
  })
  const remove = useMutation({
    mutationFn: (p: Project) => api.deleteProject(p.id),
    onSuccess: (_, p) => {
      refresh()
      toast.success(`Deleted ${p.name}`)
    },
    onError: (e) => toast.error(e.message),
  })

  const openSheet = (p: Project | null) => {
    setEditing(p)
    setSheetKey((k) => k + 1)
    setSheetOpen(true)
  }

  const active = useMemo(() => (projects ?? []).filter((p) => !p.archived), [projects])
  const teams = useMemo(
    () => [...new Set((projects ?? []).flatMap((p) => p.teams.map((t) => t.name)))].sort(),
    [projects],
  )
  // A filter for a team that is no longer listed (archived toggle, team renamed) falls back to all.
  const activeTeam = team && teams.includes(team) ? team : null
  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return (projects ?? []).filter(
      (p) =>
        (!starredOnly || p.starred) &&
        (!activeTeam || p.teams.some((t) => t.name === activeTeam)) &&
        (!q ||
          p.repo.toLowerCase().includes(q) ||
          p.name.toLowerCase().includes(q) ||
          p.tags.some((t) => t.name.includes(q))),
    )
  }, [projects, search, activeTeam, starredOnly])

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Projects</h2>
          <p className="text-sm text-muted-foreground">
            Repositories Tiamat manages, their teams, tags and release workflow.
          </p>
        </div>
        <Button onClick={() => openSheet(null)}>
          <Plus /> New project
        </Button>
      </header>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Active projects" value={projects && active.length} />
        <Stat label="Teams" value={projects && new Set(active.flatMap((p) => p.teams.map((t) => t.name))).size} />
        <Stat label="v2 workflows" value={projects && active.filter((p) => p.workflow_version === 'v2').length} />
        <Stat label="v1 workflows" value={projects && active.filter((p) => p.workflow_version === 'v1').length} />
      </div>

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
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <Switch size="sm" checked={showArchived} onCheckedChange={setShowArchived} />
            Show archived
          </label>
          <Input
            placeholder="Search name, repo or tag…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-56"
          />
        </CardHeader>
        <CardContent>
          {error ? (
            <p className="text-sm text-destructive">Could not load projects: {error.message}</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Teams</TableHead>
                  <TableHead>Workflow</TableHead>
                  <TableHead>Environments</TableHead>
                  <TableHead>Branches</TableHead>
                  <TableHead>Tags</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading &&
                  Array.from({ length: 5 }, (_, i) => (
                    <TableRow key={i}>
                      <TableCell colSpan={7}>
                        <Skeleton className="h-5 w-full" />
                      </TableCell>
                    </TableRow>
                  ))}
                {filtered.map((p) => (
                  <TableRow
                    key={p.id}
                    className={cn('cursor-pointer', p.archived && 'opacity-50')}
                    onClick={() => openSheet(p)}
                  >
                    <TableCell>
                      <div className="flex items-center gap-1.5 font-medium">
                        <StarButton projectId={p.id} name={p.name} starred={p.starred} />
                        {p.name}
                        {p.archived && (
                          <Badge variant="outline" className="ml-2">
                            archived
                          </Badge>
                        )}
                      </div>
                      <a
                        href={`https://github.com/${p.repo}`}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="text-xs text-muted-foreground hover:underline"
                      >
                        {p.repo}
                      </a>
                    </TableCell>
                    <TableCell>
                      {p.teams.length ? (
                        <div className="flex flex-wrap gap-1">
                          {p.teams.map((t) => (
                            <Badge key={t.id} variant="secondary">
                              {t.name}
                            </Badge>
                          ))}
                        </div>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant={p.workflow_version === 'v2' ? 'default' : 'secondary'}>
                        {p.workflow_version}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {p.deploy_environments ? p.deploy_environments.join(', ') || 'none' : 'all'}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {p.base_branch} ← {p.head_branch}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {p.tags.map((t) => (
                          <Badge key={t.id} variant="outline">
                            {t.name}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <DropdownMenu>
                        <DropdownMenuTrigger
                          render={<Button variant="ghost" size="icon-sm" aria-label={`Actions for ${p.name}`} />}
                        >
                          <MoreHorizontal />
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-40">
                          <DropdownMenuItem onClick={() => openSheet(p)}>
                            <Pencil /> Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => archive.mutate(p)}>
                            {p.archived ? <ArchiveRestore /> : <Archive />}
                            {p.archived ? 'Restore' : 'Archive'}
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem variant="destructive" onClick={() => setDeleting(p)}>
                            <Trash2 /> Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
                {!isLoading && filtered.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground">
                      No projects match.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <ProjectSheet key={sheetKey} open={sheetOpen} onOpenChange={setSheetOpen} project={editing} />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Delete ${deleting?.name}?`}
        description="This removes the project and its deploy and release history from Tiamat. The GitHub repository is not touched. Archive it instead if you might want it back."
        onConfirm={() => deleting && remove.mutate(deleting)}
      />
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number | undefined }) {
  return (
    <Card size="sm">
      <CardContent>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-2xl font-semibold tabular-nums">{value ?? '—'}</p>
      </CardContent>
    </Card>
  )
}
