import { render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { routes } from '../app/router'
import * as healthApi from '../lib/api/health'
import LandingPage from './LandingPage'

vi.mock('../lib/api/health', () => ({
  getHealth: vi.fn(),
  getDbHealth: vi.fn(),
}))

const routerFuture = { v7_startTransition: true, v7_relativeSplatPath: true } as const

describe('Phase 0 routes and BackendStatus', () => {
  it('renders the app name and live BackendStatus result on LandingPage', async () => {
    vi.mocked(healthApi.getHealth).mockResolvedValueOnce({
      status: 'ok',
      app: 'Namma Suvidha API',
      env: 'development',
      version: '0.1.0',
      timestamp: '2026-10-30T09:50:00Z',
    })
    vi.mocked(healthApi.getDbHealth).mockResolvedValueOnce({
      connected: false,
      postgis_available: false,
      postgis_version: null,
      error: 'RuntimeError: DATABASE_URL is not configured',
    })

    const memRouter = createMemoryRouter([
      { path: '/', element: <LandingPage /> },
      ...routes,
    ], {
      initialEntries: ['/'],
      future: { v7_relativeSplatPath: true },
    })
    render(<RouterProvider router={memRouter} future={routerFuture} />)

    expect(screen.getByRole('heading', { level: 1, name: 'Namma Suvidha' })).toBeInTheDocument()
    await waitFor(() => {
      expect(
        screen.getByText(/API: reachable — Namma Suvidha API v0\.1\.0 \(development\)/),
      ).toBeInTheDocument()
      expect(
        screen.getByText(/Database: not connected — RuntimeError: DATABASE_URL is not configured/),
      ).toBeInTheDocument()
    })
  })

  it.each([
    ['/citizen', 'Citizen'],
    ['/evaluator', 'Evaluator'],
    ['/admin', 'Admin Audit & Analytics Dashboard'],
    ['/unknown-route', '404 — Page not found'],
  ])('renders route %s with heading %s', async (path, headingText) => {
    const memRouter = createMemoryRouter(routes, {
      initialEntries: [path],
      future: { v7_relativeSplatPath: true },
    })
    render(<RouterProvider router={memRouter} future={routerFuture} />)

    expect(screen.getByRole('heading', { name: headingText })).toBeInTheDocument()
  })
})
