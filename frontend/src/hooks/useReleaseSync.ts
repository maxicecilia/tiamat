import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { toast } from 'sonner'
import { api, type SyncRun } from '@/lib/api'

function report(run: SyncRun) {
  const errors = Object.entries(run.details.errors ?? {})
  const summary = `${run.details.added ?? 0} new releases, ${run.details.lead_times ?? 0} lead times computed`
  if (run.status === 'error') {
    toast.error('Release refresh failed', { description: errors.map(([k, e]) => `${k}: ${e}`).slice(0, 3).join('; ') })
  } else if (errors.length) {
    toast.warning(`Refreshed with ${errors.length} error(s)`, {
      description: `${summary}. ${errors
        .slice(0, 3)
        .map(([k, e]) => `${k}: ${e}`)
        .join('; ')}`,
    })
  } else {
    toast.success('Release data refreshed', { description: summary })
  }
}

/** Start a background release sync and follow it until it finishes. */
export function useReleaseSync() {
  const qc = useQueryClient()
  const latest = useQuery({
    queryKey: ['release-sync'],
    queryFn: api.latestReleaseSync,
    refetchInterval: (q) => (q.state.data?.status === 'running' ? 2000 : false),
  })
  // Whichever run this tab last saw running (started here, in another tab, or before a
  // reload) is reported, and the data refreshed, when it finishes.
  const runningId = useRef<number | null>(null)

  useEffect(() => {
    const run = latest.data
    if (!run) return
    if (run.status === 'running') {
      runningId.current = run.id
    } else if (run.id === runningId.current) {
      runningId.current = null
      qc.invalidateQueries({ queryKey: ['deploys'] })
      qc.invalidateQueries({ queryKey: ['metrics'] })
      report(run)
    }
  }, [latest.data, qc])

  const start = useMutation({
    mutationFn: (months: number) => api.syncReleases(months),
    onSuccess: async (run) => {
      // Drop any in-flight poll that could overwrite the new run with the previous one.
      await qc.cancelQueries({ queryKey: ['release-sync'] })
      qc.setQueryData(['release-sync'], run)
    },
    onError: (e) => toast.error(e.message),
  })

  return {
    latest: latest.data,
    running: latest.data?.status === 'running' || start.isPending,
    start: (months = 6) => start.mutate(months),
  }
}
