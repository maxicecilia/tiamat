import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  type TooltipContentProps,
  XAxis,
  YAxis,
} from 'recharts'
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent'
import type { MonthlyMetric } from '@/lib/api'

type NumericKey = 'deploys' | 'tickets' | 'change_failure_rate' | 'median_lead_time_days' | 'avg_lead_time_days'

type Props = {
  data: MonthlyMetric[]
  dataKey: NumericKey
  kind: 'bar' | 'line'
  /** Formats a value for the tooltip. */
  format: (v: number) => string
  /** Formats axis ticks (defaults to `format`). */
  axisFormat?: (v: number) => string
  /** Tooltip label for the series, e.g. "deploys". */
  label: string
  /** Shown in the tooltip under the value, e.g. sample size. */
  detail?: (row: MonthlyMetric) => string | null
  height?: number
}

const monthLabel = (month: string, short = true) =>
  new Date(`${month}-01T00:00:00Z`).toLocaleDateString(undefined, {
    month: short ? 'short' : 'long',
    year: short ? undefined : 'numeric',
    timeZone: 'UTC',
  })

const tick = { fill: 'var(--viz-muted)', fontSize: 11 }

/** One series over months: columns for counts, a line for trends. Single hue, no legend
 * (the card title names the series); the current, partial month is drawn lighter. */
export function MonthlyChart({ data, dataKey, kind, format, axisFormat = format, label, detail, height = 200 }: Props) {
  const rows = data.map((d) => ({ ...d, name: d.partial ? `${monthLabel(d.month)}*` : monthLabel(d.month) }))
  // Text alternative for screen readers: every month's value.
  const summary = `${label} by month: ${data
    .map((d) => `${monthLabel(d.month, false)}${d.partial ? ' (so far)' : ''}: ${d[dataKey] == null ? 'no data' : format(d[dataKey] as number)}`)
    .join('; ')}`
  const common = {
    data: rows,
    margin: { top: 8, right: 8, bottom: 0, left: 0 },
    accessibilityLayer: true,
  }
  const axes = (
    <>
      <CartesianGrid vertical={false} stroke="var(--viz-grid)" strokeWidth={1} />
      <XAxis dataKey="name" tick={tick} tickLine={false} axisLine={{ stroke: 'var(--viz-axis)' }} />
      <YAxis
        tick={tick}
        tickLine={false}
        axisLine={false}
        width={40}
        allowDecimals={dataKey !== 'deploys' && dataKey !== 'tickets'}
        tickFormatter={(v: number) => axisFormat(v)}
      />
      <Tooltip
        cursor={kind === 'bar' ? { fill: 'var(--viz-grid)', opacity: 0.5 } : { stroke: 'var(--viz-axis)' }}
        content={(p) => <ChartTooltip {...p} format={format} label={label} detail={detail} />}
      />
    </>
  )

  return (
    <div role="img" aria-label={summary}>
    <ResponsiveContainer width="100%" height={height}>
      {kind === 'bar' ? (
        <BarChart {...common} barCategoryGap="30%">
          {axes}
          <Bar dataKey={dataKey} maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {rows.map((r) => (
              <Cell key={r.month} fill="var(--viz-series-1)" fillOpacity={r.partial ? 0.45 : 1} />
            ))}
          </Bar>
        </BarChart>
      ) : (
        <LineChart {...common}>
          {axes}
          <Line
            dataKey={dataKey}
            stroke="var(--viz-series-1)"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            connectNulls
            isAnimationActive={false}
            dot={{ r: 4, fill: 'var(--viz-series-1)', stroke: 'var(--card)', strokeWidth: 2 }}
            activeDot={{ r: 5, fill: 'var(--viz-series-1)', stroke: 'var(--card)', strokeWidth: 2 }}
          />
        </LineChart>
      )}
    </ResponsiveContainer>
    </div>
  )
}

function ChartTooltip({
  active,
  payload,
  format,
  label,
  detail,
}: TooltipContentProps<ValueType, NameType> & {
  format: (v: number) => string
  label: string
  detail?: (row: MonthlyMetric) => string | null
}) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload as MonthlyMetric
  const value = typeof payload[0].value === 'number' ? payload[0].value : null
  const extra = detail?.(row)
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
      <div className="mb-1 text-muted-foreground">
        {monthLabel(row.month, false)}
        {row.partial && ' (so far)'}
      </div>
      <div className="flex items-center gap-2">
        <span className="h-0.5 w-3 rounded-full" style={{ background: 'var(--viz-series-1)' }} />
        <span className="font-semibold text-foreground tabular-nums">
          {value == null ? 'no data' : format(value)}
        </span>
        <span className="text-muted-foreground">{label}</span>
      </div>
      {extra && <div className="mt-1 text-muted-foreground">{extra}</div>}
    </div>
  )
}
