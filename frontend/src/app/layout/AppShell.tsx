// OWNER: Gaurish (visual refinement). Structure: header / main <Outlet /> / footer.
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { env } from '../../config/env'
import LogoSplash from '../../components/LogoSplash'

const navItems = [
  { to: '/', label: 'Home' },
  { to: '/citizen', label: 'Citizen' },
  { to: '/evaluator', label: 'Evaluator' },
  { to: '/government', label: 'Government' },
]

export default function AppShell() {
  const [showSplash, setShowSplash] = useState(() => {
    // Show only once per browser session
    return !sessionStorage.getItem('namma_suvidha_splash_seen')
  })

  const handleSplashFinish = () => {
    sessionStorage.setItem('namma_suvidha_splash_seen', 'true')
    setShowSplash(false)
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      {showSplash && <LogoSplash onFinish={handleSplashFinish} />}
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-4 py-3">
          <span className="text-lg font-semibold text-teal-700">{env.appName}</span>
          <nav className="flex gap-4 text-sm">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  isActive ? 'font-semibold text-teal-700' : 'text-slate-600 hover:text-teal-700'
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-500">
        Team Agentics · Problem Statement CS/26-0018 · AI for Citizen Well-Being
      </footer>
    </div>
  )
}
