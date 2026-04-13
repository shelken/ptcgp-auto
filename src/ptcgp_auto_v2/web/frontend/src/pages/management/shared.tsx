import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, decodeSelectValue, encodeSelectValue } from '@/components/ui/select'
import { Tooltip } from '@/components/ui/tooltip'
import { tr } from '@/lib/i18n'

export interface InlineNoticeState {
  level: 'success' | 'error'
  text: string
}

export interface SearchableOption {
  value: string
  label: string
  searchText?: string
}

export interface SortOption {
  value: string
  labelKey: string
  fallback: string
}

const MANAGEMENT_STATE_STORAGE_PREFIX = 'ptcgp_management_state:'

export function managementStateKey(section: string, field: string): string {
  return `${MANAGEMENT_STATE_STORAGE_PREFIX}${section}:${field}`
}

export function toText(value: unknown, t?: Record<string, string>): string {
  if (value === null || value === undefined) {
    return '-'
  }
  if (typeof value === 'boolean') {
    const locale = t ?? {}
    return value ? tr(locale, 'label_read', 'Yes') : tr(locale, 'label_unread', 'No')
  }
  if (typeof value === 'number') {
    return String(value)
  }
  if (typeof value === 'string') {
    return value
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return '-'
    }
    if (typeof value[0] === 'string' || typeof value[0] === 'number') {
      return value.join(', ')
    }
    return `${value.length} ${tr(t ?? {}, 'label_total_records', 'items')}`
  }
  return JSON.stringify(value)
}

export function statusLabel(t: Record<string, string>, value: unknown): string {
  const key = typeof value === 'string' ? value : ''
  if (!key) {
    return '-'
  }
  return tr(t, `status_${key}`, key)
}

export function taskTypeLabel(t: Record<string, string>, value: unknown): string {
  const key = typeof value === 'string' ? value : ''
  if (!key) {
    return '-'
  }
  return tr(t, `task_${key}`, key)
}

export function toTotalCount(value: unknown, fallback: number): number {
  const parsed = Number(value)
  if (Number.isFinite(parsed) && parsed >= 0) {
    return Math.floor(parsed)
  }
  return Math.max(0, fallback)
}

export function sceneBadgeVariant(value: string): 'success' | 'warning' | 'danger' | 'info' | 'muted' {
  if (value === 'rare_card_obtained') {
    return 'success'
  }
  if (value === 'task_status') {
    return 'warning'
  }
  if (value === 'system_warning') {
    return 'danger'
  }
  return 'info'
}

export function renderBadge(text: string, variant: 'success' | 'warning' | 'danger' | 'info' | 'muted') {
  return <Badge variant={variant}>{text}</Badge>
}

export function InlineNotice({ notice }: { notice: InlineNoticeState | null }) {
  if (!notice) {
    return null
  }
  return (
    <div className={`surface-card text-sm ${notice.level === 'error' ? 'text-danger' : 'text-muted'}`}>
      {notice.text}
    </div>
  )
}

export function QueryTotalSummary({
  t,
  total,
  label
}: {
  t: Record<string, string>
  total: number
  label?: string
}) {
  return (
    <div className="text-xs text-muted">
      {label ? `${label} · ` : ''}
      {tr(t, 'label_query_total_records', '本次查询总记录数')}: <span className="mono">{total}</span>
    </div>
  )
}

export function buildAccountSelectOptions(
  accounts: Record<string, unknown>[],
  t: Record<string, string>,
  emptyLabel: string
): SearchableOption[] {
  const items: SearchableOption[] = [{ value: '', label: emptyLabel, searchText: emptyLabel }]
  for (const account of accounts) {
    const id = toText(account.id, t)
    const displayName = toText(account.display_name || account.nickname, t)
    const friendId = toText(account.friend_id, t)
    const gameId = toText(account.game_id, t)
    const label = gameId !== '-' ? `${id} ${displayName} (${friendId}) [${gameId}]` : `${id} ${displayName} (${friendId})`
    items.push({
      value: id,
      label,
      searchText: `${id} ${displayName} ${friendId} ${gameId}`
    })
  }
  return items
}

async function safeClipboardWrite(text: string): Promise<boolean> {
  if (!text || typeof navigator === 'undefined' || !navigator.clipboard || typeof navigator.clipboard.writeText !== 'function') {
    return false
  }
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

function formatFriendIdForDisplay(raw: string): string {
  const normalized = raw.trim()
  if (!normalized) {
    return '-'
  }
  const digitsOnly = normalized.replace(/\D+/g, '')
  if (!digitsOnly) {
    return normalized
  }
  const chunks = digitsOnly.match(/.{1,4}/g)
  return chunks ? chunks.join('-') : digitsOnly
}

export function CopyableFriendId({
  t,
  value,
  empty = '-'
}: {
  t: Record<string, string>
  value: string
  empty?: string
}) {
  const normalized = value.trim()
  const [toast, setToast] = useState<{ id: number; level: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    if (!toast) {
      return
    }
    const timer = window.setTimeout(() => setToast(null), 1600)
    return () => window.clearTimeout(timer)
  }, [toast])

  if (!normalized || normalized === '-') {
    return <span className="mono">{empty}</span>
  }
  const formatted = formatFriendIdForDisplay(normalized)
  return (
    <>
      <button
        type="button"
        className="friend-id-copy-btn mono"
        aria-label={tr(t, 'label_copy', '复制')}
        onClick={async () => {
          const copied = await safeClipboardWrite(normalized)
          setToast({
            id: Date.now(),
            level: copied ? 'success' : 'error',
            text: copied
              ? tr(t, 'msg_copied', '已复制！')
              : tr(t, 'msg_copy_failed', '复制失败')
          })
        }}
      >
        {formatted}
      </button>
      {toast && typeof document !== 'undefined' && createPortal(
        <div
          key={toast.id}
          className={`copy-toast ${toast.level === 'error' ? 'is-error' : 'is-success'}`}
          role="status"
          aria-live="polite"
        >
          {toast.text}
        </div>,
        document.body
      )}
    </>
  )
}

export function AccountIdentityCell({
  t,
  accountId,
  name,
  friendId,
  gameId
}: {
  t: Record<string, string>
  accountId: unknown
  name: unknown
  friendId?: unknown
  gameId?: unknown
}) {
  const idTextRaw = toText(accountId, t)
  const idText = idTextRaw === '-' ? '-' : `#${idTextRaw}`
  const nameText = toText(name, t)
  const friendIdText = toText(friendId, t)
  const gameIdText = toText(gameId, t)

  return (
    <div className="account-cell">
      <div className="account-primary mono">
        <span>{idText}</span>
        <span className="account-name">{nameText}</span>
      </div>
      {(friendIdText !== '-' || gameIdText !== '-') && (
        <div className="account-meta">
          {friendIdText !== '-' && <CopyableFriendId t={t} value={friendIdText} />}
          {gameIdText !== '-' && (
            <Tooltip content={gameIdText}>
              <span className="account-game-id-hint mono">gid</span>
            </Tooltip>
          )}
        </div>
      )}
    </div>
  )
}

export function searchableSelectLocale(t: Record<string, string>) {
  return {
    searchPlaceholder: tr(t, 'label_search', 'Search'),
    emptyLabel: tr(t, 'label_no_data', 'No data'),
    prevPageLabel: tr(t, 'btn_prev_page', 'Previous'),
    nextPageLabel: tr(t, 'btn_next_page', 'Next')
  }
}

export function TruncatedText({
  text,
  tooltip,
  className
}: {
  text: string
  tooltip?: string
  className?: string
}) {
  const hint = (tooltip ?? text).trim()
  const textRef = useRef<HTMLSpanElement | null>(null)
  const [truncated, setTruncated] = useState(false)

  useEffect(() => {
    const element = textRef.current
    if (!element || !hint) {
      setTruncated(false)
      return
    }

    const updateTruncated = () => {
      const isTruncated = element.scrollWidth > element.clientWidth || element.scrollHeight > element.clientHeight
      setTruncated(isTruncated)
    }

    updateTruncated()
    if (typeof ResizeObserver !== 'function') {
      window.addEventListener('resize', updateTruncated)
      return () => window.removeEventListener('resize', updateTruncated)
    }

    const observer = new ResizeObserver(updateTruncated)
    observer.observe(element)
    return () => observer.disconnect()
  }, [hint, text, className])

  const content = (
    <span
      ref={textRef}
      className={className ? `${className} text-truncate-1` : 'text-truncate-1'}
    >
      {text}
    </span>
  )

  if (!truncated || !hint) {
    return content
  }

  return <Tooltip content={hint}>{content}</Tooltip>
}

export function Pager({
  page,
  hasPrev,
  hasNext,
  onPrev,
  onNext,
  t
}: {
  page: number
  hasPrev: boolean
  hasNext: boolean
  onPrev: () => void
  onNext: () => void
  t: Record<string, string>
}) {
  return (
    <div className="pagination-row">
      <span className="text-xs mono">{tr(t, 'page_label', 'Page')} {page + 1}</span>
      <div className="filter-row">
        <Button size="sm" variant="outline" type="button" disabled={!hasPrev} onClick={onPrev}>
          {tr(t, 'btn_prev_page', 'Previous')}
        </Button>
        <Button size="sm" variant="outline" type="button" disabled={!hasNext} onClick={onNext}>
          {tr(t, 'btn_next_page', 'Next')}
        </Button>
      </div>
    </div>
  )
}

export function ListQueryControls({
  sortBy,
  sortOrder,
  pageSize,
  sortOptions,
  pageSizeOptions,
  onSortByChange,
  onSortOrderChange,
  onPageSizeChange,
  t,
  disableSortOrder = false,
  showSortControls = true
}: {
  sortBy: string
  sortOrder: 'asc' | 'desc'
  pageSize: number
  sortOptions: SortOption[]
  pageSizeOptions?: number[]
  onSortByChange: (value: string) => void
  onSortOrderChange: (value: 'asc' | 'desc') => void
  onPageSizeChange: (value: number) => void
  t: Record<string, string>
  disableSortOrder?: boolean
  showSortControls?: boolean
}) {
  const options = pageSizeOptions && pageSizeOptions.length > 0 ? pageSizeOptions : [10, 20, 50, 100]
  return (
    <div className="table-toolbar-layout table-toolbar--dense management-query-controls">
      <div className="table-toolbar-zone table-toolbar-zone--left">
        {showSortControls && (
          <>
            <div className="table-filter-item">
              <label className="section-subtitle">{tr(t, 'label_sort_by', 'Sort By')}</label>
              <Select value={encodeSelectValue(sortBy)} onValueChange={(value) => onSortByChange(decodeSelectValue(value))}>
                <SelectTrigger className="field-select table-control">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {sortOptions.map((option) => (
                    <SelectItem key={option.value} value={encodeSelectValue(option.value)}>
                      {tr(t, option.labelKey, option.fallback)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="table-filter-item">
              <label className="section-subtitle">{tr(t, 'label_sort_order', 'Order')}</label>
              <Select
                value={encodeSelectValue(sortOrder)}
                disabled={disableSortOrder}
                onValueChange={(value) => onSortOrderChange(decodeSelectValue(value) as 'asc' | 'desc')}
              >
                <SelectTrigger className="field-select table-control">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="asc">{tr(t, 'sort_order_asc', 'Ascending')}</SelectItem>
                  <SelectItem value="desc">{tr(t, 'sort_order_desc', 'Descending')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </>
        )}
      </div>

      <div className="table-toolbar-zone table-toolbar-zone--right">
        <div className="table-filter-item">
          <label className="section-subtitle">{tr(t, 'label_page_size', 'Page Size')}</label>
          <Select
            value={encodeSelectValue(String(pageSize))}
            onValueChange={(value) => onPageSizeChange(Number(decodeSelectValue(value)))}
          >
            <SelectTrigger className="field-select table-control">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {options.map((value) => (
                <SelectItem key={value} value={String(value)}>
                  {value}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  )
}
