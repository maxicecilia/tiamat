import { X } from 'lucide-react'
import { useId, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'

type Props = {
  value: string[]
  onChange: (tags: string[]) => void
  suggestions?: string[]
  id?: string
  placeholder?: string
}

/** Chip-style tag editor. Enter or comma adds a tag; Backspace on empty input removes the last. */
export function TagInput({ value, onChange, suggestions = [], id, placeholder = 'Add a tag and press Enter' }: Props) {
  const [draft, setDraft] = useState('')
  const listId = useId()

  const add = (raw: string) => {
    const fresh = raw
      .split(',')
      .map((t) => t.trim().toLowerCase())
      .filter((t) => t && !value.includes(t))
    if (fresh.length) onChange([...value, ...new Set(fresh)])
    setDraft('')
  }

  return (
    <div className="flex flex-col gap-2">
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {value.map((t) => (
            <Badge key={t} variant="secondary" className="gap-1 pr-1">
              {t}
              <button
                type="button"
                aria-label={`Remove ${t}`}
                onClick={() => onChange(value.filter((x) => x !== t))}
                className="rounded-sm hover:bg-foreground/10"
              >
                <X className="size-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
      <Input
        id={id}
        list={listId}
        value={draft}
        placeholder={placeholder}
        onChange={(e) => {
          const v = e.target.value
          if (v.includes(',')) add(v)
          else setDraft(v)
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            add(draft)
          } else if (e.key === 'Backspace' && !draft && value.length) {
            onChange(value.slice(0, -1))
          }
        }}
        onBlur={() => draft && add(draft)}
      />
      <datalist id={listId}>
        {suggestions
          .filter((s) => !value.includes(s))
          .map((s) => (
            <option key={s} value={s} />
          ))}
      </datalist>
    </div>
  )
}
