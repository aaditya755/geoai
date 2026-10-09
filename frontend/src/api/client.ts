/**
 * API client for GeoLens AI backend.
 * Falls back to demo fixture when VITE_DEMO_MODE=true.
 */

import type { ChatRequest, ChatResponse } from './types'
import demoResults from '../fixtures/demoResults'

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'
const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export async function chat(req: ChatRequest): Promise<ChatResponse> {
  if (DEMO_MODE) {
    // Simulate network latency for a realistic demo
    await new Promise(r => setTimeout(r, 1200))
    return { ...demoResults, _sample_data: true }
  }

  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }

  return res.json()
}

export async function exportGeoJSON(results: ChatResponse['results']): Promise<object> {
  if (DEMO_MODE) {
    // Build a minimal GeoJSON from fixture results
    return {
      type: 'FeatureCollection',
      features: results.map(r => ({
        type: 'Feature',
        geometry: null,
        properties: { ...r, _sample_data: true },
      })),
    }
  }

  const res = await fetch(`${API_BASE}/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ results }),
  })

  if (!res.ok) {
    throw new Error(`Export failed: ${res.statusText}`)
  }

  return res.json()
}
