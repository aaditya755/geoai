import React, { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Result } from '../api/types'
import './MapPanel.css'

// Fix for default markers not showing in Leaflet with bundlers
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

// Rio de Janeiro centre
const RIO_CENTER: [number, number] = [-22.9068, -43.1729]
const DEFAULT_ZOOM = 13

interface Props {
  results: Result[]
  selectedIdx: number | null
  onSelectResult: (i: number) => void
  sampleData: boolean
}

/**
 * Map panel using Leaflet.
 * Shows glowing markers and dashed bounding boxes for results.
 * Draws a buffer ring at distance_m radius when a result is selected.
 */
export default function MapPanel({ results, selectedIdx, onSelectResult, sampleData }: Props) {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<any>(null)
  const markersRef = useRef<any[]>([])
  const boxesRef = useRef<any[]>([])
  const bufferRef = useRef<any>(null)
  const [mapError, setMapError] = useState<string | null>(null)

  // Initialize map
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return

    try {
      console.log('Initializing Leaflet map...')
      
      // Set a minimum height for the map container
      if (mapContainerRef.current) {
        mapContainerRef.current.style.height = '100%'
        mapContainerRef.current.style.minHeight = '400px'
      }
      
      const map = L.map(mapContainerRef.current, {
        center: RIO_CENTER,
        zoom: DEFAULT_ZOOM,
        zoomControl: true,
        preferCanvas: false,
        scrollWheelZoom: true,
        doubleClickZoom: true,
        boxZoom: true,
        keyboard: true,
      })

      // Use simple OpenStreetMap tiles (most reliable)
      const tileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
        minZoom: 1,
      })

      tileLayer.on('tileerror', (e: any) => {
        console.warn('Tile loading error:', e)
      })

      tileLayer.on('tileload', () => {
        console.log('Map tiles loaded successfully')
      })

      tileLayer.addTo(map)

      // Add a test marker to verify map is working
      const testMarker = L.marker(RIO_CENTER)
        .addTo(map)
        .bindPopup('🗺️ Rio de Janeiro<br><small>Map is working!</small>')
        .openPopup()

      mapRef.current = map
      console.log('Map initialized successfully')
      setMapError(null)

      // Force map to resize after a short delay
      setTimeout(() => {
        map.invalidateSize()
      }, 100)

    } catch (error) {
      console.error('Failed to initialize map:', error)
      setMapError('Failed to load map. Please refresh the page.')
    }

    return () => {
      if (mapRef.current) {
        try {
          mapRef.current.remove()
          mapRef.current = null
        } catch (error) {
          console.warn('Error cleaning up map:', error)
        }
      }
    }
  }, [])

  // Render results as markers + bboxes
  useEffect(() => {
    const map = mapRef.current
    if (!map || !results.length) return

    try {
      // Clear previous markers
      markersRef.current.forEach(m => {
        if (map.hasLayer(m)) map.removeLayer(m)
      })
      boxesRef.current.forEach(b => {
        if (map.hasLayer(b)) map.removeLayer(b)
      })
      markersRef.current = []
      boxesRef.current = []

      results.forEach((r, i) => {
        const isSelected = i === selectedIdx

        // For demo: place markers at approximate positions offset from RIO_CENTER
        const lat = RIO_CENTER[0] + (i * 0.002) - 0.003
        const lng = RIO_CENTER[1] + (i * 0.003) - 0.004

        // Glowing marker
        const markerIcon = L.divIcon({
          className: '',
          html: `<div class="map-marker ${isSelected ? 'selected' : ''}" title="${r.concept_id} | score: ${r.score.toFixed(2)}"></div>`,
          iconSize: [14, 14],
          iconAnchor: [7, 7],
        })

        const marker = L.marker([lat, lng], { icon: markerIcon })
          .addTo(map)
          .on('click', () => onSelectResult(i))

        markersRef.current.push(marker)

        // Dashed bounding box
        const bboxBounds: [[number, number], [number, number]] = [
          [lat - 0.0008, lng - 0.0010],
          [lat + 0.0008, lng + 0.0010],
        ]
        const box = L.rectangle(bboxBounds, {
          color: isSelected ? '#2DD4BF' : '#8B5CF6',
          weight: isSelected ? 2 : 1,
          dashArray: '5, 4',
          fill: false,
          opacity: isSelected ? 0.9 : 0.5,
        }).addTo(map)
        boxesRef.current.push(box)
      })
    } catch (error) {
      console.error('Error rendering map markers:', error)
    }
  }, [results, selectedIdx, onSelectResult])

  // Buffer ring on selected result
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    try {
      if (bufferRef.current) {
        if (map.hasLayer(bufferRef.current)) {
          map.removeLayer(bufferRef.current)
        }
        bufferRef.current = null
      }

      if (selectedIdx === null || !results[selectedIdx]) return

      const r = results[selectedIdx]
      const lat = RIO_CENTER[0] + (selectedIdx * 0.002) - 0.003
      const lng = RIO_CENTER[1] + (selectedIdx * 0.003) - 0.004
      const distM = isNaN(r.measured_distance_m) ? 0 : r.measured_distance_m

      if (distM > 0) {
        bufferRef.current = L.circle([lat, lng], {
          radius: distM,
          color: '#2DD4BF',
          weight: 1.5,
          dashArray: '8, 5',
          fill: false,
          opacity: 0.5,
        }).addTo(map)
      }
    } catch (error) {
      console.error('Error rendering buffer ring:', error)
    }
  }, [selectedIdx, results])

  if (mapError) {
    return (
      <div className="map-panel">
        <div className="map-error">
          <h3>Map Error</h3>
          <p>{mapError}</p>
          <button onClick={() => window.location.reload()}>Reload Page</button>
        </div>
      </div>
    )
  }

  return (
    <div className="map-panel">
      {sampleData && (
        <div className="map-sample-overlay" aria-label="Sample data notice">
          <span className="sample-badge">Sample data — positions are illustrative</span>
        </div>
      )}
      <div ref={mapContainerRef} className="map-container" aria-label="Results map" />
    </div>
  )
}
