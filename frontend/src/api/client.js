// Small fetch wrapper. Every backend error has the shape
//   {"error": {"code": "...", "message": "...", "details": {...}}}
// and is turned into an ApiError so pages can show a clear message.

const BASE = (import.meta.env?.VITE_API_BASE || '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, { status = 0, code = 'NETWORK_ERROR', details = {} } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

export async function request(path, { method = 'GET', body, timeoutMs = 20000, signal } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  if (signal) signal.addEventListener('abort', () => controller.abort(), { once: true })

  let res
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    })
  } catch (err) {
    clearTimeout(timer)
    if (err?.name === 'AbortError') {
      throw new ApiError(`Request timed out after ${timeoutMs / 1000}s`, { code: 'TIMEOUT' })
    }
    throw new ApiError('Cannot reach the backend API. Is the FastAPI server running on port 8000?', {
      code: 'BACKEND_UNREACHABLE',
    })
  }
  clearTimeout(timer)

  let data = null
  const text = await res.text()
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = null
    }
  }
  if (!res.ok) {
    const e = data?.error
    throw new ApiError(e?.message || `HTTP ${res.status} ${res.statusText}`, {
      status: res.status,
      code: e?.code || `HTTP_${res.status}`,
      details: e?.details || {},
    })
  }
  if (data === null) throw new ApiError('Backend returned an empty or invalid response', { status: res.status, code: 'INVALID_RESPONSE' })
  return data
}

export const api = {
  health: () => request('/api/health'),
  config: () => request('/api/config'),
  overview: () => request('/api/cluster/overview'),
  services: () => request('/api/services'),
  service: (name) => request(`/api/services/${encodeURIComponent(name)}`),
  serviceHistory: (name, metric, minutes, by = 'pod') =>
    request(`/api/services/${encodeURIComponent(name)}/metrics/${metric}?minutes=${minutes}&by=${by}`),
  pods: () => request('/api/pods'),
  events: () => request('/api/events'),
  status: () => request('/api/status'),
  dependencies: () => request('/api/dependencies'),
  history: (metric, minutes) => request(`/api/metrics/${metric}?minutes=${minutes}`),
  restarts: () => request('/api/metrics/restarts'),
  chat: (message, history) =>
    request('/api/chat', { method: 'POST', body: { message, history }, timeoutMs: 180000 }),
}
