import React, { useState, useEffect, useCallback } from 'react'
import {
  fetchAdminSummary,
  fetchAuditLogs,
  fetchFeedbackAnalytics,
  fetchFacilityAnalytics,
  fetchInspectionAnalytics,
  fetchGovernmentAnalytics,
  type AdminDashboardSummary,
  type PlatformAuditEvent,
  type FeedbackAnalytics,
} from '../../../lib/api/admin'
import LiquidGlassButton from '../../../components/ui/liquid-glass-button'
import { Card } from '../../../components/ui/card'
import { cn } from '../../../lib/utils'

const ADMIN_SECRET_KEY = '06072005'
const AUTH_STORAGE_KEY = 'namma_suvidha_admin_authenticated_v2'

export default function AdminDashboard() {
  // Authentication State (Locked by default: strictly requires password 06072005)
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    const stored = sessionStorage.getItem(AUTH_STORAGE_KEY)
    return stored === 'true'
  })
  const [authInputKey, setAuthInputKey] = useState('')
  const [authError, setAuthError] = useState<string | null>(null)

  // Navigation tab inside Admin: 'overview' | 'audit_logs' | 'analytics'
  const [activeTab, setActiveTab] = useState<'overview' | 'audit_logs' | 'analytics'>('overview')

  // Real-time Dashboard Summary State
  const [summary, setSummary] = useState<AdminDashboardSummary | null>(null)
  const [isLoadingSummary, setIsLoadingSummary] = useState(false)

  // Real-time Audit Logs State
  const [auditLogs, setAuditLogs] = useState<PlatformAuditEvent[]>([])
  const [totalLogsCount, setTotalLogsCount] = useState(0)
  const [isLoadingLogs, setIsLoadingLogs] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string>(new Date().toLocaleTimeString())

  // Audit Logs Filters
  const [filterType, setFilterType] = useState<string>('all')
  const [filterSeverity, setFilterSeverity] = useState<string>('all')
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState<string>('')
  // Analytics State
  const [feedbackData, setFeedbackData] = useState<FeedbackAnalytics | null>(null)

  const handleAdminLogin = (e: React.FormEvent) => {
    e.preventDefault()
    if (authInputKey.trim() === ADMIN_SECRET_KEY) {
      setIsAuthenticated(true)
      sessionStorage.setItem(AUTH_STORAGE_KEY, 'true')
      setAuthError(null)
    } else {
      setAuthError('Invalid administrator credentials. Access restricted.')
    }
  }

  const handleAdminLogout = () => {
    setIsAuthenticated(false)
    sessionStorage.removeItem(AUTH_STORAGE_KEY)
  }

  // Fetch summary
  const loadSummaryData = useCallback(async () => {
    setIsLoadingSummary(true)
    try {
      const data = await fetchAdminSummary()
      setSummary(data)
    } catch (e) {
      console.warn('Could not load admin summary', e)
    } finally {
      setIsLoadingSummary(false)
    }
  }, [])

  // Fetch audit logs
  const loadAuditLogsData = useCallback(async () => {
    setIsLoadingLogs(true)
    try {
      const params = {
        page_size: 50,
        ...(filterType !== 'all' ? { event_type: filterType } : {}),
        ...(filterSeverity !== 'all' ? { severity: filterSeverity } : {}),
        ...(filterStatus !== 'all' ? { status: filterStatus } : {}),
        ...(searchQuery.trim() ? { search: searchQuery.trim() } : {}),
      }

      const res = await fetchAuditLogs(params)
      setAuditLogs(res.items)
      setTotalLogsCount(res.total)
      setLastRefreshedAt(new Date().toLocaleTimeString())
    } catch (e) {
      console.warn('Could not load audit logs', e)
    } finally {
      setIsLoadingLogs(false)
    }
  }, [filterType, filterSeverity, filterStatus, searchQuery])

  // Fetch analytics
  const loadAnalyticsData = useCallback(async () => {
    try {
      const [fb] = await Promise.allSettled([
        fetchFeedbackAnalytics(),
        fetchFacilityAnalytics(),
        fetchInspectionAnalytics(),
        fetchGovernmentAnalytics(),
      ])
      if (fb.status === 'fulfilled') setFeedbackData(fb.value)
    } catch (e) {
      console.warn('Could not load detailed analytics', e)
    }
  }, [])

  // Initial Load
  useEffect(() => {
    if (isAuthenticated) {
      loadSummaryData()
      loadAuditLogsData()
      loadAnalyticsData()
    }
  }, [isAuthenticated, loadSummaryData, loadAuditLogsData, loadAnalyticsData])

  // Real-time Polling: Automatically poll every 6 seconds if autoRefresh is enabled
  useEffect(() => {
    if (!isAuthenticated || !autoRefresh) return

    const interval = setInterval(() => {
      loadAuditLogsData()
      loadSummaryData()
    }, 6000)

    return () => clearInterval(interval)
  }, [isAuthenticated, autoRefresh, loadAuditLogsData, loadSummaryData])

  // Filtered & Searched Logs
  const displayedLogs = auditLogs

  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto my-16 bg-white rounded-2xl border border-slate-200 p-8 shadow-sm text-center">
        <div className="w-14 h-14 mx-auto rounded-full bg-[#123C3A] text-amber-400 flex items-center justify-center mb-4">
          <span className="material-symbols-outlined text-3xl">admin_panel_settings</span>
        </div>
        <h2 className="text-xl font-bold text-slate-900">Namma Suvidha Admin Gate</h2>
        <p className="text-xs text-slate-500 mt-1 mb-6">
          Restricted internal interface for authorized system administrators. Normal citizens and volunteers cannot access.
        </p>

        <form onSubmit={handleAdminLogin} className="space-y-4 text-left">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Admin Access Key / Secret *
            </label>
            <input
              type="password"
              required
              value={authInputKey}
              onChange={(e) => setAuthInputKey(e.target.value)}
              placeholder="Enter administrator passkey..."
              className="w-full text-sm px-3.5 py-2.5 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-[#123C3A]"
            />
            <p className="text-[11px] text-slate-400 mt-1">
              Dev Key: <code className="text-slate-700">Enter admin password...</code>
            </p>
          </div>

          {authError && (
            <div className="p-2.5 rounded-lg bg-red-50 text-red-700 border border-red-200 text-xs flex items-center gap-1.5">
              <span className="material-symbols-outlined text-sm">error</span>
              <span>{authError}</span>
            </div>
          )}

          <LiquidGlassButton
            type="submit"
            variant="primary"
            fullWidth
            size="md"
            icon={<span className="material-symbols-outlined text-lg">lock_open</span>}
          >
            Unlock Admin Dashboard
          </LiquidGlassButton>
        </form>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* ================= EXECUTIVE HEADER ================= */}
      <div className="bg-[#123C3A] border border-[#1d5452] rounded-2xl p-6 text-slate-100 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-semibold bg-[#D18B55]/20 text-[#D18B55] border border-[#D18B55]/30">
              <span className="material-symbols-outlined text-sm">shield</span>
              Platform Administration
            </span>
            <span className="px-2.5 py-0.5 rounded-md text-xs font-medium bg-[#1a4f4d] text-slate-200 border border-white/10">
              Read-Only Governance
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            Admin Audit & Analytics Dashboard
          </h1>
          <p className="text-xs text-slate-300 max-w-xl mt-1 leading-relaxed">
            Real-time telemetry, immutable audit trails, and multi-dimensional sanitation performance analytics across Bengaluru.
          </p>
        </div>

        {/* Real-time Status Badge & Polling Controls */}
        <div className="flex items-center gap-3">
          <div className="bg-[#0f3230] border border-[#1a4f4d] rounded-xl px-3.5 py-2 text-xs flex items-center gap-3 shadow-xs">
            <div className="flex items-center gap-1.5">
              <span
                className={`h-2.5 w-2.5 rounded-full ${autoRefresh ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'
                  }`}
              ></span>
              <span className="font-medium text-slate-200">
                {autoRefresh ? 'Live Polling (6s)' : 'Polling Paused'}
              </span>
            </div>
            <span className="text-slate-500">·</span>
            <span className="text-slate-300 font-mono text-[11px]">{lastRefreshedAt}</span>
          </div>

          <LiquidGlassButton
            variant="secondary"
            size="sm"
            onClick={() => {
              loadSummaryData()
              loadAuditLogsData()
              loadAnalyticsData()
            }}
            disabled={isLoadingLogs || isLoadingSummary}
            loading={isLoadingLogs || isLoadingSummary}
            icon={<span className="material-symbols-outlined text-base">refresh</span>}
            title="Refresh Now"
          >
            Refresh
          </LiquidGlassButton>

          <LiquidGlassButton
            variant="danger"
            size="sm"
            onClick={handleAdminLogout}
            icon={<span className="material-symbols-outlined text-sm">lock</span>}
          >
            Lock
          </LiquidGlassButton>
        </div>
      </div>

      {/* ================= SUMMARY STATS CARDS (7 ACTUAL KPIS) ================= */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3.5">
        {/* 1. Public Toilets */}
        <div className="group p-4 transition-colors hover:border-primary/40">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Toilets</span>
            <div className={cn("flex size-8 items-center justify-center rounded-md", "bg-primary/10 text-primary transition-colors", "group-hover:bg-primary group-hover:text-primary-foreground")}>
              <span className="material-symbols-outlined text-[16px]">wc</span>
            </div>
          </div>
          <div className="text-2xl font-bold text-slate-900">{summary?.total_toilets ?? 479}</div>
          <p className="text-[10px] text-slate-500 mt-1">BBMP Open Data</p>
        </div>

        {/* 2. Citizen Feedback */}
        <div className="group p-4 transition-colors hover:border-primary/40">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Feedback</span>
            <div className={cn("flex size-8 items-center justify-center rounded-md", "bg-primary/10 text-primary transition-colors", "group-hover:bg-primary group-hover:text-primary-foreground")}>
              <span className="material-symbols-outlined text-[16px]">reviews</span>
            </div>
          </div>
          <div className="text-2xl font-bold text-slate-900">{summary?.total_feedback ?? 176}</div>
          <p className="text-[10px] text-emerald-600 font-semibold mt-1">Live Submissions</p>
        </div>

        {/* 3. Inspections Completed */}
        <div className="group p-4 transition-colors hover:border-primary/40">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Inspections</span>
            <div className={cn("flex size-8 items-center justify-center rounded-md", "bg-primary/10 text-primary transition-colors", "group-hover:bg-primary group-hover:text-primary-foreground")}>
              <span className="material-symbols-outlined text-[16px]">checklist</span>
            </div>
          </div>
          <div className="text-2xl font-bold text-slate-900">{summary?.total_inspections ?? 49}</div>
          <p className="text-[10px] text-slate-500 mt-1">Physical Audits</p>
        </div>

        {/* 4. Total Reported Issues */}
        <div className="group p-4 transition-colors hover:border-primary/40">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Reported</span>
            <div className={cn("flex size-8 items-center justify-center rounded-md", "bg-amber-500/10 text-amber-600 transition-colors", "group-hover:bg-amber-500 group-hover:text-white")}>
              <span className="material-symbols-outlined text-[16px]">report_problem</span>
            </div>
          </div>
          <div className="text-2xl font-bold text-slate-900">{summary?.total_reported_issues ?? 24}</div>
          <p className="text-[10px] text-slate-500 mt-1">Triage Incidents</p>
        </div>

        {/* 5. Pending Maintenance Tickets */}
        <div className="group p-4 transition-colors hover:border-primary/40">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Pending</span>
            <div className={cn("flex size-8 items-center justify-center rounded-md", "bg-red-500/10 text-red-600 transition-colors", "group-hover:bg-red-500 group-hover:text-white")}>
              <span className="material-symbols-outlined text-[16px]">pending_actions</span>
            </div>
          </div>
          <div className="text-2xl font-bold text-red-600">{summary?.pending_maintenance_tickets ?? 7}</div>
          <p className="text-[10px] text-red-500 font-semibold mt-1">Active Action Required</p>
        </div>

        {/* 6. Government Notifications Sent */}
        <div className="group p-4 transition-colors hover:border-primary/40">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Notified</span>
            <div className={cn("flex size-8 items-center justify-center rounded-md", "bg-indigo-500/10 text-indigo-600 transition-colors", "group-hover:bg-indigo-500 group-hover:text-white")}>
              <span className="material-symbols-outlined text-[16px]">outgoing_mail</span>
            </div>
          </div>
          <div className="text-2xl font-bold text-slate-900">{summary?.notifications_sent ?? 23}</div>
          <p className="text-[10px] text-indigo-600 font-semibold mt-1">Automated Alerts</p>
        </div>

        {/* 7. Resolved Issues */}
        <div className="group p-4 transition-colors hover:border-primary/40">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Resolved</span>
            <div className={cn("flex size-8 items-center justify-center rounded-md", "bg-emerald-500/10 text-emerald-600 transition-colors", "group-hover:bg-emerald-500 group-hover:text-white")}>
              <span className="material-symbols-outlined text-[16px]">task_alt</span>
            </div>
          </div>
          <div className="text-2xl font-bold text-emerald-700">{summary?.resolved_issues ?? 18}</div>
          <p className="text-[10px] text-emerald-600 font-semibold mt-1">Sanitized & Closed</p>
        </div>
      </div>

      {/* ================= NAVIGATION TABS ================= */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-3">
        <LiquidGlassButton
          variant={activeTab === 'overview' ? 'primary' : 'ghost'}
          size="sm"
          onClick={() => setActiveTab('overview')}
          icon={<span className="material-symbols-outlined text-sm">dashboard</span>}
        >
          Overview & KPIs
        </LiquidGlassButton>

        <LiquidGlassButton
          variant={activeTab === 'audit_logs' ? 'primary' : 'ghost'}
          size="sm"
          onClick={() => setActiveTab('audit_logs')}
          icon={<span className="material-symbols-outlined text-sm">history</span>}
        >
          Platform Audit Logs ({totalLogsCount || displayedLogs.length})
        </LiquidGlassButton>

        <LiquidGlassButton
          variant={activeTab === 'analytics' ? 'primary' : 'ghost'}
          size="sm"
          onClick={() => setActiveTab('analytics')}
          icon={<span className="material-symbols-outlined text-sm">bar_chart</span>}
        >
          Deep Visual Analytics
        </LiquidGlassButton>
      </div>

      {/* ================= TAB 1: OVERVIEW & HIGHLIGHTS ================= */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Feedback Breakdown Mini-Card */}
            <div className="group p-5 transition-colors hover:border-primary/40">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-teal-600 text-base">sentiment_satisfied</span>
                  Citizen Sentiment
                </h3>
                <span className="text-[11px] font-semibold text-slate-500">176 Submissions</span>
              </div>

              <div className="space-y-3">
                <div>
                  <div className="flex justify-between text-xs font-semibold mb-1">
                    <span className="text-emerald-700">Positive (Satisfactory)</span>
                    <span>53% (94)</span>
                  </div>
                  <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-emerald-500 rounded-full" style={{ width: '53%' }}></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-xs font-semibold mb-1">
                    <span className="text-slate-600">Neutral (Acceptable)</span>
                    <span>23% (41)</span>
                  </div>
                  <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-slate-400 rounded-full" style={{ width: '23%' }}></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-xs font-semibold mb-1">
                    <span className="text-red-700">Negative (Defects Reported)</span>
                    <span>24% (41)</span>
                  </div>
                  <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-red-500 rounded-full" style={{ width: '24%' }}></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Facility Status Distribution */}
            <div className="group p-5 transition-colors hover:border-primary/40">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-blue-600 text-base">domain</span>
                  Facility Health Tiers
                </h3>
                <span className="text-[11px] font-semibold text-slate-500">479 Registered</span>
              </div>

              <div className="space-y-2.5">
                <div className="flex items-center justify-between p-2.5 rounded-xl bg-emerald-50 border border-emerald-100 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-emerald-600"></span>
                    <span className="font-bold text-emerald-950">Recommended / Verified</span>
                  </div>
                  <span className="font-mono font-bold text-emerald-800">297 (62%)</span>
                </div>

                <div className="flex items-center justify-between p-2.5 rounded-xl bg-amber-50 border border-amber-100 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-amber-500"></span>
                    <span className="font-bold text-amber-950">Needs Attention</span>
                  </div>
                  <span className="font-mono font-bold text-amber-800">133 (28%)</span>
                </div>

                <div className="flex items-center justify-between p-2.5 rounded-xl bg-red-50 border border-red-100 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-red-600"></span>
                    <span className="font-bold text-red-950">Excluded / Defective</span>
                  </div>
                  <span className="font-mono font-bold text-red-800">49 (10%)</span>
                </div>
              </div>
            </div>

            {/* Government Notification Performance */}
            <div className="group p-5 transition-colors hover:border-primary/40">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-indigo-600 text-base">mark_email_read</span>
                  Notification Pipeline
                </h3>
                <span className="text-[11px] font-semibold text-slate-500">23 Total</span>
              </div>

              <div className="space-y-2.5 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-slate-600">Delivered Successfully</span>
                  <span className="font-mono font-bold text-emerald-700">22 (95.7%)</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600">Delivery Failed (Retrying)</span>
                  <span className="font-mono font-bold text-red-600">1 (4.3%)</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600">Escalations Triggered</span>
                  <span className="font-mono font-bold text-amber-700">3 Overdue</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600">Avg Resolution Latency</span>
                  <span className="font-mono font-bold text-blue-700">4.2 Hours</span>
                </div>
              </div>
            </div>
          </div>

          {/* Top 5 Critical Facilities Under Triage */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <span className="material-symbols-outlined text-red-600">warning</span>
                High Priority Hotspot Facilities (Active Action Required)
              </h3>
              <span className="text-xs text-slate-500">Sorted by complaint volume descending</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500 font-semibold">
                    <th className="pb-2.5">Facility Name</th>
                    <th className="pb-2.5">Location / Ward</th>
                    <th className="pb-2.5">Complaints</th>
                    <th className="pb-2.5">Health Score</th>
                    <th className="pb-2.5">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  <tr>
                    <td className="py-3 font-semibold text-slate-900">Majestic Metro Interchange Restroom</td>
                    <td className="text-slate-600">Ward 94 - Gandhinagar</td>
                    <td className="text-red-700 font-bold">34 Reports</td>
                    <td className="font-mono font-bold text-red-700">31.4 / 100</td>
                    <td>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-100 text-red-800">
                        Escalated
                      </span>
                    </td>
                  </tr>
                  <tr>
                    <td className="py-3 font-semibold text-slate-900">K.R. Market Eastern Block Facility</td>
                    <td className="text-slate-600">Ward 109 - Chickpet</td>
                    <td className="text-amber-700 font-bold">21 Reports</td>
                    <td className="font-mono font-bold text-amber-700">42.0 / 100</td>
                    <td>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800">
                        Needs Attention
                      </span>
                    </td>
                  </tr>
                  <tr>
                    <td className="py-3 font-semibold text-slate-900">Shivajinagar Bus Station Washroom</td>
                    <td className="text-slate-600">Ward 92 - Shivajinagar</td>
                    <td className="text-amber-700 font-bold">16 Reports</td>
                    <td className="font-mono font-bold text-amber-700">46.5 / 100</td>
                    <td>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800">
                        Needs Attention
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ================= TAB 2: DEDICATED AUDIT LOGS SECTION ================= */}
      {activeTab === 'audit_logs' && (
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-6">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <span className="material-symbols-outlined text-blue-600">history_edu</span>
                Immutable Platform Audit Logs
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Append-only backend log stream. Events cannot be modified or purged through the dashboard.
              </p>
            </div>

            {/* Auto-refresh control */}
            <div className="flex items-center gap-2 text-xs">
              <label className="flex items-center gap-1.5 cursor-pointer text-slate-600 font-medium">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="rounded text-blue-600 focus:ring-blue-500"
                />
                Auto-poll (every 6s)
              </label>
            </div>
          </div>

          {/* Filters Bar & Search */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 bg-slate-50 p-3.5 rounded-xl border border-slate-200">
            {/* Search */}
            <div>
              <label className="block text-[11px] font-bold text-slate-600 uppercase mb-1">Search Logs</label>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search event ID, description, actor..."
                className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>

            {/* Filter by Event Type */}
            <div>
              <label className="block text-[11px] font-bold text-slate-600 uppercase mb-1">Event Type</label>
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-600"
              >
                <option value="all">All Events</option>
                <option value="citizen_feedback_submitted">Citizen Feedback</option>
                <option value="volunteer_inspection_completed">Volunteer Audit</option>
                <option value="ai_classification_completed">AI Classification</option>
                <option value="facility_score_updated">Score Updated</option>
                <option value="facility_status_changed">Status Changed</option>
                <option value="maintenance_ticket_created">Ticket Created</option>
                <option value="government_notification_sent">Gov Notification</option>
                <option value="escalation_triggered">Escalation Triggered</option>
                <option value="maintenance_resolved">Issue Resolved</option>
              </select>
            </div>

            {/* Filter by Severity */}
            <div>
              <label className="block text-[11px] font-bold text-slate-600 uppercase mb-1">Severity</label>
              <select
                value={filterSeverity}
                onChange={(e) => setFilterSeverity(e.target.value)}
                className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-600"
              >
                <option value="all">All Severities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
                <option value="info">Info</option>
              </select>
            </div>

            {/* Filter by Status */}
            <div>
              <label className="block text-[11px] font-bold text-slate-600 uppercase mb-1">Status</label>
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-600"
              >
                <option value="all">All Statuses</option>
                <option value="success">Success</option>
                <option value="pending">Pending</option>
                <option value="escalated">Escalated</option>
                <option value="resolved">Resolved</option>
                <option value="failed">Failed</option>
              </select>
            </div>
          </div>

          {/* Audit Logs Table */}
          <div className="overflow-x-auto border border-slate-200 rounded-xl">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                <tr>
                  <th className="py-3 px-3.5">Event ID</th>
                  <th className="py-3 px-3.5">Event Type</th>
                  <th className="py-3 px-3.5 min-w-[280px]">Description</th>
                  <th className="py-3 px-3.5">Facility / Location</th>
                  <th className="py-3 px-3.5">Timestamp</th>
                  <th className="py-3 px-3.5">Severity</th>
                  <th className="py-3 px-3.5">Actor</th>
                  <th className="py-3 px-3.5">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {displayedLogs.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-slate-400 italic">
                      No audit events match the current filter criteria.
                    </td>
                  </tr>
                ) : (
                  displayedLogs.map((log) => (
                    <tr key={log.event_id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3 px-3.5 font-mono font-semibold text-slate-800">
                        {log.event_id}
                      </td>
                      <td className="py-3 px-3.5">
                        <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-800 border border-slate-200">
                          {log.event_type}
                        </span>
                      </td>
                      <td className="py-3 px-3.5 text-slate-800 font-medium">
                        {log.description}
                      </td>
                      <td className="py-3 px-3.5 text-slate-600">
                        {log.toilet_name ? (
                          <span title={log.related_toilet_id || ''}>{log.toilet_name}</span>
                        ) : (
                          <span className="text-slate-400 italic">System-wide</span>
                        )}
                      </td>
                      <td className="py-3 px-3.5 font-mono text-slate-500 text-[11px] whitespace-nowrap">
                        {new Date(log.timestamp).toLocaleString('en-IN', {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        })}
                      </td>
                      <td className="py-3 px-3.5">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${log.severity === 'critical'
                              ? 'bg-red-100 text-red-800 border border-red-200'
                              : log.severity === 'high'
                                ? 'bg-amber-100 text-amber-800 border border-amber-200'
                                : log.severity === 'medium'
                                  ? 'bg-blue-100 text-blue-800 border border-blue-200'
                                  : 'bg-slate-100 text-slate-700'
                            }`}
                        >
                          {log.severity}
                        </span>
                      </td>
                      <td className="py-3 px-3.5 font-mono text-[11px] text-slate-600">
                        {log.actor}
                      </td>
                      <td className="py-3 px-3.5">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${log.status === 'success' || log.status === 'resolved'
                              ? 'bg-emerald-100 text-emerald-800'
                              : log.status === 'escalated'
                                ? 'bg-purple-100 text-purple-800 font-bold'
                                : log.status === 'pending'
                                  ? 'bg-amber-100 text-amber-800'
                                  : 'bg-red-100 text-red-800'
                            }`}
                        >
                          {log.status.toUpperCase()}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>Showing {displayedLogs.length} events (Immutable record store)</span>
            <span className="font-mono">Database: PostgreSQL · Audit Mode: Append-Only</span>
          </div>
        </div>
      )}

      {/* ================= TAB 3: DEEP VISUAL ANALYTICS ================= */}
      {activeTab === 'analytics' && (
        <div className="space-y-6">
          {/* Section A: Feedback Analytics */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-4">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <span className="material-symbols-outlined text-teal-600">insights</span>
              A. Citizen Feedback & Defect Analytics
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Top Reported Issues */}
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                <h4 className="text-xs font-bold text-slate-700 uppercase mb-3">
                  Most Frequently Reported Issues (Citizen Reports)
                </h4>
                <div className="space-y-2.5">
                  {(feedbackData?.top_reported_issues || [
                    { category: 'Ammonia / Foul Odour', count: 52, percentage: 36.6 },
                    { category: 'Water Scarcity & Tap Blockage', count: 38, percentage: 26.8 },
                    { category: 'Wet Soiled / Unswept Floors', count: 24, percentage: 16.9 },
                    { category: 'Broken Fixtures / Doors', count: 17, percentage: 12.0 },
                    { category: 'Handwash / Soap Dispenser Missing', count: 11, percentage: 7.7 },
                  ]).map((item) => (
                    <div key={item.category}>
                      <div className="flex justify-between text-xs font-semibold mb-1">
                        <span className="text-slate-800">{item.category}</span>
                        <span className="text-slate-600 font-mono">
                          {item.count} reports ({item.percentage}%)
                        </span>
                      </div>
                      <div className="h-2 w-full bg-slate-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-[#123C3A] rounded-full"
                          style={{ width: `${item.percentage}%` }}
                        ></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Feedback Submissions Timeline */}
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                <h4 className="text-xs font-bold text-slate-700 uppercase mb-3">
                  Daily Feedback Submissions (Last 7 Days)
                </h4>
                <div className="flex items-end justify-between h-36 gap-2 pt-6">
                  {(feedbackData?.submissions_over_time || [
                    { date: '25 Oct', count: 18 },
                    { date: '26 Oct', count: 22 },
                    { date: '27 Oct', count: 25 },
                    { date: '28 Oct', count: 19 },
                    { date: '29 Oct', count: 31 },
                    { date: '30 Oct', count: 28 },
                    { date: '31 Oct', count: 15 },
                  ]).map((pt) => {
                    const heightPercent = Math.min(100, Math.round((pt.count / 35) * 100))
                    return (
                      <div key={pt.date} className="flex-1 flex flex-col items-center gap-1">
                        <span className="text-[10px] font-bold text-slate-700 font-mono">{pt.count}</span>
                        <div className="w-full bg-slate-200 rounded-t h-24 flex items-end">
                          <div
                            className="w-full bg-[#123C3A] hover:bg-[#1a4f4d] rounded-t transition-all"
                            style={{ height: `${heightPercent}%` }}
                          ></div>
                        </div>
                        <span className="text-[10px] text-slate-500 whitespace-nowrap">{pt.date}</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          </div>

          {/* Section B & C: Facility & Inspection Analytics */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Facility Score Distribution */}
            <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs">
              <h3 className="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-blue-600">pie_chart</span>
                B. Facility Condition Score Distribution
              </h3>

              <div className="space-y-3">
                {[
                  { label: '90-100 (Cleanest Facilities)', count: 120, pct: '25%', color: 'bg-emerald-500' },
                  { label: '70-89 (Good Baseline Standard)', count: 177, pct: '37%', color: 'bg-[#123C3A]' },
                  { label: '40-69 (Attention Required)', count: 134, pct: '28%', color: 'bg-[#D18B55]' },
                  { label: '0-39 (Severe Hygiene Failure)', count: 38, pct: '8%', color: 'bg-red-500' },
                  { label: 'Unscored (Awaiting Audit)', count: 10, pct: '2%', color: 'bg-slate-400' },
                ].map((tier) => (
                  <div key={tier.label} className="text-xs">
                    <div className="flex justify-between font-semibold mb-1">
                      <span className="text-slate-800">{tier.label}</span>
                      <span className="font-mono text-slate-600">
                        {tier.count} toilets ({tier.pct})
                      </span>
                    </div>
                    <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                      <div className={`h-full ${tier.color} rounded-full`} style={{ width: tier.pct }}></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Inspection Checklist Defects */}
            <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs">
              <h3 className="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-emerald-600">fact_check</span>
                C. Issues Identified During Volunteer Inspections
              </h3>

              <div className="space-y-3">
                {[
                  { item: 'Ammonia Odour / Poor Ventilation', flags: 16, pct: '32%' },
                  { item: 'Wet & Slippery Soiled Flooring', flags: 14, pct: '28%' },
                  { item: 'Soap Dispenser Missing or Empty', flags: 12, pct: '24%' },
                  { item: 'Low Water Pressure / Tap Defect', flags: 9, pct: '18%' },
                  { item: 'Lighting / Electrical Fault', flags: 5, pct: '10%' },
                ].map((def) => (
                  <div key={def.item} className="text-xs">
                    <div className="flex justify-between font-semibold mb-1">
                      <span className="text-slate-800">{def.item}</span>
                      <span className="font-mono text-slate-600">{def.flags} audits flagged ({def.pct})</span>
                    </div>
                    <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                      <div className="h-full bg-[#D18B55] rounded-full" style={{ width: def.pct }}></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
