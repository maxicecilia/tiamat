import { useQuery } from '@tanstack/react-query'
import { ExternalLink, GitPullRequest, Plus, RefreshCw, X } from 'lucide-react'
import { type FormEvent, useState, useSyncExternalStore } from 'react'
import { Button } from '@/components/ui/button'
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
import { api, type PendingCheck, type Project } from '@/lib/api'
import { timeAgo } from '@/lib/time'
import { cn } from '@/lib/utils'

/** A target ← origin branch pair: commits on `head` that aren't on `base` yet. */
export type BranchPair = { base: string; head: string }

const PRESETS: BranchPair[] = [
  { base: 'main', head: 'release' },
  { base: 'release', head: 'develop' },
]
const CUSTOM_KEY = 'tiamat-branch-pairs'

const same = (a: BranchPair, b: BranchPair) => a.base === b.base && a.head === b.head
const label = (p: BranchPair) => `${p.base} ← ${p.head}`

function loadCustom(): BranchPair[] {
  try {
    const raw = JSON.parse(localStorage.getItem(CUSTOM_KEY) ?? '[]')
    return Array.isArray(raw)
      ? raw.filter((p) => typeof p?.base === 'string' && typeof p?.head === 'string' && p.base && p.head)
      : []
  } catch {
    return []
  }
}

// Custom pairs are shared by every project row and kept in this browser.
let customPairs = loadCustom()
const listeners = new Set<() => void>()
function saveCustom(next: BranchPair[]) {
  customPairs = next
  localStorage.setItem(CUSTOM_KEY, JSON.stringify(next))
  listeners.forEach((l) => l())
}
const subscribe = (l: () => void) => {
  listeners.add(l)
  return () => listeners.delete(l)
}

function useCustomPairs() {
  const pairs = useSyncExternalStore(subscribe, () => customPairs)
  return {
    pairs,
    add: (p: BranchPair) => !pairs.some((x) => same(x, p)) && saveCustom([...pairs, p]),
    remove: (p: BranchPair) => saveCustom(pairs.filter((x) => !same(x, p))),
  }
}

type Props = {
  project: Project
  githubReady: boolean
  onCreatePr: (row: PendingCheck) => void
}

/** The expanded part of a Deploys row: pending commits for a chosen branch pair. */
export function PendingChanges({ project, githubReady, onCreatePr }: Props) {
  const own: BranchPair = { base: project.base_branch, head: project.head_branch }
  const custom = useCustomPairs()
  const [pair, setPair] = useState<BranchPair>(own)
  const [customOpen, setCustomOpen] = useState(false)

  const presets = [own, ...PRESETS].filter((p, i, all) => all.findIndex((x) => same(x, p)) === i)
  const customs = custom.pairs.filter((p) => !presets.some((x) => same(x, p)))

  // Same key as the row's own check on the Deploys page, so the two share results.
  const query = useQuery({
    queryKey: ['pending', project.id, pair.base, pair.head],
    queryFn: async () => (await api.checkPending({ project_ids: [project.id], ...pair }))[0],
    enabled: githubReady,
    staleTime: 60_000,
  })
  const check = query.data
  const fetching = query.isFetching

  const pill = (p: BranchPair, removable = false) => (
    <span
      key={label(p)}
      className={cn(
        'inline-flex items-center rounded-full border font-mono text-xs',
        same(p, pair) ? 'bg-primary text-primary-foreground' : 'hover:bg-muted',
      )}
    >
      <button aria-pressed={same(p, pair)} onClick={() => setPair(p)} className="px-3 py-0.5">
        {label(p)}
      </button>
      {removable && (
        <button
          aria-label={`Remove ${label(p)}`}
          className="-ml-1.5 pr-2 opacity-70 hover:opacity-100"
          onClick={() => {
            custom.remove(p)
            if (same(p, pair)) setPair(own)
          }}
        >
          <X className="size-3" />
        </button>
      )}
    </span>
  )

  return (
    <div className="flex flex-col gap-3 py-2">
      <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label={`Branches for ${project.name}`}>
        <span className="mr-1 text-xs text-muted-foreground">Target ← origin</span>
        {presets.map((p) => pill(p))}
        {customs.map((p) => pill(p, true))}
        <Button size="xs" variant="ghost" onClick={() => setCustomOpen(true)}>
          <Plus />
          Custom
        </Button>
        <Button
          size="icon-xs"
          variant="ghost"
          className="ml-auto"
          aria-label="Check again"
          title="Check again"
          disabled={fetching || !githubReady}
          onClick={() => query.refetch()}
        >
          <RefreshCw className={cn(fetching && 'animate-spin')} />
        </Button>
      </div>

      {!githubReady ? (
        <p className="text-xs text-muted-foreground">Set GITHUB_TOKEN to compare branches.</p>
      ) : query.isLoading ? (
        <Skeleton className="h-12 w-full" />
      ) : query.error ? (
        <p className="text-xs text-destructive">Could not check branches: {query.error.message}</p>
      ) : !check ? null : check.error ? (
        <p className="text-xs text-destructive">{check.error}</p>
      ) : !check.ahead_by ? (
        <p className="text-xs text-muted-foreground">
          Up to date: nothing on <code>{check.head}</code> that isn't on <code>{check.base}</code>.
        </p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <span className="font-medium">
              {check.ahead_by} commit{check.ahead_by === 1 ? '' : 's'} pending
            </span>
            {check.compare_url && (
              <a href={check.compare_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:underline">
                Full diff <ExternalLink className="size-3" aria-hidden />
              </a>
            )}
            <span className="ml-auto">
              {check.open_pr_url ? (
                <a href={check.open_pr_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:underline">
                  PR open <ExternalLink className="size-3" aria-hidden />
                </a>
              ) : (
                <Button size="xs" variant="outline" onClick={() => onCreatePr(check)}>
                  <GitPullRequest />
                  Create PR
                </Button>
              )}
            </span>
          </div>
          <ul className="flex flex-col gap-1">
            {check.commits.map((c) => (
              <li key={c.sha} className="flex items-baseline gap-3 text-xs">
                {c.url ? (
                  <a href={c.url} target="_blank" rel="noreferrer" className="font-mono text-muted-foreground hover:underline">
                    {c.sha}
                  </a>
                ) : (
                  <span className="font-mono text-muted-foreground">{c.sha}</span>
                )}
                <span className="min-w-0 flex-1 truncate">{c.message}</span>
                <span className="shrink-0 text-muted-foreground">{c.author}</span>
                {c.date && <span className="shrink-0 text-muted-foreground">{timeAgo(c.date)}</span>}
              </li>
            ))}
          </ul>
          {check.ahead_by > check.commits.length && (
            <p className="text-xs text-muted-foreground">
              Showing the latest {check.commits.length} of {check.ahead_by}.
            </p>
          )}
        </>
      )}

      <CustomPairDialog
        open={customOpen}
        onOpenChange={setCustomOpen}
        onSubmit={(p) => {
          if (!presets.some((x) => same(x, p))) custom.add(p)
          setPair(p)
        }}
      />
    </div>
  )
}

function CustomPairDialog({
  open,
  onOpenChange,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (p: BranchPair) => void
}) {
  const [base, setBase] = useState('')
  const [head, setHead] = useState('')
  const ok = base.trim() && head.trim() && base.trim() !== head.trim()

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!ok) return
    onSubmit({ base: base.trim(), head: head.trim() })
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>Compare other branches</DialogTitle>
            <DialogDescription>
              Shows the commits on the origin branch that aren't on the target yet. The pair is kept for every project.
            </DialogDescription>
          </DialogHeader>
          <div className="flex items-end gap-2">
            <div className="flex flex-1 flex-col gap-1">
              <Label htmlFor="pair-base" className="text-xs">
                Target
              </Label>
              <Input id="pair-base" className="font-mono text-xs" placeholder="main" value={base} onChange={(e) => setBase(e.target.value)} autoFocus />
            </div>
            <span className="pb-2 text-muted-foreground">←</span>
            <div className="flex flex-1 flex-col gap-1">
              <Label htmlFor="pair-head" className="text-xs">
                Origin
              </Label>
              <Input id="pair-head" className="font-mono text-xs" placeholder="hotfix" value={head} onChange={(e) => setHead(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!ok}>
              Compare
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
