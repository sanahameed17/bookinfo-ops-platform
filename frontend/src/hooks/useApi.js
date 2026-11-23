import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'

// Global refresh state: a "tick" that every page listens to, the auto-refresh switch,
// and the time of the last successful load (shown in the header).
export const RefreshContext = createContext({
  tick: 0,
  refresh: () => {},
  auto: false,
  setAuto: () => {},
  lastUpdated: null,
  markUpdated: () => {},
})

export function useRefresh() {
  return useContext(RefreshContext)
}

/**
 * Load data from the backend. Re-loads when `deps` change or when the global refresh tick changes.
 * Keeps the previous data while re-loading, so the screen does not flash empty.
 */
export function useApi(loader, deps = []) {
  const { tick, markUpdated } = useRefresh()
  const [state, setState] = useState({ data: null, error: null, loading: true })
  const loaderRef = useRef(loader)
  loaderRef.current = loader

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true }))
    try {
      const data = await loaderRef.current()
      setState({ data, error: null, loading: false })
      markUpdated?.()
    } catch (error) {
      setState((s) => ({ data: s.data, error, loading: false }))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [markUpdated])

  useEffect(() => {
    let cancelled = false
    setState((s) => ({ ...s, loading: true }))
    loaderRef
      .current()
      .then((data) => {
        if (!cancelled) {
          setState({ data, error: null, loading: false })
          markUpdated?.()
        }
      })
      .catch((error) => {
        if (!cancelled) setState((s) => ({ data: s.data, error, loading: false }))
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, ...deps])

  return { ...state, reload: load }
}
