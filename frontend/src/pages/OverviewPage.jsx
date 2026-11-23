import { AlertTriangle, Boxes, CheckCircle2, Cpu, Layers, MemoryStick, PlayCircle, RotateCcw, ServerCog } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { LoadedHistoryChart } from '../components/MetricChart'
import ServiceCard from '../components/ServiceCard'
import { Card, ErrorState, Notice, PageHeader, Segmented, SkeletonCards, StatusBadge, TIME_RANGES } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { fmtCores, fmtMiB, fmtPct, isNum } from '../utils/format'

function Stat({ label, value, sub, icon: Icon, tone = 'slate' }) {
  const tones = {
    slate: 'bg-slate-100 text-slate-600',
    indigo: 'bg-indigo-50 text-indigo-600',
    emerald: 'bg-emerald-50 text-emerald-600',
    rose: 'bg-rose-50 text-rose-600',
    amber: 'bg-amber-50 text-amber-700',
  }
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-slate-500">{label}</p>
        <span className={`rounded-lg p-1.5 ${tones[tone]}`}><Icon className="h-4 w-4" aria-hidden="true" /></span>
      </div>
      <p className="mt-2 text-2xl font-semibold tabular-nums tracking-tight text-slate-900">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
    </div>
  )
}

export function OverviewStats({ overview: o }) {
  const t = o.totals
  const promDown = !o.prometheus.available
  const noData = promDown ? 'Prometheus unavailable' : 'no data'
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Stat label="Microservices" value={t.microservices} sub="Kubernetes Services" icon={Layers} tone="indigo" />
      <Stat label="Deployments" value={t.deployments} sub="workload versions" icon={ServerCog} tone="indigo" />
      <Stat label="Pods" value={t.pods} sub={`${o.cluster ? `${o.cluster.ready_nodes}/${o.cluster.nodes} nodes ready` : 'nodes unknown'}`} icon={Boxes} />
      <Stat label="Running pods" value={t.running_pods} sub={`of ${t.pods}`} icon={PlayCircle} tone="emerald" />
      <Stat label="Unhealthy pods" value={t.unhealthy_pods} sub="not Running or not Ready" icon={AlertTriangle} tone={t.unhealthy_pods ? 'rose' : 'emerald'} />
      <Stat label="Container restarts" value={t.container_restarts} sub="cumulative, all containers" icon={RotateCcw} tone={t.container_restarts ? 'amber' : 'slate'} />
      <Stat
        label="CPU usage"
        value={isNum(t.cpu_cores) ? fmtCores(t.cpu_cores) : '—'}
        sub={isNum(t.cpu_percent_of_cluster) ? `${fmtPct(t.cpu_percent_of_cluster)} of allocatable cluster CPU` : noData}
        icon={Cpu}
      />
      <Stat
        label="Memory working set"
        value={isNum(t.memory_mib) ? fmtMiB(t.memory_mib) : '—'}
        sub={isNum(t.memory_percent_of_cluster) ? `${fmtPct(t.memory_percent_of_cluster)} of allocatable cluster memory` : noData}
        icon={MemoryStick}
      />
    </div>
  )
}

export default function OverviewPage() {
  const overview = useApi(() => api.overview())
  const services = useApi(() => api.services())
  const config = useApi(() => api.config())
  const [minutes, setMinutes] = useState(15)
  const o = overview.data

  return (
    <>
      <PageHeader
        title="Overview"
        description="Live state of the Istio Bookinfo application from the Kubernetes API and Prometheus. Click a microservice to open its detail page."
      >
        {o && (
          <Link to="/monitoring" className="flex items-center gap-2 text-sm">
            <span className="text-slate-500">Anomaly status</span>
            <StatusBadge status={o.status} />
            {o.anomaly_count > 0 && <span className="text-xs text-rose-700">{o.anomaly_count} finding(s)</span>}
          </Link>
        )}
      </PageHeader>

      <div className="space-y-6">
        {o?.warnings?.length > 0 && (
          <div className="space-y-2">
            {o.warnings.map((w) => (
              <Notice key={w} tone={w.startsWith('Prometheus') ? 'slate' : 'amber'}>{w}</Notice>
            ))}
          </div>
        )}

        {overview.error && !o ? (
          <ErrorState error={overview.error} onRetry={overview.reload} />
        ) : !o ? (
          <SkeletonCards count={8} />
        ) : (
          <OverviewStats overview={o} />
        )}

        {/* ---- Microservices inventory: the main requirement, kept prominent ---- */}
        <Card
          title="Microservices"
          subtitle="Each card is one Kubernetes Service. Versions are its Deployments (e.g. reviews v1/v2/v3)."
          actions={<Link to="/services" className="text-xs font-medium text-indigo-600 hover:text-indigo-500">Inventory table →</Link>}
        >
          {services.error && !services.data ? (
            <ErrorState error={services.error} onRetry={services.reload} />
          ) : !services.data ? (
            <SkeletonCards count={4} height="h-56" />
          ) : services.data.services.length === 0 ? (
            <Notice tone="slate">No Services were found in this namespace.</Notice>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {services.data.services.map((s) => (
                <ServiceCard key={s.name} service={s} />
              ))}
            </div>
          )}
        </Card>

        <Card
          title="Resource monitoring"
          subtitle="Per-pod usage in the namespace (application + sidecar containers). Dashed red line = anomaly threshold."
          actions={<Segmented label="Time range" options={TIME_RANGES} value={minutes} onChange={setMinutes} />}
        >
          <div className="grid gap-6 xl:grid-cols-2">
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">CPU (cores)</h3>
              <LoadedHistoryChart loader={() => api.history('cpu', minutes)} deps={[minutes]} height={260} threshold={config.data?.cpu_threshold_cores} />
            </div>
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Memory working set (MiB)</h3>
              <LoadedHistoryChart loader={() => api.history('memory', minutes)} deps={[minutes]} height={260} threshold={config.data?.memory_threshold_mib} />
            </div>
          </div>
        </Card>

        {o && o.status === 'normal' && (
          <p className="flex items-center gap-1.5 text-xs text-emerald-700">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> Every running pod has CPU and memory data and is below the thresholds.
          </p>
        )}
      </div>
    </>
  )
}
