// OWNER: Gaurish (visual refinement). Structure: header / main <Outlet /> / footer.
import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { env } from '../../config/env'
import LogoSplash from '../../components/LogoSplash'

const navItems = [
  { to: '/', label: 'Citizen' },
  { to: '/evaluator', label: 'Volunteer' },
  { to: '/admin', label: 'Admin' },
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
          <Link to="/" className="text-lg font-semibold text-teal-700 hover:text-teal-800 transition-colors">
            {env.appName}
          </Link>
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
      <footer className="border-t border-slate-200 bg-white py-4 px-4 text-xs text-slate-500">
        <div className="mx-auto max-w-5xl flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>Team Agentics · Problem Statement CS/26-0018 · AI for Citizen Well-Being</span>
          <Link
            to="/admin"
            className="text-slate-400 hover:text-slate-600 transition-colors flex items-center gap-1 font-medium"
          >
            <span className="material-symbols-outlined text-[14px]">admin_panel_settings</span>
            Internal Admin Audit
          </Link>
        </div>
      </footer>
    </div>
  )
}
