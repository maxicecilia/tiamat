import { CircleCheck, CircleDashed, CircleHelp, CircleMinus, CircleX, LoaderCircle } from 'lucide-react'
import { ACTIVE_STATUSES } from '@/lib/api'
import { formatDateTime, timeAgo } from '@/lib/time'
import { cn } from '@/lib/utils'

const LABELS: Record<string, string> = {
  dispatching: 'Starting',
  dispatched: 'Waiting for run',
  queued: 'Queued',
  in_progress: 'Running',
  waiting: 'Waiting for approval',
  requested: 'Requested',
  pending: 'Pending',
  success: 'Succeeded',
  failure: 'Failed',
  cancelled: 'Cancelled',
  timed_out: 'Timed out',
  startup_failure: 'Failed to start',
  action_required: 'Action required',
  skipped: 'Skipped',
  neutral: 'Neutral',
  stale: 'Stale',
  error: 'Not triggered',
  unknown: 'Check GitHub',
  dismissed: 'Dismissed',
}

function statusLabel(status: string) {
  return LABELS[status] ?? status
}

type Props = {
  status: string
  className?: string
  /** When the deploy started; shown with the label. */
  at?: string | null
  /** Show only the icon; the label (and time) go in the tooltip. */
  iconOnly?: boolean
}

export function DeployStatus({ status, className, at, iconOnly }: Props) {
  const active = ACTIVE_STATUSES.has(status)
  const failed = ['failure', 'timed_out', 'startup_failure', 'error'].includes(status)
  const Icon = active
    ? status === 'queued' || status === 'dispatched'
      ? CircleDashed
      : LoaderCircle
    : status === 'success'
      ? CircleCheck
      : failed
        ? CircleX
        : status === 'unknown' || status === 'action_required'
          ? CircleHelp
          : CircleMinus
  const text = at ? `${statusLabel(status)} · ${timeAgo(at)}` : statusLabel(status)
  return (
    <span
      title={iconOnly ? (at ? `${text} (${formatDateTime(at)})` : text) : undefined}
      role={iconOnly ? 'img' : undefined}
      aria-label={iconOnly ? text : undefined}
      className={cn(
        'inline-flex items-center gap-1 text-xs font-medium',
        status === 'success' && 'text-emerald-600 dark:text-emerald-400',
        failed && 'text-red-600 dark:text-red-400',
        active && 'text-sky-600 dark:text-sky-400',
        !active && !failed && status !== 'success' && 'text-muted-foreground',
        className,
      )}
    >
      <Icon
        className={cn(iconOnly ? 'size-4' : 'size-3.5', active && Icon === LoaderCircle && 'animate-spin')}
        aria-hidden
      />
      {!iconOnly && statusLabel(status)}
    </span>
  )
}
