import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Star } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

type Props = { projectId: number; name: string; starred: boolean; className?: string }

/** Toggle a project's star; starred projects are listed first everywhere. */
export function StarButton({ projectId, name, starred, className }: Props) {
  const qc = useQueryClient()
  const toggle = useMutation({
    mutationFn: () => api.updateProject(projectId, { starred: !starred }),
    onSuccess: () => {
      // Not 'pending': that would re-run every branch comparison on GitHub.
      for (const key of ['projects', 'deploys', 'metrics']) {
        qc.invalidateQueries({ queryKey: [key] })
      }
    },
    onError: (e) => toast.error(e.message),
  })
  return (
    <button
      type="button"
      aria-pressed={starred}
      aria-label={starred ? `Unstar ${name}` : `Star ${name}`}
      title={starred ? 'Starred: shown first, pending changes checked live' : 'Star to show first (up to 5)'}
      disabled={toggle.isPending}
      onClick={(e) => {
        e.stopPropagation()
        toggle.mutate()
      }}
      className={cn(
        'inline-flex shrink-0 rounded-sm p-0.5 hover:text-foreground disabled:opacity-50',
        starred ? 'text-amber-500' : 'text-muted-foreground/50',
        className,
      )}
    >
      <Star className="size-4" fill={starred ? 'currentColor' : 'none'} aria-hidden />
    </button>
  )
}

/** A filter pill for "starred only" that sits beside the team pills. */
export function StarredFilter({ active, onChange }: { active: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={(e) => {
        e.preventDefault()
        onChange(!active)
      }}
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-3 py-0.5 text-xs',
        active ? 'bg-primary text-primary-foreground' : 'hover:bg-muted',
      )}
    >
      <Star className="size-3" fill={active ? 'currentColor' : 'none'} aria-hidden />
      starred
    </button>
  )
}
