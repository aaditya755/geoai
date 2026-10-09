import React, { useState } from 'react'
import type { Plan } from '../api/types'
import './PlanChips.css'

interface Props {
  plan: Plan
  onChange: (updated: Plan) => void
}

/**
 * Editable plan chips (REQ-020).
 * Each chip shows one field from the plan.
 * Clicking a chip lets the user edit its value, which triggers a re-run
 * via the onChange callback.
 *
 * Shows the English interpretation. Non-English input is already translated
 * to English by the backend before the plan is produced.
 */
export default function PlanChips({ plan, onChange }: Props) {
  const [editingField, setEditingField] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')

  function startEdit(field: string, current: string) {
    setEditingField(field)
    setEditValue(current)
  }

  function commitEdit(field: string) {
    const updated: Plan = JSON.parse(JSON.stringify(plan))
    if (field === 'concept') {
      updated.target.concept = editValue
    } else if (field === 'distance_m' && updated.relations[0]) {
      const v = parseFloat(editValue)
      if (!isNaN(v) && v >= 0) updated.relations[0].distance_m = v
    } else if (field === 'limit') {
      const v = parseInt(editValue, 10)
      updated.limit = isNaN(v) ? null : v
    }
    setEditingField(null)
    onChange(updated)
  }

  function handleKey(e: React.KeyboardEvent, field: string) {
    if (e.key === 'Enter') commitEdit(field)
    if (e.key === 'Escape') setEditingField(null)
  }

  const dwithinRel = plan.relations.find(r => r.type === 'dwithin')
  const intersectsRel = plan.relations.find(r => r.type === 'intersects')

  return (
    <div className="plan-chips" aria-label="Query plan interpretation">
      <Chip
        label="find"
        value={plan.target.concept}
        field="concept"
        editingField={editingField}
        editValue={editValue}
        onEdit={startEdit}
        onCommit={commitEdit}
        onEditChange={setEditValue}
        onKey={handleKey}
        color="teal"
      />
      <span className="plan-chips-kind-badge">{plan.target.kind}</span>

      {dwithinRel && (
        <>
          <span className="plan-chips-sep">within</span>
          <Chip
            label="m of"
            value={String(dwithinRel.distance_m ?? '?')}
            field="distance_m"
            editingField={editingField}
            editValue={editValue}
            onEdit={startEdit}
            onCommit={commitEdit}
            onEditChange={setEditValue}
            onKey={handleKey}
            color="violet"
          />
          <span className="plan-chips-sep">{dwithinRel.reference_concept}</span>
        </>
      )}

      {intersectsRel && (
        <>
          <span className="plan-chips-sep">intersecting</span>
          <span className="plan-chips-ref">{intersectsRel.reference_concept}</span>
        </>
      )}

      {plan.limit !== null && (
        <>
          <span className="plan-chips-sep">·  limit</span>
          <Chip
            label=""
            value={String(plan.limit)}
            field="limit"
            editingField={editingField}
            editValue={editValue}
            onEdit={startEdit}
            onCommit={commitEdit}
            onEditChange={setEditValue}
            onKey={handleKey}
            color="pink"
          />
        </>
      )}
    </div>
  )
}

interface ChipProps {
  label: string
  value: string
  field: string
  editingField: string | null
  editValue: string
  color: 'teal' | 'violet' | 'pink'
  onEdit: (field: string, current: string) => void
  onCommit: (field: string) => void
  onEditChange: (v: string) => void
  onKey: (e: React.KeyboardEvent, field: string) => void
}

function Chip({
  label, value, field, editingField, editValue, color,
  onEdit, onCommit, onEditChange, onKey,
}: ChipProps) {
  const isEditing = editingField === field
  return (
    <button
      className={`plan-chip plan-chip-${color}`}
      onClick={() => onEdit(field, value)}
      aria-label={`Edit ${field}: currently ${value}`}
    >
      {isEditing ? (
        <input
          autoFocus
          className="plan-chip-input"
          value={editValue}
          onChange={e => onEditChange(e.target.value)}
          onBlur={() => onCommit(field)}
          onKeyDown={e => onKey(e, field)}
          onClick={e => e.stopPropagation()}
          aria-label={`Edit ${field}`}
        />
      ) : (
        <>
          {label && <span className="plan-chip-label">{label} </span>}
          <span className="plan-chip-value">{value}</span>
          <span className="plan-chip-edit-icon" aria-hidden="true">✎</span>
        </>
      )}
    </button>
  )
}
