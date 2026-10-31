/**
 * LiquidGlassNavbar - Waterline / Liquid Glass Navigation Bar
 *
 * Adapted from 21st.dev / anark17r for Namma Suvidha.
 * Supports WebGL canvas liquid refraction shader with pure CSS glass fallback,
 * smooth hover ripple refraction, reduced-motion compliance, and accessible tab/link navigation.
 */

import { useEffect, useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'

export interface NavItem {
  to: string
  label: string
  icon?: string
}

export interface LiquidGlassNavbarProps {
  items: NavItem[]
  className?: string
}

export function LiquidGlassNavbar({ items, className = '' }: LiquidGlassNavbarProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [hasWebGL, setHasWebGL] = useState<boolean>(true)
  const animFrameRef = useRef<number | null>(null)

  // Lightweight WebGL liquid shader simulation
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const prefersReducedMotion =
      typeof window !== 'undefined' && typeof window.matchMedia === 'function'
        ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
        : false
    if (prefersReducedMotion) {
      setHasWebGL(false)
      return
    }

    // Guard against JSDOM / non-browser test runners where getContext is not implemented
    if (typeof canvas.getContext !== 'function') {
      setHasWebGL(false)
      return
    }

    let gl: WebGLRenderingContext | null = null
    try {
      gl = (canvas.getContext('webgl', { alpha: true, antialias: true }) ||
        canvas.getContext('experimental-webgl')) as WebGLRenderingContext | null
    } catch {
      gl = null
    }

    if (!gl) {
      setHasWebGL(false)
      return
    }

    // Vertex shader
    const vsSource = `
      attribute vec2 a_position;
      varying vec2 v_uv;
      void main() {
        v_uv = a_position * 0.5 + 0.5;
        gl_Position = vec4(a_position, 0.0, 1.0);
      }
    `

    // Fragment shader with liquid waterline ripple & caustics
    const fsSource = `
      precision mediump float;
      varying vec2 v_uv;
      uniform float u_time;
      void main() {
        vec2 uv = v_uv;
        float wave = sin(uv.x * 12.0 + u_time * 1.5) * 0.02 + cos(uv.y * 8.0 + u_time * 0.9) * 0.015;
        vec3 deepTeal = vec3(0.07, 0.235, 0.227); // #123C3A
        vec3 ivoryTint = vec3(0.95, 0.933, 0.898); // #F2EEE5
        float rim = smoothstep(0.0, 0.15, uv.y) * (1.0 - smoothstep(0.85, 1.0, uv.y));
        float highlight = smoothstep(0.48, 0.52, uv.y + wave * 0.5);
        vec3 col = mix(deepTeal, ivoryTint, highlight * 0.18 + rim * 0.12);
        gl_FragColor = vec4(col, 0.12 + rim * 0.08);
      }
    `

    function createShader(glCtx: WebGLRenderingContext, type: number, src: string) {
      const shader = glCtx.createShader(type)
      if (!shader) return null
      glCtx.shaderSource(shader, src)
      glCtx.compileShader(shader)
      if (!glCtx.getShaderParameter(shader, glCtx.COMPILE_STATUS)) {
        glCtx.deleteShader(shader)
        return null
      }
      return shader
    }

    const vs = createShader(gl, gl.VERTEX_SHADER, vsSource)
    const fs = createShader(gl, gl.FRAGMENT_SHADER, fsSource)
    if (!vs || !fs) {
      setHasWebGL(false)
      return
    }

    const program = gl.createProgram()
    if (!program) {
      setHasWebGL(false)
      return
    }
    gl.attachShader(program, vs)
    gl.attachShader(program, fs)
    gl.linkProgram(program)

    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      setHasWebGL(false)
      return
    }

    gl.useProgram(program)

    const posBuffer = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, posBuffer)
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      gl.STATIC_DRAW,
    )

    const posAttr = gl.getAttribLocation(program, 'a_position')
    gl.enableVertexAttribArray(posAttr)
    gl.vertexAttribPointer(posAttr, 2, gl.FLOAT, false, 0, 0)

    const timeUniform = gl.getUniformLocation(program, 'u_time')
    let startTime = performance.now()
    let isRunning = true

    const resize = () => {
      if (!canvas) return
      const rect = canvas.getBoundingClientRect()
      canvas.width = rect.width * (window.devicePixelRatio || 1)
      canvas.height = rect.height * (window.devicePixelRatio || 1)
      gl?.viewport(0, 0, canvas.width, canvas.height)
    }
    resize()
    window.addEventListener('resize', resize)

    const render = () => {
      if (!isRunning || !gl) return
      const elapsed = (performance.now() - startTime) / 1000
      gl.uniform1f(timeUniform, elapsed)
      gl.drawArrays(gl.TRIANGLES, 0, 6)
      animFrameRef.current = requestAnimationFrame(render)
    }
    render()

    return () => {
      isRunning = false
      window.removeEventListener('resize', resize)
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
      if (gl && program) {
        gl.deleteProgram(program)
      }
    }
  }, [])

  return (
    <nav
      aria-label="Primary Navigation"
      className={`relative inline-flex items-center p-1.5 rounded-full backdrop-blur-xl bg-white/70 shadow-[0_8px_32px_0_rgba(18,60,58,0.12),inset_0_1px_1px_0_rgba(255,255,255,0.85)] border border-white/60 overflow-hidden ${className}`}
    >
      {/* Background WebGL Liquid Canvas */}
      {hasWebGL && (
        <canvas
          ref={canvasRef}
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 w-full h-full opacity-60 rounded-full"
        />
      )}

      {/* Navigation Items */}
      <div className="relative z-10 flex items-center gap-1.5">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `relative px-4 py-2 rounded-full font-label-md text-label-md transition-all duration-300 flex items-center gap-1.5 select-none ${
                isActive
                  ? 'bg-[#123C3A] text-[#F2EEE5] shadow-[0_4px_16px_rgba(18,60,58,0.35),inset_0_1px_1px_rgba(255,255,255,0.3)] font-semibold scale-[1.02]'
                  : 'text-[#29312F]/80 hover:text-[#123C3A] hover:bg-white/40'
              }`
            }
          >
            {item.icon && (
              <span className="material-symbols-outlined text-[17px]">{item.icon}</span>
            )}
            <span>{item.label}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  )
}

export default LiquidGlassNavbar

