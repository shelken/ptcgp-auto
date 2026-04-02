import { useEffect, useId, useMemo, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { useDismissibleLayer } from '@/hooks/use-dismissible-layer'
import { cn } from '@/lib/utils'

interface SearchableSelectOption {
  value: string
  label: string
  searchText?: string
}

interface SearchableSelectProps {
  value: string
  options: SearchableSelectOption[]
  onValueChange: (value: string) => void
  placeholder?: string
  searchPlaceholder?: string
  emptyLabel?: string
  pageSize?: number
  className?: string
  triggerClassName?: string
  disabled?: boolean
  prevPageLabel?: string
  nextPageLabel?: string
}

export function SearchableSelect({
  value,
  options,
  onValueChange,
  placeholder,
  searchPlaceholder,
  emptyLabel,
  pageSize = 12,
  className,
  triggerClassName,
  disabled = false,
  prevPageLabel,
  nextPageLabel
}: SearchableSelectProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)
  const rootRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)
  const searchInputId = useId()

  const selectedLabel = useMemo(
    () => options.find((item) => item.value === value)?.label ?? '',
    [options, value]
  )

  const filteredOptions = useMemo(() => {
    const keyword = query.trim().toLowerCase()
    if (!keyword) {
      return options
    }
    return options.filter((item) => {
      const label = item.label.toLowerCase()
      const extra = (item.searchText ?? '').toLowerCase()
      return label.includes(keyword) || extra.includes(keyword)
    })
  }, [options, query])

  const totalPages = Math.max(1, Math.ceil(filteredOptions.length / pageSize))

  useEffect(() => {
    if (!open) {
      return
    }
    setPage(0)
  }, [open, query])

  useDismissibleLayer({
    open,
    rootRef,
    onDismiss: () => setOpen(false)
  })

  useEffect(() => {
    if (open) {
      inputRef.current?.focus()
    }
  }, [open])

  const pageIndex = Math.min(page, totalPages - 1)
  const startIndex = pageIndex * pageSize
  const pageItems = filteredOptions.slice(startIndex, startIndex + pageSize)

  return (
    <div className={cn('searchable-select', className)} ref={rootRef}>
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={disabled}
        className={cn('searchable-select-trigger', triggerClassName)}
        onClick={() => setOpen((previous) => !previous)}
      >
        <span className="searchable-select-trigger-label">{selectedLabel || placeholder || '--'}</span>
        <span className="searchable-select-trigger-icon">▾</span>
      </Button>

      {open && !disabled && (
        <div className="searchable-select-panel">
          <input
            id={searchInputId}
            name={searchInputId}
            ref={inputRef}
            className="field-input searchable-select-input"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={searchPlaceholder || 'Search'}
          />

          <div className="searchable-select-list">
            {pageItems.length === 0 ? (
              <div className="searchable-select-empty">{emptyLabel || 'No data'}</div>
            ) : (
              pageItems.map((item) => (
                <button
                  key={item.value || '__empty__'}
                  type="button"
                  className={cn('searchable-select-item', item.value === value && 'is-selected')}
                  onClick={() => {
                    onValueChange(item.value)
                    setOpen(false)
                  }}
                >
                  {item.label}
                </button>
              ))
            )}
          </div>

          <div className="searchable-select-footer">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={pageIndex <= 0}
              onClick={() => setPage((previous) => Math.max(previous - 1, 0))}
            >
              {prevPageLabel || 'Prev'}
            </Button>
            <span className="searchable-select-page mono">{pageIndex + 1}/{totalPages}</span>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={pageIndex >= totalPages - 1}
              onClick={() => setPage((previous) => Math.min(previous + 1, totalPages - 1))}
            >
              {nextPageLabel || 'Next'}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
