import { Link } from 'react-router-dom'
import BackendStatus from '../components/status/BackendStatus'
import { env } from '../config/env'

const modules = [
  {
    to: '/citizen',
    title: 'Citizen Portal',
    badge: 'Live Public Map',
    icon: 'location_on',
    color: 'border-teal-500 hover:border-teal-600 group-hover:bg-teal-50',
    iconBg: 'bg-teal-100 text-teal-700',
    text: 'Discover nearby public washrooms across Bengaluru with live BBMP data, filter amenities, and report cleanliness.',
  },
  {
    to: '/evaluator',
    title: 'Volunteer Portal',
    badge: 'Civic Inspector',
    icon: 'volunteer_activism',
    color: 'border-emerald-500 hover:border-emerald-600 group-hover:bg-emerald-50',
    iconBg: 'bg-emerald-100 text-emerald-700',
    text: 'Register as a civic volunteer with real-time GPS & ID verification, complete hygiene audits, and track honorarium.',
  },
]

const devLinks = [
  {
    href: 'http://127.0.0.1:8000/docs',
    title: 'FastAPI Interactive Swagger',
    desc: 'Test all 30+ endpoints live',
  },
  {
    href: 'http://127.0.0.1:8000/api/v1/toilets/nearby?latitude=12.9767&longitude=77.5713&radius=3000',
    title: 'Live BBMP Nearby API',
    desc: '479 verified Bengaluru records',
  },
  {
    href: 'http://127.0.0.1:8000/api/v1/health',
    title: 'Backend Health Check',
    desc: 'Status, environment & version',
  },
]

export default function LandingPage() {
  const replaySplash = () => {
    sessionStorage.removeItem('namma_suvidha_splash_seen')
    window.location.reload()
  }

  return (
    <div className="space-y-10">
      {/* Hero Header */}
      <header className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-slate-200 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-2xl font-bold tracking-tight text-teal-800">{env.appName}</span>
            <span className="rounded-full bg-teal-100 px-2.5 py-0.5 text-xs font-semibold text-teal-800">
              Bengaluru MVP
            </span>
          </div>
          <p className="text-sm md:text-base text-slate-600 max-w-2xl">
            AI-assisted public washroom discovery, WebAuthn gig verification, and BBMP municipal hygiene monitoring.
          </p>
        </div>
        <button
          onClick={replaySplash}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
          title="Replay opening logo reveal video"
        >
          <span className="material-symbols-outlined text-sm">play_circle</span>
          Replay Logo Reveal
        </button>
      </header>

      {/* Main Portals Grid */}
      <section>
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-4">Application Portals</h2>
        <div className="grid gap-6 md:grid-cols-3">
          {modules.map((m) => (
            <Link
              key={m.to}
              to={m.to}
              className={`group flex flex-col justify-between rounded-xl border-2 bg-white p-6 shadow-sm transition-all hover:shadow-md ${m.color}`}
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className={`p-2.5 rounded-lg ${m.iconBg}`}>
                    <span className="material-symbols-outlined text-xl">{m.icon}</span>
                  </div>
                  <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                    {m.badge}
                  </span>
                </div>
                <h3 className="text-lg font-bold text-slate-900 group-hover:text-teal-700 transition-colors">
                  {m.title}
                </h3>
                <p className="mt-2 text-sm text-slate-600 leading-relaxed">{m.text}</p>
              </div>
              <div className="mt-6 flex items-center gap-1 text-sm font-semibold text-teal-700">
                Launch Portal
                <span className="material-symbols-outlined text-sm transition-transform group-hover:translate-x-1">
                  arrow_forward
                </span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Developer & API Links Section */}
      <section className="rounded-xl border border-slate-200 bg-slate-50/70 p-6">
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
          Direct Backend & API Endpoints
        </h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {devLinks.map((l) => (
            <a
              key={l.href}
              href={l.href}
              target="_blank"
              rel="noreferrer"
              className="flex flex-col justify-center rounded-lg border border-slate-200 bg-white p-3 hover:border-teal-500 transition-colors shadow-2xs"
            >
              <span className="text-sm font-semibold text-slate-800 flex items-center justify-between">
                {l.title}
                <span className="material-symbols-outlined text-xs text-slate-400">open_in_new</span>
              </span>
              <span className="text-xs text-slate-500 mt-0.5">{l.desc}</span>
            </a>
          ))}
        </div>
      </section>

      {/* Backend & Supabase Live Status */}
      <BackendStatus />
    </div>
  )
}
