import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as discoveryApi from '../../../lib/api/discovery'
import type { NearbyToiletResponse } from '../../../lib/api/discovery.types'
import { GEOLOCATION_OPTIONS } from '../geolocation'
import CitizenHome from './CitizenHome'

// Mock Leaflet map in jsdom to keep unit/integration tests deterministic and fast
vi.mock('../components/CitizenDiscoveryMap', () => ({
  default: ({
    userLocation,
    toilets,
  }: {
    userLocation: { latitude: number; longitude: number } | null
    toilets: Array<{ osm_id: number }>
  }) => (
    <div data-testid="citizen-osm-map">
      {userLocation
        ? `MAP_ORIGIN:${userLocation.latitude},${userLocation.longitude}`
        : 'MAP_NO_ORIGIN'}
      |MARKERS:{toilets.length}
    </div>
  ),
}))

const SAMPLE_DISCOVERY_RESPONSE: NearbyToiletResponse = {
  success: true,
  origin: {
    latitude: 13.0827,
    longitude: 80.2707,
  },
  radius_meters: 10000,
  total_results: 2,
  source: 'OpenStreetMap',
  results: [
    {
      osm_id: 501001,
      osm_type: 'node',
      name: 'Central Station Public Restroom',
      latitude: 13.0832,
      longitude: 80.2715,
      distance_meters: 103,
      distance_km: 0.1,
      address: {
        street: 'Poonamallee High Road',
        city: 'Chennai',
        postcode: '600003',
      },
      tags: {
        amenity: 'toilets',
        name: 'Central Station Public Restroom',
        fee: 'no',
        access: 'yes',
        wheelchair: 'yes',
        changing_table: 'yes',
      },
    },
    {
      osm_id: 501002,
      osm_type: 'way',
      name: null,
      latitude: 13.095,
      longitude: 80.285,
      distance_meters: 2065,
      distance_km: 2.07,
      address: {
        street: null,
        city: null,
        postcode: null,
      },
      tags: {
        amenity: 'toilets',
        fee: 'yes',
        access: 'permissive',
      },
    },
  ],
}

describe('CitizenHome — Real-Time GPS & OpenStreetMap Toilet Discovery', () => {
  const getNearbyToiletsSpy = vi.spyOn(discoveryApi, 'getNearbyToilets')
  const originalGeolocation = navigator.geolocation

  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(window, 'isSecureContext', {
      value: true,
      configurable: true,
    })
  })

  afterEach(() => {
    Object.defineProperty(navigator, 'geolocation', {
      value: originalGeolocation,
      configurable: true,
    })
  })

  it('6. does not use any hardcoded location fallback or call the backend before user action', () => {
    const getCurrentPositionMock = vi.fn()
    Object.defineProperty(navigator, 'geolocation', {
      value: { getCurrentPosition: getCurrentPositionMock },
      configurable: true,
    })

    render(<CitizenHome />)

    expect(screen.getByRole('heading', { name: 'Citizen' })).toBeInTheDocument()
    expect(screen.getByTestId('initial-discovery-prompt')).toBeInTheDocument()
    expect(screen.getByTestId('telemetry-coordinates')).toHaveTextContent(
      'GPS: Awaiting location permission',
    )
    // Verify no automatic geolocation prompt or hardcoded Bengaluru coordinates
    expect(getCurrentPositionMock).not.toHaveBeenCalled()
    expect(getNearbyToiletsSpy).not.toHaveBeenCalled()
    expect(screen.queryByText(/12\.9716/)).not.toBeInTheDocument()
    expect(screen.queryByText(/77\.5946/)).not.toBeInTheDocument()
  })

  it('1, 5, 27–31. retrieves real device GPS coordinates, passes exact coordinates to backend, and renders returned OSM toilets', async () => {
    const getCurrentPositionMock = vi.fn<Geolocation['getCurrentPosition']>((success) => {
      success({
        coords: {
          latitude: 13.0827,
          longitude: 80.2707,
          accuracy: 12.4,
          altitude: null,
          altitudeAccuracy: null,
          heading: null,
          speed: null,
          toJSON: () => ({}),
        },
        timestamp: Date.now(),
        toJSON: () => ({}),
      })
    })
    Object.defineProperty(navigator, 'geolocation', {
      value: { getCurrentPosition: getCurrentPositionMock },
      configurable: true,
    })
    getNearbyToiletsSpy.mockResolvedValueOnce(SAMPLE_DISCOVERY_RESPONSE)

    render(<CitizenHome />)

    fireEvent.click(
      screen.getByRole('button', { name: /Detect My Location & Find Nearby Toilets/i }),
    )

    await waitFor(() => {
      expect(getCurrentPositionMock).toHaveBeenCalledTimes(1)
    })

    // Verify exact high-accuracy geolocation options (Phase 3)
    expect(getCurrentPositionMock.mock.calls[0]?.[2]).toEqual(GEOLOCATION_OPTIONS)
    expect(GEOLOCATION_OPTIONS).toEqual({
      enableHighAccuracy: true,
      timeout: 15000,
      maximumAge: 0,
    })

    // Verify backend receives exact coordinates and default 10000m radius
    await waitFor(() => {
      expect(getNearbyToiletsSpy).toHaveBeenCalledWith({
        latitude: 13.0827,
        longitude: 80.2707,
        radius: 10000,
      })
    })

    // Verify user coordinates are displayed accurately
    await waitFor(() => {
      expect(screen.getByTestId('telemetry-coordinates')).toHaveTextContent(
        'GPS: 13.0827° N, 80.2707° E (±12m)',
      )
    })

    // Verify selected toilet card displays real OSM data
    const selectedCard = screen.getByTestId('selected-toilet-card')
    expect(selectedCard).toHaveTextContent('Central Station Public Restroom')
    expect(selectedCard).toHaveTextContent('OSM NODE #501001')
    expect(selectedCard).toHaveTextContent('103 m')
    expect(selectedCard).toHaveTextContent('Poonamallee High Road, Chennai, 600003')

    // Switch to Results list view and verify both named and unnamed OSM records render
    fireEvent.click(screen.getByRole('button', { name: /Results \(2\)/i }))

    const card1 = screen.getByTestId('toilet-card-501001')
    expect(card1).toHaveTextContent('Central Station Public Restroom')
    expect(card1).toHaveTextContent('103 m')

    const card2 = screen.getByTestId('toilet-card-501002')
    expect(card2).toHaveTextContent('Unnamed OSM Toilet (way #501002)')
    expect(card2).toHaveTextContent('2.07 km')
    expect(card2).toHaveTextContent('Address not specified in OpenStreetMap')

    // Switch to Details view and verify full OSM tags are preserved
    fireEvent.click(screen.getAllByRole('button', { name: /Details/i })[0])
    const details = screen.getByTestId('facility-details-cockpit')
    expect(details).toHaveTextContent('OSM NODE #501001')
    expect(details).toHaveTextContent('changing_table')
    expect(details).toHaveTextContent('wheelchair')
  })

  it('2. handles PERMISSION_DENIED (code 1) without calling backend or using fallback coordinates', async () => {
    const getCurrentPositionMock = vi.fn(
      (_success: PositionCallback, error?: PositionErrorCallback) => {
        error?.({
          code: 1,
          message: 'User denied Geolocation',
          PERMISSION_DENIED: 1,
          POSITION_UNAVAILABLE: 2,
          TIMEOUT: 3,
        })
      },
    )
    Object.defineProperty(navigator, 'geolocation', {
      value: { getCurrentPosition: getCurrentPositionMock },
      configurable: true,
    })

    render(<CitizenHome />)
    fireEvent.click(
      screen.getByRole('button', { name: /Detect My Location & Find Nearby Toilets/i }),
    )

    const banner = await screen.findByTestId('geolocation-error-banner')
    expect(banner).toHaveTextContent('PERMISSION_DENIED')
    expect(banner).toHaveTextContent('Location permission was denied')
    expect(getNearbyToiletsSpy).not.toHaveBeenCalled()
  })

  it('3. handles POSITION_UNAVAILABLE (code 2) with clear error message', async () => {
    const getCurrentPositionMock = vi.fn(
      (_success: PositionCallback, error?: PositionErrorCallback) => {
        error?.({
          code: 2,
          message: 'Position unavailable',
          PERMISSION_DENIED: 1,
          POSITION_UNAVAILABLE: 2,
          TIMEOUT: 3,
        })
      },
    )
    Object.defineProperty(navigator, 'geolocation', {
      value: { getCurrentPosition: getCurrentPositionMock },
      configurable: true,
    })

    render(<CitizenHome />)
    fireEvent.click(
      screen.getByRole('button', { name: /Detect My Location & Find Nearby Toilets/i }),
    )

    const banner = await screen.findByTestId('geolocation-error-banner')
    expect(banner).toHaveTextContent('POSITION_UNAVAILABLE')
    expect(banner).toHaveTextContent('Current GPS position is unavailable')
    expect(getNearbyToiletsSpy).not.toHaveBeenCalled()
  })

  it('4. handles TIMEOUT (code 3) with clear error message', async () => {
    const getCurrentPositionMock = vi.fn(
      (_success: PositionCallback, error?: PositionErrorCallback) => {
        error?.({
          code: 3,
          message: 'Timeout expired',
          PERMISSION_DENIED: 1,
          POSITION_UNAVAILABLE: 2,
          TIMEOUT: 3,
        })
      },
    )
    Object.defineProperty(navigator, 'geolocation', {
      value: { getCurrentPosition: getCurrentPositionMock },
      configurable: true,
    })

    render(<CitizenHome />)
    fireEvent.click(
      screen.getByRole('button', { name: /Detect My Location & Find Nearby Toilets/i }),
    )

    const banner = await screen.findByTestId('geolocation-error-banner')
    expect(banner).toHaveTextContent('TIMEOUT')
    expect(banner).toHaveTextContent('Location request timed out after 15 seconds')
    expect(getNearbyToiletsSpy).not.toHaveBeenCalled()
  })
})
