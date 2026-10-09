import React from 'react'
import './TopBar.css'

interface Props {
  onAttributionClick: () => void
  demoMode: boolean
}

export default function TopBar({ onAttributionClick, demoMode }: Props) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <span className="topbar-logo">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="10" stroke="#2DD4BF" strokeWidth="2"/>
            <circle cx="12" cy="12" r="4" fill="#2DD4BF" opacity="0.7"/>
            <line x1="12" y1="2" x2="12" y2="6" stroke="#2DD4BF" strokeWidth="2"/>
            <line x1="12" y1="18" x2="12" y2="22" stroke="#2DD4BF" strokeWidth="2"/>
            <line x1="2" y1="12" x2="6" y2="12" stroke="#2DD4BF" strokeWidth="2"/>
            <line x1="18" y1="12" x2="22" y2="12" stroke="#2DD4BF" strokeWidth="2"/>
          </svg>
          GeoLens AI
        </span>
        <span className="topbar-dataset-chip">
          SpaceNet Rio · OSM
        </span>
        {demoMode && (
          <span className="sample-badge" title="Demo mode: serving fixture data">
            Demo mode
          </span>
        )}
      </div>
      <nav className="topbar-right">
        <button
          className="topbar-nav-btn"
          onClick={onAttributionClick}
          aria-label="Data attribution"
        >
          Attribution
        </button>
      </nav>
    </header>
  )
}
