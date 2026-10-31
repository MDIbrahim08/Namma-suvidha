import { useEffect, useRef } from 'react'
import L from 'leaflet'
import { env } from '../../../config/env'
import type { NearbyToilet, UserLocation } from '../../../lib/api/discovery.types'
import { formatDistance, getDisplayName } from '../utils/formatters'

interface CitizenDiscoveryMapProps {
  userLocation: UserLocation | null
  toilets: NearbyToilet[]
  selectedToilet: NearbyToilet | null
  onSelectToilet: (toilet: NearbyToilet) => void
  zoomCommand: number
}

export default function CitizenDiscoveryMap({
  userLocation,
  toilets,
  selectedToilet,
  onSelectToilet,
  zoomCommand,
}: CitizenDiscoveryMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<L.Map | null>(null)
  const markersLayerRef = useRef<L.LayerGroup | null>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el || mapRef.current) return

    // Guard for jsdom / test environments where layout dimensions may be 0
    try {
      const map = L.map(el, {
        zoomControl: false,
        attributionControl: true,
      }).setView([20.5937, 78.9629], 5)

      const tileUrl = env.mapboxToken
        ? `https://api.mapbox.com/styles/v1/mapbox/streets-v12/tiles/{z}/{x}/{y}?access_token=${env.mapboxToken}`
        : 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'

      L.tileLayer(tileUrl, {
        maxZoom: 19,
        tileSize: env.mapboxToken ? 512 : 256,
        zoomOffset: env.mapboxToken ? -1 : 0,
        attribution: '&copy; Mapbox &copy; OpenStreetMap contributors',
      }).addTo(map)

      const layerGroup = L.layerGroup().addTo(map)
      mapRef.current = map
      markersLayerRef.current = layerGroup
    } catch {
      // Fallback if Leaflet fails to initialize in a headless test DOM
    }

    return () => {
      if (mapRef.current) {
        mapRef.current.remove()
        mapRef.current = null
        markersLayerRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    const layer = markersLayerRef.current
    if (!map || !layer) return

    layer.clearLayers()

    if (userLocation) {
      const userMarker = L.circleMarker([userLocation.latitude, userLocation.longitude], {
        radius: 9,
        color: '#003244',
        weight: 3,
        fillColor: '#006398',
        fillOpacity: 0.9,
      })
      userMarker.bindTooltip('Your GPS Location', { direction: 'top' })
      userMarker.addTo(layer)
    }

    toilets.forEach((toilet) => {
      const isSelected =
        selectedToilet?.osm_id === toilet.osm_id && selectedToilet?.osm_type === toilet.osm_type
      const marker = L.circleMarker([toilet.latitude, toilet.longitude], {
        radius: isSelected ? 10 : 7,
        color: isSelected ? '#003244' : '#004f34',
        weight: isSelected ? 3 : 2,
        fillColor: isSelected ? '#5bb8fe' : '#31c98f',
        fillOpacity: 0.95,
      })
      marker.bindTooltip(
        `${getDisplayName(toilet)} (${formatDistance(toilet.distance_meters, toilet.distance_km)})`,
        { direction: 'top' },
      )
      marker.on('click', () => onSelectToilet(toilet))
      marker.addTo(layer)
    })

    if (selectedToilet) {
      map.setView([selectedToilet.latitude, selectedToilet.longitude], Math.max(map.getZoom(), 15))
    } else if (userLocation) {
      map.setView([userLocation.latitude, userLocation.longitude], 14)
    }
  }, [userLocation, toilets, selectedToilet, onSelectToilet])

  useEffect(() => {
    const map = mapRef.current
    if (!map || zoomCommand === 0) return
    if (zoomCommand > 0) {
      map.zoomIn()
    } else {
      map.zoomOut()
    }
  }, [zoomCommand])

  return (
    <div
      ref={containerRef}
      data-testid="citizen-osm-map"
      className="absolute inset-0 h-full w-full z-0"
    />
  )
}
