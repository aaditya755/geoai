import React from 'react'
import type { PipelineStep } from '../api/types'
import './PipelineCard.css'

const STEPS: { id: PipelineStep; label: string; icon: string }[] = [
  { id: 'understanding', label: 'Understanding query', icon: '🧠' },
  { id: 'searching',     label: 'Searching imagery',  icon: '🛰️' },
  { id: 'spatial',       label: 'Applying spatial rules', icon: '📐' },
  { id: 'ranking',       label: 'Ranking results',    icon: '🏆' },
]

const STEP_ORDER: PipelineStep[] = ['understanding', 'searching', 'spatial', 'ranking', 'done']

function stepIndex(step: PipelineStep): number {
  return STEP_ORDER.indexOf(step)
}

interface Props {
  currentStep: PipelineStep
}

export default function PipelineCard({ currentStep }: Props) {
  if (currentStep === 'idle') return null

  const currentIdx = stepIndex(currentStep)

  return (
    <div className="pipeline-card" role="status" aria-live="polite" aria-label="Pipeline progress">
      <div className="pipeline-steps">
        {STEPS.map((step, i) => {
          const done = currentStep === 'done' || currentIdx > i
          const active = currentIdx === i && currentStep !== 'done'

          return (
            <div
              key={step.id}
              className={`pipeline-step ${done ? 'done' : ''} ${active ? 'active' : ''}`}
            >
              <span className="pipeline-step-icon" aria-hidden="true">
                {done ? '✓' : step.icon}
              </span>
              <span className="pipeline-step-label">{step.label}</span>
              {active && <span className="pipeline-spinner" aria-hidden="true" />}
            </div>
          )
        })}
      </div>
    </div>
  )
}
