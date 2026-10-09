// GeoLens AI — shared TypeScript types (mirrors types.py)

export interface TargetFilters {
  min_area_m2: number | null  // PROPOSED — FEATURE_MIN_AREA
}

export interface Target {
  concept: string
  kind: 'instance' | 'osm_only'
  filters: TargetFilters
}

export interface Relation {
  type: 'dwithin' | 'intersects' | 'negate'
  reference_concept: string
  distance_m: number | null
  negate: boolean  // PROPOSED — FEATURE_NEGATE
}

export interface Plan {
  target: Target
  relations: Relation[]
  limit: number | null
  session_id: string | null
}

export interface ScoreBreakdown {
  confidence: number
  proximity: number
  size: number
  scorer?: string   // "local" or "jev_ai" — see jev_ranker.py; optional for backward compat
  note: string
}

export interface Result {
  tile_id: string
  bbox: [number, number, number, number]
  score: number
  concept_id: string
  measured_distance_m: number
  rank: number
  jev_score?: number
  score_breakdown?: ScoreBreakdown
  geometry_wkt?: string
}

export interface HistoryEntry {
  query: string
  plan: Plan
}

export interface ChatResponse {
  session_id: string
  plan: Plan
  candidates: Result[]
  results: Result[]
  session_history: HistoryEntry[]
  not_found_message: string | null
  error?: string
  _sample_data?: boolean
}

export interface ChatRequest {
  query: string
  session_id?: string | null
  lang?: string | null
}

export type PipelineStep = 'understanding' | 'searching' | 'spatial' | 'ranking' | 'done' | 'idle'
