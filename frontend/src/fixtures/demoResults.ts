/**
 * Demo fixture — used when VITE_DEMO_MODE=true or API is unavailable.
 * All values are illustrative. Labelled "Sample data" wherever shown.
 */

import type { ChatResponse } from '../api/types'

const demoResults: ChatResponse = {
  session_id: 'demo-session-001',
  plan: {
    target: {
      concept: 'swimming_pool',
      kind: 'instance',
      filters: { min_area_m2: null },
    },
    relations: [
      {
        type: 'dwithin',
        reference_concept: 'road',
        distance_m: 100,
        negate: false,
      },
    ],
    limit: null,
    session_id: 'demo-session-001',
  },
  candidates: [
    {
      tile_id: 'SN1_buildings_00001',
      bbox: [120, 85, 175, 135],
      score: 0.72,
      concept_id: 'swimming_pool',
      measured_distance_m: 42.3,
      rank: 1,
      jev_score: 0.71,
      score_breakdown: { confidence: 0.72, proximity: 0.8, size: 0.55, note: 'ranks for human review' },
    },
    {
      tile_id: 'SN1_buildings_00008',
      bbox: [200, 310, 260, 370],
      score: 0.65,
      concept_id: 'swimming_pool',
      measured_distance_m: 78.1,
      rank: 2,
      jev_score: 0.63,
      score_breakdown: { confidence: 0.65, proximity: 0.65, size: 0.6, note: 'ranks for human review' },
    },
    {
      tile_id: 'SN1_buildings_00023',
      bbox: [88, 155, 142, 210],
      score: 0.60,
      concept_id: 'swimming_pool',
      measured_distance_m: 95.0,
      rank: 3,
      jev_score: 0.55,
      score_breakdown: { confidence: 0.6, proximity: 0.52, size: 0.48, note: 'ranks for human review' },
    },
  ],
  results: [
    {
      tile_id: 'SN1_buildings_00001',
      bbox: [120, 85, 175, 135],
      score: 0.72,
      concept_id: 'swimming_pool',
      measured_distance_m: 42.3,
      rank: 1,
      jev_score: 0.71,
      score_breakdown: { confidence: 0.72, proximity: 0.8, size: 0.55, note: 'ranks for human review' },
    },
    {
      tile_id: 'SN1_buildings_00008',
      bbox: [200, 310, 260, 370],
      score: 0.65,
      concept_id: 'swimming_pool',
      measured_distance_m: 78.1,
      rank: 2,
      jev_score: 0.63,
      score_breakdown: { confidence: 0.65, proximity: 0.65, size: 0.6, note: 'ranks for human review' },
    },
    {
      tile_id: 'SN1_buildings_00023',
      bbox: [88, 155, 142, 210],
      score: 0.60,
      concept_id: 'swimming_pool',
      measured_distance_m: 95.0,
      rank: 3,
      jev_score: 0.55,
      score_breakdown: { confidence: 0.6, proximity: 0.52, size: 0.48, note: 'ranks for human review' },
    },
  ],
  session_history: [
    {
      query: 'swimming pools within 100 m of a road',
      plan: {
        target: { concept: 'swimming_pool', kind: 'instance', filters: { min_area_m2: null } },
        relations: [{ type: 'dwithin', reference_concept: 'road', distance_m: 100, negate: false }],
        limit: null,
        session_id: 'demo-session-001',
      },
    },
  ],
  not_found_message: null,
  _sample_data: true,
}

export default demoResults
