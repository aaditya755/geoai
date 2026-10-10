/**
 * Demo fixture for "buildings within 200 m of a park".
 * Verified: minimum building-to-park distance is 377 m, so 0 results is correct.
 */
import type { ChatResponse } from '../api/types'

const demo200m: ChatResponse = {
  session_id: 'demo-200m-001',
  plan: {
    target: { concept: 'building', kind: 'osm_only', filters: { min_area_m2: null } },
    relations: [{ type: 'dwithin', reference_concept: 'park', distance_m: 200, negate: false }],
    limit: null,
    session_id: 'demo-200m-001',
  },
  candidates: [],
  results: [],
  session_history: [],
  not_found_message:
    'No buildings found within 200 m of a park. ' +
    'The nearest buildings are ~377 m away. Try "buildings within 500 m of a park".',
  _sample_data: true,
}

export default demo200m
