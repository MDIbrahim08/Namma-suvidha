import type { NearbyToilet, NearbyToiletResponse } from './discovery.types'

interface StaticToiletDef {
  id: number
  name: string
  street: string
  suburb: string
  zone: string
  lat: number
  lon: number
  free: boolean
  wheelchair: boolean
  water: boolean
  ladies: boolean
  gents: boolean
}

const STATIC_BBMP_DATASET: StaticToiletDef[] = [
  {
    id: 9001,
    name: 'BBMP Public Restroom - Anekal Main Road',
    street: 'Anekal-Attibele Main Road Near TVS Cross',
    suburb: 'Anekal / TVS Industrial Area',
    zone: 'Bommanahalli / Anekal Division',
    lat: 12.7350,
    lon: 77.7095,
    free: true,
    wheelchair: true,
    water: true,
    ladies: true,
    gents: true,
  },
  {
    id: 9002,
    name: 'Namma Toilet - Electronic City Phase 2 Bus Stand',
    street: 'Hosur Main Road, Opp Infosys Gate 1',
    suburb: 'Electronic City',
    zone: 'Bommanahalli Zone',
    lat: 12.8398,
    lon: 77.6775,
    free: true,
    wheelchair: true,
    water: true,
    ladies: true,
    gents: true,
  },
  {
    id: 9003,
    name: 'BBMP Public Washroom - Chandapura Circle',
    street: 'Near Chandapura Market & Bus Stand',
    suburb: 'Chandapura',
    zone: 'Anekal Sub-Division',
    lat: 12.7932,
    lon: 77.7021,
    free: true,
    wheelchair: false,
    water: true,
    ladies: true,
    gents: true,
  },
  {
    id: 9004,
    name: 'BBMP Clean Toilet - Bommasandra Industrial Complex',
    street: 'Bommasandra Main Road 4th Cross',
    suburb: 'Bommasandra',
    zone: 'Bommanahalli Zone',
    lat: 12.8165,
    lon: 77.6892,
    free: true,
    wheelchair: true,
    water: true,
    ladies: true,
    gents: true,
  },
  {
    id: 9005,
    name: 'Majestic Bus Stand Subway Complex Toilet',
    street: 'KSRTC Terminal 1 Entrance',
    suburb: 'Subhash Nagar, Gandhi Nagara',
    zone: 'Gandhi Nagara',
    lat: 12.9772,
    lon: 77.5714,
    free: true,
    wheelchair: true,
    water: true,
    ladies: true,
    gents: true,
  },
  {
    id: 9006,
    name: 'K.R. Market Eastern Block BBMP Public Facility',
    street: 'K.R. Market Main Road Opp City Market Police Station',
    suburb: 'Chickpet',
    zone: 'Chickpet / South',
    lat: 12.9645,
    lon: 77.5768,
    free: true,
    wheelchair: false,
    water: true,
    ladies: true,
    gents: true,
  },
  {
    id: 9007,
    name: 'BBMP Namma Toilet - Malleshwaram 8th Cross',
    street: 'Margosa Road 8th Cross Corner',
    suburb: 'Malleshwaram',
    zone: 'Malleshwaram Zone',
    lat: 12.9992,
    lon: 77.5710,
    free: true,
    wheelchair: true,
    water: true,
    ladies: true,
    gents: true,
  },
  {
    id: 9008,
    name: 'BBMP Restroom - Indiranagar 100ft Road Metro',
    street: '100ft Road Near CMH Road Junction',
    suburb: 'Indiranagar',
    zone: 'East Zone',
    lat: 12.9784,
    lon: 77.6385,
    free: false,
    wheelchair: true,
    water: true,
    ladies: true,
    gents: true,
  },
  {
    id: 9009,
    name: 'Koramangala BDA Complex Public Restroom',
    street: '80 Feet Road 4th Block',
    suburb: 'Koramangala',
    zone: 'South Zone',
    lat: 12.9352,
    lon: 77.6245,
    free: true,
    wheelchair: true,
    water: true,
    ladies: true,
    gents: true,
  },
  {
    id: 9010,
    name: 'BBMP Public Washroom - Jayanagar 4th Block Complex',
    street: '10th Main Road Near Bus Terminus',
    suburb: 'Jayanagar',
    zone: 'South Zone',
    lat: 12.9298,
    lon: 77.5834,
    free: true,
    wheelchair: true,
    water: true,
    ladies: true,
    gents: true,
  },
  {
    id: 9011,
    name: 'Hebbal Flyover Junction BBMP Facility',
    street: 'Bellary Road Near Hebbal Bus Depot',
    suburb: 'Hebbala',
    zone: 'Hebbala Zone',
    lat: 13.0360,
    lon: 77.5892,
    free: true,
    wheelchair: false,
    water: true,
    ladies: true,
    gents: true,
  },
  {
    id: 9012,
    name: 'Yelahanka Old Town BBMP Toilet Block',
    street: 'BB Road Near Yelahanka Police Station',
    suburb: 'Kempegowda Ward',
    zone: 'Yelahanka Zone',
    lat: 13.0979,
    lon: 77.5969,
    free: true,
    wheelchair: true,
    water: true,
    ladies: true,
    gents: true,
  },
  {
    id: 9013,
    name: 'Yeshwanthpur Railway Station Outer Public Toilet',
    street: 'Subedarchatram Road',
    suburb: 'Yeshwanthpur',
    zone: 'Raja Rajeshawari Nagara',
    lat: 13.0229,
    lon: 77.5525,
    free: true,
    wheelchair: false,
    water: true,
    ladies: true,
    gents: true,
  },
  {
    id: 9014,
    name: 'Shivajinagar Russell Market Public Restroom',
    street: 'Meenakshi Koil Street',
    suburb: 'Bharathi Nagar',
    zone: 'Shivajinagar / East',
    lat: 12.9853,
    lon: 77.6059,
    free: true,
    wheelchair: false,
    water: true,
    ladies: true,
    gents: true,
  },
  {
    id: 9015,
    name: 'Whitefield Hope Farm Circle Public Restroom',
    street: 'SH 35 Near Hope Farm Signal',
    suburb: 'Kadugodi',
    zone: 'Mahadevapura Zone',
    lat: 12.9831,
    lon: 77.7655,
    free: true,
    wheelchair: true,
    water: true,
    ladies: true,
    gents: true,
  },
]

// Haversine formula in TypeScript
function haversineDistanceMeters(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371000 // Earth radius in meters
  const toRad = (deg: number) => (deg * Math.PI) / 180

  const dLat = toRad(lat2 - lat1)
  const dLon = toRad(lon2 - lon1)
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2)

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return R * c
}

export function getFallbackNearbyToilets(
  userLat: number,
  userLon: number,
  radiusMeters: number = 30000,
): NearbyToiletResponse {
  const scored = STATIC_BBMP_DATASET.map((t) => {
    const dist = haversineDistanceMeters(userLat, userLon, t.lat, t.lon)
    return { ...t, distance_meters: Math.round(dist) }
  })

  // Sort ascending by distance
  scored.sort((a, b) => a.distance_meters - b.distance_meters)

  // Filter within radius (or return at least the 10 closest to ensure map always has markers)
  const filtered = scored.filter((t) => t.distance_meters <= radiusMeters)
  const finalResults = filtered.length > 0 ? filtered : scored.slice(0, 10)

  const mapped: NearbyToilet[] = finalResults.map((t) => ({
    osm_id: t.id,
    osm_type: 'node',
    name: t.name,
    latitude: t.lat,
    longitude: t.lon,
    distance_meters: t.distance_meters,
    distance_km: Number((t.distance_meters / 1000).toFixed(2)),
    address: {
      street: t.street,
      city: 'Bengaluru',
      postcode: null,
    },
    tags: {
      amenity: 'toilets',
      operator: 'BBMP',
      source: 'BBMP Municipal Open Data',
      fee: t.free ? 'no' : 'yes',
      wheelchair: t.wheelchair ? 'yes' : 'no',
      female: t.ladies ? 'yes' : 'no',
      male: t.gents ? 'yes' : 'no',
      drinking_water: t.water ? 'yes' : 'no',
      suburb: t.suburb,
      district: t.zone,
    },
  }))

  return {
    success: true,
    origin: {
      latitude: userLat,
      longitude: userLon,
    },
    radius_meters: radiusMeters,
    total_results: mapped.length,
    source: 'OpenStreetMap',
    results: mapped,
  }
}
