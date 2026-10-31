import React, { useState, useEffect, useRef } from 'react'

interface LogoSplashProps {
  onFinish?: () => void
}

export const LogoSplash: React.FC<LogoSplashProps> = ({ onFinish }) => {
  const [isVisible, setIsVisible] = useState(true)
  const [isFading, setIsFading] = useState(false)
  const [useSvgFallback] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const hasDismissedRef = useRef(false)

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.setAttribute('muted', '')
      videoRef.current.muted = true
    }
  }, [isVisible, useSvgFallback])

  const handleDismiss = () => {
    if (hasDismissedRef.current) return
    hasDismissedRef.current = true

    setIsFading(true)
    setTimeout(() => {
      setIsVisible(false)
      if (onFinish) onFinish()
    }, 500)
  }

  useEffect(() => {
    // Check prefers-reduced-motion
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      handleDismiss()
      return
    }

    // 5.5-second total safety fallback
    const timer = setTimeout(() => {
      handleDismiss()
    }, 5500)

    return () => clearTimeout(timer)
  }, [])

  if (!isVisible) return null

  return (
    <div
      role="region"
      aria-label="Welcome Logo Reveal"
      className={`fixed inset-0 z-50 flex items-center justify-center bg-white transition-opacity duration-500 ${
        isFading ? 'opacity-0 pointer-events-none' : 'opacity-100'
      }`}
    >
      {!useSvgFallback ? (
        <video
          ref={videoRef}
          src="/logo-reveal.mp4"
          autoPlay
          muted
          playsInline
          preload="auto"
          onEnded={handleDismiss}
          onError={handleDismiss}
          className="w-full max-w-2xl h-auto aspect-video object-contain"
        />
      ) : (
        <iframe
          src="/namma-suvidha-logo-animation.html"
          title="Namma Suvidha Logo Animation"
          className="w-full h-full border-0 pointer-events-none"
        />
      )}

      <button
        type="button"
        onClick={handleDismiss}
        className="absolute top-6 right-6 z-10 px-4 py-1.5 text-xs font-semibold tracking-wider uppercase text-slate-500 bg-slate-100 hover:bg-slate-200 active:scale-95 rounded-full transition-all shadow-xs"
      >
        Skip
      </button>
    </div>
  )
}

export default LogoSplash
