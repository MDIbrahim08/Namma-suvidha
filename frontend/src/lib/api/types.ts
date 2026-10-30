/** Mirrors backend/app/schemas/common.py - keep in sync. */

export interface HealthResponse {
  status: string
  app: string
  env: string
  version: string
  timestamp: string
}

export interface DatabaseHealthResponse {
  connected: boolean
  postgis_available: boolean
  postgis_version: string | null
  error: string | null
}

export interface ErrorResponse {
  detail: string
  code: string
}

/** Normalised error shape produced by the Axios response interceptor. */
export interface ApiError {
  message: string
  status: number | null
  code: string
}
