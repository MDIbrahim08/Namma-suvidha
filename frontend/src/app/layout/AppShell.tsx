// OWNER: Gaurish (visual refinement). Structure: header / main <Outlet /> / footer.
import { useState } from 'react'
import { Link, Outlet } from 'react-router-dom'
import { env } from '../../config/env'
import LogoSplash from '../../components/LogoSplash'
import LiquidGlassNavbar from '../../components/ui/liquid-glass-navbar'

const navItems = [
  { to: '/', label: 'Citizen', icon: 'explore' },
  { to: '/evaluator', label: 'Volunteer', icon: 'volunteer_activism' },
  { to: '/admin', label: 'Admin', icon: 'admin_panel_settings' },
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
      <header className="border-b border-slate-200/80 bg-white/80 backdrop-blur-md sticky top-0 z-30">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-4 py-2.5">
          <Link
            to="/"
            className="flex items-center gap-2 hover:opacity-90 transition-opacity"
          >
            <span className="material-symbols-outlined text-[24px] text-[#D18B55]">water_drop</span>
            <span className="text-lg font-bold tracking-tight text-[#123C3A] m-0 p-0">{env.appName}</span>
          </Link>
          <LiquidGlassNavbar items={navItems} />
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
            className="text-slate-400 hover:text-[#123C3A] transition-colors flex items-center gap-1 font-medium"
          >
            <span className="material-symbols-outlined text-[14px]">admin_panel_settings</span>
            Internal Admin Audit
          </Link>
        </div>
      </footer>
    </div>
  )
}
