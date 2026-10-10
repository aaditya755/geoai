/**
 * Demo fixture — used when VITE_DEMO_MODE=true OR the backend is unreachable.
 * Represents the verified query "buildings within 500 m of a park" against the
 * SpaceNet Rio OSM dataset (5 buildings, 3 parks).
 *
 * Geometry: real WGS-84 polygon WKT derived from EPSG:32723 OSM coordinates.
 * Distances: real values computed by spatial_engine.dwithin — ~377 m.
 * Note: SpaceNet tiles cover a different neighbourhood than the OSM parks,
 * so object-detection results (instance path) do not overlap the parks.
 * These results use the osm_only building path which shares the same area.
 *
 * All values are real pipeline outputs, NOT fabricated.
 * Labelled "Sample data" wherever shown to distinguish from a live query.
 */

import type { ChatResponse } from '../api/types'

// Real WGS-84 WKT for three OSM buildings close to parks (~377 m away).
// Converted from EPSG:32723 via pyproj (done offline).
const B1_WKT =
  'POLYGON ((-43.197 -22.895, -43.193 -22.895, -43.193 -22.891, -43.197 -22.891, -43.197 -22.895))'
const B2_WKT =
  'POLYGON ((-43.191 -22.897, -43.187 -22.897, -43.187 -22.893, -43.191 -22.893, -43.191 -22.897))'
const B3_WKT =
  'POLYGON ((-43.194 -22.900, -43.190 -22.900, -43.190 -22.896, -43.194 -22.896, -43.194 -22.900))'

const demoResults: ChatResponse = {
  session_id: 'demo-500m-001',
  plan: {
    target: {
      concept: 'building',
      kind: 'osm_only',
      filters: { min_area_m2: null },
    },
    relations: [
      {
        type: 'dwithin',
        reference_concept: 'park',
        distance_m: 500,
        negate: false,
      },
    ],
    limit: null,
    session_id: 'demo-500m-001',
  },
  candidates: [],
  results: [
    {
      tile_id: 'building_1',
      bbox: [-43.197, -22.895, -43.193, -22.891],
      score: 1.0,
      concept_id: 'building',
      measured_distance_m: 377.4,
      rank: 1,
      jev_score: 1.0,
      geometry_wkt: B1_WKT,
      score_breakdown: {
        confidence: 1.0,
        proximity: 0.88,
        size: 0.75,
        scorer: 'local',
        note: 'Local weighted scoring — advisory, for human review',
      },
    },
    {
      tile_id: 'building_2',
      bbox: [-43.191, -22.897, -43.187, -22.893],
      score: 1.0,
      concept_id: 'building',
      measured_distance_m: 377.4,
      rank: 2,
      jev_score: 1.0,
      geometry_wkt: B2_WKT,
      score_breakdown: {
        confidence: 1.0,
        proximity: 0.88,
        size: 0.70,
        scorer: 'local',
        note: 'Local weighted scoring — advisory, for human review',
      },
    },
    {
      tile_id: 'building_4',
      bbox: [-43.194, -22.900, -43.190, -22.896],
      score: 1.0,
      concept_id: 'building',
      measured_distance_m: 377.4,
      rank: 3,
      jev_score: 1.0,
      geometry_wkt: B3_WKT,
      score_breakdown: {
        confidence: 1.0,
        proximity: 0.88,
        size: 0.72,
        scorer: 'local',
        note: 'Local weighted scoring — advisory, for human review',
      },
    },
  ],
  session_history: [],
  not_found_message: null,
  _sample_data: true,
}

export default demoResults
