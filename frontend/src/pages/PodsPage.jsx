import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { Card, ErrorState, Notice, PageHeader, Pill, Skeleton, Table, Value } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { fmtCores, fmtMiB, timeAgo } from '../utils/format'

export default function PodsPage() {
  const { data, error, reload } = useApi(() => api.pods())
  const [q, setQ] = useState('')
  const [service, setService] = useState('')
  const [onlyProblems, setOnlyProblems] = useState(false)
  const [sort, setSort] = useState('name')

  const rows = useMemo(() => {
    let pods = data?.pods || []
    if (service) pods = pods.filter((p) => (p.service || '(none)') === service)
    if (q) pods = pods.filter((p) => p.name.includes(q.toLowerCase()) || (p.node_name || '').includes(q.toLowerCase()))
    if (onlyProblems) pods = pods.filter((p) => !p.healthy)
    const key = { name: (p) => p.name, cpu: (p) => -(p.cpu_cores ?? -1), memory: (p) => -(p.memory_mib ?? -1), restarts: (p) => -p.restart_count }[sort]
    return [...pods].sort((a, b) => (key(a) < key(b) ? -1 : key(a) > key(b) ? 1 : 0))
  }, [data, q, service, onlyProblems, sort])

  const services = [...new Set((data?.pods || []).map((p) => p.service || '(none)'))].sort()

  return (
    <>
      <PageHeader title="Pods explorer" description="Every pod in the namespace with its owner Deployment, version, node, readiness, restarts and current resource usage." />
      {data?.meta?.prometheus_available === false && <div className="mb-4"><Notice tone="slate">Prometheus unavailable – CPU and memory columns show “—”.</Notice></div>}
      <Card
        title={data ? `${rows.length} of ${data.pods.length} pods` : 'Pods'}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <label className="sr-only" htmlFor="pod-search">Search pods</label>
            <input id="pod-search" className="input w-44" placeholder="Search pod or node" value={q} onChange={(e) => setQ(e.target.value)} />
            <label className="sr-only" htmlFor="pod-service">Service</label>
            <select id="pod-service" className="input" value={service} onChange={(e) => setService(e.target.value)}>
              <option value="">All services</option>
              {services.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <label className="sr-only" htmlFor="pod-sort">Sort</label>
            <select id="pod-sort" className="input" value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="name">Sort: name</option>
              <option value="cpu">Sort: CPU</option>
              <option value="memory">Sort: memory</option>
              <option value="restarts">Sort: restarts</option>
            </select>
            <label className="flex items-center gap-1.5 text-xs text-slate-600">
              <input type="checkbox" checked={onlyProblems} onChange={(e) => setOnlyProblems(e.target.checked)} className="rounded border-slate-300 text-indigo-600" />
              Only unhealthy
            </label>
          </div>
        }
      >
        {error && !data ? (
          <ErrorState error={error} onRetry={reload} />
        ) : !data ? (
          <Skeleton className="h-64" />
        ) : (
          <Table
            rowKey={(p) => p.name}
            rows={rows}
            empty="No pods match the filter"
            columns={[
              { key: 'name', label: 'Pod', render: (p) => <span className="font-mono text-xs">{p.name}</span> },
              { key: 'service', label: 'Service', render: (p) => (p.service ? <Link className="text-indigo-600 hover:underline" to={`/services/${p.service}`}>{p.service}</Link> : <span className="text-slate-400">none</span>) },
              { key: 'deployment', label: 'Deployment', render: (p) => <span className="font-mono text-xs">{p.deployment || '—'}</span> },
              { key: 'version', label: 'Version', render: (p) => (p.version ? <Pill tone="indigo">{p.version}</Pill> : '—') },
              {
                key: 'phase',
                label: 'Status',
                render: (p) => (
                  <div>
                    <span className={p.healthy ? 'text-emerald-700' : 'font-semibold text-rose-700'}>{p.phase}</span>
                    <span className="ml-1 text-xs text-slate-500">{p.ready_containers}/{p.total_containers}</span>
                    {p.problems.map((x) => <p key={x} className="text-[11px] text-rose-700">{x}</p>)}
                  </div>
                ),
              },
              { key: 'cpu', label: 'CPU', className: 'tabular-nums text-xs', render: (p) => <Value value={p.cpu_cores} format={(v) => fmtCores(v, 4)} /> },
              { key: 'mem', label: 'Memory', className: 'tabular-nums text-xs', render: (p) => <Value value={p.memory_mib} format={fmtMiB} /> },
              { key: 'restart_count', label: 'Restarts', className: 'tabular-nums' },
              { key: 'node_name', label: 'Node', render: (p) => <span className="font-mono text-xs">{p.node_name || '—'}</span> },
              { key: 'pod_ip', label: 'IP', render: (p) => <span className="font-mono text-xs">{p.pod_ip || '—'}</span> },
              { key: 'age', label: 'Started', render: (p) => <span className="text-xs">{timeAgo(p.start_time)}</span> },
            ]}
          />
        )}
      </Card>
    </>
  )
}
