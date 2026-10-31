/**
 * Typed Axios client for OpenStreetMap public toilet discovery.
 *
 * Communicates with FastAPI `GET /api/v1/toilets/nearby` (also mounted at `/api/toilets/nearby`).
 */

import { apiClient } from './client'
import { getFallbackNearbyToilets } from './bbmpFallback'
import type { NearbyToiletQuery, NearbyToiletResponse } from './discovery.types'

export async function getNearbyToilets(params: NearbyToiletQuery): Promise<NearbyToiletResponse> {
  try {
    const { data } = await apiClient.get<NearbyToiletResponse>('/toilets/nearby', {
      params: {
        latitude: params.latitude,
        longitude: params.longitude,
        radius: params.radius ?? 10000,
      },
      timeout: 3500,
    })

    if (data && data.results && data.results.length > 0) {
      return data
    }
    return getFallbackNearbyToilets(params.latitude, params.longitude, params.radius ?? 30000)
  } catch (err) {
    console.info('Backend unreachable, using embedded BBMP municipal dataset fallback:', err)
    return getFallbackNearbyToilets(params.latitude, params.longitude, params.radius ?? 30000)
  }
}
