/**
 * Typed Axios client for OpenStreetMap public toilet discovery.
 *
 * Communicates with FastAPI `GET /api/v1/toilets/nearby` (also mounted at `/api/toilets/nearby`).
 */

import { apiClient } from './client'
import type { NearbyToiletQuery, NearbyToiletResponse } from './discovery.types'

export async function getNearbyToilets(params: NearbyToiletQuery): Promise<NearbyToiletResponse> {
  const { data } = await apiClient.get<NearbyToiletResponse>('/toilets/nearby', {
    params: {
      latitude: params.latitude,
      longitude: params.longitude,
      radius: params.radius ?? 10000,
    },
    timeout: 32_000,
  })
  return data
}
