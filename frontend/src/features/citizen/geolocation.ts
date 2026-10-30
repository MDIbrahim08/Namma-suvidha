/**
 * Browser Geolocation wrapper for real-time citizen location detection.
 *
 * Strictly uses `navigator.geolocation.getCurrentPosition()` with:
 * - enableHighAccuracy: true
 * - timeout: 15000
 * - maximumAge: 0
 *
 * Never falls back to hardcoded Bengaluru or sample coordinates.
 */

import type { UserLocation } from '../../lib/api/discovery.types'

export type GeolocationErrorCode =
  | 'PERMISSION_DENIED'
  | 'POSITION_UNAVAILABLE'
  | 'TIMEOUT'
  | 'UNSUPPORTED'
  | 'INSECURE_ORIGIN'
  | 'UNKNOWN'

export class DeviceLocationError extends Error {
  readonly code: GeolocationErrorCode

  constructor(code: GeolocationErrorCode, message: string) {
    super(message)
    this.name = 'DeviceLocationError'
    this.code = code
  }
}

export const GEOLOCATION_OPTIONS: PositionOptions = {
  enableHighAccuracy: true,
  timeout: 15000,
  maximumAge: 0,
}

export function detectDeviceLocation(): Promise<UserLocation> {
  return new Promise((resolve, reject) => {
    if (typeof window !== 'undefined' && window.isSecureContext === false) {
      reject(
        new DeviceLocationError(
          'INSECURE_ORIGIN',
          'Browser location requires HTTPS or localhost. Open the app over localhost or a secure HTTPS tunnel.',
        ),
      )
      return
    }

    if (
      typeof navigator === 'undefined' ||
      !('geolocation' in navigator) ||
      !navigator.geolocation
    ) {
      reject(
        new DeviceLocationError(
          'UNSUPPORTED',
          'Geolocation is not supported by this browser or device.',
        ),
      )
      return
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracyMeters:
            typeof position.coords.accuracy === 'number'
              ? Math.round(position.coords.accuracy)
              : null,
        })
      },
      (geoError) => {
        // Standard GeolocationPositionError codes: 1 = PERMISSION_DENIED, 2 = POSITION_UNAVAILABLE, 3 = TIMEOUT
        if (geoError.code === 1) {
          reject(
            new DeviceLocationError(
              'PERMISSION_DENIED',
              'Location permission was denied. Please allow location access in your browser settings and try again.',
            ),
          )
          return
        }
        if (geoError.code === 2) {
          reject(
            new DeviceLocationError(
              'POSITION_UNAVAILABLE',
              'Current GPS position is unavailable. Check that device location services are turned on.',
            ),
          )
          return
        }
        if (geoError.code === 3) {
          reject(
            new DeviceLocationError(
              'TIMEOUT',
              'Location request timed out after 15 seconds. Move to an area with clearer GPS/network reception and retry.',
            ),
          )
          return
        }
        reject(
          new DeviceLocationError(
            'UNKNOWN',
            geoError.message || 'Unable to retrieve your current device location.',
          ),
        )
      },
      GEOLOCATION_OPTIONS,
    )
  })
}
