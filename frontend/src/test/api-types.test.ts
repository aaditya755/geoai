/**
 * Test suite for API types validation and JSON serialization
 * Tests the TypeScript interfaces defined in src/api/types.ts
 */

import { describe, it, expect } from 'vitest'
import type {
  Plan,
  Target,
  Relation,
  Result,
  ChatResponse,
  ChatRequest,
  PipelineStep,
  TargetFilters,
  ScoreBreakdown,
  HistoryEntry
} from '../api/types'

describe('API Types', () => {
  describe('Plan Structure', () => {
    it('should accept a minimal valid plan', () => {
      const plan: Plan = {
        target: {
          concept: 'swimming_pool',
          kind: 'instance',
          filters: { min_area_m2: null }
        },
        relations: [],
        limit: null,
        session_id: null
      }
      
      expect(plan.target.concept).toBe('swimming_pool')
      expect(plan.target.kind).toBe('instance')
      expect(plan.relations).toHaveLength(0)
    })

    it('should accept a full plan with relations', () => {
      const plan: Plan = {
        target: {
          concept: 'swimming_pool',
          kind: 'instance',
          filters: { min_area_m2: 100 }
        },
        relations: [
          {
            type: 'dwithin',
            reference_concept: 'road',
            distance_m: 100,
            negate: false
          }
        ],
        limit: 10,
        session_id: 'test-session-1'
      }
      
      expect(plan.target.concept).toBe('swimming_pool')
      expect(plan.relations).toHaveLength(1)
      expect(plan.relations[0].type).toBe('dwithin')
      expect(plan.relations[0].distance_m).toBe(100)
      expect(plan.limit).toBe(10)
    })

    it('should accept osm_only targets', () => {
      const target: Target = {
        concept: 'road',
        kind: 'osm_only',
        filters: { min_area_m2: null }
      }
      
      expect(target.kind).toBe('osm_only')
    })

    it('should accept intersects relations', () => {
      const relation: Relation = {
        type: 'intersects',
        reference_concept: 'park',
        distance_m: null,
        negate: false
      }
      
      expect(relation.type).toBe('intersects')
      expect(relation.distance_m).toBe(null)
    })

    it('should accept negate relations', () => {
      const relation: Relation = {
        type: 'dwithin',
        reference_concept: 'road',
        distance_m: 50,
        negate: true
      }
      
      expect(relation.negate).toBe(true)
    })
  })

  describe('Result Structure', () => {
    it('should accept a valid result', () => {
      const result: Result = {
        tile_id: 'tile_001',
        bbox: [-43.2, -22.9, -43.1, -22.8],
        score: 0.85,
        concept_id: 'swimming_pool_123',
        measured_distance_m: 150,
        rank: 1
      }
      
      expect(result.tile_id).toBe('tile_001')
      expect(result.bbox).toHaveLength(4)
      expect(result.score).toBe(0.85)
    })

    it('should accept optional score breakdown', () => {
      const scoreBreakdown: ScoreBreakdown = {
        confidence: 0.9,
        proximity: 0.8,
        size: 0.85,
        scorer: 'jev_ai',
        note: 'High confidence detection'
      }
      
      expect(scoreBreakdown.confidence).toBe(0.9)
      expect(scoreBreakdown.scorer).toBe('jev_ai')
    })
  })

  describe('ChatResponse Structure', () => {
    it('should accept a valid chat response', () => {
      const response: ChatResponse = {
        session_id: 'session_123',
        plan: {
          target: {
            concept: 'building',
            kind: 'instance',
            filters: { min_area_m2: null }
          },
          relations: [],
          limit: null,
          session_id: 'session_123'
        },
        candidates: [],
        results: [],
        session_history: [],
        not_found_message: null
      }
      
      expect(response.session_id).toBe('session_123')
      expect(response.plan.target.concept).toBe('building')
      expect(Array.isArray(response.results)).toBe(true)
    })

    it('should accept sample data flag', () => {
      const response: ChatResponse = {
        session_id: 'test',
        plan: {
          target: { concept: 'test', kind: 'instance', filters: { min_area_m2: null } },
          relations: [],
          limit: null,
          session_id: null
        },
        candidates: [],
        results: [],
        session_history: [],
        not_found_message: null,
        _sample_data: true
      }
      
      expect(response._sample_data).toBe(true)
    })
  })

  describe('ChatRequest Structure', () => {
    it('should accept a minimal chat request', () => {
      const request: ChatRequest = {
        query: 'Find swimming pools near roads'
      }
      
      expect(request.query).toBe('Find swimming pools near roads')
    })

    it('should accept optional session and language', () => {
      const request: ChatRequest = {
        query: 'Encontrar piscinas',
        session_id: 'session_456',
        lang: 'es'
      }
      
      expect(request.session_id).toBe('session_456')
      expect(request.lang).toBe('es')
    })
  })

  describe('PipelineStep enum', () => {
    it('should accept all valid pipeline steps', () => {
      const steps: PipelineStep[] = [
        'idle',
        'understanding', 
        'searching',
        'spatial',
        'ranking',
        'done'
      ]
      
      steps.forEach(step => {
        expect(typeof step).toBe('string')
      })
    })
  })

  describe('JSON Serialization', () => {
    it('should serialize and deserialize a complete plan', () => {
      const originalPlan: Plan = {
        target: {
          concept: 'swimming_pool',
          kind: 'instance',
          filters: { min_area_m2: 500 }
        },
        relations: [
          {
            type: 'dwithin',
            reference_concept: 'road',
            distance_m: 100,
            negate: false
          }
        ],
        limit: 10,
        session_id: 'test-session'
      }

      const jsonString = JSON.stringify(originalPlan)
      const parsedPlan: Plan = JSON.parse(jsonString)

      expect(parsedPlan.target.concept).toBe(originalPlan.target.concept)
      expect(parsedPlan.relations[0].distance_m).toBe(originalPlan.relations[0].distance_m)
      expect(parsedPlan.limit).toBe(originalPlan.limit)
    })

    it('should handle null values in serialization', () => {
      const plan: Plan = {
        target: {
          concept: 'test',
          kind: 'instance',
          filters: { min_area_m2: null }
        },
        relations: [],
        limit: null,
        session_id: null
      }

      const jsonString = JSON.stringify(plan)
      const parsed: Plan = JSON.parse(jsonString)

      expect(parsed.limit).toBe(null)
      expect(parsed.session_id).toBe(null)
      expect(parsed.target.filters.min_area_m2).toBe(null)
    })
  })
})