import React, { useState } from 'react'
import type { ChatResponse, Result } from '../api/types'
import { exportGeoJSON } from '../api/client'
import './ResultsPanel.css'

type Tab = 'results' | 'ranking' | 'evidence' | 'export'

interface Props {
  response: ChatResponse | null
  selectedIdx: number | null
  onSelectResult: (i: number) => void
  sampleData: boolean
}

export default function ResultsPanel({ response, selectedIdx, onSelectResult, sampleData }: Props) {
  const [tab, setTab] = useState<Tab>('results')
  const [exporting, setExporting] = useState(false)

  const results = response?.results ?? []

  async function handleExport() {
    if (!results.length) return
    setExporting(true)
    try {
      const geojson = await exportGeoJSON(results)
      const blob = new Blob([JSON.stringify(geojson, null, 2)], { type: 'application/geo+json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `geolens-results${sampleData ? '-sample' : ''}.geojson`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      console.error('Export failed:', e)
    } finally {
      setExporting(false)
    }
  }

  return (
    <aside className="results-panel" aria-label="Results panel">
      <div className="results-tabs" role="tablist">
        {(['results', 'ranking', 'evidence', 'export'] as Tab[]).map(t => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            className={`results-tab ${tab === t ? 'active' : ''}`}
            onClick={() => setTab(t)}
          >
            {t === 'ranking' ? 'Ranking' : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      <div className="results-body" role="tabpanel">
        {sampleData && (
          <div className="results-sample-notice">
            <span className="sample-badge">Sample data</span>
          </div>
        )}

        {tab === 'results' && <ResultsTab results={results} selectedIdx={selectedIdx} onSelect={onSelectResult} />}
        {tab === 'ranking' && <RankingTab results={results} />}
        {tab === 'evidence' && <EvidenceTab results={results} selectedIdx={selectedIdx} sampleData={sampleData} />}
        {tab === 'export' && (
          <ExportTab
            results={results}
            onExport={handleExport}
            exporting={exporting}
            sampleData={sampleData}
          />
        )}
      </div>
    </aside>
  )
}

// ---------------------------------------------------------------------------
// Results tab
// ---------------------------------------------------------------------------

function ResultsTab({ results, selectedIdx, onSelect }: {
  results: Result[]
  selectedIdx: number | null
  onSelect: (i: number) => void
}) {
  if (!results.length) {
    return <div className="results-empty">No results yet. Try a query.</div>
  }
  return (
    <ul className="results-list" aria-label="Search results">
      {results.map((r, i) => (
        <li
          key={r.tile_id + i}
          className={`result-item ${i === selectedIdx ? 'selected' : ''}`}
          onClick={() => onSelect(i)}
          role="button"
          tabIndex={0}
          onKeyDown={e => e.key === 'Enter' && onSelect(i)}
          aria-current={i === selectedIdx}
        >
          <div className="result-item-header">
            <span className="result-rank">#{r.rank}</span>
            <span className="result-tile-id" title={r.tile_id}>{r.tile_id}</span>
            <span className="result-score">{(r.score * 100).toFixed(0)}%</span>
          </div>
          <div className="result-item-meta">
            {isFinite(r.measured_distance_m) && r.measured_distance_m >= 0 ? (
              <span className="result-dist">
                {r.measured_distance_m < 1
                  ? `${r.measured_distance_m.toFixed(1)} m`
                  : `${Math.round(r.measured_distance_m)} m`}
              </span>
            ) : (
              <span className="result-dist dimmed">distance not measured</span>
            )}
            <span className="result-concept">{r.concept_id}</span>
          </div>
        </li>
      ))}
    </ul>
  )
}

// ---------------------------------------------------------------------------
// Ranking tab — local scorer; labelled honestly
// ---------------------------------------------------------------------------

function RankingTab({ results }: { results: Result[] }) {
  if (!results.length) {
    return <div className="results-empty">No results yet.</div>
  }

  // Determine scorer from first result's breakdown
  const scorer = results[0]?.score_breakdown?.scorer ?? 'local'
  const scorerLabel = scorer === 'jev_ai' ? 'Jev AI' : 'Local scorer'
  const scorerNote = scorer === 'jev_ai'
    ? 'Jev AI ranking — advisory, for human review'
    : 'Local weighted scoring — advisory, for human review. Jev AI not active.'

  return (
    <div>
      <div className="ranking-scorer-label" title={scorerNote}>
        {scorerLabel} · <span className="ranking-scorer-note">{scorerNote}</span>
      </div>
      <ul className="results-list">
        {results.map((r, i) => {
          const bd = r.score_breakdown
          return (
            <li key={r.tile_id + i} className="result-item">
              <div className="result-item-header">
                <span className="result-rank">#{r.rank}</span>
                <span className="result-tile-id">{r.tile_id}</span>
                <span className="result-score">{(r.jev_score ?? r.score).toFixed(3)}</span>
              </div>
              {bd && (
                <div className="ranking-breakdown">
                  <BreakdownBar label="Confidence" value={bd.confidence} color="teal" />
                  <BreakdownBar label="Proximity" value={bd.proximity} color="violet" />
                  <BreakdownBar label="Size" value={bd.size} color="pink" />
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function BreakdownBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="breakdown-bar-row">
      <span className="breakdown-label">{label}</span>
      <div className="breakdown-track">
        <div
          className={`breakdown-fill breakdown-fill-${color}`}
          style={{ width: `${Math.round(value * 100)}%` }}
          aria-label={`${label}: ${(value * 100).toFixed(0)}%`}
        />
      </div>
      <span className="breakdown-value">{(value * 100).toFixed(0)}%</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Evidence tab — thumbnails (REQ-021)
// ---------------------------------------------------------------------------

function EvidenceTab({ results, selectedIdx, sampleData }: {
  results: Result[]
  selectedIdx: number | null
  sampleData: boolean
}) {
  if (!results.length) {
    return <div className="results-empty">No results yet.</div>
  }
  const r = selectedIdx !== null ? results[selectedIdx] : results[0]
  return (
    <div className="evidence-tab">
      <p className="evidence-hint">
        112×112 px crop centred on candidate.
        {sampleData && ' '}
        {sampleData && <span className="sample-badge">Sample data</span>}
      </p>
      <div className="evidence-thumb-container">
        {/* Placeholder — real thumbnails served from /evidence endpoint once P5.4 is complete */}
        <div className="evidence-thumb-placeholder" aria-label="Evidence thumbnail placeholder">
          <span className="evidence-thumb-tile">{r.tile_id}</span>
          <span className="evidence-thumb-label">Thumbnail available after GPU indexing (P3.3)</span>
        </div>
      </div>
      <div className="evidence-meta">
        <div>Score: {r.score.toFixed(4)}</div>
        <div>Concept: {r.concept_id}</div>
        <div>Distance: {isFinite(r.measured_distance_m)
          ? `${Math.round(r.measured_distance_m)} m`
          : 'not measured'}</div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Export tab (REQ-014)
// ---------------------------------------------------------------------------

function ExportTab({ results, onExport, exporting, sampleData }: {
  results: Result[]
  onExport: () => void
  exporting: boolean
  sampleData: boolean
}) {
  return (
    <div className="export-tab">
      <p className="export-desc">
        Export all {results.length} result{results.length !== 1 ? 's' : ''} as a GeoJSON
        FeatureCollection. Each feature includes <code>confidence</code> and{' '}
        <code>measured_distance_m</code> properties.
        {sampleData && (
          <> <span className="sample-badge">Sample data</span> — positions are illustrative.</>
        )}
      </p>
      <button
        className="export-btn"
        onClick={onExport}
        disabled={exporting || !results.length}
        aria-label="Download GeoJSON"
      >
        {exporting ? 'Exporting…' : '↓ Download GeoJSON'}
      </button>
      {sampleData && (
        <p className="export-sample-note">
          Note: sample data positions do not reflect real imagery coordinates.
        </p>
      )}
    </div>
  )
}
