import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Pencil, Plus, Trash2, X } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { toast } from 'sonner'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { api } from '@/lib/api'

type Label = { id: number; name: string; project_count: number }

type LabelApi = {
  queryKey: string
  noun: string
  description: string
  list: () => Promise<Label[]>
  create: (name: string) => Promise<{ name: string }>
  rename: (id: number, name: string) => Promise<unknown>
  remove: (id: number) => Promise<void>
}

const TEAMS: LabelApi = {
  queryKey: 'teams',
  noun: 'team',
  description: 'Who owns a project. A project can belong to several teams.',
  list: api.teams,
  create: api.createTeam,
  rename: api.renameTeam,
  remove: api.deleteTeam,
}

const TAGS: LabelApi = {
  queryKey: 'tags',
  noun: 'tag',
  description: 'Free-form labels for grouping projects.',
  list: api.tags,
  create: (name) => api.createTag({ name }),
  rename: (id, name) => api.updateTag(id, { name }),
  remove: api.deleteTag,
}

export default function TagsPage() {
  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <header>
        <h2 className="text-lg font-semibold">Teams & tags</h2>
        <p className="text-sm text-muted-foreground">
          Labels for grouping projects. Both can also be set straight from a project.
        </p>
      </header>
      <LabelsCard config={TEAMS} />
      <LabelsCard config={TAGS} />
    </div>
  )
}

function LabelsCard({ config }: { config: LabelApi }) {
  const qc = useQueryClient()
  const { noun } = config
  const { data: tags, error } = useQuery({ queryKey: [config.queryKey], queryFn: config.list })
  const [newTag, setNewTag] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [draft, setDraft] = useState('')
  const [deleting, setDeleting] = useState<Label | null>(null)

  const refresh = () => {
    qc.invalidateQueries({ queryKey: [config.queryKey] })
    qc.invalidateQueries({ queryKey: ['projects'] })
    qc.invalidateQueries({ queryKey: ['deploys'] })
  }
  const create = useMutation({
    mutationFn: (name: string) => config.create(name),
    onSuccess: (t) => {
      refresh()
      setNewTag('')
      toast.success(`Added ${noun} ${t.name}`)
    },
    onError: (e) => toast.error(e.message),
  })
  const rename = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) => config.rename(id, name),
    onSuccess: () => {
      refresh()
      setEditingId(null)
    },
    onError: (e) => toast.error(e.message),
  })
  const remove = useMutation({
    mutationFn: (t: Label) => config.remove(t.id),
    onSuccess: (_, t) => {
      refresh()
      toast.success(`Deleted ${noun} ${t.name}`)
    },
    onError: (e) => toast.error(e.message),
  })

  const submitNew = (e: FormEvent) => {
    e.preventDefault()
    if (newTag.trim()) create.mutate(newTag.trim().toLowerCase())
  }

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center gap-3">
          <div className="mr-auto">
            <CardTitle className="capitalize">{noun}s</CardTitle>
            <CardDescription>{config.description}</CardDescription>
          </div>
          <form onSubmit={submitNew} className="flex gap-2">
            <Input aria-label={`New ${noun} name`} placeholder={`New ${noun}`} value={newTag} onChange={(e) => setNewTag(e.target.value)} className="w-44" />
            <Button type="submit" variant="outline" disabled={!newTag.trim() || create.isPending}>
              <Plus /> Add
            </Button>
          </form>
        </CardHeader>
        <CardContent>
          {error ? (
            <p className="text-sm text-destructive">Could not load {noun}s: {error.message}</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="capitalize">{noun}</TableHead>
                  <TableHead className="w-28 text-right">Projects</TableHead>
                  <TableHead className="w-24" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {tags?.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell>
                      {editingId === t.id ? (
                        <form
                          className="flex gap-1"
                          onSubmit={(e) => {
                            e.preventDefault()
                            rename.mutate({ id: t.id, name: draft.trim().toLowerCase() })
                          }}
                        >
                          <Input autoFocus aria-label={`${noun} name`} value={draft} onChange={(e) => setDraft(e.target.value)} className="h-7 w-48" />
                          <Button type="submit" variant="ghost" size="icon-sm" aria-label={`Save ${noun} name`}>
                            <Check />
                          </Button>
                          <Button type="button" variant="ghost" size="icon-sm" aria-label="Cancel rename" onClick={() => setEditingId(null)}>
                            <X />
                          </Button>
                        </form>
                      ) : (
                        <Badge variant="outline">{t.name}</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{t.project_count}</TableCell>
                    <TableCell>
                      <div className="flex justify-end">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={`Rename ${t.name}`}
                          onClick={() => {
                            setEditingId(t.id)
                            setDraft(t.name)
                          }}
                        >
                          <Pencil />
                        </Button>
                        <Button variant="ghost" size="icon-sm" aria-label={`Delete ${t.name}`} onClick={() => setDeleting(t)}>
                          <Trash2 />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {tags?.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={3} className="text-center text-muted-foreground">
                      No {noun}s yet.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Delete ${noun} ${deleting?.name}?`}
        description={`It will be removed from ${deleting?.project_count ?? 0} project(s).`}
        onConfirm={() => deleting && remove.mutate(deleting)}
      />
    </>
  )
}
