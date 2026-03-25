import { useEffect, useMemo, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface DatePickerProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
  disabled?: boolean
  i18n?: {
    selectDateLabel?: string
    todayLabel?: string
    clearLabel?: string
    prevMonthLabel?: string
    nextMonthLabel?: string
    weekdayLabels?: string[]
  }
}

function parseDate(value: string): Date | null {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!match) {
    return null
  }
  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
    return null
  }
  const date = new Date(year, month - 1, day)
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
    return null
  }
  return date
}

function formatDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function monthStart(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

function monthLabel(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

function buildCalendarDays(currentMonth: Date): Date[] {
  const start = monthStart(currentMonth)
  const startWeekday = (start.getDay() + 6) % 7
  const gridStart = new Date(start)
  gridStart.setDate(start.getDate() - startWeekday)

  const days: Date[] = []
  for (let index = 0; index < 42; index += 1) {
    const day = new Date(gridStart)
    day.setDate(gridStart.getDate() + index)
    days.push(day)
  }
  return days
}

export function DatePicker({ value, onChange, placeholder, className, disabled = false, i18n }: DatePickerProps) {
  const [open, setOpen] = useState(false)
  const selectedDate = useMemo(() => parseDate(value), [value])
  const [viewMonth, setViewMonth] = useState<Date>(() => monthStart(selectedDate ?? new Date()))
  const rootRef = useRef<HTMLDivElement | null>(null)
  const weekdayLabels = useMemo(() => {
    const fallback = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    if (!Array.isArray(i18n?.weekdayLabels) || i18n.weekdayLabels.length !== 7) {
      return fallback
    }
    return i18n.weekdayLabels
  }, [i18n?.weekdayLabels])

  useEffect(() => {
    if (selectedDate) {
      setViewMonth(monthStart(selectedDate))
    }
  }, [selectedDate])

  useEffect(() => {
    if (!open) {
      return
    }
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null
      if (target && rootRef.current && !rootRef.current.contains(target)) {
        setOpen(false)
      }
    }
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
      }
    }
    window.addEventListener('pointerdown', onPointerDown)
    window.addEventListener('keydown', onEscape)
    return () => {
      window.removeEventListener('pointerdown', onPointerDown)
      window.removeEventListener('keydown', onEscape)
    }
  }, [open])

  const days = useMemo(() => buildCalendarDays(viewMonth), [viewMonth])
  const currentMonth = viewMonth.getMonth()
  const today = useMemo(() => formatDate(new Date()), [])

  return (
    <div className={cn('date-picker', className)} ref={rootRef}>
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="date-picker-trigger"
        disabled={disabled}
        onClick={() => setOpen((previous) => !previous)}
      >
        {value || placeholder || i18n?.selectDateLabel || 'Select date'}
      </Button>
      {open && !disabled && (
        <div className="date-picker-panel">
          <div className="date-picker-header">
            <Button
              type="button"
              size="sm"
              variant="outline"
              aria-label={i18n?.prevMonthLabel || 'Previous month'}
              onClick={() => {
                const next = new Date(viewMonth)
                next.setMonth(viewMonth.getMonth() - 1)
                setViewMonth(monthStart(next))
              }}
            >
              ←
            </Button>
            <div className="mono text-xs">{monthLabel(viewMonth)}</div>
            <Button
              type="button"
              size="sm"
              variant="outline"
              aria-label={i18n?.nextMonthLabel || 'Next month'}
              onClick={() => {
                const next = new Date(viewMonth)
                next.setMonth(viewMonth.getMonth() + 1)
                setViewMonth(monthStart(next))
              }}
            >
              →
            </Button>
          </div>

          <div className="date-picker-weekday-grid">
            {weekdayLabels.map((weekday) => (
              <div key={weekday} className="date-picker-weekday">{weekday}</div>
            ))}
          </div>

          <div className="date-picker-day-grid">
            {days.map((day) => {
              const dayValue = formatDate(day)
              const isSelected = dayValue === value
              const isToday = dayValue === today
              const isOutside = day.getMonth() !== currentMonth
              return (
                <button
                  key={dayValue}
                  type="button"
                  className={cn(
                    'date-picker-day',
                    isSelected && 'is-selected',
                    isToday && 'is-today',
                    isOutside && 'is-outside'
                  )}
                  onClick={() => {
                    onChange(dayValue)
                    setOpen(false)
                  }}
                >
                  {day.getDate()}
                </button>
              )
            })}
          </div>

          <div className="date-picker-footer">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                onChange(today)
                setOpen(false)
              }}
            >
              {i18n?.todayLabel || 'Today'}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                onChange('')
                setOpen(false)
              }}
            >
              {i18n?.clearLabel || 'Clear'}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
