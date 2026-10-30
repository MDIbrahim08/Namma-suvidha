import type { ReactNode } from 'react'

interface ModuleShellProps {
  title: string
  description: string
  owners: string
  plannedFeatures: string[]
  children?: ReactNode
}

/** Generic wrapper for module home/dashboard pages. Shows static, honest status only. */
export default function ModuleShell({
  title,
  description,
  owners,
  plannedFeatures,
  children,
}: ModuleShellProps) {
  return (
    <section className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold">{title}</h1>
        <p className="text-slate-700">{description}</p>
        <p className="text-sm text-slate-500">Owner(s): {owners}</p>
      </header>
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
        <h2 className="mb-2 font-semibold text-amber-800">Planned — Phase 1+</h2>
        <ul className="list-inside list-disc space-y-1 text-sm text-amber-900">
          {plannedFeatures.map((feature) => (
            <li key={feature}>{feature}</li>
          ))}
        </ul>
      </div>
      {children}
    </section>
  )
}
