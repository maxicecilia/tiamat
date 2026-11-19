import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, X } from 'lucide-react'
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { api, type WorkflowPreset, type WorkflowPresetInput } from '@/lib/api'

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  preset?: WorkflowPreset | null
}

type Row = { key: string; value: string }

export function PresetDialog({ open, onOpenChange, preset }: Props) {
  const qc = useQueryClient()
  // The parent remounts this component (via `key`) each time it opens, so state starts fresh.
  const [environment, setEnvironment] = useState(preset?.environment ?? '')
  const [version, setVersion] = useState<WorkflowPresetInput['version']>(preset?.version ?? 'v1')
  const [workflowFile, setWorkflowFile] = useState(preset?.workflow_file ?? '')
  const [branch, setBranch] = useState(preset?.branch ?? '')
  const [description, setDescription] = useState(preset?.description ?? '')
  const [lockBranch, setLockBranch] = useState(preset?.lock_branch ?? /prod/i.test(preset?.environment ?? ''))
  const [inputs, setInputs] = useState<Row[]>(() =>
    Object.entries(preset?.inputs ?? {}).map(([key, value]) => ({ key, value })),
  )

  const save = useMutation({
    mutationFn: (data: WorkflowPresetInput) =>
      preset ? api.updatePreset(preset.id, data) : api.createPreset(data),
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: ['workflow-presets'] })
      toast.success(`Saved ${p.environment} (${p.version})`)
      onOpenChange(false)
    },
    onError: (e) => toast.error(e.message),
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate({
      environment: environment.trim(),
      version,
      workflow_file: workflowFile.trim(),
      branch: branch.trim() || null,
      description: description.trim() || null,
      lock_branch: lockBranch,
      inputs: Object.fromEntries(
        inputs.filter((r) => r.key.trim()).map((r) => [r.key.trim(), r.value]),
      ),
    })
  }

  const setRow = (i: number, patch: Partial<Row>) =>
    setInputs((rows) => rows.map((r, j) => (j === i ? { ...r, ...patch } : r)))

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>{preset ? 'Edit deploy preset' : 'New deploy preset'}</DialogTitle>
            <DialogDescription>
              The GitHub Actions workflow that runs when a project with this workflow version deploys to
              this environment.
            </DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="env">Environment</Label>
              <Input id="env" required placeholder="staging" value={environment} onChange={(e) => setEnvironment(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Workflow version</Label>
              <Select value={version} onValueChange={(v) => setVersion(v as WorkflowPresetInput['version'])}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="v1">v1</SelectItem>
                  <SelectItem value="v2">v2</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="wf">Workflow file</Label>
              <Input id="wf" required placeholder="deploy-staging.yml" className="font-mono text-xs" value={workflowFile} onChange={(e) => setWorkflowFile(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="branch">Branch</Label>
              <Input id="branch" placeholder="project default" className="font-mono text-xs" value={branch} onChange={(e) => setBranch(e.target.value)} />
            </div>
          </div>
          <label className="flex items-start gap-2 text-sm">
            <Checkbox checked={lockBranch} onCheckedChange={setLockBranch} className="mt-0.5" />
            <span>
              Lock the branch
              <span className="block text-xs text-muted-foreground">
                Deploys must use this branch (or the project's base branch when it's empty). Recommended for prod.
              </span>
            </span>
          </label>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="desc">Description</Label>
            <Input id="desc" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <Label>Workflow inputs</Label>
              <Button type="button" variant="ghost" size="xs" onClick={() => setInputs((r) => [...r, { key: '', value: '' }])}>
                <Plus /> Add input
              </Button>
            </div>
            {inputs.length === 0 && <p className="text-xs text-muted-foreground">No inputs: only the branch is sent.</p>}
            {inputs.map((row, i) => (
              <div key={i} className="flex gap-2">
                <Input aria-label="Input name" placeholder="name" className="font-mono text-xs" value={row.key} onChange={(e) => setRow(i, { key: e.target.value })} />
                <Input aria-label="Input value" placeholder="value" className="font-mono text-xs" value={row.value} onChange={(e) => setRow(i, { value: e.target.value })} />
                <Button type="button" variant="ghost" size="icon" aria-label="Remove input" onClick={() => setInputs((r) => r.filter((_, j) => j !== i))}>
                  <X />
                </Button>
              </div>
            ))}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? 'Saving…' : 'Save preset'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
