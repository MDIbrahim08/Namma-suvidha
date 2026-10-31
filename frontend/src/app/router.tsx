import { createBrowserRouter } from 'react-router-dom'
import AppShell from './layout/AppShell'
import LandingPage from '../pages/LandingPage'
import NotFoundPage from '../pages/NotFoundPage'
import ErrorBoundary from '../components/ErrorBoundary'
import CitizenHome from '../features/citizen/pages/CitizenHome'
import EvaluatorHome from '../features/evaluator/pages/EvaluatorHome'
import AdminDashboard from '../features/admin/pages/AdminDashboard'

export const routes = [
  {
    element: <AppShell />,
    errorElement: <ErrorBoundary />,
    children: [
      { path: '/', element: <LandingPage /> },
      { path: '/citizen', element: <CitizenHome /> },
      { path: '/evaluator', element: <EvaluatorHome /> },
      { path: '/admin', element: <AdminDashboard /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

export const router = createBrowserRouter(routes, {
  future: { v7_relativeSplatPath: true },
})
