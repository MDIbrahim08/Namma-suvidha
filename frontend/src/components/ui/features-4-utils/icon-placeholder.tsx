import React from "react"

export interface IconPlaceholderProps {
  lucide?: string
  tabler?: string
  hugeicons?: string
  phosphor?: string
  remixicon?: string
  className?: string
  size?: number | string
  [key: string]: any
}

// Maps icon names to Material Symbols font ligature or pure SVG fallback
const symbolMap: Record<string, string> = {
  Group: 'group',
  MessageCircle: 'chat',
  History: 'history',
  Flashlight: 'bolt',
  Bot: 'smart_toy',
  Timer: 'timer',
  ShieldCheck: 'verified_user',
  Key: 'vpn_key',
  Fingerprint: 'fingerprint',
  Braces: 'code',
  GitBranch: 'alt_route',
}

export function IconPlaceholder({ lucide, className, size, ...props }: IconPlaceholderProps) {
  const symbol = (lucide && symbolMap[lucide]) || 'star'
  return (
    <span
      className={`material-symbols-outlined inline-flex items-center justify-center select-none ${className || ''}`}
      style={size ? { fontSize: typeof size === 'number' ? `${size}px` : size } : undefined}
      {...props}
    >
      {symbol}
    </span>
  )
}
