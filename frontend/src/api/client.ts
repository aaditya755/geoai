/**
 * API client for GeoLens AI backend.
 *
 * Priority:
 *  1. VITE_DEMO_MODE=true  → always serve fixture (no network)
 *  2. Backend reachable    → real response; mark _sample_data=false
 *  3. Backend unreachable  → auto-fallback to fixture; mark _sample_data=true
 *
 * The caller receives _sample_data=true whenever fixture data is used so the
 * UI can show the "Sample data" badge.  API keys are never handled here.
 */

import type { ChatRequest, ChatResponse } from './types'
import demoResults from '../fixtures/demoResults'
import demoParkResults from '../fixtures/demoParkResults'
import demo200mResults from '../fixtures/demo200mResults'

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'
const API_BASE  = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')

/** Pick a suitable demo fixture based on query keywords. */
function pickDemoFixture(query: string): ChatResponse {
  const q = query.toLowerCase()
  if (q.includes('200')) return { ...demo200mResults, _sample_data: true }
  if (q.includes('park'))  return { ...demoParkResults, _sample_data: true }
  return { ...demoResults, _sample_data: true }
}

export async function chat(req: ChatRequest): Promise<ChatResponse> {
  if (DEMO_MODE) {
    await new Promise(r => setTimeout(r, 900))
    return pickDemoFixture(req.query)
  }

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail ?? `HTTP ${res.status}`)
    }

    const data: ChatResponse = await res.json()
    return { ...data, _sample_data: false }

  } catch (networkErr) {
    console.warn('[GeoLens] Backend unreachable, using demo fixture:', networkErr)
    await new Promise(r => setTimeout(r, 600))
    return pickDemoFixture(req.query)
  }
}

export async function exportGeoJSON(results: ChatResponse['results']): Promise<object> {
  const isSampleData = results.some(r => r.tile_id.startsWith('building_') || r.tile_id.startsWith('SN1_'))

  if (DEMO_MODE || isSampleData) {
    return buildLocalGeoJSON(results)
  }

  try {
    const res = await fetch(`${API_BASE}/export`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ results }),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  } catch {
    return buildLocalGeoJSON(results)
  }
}

function buildLocalGeoJSON(results: ChatResponse['results']): object {
  return {
    type: 'FeatureCollection',
    features: results.map(r => {
      let geometry: object | null = null

      if (r.geometry_wkt) {
        // Parse simple polygon WKT into GeoJSON (covers rectangular demo fixtures)
        const match = r.geometry_wkt.match(/POLYGON\s*\(\(([^)]+)\)\)/)
        if (match) {
          const coords = match[1].split(',').map(pair => {
            const [x, y] = pair.trim().split(/\s+/).map(Number)
            return [x, y]
          })
          geometry = { type: 'Polygon', coordinates: [coords] }
        }
      }

      if (!geometry && r.bbox?.length === 4) {
        const [minx, miny, maxx, maxy] = r.bbox
        geometry = {
          type: 'Polygon',
          coordinates: [[[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny]]],
        }
      }

      return {
        type: 'Feature',
        geometry,
        properties: {
          tile_id: r.tile_id,
          concept_id: r.concept_id,
          score: r.score,
          measured_distance_m: r.measured_distance_m,
          rank: r.rank,
          _sample_data: true,
        },
      }
    }),
  }
}
