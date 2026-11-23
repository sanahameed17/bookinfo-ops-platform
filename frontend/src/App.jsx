import { useCallback, useEffect, useMemo, useState } from 'react'
import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { RefreshContext } from './hooks/useApi'
import AgentPage from './pages/AgentPage'
import EventsPage from './pages/EventsPage'
import MonitoringPage from './pages/MonitoringPage'
import NotFoundPage from './pages/NotFoundPage'
import OverviewPage from './pages/OverviewPage'
import PodsPage from './pages/PodsPage'
import ServiceDetailPage from './pages/ServiceDetailPage'
import ServicesPage from './pages/ServicesPage'
import SettingsPage from './pages/SettingsPage'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<OverviewPage />} />
        <Route path="services" element={<ServicesPage />} />
        <Route path="services/:name" element={<ServiceDetailPage />} />
        <Route path="pods" element={<PodsPage />} />
        <Route path="monitoring" element={<MonitoringPage />} />
        <Route path="agent" element={<AgentPage />} />
        <Route path="events" element={<EventsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  const [tick, setTick] = useState(0)
  const [auto, setAuto] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(null)

  const refresh = useCallback(() => setTick((t) => t + 1), [])
  const markUpdated = useCallback(() => setLastUpdated(new Date().toISOString()), [])

  useEffect(() => {
    if (!auto) return undefined
    const id = setInterval(refresh, 15000)
    return () => clearInterval(id)
  }, [auto, refresh])

  const value = useMemo(() => ({ tick, refresh, auto, setAuto, lastUpdated, markUpdated }), [tick, refresh, auto, lastUpdated, markUpdated])
  return (
    <RefreshContext.Provider value={value}>
      <AppRoutes />
    </RefreshContext.Provider>
  )
}
