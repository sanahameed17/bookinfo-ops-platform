import { CheckCircle2, CircleAlert } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api/client'
import { LoadedHistoryChart } from '../components/MetricChart'
import { Card, ErrorState, PageHeader, Segmented, Skeleton, StatusBadge, Table, TIME_RANGES, Value } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { fmtCores, fmtMiB } from '../utils/format'

export default function MonitoringPage() {
  const [minutes, setMinutes] = useState(15)
  const status = useApi(() => api.status())
  const pods = useApi(() => api.pods())
  const restarts = useApi(() => api.restarts())
  const st = status.data

  return (
    <>
      <PageHeader title="Resource monitoring" description="CPU (cores) and memory working set (MiB) from Prometheus, and the deterministic anomaly check.">
        <Segmented label="Time range" options={TIME_RANGES} value={minutes} onChange={setMinutes} />
      </PageHeader>

      <div className="space-y-6">
        <Card title="Anomaly status" subtitle={st ? `Thresholds: CPU > ${st.thresholds.cpu_cores} cores, memory > ${st.thresholds.memory_mib} MiB per pod` : 'Deterministic check'} actions={st && <StatusBadge status={st.status} />}>
          {status.error && !st ? (
            <ErrorState error={status.error} onRetry={status.reload} />
          ) : !st ? (
            <Skeleton className="h-16" />
          ) : (
            <div className="space-y-2 text-sm">
              {st.status === 'normal' && <p className="flex items-center gap-1.5 text-emerald-700"><CheckCircle2 className="h-4 w-4" />All {st.pods_evaluated} pods have data and are within the thresholds.</p>}
              {st.status === 'prometheus_unavailable' && <p className="text-slate-700">Prometheus is unavailable, so CPU and memory cannot be evaluated: {st.prometheus_error}</p>}
              {st.anomalies.map((a, i) => (
                <p key={i} className="flex items-start gap-1.5 text-rose-700"><CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />{a.message}{a.service ? ` (service ${a.service})` : ''}</p>
              ))}
              {st.missing_metrics.length > 0 && (
                <p className="text-amber-800">Missing samples: {st.missing_metrics.map((m) => `${m.pod} (${m.metric})`).join(', ')}</p>
              )}
            </div>
          )}
        </Card>

        <div className="grid gap-6 xl:grid-cols-2">
          <Card title="CPU usage per pod" subtitle="cores · rate(container_cpu_usage_seconds_total)">
            <LoadedHistoryChart loader={() => api.history('cpu', minutes)} deps={[minutes]} height={300} threshold={st?.thresholds.cpu_cores} />
          </Card>
          <Card title="Memory working set per pod" subtitle="MiB · container_memory_working_set_bytes">
            <LoadedHistoryChart loader={() => api.history('memory', minutes)} deps={[minutes]} height={300} threshold={st?.thresholds.memory_mib} />
          </Card>
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <Card title="Current pod usage" subtitle="Instant query; “—” = no sample (not zero)">
            {pods.error && !pods.data ? (
              <ErrorState error={pods.error} onRetry={pods.reload} compact />
            ) : !pods.data ? (
              <Skeleton className="h-48" />
            ) : (
              <Table
                dense
                rowKey={(p) => p.name}
                rows={[...pods.data.pods].sort((a, b) => (b.cpu_cores ?? -1) - (a.cpu_cores ?? -1))}
                columns={[
                  { key: 'name', label: 'Pod', render: (p) => <span className="font-mono text-xs">{p.name}</span> },
                  { key: 'cpu', label: 'CPU', className: 'tabular-nums text-xs', render: (p) => <Value value={p.cpu_cores} format={(v) => fmtCores(v, 4)} /> },
                  { key: 'mem', label: 'Memory', className: 'tabular-nums text-xs', render: (p) => <Value value={p.memory_mib} format={fmtMiB} /> },
                ]}
              />
            )}
          </Card>
          <Card title="Container restarts" subtitle="kube-state-metrics (Prometheus) and Kubernetes API">
            {restarts.error && !restarts.data ? (
              <ErrorState error={restarts.error} onRetry={restarts.reload} compact />
            ) : !restarts.data ? (
              <Skeleton className="h-48" />
            ) : (
              <>
                {!restarts.data.prometheus.available && <p className="mb-2 text-xs text-slate-500">kube-state-metrics not available: {restarts.data.prometheus.error}. Showing Kubernetes API values.</p>}
                <Table
                  dense
                  rowKey={(r) => `${r.pod}/${r.container}`}
                  rows={restarts.data.kubernetes.items.filter((r) => r.restarts > 0).sort((a, b) => b.restarts - a.restarts)}
                  empty="No container has restarted"
                  columns={[
                    { key: 'pod', label: 'Pod', render: (r) => <span className="font-mono text-xs">{r.pod}</span> },
                    { key: 'container', label: 'Container', className: 'text-xs' },
                    { key: 'restarts', label: 'Restarts', className: 'tabular-nums font-semibold text-amber-800' },
                    { key: 'reason', label: 'Last exit', render: (r) => <span className="text-xs">{r.last_terminated_reason || '—'}</span> },
                  ]}
                />
              </>
            )}
          </Card>
        </div>
      </div>
    </>
  )
}
