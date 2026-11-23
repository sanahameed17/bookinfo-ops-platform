import { CheckCircle2, XCircle } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { Card, ErrorState, KV, PageHeader, Skeleton } from '../components/ui'
import { useApi } from '../hooks/useApi'

function Ok({ ok, children }) {
  return (
    <span className={`inline-flex items-center gap-1.5 ${ok ? 'text-emerald-700' : 'text-rose-700'}`}>
      {ok ? <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> : <XCircle className="h-4 w-4" aria-hidden="true" />}
      {children}
    </span>
  )
}

export default function SettingsPage() {
  const config = useApi(() => api.config())
  const health = useApi(() => api.health())
  const c = config.data
  const h = health.data

  return (
    <>
      <PageHeader title="Settings and configuration" description="Values are read by the backend from environment variables (.env). Change them there and restart the backend. Secrets are never sent to the browser." />
      <div className="grid gap-6 xl:grid-cols-2">
        <Card title="Connectivity">
          {health.error && !h ? (
            <ErrorState error={health.error} onRetry={health.reload} />
          ) : !h ? (
            <Skeleton className="h-40" />
          ) : (
            <KV
              items={[
                ['Kubernetes API', <Ok key="k" ok={h.kubernetes.ok}>{h.kubernetes.ok ? `connected (${h.kubernetes.version})` : h.kubernetes.error}</Ok>],
                ['Context', <span key="c" className="font-mono">{h.kubernetes.context || '—'}</span>],
                ['API server', <span key="s" className="font-mono text-xs">{h.kubernetes.server || '—'}</span>],
                ['Prometheus', <Ok key="p" ok={h.prometheus.available}>{h.prometheus.available ? `connected (v${h.prometheus.version})` : h.prometheus.error}</Ok>],
                ['Prometheus URL', <span key="u" className="font-mono text-xs">{h.prometheus.url}</span>],
                ['AI agent LLM', <Ok key="l" ok={h.llm_configured}>{h.llm_configured ? 'API key configured' : 'not configured'}</Ok>],
              ]}
            />
          )}
        </Card>

        <Card title="Runtime configuration" subtitle="GET /api/config">
          {config.error && !c ? (
            <ErrorState error={config.error} onRetry={config.reload} />
          ) : !c ? (
            <Skeleton className="h-40" />
          ) : (
            <KV
              items={[
                ['Namespace (K8S_NAMESPACE)', c.namespace],
                ['Context (K8S_CONTEXT)', c.kubernetes_context],
                ['In-cluster config', String(c.kubernetes_in_cluster)],
                ['PROMETHEUS_URL', <span key="p" className="font-mono text-xs">{c.prometheus_url}</span>],
                ['Prometheus timeout', `${c.prometheus_timeout_seconds} s`],
                ['CPU rate window', c.prometheus_rate_window],
                ['JAEGER_URL', <span key="j" className="font-mono text-xs">{c.jaeger_url}</span>],
                ['CPU threshold', `${c.cpu_threshold_cores} cores`],
                ['Memory threshold', `${c.memory_threshold_mib} MiB`],
                ['LLM provider / model', `${c.llm_provider} / ${c.llm_model}`],
                ['LLM endpoint', c.llm_base_url_host],
              ]}
            />
          )}
        </Card>

        <Card title="Useful links" className="xl:col-span-2">
          <ul className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <li><a className="text-indigo-600 hover:underline" href="http://localhost:8000/docs" target="_blank" rel="noreferrer">Backend API docs (OpenAPI)</a><p className="text-xs text-slate-500">http://localhost:8000/docs</p></li>
            <li><a className="text-indigo-600 hover:underline" href="http://127.0.0.1:9091" target="_blank" rel="noreferrer">Prometheus UI</a><p className="text-xs text-slate-500">needs the port-forward</p></li>
            <li><a className="text-indigo-600 hover:underline" href="http://127.0.0.1:16686/jaeger" target="_blank" rel="noreferrer">Jaeger UI</a><p className="text-xs text-slate-500">needs the port-forward</p></li>
            <li><Link className="text-indigo-600 hover:underline" to="/agent">AI OpsAgent</Link><p className="text-xs text-slate-500">read-only assistant</p></li>
          </ul>
        </Card>
      </div>
    </>
  )
}
