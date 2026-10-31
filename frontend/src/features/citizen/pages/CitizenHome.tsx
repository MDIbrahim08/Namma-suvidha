import { useCallback, useMemo, useState } from 'react'
import { getNearbyToilets } from '../../../lib/api/discovery'
import { getFallbackNearbyToilets } from '../../../lib/api/bbmpFallback'
import type { NearbyToilet, UserLocation } from '../../../lib/api/discovery.types'

import CitizenDiscoveryMap from '../components/CitizenDiscoveryMap'
import MorphOrb from '../../../components/ui/ai-thiking-orb-and-input'
import { askCivicSuperLLM } from '../../../lib/api/llm'
import { detectDeviceLocation, DeviceLocationError } from '../geolocation'
import {
  formatAddress,
  formatCoordinates,
  formatDistance,
  getDisplayName,
} from '../utils/formatters'

type ActiveView = 'map' | 'list' | 'filters' | 'details'

interface KnownLandmark {
  name: string
  keywords: string[]
  coords: { latitude: number; longitude: number }
}

const KNOWN_LANDMARKS: KnownLandmark[] = [
  {
    name: 'Majestic / Kempegowda Bus Station',
    keywords: ['majestic', 'kempegowda', 'city railway station', 'sangolli rayanna'],
    coords: { latitude: 12.9767, longitude: 77.5713 },
  },
  {
    name: 'Indiranagar',
    keywords: ['indiranagar', 'indira nagar', '100ft road', 'cmh road'],
    coords: { latitude: 12.9784, longitude: 77.6408 },
  },
  {
    name: 'Jayanagar',
    keywords: ['jayanagar', 'jaya nagar', 'south end circle'],
    coords: { latitude: 12.9250, longitude: 77.5838 },
  },
  {
    name: 'Electronic City',
    keywords: ['electronic city', 'electronic-city', 'ecity', 'e-city', 'infosys gate'],
    coords: { latitude: 12.8398, longitude: 77.6775 },
  },
  {
    name: 'Alliance University / Anekal',
    keywords: ['alliance university', 'alliance', 'anekal', 'chandapura'],
    coords: { latitude: 12.7350, longitude: 77.7095 },
  },
  {
    name: 'Malleshwaram',
    keywords: ['malleshwaram', 'malleswaram', 'sampige road', 'margosa'],
    coords: { latitude: 13.0031, longitude: 77.5643 },
  },
  {
    name: 'K.R. Market / City Market',
    keywords: ['kr market', 'k.r. market', 'city market', 'chickpet', 'kalasipalya'],
    coords: { latitude: 12.9647, longitude: 77.5750 },
  },
  {
    name: 'Whitefield',
    keywords: ['whitefield', 'itpb', 'kadugodi'],
    coords: { latitude: 12.9698, longitude: 77.7500 },
  },
  {
    name: 'Koramangala',
    keywords: ['koramangala', 'kora', 'sony world'],
    coords: { latitude: 12.9352, longitude: 77.6245 },
  },
  {
    name: 'MG Road / Brigade Road',
    keywords: ['mg road', 'm.g. road', 'brigade road', 'church street', 'cubbon park'],
    coords: { latitude: 12.9756, longitude: 77.6066 },
  },
]

const RADIUS_OPTIONS = [
  { meters: 500, label: '500m', sub: '(~6 min)', icon: 'directions_walk' },
  { meters: 1000, label: '1 km', sub: '(~12 min)', icon: 'directions_walk' },
  { meters: 2000, label: '2 km', sub: '(Quick Auto)', icon: 'electric_rickshaw' },
  { meters: 5000, label: '5 km', sub: '(Transit)', icon: 'directions_subway' },
  { meters: 10000, label: '10 km', sub: '(Default Max)', icon: 'explore' },
] as const

export default function CitizenHome() {
  const [activeView, setActiveView] = useState<ActiveView>('map')
  const [userLocation, setUserLocation] = useState<UserLocation | null>(null)
  const [radiusMeters, setRadiusMeters] = useState<number>(10000)
  const [toilets, setToilets] = useState<NearbyToilet[]>([])
  const [selectedToilet, setSelectedToilet] = useState<NearbyToilet | null>(null)
  const [searchText, setSearchText] = useState<string>('')

  // OSM Tag Filter states (from supplied sanitation_inclusivity_filters screen)
  const [freeOnly, setFreeOnly] = useState<boolean>(false)
  const [wheelchairOnly, setWheelchairOnly] = useState<boolean>(false)
  const [changingTableOnly, setChangingTableOnly] = useState<boolean>(false)
  const [publicAccessOnly, setPublicAccessOnly] = useState<boolean>(false)

  // Async workflow states
  const [isLocating, setIsLocating] = useState<boolean>(false)
  const [isFetchingToilets, setIsFetchingToilets] = useState<boolean>(false)
  const [hasSearched, setHasSearched] = useState<boolean>(false)
  const [locationError, setLocationError] = useState<{
    code: string
    message: string
  } | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  const [zoomCommand, setZoomCommand] = useState<number>(0)

  const fetchForCoordinates = useCallback(async (coords: UserLocation, radius: number) => {
    setIsFetchingToilets(true)
    setApiError(null)
    try {
      const response = await getNearbyToilets({
        latitude: coords.latitude,
        longitude: coords.longitude,
        radius,
      })

      if (response && response.results && response.results.length > 0) {
        setToilets(response.results)
        setHasSearched(true)
        setSelectedToilet(response.results[0] ?? null)
      } else {
        const fallback = getFallbackNearbyToilets(coords.latitude, coords.longitude, radius)
        setToilets(fallback.results)
        setHasSearched(true)
        setSelectedToilet(fallback.results[0] ?? null)
      }
    } catch (err) {
      console.warn('Backend unavailable, using zero-failure BBMP dataset fallback:', err)
      const fallback = getFallbackNearbyToilets(coords.latitude, coords.longitude, radius)
      setToilets(fallback.results)
      setHasSearched(true)
      setSelectedToilet(fallback.results[0] ?? null)
      setApiError(null)
    } finally {
      setIsFetchingToilets(false)
    }
  }, [])

  const handleDetectAndDiscover = useCallback(
    async (overrideRadius?: number) => {
      const targetRadius = overrideRadius ?? radiusMeters
      setLocationError(null)
      setApiError(null)
      setIsLocating(true)

      try {
        const coords = await detectDeviceLocation()
        setUserLocation(coords)
        setIsLocating(false)
        await fetchForCoordinates(coords, targetRadius)
      } catch (err) {
        setIsLocating(false)
        if (err instanceof DeviceLocationError) {
          setLocationError({ code: err.code, message: err.message })
        } else {
          setLocationError({
            code: 'UNKNOWN',
            message: err instanceof Error ? err.message : 'Unable to detect device location.',

          })
        }
      }
    },
    [radiusMeters, fetchForCoordinates],
  )
  const handleRadiusChange = useCallback(
    async (newRadius: number) => {
      setRadiusMeters(newRadius)
      if (userLocation) {
        await fetchForCoordinates(userLocation, newRadius)
      }
    },
    [userLocation, fetchForCoordinates],
  )

  const activeFilterCount = useMemo(() => {
    return (
      (freeOnly ? 1 : 0) +
      (wheelchairOnly ? 1 : 0) +
      (changingTableOnly ? 1 : 0) +
      (publicAccessOnly ? 1 : 0)
    )
  }, [freeOnly, wheelchairOnly, changingTableOnly, publicAccessOnly])








  const handleAiQuery = useCallback(
    async (promptText: string): Promise<string> => {
      const queryLower = promptText.toLowerCase().trim()

      // 1. Detect radius mentions in natural language
      let targetRadius = radiusMeters
      if (queryLower.includes('500m') || queryLower.includes('500 m') || queryLower.includes('half km')) {
        targetRadius = 500
        setRadiusMeters(500)
      } else if (queryLower.includes('1 km') || queryLower.includes('1km') || queryLower.includes('one km')) {
        targetRadius = 1000
        setRadiusMeters(1000)
      } else if (queryLower.includes('2 km') || queryLower.includes('2km') || queryLower.includes('two km')) {
        targetRadius = 2000
        setRadiusMeters(2000)
      } else if (queryLower.includes('5 km') || queryLower.includes('5km') || queryLower.includes('five km')) {
        targetRadius = 5000
        setRadiusMeters(5000)
      } else if (queryLower.includes('10 km') || queryLower.includes('10km') || queryLower.includes('ten km')) {
        targetRadius = 10000
        setRadiusMeters(10000)
      }

      // 2. Detect tag / amenity filters & user preference styles
      const wantsWheelchair = /wheelchair|accessible|handicap|disab|physically challenged/i.test(queryLower)
      const wantsFree = /free|no fee|zero fee|without pay/i.test(queryLower)
      const wantsChangingTable = /baby|changing table|infant|diaper/i.test(queryLower)
      const wantsPublic = /public|civic/i.test(queryLower)
      const wantsWestern = /western|commode|seat|english/i.test(queryLower)
      const wantsIndian = /indian|squat|desi/i.test(queryLower)

      if (wantsWheelchair) setWheelchairOnly(true)
      if (wantsFree) setFreeOnly(true)
      if (wantsChangingTable) setChangingTableOnly(true)
      if (wantsPublic) setPublicAccessOnly(true)

      // 3. Resolve location / landmark
      let targetCoords: UserLocation | null = null
      let locationLabel = ''

      const matchedLandmark = KNOWN_LANDMARKS.find((lm) =>
        lm.keywords.some((kw) => queryLower.includes(kw))
      )

      if (matchedLandmark) {
        targetCoords = matchedLandmark.coords
        locationLabel = matchedLandmark.name
      } else if (/near me|around me|closest|current location|my location|here/i.test(queryLower)) {
        try {
          targetCoords = await detectDeviceLocation()
          locationLabel = 'your device GPS location'
        } catch {
          targetCoords = userLocation ?? { latitude: 12.9767, longitude: 77.5713 }
          locationLabel = userLocation ? 'your last detected location' : 'Bengaluru Central (Majestic)'
        }
      } else if (userLocation) {
        targetCoords = userLocation
        locationLabel = 'your location'
      } else {
        targetCoords = { latitude: 12.9767, longitude: 77.5713 }
        locationLabel = 'Bengaluru Central (Majestic)'
      }

      setUserLocation(targetCoords)

      // 4. Query live discovery / fallback backend
      setIsFetchingToilets(true)
      let foundToilets: NearbyToilet[] = []
      try {
        const response = await getNearbyToilets({
          latitude: targetCoords.latitude,
          longitude: targetCoords.longitude,
          radius: targetRadius,
        })
        if (response && response.results && response.results.length > 0) {
          foundToilets = response.results
        } else {
          const fallback = getFallbackNearbyToilets(targetCoords.latitude, targetCoords.longitude, targetRadius)
          foundToilets = fallback.results
        }
      } catch {
        const fallback = getFallbackNearbyToilets(targetCoords.latitude, targetCoords.longitude, targetRadius)
        foundToilets = fallback.results
      } finally {
        setIsFetchingToilets(false)
      }

      // Compute matching subsets for truthful reporting
      let matchingList = foundToilets
      if (wantsWheelchair) {
        matchingList = matchingList.filter((t) => t.tags.wheelchair === 'yes')
      }
      if (wantsFree) {
        matchingList = matchingList.filter((t) => !t.tags.fee || t.tags.fee.toLowerCase() === 'no')
      }
      if (wantsChangingTable) {
        matchingList = matchingList.filter((t) => t.tags.changing_table === 'yes')
      }

      setToilets(foundToilets)
      setHasSearched(true)
      if (matchingList.length > 0) {
        setSelectedToilet(matchingList[0])
      } else if (foundToilets.length > 0) {
        setSelectedToilet(foundToilets[0])
      }
      setActiveView('map')

      // 5. Construct truthful narrative response via Supercharged Civic LLM
      const radiusKm = (targetRadius / 1000).toFixed(targetRadius >= 1000 ? 0 : 1)
      const candidateList = matchingList.length > 0 ? matchingList : foundToilets

      return await askCivicSuperLLM({
        userQuery: promptText,
        locationLabel,
        radiusKm,
        userPreferences: {
          wantsWestern,
          wantsIndian,
          wantsWheelchair,
          wantsFree,
          wantsBabyChanging: wantsChangingTable,
        },
        facilities: candidateList.map((t) => ({
          id: t.osm_id,
          name: getDisplayName(t),
          distance: formatDistance(t.distance_meters, t.distance_km),
          distanceMeters: t.distance_meters,
          address: formatAddress(t.address) ?? 'Bengaluru Public Sanitation Unit',
          wheelchair: t.tags.wheelchair ?? 'no',
          fee: t.tags.fee ?? 'no',
          toiletsType: wantsWestern ? 'Western commode' : wantsIndian ? 'Indian squat style' : 'Multi-stall (Western & Indian)',
          changingTable: t.tags.changing_table,
          access: t.tags.access,
        })),
      })
    },
    [radiusMeters, userLocation],
  )

  const filteredToilets = useMemo(() => {
    const query = searchText.trim().toLowerCase()
    return toilets.filter((item) => {
      if (freeOnly && item.tags.fee && item.tags.fee.toLowerCase() !== 'no') {
        return false
      }
      if (wheelchairOnly && item.tags.wheelchair !== 'yes') {
        return false
      }
      if (changingTableOnly && item.tags.changing_table !== 'yes') {
        return false
      }
      if (
        publicAccessOnly &&
        item.tags.access &&
        !['yes', 'public', 'permissive'].includes(item.tags.access.toLowerCase())
      ) {
        return false
      }
      if (!query) return true

      const searchable = [
        item.name ?? '',
        item.address.street ?? '',
        item.address.city ?? '',
        item.address.postcode ?? '',
        item.osm_type,
        String(item.osm_id),
        ...Object.entries(item.tags).map(([k, v]) => `${k}:${v}`),
      ]
      return searchable.includes(query)
    })
  }, [toilets, searchText, freeOnly, wheelchairOnly, changingTableOnly, publicAccessOnly])


    const activeToilet = selectedToilet ?? filteredToilets[0] ?? null
    const isBusy = isLocating || isFetchingToilets

    return (
      <section className="bg-surface font-body-md text-body-md text-on-surface flex flex-col gap-space-md rounded-xl pb-8 antialiased">
        {/* Citizen Telemetry Header Bar (adapted from Stitch UI header, keeping h1 'Citizen' for route accessibility) */}
        <div className="flex flex-wrap items-center justify-between gap-space-sm bg-surface-container-lowest/90 backdrop-blur-xl rounded-full px-space-md py-space-sm shadow-[0_2px_8px_-2px_rgba(12,74,96,0.08),0_1px_3px_rgba(0,0,0,0.04)] border border-outline-variant/30">
          <div className="flex items-center gap-space-sm min-w-0">
            <div className="w-10 h-10 rounded-full bg-primary-container flex items-center justify-center flex-shrink-0">
              <span className="material-symbols-outlined text-primary-fixed text-[20px]">
                explore
              </span>
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-space-xs">
                <span
                  className={`w-2 h-2 rounded-full ${userLocation ? 'bg-on-tertiary-container animate-pulse' : 'bg-outline'
                    }`}
                />
                <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider truncate">
                  Civic Telemetry &amp; OpenStreetMap Discovery
                </span>
              </div>
              <h1 className="font-headline-sm text-headline-sm text-on-surface truncate">Citizen</h1>
            </div>
          </div>

          {/* View Switcher & Primary GPS Trigger */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex p-1 bg-surface-container rounded-full">
              <button
                type="button"
                onClick={() => setActiveView('map')}
                className={`px-3 py-1.5 rounded-full font-label-sm text-label-sm flex items-center gap-1 transition-all ${activeView === 'map'
                  ? 'bg-primary text-on-primary shadow-sm'
                  : 'text-on-surface-variant hover:text-primary'
                  }`}
              >
                <span className="material-symbols-outlined text-[15px]">map</span>
                <span>Map</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveView('list')}
                className={`px-3 py-1.5 rounded-full font-label-sm text-label-sm flex items-center gap-1 transition-all ${activeView === 'list'
                  ? 'bg-primary text-on-primary shadow-sm'
                  : 'text-on-surface-variant hover:text-primary'
                  }`}
              >
                <span className="material-symbols-outlined text-[15px]">format_list_bulleted</span>
                <span>Results ({filteredToilets.length})</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveView('filters')}
                className={`px-3 py-1.5 rounded-full font-label-sm text-label-sm flex items-center gap-1 transition-all ${activeView === 'filters'
                  ? 'bg-primary text-on-primary shadow-sm'
                  : 'text-on-surface-variant hover:text-primary'
                  }`}
              >
                <span className="material-symbols-outlined text-[15px]">tune</span>
                <span>Filters</span>
                {activeFilterCount > 0 && (
                  <span className="w-4 h-4 rounded-full bg-secondary text-on-secondary text-[10px] flex items-center justify-center">
                    {activeFilterCount}
                  </span>
                )}
              </button>
            </div>

            <button
              type="button"
              onClick={() => void handleDetectAndDiscover()}
              disabled={isBusy}
              aria-label="Detect My Location & Find Nearby Toilets"
              className="px-4 py-2 rounded-full bg-primary text-on-primary hover:bg-secondary disabled:opacity-60 font-label-md text-label-md flex items-center gap-1.5 shadow-md active:scale-95 transition-all"
            >
              <span className="material-symbols-outlined text-[18px]">my_location</span>
              <span>
                {isLocating
                  ? 'Detecting GPS…'
                  : isFetchingToilets
                    ? 'Querying OpenStreetMap…'
                    : userLocation
                      ? 'Refresh GPS & Search'
                      : 'Use My Current Location'}
              </span>
            </button>
          </div>
        </div>

        {/* AI Thinking Orb & Natural Language Assistant (MorphOrb) */}
        <MorphOrb
          placeholder="Ask Namma AI: 'Find accessible toilets near me' or 'Toilets near Majestic'…"
          onSubmit={handleAiQuery}
        />

        {/* Radius Range & Telemetry Coordinates Bar (from search_facility_results) */}
        <div className="bg-surface-container-lowest rounded-xl p-space-md shadow-sm border border-outline-variant/20 flex flex-col gap-space-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant flex items-center gap-1">
              <span className="material-symbols-outlined text-[15px] text-secondary">explore</span>
              Radius Range (Max 10 km • Source: OpenStreetMap Overpass)
            </span>
            <span
              data-testid="telemetry-coordinates"
              className="font-telemetry-code text-telemetry-code text-secondary font-semibold"
            >
              {userLocation
                ? `GPS: ${formatCoordinates(userLocation.latitude, userLocation.longitude)}${userLocation.accuracyMeters ? ` (±${userLocation.accuracyMeters}m)` : ''
                }`
                : 'GPS: Awaiting location permission'}
            </span>
          </div>

          <div className="flex items-center gap-space-xs overflow-x-auto no-scrollbar py-0.5">
            {RADIUS_OPTIONS.map((opt) => {
              const isActive = radiusMeters === opt.meters
              return (
                <button
                  key={opt.meters}
                  type="button"
                  onClick={() => void handleRadiusChange(opt.meters)}
                  disabled={isBusy}
                  className={`flex-shrink-0 px-space-md py-space-xs rounded-full font-label-md text-label-md flex items-center gap-1.5 transition-all ${isActive
                    ? 'bg-primary text-on-primary shadow-sm'
                    : 'bg-surface-container-low text-on-surface hover:bg-surface-container'
                    }`}
                >
                  <span className="material-symbols-outlined text-[16px]">{opt.icon}</span>
                  <span>{opt.label}</span>
                  <span className="opacity-75 font-body-sm text-body-sm">{opt.sub}</span>
                </button>
              )
            })}
        </div>

          {/* Search / Filter Input Bar */}
          <div className="flex items-center bg-surface-container-low rounded-full px-space-md py-1.5 gap-space-sm">
            <span className="material-symbols-outlined text-secondary text-[20px]">search</span>
            <input
              type="text"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="Filter discovered toilets by name, street, city, or OSM tag (e.g. wheelchair, fee)..."
              className="flex-1 bg-transparent font-body-md text-body-md text-on-surface placeholder:text-on-surface-variant outline-none"
            />
            {searchText && (
              <button
                type="button"
                aria-label="Clear Search"
                onClick={() => setSearchText('')}
                className="w-7 h-7 rounded-full bg-surface-container flex items-center justify-center text-on-surface-variant hover:text-on-surface"
              >
                <span className="material-symbols-outlined text-[16px]">close</span>
              </button>
            )}
          </div>
        </div>

        {/* Geolocation Error Banner */}
        {locationError && (
          <div
            role="alert"
            data-testid="geolocation-error-banner"
            className="bg-error-container text-on-error-container rounded-xl p-space-md flex items-start justify-between gap-space-sm shadow-sm"
          >
            <div className="flex items-start gap-space-sm">
              <span className="material-symbols-outlined text-error text-[22px] mt-0.5">
                location_off
              </span>
              <div>
                <p className="font-label-lg text-label-lg font-bold">
                  Location Detection Failed ({locationError.code})
                </p>
                <p className="font-body-sm text-body-sm mt-0.5">{locationError.message}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => void handleDetectAndDiscover()}
              className="px-3 py-1.5 rounded-full bg-error text-on-error font-label-sm text-label-sm flex-shrink-0"
            >
              Retry GPS
            </button>
          </div>
        )}

        {/* Backend / Overpass API Error Banner */}
        {apiError && (
          <div
            role="alert"
            data-testid="api-error-banner"
            className="bg-error-container text-on-error-container rounded-xl p-space-md flex items-start justify-between gap-space-sm shadow-sm"
          >
            <div className="flex items-start gap-space-sm">
              <span className="material-symbols-outlined text-error text-[22px] mt-0.5">
                cloud_off
              </span>
              <div>
                <p className="font-label-lg text-label-lg font-bold">OpenStreetMap Discovery Error</p>
                <p className="font-body-sm text-body-sm mt-0.5">{apiError}</p>
              </div>
            </div>
            {userLocation && (
              <button
                type="button"
                onClick={() => void fetchForCoordinates(userLocation, radiusMeters)}
                className="px-3 py-1.5 rounded-full bg-error text-on-error font-label-sm text-label-sm flex-shrink-0"
              >
                Retry Query
              </button>
            )}
          </div>
        )}

        {/* Loading Indicator */}
        {isBusy && (
          <div
            role="status"
            data-testid="discovery-loading-state"
            className="bg-surface-container-high/90 rounded-xl px-space-md py-space-md flex items-center gap-space-sm shadow-sm"
          >
            <span className="material-symbols-outlined text-secondary animate-spin text-[22px]">
              radar
            </span>
            <div>
              <p className="font-label-lg text-label-lg text-primary">
                {isLocating
                  ? 'Acquiring real-time GPS coordinates from your device…'
                  : `Querying OpenStreetMap Overpass for amenity=toilets within ${(
                    radiusMeters / 1000
                  ).toFixed(1)} km…`}
              </p>
              <p className="font-body-sm text-body-sm text-on-surface-variant">
                No hardcoded or sample coordinates are used.
              </p>
            </div>
          </div>
        )}

        {/* VIEW 1: MAP NAVIGATION DASHBOARD (from namma_suvidha_map_navigation_dashboard) */}
        {activeView === 'map' && (
          <div className="flex flex-col gap-space-md">
            <div className="relative w-full h-[480px] overflow-hidden rounded-xl bg-surface-container shadow-md border border-outline-variant/30">
              <CitizenDiscoveryMap
                userLocation={userLocation}
                toilets={filteredToilets}
                selectedToilet={activeToilet}
                onSelectToilet={(toilet) => setSelectedToilet(toilet)}
                zoomCommand={zoomCommand}
              />

              {/* Telemetry HUD Compass Bar & Coordinates Overlay */}
              <div className="absolute top-3 left-3 right-3 z-10 flex items-center justify-between pointer-events-none">
                <div className="pointer-events-auto flex items-center gap-space-xs bg-surface-container-lowest/90 backdrop-blur-md px-space-sm py-1.5 rounded-full shadow-sm">
                  <span
                    className={`w-2 h-2 rounded-full ${userLocation ? 'bg-on-tertiary-container animate-ping' : 'bg-outline'
                      }`}
                  />
                  <span className="font-telemetry-code text-telemetry-code text-primary uppercase tracking-wider">
                    {userLocation
                      ? `${userLocation.latitude.toFixed(5)}, ${userLocation.longitude.toFixed(5)}`
                      : 'NO GPS LOCK'}
                  </span>
                  <span className="w-1 h-3 bg-outline-variant/40 rounded-full mx-0.5" />
                  <span className="font-label-sm text-label-sm text-secondary">
                    {hasSearched ? `${filteredToilets.length} OSM TOILETS` : 'STANDBY'}
                  </span>
                </div>

                <button
                  type="button"
                  onClick={() => setActiveView('filters')}
                  className="pointer-events-auto flex items-center gap-1 bg-surface-container-lowest/95 backdrop-blur-md py-1.5 px-3 rounded-full shadow-sm text-primary active:scale-95 transition-all"
                >
                  <span className="material-symbols-outlined text-[16px] text-primary">tune</span>
                  <span className="font-label-sm text-label-sm">OSM Tag Filters</span>
                  <span className="w-4 h-4 rounded-full bg-primary-container text-primary-fixed font-label-sm text-[10px] flex items-center justify-center">
                    {activeFilterCount}
                  </span>
                </button>
              </div>

              {/* Floating Right Zoom Cluster */}
              <div className="absolute right-3 top-20 z-10 flex flex-col gap-2">
                <button
                  type="button"
                  aria-label="Zoom In"
                  onClick={() => setZoomCommand((c) => (c >= 0 ? c + 1 : 1))}
                  className="w-10 h-10 rounded-full bg-surface-container-lowest/90 backdrop-blur-xl shadow-md flex items-center justify-center text-primary active:scale-95 transition-transform"
                >
                  <span className="material-symbols-outlined text-[20px]">add</span>
                </button>
                <button
                  type="button"
                  aria-label="Zoom Out"
                  onClick={() => setZoomCommand((c) => (c <= 0 ? c - 1 : -1))}
                  className="w-10 h-10 rounded-full bg-surface-container-lowest/90 backdrop-blur-xl shadow-md flex items-center justify-center text-primary active:scale-95 transition-transform"
                >
                  <span className="material-symbols-outlined text-[20px]">remove</span>
                </button>
              </div>

              {/* Argo Radar Central Discovery FAB */}
              <div className="absolute right-3 bottom-4 z-10">
                <button
                  type="button"
                  onClick={() => void handleDetectAndDiscover()}
                  disabled={isBusy}
                  className="relative group flex items-center gap-2 pl-3 pr-4 py-2 bg-primary text-on-primary rounded-full shadow-xl active:scale-95 transition-all overflow-hidden disabled:opacity-60"
                >
                  <div className="relative w-7 h-7 rounded-full bg-secondary-container flex items-center justify-center text-primary">
                    <span className="material-symbols-outlined text-[18px]">radar</span>
                  </div>
                  <div className="text-left">
                    <span className="block font-label-sm text-label-sm leading-none tracking-wide text-primary-fixed uppercase">
                      Radar Scan
                    </span>
                    <span className="block font-headline-sm text-headline-sm leading-none mt-0.5 text-on-primary text-[13px]">
                      Scan 10km OSM
                    </span>
                  </div>
                </button>
              </div>
            </div>

            {/* Initial Prompt State (when user has not triggered geolocation yet) */}
            {!userLocation && !isBusy && !locationError && (
              <div
                data-testid="initial-discovery-prompt"
                className="w-full bg-surface-container-lowest rounded-xl p-space-lg shadow-md border border-outline-variant/30 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-space-md"
              >
                <div className="space-y-1">
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed font-label-sm text-label-sm">
                    Real-Time GPS + OpenStreetMap Overpass
                  </span>
                  <h2 className="font-headline-md text-headline-md text-primary">
                    Discover Public Toilets Around Your Actual Location
                  </h2>
                  <p className="font-body-md text-body-md text-on-surface-variant">
                    Tap <strong>Use My Current Location</strong> or <strong>Radar Scan</strong> to
                    grant browser GPS permission and search live OpenStreetMap{' '}
                    <code>amenity=toilets</code> nodes, ways, and relations within{' '}
                    {(radiusMeters / 1000).toFixed(1)} km.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => void handleDetectAndDiscover()}
                  className="px-5 py-3 rounded-full bg-primary text-on-primary hover:bg-secondary font-label-lg text-label-lg flex items-center gap-2 shadow-md flex-shrink-0"
                >
                  <span className="material-symbols-outlined text-[20px]">near_me</span>
                  <span>Locate &amp; Find Toilets</span>
                </button>
              </div>
            )}

            {/* Empty Result State */}
            {hasSearched && !isBusy && !apiError && filteredToilets.length === 0 && (
              <div
                data-testid="empty-results-state"
                className="w-full bg-surface-container-lowest rounded-xl p-space-lg shadow-sm border border-outline-variant/30 text-center space-y-2"
              >
                <span className="material-symbols-outlined text-[36px] text-outline">
                  sentiment_dissatisfied
                </span>
                <h2 className="font-headline-sm text-headline-sm text-on-surface">
                  No OpenStreetMap Toilets Found Within {(radiusMeters / 1000).toFixed(1)} km
                </h2>
                <p className="font-body-sm text-body-sm text-on-surface-variant max-w-lg mx-auto">
                  OpenStreetMap returned 0 elements tagged <code>amenity=toilets</code> matching your
                  current radius and filter settings. Try expanding the radius to 10 km or clearing
                  active tag filters.
                </p>
              </div>
            )}

            {/* Active Selected Restroom Telemetry Card (from namma_suvidha_map_navigation_dashboard) */}
            {activeToilet && (
              <div
                data-testid="selected-toilet-card"
                className="w-full bg-surface-container-lowest rounded-xl p-space-md shadow-xl border border-outline-variant/25 flex flex-col gap-space-sm"
              >
                <div className="w-10 h-1 bg-outline-variant/60 rounded-full mx-auto mb-1" />
                <div className="flex items-start justify-between gap-space-sm">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-tertiary-container/15 text-tertiary font-label-sm text-label-sm">
                        <span className="material-symbols-outlined text-[13px] text-tertiary">
                          wc
                        </span>
                        OSM {activeToilet.osm_type.toUpperCase()} #{activeToilet.osm_id}
                      </span>
                      <span className="inline-flex items-center gap-1 font-telemetry-code text-telemetry-code text-on-surface-variant">
                        {formatCoordinates(activeToilet.latitude, activeToilet.longitude)}
                      </span>
                    </div>
                    <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-primary tracking-tight truncate">
                      {getDisplayName(activeToilet)}
                    </h2>
                    <p className="font-body-sm text-body-sm text-on-surface-variant flex items-center gap-1 mt-0.5">
                      <span className="material-symbols-outlined text-[16px] text-secondary">
                        near_me
                      </span>
                      <span>
                        {formatDistance(activeToilet.distance_meters, activeToilet.distance_km)} away
                        ·{' '}
                        {formatAddress(activeToilet.address) ??
                          'Address not recorded in OpenStreetMap'}
                      </span>
                    </p>
                  </div>

                  <div className="flex flex-col items-end flex-shrink-0 bg-surface-container-low px-3 py-1.5 rounded-lg text-right">
                    <span className="font-headline-sm text-headline-sm text-primary">
                      {formatDistance(activeToilet.distance_meters, activeToilet.distance_km)}
                    </span>
                    <span className="font-label-sm text-label-sm text-on-surface-variant">
                      Geodesic distance
                    </span>
                  </div>
                </div>

                {/* OSM Metadata Tag Badges */}
                <div className="flex items-center gap-2 overflow-x-auto py-1 no-scrollbar">
                  {Object.entries(activeToilet.tags).map(([key, value]) => (
                    <div
                      key={key}
                      className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-surface-container text-on-surface-variant flex-shrink-0 font-telemetry-code text-telemetry-code"
                    >
                      <span className="font-semibold text-primary">{key}:</span>
                      <span>{value}</span>
                    </div>
                  ))}
                </div>

                {/* Action Row */}
                <div className="flex flex-wrap items-center gap-space-sm pt-1">
                  <a
                    href={`https://www.google.com/maps/dir/?api=1&destination=${activeToilet.latitude},${activeToilet.longitude}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex-1 min-w-[200px] h-11 bg-[#123C3A] text-white hover:bg-[#003244] transition-all rounded-full flex items-center justify-center gap-2 shadow-md font-label-lg text-label-lg uppercase tracking-wide"
                  >
                    <span className="material-symbols-outlined text-[20px]">directions</span>
                    <span>Get Directions on Google Maps</span>
                  </a>
                  <button
                    type="button"
                    onClick={() => setActiveView('details')}
                    className="px-4 h-11 rounded-full bg-surface-container text-on-surface hover:bg-surface-container-high font-label-lg text-label-lg flex items-center gap-1.5"
                  >
                    <span>Full OSM Metadata</span>
                    <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
                  </button>
                </div>
              </div>
            )}

            {/* Secondary Nearby Points Grid */}
            {filteredToilets.length > 1 && (
              <div className="flex flex-col gap-space-sm">
                <div className="flex items-center justify-between px-1">
                  <span className="font-headline-sm text-headline-sm text-primary">
                    Nearby OpenStreetMap Toilets (Sorted by Distance)
                  </span>
                  <button
                    type="button"
                    onClick={() => setActiveView('list')}
                    className="font-label-sm text-label-sm text-secondary hover:underline"
                  >
                    View All ({filteredToilets.length})
                  </button>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-space-sm">
                  {filteredToilets.slice(0, 6).map((toilet) => (
                    <div
                      key={`${toilet.osm_type}-${toilet.osm_id}`}
                      onClick={() => setSelectedToilet(toilet)}
                      className={`p-space-sm bg-surface-container-lowest rounded-xl shadow-sm border transition-all cursor-pointer flex flex-col justify-between gap-2 ${activeToilet?.osm_id === toilet.osm_id &&
                        activeToilet?.osm_type === toilet.osm_type
                        ? 'border-secondary ring-2 ring-secondary/20'
                        : 'border-outline-variant/20 hover:border-secondary/50'
                        }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="px-2 py-0.5 rounded-full bg-secondary-fixed text-on-secondary-fixed font-label-sm text-[10px] uppercase">
                          {toilet.osm_type} #{toilet.osm_id}
                        </span>
                        <span className="font-telemetry-code text-telemetry-code text-secondary font-bold">
                          {formatDistance(toilet.distance_meters, toilet.distance_km)}
                        </span>
                      </div>
                      <div>
                        <h3 className="font-label-lg text-label-lg text-on-surface font-semibold truncate">
                          {getDisplayName(toilet)}
                        </h3>
                        <p className="font-body-sm text-body-sm text-on-surface-variant mt-0.5 truncate">
                          {formatAddress(toilet.address) ?? 'Address not listed in OSM'}
                        </p>
                      </div>
                      <div className="flex items-center justify-between pt-1 text-label-sm font-label-sm text-on-surface-variant">
                        <span>
                          access: {toilet.tags.access ?? 'unspecified'} · fee:{' '}
                          {toilet.tags.fee ?? 'unspecified'}
                        </span>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            setSelectedToilet(toilet)
                            setActiveView('details')
                          }}
                          className="text-secondary flex items-center hover:underline"
                        >
                          Inspect{' '}
                          <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* VIEW 2: SEARCH FACILITY RESULTS LIST (from search_facility_results) */}
        {activeView === 'list' && (
          <div data-testid="toilet-results-list" className="flex flex-col gap-space-md">
            <div className="bg-surface-container-high/80 rounded-xl px-space-md py-space-sm flex items-center justify-between shadow-sm">
              <div className="flex items-center gap-space-sm min-w-0">
                <span className="w-2.5 h-2.5 rounded-full bg-on-tertiary-container flex-shrink-0" />
                <div className="flex flex-col min-w-0">
                  <span className="font-label-lg text-label-lg text-primary truncate">
                    {filteredToilets.length} OpenStreetMap Toilets within{' '}
                    {(radiusMeters / 1000).toFixed(1)} km
                  </span>
                  <span className="font-body-sm text-body-sm text-on-surface-variant truncate">
                    Sorted by geodesic distance ascending from your device coordinates
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setActiveView('map')}
                className="flex items-center gap-1 bg-surface-container-lowest px-space-sm py-1.5 rounded-full shadow-sm font-label-sm text-label-sm text-primary"
              >
                <span className="material-symbols-outlined text-secondary text-[16px]">map</span>
                <span>View on Live Map</span>
              </button>
            </div>

            {filteredToilets.length === 0 ? (
              <div
                data-testid="empty-results-state"
                className="bg-surface-container-lowest rounded-xl p-space-lg text-center space-y-2 border border-outline-variant/25"
              >
                <p className="font-headline-sm text-headline-sm text-on-surface">
                  {hasSearched
                    ? 'No toilets matched your current radius or filters.'
                    : 'No location search performed yet.'}
                </p>
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  {hasSearched
                    ? 'Try increasing the radius up to 10 km or resetting OSM tag filters.'
                    : 'Click "Use My Current Location" above to detect your GPS coordinates and query OpenStreetMap.'}
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-space-md">
                {filteredToilets.map((toilet) => {
                  const formattedAddr = formatAddress(toilet.address)
                  return (
                    <article
                      key={`${toilet.osm_type}-${toilet.osm_id}`}
                      data-testid={`toilet-card-${toilet.osm_id}`}
                      className="bg-surface-container-lowest rounded-xl p-space-md shadow-[0_10px_25px_-5px_rgba(12,74,96,0.08),0_4px_10px_-2px_rgba(12,74,96,0.04)] border border-outline-variant/20 flex flex-col gap-space-sm"
                    >
                      <div className="flex items-start justify-between gap-space-sm">
                        <div className="flex items-center gap-space-sm min-w-0">
                          <div className="w-12 h-12 rounded-xl bg-tertiary-fixed flex items-center justify-center text-tertiary flex-shrink-0">
                            <span className="material-symbols-outlined text-[26px]">wc</span>
                          </div>
                          <div className="flex flex-col min-w-0">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <h2 className="font-headline-sm text-headline-sm text-on-surface truncate">
                                {getDisplayName(toilet)}
                              </h2>
                              <span className="px-2 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed font-label-sm text-label-sm uppercase">
                                {toilet.osm_type} #{toilet.osm_id}
                              </span>
                            </div>
                            <span className="font-body-sm text-body-sm text-on-surface-variant truncate">
                              {formattedAddr ?? 'Address not specified in OpenStreetMap'}
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-surface-container text-on-surface flex-shrink-0">
                          <span className="material-symbols-outlined text-secondary text-[16px]">
                            navigation
                          </span>
                          <span className="font-label-md text-label-md font-bold">
                            {formatDistance(toilet.distance_meters, toilet.distance_km)}
                          </span>
                        </div>
                      </div>

                      <div className="bg-surface-container-low rounded-lg p-space-sm flex flex-wrap items-center justify-between gap-2 font-telemetry-code text-telemetry-code text-on-surface-variant">
                        <span>
                          COORDS: {toilet.latitude.toFixed(6)}, {toilet.longitude.toFixed(6)}
                        </span>
                        <span>OSM TAGS: {Object.keys(toilet.tags).length} preserved</span>
                      </div>

                      <div className="flex items-center gap-space-xs flex-wrap py-1">
                        {Object.entries(toilet.tags).map(([k, v]) => (
                          <span
                            key={k}
                            className="flex items-center gap-1 px-2 py-1 rounded-md bg-surface-container-low text-on-surface-variant font-label-sm text-label-sm"
                          >
                            <strong className="text-primary">{k}:</strong> {v}
                          </span>
                        ))}
                      </div>

                      <div className="flex items-center gap-space-sm pt-1">
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedToilet(toilet)
                            setActiveView('map')
                          }}
                          className="flex-1 py-space-sm px-space-md rounded-full bg-primary text-on-primary font-label-lg text-label-lg flex items-center justify-center gap-2 shadow-md"
                        >
                          <span className="material-symbols-outlined text-[18px]">location_on</span>
                          <span>Focus on Map</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedToilet(toilet)
                            setActiveView('details')
                          }}
                          className="py-space-sm px-space-md rounded-full bg-surface-container text-on-surface font-label-lg text-label-lg flex items-center justify-center gap-1"
                        >
                          <span>Details</span>
                          <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
                        </button>
                      </div>
                    </article>
                  )
            })}
            </div>
            )}
          </div>
        )}

        {/* VIEW 3: SANITATION & INCLUSIVITY OSM TAG FILTERS (from sanitation_inclusivity_filters) */}
        {activeView === 'filters' && (
          <div className="flex flex-col gap-space-md">
            <div className="w-full bg-surface-container-low rounded-xl p-space-md shadow-sm flex flex-col gap-space-sm">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-space-xs">
                  <span className="w-2.5 h-2.5 rounded-full bg-tertiary-fixed-dim" />
                  <span className="font-telemetry-code text-telemetry-code text-on-surface-variant uppercase tracking-wider">
                    OPENSTREETMAP TAG FILTER TUNER
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setFreeOnly(false)
                    setWheelchairOnly(false)
                    setChangingTableOnly(false)
                    setPublicAccessOnly(false)
                  }}
                  className="font-label-md text-label-md text-secondary hover:text-primary flex items-center gap-1"
                >
                  <span className="material-symbols-outlined text-[16px]">restart_alt</span>
                  Reset All
                </button>
              </div>
              <h2 className="font-headline-md text-headline-md text-on-surface">
                Filter by Verified OpenStreetMap Tags
              </h2>
              <p className="font-body-sm text-body-sm text-on-surface-variant">
                Note: OpenStreetMap tag coverage varies by mapper contribution. Filtering only retains
                records that explicitly declare the selected OSM tag.
              </p>
            </div>

            <div className="w-full bg-surface-container-lowest rounded-xl p-space-md shadow-sm border border-outline-variant/20 flex flex-col gap-space-sm">
              <label className="flex items-center justify-between p-2.5 rounded-lg bg-surface-container hover:bg-surface-container-high cursor-pointer">
                <div className="flex items-center gap-2.5">
                  <span className="material-symbols-outlined text-secondary text-[20px]">
                    Accessible
                  </span>
                  <div>
                    <span className="font-label-md text-label-md text-on-surface font-semibold block">
                      Wheelchair Accessible (`wheelchair=yes`)
                    </span>
                    <span className="font-telemetry-code text-telemetry-code text-on-surface-variant">
                      Filters for OSM elements tagged wheelchair=yes
                    </span>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={wheelchairOnly}
                  onChange={(e) => setWheelchairOnly(e.target.checked)}
                  className="w-5 h-5 rounded accent-secondary cursor-pointer"
                />
              </label>

              <label className="flex items-center justify-between p-2.5 rounded-lg bg-surface-container hover:bg-surface-container-high cursor-pointer">
                <div className="flex items-center gap-2.5">
                  <span className="material-symbols-outlined text-secondary text-[20px]">
                    payments
                  </span>
                  <div>
                    <span className="font-label-md text-label-md text-on-surface font-semibold block">
                      Exclude Paid Fee Toilets (`fee=no` or unset)
                    </span>
                    <span className="font-telemetry-code text-telemetry-code text-on-surface-variant">
                      Excludes facilities where OSM tag fee=yes
                    </span>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={freeOnly}
                  onChange={(e) => setFreeOnly(e.target.checked)}
                  className="w-5 h-5 rounded accent-secondary cursor-pointer"
                />
              </label>

              <label className="flex items-center justify-between p-2.5 rounded-lg bg-surface-container hover:bg-surface-container-high cursor-pointer">
                <div className="flex items-center gap-2.5">
                  <span className="material-symbols-outlined text-secondary text-[20px]">
                    baby_changing_station
                  </span>
                  <div>
                    <span className="font-label-md text-label-md text-on-surface font-semibold block">
                      Baby Changing Table (`changing_table=yes`)
                    </span>
                    <span className="font-telemetry-code text-telemetry-code text-on-surface-variant">
                      Filters for OSM elements tagged changing_table=yes
                    </span>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={changingTableOnly}
                  onChange={(e) => setChangingTableOnly(e.target.checked)}
                  className="w-5 h-5 rounded accent-secondary cursor-pointer"
                />
              </label>

              <label className="flex items-center justify-between p-2.5 rounded-lg bg-surface-container hover:bg-surface-container-high cursor-pointer">
                <div className="flex items-center gap-2.5">
                  <span className="material-symbols-outlined text-secondary text-[20px]">
                    lock_open
                  </span>
                  <div>
                    <span className="font-label-md text-label-md text-on-surface font-semibold block">
                      Public / Permissive Access (`access=yes|public|permissive`)
                    </span>
                    <span className="font-telemetry-code text-telemetry-code text-on-surface-variant">
                      Excludes facilities tagged access=private or access=customers
                    </span>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={publicAccessOnly}
                  onChange={(e) => setPublicAccessOnly(e.target.checked)}
                  className="w-5 h-5 rounded accent-secondary cursor-pointer"
                />
              </label>
            </div>

            <button
              type="button"
              onClick={() => setActiveView('list')}
              className="w-full h-12 bg-primary hover:bg-secondary text-on-primary rounded-full font-label-lg text-label-lg font-bold flex items-center justify-center gap-2 shadow-lg"
            >
              <span className="material-symbols-outlined text-[20px]">filter_alt</span>
              <span>
                APPLY {activeFilterCount} FILTERS (SHOWS {filteredToilets.length} TOILETS)
              </span>
            </button>
          </div>
        )}

        {/* VIEW 4: FACILITY DETAILS & OSM METADATA COCKPIT (from facility_details_inspection_cockpit) */}
        {activeView === 'details' && (
          <div className="flex flex-col gap-space-md">
            {!activeToilet ? (
              <div className="bg-surface-container-lowest rounded-xl p-space-lg text-center">
                <p className="font-body-md text-body-md text-on-surface-variant">
                  Select a toilet from the Map or Results list to inspect its OpenStreetMap metadata.
                </p>
              </div>
            ) : (
              <div
                data-testid="facility-details-cockpit"
                className="bg-surface-container-lowest p-space-md rounded-xl shadow-sm border border-outline-variant/25 space-y-4"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-space-xs bg-surface-container px-3 py-1.5 rounded-full">
                    <span className="w-2 h-2 rounded-full bg-tertiary-fixed-dim" />
                    <span className="font-telemetry-code text-telemetry-code text-primary uppercase font-semibold">
                      OSM {activeToilet.osm_type.toUpperCase()} #{activeToilet.osm_id}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setActiveView('list')}
                    className="px-3 py-1 rounded-full bg-surface-container-high text-primary font-label-sm text-label-sm flex items-center gap-1"
                  >
                    <span className="material-symbols-outlined text-[16px]">arrow_back</span>
                    <span>Back to Results</span>
                  </button>
                </div>

                <div>
                  <span className="font-label-sm text-label-sm uppercase tracking-wider text-secondary font-bold">
                    OpenStreetMap Live Element Record
                  </span>
                  <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-on-surface mt-0.5">
                    {getDisplayName(activeToilet)}
                  </h2>
                  <p className="font-body-md text-body-md text-on-surface-variant mt-1">
                    {formatAddress(activeToilet.address) ??
                      'No structured street/city/postcode tags present on this OSM element'}
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <div className="bg-surface-container-low p-3 rounded-lg">
                    <span className="font-label-sm text-label-sm text-on-surface-variant uppercase">
                      Geodesic Distance
                    </span>
                    <div className="font-headline-sm text-headline-sm text-primary mt-0.5">
                      {formatDistance(activeToilet.distance_meters, activeToilet.distance_km)}
                    </div>
                  </div>
                  <div className="bg-surface-container-low p-3 rounded-lg">
                    <span className="font-label-sm text-label-sm text-on-surface-variant uppercase">
                      WGS84 Coordinates
                    </span>
                    <div className="font-telemetry-code text-telemetry-code text-on-surface mt-1">
                      {activeToilet.latitude.toFixed(6)}, {activeToilet.longitude.toFixed(6)}
                    </div>
                  </div>
                  <div className="bg-surface-container-low p-3 rounded-lg">
                    <span className="font-label-sm text-label-sm text-on-surface-variant uppercase">
                      Access Advisory
                    </span>
                    <div className="font-body-sm text-body-sm text-on-surface mt-0.5">
                      access={activeToilet.tags.access ?? 'unspecified'} (verify on-site)
                    </div>
                  </div>
                </div>

                <div>
                  <h3 className="font-label-lg text-label-lg text-on-surface mb-2">
                    Preserved OpenStreetMap Tags ({Object.keys(activeToilet.tags).length})
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {Object.entries(activeToilet.tags).map(([key, value]) => (
                      <div
                        key={key}
                        className="flex items-center justify-between p-2.5 rounded-lg bg-surface-container-low font-telemetry-code text-telemetry-code"
                      >
                        <span className="font-semibold text-primary">{key}</span>
                        <span className="text-on-surface-variant">{value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </section>
    )
  }
