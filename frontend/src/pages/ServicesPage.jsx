import { Link } from 'react-router-dom'
import { api } from '../api/client'
import ServiceCard from '../components/ServiceCard'
import { Card, ErrorState, HealthBadge, Notice, PageHeader, Pill, SkeletonCards, StatusBadge, Table, Value } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { fmtCores, fmtMiB } from '../utils/format'

export default function ServicesPage() {
  const { data, error, reload } = useApi(() => api.services())

  return (
    <>
      <PageHeader
        title="Microservices inventory"
        description="Logical services (Kubernetes Services), their workload versions (Deployments) and pods, discovered through label selectors and owner references."
      />
      {data?.meta?.prometheus_available === false && (
        <div className="mb-4"><Notice tone="slate">Prometheus unavailable: CPU and memory are shown as “—”. {data.meta.prometheus_error}</Notice></div>
      )}
      {error && !data ? (
        <ErrorState error={error} onRetry={reload} />
      ) : !data ? (
        <SkeletonCards count={4} height="h-56" />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {data.services.map((s) => (
              <ServiceCard key={s.name} service={s} />
            ))}
          </div>
          <Card title="Inventory table" subtitle="Services → Deployments (versions) → Pods">
            <Table
              rowKey={(r) => r.name}
              rows={data.services}
              columns={[
                { key: 'name', label: 'Service', render: (r) => <Link className="font-medium text-indigo-600 hover:underline" to={`/services/${r.name}`}>{r.name}</Link> },
                { key: 'health', label: 'Health', render: (r) => <HealthBadge health={r.health} /> },
                { key: 'status', label: 'Status', render: (r) => <StatusBadge status={r.status} /> },
                { key: 'deployments', label: 'Deployments (versions)', render: (r) => <div className="flex flex-wrap gap-1">{r.deployments.map((d) => <Pill key={d} tone="indigo">{d}</Pill>)}</div> },
                { key: 'replicas', label: 'Ready / desired', className: 'tabular-nums', render: (r) => `${r.ready_replicas}/${r.desired_replicas}` },
                { key: 'pod_count', label: 'Pods', className: 'tabular-nums' },
                { key: 'cpu', label: 'CPU', className: 'tabular-nums', render: (r) => <Value value={r.cpu_cores} format={(v) => fmtCores(v, 4)} /> },
                { key: 'mem', label: 'Memory', className: 'tabular-nums', render: (r) => <Value value={r.memory_mib} format={fmtMiB} /> },
                { key: 'restart_count', label: 'Restarts', className: 'tabular-nums' },
              ]}
            />
          </Card>
        </div>
      )}
    </>
  )
}
