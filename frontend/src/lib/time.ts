import { parseDate } from '@/lib/api'

const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
const units: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 31_536_000],
  ['month', 2_592_000],
  ['week', 604_800],
  ['day', 86_400],
  ['hour', 3_600],
  ['minute', 60],
]

export function timeAgo(value: string, now = Date.now()): string {
  const seconds = Math.round((parseDate(value).getTime() - now) / 1000)
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit)
  }
  return 'just now'
}

export function formatDateTime(value: string): string {
  return parseDate(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function duration(start: string, end: string | null, now = Date.now()): string {
  const ms = (end ? parseDate(end).getTime() : now) - parseDate(start).getTime()
  const s = Math.max(0, Math.round(ms / 1000))
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`
}
