import { useEffect, useState } from 'react'
import { getDbHealth, getHealth } from '../../lib/api/health'
import type { ApiError, DatabaseHealthResponse, HealthResponse } from '../../lib/api/types'

type Result<T> = { state: 'loading' } | { state: 'ok'; data: T } | { state: 'error'; error: string }

function toMessage(err: unknown): string {
  return (err as ApiError)?.message ?? 'Unknown error'
}

function Dot({ ok }: { ok: boolean | null }) {
  const colour = ok === null ? 'bg-slate-300' : ok ? 'bg-emerald-500' : 'bg-red-500'
  return <span className={`inline-block h-2.5 w-2.5 rounded-full ${colour}`} aria-hidden />
}

/** Shows live backend + database health. The only dynamic data in Phase 0. */
export default function BackendStatus() {
  const [api, setApi] = useState<Result<HealthResponse>>({ state: 'loading' })
  const [db, setDb] = useState<Result<DatabaseHealthResponse>>({ state: 'loading' })

  useEffect(() => {
    getHealth()
      .then((data) => setApi({ state: 'ok', data }))
      .catch((err) => setApi({ state: 'error', error: toMessage(err) }))
    getDbHealth()
      .then((data) => setDb({ state: 'ok', data }))
      .catch((err) => setDb({ state: 'error', error: toMessage(err) }))
  }, [])

  return (
    <div
      className="rounded-lg border border-slate-200 bg-white p-4 text-sm"
      data-testid="backend-status"
    >
      <h2 className="mb-3 font-semibold">System status (live)</h2>
      <ul className="space-y-2">
        <li className="flex items-center gap-2">
          <Dot ok={api.state === 'loading' ? null : api.state === 'ok'} />
          {api.state === 'loading' && 'API: checking…'}
          {api.state === 'ok' &&
            `API: reachable — ${api.data.app} v${api.data.version} (${api.data.env})`}
          {api.state === 'error' && `API: not reachable — ${api.error}`}
        </li>
        <li className="flex items-center gap-2">
          <Dot ok={db.state === 'loading' ? null : db.state === 'ok' && db.data.connected} />
          {db.state === 'loading' && 'Database: checking…'}
          {db.state === 'ok' &&
            (db.data.connected
              ? `Database: connected — PostGIS ${db.data.postgis_version ?? 'not available'}`
              : `Database: not connected — ${db.data.error ?? 'unknown error'}`)}
          {db.state === 'error' && `Database: status unavailable — ${db.error}`}
        </li>
      </ul>
    </div>
  )
}
