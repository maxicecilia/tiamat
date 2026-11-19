import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Lock, Rocket, TriangleAlert } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
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
import { api, type DeployTarget, type Project } from '@/lib/api'
import { cn } from '@/lib/utils'

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  project: Project
  target: DeployTarget
}

export function DeployDialog({ open, onOpenChange, project, target }: Props) {
  const qc = useQueryClient()
  // Remounted per open (via `key`), so this starts from the preset's default branch.
  const [branch, setBranch] = useState(target.branch)
  const isProd = /prod/i.test(target.environment)

  const deploy = useMutation({
    mutationFn: () =>
      api.deploy({
        project_id: project.id,
        environment: target.environment,
        branch: target.lock_branch ? target.branch : branch.trim() || null,
      }),
    onSuccess: (dep) => {
      qc.invalidateQueries({ queryKey: ['deploys'] })
      if (dep.status === 'dispatched' && dep.error) {
        toast.warning(`GitHub did not confirm the deploy of ${project.name}`, {
          description: 'Tiamat is looking for the run. Check GitHub before deploying again.',
        })
      } else if (dep.status === 'error') {
        toast.error(`${project.name} → ${target.environment} was not triggered`, { description: dep.error ?? undefined })
      } else {
        toast.success(`Deploying ${project.name} to ${target.environment}`, {
          description: dep.run_url ? 'Workflow run started on GitHub.' : 'Waiting for GitHub to start the run.',
        })
      }
      onOpenChange(false)
    },
    onError: (e) => toast.error(e.message),
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    deploy.mutate()
  }

  return (
    // While the dispatch request is in flight, closing would look like a cancel but isn't.
    <Dialog open={open} onOpenChange={(o) => (o || !deploy.isPending) && onOpenChange(o)}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>
              Deploy {project.name} to {target.environment}
            </DialogTitle>
            <DialogDescription>{target.description ?? project.repo}</DialogDescription>
          </DialogHeader>

          {isProd && (
            <div className="flex gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-300">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
              This triggers a production deploy on GitHub.
            </div>
          )}

          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
            <dt className="text-muted-foreground">Repository</dt>
            <dd className="font-mono text-xs leading-5">{project.repo}</dd>
            <dt className="text-muted-foreground">Workflow</dt>
            <dd className="flex items-center gap-2 font-mono text-xs leading-5">
              {target.workflow_file}
              <Badge variant={project.workflow_version === 'v2' ? 'default' : 'secondary'}>
                {project.workflow_version}
              </Badge>
            </dd>
            <dt className="text-muted-foreground">Inputs</dt>
            <dd className="font-mono text-xs leading-5">
              {Object.keys(target.inputs).length
                ? Object.entries(target.inputs).map(([k, v]) => `${k}=${v}`).join(', ')
                : 'none'}
            </dd>
          </dl>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="deploy-branch" className="flex items-center gap-1.5">
              Branch
              {target.lock_branch && <Lock className="size-3 text-muted-foreground" aria-hidden />}
            </Label>
            <Input
              id="deploy-branch"
              required
              readOnly={target.lock_branch}
              aria-describedby={target.lock_branch ? 'deploy-branch-locked' : undefined}
              className={cn('font-mono text-xs', target.lock_branch && 'bg-muted text-muted-foreground')}
              value={target.lock_branch ? target.branch : branch}
              onChange={(e) => setBranch(e.target.value)}
            />
            {target.lock_branch && (
              <p id="deploy-branch-locked" className="text-xs text-muted-foreground">
                {target.environment} deploys always use <code>{target.branch}</code>. You can unlock this in
                Settings → Workflows.
              </p>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={deploy.isPending}
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" variant={isProd ? 'destructive' : 'default'} disabled={deploy.isPending || !branch.trim()}>
              <Rocket />
              {deploy.isPending ? 'Triggering…' : `Deploy to ${target.environment}`}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
