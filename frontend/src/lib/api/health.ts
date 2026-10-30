import { apiClient } from './client'
import type { DatabaseHealthResponse, HealthResponse } from './types'

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>('/health')
  return data
}

export async function getDbHealth(): Promise<DatabaseHealthResponse> {
  const { data } = await apiClient.get<DatabaseHealthResponse>('/health/db')
  return data
}
