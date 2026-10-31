import React, { useState, useEffect, useRef } from 'react'

interface LogoSplashProps {
  onFinish?: () => void
}

export const LogoSplash: React.FC<LogoSplashProps> = ({ onFinish }) => {
  const [isVisible, setIsVisible] = useState(true)
  const [isFading, setIsFading] = useState(false)
  const [useFallback, setUseFallback] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const hasDismissedRef = useRef(false)

  const handleDismiss = () => {
    if (hasDismissedRef.current) return
    hasDismissedRef.current = true

    setIsFading(true)
    setTimeout(() => {
      setIsVisible(false)
      if (onFinish) onFinish()
    }, 450)
  }

  useEffect(() => {
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      handleDismiss()
      return
    }

    if (videoRef.current) {
      videoRef.current.muted = true
      videoRef.current.play().catch(() => {
        setUseFallback(true)
      })
    }

    // Safety fallback only triggers if video fails to report onEnded after 11 seconds (video is 9.96s)
    const safetyTimer = setTimeout(() => {
      handleDismiss()
    }, 11500)

    return () => clearTimeout(safetyTimer)
  }, [])

  if (!isVisible) return null

  return (
    <div
      role="region"
      aria-label="Welcome Logo Reveal"
      style={{ backgroundColor: '#e6e4d9' }}
      className={`fixed inset-0 z-50 flex items-center justify-center transition-opacity duration-500 overflow-hidden ${
        isFading ? 'opacity-0 pointer-events-none' : 'opacity-100'
      }`}
    >
      {!useFallback ? (
        <div className="relative w-full h-full flex items-center justify-center">
          <video
            ref={videoRef}
            src="/logo-reveal.mp4"
            autoPlay
            muted
            playsInline
            preload="auto"
            onEnded={handleDismiss}
            onError={() => setUseFallback(true)}
            className="w-full h-full max-w-4xl max-h-[85vh] object-contain"
          />
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center animate-in fade-in zoom-in-95 duration-500">
          <div className="relative p-6 sm:p-8 bg-[#e6e4d9] rounded-3xl border border-stone-300/60 shadow-lg flex flex-col items-center">
            <img
              src="/logo.png"
              alt="Namma Suvidha"
              className="w-36 h-36 sm:w-48 sm:h-48 object-contain animate-bounce transition-transform"
              style={{ animationDuration: '2s' }}
            />
            <h1 className="mt-4 text-2xl sm:text-3xl font-black text-[#123C3A] tracking-tight">
              ನಮ್ಮ Suvidha
            </h1>
            <p className="text-xs sm:text-sm font-medium text-emerald-900/80 mt-1">
              Bengaluru Public Sanitation Network
            </p>
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={handleDismiss}
        className="absolute top-5 right-5 z-10 px-4 py-1.5 text-xs font-bold tracking-wider uppercase text-stone-700 bg-white/80 hover:bg-white active:scale-95 rounded-full transition-all shadow-sm border border-stone-300 backdrop-blur-xs"
      >
        Skip &rarr;
      </button>
    </div>
  )
}

export default LogoSplash
