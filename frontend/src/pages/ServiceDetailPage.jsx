import { ArrowLeft, ArrowRight, CheckCircle2, CircleAlert, GitBranch, Network } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { LoadedHistoryChart } from '../components/MetricChart'
import {
  Card,
  EmptyState,
  ErrorState,
  HealthBadge,
  KV,
  Notice,
  Pill,
  Segmented,
  Skeleton,
  SkeletonCards,
  StatusBadge,
  Table,
  TIME_RANGES,
  Value,
} from '../components/ui'
import { useApi } from '../hooks/useApi'
import { fmtCores, fmtMiB, fmtTime, timeAgo } from '../utils/format'

const SECTIONS = [
  ['overview', 'Overview'],
  ['workloads', 'Workloads'],
  ['metrics', 'Resource metrics'],
  ['health', 'Health & diagnostics'],
  ['related', 'Related resources'],
  ['events', 'Events'],
]

function QuickStat({ label, children }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-0.5 text-lg font-semibold tabular-nums text-slate-900">{children}</p>
    </div>
  )
}

function ResList({ obj }) {
  const entries = Object.entries(obj || {})
  if (!entries.length) return <span className="text-xs text-slate-400">not set</span>
  return <span className="font-mono text-xs">{entries.map(([k, v]) => `${k}=${v}`).join(', ')}</span>
}

function ProbeCell({ probe }) {
  if (!probe?.configured) return <span className="text-xs text-slate-400">not configured</span>
  return <span className="font-mono text-xs">{probe.handler}</span>
}

function ContainerState({ c }) {
  const bad = c.state_reason && c.state !== 'running'
  return (
    <span className={`text-xs ${bad ? 'font-semibold text-rose-700' : 'text-slate-700'}`}>
      {c.state}{c.state_reason ? ` (${c.state_reason})` : ''}
      {c.last_terminated_reason && <span className="block text-[11px] font-normal text-slate-500">last exit: {c.last_terminated_reason}</span>}
    </span>
  )
}

function WeightBar({ routes }) {
  const total = routes.reduce((a, r) => a + (r.weight ?? 0), 0) || 100
  const colors = ['bg-indigo-500', 'bg-cyan-500', 'bg-amber-500', 'bg-pink-500']
  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-slate-100">
        {routes.map((r, i) => (
          <div key={i} className={colors[i % colors.length]} style={{ width: `${((r.weight ?? (routes.length === 1 ? 100 : 0)) / total) * 100}%` }} />
        ))}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-3 text-xs text-slate-600">
        {routes.map((r, i) => (
          <span key={i} className="inline-flex items-center gap-1">
            <span className={`h-2 w-2 rounded-full ${colors[i % colors.length]}`} />
            {r.short_host}{r.subset ? `:${r.subset}` : ''} {r.weight != null ? `${r.weight}%` : routes.length === 1 ? '100%' : ''}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function ServiceDetailPage() {
  const { name } = useParams()
  const { data: d, error, loading, reload } = useApi(() => api.service(name), [name])
  const config = useApi(() => api.config())
  const [minutes, setMinutes] = useState(15)
  const [by, setBy] = useState('pod')

  const back = (
    <Link to="/" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-indigo-600">
      <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to dashboard
    </Link>
  )

  if (error && (!d || d.service?.name !== name)) {
    return (
      <div className="space-y-4">
        {back}
        <ErrorState error={error} onRetry={reload} />
        {error.details?.available_services && (
          <p className="text-sm text-slate-600">
            Available services:{' '}
            {error.details.available_services.map((s) => (
              <Link key={s} to={`/services/${s}`} className="mr-2 font-medium text-indigo-600 hover:underline">{s}</Link>
            ))}
          </p>
        )}
      </div>
    )
  }
  if (!d || (loading && d.service?.name !== name)) {
    return (
      <div className="space-y-4" role="status" aria-label="Loading service">
        {back}
        <Skeleton className="h-10 w-72" />
        <SkeletonCards count={4} height="h-20" />
        <Skeleton className="h-72" />
      </div>
    )
  }

  const s = d.summary
  const svc = d.service
  const diag = d.diagnostics
  const cpuT = config.data?.cpu_threshold_cores
  const memT = config.data?.memory_threshold_mib
  const containers = d.pods.flatMap((p) => p.containers.map((c) => ({ ...c, pod: p.name, version: p.version })))

  return (
    <div className="space-y-6">
      {back}

      {/* ---------------- header ---------------- */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{svc.name}</h1>
            <HealthBadge health={s.health} />
            <StatusBadge status={s.status} />
          </div>
          <p className="mt-1 text-sm text-slate-500">
            {s.health_reason} · namespace <span className="font-mono">{svc.namespace}</span> · updated {timeAgo(d.meta.generated_at)}
          </p>
        </div>
        <nav aria-label="Sections" className="flex flex-wrap gap-1">
          {SECTIONS.map(([id, label]) => (
            <a key={id} href={`#${id}`} className="rounded-md px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-white hover:text-indigo-600">{label}</a>
          ))}
        </nav>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <QuickStat label="Ready / desired">{s.ready_replicas}/{s.desired_replicas}</QuickStat>
        <QuickStat label="Pods">{s.ready_pods}/{s.pod_count} ready</QuickStat>
        <QuickStat label="Versions">{s.versions.join(', ') || '—'}</QuickStat>
        <QuickStat label="CPU"><Value value={s.cpu_cores} format={(v) => fmtCores(v, 4)} /></QuickStat>
        <QuickStat label="Memory"><Value value={s.memory_mib} format={fmtMiB} /></QuickStat>
        <QuickStat label="Restarts">{s.restart_count}</QuickStat>
      </div>

      {!d.metrics.available && <Notice tone="slate">Prometheus unavailable – metrics are not shown. {d.metrics.error}</Notice>}

      {/* ---------------- A. overview ---------------- */}
      <div id="overview" className="scroll-mt-24">
      <Card title="Service overview" subtitle="Kubernetes Service object">
        <KV
          items={[
            ['Service name', svc.name],
            ['Namespace', svc.namespace],
            ['Type', svc.type],
            ['ClusterIP', <span className="font-mono" key="ip">{svc.cluster_ip}</span>],
            ['Selector', <ResList key="sel" obj={svc.selector} />],
            ['Ports', svc.ports.map((p) => `${p.name ? `${p.name} ` : ''}${p.port}→${p.target_port}/${p.protocol}`).join(', ')],
            ['Created', fmtTime(svc.created_at)],
            ['Health', <HealthBadge key="h" health={s.health} />],
          ]}
        />
      </Card>
      </div>

      {/* ---------------- B. workloads ---------------- */}
      <div id="workloads" className="scroll-mt-24 space-y-4">
        <Card title="Workloads" subtitle={`${d.deployments.length} Deployment(s) select by ${Object.entries(svc.selector).map(([k, v]) => `${k}=${v}`).join(',')}`}>
          {d.deployments.length === 0 ? (
            <EmptyState title="No Deployment matches this Service's selector" />
          ) : (
            <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
              {d.deployments.map((dep) => (
                <div key={dep.name} className="rounded-lg border border-slate-200 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-mono text-sm font-semibold text-slate-900">{dep.name}</p>
                    <Pill tone="indigo">{dep.version}</Pill>
                  </div>
                  <p className={`mt-1 text-sm tabular-nums ${dep.ready_replicas < dep.desired_replicas ? 'font-semibold text-rose-700' : 'text-slate-700'}`}>
                    {dep.ready_replicas}/{dep.desired_replicas} ready · {dep.available_replicas} available
                  </p>
                  <p className="mt-2 break-all font-mono text-[11px] text-slate-500">{dep.images.join(', ')}</p>
                  <div className="mt-3 text-xs text-slate-600">
                    <p className="font-medium text-slate-500">ReplicaSets</p>
                    {dep.replicasets.map((r) => (
                      <p key={r.name} className="font-mono">
                        {r.name} <span className="text-slate-400">rev {r.revision ?? '?'} · {r.ready_replicas}/{r.desired_replicas}</span>
                      </p>
                    ))}
                    <p className="mt-2 font-medium text-slate-500">Pods</p>
                    {dep.pods.length ? dep.pods.map((p) => <p key={p} className="font-mono">{p}</p>) : <p className="text-slate-400">none</p>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Pods" subtitle="Status, placement and containers of every pod of this service">
          <Table
            rowKey={(p) => p.name}
            rows={d.pods}
            empty="No pods match this service"
            columns={[
              { key: 'name', label: 'Pod', render: (p) => <span className="font-mono text-xs">{p.name}</span> },
              { key: 'version', label: 'Version', render: (p) => (p.version ? <Pill tone="indigo">{p.version}</Pill> : '—') },
              { key: 'phase', label: 'Status', render: (p) => <span className={p.healthy ? 'text-emerald-700' : 'font-semibold text-rose-700'}>{p.phase}{p.ready ? '' : ' · not ready'}</span> },
              { key: 'ready', label: 'Ready', className: 'tabular-nums', render: (p) => `${p.ready_containers}/${p.total_containers}` },
              { key: 'pod_ip', label: 'Pod IP', render: (p) => <span className="font-mono text-xs">{p.pod_ip || '—'}</span> },
              { key: 'node_name', label: 'Node', render: (p) => <span className="font-mono text-xs">{p.node_name || '—'}</span> },
              { key: 'containers', label: 'Containers', render: (p) => <span className="text-xs">{p.containers.map((c) => c.name).join(', ')}</span> },
              { key: 'restart_count', label: 'Restarts', className: 'tabular-nums' },
              { key: 'age', label: 'Started', render: (p) => <span className="text-xs">{timeAgo(p.start_time)}</span> },
            ]}
          />
        </Card>
      </div>

      {/* ---------------- C. metrics ---------------- */}
      <div id="metrics" className="scroll-mt-24 space-y-4">
        <Card
          title="Resource metrics"
          subtitle="Prometheus (cAdvisor). CPU = rate of container_cpu_usage_seconds_total; memory = container_memory_working_set_bytes."
          actions={
            <>
              <Segmented label="Group by" options={[{ value: 'pod', label: 'Per pod' }, { value: 'container', label: 'Per container' }]} value={by} onChange={setBy} />
              <Segmented label="Time range" options={TIME_RANGES} value={minutes} onChange={setMinutes} />
            </>
          }
        >
          <div className="grid gap-6 xl:grid-cols-2">
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">CPU usage (cores)</h3>
              <LoadedHistoryChart loader={() => api.serviceHistory(name, 'cpu', minutes, by)} deps={[name, minutes, by]} height={250} threshold={by === 'pod' ? cpuT : undefined} />
            </div>
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Memory working set (MiB)</h3>
              <LoadedHistoryChart loader={() => api.serviceHistory(name, 'memory', minutes, by)} deps={[name, minutes, by]} height={250} threshold={by === 'pod' ? memT : undefined} />
            </div>
          </div>
        </Card>

        <Card title="Per-container metrics, restarts, requests and limits" subtitle={d.metrics.container_metrics_available ? 'Current values' : 'Container metrics unavailable'}>
          <Table
            rowKey={(c) => `${c.pod}/${c.name}`}
            rows={containers}
            dense
            columns={[
              { key: 'pod', label: 'Pod', render: (c) => <span className="font-mono text-xs">{c.pod}</span> },
              { key: 'name', label: 'Container', render: (c) => <span className="text-xs">{c.name}{c.is_sidecar && <span className="ml-1 text-slate-400">(sidecar)</span>}</span> },
              { key: 'image', label: 'Image', render: (c) => <span className="break-all font-mono text-[11px] text-slate-600">{c.image}</span> },
              { key: 'cpu', label: 'CPU', className: 'tabular-nums text-xs', render: (c) => <Value value={c.cpu_cores} format={(v) => fmtCores(v, 4)} /> },
              { key: 'mem', label: 'Memory', className: 'tabular-nums text-xs', render: (c) => <Value value={c.memory_mib} format={fmtMiB} /> },
              { key: 'restart_count', label: 'Restarts', className: 'tabular-nums text-xs' },
              { key: 'requests', label: 'Requests', render: (c) => <ResList obj={c.requests} /> },
              { key: 'limits', label: 'Limits', render: (c) => <ResList obj={c.limits} /> },
            ]}
          />
          {!diag.resources_configured && (
            <p className="mt-3 text-xs text-slate-500">The application containers have no CPU/memory requests or limits (the Bookinfo sample does not set them), so utilisation “% of request” cannot be calculated.</p>
          )}
        </Card>
      </div>

      {/* ---------------- D. health ---------------- */}
      <div id="health" className="scroll-mt-24">
        <Card title="Health and diagnostics" subtitle="Deterministic checks - no AI involved" actions={<StatusBadge status={diag.status.status} />}>
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="space-y-4">
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Anomalies</h3>
                {diag.status.anomalies.length === 0 ? (
                  <p className="mt-1 flex items-center gap-1.5 text-sm text-emerald-700"><CheckCircle2 className="h-4 w-4" /> None (CPU &gt; {diag.status.thresholds.cpu_cores} cores, memory &gt; {diag.status.thresholds.memory_mib} MiB, pod status)</p>
                ) : (
                  <ul className="mt-1 space-y-1">
                    {diag.status.anomalies.map((a, i) => (
                      <li key={i} className="flex items-start gap-1.5 text-sm text-rose-700"><CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />{a.message}</li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Missing or unavailable metrics</h3>
                {!diag.status.prometheus_available ? (
                  <p className="mt-1 text-sm text-slate-700">Prometheus unavailable – CPU/memory could not be evaluated.</p>
                ) : diag.status.missing_metrics.length === 0 ? (
                  <p className="mt-1 text-sm text-slate-600">All running pods have CPU and memory samples.</p>
                ) : (
                  <ul className="mt-1 text-sm text-amber-800">
                    {diag.status.missing_metrics.map((m, i) => <li key={i}>{m.pod}: no {m.metric} sample</li>)}
                  </ul>
                )}
              </div>
              <KV
                items={[
                  ['Failed / pending pods', diag.failed_or_pending_pods.join(', ') || 'none'],
                  ['CrashLoopBackOff', diag.crashloop_pods.join(', ') || 'none'],
                  ['ImagePullBackOff / ErrImagePull', diag.image_pull_problems.join(', ') || 'none'],
                  ['Not ready pods', diag.not_ready_pods.join(', ') || 'none'],
                ]}
              />
            </div>
            <div className="space-y-4">
              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Readiness and liveness probes</h3>
                <Table
                  dense
                  rowKey={(c) => `${c.pod}/${c.name}`}
                  rows={containers}
                  columns={[
                    { key: 'c', label: 'Container', render: (c) => <span className="text-xs">{c.name} <span className="text-slate-400">· {c.version || c.pod}</span></span> },
                    { key: 'ready', label: 'Ready', render: (c) => (c.ready ? <span className="text-xs text-emerald-700">yes</span> : <span className="text-xs font-semibold text-rose-700">no</span>) },
                    { key: 'state', label: 'State', render: (c) => <ContainerState c={c} /> },
                    { key: 'rp', label: 'Readiness', render: (c) => <ProbeCell probe={c.readiness_probe} /> },
                    { key: 'lp', label: 'Liveness', render: (c) => <ProbeCell probe={c.liveness_probe} /> },
                  ]}
                />
              </div>
              <div>
                <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Recent warning events</h3>
                {diag.warning_events.length === 0 ? (
                  <p className="text-sm text-slate-600">No warning events (Kubernetes keeps events for about one hour).</p>
                ) : (
                  <ul className="space-y-1 text-sm">
                    {diag.warning_events.map((e, i) => (
                      <li key={i}><span className="font-semibold text-amber-800">{e.reason}</span> <span className="text-slate-600">{e.object_name}: {e.message}</span></li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* ---------------- E. related ---------------- */}
      <div id="related" className="scroll-mt-24 grid gap-4 xl:grid-cols-2">
        <Card title="Service dependencies" subtitle={d.dependencies.available ? `Source: ${d.dependencies.source}` : 'Only shown when telemetry or traces prove the calls'}>
          {!d.dependencies.available ? (
            <EmptyState title="Dependency information unavailable" icon={Network}>{d.dependencies.note}</EmptyState>
          ) : (
            <div className="space-y-3 text-sm">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Called by</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  {d.dependencies.called_by.length ? d.dependencies.called_by.map((n) => <DepLink key={n} name={n} />) : <span className="text-slate-400">nothing observed</span>}
                </div>
              </div>
              <div className="flex items-center gap-2 font-semibold text-slate-900"><ArrowRight className="h-4 w-4 text-slate-400" />{svc.name}<ArrowRight className="h-4 w-4 text-slate-400" /></div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Calls</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  {d.dependencies.calls.length ? d.dependencies.calls.map((n) => <DepLink key={n} name={n} />) : <span className="text-slate-400">nothing observed</span>}
                </div>
              </div>
              {d.dependencies.note && <p className="text-xs text-slate-500">{d.dependencies.note}</p>}
            </div>
          )}
        </Card>

        <Card title="Istio routing" subtitle="VirtualServices and DestinationRules that reference this service">
          {!d.istio.installed ? (
            <EmptyState title="Istio resources not available" icon={GitBranch}>{d.istio.note}</EmptyState>
          ) : (
            <div className="space-y-4">
              {d.istio.note && <p className="text-sm text-slate-600">{d.istio.note}</p>}
              {d.istio.virtual_services.map((vs) => (
                <div key={`${vs.namespace}/${vs.name}`} className="rounded-lg border border-slate-200 p-3">
                  <p className="text-sm font-medium text-slate-900">VirtualService <span className="font-mono">{vs.namespace}/{vs.name}</span></p>
                  <p className="mb-2 text-xs text-slate-500">hosts: {vs.hosts.join(', ')}{vs.gateways.length ? ` · gateways: ${vs.gateways.join(', ')}` : ''}</p>
                  <WeightBar routes={vs.routes} />
                </div>
              ))}
              {d.istio.destination_rules.map((dr) => (
                <div key={`${dr.namespace}/${dr.name}`} className="rounded-lg border border-slate-200 p-3">
                  <p className="text-sm font-medium text-slate-900">DestinationRule <span className="font-mono">{dr.namespace}/{dr.name}</span></p>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {dr.subsets.map((sub) => (
                      <Pill key={sub.name} tone="indigo">{sub.name}: {Object.entries(sub.labels).map(([k, v]) => `${k}=${v}`).join(',')}</Pill>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* ---------------- F. events ---------------- */}
      <div id="events" className="scroll-mt-24">
        <Card title="Kubernetes events" subtitle="Events of this service, its Deployments, ReplicaSets and Pods">
          <Table
            rowKey={(e) => `${e.object_name}-${e.reason}-${e.last_seen}`}
            rows={d.events}
            empty="No recent events (Kubernetes deletes events after about one hour)"
            columns={[
              { key: 'type', label: 'Type', render: (e) => <Pill tone={e.type === 'Warning' ? 'amber' : 'slate'}>{e.type}</Pill> },
              { key: 'reason', label: 'Reason', className: 'text-xs font-medium' },
              { key: 'object', label: 'Object', render: (e) => <span className="font-mono text-xs">{e.object_kind}/{e.object_name}</span> },
              { key: 'message', label: 'Message', className: 'text-xs text-slate-600' },
              { key: 'count', label: 'Count', className: 'tabular-nums text-xs' },
              { key: 'last_seen', label: 'Last seen', render: (e) => <span className="text-xs">{timeAgo(e.last_seen)}</span> },
            ]}
          />
        </Card>
      </div>
    </div>
  )
}

function DepLink({ name }) {
  // services of this namespace link to their page; mesh components (gateway, "unknown") do not
  const known = name && name !== 'unknown' && !name.includes('gateway') && !name.includes('.')
  return known ? (
    <Link to={`/services/${name}`} className="rounded-md bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100">{name}</Link>
  ) : (
    <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">{name}</span>
  )
}
