import { useMemo, useState } from 'react'
import { api } from '../api/client'
import { Card, ErrorState, PageHeader, Pill, Segmented, Skeleton, Table } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { fmtTime, timeAgo } from '../utils/format'

export default function EventsPage() {
  const { data, error, reload } = useApi(() => api.events())
  const [type, setType] = useState('all')
  const [q, setQ] = useState('')

  const rows = useMemo(() => {
    let ev = data?.events || []
    if (type !== 'all') ev = ev.filter((e) => e.type === type)
    if (q) {
      const s = q.toLowerCase()
      ev = ev.filter((e) => `${e.reason} ${e.object_name} ${e.message}`.toLowerCase().includes(s))
    }
    return ev
  }, [data, type, q])

  return (
    <>
      <PageHeader title="Kubernetes events" description="Events of the namespace, newest first. Kubernetes keeps events for about one hour by default." />
      <Card
        title={data ? `${rows.length} event(s)` : 'Events'}
        actions={
          <>
            <label htmlFor="ev-search" className="sr-only">Filter events</label>
            <input id="ev-search" className="input w-48" placeholder="Filter reason / object / text" value={q} onChange={(e) => setQ(e.target.value)} />
            <Segmented label="Event type" options={[{ value: 'all', label: 'All' }, { value: 'Warning', label: 'Warning' }, { value: 'Normal', label: 'Normal' }]} value={type} onChange={setType} />
          </>
        }
      >
        {error && !data ? (
          <ErrorState error={error} onRetry={reload} />
        ) : !data ? (
          <Skeleton className="h-64" />
        ) : (
          <Table
            rowKey={(e) => `${e.object_name}-${e.reason}-${e.last_seen}-${e.message}`}
            rows={rows}
            empty="No events in the last hour"
            columns={[
              { key: 'type', label: 'Type', render: (e) => <Pill tone={e.type === 'Warning' ? 'amber' : 'slate'}>{e.type}</Pill> },
              { key: 'reason', label: 'Reason', className: 'text-xs font-semibold' },
              { key: 'obj', label: 'Object', render: (e) => <span className="font-mono text-xs">{e.object_kind}/{e.object_name}</span> },
              { key: 'message', label: 'Message', className: 'max-w-xl text-xs text-slate-600' },
              { key: 'count', label: 'Count', className: 'tabular-nums text-xs' },
              { key: 'source', label: 'Source', className: 'text-xs text-slate-500' },
              { key: 'last', label: 'Last seen', render: (e) => <span className="text-xs" title={fmtTime(e.last_seen)}>{timeAgo(e.last_seen)}</span> },
            ]}
          />
        )}
      </Card>
    </>
  )
}
