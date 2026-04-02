import { useEffect, useMemo, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { useDismissibleLayer } from '@/hooks/use-dismissible-layer'
import { formatDateYmd, parseDateYmd } from '@/lib/time-display'
import { cn } from '@/lib/utils'

interface DatePickerProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
  disabled?: boolean
  todayValue?: string
  i18n?: {
    selectDateLabel?: string
    todayLabel?: string
    clearLabel?: string
    prevMonthLabel?: string
    nextMonthLabel?: string
    weekdayLabels?: string[]
  }
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

export function DatePicker({ value, onChange, placeholder, className, disabled = false, todayValue, i18n }: DatePickerProps) {
  const [open, setOpen] = useState(false)
  const selectedDate = useMemo(() => parseDateYmd(value), [value])
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

  useDismissibleLayer({
    open,
    rootRef,
    onDismiss: () => setOpen(false)
  })

  const days = useMemo(() => buildCalendarDays(viewMonth), [viewMonth])
  const currentMonth = viewMonth.getMonth()
  const today = useMemo(() => todayValue || formatDateYmd(new Date()), [todayValue])

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
              const dayValue = formatDateYmd(day)
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
