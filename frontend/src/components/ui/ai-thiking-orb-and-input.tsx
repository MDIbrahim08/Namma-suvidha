/**
 * MorphOrb - AI Thinking Orb and Input Component
 *
 * Adapted from 21st.dev / anark17r for Namma Suvidha.
 * Brand Identity:
 *   - Deep petrol teal: #123C3A
 *   - Warm ivory: #F2EEE5
 *   - Terracotta accent: #D18B55
 *   - Dark charcoal: #29312F
 */

import React, { useCallback, useEffect, useRef, useState } from 'react'

export interface MorphOrbProps {
  minThinkMs?: number
  speed?: number
  placeholder?: string
  onSubmit?: (question: string) => Promise<string | void>
  className?: string
  defaultPrompt?: string
}

type OrbState = 'idle' | 'thinking' | 'answered'

interface Particle3D {
  x: number
  y: number
  z: number
  baseRadius: number
  color: string
}

const BRAND = {
  petrolTeal: '#123C3A',
  petrolTealLight: '#1d5452',
  warmIvory: '#F2EEE5',
  terracotta: '#D18B55',
  charcoal: '#29312F',
}

const PRESET_QUERIES = [
  { label: 'Toilets near me', query: 'Find public toilets near me' },
  { label: 'Accessible washrooms', query: 'Find wheelchair accessible toilets nearby' },
  { label: 'With running water', query: 'Show toilets with running water facilities' },
  { label: 'Within 1 km', query: 'Find toilets within 1 km' },
  { label: 'Near Majestic', query: 'Find public toilets near Majestic' },
]

export function MorphOrb({
  minThinkMs = 700,
  speed = 1,
  placeholder = "Ask Namma AI: 'Find accessible toilets near me' or 'Toilets near Majestic'…",
  onSubmit,
  className = '',
  defaultPrompt = '',
}: MorphOrbProps) {
  const [query, setQuery] = useState(defaultPrompt)
  const [state, setState] = useState<OrbState>('idle')
  const [answer, setAnswer] = useState<string>('')
  const [activeQuestion, setActiveQuestion] = useState<string>('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const animFrameRef = useRef<number | null>(null)
  const isSubmittingRef = useRef<boolean>(false)

  // Canvas 3D Thinking Orb Particle System
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Check prefers-reduced-motion
    const prefersReducedMotion =
      typeof window !== 'undefined' && typeof window.matchMedia === 'function'
        ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
        : false

    let isMounted = true
    const dpr = window.devicePixelRatio || 1
    const width = 160
    const height = 160

    canvas.width = width * dpr
    canvas.height = height * dpr
    ctx.scale(dpr, dpr)

    // Generate 3D spherical particle points
    const numParticles = 120
    const sphereRadius = 48
    const particles: Particle3D[] = []

    for (let i = 0; i < numParticles; i++) {
      const phi = Math.acos(-1 + (2 * i) / numParticles)
      const theta = Math.sqrt(numParticles * Math.PI) * phi

      const x = sphereRadius * Math.cos(theta) * Math.sin(phi)
      const y = sphereRadius * Math.sin(theta) * Math.sin(phi)
      const z = sphereRadius * Math.cos(phi)

      // Mix palette: deep petrol teal, terracotta, and warm ivory highlights
      let color = BRAND.petrolTealLight
      if (i % 5 === 0) color = BRAND.terracotta
      else if (i % 7 === 0) color = '#8ec3b0'

      particles.push({
        x,
        y,
        z,
        baseRadius: (i % 3 === 0 ? 2.2 : 1.5) + Math.random() * 0.8,
        color,
      })
    }

    let angleX = 0
    let angleY = 0

    const render = () => {
      if (!isMounted) return

      ctx.clearRect(0, 0, width, height)

      // Background soft ambient glow
      const gradient = ctx.createRadialGradient(
        width / 2,
        height / 2,
        10,
        width / 2,
        height / 2,
        sphereRadius + 20,
      )
      gradient.addColorStop(0, 'rgba(18, 60, 58, 0.15)')
      gradient.addColorStop(0.6, 'rgba(209, 139, 85, 0.08)')
      gradient.addColorStop(1, 'rgba(255, 255, 255, 0)')
      ctx.fillStyle = gradient
      ctx.beginPath()
      ctx.arc(width / 2, height / 2, sphereRadius + 20, 0, Math.PI * 2)
      ctx.fill()

      const currentSpeed = (state === 'thinking' ? 0.025 : 0.008) * speed
      if (!prefersReducedMotion) {
        angleX += currentSpeed * 0.7
        angleY += currentSpeed
      }

      const cosX = Math.cos(angleX)
      const sinX = Math.sin(angleX)
      const cosY = Math.cos(angleY)
      const sinY = Math.sin(angleY)

      const focalLength = 180

      // Sort particles by depth for correct painter's order
      const projected = particles.map((p) => {
        // Rotate Y
        const x1 = p.x * cosY - p.z * sinY
        const z1 = p.z * cosY + p.x * sinY

        // Rotate X
        const y2 = p.y * cosX - z1 * sinX
        const z2 = z1 * cosX + p.y * sinX

        const scale = focalLength / (focalLength + z2 + 80)
        const projX = width / 2 + x1 * scale
        const projY = height / 2 + y2 * scale
        const alpha = Math.max(0.15, Math.min(1, (z2 + sphereRadius) / (2 * sphereRadius) + 0.2))

        return { projX, projY, scale, alpha, color: p.color, radius: p.baseRadius * scale }
      })

      projected.sort((a, b) => a.scale - b.scale)

      for (const pt of projected) {
        ctx.beginPath()
        ctx.arc(pt.projX, pt.projY, Math.max(0.5, pt.radius), 0, Math.PI * 2)
        ctx.fillStyle = pt.color
        ctx.globalAlpha = pt.alpha
        ctx.fill()
      }
      ctx.globalAlpha = 1.0

      animFrameRef.current = requestAnimationFrame(render)
    }

    render()

    return () => {
      isMounted = false
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current)
      }
    }
  }, [state, speed])

  const handleExecuteQuery = useCallback(
    async (textToSubmit: string) => {
      const trimmed = textToSubmit.trim()
      if (!trimmed || isSubmittingRef.current) return

      isSubmittingRef.current = true
      setErrorMessage(null)
      setActiveQuestion(trimmed)
      setState('thinking')

      const startTime = Date.now()

      try {
        let resultText = ''
        if (onSubmit) {
          const res = await onSubmit(trimmed)
          if (typeof res === 'string') {
            resultText = res
          }
        }

        const elapsed = Date.now() - startTime
        const remaining = Math.max(0, minThinkMs - elapsed)

        setTimeout(() => {
          setAnswer(
            resultText ||
              "I've updated the map and facility list with the latest verified records.",
          )
          setState('answered')
          isSubmittingRef.current = false
        }, remaining)
      } catch (err) {
        console.error('MorphOrb query submission failed:', err)
        const elapsed = Date.now() - startTime
        const remaining = Math.max(0, minThinkMs - elapsed)

        setTimeout(() => {
          setErrorMessage(
            'Unable to complete search request right now. Please check your connectivity or try again.',
          )
          setState('idle')
          isSubmittingRef.current = false
        }, remaining)
      }
    },
    [onSubmit, minThinkMs],
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    handleExecuteQuery(query)
  }

  const handleReset = () => {
    setState('idle')
    setAnswer('')
    setQuery('')
    setErrorMessage(null)
  }

  return (
    <div
      data-testid="morph-orb-container"
      className={`w-full max-w-4xl mx-auto transition-all duration-300 ${className}`}
    >
      <div className="bg-white/95 backdrop-blur-md rounded-2xl border border-[#123C3A]/15 shadow-[0_4px_20px_-4px_rgba(18,60,58,0.1)] p-4 sm:p-5">
        {/* ================= STATE 1: IDLE PROMPT INPUT ================= */}
        {state === 'idle' && (
          <div className="space-y-3.5">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-[#123C3A] text-white">
                <span className="material-symbols-outlined text-[16px]">psychology</span>
              </span>
              <div>
                <span className="font-semibold text-xs tracking-wider uppercase text-[#123C3A] flex items-center gap-1.5">
                  Namma Suvidha AI Discovery Assistant
                  <span className="w-1.5 h-1.5 rounded-full bg-[#D18B55] animate-ping" />
                </span>
                <p className="text-[11px] text-slate-500">
                  Natural language search across BBMP &amp; OpenStreetMap washroom records
                </p>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="relative flex items-center">
              <div className="relative flex-1">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                  <span className="material-symbols-outlined text-slate-400 text-[18px]">
                    explore
                  </span>
                </div>
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={placeholder}
                  className="w-full text-xs sm:text-sm pl-10 pr-24 py-3 rounded-xl border border-slate-200 bg-[#F2EEE5]/30 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#123C3A] focus:border-transparent transition-all shadow-inner"
                />
              </div>

              <button
                type="submit"
                disabled={!query.trim()}
                aria-label="Ask AI Assistant"
                className="absolute right-1.5 top-1.5 bottom-1.5 px-4 rounded-lg bg-[#123C3A] text-white text-xs font-semibold hover:bg-[#1d5452] active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center gap-1 shadow-sm"
              >
                <span>Search</span>
                <span className="material-symbols-outlined text-[15px]">arrow_forward</span>
              </button>
            </form>

            {/* Quick Suggestion Chips */}
            <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mr-1">
                Try asking:
              </span>
              {PRESET_QUERIES.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => {
                    setQuery(preset.query)
                    handleExecuteQuery(preset.query)
                  }}
                  className="px-2.5 py-1 rounded-full bg-slate-100 hover:bg-[#F2EEE5] text-[11px] font-medium text-slate-700 hover:text-[#123C3A] border border-slate-200 transition-all active:scale-95"
                >
                  {preset.label}
                </button>
              ))}
            </div>

            {errorMessage && (
              <div className="p-2.5 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700 flex items-center gap-1.5">
                <span className="material-symbols-outlined text-sm">error</span>
                <span>{errorMessage}</span>
              </div>
            )}
          </div>
        )}

        {/* ================= STATE 2: THINKING ORB CANVAS ================= */}
        {state === 'thinking' && (
          <div
            data-testid="morph-orb-thinking-state"
            className="flex flex-col items-center justify-center py-6 text-center space-y-3"
          >
            <div className="relative flex items-center justify-center">
              <canvas
                ref={canvasRef}
                className="mo-orb-canvas w-32 h-32 rounded-full mo-orb-glow"
              />
            </div>

            <div className="space-y-1">
              <div className="flex items-center justify-center gap-2 text-xs font-semibold text-[#123C3A]">
                <span className="material-symbols-outlined text-sm animate-spin text-[#D18B55]">
                  sync
                </span>
                <span>Analyzing Sanitation Telemetry…</span>
              </div>
              <p className="text-xs text-slate-600 font-medium italic max-w-md truncate">
                &ldquo;{activeQuestion}&rdquo;
              </p>
              <p className="text-[11px] text-slate-400">
                Scanning BBMP spatial coordinates and OpenStreetMap facility tags…
              </p>
            </div>
          </div>
        )}

        {/* ================= STATE 3: ANSWER CARD ================= */}
        {state === 'answered' && (
          <div data-testid="morph-orb-answer-state" className="mo-card-unfold space-y-4">
            <div className="flex items-start justify-between gap-3 pb-3 border-b border-slate-100">
              <div className="flex items-start gap-2.5">
                <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-[#123C3A] text-white flex-shrink-0 mt-0.5">
                  <span className="material-symbols-outlined text-[15px]">assistant</span>
                </span>
                <div>
                  <span className="text-[10px] uppercase font-bold text-[#123C3A] tracking-wider block">
                    AI Assistant Response
                  </span>
                  <p className="text-xs text-slate-500 font-medium italic">
                    &ldquo;{activeQuestion}&rdquo;
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={handleReset}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 transition-colors flex items-center gap-1"
              >
                <span className="material-symbols-outlined text-sm">edit</span>
                <span>Ask Another</span>
              </button>
            </div>

            {/* Answer Text */}
            <div className="p-3.5 rounded-xl bg-[#F2EEE5]/50 border border-[#123C3A]/10 text-xs sm:text-sm text-slate-800 leading-relaxed font-medium">
              {answer}
            </div>

            {/* Quick Actions Footer */}
            <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
              <span className="flex items-center gap-1 text-[#123C3A] font-semibold">
                <span className="material-symbols-outlined text-sm text-[#D18B55]">check_circle</span>
                Live map view and results updated
              </span>
              <button
                type="button"
                onClick={handleReset}
                className="text-[#123C3A] hover:underline font-semibold"
              >
                New query &rarr;
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default MorphOrb
