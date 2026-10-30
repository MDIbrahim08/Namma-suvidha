import { createBrowserRouter } from 'react-router-dom'
import AppShell from './layout/AppShell'
import LandingPage from '../pages/LandingPage'
import NotFoundPage from '../pages/NotFoundPage'
import CitizenHome from '../features/citizen/pages/CitizenHome'
import EvaluatorHome from '../features/evaluator/pages/EvaluatorHome'
import GovernmentHome from '../features/government/pages/GovernmentHome'

export const routes = [
  {
    element: <AppShell />,
    children: [
      { path: '/', element: <LandingPage /> },
      { path: '/citizen', element: <CitizenHome /> },
      { path: '/evaluator', element: <EvaluatorHome /> },
      { path: '/government', element: <GovernmentHome /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

export const router = createBrowserRouter(routes, {
  future: { v7_relativeSplatPath: true },
})
