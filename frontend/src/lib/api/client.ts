import axios, { AxiosError } from 'axios'
import { env } from '../../config/env'
import type { ApiError, ErrorResponse } from './types'

export const apiClient = axios.create({
  baseURL: `${env.apiBaseUrl}/api/v1`,
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
})

// AUTH TOKEN INTERCEPTOR - OWNER: Shabaz (Phase 1)
// Attach the Supabase access token here via apiClient.interceptors.request.use(...).
// Intentionally not implemented in Phase 0.

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ErrorResponse>) => {
    const normalised: ApiError = {
      message: error.response?.data?.detail ?? error.message ?? 'Unknown error',
      status: error.response?.status ?? null,
      code: error.response?.data?.code ?? error.code ?? 'network_error',
    }
    return Promise.reject(normalised)
  },
)
