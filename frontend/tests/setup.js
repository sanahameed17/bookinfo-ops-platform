import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

// recharts' ResponsiveContainer needs ResizeObserver, which jsdom does not have
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
}
