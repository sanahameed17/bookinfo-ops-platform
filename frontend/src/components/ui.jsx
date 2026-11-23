import { AlertTriangle, Inbox, RefreshCw } from 'lucide-react'
import { HEALTH_STYLE, STATUS_STYLE } from '../utils/format'

export function Card({ title, subtitle, actions, children, className = '', bodyClass = 'p-5' }) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-5 py-3.5">
          <div>
            {title && <h2 className="text-sm font-semibold text-slate-900">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  )
}

export function PageHeader({ title, description, children }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-slate-500">{description}</p>}
      </div>
      {children}
    </div>
  )
}

export function HealthBadge({ health, className = '' }) {
  const s = HEALTH_STYLE[health] || HEALTH_STYLE.Unknown
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${s.badge} ${className}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} aria-hidden="true" />
      {s.label}
    </span>
  )
}

export function StatusBadge({ status }) {
  const s = STATUS_STYLE[status] || STATUS_STYLE.metrics_unavailable
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${s.badge}`}>
      {s.label}
    </span>
  )
}

export function Pill({ children, tone = 'slate' }) {
  const tones = {
    slate: 'bg-slate-100 text-slate-700',
    indigo: 'bg-indigo-50 text-indigo-700',
    amber: 'bg-amber-50 text-amber-800',
    rose: 'bg-rose-50 text-rose-700',
    emerald: 'bg-emerald-50 text-emerald-700',
  }
  return <span className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>
}

export function Skeleton({ className = '', style }) {
  return <div className={`animate-pulse rounded-md bg-slate-200/70 ${className}`} style={style} aria-hidden="true" />
}

export function SkeletonCards({ count = 4, height = 'h-28' }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" role="status" aria-label="Loading">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className={height} />
      ))}
    </div>
  )
}

export function ErrorState({ error, onRetry, compact = false }) {
  const code = error?.code
  const hint =
    code === 'BACKEND_UNREACHABLE'
      ? 'Start the backend: cd backend; uvicorn app.main:app --port 8000'
      : code === 'PROMETHEUS_UNAVAILABLE'
        ? 'Start the Prometheus port-forward: .\\scripts\\start-port-forwards.ps1'
        : code === 'KUBERNETES_UNAVAILABLE'
          ? 'Check that Docker Desktop Kubernetes is running and K8S_CONTEXT is correct.'
          : null
  return (
    <div role="alert" className={`rounded-xl border border-rose-200 bg-rose-50/60 ${compact ? 'p-3' : 'p-5'}`}>
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-rose-600" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-rose-900">{error?.message || 'Something went wrong'}</p>
          {code && <p className="mt-0.5 font-mono text-xs text-rose-700">{code}{error?.status ? ` · HTTP ${error.status}` : ''}</p>}
          {hint && <p className="mt-2 text-xs text-rose-800">{hint}</p>}
          {error?.details?.available_contexts && (
            <p className="mt-1 text-xs text-rose-800">Available contexts: {error.details.available_contexts.join(', ')}</p>
          )}
        </div>
        {onRetry && (
          <button type="button" onClick={onRetry} className="btn-secondary shrink-0">
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" /> Retry
          </button>
        )}
      </div>
    </div>
  )
}

export function EmptyState({ title = 'No data', children, icon: Icon = Inbox }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 px-6 py-10 text-center">
      <Icon className="h-8 w-8 text-slate-400" aria-hidden="true" />
      <p className="mt-3 text-sm font-medium text-slate-700">{title}</p>
      {children && <div className="mt-1 max-w-md text-xs text-slate-500">{children}</div>}
    </div>
  )
}

export function Notice({ tone = 'amber', children }) {
  const tones = {
    amber: 'border-amber-200 bg-amber-50 text-amber-900',
    slate: 'border-slate-200 bg-slate-50 text-slate-700',
    rose: 'border-rose-200 bg-rose-50 text-rose-900',
    indigo: 'border-indigo-200 bg-indigo-50 text-indigo-900',
  }
  return <div className={`rounded-lg border px-3.5 py-2.5 text-sm ${tones[tone]}`}>{children}</div>
}

/** Shows a value or an explicit "no data" marker with a tooltip explaining why. */
export function Value({ value, format, why = 'No data from Prometheus' }) {
  if (value === null || value === undefined) {
    return (
      <span className="text-slate-400" title={why}>
        —<span className="sr-only"> ({why})</span>
      </span>
    )
  }
  return <span>{format ? format(value) : value}</span>
}

export function KV({ items }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
      {items.map(([k, v]) => (
        <div key={k} className="min-w-0">
          <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{k}</dt>
          <dd className="mt-0.5 break-words text-sm text-slate-900">{v ?? '—'}</dd>
        </div>
      ))}
    </dl>
  )
}

export function Table({ columns, rows, rowKey, empty = 'No rows', dense = false }) {
  if (!rows?.length) return <EmptyState title={empty} />
  return (
    <div className="-mx-5 overflow-x-auto">
      <table className="min-w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
            {columns.map((c) => (
              <th key={c.key} scope="col" className={`whitespace-nowrap px-5 py-2 font-medium ${c.className || ''}`}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r, i) => (
            <tr key={rowKey ? rowKey(r) : i} className="hover:bg-slate-50/70">
              {columns.map((c) => (
                <td key={c.key} className={`px-5 ${dense ? 'py-1.5' : 'py-2.5'} align-top ${c.className || ''}`}>
                  {c.render ? c.render(r) : r[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Segmented({ options, value, onChange, label }) {
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={`rounded-md px-2.5 py-1 text-xs font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
            value === o.value ? 'bg-indigo-600 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export const TIME_RANGES = [
  { value: 5, label: '5 min' },
  { value: 15, label: '15 min' },
  { value: 60, label: '60 min' },
]
