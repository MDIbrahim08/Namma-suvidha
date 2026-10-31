// OWNER: Gaurish (visual refinement). Structure: header / main <Outlet /> / footer.
import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { env } from '../../config/env'
import LogoSplash from '../../components/LogoSplash'
import LiquidGlassNavbar from '../../components/ui/liquid-glass-navbar'
import BackgroundGlow from '../../components/ui/background-components'

const navItems = [
  { to: '/', label: 'Citizen', icon: 'location_city' },
  { to: '/evaluator', label: 'Volunteer', icon: 'badge' },
  { to: '/admin', label: 'Admin', icon: 'shield_person' },
]

export default function AppShell() {
  const [showSplash, setShowSplash] = useState(() => {
    // Show only once per browser session
    return !sessionStorage.getItem('namma_suvidha_splash_seen')
  })
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const handleSplashFinish = () => {
    sessionStorage.setItem('namma_suvidha_splash_seen', 'true')
    setShowSplash(false)
  }

  return (
    <BackgroundGlow className="text-slate-900 min-h-screen flex flex-col">
      {showSplash && <LogoSplash onFinish={handleSplashFinish} />}
      <header className="border-b border-slate-200/80 bg-white/85 backdrop-blur-md sticky top-0 z-40">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-2 sm:gap-4 px-3 sm:px-4 py-2 sm:py-2.5">
          <Link
            to="/"
            onClick={() => setMobileMenuOpen(false)}
            className="flex items-center gap-2.5 sm:gap-3 hover:opacity-90 transition-opacity shrink-0"
          >
            <img
              src="/logo.png"
              alt="Namma Suvidha Logo"
              className="w-11 h-11 sm:w-14 sm:h-14 object-contain rounded-xl shadow-xs bg-white p-0.5 border border-slate-100"
            />
            <div className="flex flex-col">
              <span className="text-lg sm:text-xl font-bold tracking-tight text-[#123C3A] leading-tight m-0 p-0">{env.appName}</span>
              <span className="text-[10px] sm:text-xs font-semibold text-emerald-700 tracking-wider uppercase">Bengaluru Civic</span>
            </div>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:block">
            <LiquidGlassNavbar items={navItems} />
          </div>

          {/* Mobile Hamburger Button */}
          <div className="md:hidden flex items-center">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label={mobileMenuOpen ? 'Close Menu' : 'Open Menu'}
              aria-expanded={mobileMenuOpen}
              className="w-10 h-10 rounded-xl bg-slate-100/90 hover:bg-slate-200 text-slate-800 flex items-center justify-center transition-all border border-slate-200 shadow-xs active:scale-95"
            >
              <span className="material-symbols-outlined text-[24px]">
                {mobileMenuOpen ? 'close' : 'menu'}
              </span>
            </button>
          </div>
        </div>

        {/* Mobile Dropdown Drawer Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-slate-200/70 bg-white/95 backdrop-blur-xl px-4 py-3 shadow-xl animate-in slide-in-from-top-2 duration-200">
            <div className="flex flex-col gap-2">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  onClick={() => setMobileMenuOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-4 py-2.5 rounded-xl font-semibold text-sm transition-all ${
                      isActive
                        ? 'bg-[#123C3A] text-white shadow-sm'
                        : 'text-slate-700 hover:bg-slate-100'
                    }`
                  }
                >
                  <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          </div>
        )}
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-3 sm:px-4 py-6 sm:py-8">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200/70 bg-white/70 backdrop-blur-sm py-4 px-4 text-xs text-slate-500">
        <div className="mx-auto max-w-5xl flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>Team Agentics · Problem Statement CS/26-0018 · AI for Citizen Well-Being</span>
          <Link
            to="/admin"
            className="text-slate-400 hover:text-[#123C3A] transition-colors flex items-center gap-1 font-medium"
          >
            <span className="material-symbols-outlined text-[14px]">shield_person</span>
            Internal Admin Audit
          </Link>
        </div>
      </footer>
    </BackgroundGlow>
  )
}
