import { useMutation, useQueryClient } from '@tanstack/react-query'
import { GitPullRequest } from 'lucide-react'
import { useState } from 'react'
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
import { api, type PendingCheck, type PullRequestsResponse } from '@/lib/api'

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  rows: PendingCheck[]
  slackConfigured: boolean
  onDone: (res: PullRequestsResponse) => void
}

export function CreatePrsDialog({ open, onOpenChange, rows, slackConfigured, onDone }: Props) {
  const qc = useQueryClient()
  const [notify, setNotify] = useState(slackConfigured)

  const create = useMutation({
    // Send exactly the branches shown in this dialog.
    mutationFn: () =>
      api.createPullRequests({
        targets: rows.map((r) => ({ project_id: r.project_id, base: r.base, head: r.head })),
        notify_slack: notify,
      }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['pending'] })
      const created = res.results.filter((r) => r.status === 'created').length
      const existing = res.results.filter((r) => r.status === 'exists').length
      const failed = res.results.filter((r) => r.status === 'error')
      const slackFailed = res.slack.sent.some((s) => !s.ok)
      const parts = [
        `${created} created`,
        existing && `${existing} already open`,
        res.slack.sent.length > 0 && (slackFailed ? 'Slack message failed' : 'Slack notified'),
      ].filter(Boolean)
      if (failed.length) {
        toast.error(`${failed.length} PR(s) failed`, {
          description: failed.map((f) => `${f.name}: ${f.error}`).join('\n'),
        })
      } else {
        toast.success('Pull requests done', { description: parts.join(' · ') })
      }
      onDone(res)
      onOpenChange(false)
    },
    onError: (e) => {
      // The request may still have reached GitHub: re-check before letting anyone retry.
      qc.invalidateQueries({ queryKey: ['pending'] })
      toast.error(e.message, { description: 'Some PRs may have been created. The list was checked again.' })
    },
  })

  const fe = rows.filter((r) => r.frontend).length
  const be = rows.length - fe

  return (
    <Dialog open={open} onOpenChange={(o) => (o || !create.isPending) && onOpenChange(o)}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            Create {rows.length} pull request{rows.length === 1 ? '' : 's'}
          </DialogTitle>
          <DialogDescription>
            Opens a PR on GitHub from the head branch into the base branch for each project, titled like the CLI's{' '}
            <code>createpr</code>.
          </DialogDescription>
        </DialogHeader>

        <ul className="max-h-60 divide-y overflow-y-auto rounded-md border text-sm">
          {rows.map((r) => (
            <li key={r.project_id} className="flex items-center justify-between gap-3 px-3 py-2">
              <div className="min-w-0">
                <div className="truncate font-medium">{r.name}</div>
                <div className="font-mono text-xs text-muted-foreground">
                  {r.head} → {r.base}
                </div>
              </div>
              <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                {r.ahead_by} commit{r.ahead_by === 1 ? '' : 's'}
              </span>
            </li>
          ))}
        </ul>

        <label className="flex items-start gap-2 text-sm">
          <Checkbox
            checked={notify}
            disabled={!slackConfigured || create.isPending}
            onCheckedChange={setNotify}
            className="mt-0.5"
          />
          <span>
            Announce new PRs on Slack
            <span className="block text-xs text-muted-foreground">
              {slackConfigured
                ? `Tags ${[be && 'backend developers', fe && 'frontend developers'].filter(Boolean).join(' and ')} in the default channel, like the CLI. PRs that were already open aren't announced again.`
                : 'Slack is not configured (set SLACK_BOT_TOKEN or SLACK_WEBHOOK_URL).'}
            </span>
          </span>
        </label>

        <DialogFooter>
          <Button variant="outline" disabled={create.isPending} onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => create.mutate()} disabled={create.isPending || rows.length === 0}>
            <GitPullRequest />
            {create.isPending ? 'Creating…' : `Create ${rows.length} PR${rows.length === 1 ? '' : 's'}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
