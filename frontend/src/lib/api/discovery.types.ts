/**
 * TypeScript interfaces for real-time citizen GPS location detection
 * and OpenStreetMap public toilet discovery (`/api/v1/toilets/nearby`).
 *
 * OWNER: Ibrahim (integration) + Gaurish (UI consumer)
 */

export interface UserLocation {
  latitude: number
  longitude: number
  accuracyMeters?: number | null
}

export interface AddressInformation {
  street: string | null
  city: string | null
  postcode: string | null
}

export type OSMMetadata = Record<string, string>

export interface NearbyToilet {
  osm_id: number
  osm_type: 'node' | 'way' | 'relation'
  name: string | null
  latitude: number
  longitude: number
  distance_meters: number
  distance_km: number
  address: AddressInformation
  tags: OSMMetadata
}

export interface NearbyToiletResponse {
  success: boolean
  origin: {
    latitude: number
    longitude: number
  }
  radius_meters: number
  total_results: number
  source: 'OpenStreetMap'
  results: NearbyToilet[]
}

export interface NearbyToiletQuery {
  latitude: number
  longitude: number
  radius?: number
}
