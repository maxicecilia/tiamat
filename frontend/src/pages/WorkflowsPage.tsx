import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Lock, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { PresetDialog } from '@/components/PresetDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { api, type WorkflowPreset } from '@/lib/api'

export default function WorkflowsPage() {
  const qc = useQueryClient()
  const { data, error } = useQuery({ queryKey: ['workflow-presets'], queryFn: api.workflowPresets })
  const [editing, setEditing] = useState<WorkflowPreset | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogKey, setDialogKey] = useState(0)
  const [deleting, setDeleting] = useState<WorkflowPreset | null>(null)

  const remove = useMutation({
    mutationFn: (p: WorkflowPreset) => api.deletePreset(p.id),
    onSuccess: (_, p) => {
      qc.invalidateQueries({ queryKey: ['workflow-presets'] })
      toast.success(`Deleted ${p.environment} (${p.version})`)
    },
    onError: (e) => toast.error(e.message),
  })

  const open = (p: WorkflowPreset | null) => {
    setEditing(p)
    setDialogKey((k) => k + 1)
    setDialogOpen(true)
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Workflows</h2>
          <p className="text-sm text-muted-foreground">
            Deploy environments and the GitHub Actions workflow each one runs, per workflow version.
          </p>
        </div>
        <Button onClick={() => open(null)}>
          <Plus /> New preset
        </Button>
      </header>
      <Card>
        <CardHeader>
          <CardTitle>Deploy presets</CardTitle>
        </CardHeader>
        <CardContent>
          {error ? (
            <p className="text-sm text-destructive">Could not load presets: {error.message}</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Environment</TableHead>
                  <TableHead>Version</TableHead>
                  <TableHead>Workflow file</TableHead>
                  <TableHead>Branch</TableHead>
                  <TableHead>Inputs</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead className="w-20" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium">{p.environment}</TableCell>
                    <TableCell>
                      <Badge variant={p.version === 'v2' ? 'default' : 'secondary'}>{p.version}</Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs">{p.workflow_file}</TableCell>
                    <TableCell className="font-mono text-xs">
                      <span className="inline-flex items-center gap-1">
                        {p.branch ?? 'project base'}
                        {p.lock_branch && (
                          <Lock className="size-3 text-muted-foreground" aria-label="Branch locked" />
                        )}
                      </span>
                    </TableCell>
                    <TableCell className="font-mono text-xs whitespace-normal text-muted-foreground">
                      {Object.keys(p.inputs).length
                        ? Object.entries(p.inputs).map(([k, v]) => `${k}=${v}`).join(', ')
                        : '—'}
                    </TableCell>
                    <TableCell className="whitespace-normal text-muted-foreground">{p.description}</TableCell>
                    <TableCell>
                      <div className="flex justify-end">
                        <Button variant="ghost" size="icon-sm" aria-label={`Edit ${p.environment} ${p.version}`} onClick={() => open(p)}>
                          <Pencil />
                        </Button>
                        <Button variant="ghost" size="icon-sm" aria-label={`Delete ${p.environment} ${p.version}`} onClick={() => setDeleting(p)}>
                          <Trash2 />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <PresetDialog key={dialogKey} open={dialogOpen} onOpenChange={setDialogOpen} preset={editing} />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Delete the ${deleting?.environment} (${deleting?.version}) preset?`}
        description="Projects on this workflow version will no longer be able to deploy to this environment from the dashboard."
        onConfirm={() => deleting && remove.mutate(deleting)}
      />
    </div>
  )
}
