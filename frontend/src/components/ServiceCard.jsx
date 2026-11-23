import { ArrowUpRight, Boxes, Cpu, MemoryStick, RotateCcw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { fmtCores, fmtMiB, timeAgo } from '../utils/format'
import { HealthBadge, Pill, StatusBadge, Value } from './ui'

const SERVICE_BLURB = {
  productpage: 'Front-end · Python',
  details: 'Book details · Ruby',
  reviews: 'Book reviews · Java',
  ratings: 'Star ratings · Node.js',
}

const metricWhy = (s) =>
  s.metrics_state === 'prometheus_unavailable' ? 'Prometheus unavailable' : 'Metric unavailable for at least one pod'

export default function ServiceCard({ service: s }) {
  const accent = { Healthy: 'bg-emerald-500', Degraded: 'bg-amber-500', Down: 'bg-rose-500' }[s.health] || 'bg-slate-400'
  return (
    <Link
      to={`/services/${encodeURIComponent(s.name)}`}
      aria-label={`Open details of the ${s.name} microservice`}
      data-testid={`service-card-${s.name}`}
      className="group relative flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
    >
      <span className={`absolute inset-x-0 top-0 h-1 ${accent}`} aria-hidden="true" />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold text-slate-900">{s.name}</h3>
          <p className="text-xs text-slate-500">{SERVICE_BLURB[s.name] || 'Kubernetes Service'}</p>
        </div>
        <ArrowUpRight className="h-4 w-4 shrink-0 text-slate-400 transition group-hover:text-indigo-600" aria-hidden="true" />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <HealthBadge health={s.health} />
        <StatusBadge status={s.status} />
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        <div>
          <dt className="flex items-center gap-1 text-xs text-slate-500"><Boxes className="h-3.5 w-3.5" aria-hidden="true" />Replicas</dt>
          <dd className="font-semibold tabular-nums text-slate-900">
            {s.ready_replicas}/{s.desired_replicas}
            <span className="ml-1 text-xs font-normal text-slate-500">· {s.pod_count} pod{s.pod_count === 1 ? '' : 's'}</span>
          </dd>
        </div>
        <div>
          <dt className="flex items-center gap-1 text-xs text-slate-500"><RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />Restarts</dt>
          <dd className={`font-semibold tabular-nums ${s.restart_count > 0 ? 'text-amber-700' : 'text-slate-900'}`}>{s.restart_count}</dd>
        </div>
        <div>
          <dt className="flex items-center gap-1 text-xs text-slate-500"><Cpu className="h-3.5 w-3.5" aria-hidden="true" />CPU</dt>
          <dd className="font-semibold tabular-nums text-slate-900"><Value value={s.cpu_cores} format={(v) => fmtCores(v, 4)} why={metricWhy(s)} /></dd>
        </div>
        <div>
          <dt className="flex items-center gap-1 text-xs text-slate-500"><MemoryStick className="h-3.5 w-3.5" aria-hidden="true" />Memory</dt>
          <dd className="font-semibold tabular-nums text-slate-900"><Value value={s.memory_mib} format={fmtMiB} why={metricWhy(s)} /></dd>
        </div>
      </dl>

      <div className="mt-4 flex flex-wrap items-center gap-1.5 border-t border-slate-100 pt-3">
        <span className="text-xs text-slate-500">{s.version_count} version{s.version_count === 1 ? '' : 's'}:</span>
        {s.versions.map((v) => (
          <Pill key={v} tone="indigo">{v}</Pill>
        ))}
        <span className="ml-auto text-[11px] text-slate-400">updated {timeAgo(s.updated_at)}</span>
      </div>
      {s.health !== 'Healthy' && <p className="mt-2 line-clamp-2 text-xs text-rose-700">{s.health_reason}</p>}
    </Link>
  )
}
