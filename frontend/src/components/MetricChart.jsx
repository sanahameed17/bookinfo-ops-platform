import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useApi } from '../hooks/useApi'
import { SERIES_COLORS, fmtClock, seriesToRows, shortPod } from '../utils/format'
import { EmptyState, ErrorState, Skeleton } from './ui'

/**
 * Line chart for a HistoryResponse ({series:[{name, points:[{t,v}]}], unit}).
 * Gaps (null samples) are drawn as gaps - they are not filled with zero.
 */
export function HistoryChart({ history, height = 260, threshold }) {
  const series = history?.series || []
  if (!series.length) {
    return (
      <EmptyState title="No samples in this time range">
        Prometheus returned an empty result for this query. This is shown as “no data”, not as zero.
      </EmptyState>
    )
  }
  const rows = seriesToRows(series)
  const unit = history.unit
  const fmt = (v) => (v === null || v === undefined ? 'no data' : unit === 'cores' ? `${v.toFixed(4)} cores` : `${v.toFixed(1)} MiB`)
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="t" tickFormatter={fmtClock} tick={{ fontSize: 11, fill: '#64748b' }} minTickGap={40} />
          <YAxis
            tick={{ fontSize: 11, fill: '#64748b' }}
            width={56}
            tickFormatter={(v) => (unit === 'cores' ? v.toFixed(3) : v.toFixed(0))}
            label={{ value: unit, angle: -90, position: 'insideLeft', fontSize: 11, fill: '#94a3b8' }}
          />
          <Tooltip
            formatter={(v, name) => [fmt(v), shortPod(name)]}
            labelFormatter={(t) => new Date(t).toLocaleString()}
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />
          <Legend formatter={(name) => <span className="text-xs text-slate-600">{shortPod(name)}</span>} />
          {series.map((s, i) => (
            <Line
              key={s.name}
              type="monotone"
              dataKey={s.name}
              stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
              strokeWidth={1.8}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
          ))}
          {threshold !== undefined && (
            <Line dataKey={() => threshold} name="threshold" stroke="#e11d48" strokeDasharray="5 4" dot={false} legendType="none" isAnimationActive={false} />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Loads a history and renders it (with its own loading / error states). */
export function LoadedHistoryChart({ loader, deps, height, threshold }) {
  const { data, error, loading, reload } = useApi(loader, deps)
  if (loading && !data) return <Skeleton className="w-full" style={{ height }} />
  if (error && !data) return <ErrorState error={error} onRetry={reload} compact />
  return (
    <div>
      <HistoryChart history={data} height={height} threshold={threshold} />
      {data?.query && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-slate-500 hover:text-slate-700">PromQL</summary>
          <code className="mt-1 block overflow-x-auto rounded bg-slate-900 px-3 py-2 font-mono text-[11px] text-slate-100">{data.query}</code>
        </details>
      )}
    </div>
  )
}
