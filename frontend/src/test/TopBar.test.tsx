/**
 * Test suite for TopBar component
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import TopBar from '../components/TopBar'

describe('TopBar', () => {
  it('should render the logo and title', () => {
    const mockOnAttributionClick = vi.fn()
    
    render(
      <TopBar 
        onAttributionClick={mockOnAttributionClick} 
        demoMode={false} 
      />
    )
    
    expect(screen.getByText('GeoLens AI')).toBeInTheDocument()
    expect(screen.getByText('SpaceNet Rio · OSM')).toBeInTheDocument()
  })

  it('should show demo mode badge when demoMode is true', () => {
    const mockOnAttributionClick = vi.fn()
    
    render(
      <TopBar 
        onAttributionClick={mockOnAttributionClick} 
        demoMode={true} 
      />
    )
    
    expect(screen.getByText('Demo mode')).toBeInTheDocument()
    expect(screen.getByTitle('Demo mode: serving fixture data')).toBeInTheDocument()
  })

  it('should not show demo mode badge when demoMode is false', () => {
    const mockOnAttributionClick = vi.fn()
    
    render(
      <TopBar 
        onAttributionClick={mockOnAttributionClick} 
        demoMode={false} 
      />
    )
    
    expect(screen.queryByText('Demo mode')).not.toBeInTheDocument()
  })

  it('should call onAttributionClick when Attribution button is clicked', () => {
    const mockOnAttributionClick = vi.fn()
    
    render(
      <TopBar 
        onAttributionClick={mockOnAttributionClick} 
        demoMode={false} 
      />
    )
    
    const attributionButton = screen.getByText('Attribution')
    fireEvent.click(attributionButton)
    
    expect(mockOnAttributionClick).toHaveBeenCalledTimes(1)
  })

  it('should have proper accessibility attributes', () => {
    const mockOnAttributionClick = vi.fn()
    
    render(
      <TopBar 
        onAttributionClick={mockOnAttributionClick} 
        demoMode={false} 
      />
    )
    
    const attributionButton = screen.getByLabelText('Data attribution')
    expect(attributionButton).toBeInTheDocument()
    
    // Check that the SVG has aria-hidden attribute (it should be decorative)
    const svg = document.querySelector('svg')
    expect(svg).toHaveAttribute('aria-hidden', 'true')
  })
})