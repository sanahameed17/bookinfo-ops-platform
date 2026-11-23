import {
  Activity,
  Boxes,
  Bot,
  CalendarClock,
  LayoutDashboard,
  Layers,
  Menu,
  RefreshCw,
  Settings,
  X,
} from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { api } from '../api/client'
import { useApi, useRefresh } from '../hooks/useApi'
import { fmtClock } from '../utils/format'

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/services', label: 'Microservices', icon: Layers },
  { to: '/pods', label: 'Pods Explorer', icon: Boxes },
  { to: '/monitoring', label: 'Resource Monitoring', icon: Activity },
  { to: '/agent', label: 'AI OpsAgent', icon: Bot },
  { to: '/events', label: 'Kubernetes Events', icon: CalendarClock },
  { to: '/settings', label: 'Settings', icon: Settings },
]

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden="true">
        <rect width="32" height="32" rx="8" fill="#4f46e5" />
        <path d="M9 8h9a5 5 0 0 1 0 10H9z" fill="none" stroke="#fff" strokeWidth="2.5" />
        <path d="M9 14h10a5 5 0 0 1 0 10H9z" fill="none" stroke="#a5b4fc" strokeWidth="2.5" />
      </svg>
      <div className="leading-tight">
        <p className="text-sm font-semibold text-white">Bookinfo Ops</p>
        <p className="text-[11px] text-slate-400">Observability & AI</p>
      </div>
    </div>
  )
}

function Sidebar({ onNavigate }) {
  return (
    <nav aria-label="Main navigation" className="flex h-full flex-col bg-slate-900 px-3 py-5">
      <div className="px-2"><Logo /></div>
      <ul className="mt-8 space-y-1">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={end}
              onClick={onNavigate}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 ${
                  isActive ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`
              }
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
      <p className="mt-auto px-3 text-[11px] leading-relaxed text-slate-500">
        Read-only. Data from the Kubernetes API and Prometheus.
      </p>
    </nav>
  )
}

function Dot({ ok, label }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-slate-600">
      <span className={`h-2 w-2 rounded-full ${ok === null ? 'bg-slate-300' : ok ? 'bg-emerald-500' : 'bg-rose-500'}`} aria-hidden="true" />
      {label}
    </span>
  )
}

function Header({ onMenu }) {
  const { refresh, auto, setAuto, lastUpdated } = useRefresh()
  const { data: health, error } = useApi(() => api.health())
  const { data: config } = useApi(() => api.config())
  const k8sOk = health ? health.kubernetes.ok : error ? false : null
  const promOk = health ? health.prometheus.available : error ? false : null
  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3 lg:px-8">
        <button type="button" onClick={onMenu} className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100 lg:hidden" aria-label="Open navigation">
          <Menu className="h-5 w-5" />
        </button>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <span className="text-xs text-slate-500">
            Context <span className="font-mono font-medium text-slate-800">{health?.kubernetes?.context || '—'}</span>
          </span>
          <span className="text-xs text-slate-500">
            Namespace <span className="rounded bg-indigo-50 px-1.5 py-0.5 font-mono font-medium text-indigo-700">{config?.namespace || '—'}</span>
          </span>
          <Dot ok={k8sOk} label={k8sOk === false ? 'Kubernetes unreachable' : 'Kubernetes'} />
          <Dot ok={promOk} label={promOk === false ? 'Prometheus unavailable' : 'Prometheus'} />
          {error && <span className="text-xs font-medium text-rose-600">Backend unreachable</span>}
        </div>
        <div className="ml-auto flex items-center gap-3">
          <span className="hidden text-xs text-slate-500 sm:inline">
            Last updated <span className="tabular-nums text-slate-700">{lastUpdated ? fmtClock(lastUpdated) : '—'}</span>
          </span>
          <label className="flex cursor-pointer items-center gap-1.5 text-xs text-slate-600">
            <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} className="h-3.5 w-3.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
            Auto (15s)
          </label>
          <button type="button" onClick={refresh} className="btn-primary" aria-label="Refresh data">
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" /> Refresh
          </button>
        </div>
      </div>
    </header>
  )
}

export default function Layout() {
  const [open, setOpen] = useState(false)
  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 lg:block">
        <Sidebar />
      </aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-64">
            <button type="button" onClick={() => setOpen(false)} className="absolute right-2 top-3 z-10 rounded p-1 text-slate-300 hover:text-white" aria-label="Close navigation">
              <X className="h-5 w-5" />
            </button>
            <Sidebar onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}
      <div className="lg:pl-60">
        <Header onMenu={() => setOpen(true)} />
        <main id="main" className="mx-auto max-w-[1500px] px-4 py-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
