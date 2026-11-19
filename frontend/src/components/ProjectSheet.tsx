import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { TagInput } from '@/components/TagInput'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import { api, type Project, type ProjectInput } from '@/lib/api'

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Project to edit; omit to create a new one. */
  project?: Project | null
}

const empty: ProjectInput = {
  repo: '',
  name: '',
  teams: [],
  workflow_version: 'v1',
  base_branch: 'main',
  head_branch: 'release',
  description: null,
  deploy_environments: null,
  tags: [],
}

function toForm(p: Project): ProjectInput {
  return {
    repo: p.repo,
    name: p.name,
    teams: p.teams.map((t) => t.name),
    workflow_version: p.workflow_version,
    base_branch: p.base_branch,
    head_branch: p.head_branch,
    description: p.description,
    deploy_environments: p.deploy_environments,
    tags: p.tags.map((t) => t.name),
  }
}

export function ProjectSheet({ open, onOpenChange, project }: Props) {
  const qc = useQueryClient()
  // The parent remounts this component (via `key`) each time it opens, so state starts fresh.
  const [form, setForm] = useState<ProjectInput>(() => (project ? toForm(project) : empty))
  const isEdit = !!project

  const { data: tags } = useQuery({ queryKey: ['tags'], queryFn: api.tags })
  const { data: teams } = useQuery({ queryKey: ['teams'], queryFn: api.teams })
  const { data: presets, error: presetsError } = useQuery({
    queryKey: ['workflow-presets'],
    queryFn: api.workflowPresets,
  })
  const environments = useMemo(
    () => [
      ...new Set(
        (presets ?? []).filter((p) => p.version === form.workflow_version).map((p) => p.environment),
      ),
    ],
    [presets, form.workflow_version],
  )

  const save = useMutation({
    mutationFn: (data: ProjectInput) => {
      const payload = {
        ...data,
        // Clearing the display name falls back to the repo name.
        name: data.name?.trim() || data.repo.split('/')[1],
        // Drop environments that no longer have a preset for this workflow version.
        deploy_environments: presets ? normalizeEnvs(data.deploy_environments, environments) : data.deploy_environments,
      }
      return project ? api.updateProject(project.id, payload) : api.createProject(payload)
    },
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      qc.invalidateQueries({ queryKey: ['tags'] })
      qc.invalidateQueries({ queryKey: ['teams'] })
      qc.invalidateQueries({ queryKey: ['deploys'] })
      toast.success(isEdit ? `Saved ${p.name}` : `Added ${p.name}`)
      onOpenChange(false)
    },
    onError: (e) => toast.error(e.message),
  })

  const set = <K extends keyof ProjectInput>(key: K, value: ProjectInput[K]) =>
    setForm((f) => ({ ...f, [key]: value }))

  const allEnvs = form.deploy_environments === null
  const toggleEnv = (env: string, on: boolean) => {
    const current = (form.deploy_environments ?? environments).filter((e) => environments.includes(e))
    const next = on ? [...new Set([...current, env])] : current.filter((e) => e !== env)
    set('deploy_environments', normalizeEnvs(next, environments))
  }

  const changeVersion = (version: ProjectInput['workflow_version']) => {
    // Keep the selected environments that also exist for the new version; otherwise reset to all.
    const nextEnvs = [...new Set((presets ?? []).filter((p) => p.version === version).map((p) => p.environment))]
    const kept = form.deploy_environments?.filter((e) => nextEnvs.includes(e))
    setForm((f) => ({
      ...f,
      workflow_version: version,
      deploy_environments: kept && kept.length ? normalizeEnvs(kept, nextEnvs) : null,
    }))
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate(form)
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <form onSubmit={submit} className="flex h-full flex-col">
          <SheetHeader>
            <SheetTitle>{isEdit ? `Edit ${project.name}` : 'New project'}</SheetTitle>
            <SheetDescription>
              {isEdit ? project.repo : 'Add a GitHub repository for Tiamat to manage.'}
            </SheetDescription>
          </SheetHeader>

          <div className="flex flex-1 flex-col gap-5 px-4">
            <Field label="Repository" htmlFor="repo" hint="org/name, as on GitHub">
              <Input
                id="repo"
                required
                pattern="[^/\s]+/[^/\s]+"
                placeholder="my-org/my-service"
                value={form.repo}
                disabled={isEdit}
                onChange={(e) => set('repo', e.target.value.trim())}
              />
            </Field>

            <Field label="Display name" htmlFor="name">
              <Input
                id="name"
                placeholder={form.repo.split('/')[1] || 'defaults to repo name'}
                value={form.name ?? ''}
                onChange={(e) => set('name', e.target.value)}
              />
            </Field>

            <Field label="Teams" htmlFor="teams" hint="A project can belong to several teams.">
              <TagInput
                id="teams"
                placeholder="Add a team and press Enter"
                value={form.teams}
                onChange={(t) => set('teams', t)}
                suggestions={teams?.map((t) => t.name)}
              />
            </Field>

            <Field label="Tags" htmlFor="tags">
              <TagInput
                id="tags"
                value={form.tags}
                onChange={(t) => set('tags', t)}
                suggestions={tags?.map((t) => t.name)}
              />
            </Field>

            <Field label="Description" htmlFor="description">
              <Textarea
                id="description"
                rows={2}
                value={form.description ?? ''}
                onChange={(e) => set('description', e.target.value || null)}
              />
            </Field>

            <fieldset className="flex flex-col gap-4 rounded-lg border p-4">
              <legend className="px-1 text-sm font-medium">Release workflow</legend>
              <Field
                label="Workflow version"
                htmlFor="workflow-version"
                hint={
                  form.workflow_version === 'v2'
                    ? 'v2: release.<env>.yml creates the release itself and only takes the branch.'
                    : 'v1: classic deploy workflows; releases are created with bump.'
                }
              >
                <Select
                  value={form.workflow_version}
                  onValueChange={(v) => changeVersion(v as ProjectInput['workflow_version'])}
                >
                  <SelectTrigger id="workflow-version" aria-label="Workflow version" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="v1">v1</SelectItem>
                    <SelectItem value="v2">v2</SelectItem>
                  </SelectContent>
                </Select>
              </Field>

              <div className="grid grid-cols-2 gap-3">
                <Field label="Base branch" htmlFor="base">
                  <Input
                    id="base"
                    required
                    value={form.base_branch}
                    onChange={(e) => set('base_branch', e.target.value.trim())}
                  />
                </Field>
                <Field label="Head branch" htmlFor="head">
                  <Input
                    id="head"
                    required
                    value={form.head_branch}
                    onChange={(e) => set('head_branch', e.target.value.trim())}
                  />
                </Field>
              </div>

              <div role="group" aria-labelledby="deploy-envs-label" className="flex flex-col gap-2">
                <Label id="deploy-envs-label">Deploy environments</Label>
                {presetsError ? (
                  <p className="text-xs text-destructive">Could not load presets: {presetsError.message}</p>
                ) : !presets ? (
                  <p className="text-xs text-muted-foreground">Loading environments…</p>
                ) : environments.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    No {form.workflow_version} presets yet. Add them in Settings → Workflows.
                  </p>
                ) : (
                  <div className="flex flex-wrap gap-4">
                    {environments.map((env) => (
                      <label key={env} className="flex items-center gap-2 text-sm">
                        <Checkbox
                          checked={allEnvs || !!form.deploy_environments?.includes(env)}
                          onCheckedChange={(c) => toggleEnv(env, c)}
                        />
                        {env}
                      </label>
                    ))}
                  </div>
                )}
              </div>
            </fieldset>
          </div>

          <SheetFooter className="flex-row justify-end">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? 'Saving…' : isEdit ? 'Save changes' : 'Add project'}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  )
}

/** `null` means every environment; collapse to it when all are selected. */
function normalizeEnvs(selected: string[] | null, available: string[]): string[] | null {
  if (selected === null) return null
  const valid = selected.filter((e) => available.includes(e))
  return available.length > 0 && available.every((e) => valid.includes(e)) ? null : valid
}

function Field({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: string
  htmlFor?: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}
