import React, { useState } from 'react'
import TopBar from './components/TopBar'
import ChatPanel from './components/ChatPanel'
import MapPanel from './components/MapPanel'
import ResultsPanel from './components/ResultsPanel'
import AttributionPage from './pages/AttributionPage'
import type { ChatResponse, PipelineStep } from './api/types'
import './App.css'

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'

export default function App() {
  const [page, setPage] = useState<'main' | 'attribution'>('main')
  const [response, setResponse] = useState<ChatResponse | null>(null)
  const [pipelineStep, setPipelineStep] = useState<PipelineStep>('idle')
  const [selectedResultIdx, setSelectedResultIdx] = useState<number | null>(null)

  if (page === 'attribution') {
    return <AttributionPage onBack={() => setPage('main')} />
  }

  return (
    <div className="app-layout">
      <TopBar
        onAttributionClick={() => setPage('attribution')}
        demoMode={DEMO_MODE}
      />
      <div className="app-body">
        <ChatPanel
          onResponse={setResponse}
          onPipelineStep={setPipelineStep}
          pipelineStep={pipelineStep}
          sessionId={response?.session_id ?? null}
          sampleData={response?._sample_data ?? false}
        />
        <MapPanel
          results={response?.results ?? []}
          selectedIdx={selectedResultIdx}
          onSelectResult={setSelectedResultIdx}
          sampleData={response?._sample_data ?? false}
        />
        <ResultsPanel
          response={response}
          selectedIdx={selectedResultIdx}
          onSelectResult={setSelectedResultIdx}
          sampleData={response?._sample_data ?? false}
        />
      </div>
    </div>
  )
}
