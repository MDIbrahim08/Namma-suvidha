/**
 * Pure formatting helpers for OpenStreetMap toilet records.
 * Never fabricates names or addresses when OSM metadata is missing.
 */

import type { AddressInformation, NearbyToilet } from '../../../lib/api/discovery.types'

export function getDisplayName(toilet: NearbyToilet): string {
  if (toilet.name && toilet.name.trim().length > 0) {
    return toilet.name.trim()
  }
  return `Unnamed OSM Toilet (${toilet.osm_type} #${toilet.osm_id})`
}

export function formatAddress(address: AddressInformation): string | null {
  const parts = [address.street, address.city, address.postcode].filter((part): part is string =>
    Boolean(part && part.trim().length > 0),
  )
  return parts.length > 0 ? parts.join(', ') : null
}

export function formatDistance(distanceMeters: number, distanceKm: number): string {
  if (distanceMeters < 1000) {
    return `${distanceMeters} m`
  }
  return `${distanceKm.toFixed(2)} km (${distanceMeters} m)`
}

export function formatCoordinates(lat: number, lon: number): string {
  const latDir = lat >= 0 ? 'N' : 'S'
  const lonDir = lon >= 0 ? 'E' : 'W'
  return `${Math.abs(lat).toFixed(4)}° ${latDir}, ${Math.abs(lon).toFixed(4)}° ${lonDir}`
}
