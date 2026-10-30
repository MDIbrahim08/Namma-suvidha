import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import LogoSplash from './LogoSplash'

describe('LogoSplash Component', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  it('renders video and skip button', () => {
    render(<LogoSplash />)
    expect(screen.getByRole('button', { name: /skip/i })).toBeInTheDocument()
    const video = document.querySelector('video')
    expect(video).toBeInTheDocument()
    expect(video).toHaveAttribute('muted')
  })

  it('immediately dismisses when prefers-reduced-motion is true', () => {
    window.matchMedia = vi.fn().mockImplementation(() => ({
      matches: true,
    }))
    const onFinish = vi.fn()
    render(<LogoSplash onFinish={onFinish} />)

    act(() => {
      vi.advanceTimersByTime(600)
    })
    expect(onFinish).toHaveBeenCalled()
  })

  it('dismisses when skip button is clicked', () => {
    const onFinish = vi.fn()
    render(<LogoSplash onFinish={onFinish} />)

    fireEvent.click(screen.getByRole('button', { name: /skip/i }))
    act(() => {
      vi.advanceTimersByTime(600)
    })
    expect(onFinish).toHaveBeenCalled()
  })

  it('dismisses after the 5.5s safety timeout', () => {
    const onFinish = vi.fn()
    render(<LogoSplash onFinish={onFinish} />)

    act(() => {
      vi.advanceTimersByTime(5600)
      vi.advanceTimersByTime(600)
    })
    expect(onFinish).toHaveBeenCalled()
  })

  it('gracefully dismisses on video error without crashing', () => {
    const onFinish = vi.fn()
    render(<LogoSplash onFinish={onFinish} />)

    const video = document.querySelector('video')
    if (video) {
      fireEvent.error(video)
    }
    act(() => {
      vi.advanceTimersByTime(600)
    })
    expect(onFinish).toHaveBeenCalled()
  })
})

