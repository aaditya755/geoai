import React, { useState, useRef } from 'react'
import { chat } from '../api/client'
import type { ChatResponse, Plan, PipelineStep } from '../api/types'
import PipelineCard from './PipelineCard'
import PlanChips from './PlanChips'
import './ChatPanel.css'

const DEMO_QUERIES = [
  'swimming pools within 100 m of a road',
  'buildings within 200 m of a park',
  'primary roads near the tile boundary',
  'top 10 parking lots near a school',
]

interface Props {
  onResponse: (r: ChatResponse) => void
  onPipelineStep: (step: PipelineStep) => void
  pipelineStep: PipelineStep
  sessionId: string | null
  sampleData: boolean
}

export default function ChatPanel({
  onResponse, onPipelineStep, pipelineStep, sessionId, sampleData,
}: Props) {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastPlan, setLastPlan] = useState<Plan | null>(null)
  const [showPlanJson, setShowPlanJson] = useState(false)
  const [history, setHistory] = useState<{ query: string; answer: string }[]>([])
  const inputRef = useRef<HTMLTextAreaElement>(null)

  async function submit(q: string) {
    if (!q.trim() || loading) return
    setLoading(true)
    setError(null)

    // Simulate pipeline step progression
    const steps: PipelineStep[] = ['understanding', 'searching', 'spatial', 'ranking']
    let stepIdx = 0
    onPipelineStep('understanding')
    const stepTimer = setInterval(() => {
      stepIdx++
      if (stepIdx < steps.length) {
        onPipelineStep(steps[stepIdx])
      } else {
        clearInterval(stepTimer)
      }
    }, 700)

    try {
      const resp = await chat({ query: q, session_id: sessionId })
      clearInterval(stepTimer)
      onPipelineStep('done')
      onResponse(resp)
      setLastPlan(resp.plan)
      setHistory(h => [...h, {
        query: q,
        answer: resp.not_found_message
          ? resp.not_found_message
          : `${resp.results.length} result${resp.results.length !== 1 ? 's' : ''} found`,
      }])
      setQuery('')
    } catch (e: any) {
      clearInterval(stepTimer)
      onPipelineStep('idle')
      setError(e?.message ?? 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  function handleChipChange(updated: Plan) {
    // Re-run the query using the updated plan's fields as the new query text
    const dwithin = updated.relations.find(r => r.type === 'dwithin')
    let q = `${updated.target.concept}`
    if (dwithin) q += ` within ${dwithin.distance_m} m of a ${dwithin.reference_concept}`
    if (updated.limit) q += `, top ${updated.limit}`
    setQuery(q)
    submit(q)
  }

  return (
    <aside className="chat-panel" aria-label="Search panel">
      <div className="chat-history">
        {history.length === 0 && (
          <div className="chat-demo-queries">
            <p className="chat-hint">Try a query:</p>
            {DEMO_QUERIES.map(dq => (
              <button
                key={dq}
                className="chat-demo-query-btn"
                onClick={() => { setQuery(dq); submit(dq) }}
              >
                {dq}
              </button>
            ))}
          </div>
        )}
        {history.map((h, i) => (
          <div key={i} className="chat-turn">
            <div className="chat-bubble user">{h.query}</div>
            <div className="chat-bubble assistant">{h.answer}</div>
          </div>
        ))}
      </div>

      {pipelineStep !== 'idle' && (
        <PipelineCard currentStep={pipelineStep} />
      )}

      {lastPlan && (
        <div className="chat-plan-section">
          {sampleData && <span className="sample-badge">Sample data</span>}
          <PlanChips plan={lastPlan} onChange={handleChipChange} />
          <button
            className="chat-plan-toggle"
            onClick={() => setShowPlanJson(s => !s)}
            aria-expanded={showPlanJson}
          >
            {showPlanJson ? '▲ Hide plan JSON' : '▼ Show plan JSON'}
          </button>
          {showPlanJson && (
            <pre className="chat-plan-json">
              {JSON.stringify(lastPlan, null, 2)}
            </pre>
          )}
        </div>
      )}

      {error && (
        <div className="chat-error" role="alert">{error}</div>
      )}

      <form
        className="chat-input-row"
        onSubmit={e => { e.preventDefault(); submit(query) }}
      >
        <textarea
          ref={inputRef}
          className="chat-input"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submit(query)
            }
          }}
          placeholder="Ask about the imagery…"
          rows={2}
          disabled={loading}
          aria-label="Search query"
        />
        <button
          type="submit"
          className="chat-submit"
          disabled={loading || !query.trim()}
          aria-label="Search"
        >
          {loading ? '…' : '↑'}
        </button>
      </form>
    </aside>
  )
}
