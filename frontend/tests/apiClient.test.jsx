// Requirement: the frontend handles API errors (structured backend errors, unreachable backend).
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ApiError, api } from '../src/api/client'
import { ErrorState } from '../src/components/ui'

function mockFetch(status, body) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(body === undefined ? '' : JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }),
  )
}

describe('api client', () => {
  it('returns JSON on success', async () => {
    mockFetch(200, { services: [] })
    await expect(api.services()).resolves.toEqual({ services: [] })
  })

  it('turns a structured backend error into ApiError with code and status', async () => {
    mockFetch(503, { error: { code: 'PROMETHEUS_UNAVAILABLE', message: 'Cannot reach Prometheus', details: {} } })
    const err = await api.history('cpu', 15).catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(503)
    expect(err.code).toBe('PROMETHEUS_UNAVAILABLE')
    expect(err.message).toBe('Cannot reach Prometheus')
  })

  it('handles a 404 for an unknown service', async () => {
    mockFetch(404, { error: { code: 'SERVICE_NOT_FOUND', message: "Service 'x' not found", details: { available_services: ['reviews'] } } })
    const err = await api.service('x').catch((e) => e)
    expect(err.code).toBe('SERVICE_NOT_FOUND')
    expect(err.details.available_services).toEqual(['reviews'])
  })

  it('reports an unreachable backend', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    const err = await api.overview().catch((e) => e)
    expect(err.code).toBe('BACKEND_UNREACHABLE')
  })

  it('handles a non-JSON error body', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('Bad Gateway', { status: 502, statusText: 'Bad Gateway' }))
    const err = await api.status().catch((e) => e)
    expect(err.status).toBe(502)
    expect(err.code).toBe('HTTP_502')
  })
})

describe('ErrorState', () => {
  it('shows the message, the code and a hint', () => {
    render(<ErrorState error={new ApiError('Cannot reach Prometheus', { status: 503, code: 'PROMETHEUS_UNAVAILABLE' })} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Cannot reach Prometheus')
    expect(screen.getByRole('alert')).toHaveTextContent('PROMETHEUS_UNAVAILABLE')
    expect(screen.getByRole('alert')).toHaveTextContent('port-forward')
  })
})
