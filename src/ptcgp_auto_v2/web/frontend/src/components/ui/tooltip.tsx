import { type CSSProperties, type ReactNode, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import { cn } from '@/lib/utils'

interface TooltipProps {
  content: string
  children: ReactNode
  className?: string
  bubbleClassName?: string
  triggerClassName?: string
  focusable?: boolean
}

interface TooltipPosition {
  left: number
  top: number
}

export function Tooltip({
  content,
  children,
  className,
  bubbleClassName,
  triggerClassName,
  focusable = false
}: TooltipProps) {
  const tooltipId = useId()
  const triggerRef = useRef<HTMLSpanElement | null>(null)
  const bubbleRef = useRef<HTMLSpanElement | null>(null)
  const [open, setOpen] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [position, setPosition] = useState<TooltipPosition>({ left: 0, top: 0 })

  useEffect(() => {
    setMounted(true)
  }, [])

  useLayoutEffect(() => {
    if (!open) {
      return
    }

    const updatePosition = () => {
      const trigger = triggerRef.current
      const bubble = bubbleRef.current
      if (!trigger || !bubble) {
        return
      }

      const triggerRect = trigger.getBoundingClientRect()
      const bubbleRect = bubble.getBoundingClientRect()
      const viewportWidth = window.innerWidth
      const viewportHeight = window.innerHeight
      const gap = 8
      const padding = 10
      const centeredLeft = triggerRect.left + (triggerRect.width / 2) - (bubbleRect.width / 2)
      const clampedLeft = Math.min(
        Math.max(centeredLeft, padding),
        Math.max(padding, viewportWidth - bubbleRect.width - padding)
      )
      const placeAbove = triggerRect.top >= bubbleRect.height + gap + padding
      const aboveTop = triggerRect.top - bubbleRect.height - gap
      const belowTop = triggerRect.bottom + gap
      const clampedTop = placeAbove
        ? Math.max(padding, aboveTop)
        : Math.min(belowTop, Math.max(padding, viewportHeight - bubbleRect.height - padding))

      setPosition({ left: clampedLeft, top: clampedTop })
    }

    updatePosition()
    window.addEventListener('scroll', updatePosition, true)
    window.addEventListener('resize', updatePosition)
    return () => {
      window.removeEventListener('scroll', updatePosition, true)
      window.removeEventListener('resize', updatePosition)
    }
  }, [open, content])

  if (!content) {
    return <>{children}</>
  }

  const bubbleStyle: CSSProperties = {
    left: `${position.left}px`,
    top: `${position.top}px`
  }

  return (
    <span
      className={cn('tooltip-root', className)}
      tabIndex={focusable ? 0 : undefined}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <span
        ref={triggerRef}
        className={cn('tooltip-trigger', triggerClassName)}
        aria-describedby={open ? tooltipId : undefined}
      >
        {children}
      </span>
      {mounted && open && typeof document !== 'undefined' && createPortal(
        <span
          id={tooltipId}
          ref={bubbleRef}
          className={cn('tooltip-content', bubbleClassName)}
          role="tooltip"
          style={bubbleStyle}
        >
          {content}
        </span>,
        document.body
      )}
    </span>
  )
}
