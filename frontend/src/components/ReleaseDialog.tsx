import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Tag, TriangleAlert } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { api, type BumpKind, type Project } from '@/lib/api'
import { timeAgo } from '@/lib/time'
import { cn } from '@/lib/utils'

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  project: Project
}

const KINDS: { kind: BumpKind; label: string }[] = [
  { kind: 'patch', label: 'Patch' },
  { kind: 'minor', label: 'Minor' },
  { kind: 'major', label: 'Major' },
]

/** The dashboard version of `bump`: next semver from the latest release, then a GitHub release. */
export function ReleaseDialog({ open, onOpenChange, project }: Props) {
  const qc = useQueryClient()
  const [target, setTarget] = useState(project.base_branch)
  const [checkedTarget, setCheckedTarget] = useState(project.base_branch)
  const [kind, setKind] = useState<BumpKind>('minor')
  const [custom, setCustom] = useState('')
  const [name, setName] = useState('')
  const [draft, setDraft] = useState(false)
  const [prerelease, setPrerelease] = useState(false)

  const plan = useQuery({
    queryKey: ['next-version', project.id, checkedTarget],
    queryFn: () => api.nextVersion(project.id, checkedTarget),
    enabled: open,
    staleTime: 0,
  })
  const p = plan.data
  const useCustom = !!p && (!p.parseable || custom.trim() !== '')
  const tag = useCustom ? custom.trim() : (p?.candidates[kind] ?? '')

  const create = useMutation({
    mutationFn: () =>
      api.createRelease(project.id, {
        bump: useCustom ? null : kind,
        version: useCustom ? custom.trim() : null,
        expected_current: p?.current ?? null,
        target: checkedTarget,
        name: name.trim() || null,
        draft,
        prerelease,
      }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['deploys'] })
      qc.invalidateQueries({ queryKey: ['metrics'] })
      toast.success(`Created ${r.draft ? 'draft ' : ''}release ${r.tag} for ${project.name}`, {
        description: [
          r.previous && `Previous: ${r.previous}`,
          !r.recorded && !r.draft && 'Use Refresh releases to show it here.',
        ]
          .filter(Boolean)
          .join(' · ') || undefined,
        action: r.url ? { label: 'Open', onClick: () => window.open(r.url!, '_blank', 'noreferrer') } : undefined,
      })
      onOpenChange(false)
    },
    onError: (e) => {
      // A newer release may exist, or this one may have been created before an error.
      qc.invalidateQueries({ queryKey: ['next-version', project.id] })
      toast.error(e.message)
    },
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (target.trim() !== checkedTarget) {
      setCheckedTarget(target.trim()) // re-plan against the new branch first
      return
    }
    create.mutate()
  }

  return (
    <Dialog open={open} onOpenChange={(o) => (o || !create.isPending) && onOpenChange(o)}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>New release for {project.name}</DialogTitle>
            <DialogDescription>
              Creates a GitHub release and tag with generated notes, like the CLI's <code>bump</code>.
            </DialogDescription>
          </DialogHeader>

          {plan.isLoading && <Skeleton className="h-24" />}
          {plan.error && <p className="text-sm text-destructive">Could not load releases: {plan.error.message}</p>}

          {p && (
            <>
              {p.managed_by_workflow && (
                <div className="flex gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-300">
                  <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                  This project uses the v2 release workflows, which create releases when you deploy. Use Deploy instead.
                </div>
              )}

              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
                <dt className="text-muted-foreground">Latest release</dt>
                <dd>
                  {p.current ? (
                    <>
                      <a href={p.current_url ?? undefined} target="_blank" rel="noreferrer" className="font-mono text-xs hover:underline">
                        {p.current}
                      </a>
                      {p.current_date && <span className="ml-2 text-xs text-muted-foreground">{timeAgo(p.current_date)}</span>}
                    </>
                  ) : (
                    <span className="text-xs text-muted-foreground">None yet</span>
                  )}
                </dd>
                <dt className="text-muted-foreground">Unreleased</dt>
                <dd className="text-xs">
                  {p.unreleased_commits == null
                    ? '—'
                    : p.unreleased_commits === 0
                      ? `Nothing new on ${p.target} since ${p.current}`
                      : `${p.unreleased_commits} commit${p.unreleased_commits === 1 ? '' : 's'} on ${p.target} since ${p.current}`}
                </dd>
              </dl>

              {p.parseable ? (
                <div role="group" aria-label="Version bump" className="grid grid-cols-3 gap-2">
                  {KINDS.map(({ kind: k, label }) => (
                    <button
                      key={k}
                      type="button"
                      aria-pressed={!useCustom && kind === k}
                      onClick={() => {
                        setKind(k)
                        setCustom('')
                      }}
                      className={cn(
                        'flex flex-col items-center rounded-lg border px-2 py-2 text-xs',
                        !useCustom && kind === k ? 'border-primary bg-primary/10' : 'hover:bg-muted',
                      )}
                    >
                      <span className="text-muted-foreground">{label}</span>
                      <span className="font-mono text-sm font-medium">{p.candidates[k]}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">
                  <code>{p.current}</code> isn't a plain x.y.z version, so it can't be bumped automatically. Enter the
                  version below.
                </p>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="rel-version">{p.parseable ? 'Or a custom version' : 'Version'}</Label>
                  <Input
                    id="rel-version"
                    className="font-mono text-xs"
                    placeholder={p.parseable ? 'optional' : 'e.g. 3.5.0.web'}
                    value={custom}
                    onChange={(e) => setCustom(e.target.value)}
                    required={!p.parseable}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="rel-target">Target branch</Label>
                  <Input
                    id="rel-target"
                    required
                    className="font-mono text-xs"
                    value={target}
                    onChange={(e) => setTarget(e.target.value)}
                  />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="rel-name">Release name</Label>
                <Input id="rel-name" placeholder={tag || 'defaults to the version'} value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="flex gap-6 text-sm">
                <label className="flex items-center gap-2">
                  <Checkbox checked={draft} onCheckedChange={setDraft} /> Draft
                </label>
                <label className="flex items-center gap-2">
                  <Checkbox checked={prerelease} onCheckedChange={setPrerelease} /> Pre-release
                </label>
              </div>
            </>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" disabled={create.isPending} onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            {target.trim() !== checkedTarget ? (
              <Button type="submit" variant="outline" disabled={!target.trim()}>
                Check {target.trim() || 'branch'}
              </Button>
            ) : (
              <Button
                type="submit"
                disabled={!p || p.managed_by_workflow || !tag || create.isPending || plan.isFetching}
              >
                <Tag />
                {create.isPending ? 'Creating…' : tag ? `Create ${tag}` : 'Create release'}
              </Button>
            )}
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
