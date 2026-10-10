/**
 * Demo fixture for "Find parks" query.
 * Three OSM parks from the SpaceNet Rio dataset, real coordinates.
 */
import type { ChatResponse } from '../api/types'

const demoParks: ChatResponse = {
  session_id: 'demo-parks-001',
  plan: {
    target: { concept: 'park', kind: 'osm_only', filters: { min_area_m2: null } },
    relations: [],
    limit: null,
    session_id: 'demo-parks-001',
  },
  candidates: [],
  results: [
    {
      tile_id: 'park_1',
      bbox: [-43.197, -22.907, -43.153, -22.895],
      score: 1.0,
      concept_id: 'park',
      measured_distance_m: 0,
      rank: 1,
      jev_score: 1.0,
      geometry_wkt: 'POLYGON ((-43.197 -22.907, -43.153 -22.907, -43.153 -22.895, -43.197 -22.895, -43.197 -22.907))',
      score_breakdown: { confidence: 1.0, proximity: 1.0, size: 1.0, scorer: 'local', note: 'OSM data' },
    },
    {
      tile_id: 'park_2',
      bbox: [-43.180, -22.901, -43.156, -22.889],
      score: 1.0,
      concept_id: 'park',
      measured_distance_m: 0,
      rank: 2,
      jev_score: 1.0,
      geometry_wkt: 'POLYGON ((-43.180 -22.901, -43.156 -22.901, -43.156 -22.889, -43.180 -22.889, -43.180 -22.901))',
      score_breakdown: { confidence: 1.0, proximity: 1.0, size: 1.0, scorer: 'local', note: 'OSM data' },
    },
    {
      tile_id: 'park_3',
      bbox: [-43.215 , -22.888, -43.198, -22.876],
      score: 1.0,
      concept_id: 'park',
      measured_distance_m: 0,
      rank: 3,
      jev_score: 1.0,
      geometry_wkt: 'POLYGON ((-43.215 -22.888, -43.198 -22.888, -43.198 -22.876, -43.215 -22.876, -43.215 -22.888))',
      score_breakdown: { confidence: 1.0, proximity: 1.0, size: 1.0, scorer: 'local', note: 'OSM data' },
    },
  ],
  session_history: [],
  not_found_message: null,
  _sample_data: true,
}

export default demoParks
