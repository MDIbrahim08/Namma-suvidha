/**
 * LiquidGlassButton - Waterline / Liquid Glass Button Design System
 *
 * Designed with the exact Namma Suvidha palette:
 *   - Deep petrol teal: #123C3A
 *   - Warm ivory: #F2EEE5
 *   - Terracotta accent: #D18B55
 *   - Dark charcoal: #29312F
 *
 * Features:
 *   - Translucent glass surface with subtle inner specular highlight
 *   - Soft glass rim border (waterline reflection)
 *   - Liquid-inspired active/hover spring physics
 *   - Accessible keyboard focus rings
 *   - Semantic HTML button with loading / disabled states
 *   - Full support for variants: primary, secondary, outline, ghost, danger
 */

import React, { forwardRef } from 'react'

export interface LiquidGlassButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  fullWidth?: boolean
  loading?: boolean
  icon?: React.ReactNode
  iconRight?: React.ReactNode
}

export const LiquidGlassButton = forwardRef<HTMLButtonElement, LiquidGlassButtonProps>(
  (
    {
      children,
      variant = 'primary',
      size = 'md',
      fullWidth = false,
      loading = false,
      disabled = false,
      icon,
      iconRight,
      className = '',
      type = 'button',
      onClick,
      ...rest
    },
    ref,
  ) => {
    // Size mappings
    const sizeClasses = {
      sm: 'px-3 py-1.5 text-xs gap-1.5 min-h-[32px]',
      md: 'px-4 py-2 text-sm gap-2 min-h-[40px]',
      lg: 'px-6 py-3 text-base gap-2.5 min-h-[48px]',
    }[size]

    // Variant mappings using Namma Suvidha brand tokens and liquid-glass specular layers
    const variantClasses = {
      primary: `
        bg-[#123C3A] text-[#F2EEE5]
        shadow-[0_4px_16px_rgba(18,60,58,0.25),inset_0_1px_1px_rgba(255,255,255,0.35),inset_0_-1px_1px_rgba(0,0,0,0.25)]
        border border-white/20
        hover:bg-[#1a4f4d] hover:shadow-[0_6px_20px_rgba(18,60,58,0.35),inset_0_1px_2px_rgba(255,255,255,0.45)]
        active:scale-[0.98] active:bg-[#0f3230]
      `,
      secondary: `
        bg-white/70 text-[#123C3A] backdrop-blur-md
        shadow-[0_2px_10px_rgba(0,0,0,0.06),inset_0_1px_1px_rgba(255,255,255,0.9),inset_0_-1px_1px_rgba(0,0,0,0.05)]
        border border-white/80
        hover:bg-white/90 hover:shadow-[0_4px_14px_rgba(18,60,58,0.12)]
        active:scale-[0.98] active:bg-white/60
      `,
      outline: `
        bg-transparent text-[#123C3A] backdrop-blur-sm
        border border-[#123C3A]/30
        shadow-[inset_0_1px_1px_rgba(255,255,255,0.4)]
        hover:bg-[#123C3A]/10 hover:border-[#123C3A]/60
        active:scale-[0.98]
      `,
      ghost: `
        bg-transparent text-[#29312F]
        hover:bg-black/5 hover:text-[#123C3A]
        active:scale-[0.98]
      `,
      danger: `
        bg-[#ba1a1a] text-white
        shadow-[0_4px_14px_rgba(186,26,26,0.25),inset_0_1px_1px_rgba(255,255,255,0.3)]
        border border-white/20
        hover:bg-[#93000a] hover:shadow-[0_6px_18px_rgba(186,26,26,0.35)]
        active:scale-[0.98]
      `,
    }[variant]

    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled || loading}
        onClick={onClick}
        className={`
          relative inline-flex items-center justify-center font-medium rounded-full
          transition-all duration-200 select-none outline-none
          focus-visible:ring-2 focus-visible:ring-[#123C3A] focus-visible:ring-offset-2
          disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-none
          ${fullWidth ? 'w-full' : ''}
          ${sizeClasses}
          ${variantClasses}
          ${className}
        `}
        {...rest}
      >
        {/* Subtle Waterline Top Rim Specular Glare */}
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-2 top-0 h-[1px] bg-gradient-to-r from-transparent via-white/50 to-transparent opacity-70"
        />

        {/* Loading Spinner */}
        {loading && (
          <span
            className="material-symbols-outlined animate-spin text-[18px] flex-shrink-0"
            aria-hidden="true"
          >
            progress_activity
          </span>
        )}

        {/* Left Icon */}
        {!loading && icon && (
          <span className="inline-flex items-center justify-center flex-shrink-0" aria-hidden="true">
            {icon}
          </span>
        )}

        {/* Label */}
        <span className="truncate">{children}</span>

        {/* Right Icon */}
        {!loading && iconRight && (
          <span className="inline-flex items-center justify-center flex-shrink-0" aria-hidden="true">
            {iconRight}
          </span>
        )}
      </button>
    )
  },
)

LiquidGlassButton.displayName = 'LiquidGlassButton'

export default LiquidGlassButton

