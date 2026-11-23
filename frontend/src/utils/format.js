// Formatting helpers. A null/undefined value means "no data" and is shown as an em dash -
// it is never displayed as 0.

export const isNum = (v) => typeof v === 'number' && Number.isFinite(v)

export function fmtCores(v, digits = 3) {
  if (!isNum(v)) return '—'
  if (v > 0 && v < 0.001) return '<0.001 cores'
  return `${v.toFixed(digits)} cores`
}

export function fmtMilli(v) {
  if (!isNum(v)) return '—'
  return `${(v * 1000).toFixed(1)} m`
}

export function fmtMiB(v, digits = 1) {
  if (!isNum(v)) return '—'
  if (v >= 1024) return `${(v / 1024).toFixed(2)} GiB`
  return `${v.toFixed(digits)} MiB`
}

export function fmtPct(v) {
  return isNum(v) ? `${v.toFixed(1)}%` : '—'
}

export function fmtTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString()
}

export function fmtClock(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function timeAgo(iso) {
  if (!iso) return '—'
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000)
  if (Number.isNaN(s)) return '—'
  if (s < 60) return `${Math.max(s, 0)}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

export const HEALTH_STYLE = {
  Healthy: { dot: 'bg-emerald-500', badge: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20', label: 'Healthy' },
  Degraded: { dot: 'bg-amber-500', badge: 'bg-amber-50 text-amber-800 ring-amber-600/20', label: 'Degraded' },
  Down: { dot: 'bg-rose-500', badge: 'bg-rose-50 text-rose-700 ring-rose-600/20', label: 'Down' },
  Unknown: { dot: 'bg-slate-400', badge: 'bg-slate-100 text-slate-700 ring-slate-500/20', label: 'Unknown' },
}

export const STATUS_STYLE = {
  normal: { badge: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20', label: 'Normal' },
  anomalous: { badge: 'bg-rose-50 text-rose-700 ring-rose-600/20', label: 'Anomalous' },
  prometheus_unavailable: { badge: 'bg-slate-100 text-slate-700 ring-slate-500/30', label: 'Prometheus unavailable' },
  metrics_unavailable: { badge: 'bg-amber-50 text-amber-800 ring-amber-600/20', label: 'Metrics unavailable' },
}

// Stable colours for chart series
export const SERIES_COLORS = ['#4f46e5', '#0891b2', '#d97706', '#db2777', '#059669', '#7c3aed', '#dc2626', '#0d9488', '#65a30d', '#2563eb']

/** Turn [{name, points:[{t,v}]}] into recharts rows [{t, <name>: v}] */
export function seriesToRows(series = []) {
  const map = new Map()
  for (const s of series) {
    for (const p of s.points || []) {
      if (!map.has(p.t)) map.set(p.t, { t: p.t })
      map.get(p.t)[s.name] = isNum(p.v) ? p.v : null
    }
  }
  return [...map.values()].sort((a, b) => (a.t < b.t ? -1 : 1))
}

/** Short pod name for legends: reviews-v1-847664ccd7-mfjkw -> reviews-v1-…mfjkw */
export function shortPod(name = '') {
  const parts = name.split('-')
  if (parts.length < 3) return name
  const [podId] = parts.slice(-1)
  return `${parts.slice(0, -2).join('-')}-…${podId}`
}
