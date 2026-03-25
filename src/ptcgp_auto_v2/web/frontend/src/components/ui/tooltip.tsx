import { type ReactNode } from 'react'

import { cn } from '@/lib/utils'

interface TooltipProps {
  content: string
  children: ReactNode
  className?: string
  bubbleClassName?: string
  triggerClassName?: string
  focusable?: boolean
}

export function Tooltip({
  content,
  children,
  className,
  bubbleClassName,
  triggerClassName,
  focusable = false
}: TooltipProps) {
  if (!content) {
    return <>{children}</>
  }

  return (
    <span className={cn('tooltip-root', className)} tabIndex={focusable ? 0 : -1}>
      <span className={cn('tooltip-trigger', triggerClassName)}>{children}</span>
      <span className={cn('tooltip-content', bubbleClassName)} role="tooltip">
        {content}
      </span>
    </span>
  )
}
