import React, { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Result } from '../api/types'
import './MapPanel.css'

// Fix Leaflet default icon URLs when bundled
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl:       'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl:     'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

// Rio de Janeiro centre — default view
const RIO_CENTER: [number, number] = [-22.9068, -43.1729]
const DEFAULT_ZOOM = 13

interface Props {
  results: Result[]
  selectedIdx: number | null
  onSelectResult: (i: number) => void
  sampleData: boolean
}

// ── Geometry helpers ────────────────────────────────────────────────────────

/**
 * Try to extract [lat, lng] centroid from a result.
 * Prefers geometry_wkt → bbox (treated as WGS-84 lon/lat).
 */
function resultCentroid(r: Result): [number, number] | null {
  // 1. geometry_wkt: POLYGON ((lon lat, ...))
  if (r.geometry_wkt) {
    const match = r.geometry_wkt.match(/POLYGON\s*\(\(([^)]+)\)\)/)
    if (match) {
      const pairs = match[1].split(',').map(p => {
        const [x, y] = p.trim().split(/\s+/).map(Number)
        return [x, y] as [number, number]
      })
      if (pairs.length) {
        const avgLon = pairs.reduce((s, p) => s + p[0], 0) / pairs.length
        const avgLat = pairs.reduce((s, p) => s + p[1], 0) / pairs.length
        return [avgLat, avgLon]  // Leaflet wants [lat, lng]
      }
    }
  }
  // 2. bbox [minx, miny, maxx, maxy] in WGS-84
  if (r.bbox?.length === 4) {
    const [minx, miny, maxx, maxy] = r.bbox
    // Treat as WGS-84 only if values look like lon/lat (roughly -180..180)
    if (Math.abs(minx) <= 180 && Math.abs(miny) <= 90) {
      return [(miny + maxy) / 2, (minx + maxx) / 2]
    }
  }
  return null
}

/** Parse polygon WKT into a Leaflet LatLng array, or null on failure. */
function wktToLatLngs(wkt: string): L.LatLng[] | null {
  const match = wkt.match(/POLYGON\s*\(\(([^)]+)\)\)/)
  if (!match) return null
  return match[1].split(',').map(p => {
    const [x, y] = p.trim().split(/\s+/).map(Number)
    return L.latLng(y, x)  // WKT is (lon lat), Leaflet is (lat, lng)
  })
}

/** Build Leaflet bounds from a bbox [minx, miny, maxx, maxy] in WGS-84. */
function bboxToBounds(bbox: number[]): L.LatLngBounds | null {
  if (bbox.length !== 4) return null
  const [minx, miny, maxx, maxy] = bbox
  if (Math.abs(minx) > 180 || Math.abs(miny) > 90) return null
  return L.latLngBounds([[miny, minx], [maxy, maxx]])
}

// ── Component ────────────────────────────────────────────────────────────────

export default function MapPanel({ results, selectedIdx, onSelectResult, sampleData }: Props) {
  const containerRef  = useRef<HTMLDivElement>(null)
  const mapRef        = useRef<L.Map | null>(null)
  const layersRef     = useRef<L.Layer[]>([])
  const [mapError, setMapError] = useState<string | null>(null)

  // ── Init map ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    try {
      const map = L.map(containerRef.current, {
        center: RIO_CENTER,
        zoom: DEFAULT_ZOOM,
        zoomControl: true,
        scrollWheelZoom: true,
      })

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map)

      mapRef.current = map
      setTimeout(() => map.invalidateSize(), 100)
    } catch (err) {
      console.error('Map init error:', err)
      setMapError('Failed to load map. Please refresh the page.')
    }

    return () => {
      if (mapRef.current) { mapRef.current.remove(); mapRef.current = null }
    }
  }, [])

  // ── Render result layers ────────────────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    // Remove previous result layers
    layersRef.current.forEach(l => map.removeLayer(l))
    layersRef.current = []

    if (!results.length) return

    const allBounds: L.LatLngBounds[] = []

    results.forEach((r, i) => {
      const selected = i === selectedIdx
      const color    = selected ? '#2DD4BF' : '#8B5CF6'
      const weight   = selected ? 2.5 : 1.5

      // ── Polygon from WKT ────────────────────────────────────────────────
      if (r.geometry_wkt) {
        const latlngs = wktToLatLngs(r.geometry_wkt)
        if (latlngs && latlngs.length >= 3) {
          const poly = L.polygon(latlngs, {
            color,
            weight,
            fillColor: color,
            fillOpacity: selected ? 0.3 : 0.1,
            dashArray: selected ? undefined : '5,4',
          })
            .addTo(map)
            .on('click', () => onSelectResult(i))

          const popupText = [
            `<b>${r.concept_id}</b>`,
            `Rank #${r.rank}`,
            isFinite(r.measured_distance_m) ? `Distance: ${Math.round(r.measured_distance_m)} m` : null,
            `Score: ${(r.score * 100).toFixed(0)}%`,
          ].filter(Boolean).join('<br>')
          poly.bindPopup(popupText)

          layersRef.current.push(poly)
          allBounds.push(poly.getBounds())
        }
      }

      // ── Fallback: rectangle from bbox ───────────────────────────────────
      if (!r.geometry_wkt && r.bbox) {
        const bounds = bboxToBounds(r.bbox)
        if (bounds) {
          const rect = L.rectangle(bounds, {
            color,
            weight,
            fillColor: color,
            fillOpacity: selected ? 0.3 : 0.1,
            dashArray: selected ? undefined : '5,4',
          })
            .addTo(map)
            .on('click', () => onSelectResult(i))
          layersRef.current.push(rect)
          allBounds.push(bounds)
        }
      }

      // ── Marker at centroid ──────────────────────────────────────────────
      const centroid = resultCentroid(r)
      if (centroid) {
        const markerHtml = `<div class="map-marker ${selected ? 'selected' : ''}" title="${r.concept_id}"></div>`
        const icon = L.divIcon({ className: '', html: markerHtml, iconSize: [14, 14], iconAnchor: [7, 7] })
        const marker = L.marker(centroid, { icon })
          .addTo(map)
          .on('click', () => onSelectResult(i))
        layersRef.current.push(marker)
      }

      // ── Buffer ring on selected ─────────────────────────────────────────
      if (selected && centroid && isFinite(r.measured_distance_m) && r.measured_distance_m > 0) {
        const ring = L.circle(centroid, {
          radius: r.measured_distance_m,
          color: '#2DD4BF',
          weight: 1.5,
          dashArray: '8,5',
          fill: false,
          opacity: 0.5,
        }).addTo(map)
        layersRef.current.push(ring)
      }
    })

    // Fit map to all results (only when results change, not on selection change)
    if (allBounds.length) {
      const union = allBounds.reduce((acc, b) => acc.extend(b), L.latLngBounds(allBounds[0]))
      map.fitBounds(union, { padding: [40, 40], maxZoom: 16 })
    }
  }, [results, selectedIdx, onSelectResult])

  // ── Error state ─────────────────────────────────────────────────────────
  if (mapError) {
    return (
      <div className="map-panel">
        <div className="map-error">
          <h3>Map Error</h3>
          <p>{mapError}</p>
          <button onClick={() => window.location.reload()}>Reload</button>
        </div>
      </div>
    )
  }

  return (
    <div className="map-panel">
      {sampleData && (
        <div className="map-sample-overlay" aria-label="Sample data notice">
          <span className="sample-badge">Sample data</span>
        </div>
      )}
      <div ref={containerRef} className="map-container" aria-label="Results map" />
    </div>
  )
}
