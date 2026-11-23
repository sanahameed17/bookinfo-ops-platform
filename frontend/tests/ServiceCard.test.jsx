// Requirement: clicking a microservice card opens its dedicated detail page.
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import ServiceCard from '../src/components/ServiceCard'

const reviews = {
  name: 'reviews',
  health: 'Healthy',
  health_reason: '3/3 pods ready',
  status: 'normal',
  ready_replicas: 3,
  desired_replicas: 3,
  pod_count: 3,
  ready_pods: 3,
  versions: ['v1', 'v2', 'v3'],
  version_count: 3,
  deployments: ['reviews-v1', 'reviews-v2', 'reviews-v3'],
  cpu_cores: 0.0291,
  memory_mib: 465.2,
  metrics_state: 'ok',
  restart_count: 9,
  anomalies: [],
  updated_at: new Date().toISOString(),
}

function DetailProbe() {
  const { name } = useParams()
  return <h1>detail page for {name}</h1>
}

function renderCard(service) {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<ServiceCard service={service} />} />
        <Route path="/services/:name" element={<DetailProbe />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ServiceCard', () => {
  it('shows name, health, replicas, versions, CPU and memory', () => {
    renderCard(reviews)
    expect(screen.getByText('reviews')).toBeInTheDocument()
    expect(screen.getByText('Healthy')).toBeInTheDocument()
    expect(screen.getByText('3/3', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('v1')).toBeInTheDocument()
    expect(screen.getByText('v3')).toBeInTheDocument()
    expect(screen.getByText('0.0291 cores')).toBeInTheDocument()
    expect(screen.getByText('465.2 MiB')).toBeInTheDocument()
  })

  it('navigates to /services/<name> when clicked', () => {
    renderCard(reviews)
    fireEvent.click(screen.getByRole('link', { name: /open details of the reviews microservice/i }))
    expect(screen.getByRole('heading', { name: 'detail page for reviews' })).toBeInTheDocument()
  })

  it('shows missing metrics as a dash, never as zero', () => {
    renderCard({ ...reviews, cpu_cores: null, memory_mib: null, metrics_state: 'prometheus_unavailable' })
    expect(screen.queryByText('0.0000 cores')).not.toBeInTheDocument()
    expect(screen.getAllByTitle('Prometheus unavailable')).toHaveLength(2)
  })
})
