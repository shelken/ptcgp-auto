import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { useInfiniteTrigger } from '@/hooks/use-infinite-trigger'
import { usePersistedSearchParams } from '@/hooks/use-persisted-search-params'
import { buildQuery, fetchJson, requestFormJson, requestJson } from '@/lib/api'
import { getCardImageUrls, type CardImageAssets } from '@/lib/card-image'
import { tr } from '@/lib/i18n'

interface ManagementPageProps {
  lang: string
  t: Record<string, string>
  assets: CardImageAssets
}

interface ColumnDef {
  key: string
  label: string
  render?: (row: Record<string, unknown>) => string
  sortKey?: string
}

interface SortOption {
  value: string
  labelKey: string
  fallback: string
}

interface AccountPlanItemState {
  plan_id: number
  plan_name: string
  is_active: boolean
}

interface PlanTaskConfigState {
  enabled: boolean
  resetType: string
  intervalSeconds: number
}

interface InlineNoticeState {
  level: 'success' | 'error'
  text: string
}

const sections = [
  { key: 'accounts', labelKey: 'menu_accounts', fallback: 'Accounts' },
  { key: 'plans', labelKey: 'menu_plans', fallback: 'Plans' },
  { key: 'resources', labelKey: 'menu_resources', fallback: 'Resources' },
  { key: 'tasks', labelKey: 'menu_tasks', fallback: 'Tasks' },
  { key: 'metadata', labelKey: 'menu_metadata', fallback: 'Metadata' },
  { key: 'daily-gift', labelKey: 'menu_daily_gift', fallback: 'Daily Gift' },
  { key: 'friendships', labelKey: 'menu_friendships', fallback: 'Friendships' },
  { key: 'exchange-cards', labelKey: 'menu_exchange_cards', fallback: 'Exchange Cards' },
  { key: 'notifications', labelKey: 'menu_notifications', fallback: 'Notifications' }
] as const

const MANAGEMENT_STATE_STORAGE_PREFIX = 'ptcgp_management_state:'

function managementStateKey(section: string, field: string): string {
  return `${MANAGEMENT_STATE_STORAGE_PREFIX}${section}:${field}`
}

/**
 * 管理页筛选/排序/分页状态持久化（localStorage）
 */
function usePersistedState<T>(storageKey: string, initialValue: T) {
  const [value, setValue] = useState<T>(() => {
    const raw = window.localStorage.getItem(storageKey)
    if (raw === null) {
      return initialValue
    }
    try {
      return JSON.parse(raw) as T
    } catch {
      return initialValue
    }
  })

  useEffect(() => {
    window.localStorage.setItem(storageKey, JSON.stringify(value))
  }, [storageKey, value])

  return [value, setValue] as const
}

function toText(value: unknown, t?: Record<string, string>): string {
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

function formatTime(value: unknown): string {
  if (typeof value !== 'string' || value.length === 0) {
    return '-'
  }
  return value.replace('T', ' ').slice(0, 19)
}

function statusLabel(t: Record<string, string>, value: unknown): string {
  const key = typeof value === 'string' ? value : ''
  if (!key) {
    return '-'
  }
  return tr(t, `status_${key}`, key)
}

function giftStatusLabel(t: Record<string, string>, value: unknown): string {
  const key = typeof value === 'string' ? value : ''
  if (!key) {
    return '-'
  }
  return tr(t, `gift_status_${key}`, key)
}

function pairProgressLabel(t: Record<string, string>, value: unknown): string {
  const key = typeof value === 'string' ? value : ''
  if (!key) {
    return '-'
  }
  return tr(t, `gift_pair_progress_${key}`, key)
}

function taskTypeLabel(t: Record<string, string>, value: unknown): string {
  const key = typeof value === 'string' ? value : ''
  if (!key) {
    return '-'
  }
  return tr(t, `task_${key}`, key)
}

function requestTypeLabel(t: Record<string, string>, value: unknown): string {
  const key = typeof value === 'string' ? value : ''
  if (!key) {
    return '-'
  }
  return tr(t, `friend_request_type_${key}`, key)
}

function requestStatusLabel(t: Record<string, string>, value: unknown): string {
  const key = typeof value === 'string' ? value : ''
  if (!key) {
    return '-'
  }
  return tr(t, `friend_request_status_${key}`, key)
}

function InlineNotice({ notice }: { notice: InlineNoticeState | null }) {
  if (!notice) {
    return null
  }
  return (
    <div className={`surface-card text-sm ${notice.level === 'error' ? 'text-danger' : 'text-muted'}`}>
      {notice.text}
    </div>
  )
}

function SortableHeaderCell({
  label,
  sortKey,
  sortBy,
  sortOrder,
  onToggle,
  className
}: {
  label: string
  sortKey: string
  sortBy: string
  sortOrder: 'asc' | 'desc'
  onToggle: (sortKey: string) => void
  className?: string
}) {
  const isActive = sortBy === sortKey
  const direction = isActive ? (sortOrder === 'asc' ? '↑' : '↓') : ''
  return (
    <th
      role="button"
      tabIndex={0}
      className={className}
      style={{ cursor: 'pointer', userSelect: 'none' }}
      onClick={() => onToggle(sortKey)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onToggle(sortKey)
        }
      }}
    >
      {label}{direction ? ` ${direction}` : ''}
    </th>
  )
}

function exchangeStatusLabel(t: Record<string, string>, value: unknown): string {
  const key = typeof value === 'string' ? value : ''
  if (!key) {
    return '-'
  }
  return tr(t, `exchange_request_status_${key}`, key)
}

function Pager({
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

function DataGrid({
  rows,
  columns,
  t,
  sortBy,
  sortOrder,
  onSortChange
}: {
  rows: Record<string, unknown>[]
  columns: ColumnDef[]
  t: Record<string, string>
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
  onSortChange?: (sortKey: string) => void
}) {
  return (
    <div className="table-wrap">
      <table className="grid-table">
        <thead>
          <tr>
            {columns.map((col) => {
              if (onSortChange && sortBy && sortOrder && col.sortKey) {
                return (
                  <SortableHeaderCell
                    key={col.key}
                    label={col.label}
                    sortKey={col.sortKey}
                    sortBy={sortBy}
                    sortOrder={sortOrder}
                    onToggle={onSortChange}
                  />
                )
              }
              return <th key={col.key}>{col.label}</th>
            })}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="text-center text-muted">{tr(t, 'label_no_data', 'No data')}</td>
            </tr>
          )}
          {rows.map((row, rowIndex) => (
            <tr key={`${rowIndex}-${toText(row.id, t)}`}>
              {columns.map((col) => (
                <td key={`${rowIndex}-${col.key}`}>
                  {col.render ? col.render(row) : toText(row[col.key], t)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ListQueryControls({
  sortBy,
  sortOrder,
  pageSize,
  sortOptions,
  pageSizeOptions,
  onSortByChange,
  onSortOrderChange,
  onPageSizeChange,
  t,
  disableSortOrder = false
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
}) {
  const options = pageSizeOptions && pageSizeOptions.length > 0 ? pageSizeOptions : [10, 20, 50, 100]
  return (
    <div className="table-toolbar-layout table-toolbar--dense management-query-controls">
      <div className="table-toolbar-zone table-toolbar-zone--left">
        <div className="table-filter-item">
          <label className="section-subtitle">{tr(t, 'label_sort_by', 'Sort By')}</label>
          <select className="field-select table-control" value={sortBy} onChange={(event) => onSortByChange(event.target.value)}>
            {sortOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {tr(t, option.labelKey, option.fallback)}
              </option>
            ))}
          </select>
        </div>

        <div className="table-filter-item">
          <label className="section-subtitle">{tr(t, 'label_sort_order', 'Order')}</label>
          <select
            className="field-select table-control"
            value={sortOrder}
            disabled={disableSortOrder}
            onChange={(event) => onSortOrderChange(event.target.value as 'asc' | 'desc')}
          >
            <option value="asc">{tr(t, 'sort_order_asc', 'Ascending')}</option>
            <option value="desc">{tr(t, 'sort_order_desc', 'Descending')}</option>
          </select>
        </div>
      </div>

      <div className="table-toolbar-zone table-toolbar-zone--right">
        <div className="table-filter-item">
          <label className="section-subtitle">{tr(t, 'label_page_size', 'Page Size')}</label>
          <select
            className="field-select table-control"
            value={String(pageSize)}
            onChange={(event) => onPageSizeChange(Number(event.target.value))}
          >
            {options.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  )
}

function AccountsSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const queryClient = useQueryClient()
  const [q, setQ] = usePersistedState<string>(managementStateKey('accounts', 'q'), '')
  const [page, setPage] = usePersistedState<number>(managementStateKey('accounts', 'page'), 0)
  const [sortBy, setSortBy] = usePersistedState<string>(managementStateKey('accounts', 'sort_by'), 'id')
  const [sortOrder, setSortOrder] = usePersistedState<'asc' | 'desc'>(managementStateKey('accounts', 'sort_order'), 'asc')
  const [pageSize, setPageSize] = usePersistedState<number>(managementStateKey('accounts', 'page_size'), 10)
  const [editingAccount, setEditingAccount] = useState<Record<string, unknown> | null>(null)
  const [editingPlans, setEditingPlans] = useState<{ accountId: number; items: AccountPlanItemState[] } | null>(null)
  const [currentPlans, setCurrentPlans] = useState<Record<string, unknown>[]>([])
  const [editingPackConfig, setEditingPackConfig] = useState<{ accountId: number; setCode: string; boosterName: string } | null>(null)
  const [cardSets, setCardSets] = useState<Array<{ code: string; display_name: string }>>([])
  const [boosterOptions, setBoosterOptions] = useState<Array<{ name: string; display_name: string }>>([])
  const [notice, setNotice] = useState<InlineNoticeState | null>(null)

  const queryString = useMemo(
    () =>
      buildQuery({
        lang,
        q,
        page,
        page_size: pageSize,
        sort_by: sortBy,
        sort_order: sortOrder
      }),
    [lang, page, pageSize, q, sortBy, sortOrder]
  )

  const query = useQuery({
    queryKey: ['management-accounts', queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/accounts?${queryString}`)
  })

  const handleHeaderSort = useCallback((nextSortBy: string) => {
    setPage(0)
    if (sortBy === nextSortBy) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
      return
    }
    setSortBy(nextSortBy)
    setSortOrder('asc')
  }, [sortBy])

  const saveAccountMutation = useMutation({
    mutationFn: (payload: { accountId: number; nickname: string; remark: string }) =>
      requestJson<{ ok: boolean; message: string }>(`/api/react/management/accounts/${payload.accountId}`, {
        method: 'PUT',
        body: { nickname: payload.nickname, remark: payload.remark }
      }),
    onSuccess: (result) => {
      setNotice({ level: result.ok ? 'success' : 'error', text: result.message })
      setEditingAccount(null)
      queryClient.invalidateQueries({ queryKey: ['management-accounts'] })
    }
  })

  const savePlansMutation = useMutation({
    mutationFn: (payload: { accountId: number; items: AccountPlanItemState[] }) =>
      requestJson<{ ok: boolean }>(`/api/react/management/accounts/${payload.accountId}/plans`, {
        method: 'PUT',
        body: payload.items.map((item) => ({ plan_id: item.plan_id, is_active: item.is_active }))
      }),
    onSuccess: () => {
      setEditingPlans(null)
      queryClient.invalidateQueries({ queryKey: ['management-accounts'] })
    }
  })

  const savePackConfigMutation = useMutation({
    mutationFn: (payload: { accountId: number; setCode: string; boosterName: string }) =>
      requestJson<{ ok: boolean; message: string }>(`/api/react/management/accounts/${payload.accountId}/pack-config`, {
        method: 'PUT',
        body: { set_code: payload.setCode, booster_name: payload.boosterName }
      }),
    onSuccess: (result) => {
      setNotice({ level: result.ok ? 'success' : 'error', text: result.message })
      setEditingPackConfig(null)
      queryClient.invalidateQueries({ queryKey: ['management-accounts'] })
    }
  })

  const items = ((query.data?.items as unknown[]) ?? []) as Record<string, unknown>[]
  const packConfigs = (query.data?.pack_configs as Record<string, Record<string, unknown>>) ?? {}
  const autoPackMap = (query.data?.auto_pack_map as Record<string, Record<string, unknown>>) ?? {}

  async function openPlansEditor(accountId: number) {
    const data = await fetchJson<Record<string, unknown>>(`/api/react/management/accounts/${accountId}/plans?${buildQuery({ lang })}`)
    const current = ((data.current_assocs as unknown[]) ?? []) as Record<string, unknown>[]
    const available = ((data.available_plans as unknown[]) ?? []) as Record<string, unknown>[]

    const currentItems = current
      .map((item) => ({
        plan_id: Number(item.plan_id),
        plan_name: toText((item.task_plan as Record<string, unknown>)?.name, t),
        is_active: Boolean(item.is_active),
        priority: Number(item.priority ?? 0)
      }))
      .filter((item) => Number.isFinite(item.plan_id))
      .sort((a, b) => b.priority - a.priority)
      .map(({ plan_id, plan_name, is_active }) => ({ plan_id, plan_name, is_active }))

    const existingIds = new Set(currentItems.map((item) => item.plan_id))
    const candidateItems = available
      .map((item) => ({
        plan_id: Number(item.id),
        plan_name: toText(item.name, t),
        is_active: false
      }))
      .filter((item) => Number.isFinite(item.plan_id) && !existingIds.has(item.plan_id))

    setCurrentPlans(current)
    setEditingPlans({ accountId, items: [...currentItems, ...candidateItems] })
  }

  async function openPackConfigEditor(accountId: number) {
    const [config, sets] = await Promise.all([
      fetchJson<Record<string, unknown>>(`/api/react/management/accounts/${accountId}/pack-config?${buildQuery({ lang })}`),
      fetchJson<Array<{ code: string; display_name: string }>>('/api/react/management/card-sets')
    ])
    const setCode = String(config.selected_set_code ?? '')
    const boosterName = String(config.selected_booster_name ?? '')
    setCardSets(sets)
    if (setCode) {
      const boosters = await fetchJson<Array<{ name: string; display_name: string }>>(`/api/react/management/card-sets/${encodeURIComponent(setCode)}/boosters`)
      setBoosterOptions(boosters)
    } else {
      setBoosterOptions([])
    }
    setEditingPackConfig({ accountId, setCode, boosterName })
  }

  return (
    <section className="section-stack">
      <div className="surface-card section-stack">
        <div className="pagination-row">
          <div className="section-title">{tr(t, 'menu_accounts', 'Accounts')}</div>
          <div className="filter-row">
            <input className="field-input" value={q} onChange={(event) => setQ(event.target.value)} placeholder={tr(t, 'filter_account_id_placeholder', 'Search account')} />
            <Button type="button" size="sm" variant="outline" onClick={() => setPage(0)}>{tr(t, 'label_search', 'Search')}</Button>
          </div>
        </div>
        <ListQueryControls
          sortBy={sortBy}
          sortOrder={sortOrder}
          pageSize={pageSize}
          sortOptions={[
            { value: 'id', labelKey: 'col_id', fallback: 'ID' },
            { value: 'nickname', labelKey: 'col_nickname', fallback: 'Nickname' },
            { value: 'friend_id', labelKey: 'col_friend_id', fallback: 'Friend ID' }
          ]}
          onSortByChange={(value) => {
            setPage(0)
            setSortBy(value)
          }}
          onSortOrderChange={(value) => {
            setPage(0)
            setSortOrder(value)
          }}
          onPageSizeChange={(value) => {
            setPage(0)
            setPageSize(value)
          }}
          t={t}
        />

        {query.isLoading && <div className="text-sm text-muted">{tr(t, 'label_loading', 'Loading...')}</div>}
        {query.isError && <div className="text-sm text-danger">{(query.error as Error).message}</div>}
        <InlineNotice notice={notice} />

        {query.data && (
          <>
            <div className="table-wrap">
              <table className="grid-table">
                <thead>
                  <tr>
                    <SortableHeaderCell
                      label={tr(t, 'col_id', 'ID')}
                      sortKey="id"
                      sortBy={sortBy}
                      sortOrder={sortOrder}
                      onToggle={handleHeaderSort}
                    />
                    <th>{tr(t, 'col_nickname', 'Nickname')}</th>
                    <th>{tr(t, 'col_friend_id', 'Friend ID')}</th>
                    <th>{tr(t, 'col_plans', 'Plans')}</th>
                    <th>{tr(t, 'col_target_pack', 'Target Pack')}</th>
                    <th>{tr(t, 'col_actions', 'Actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.length === 0 && (
                    <tr>
                      <td colSpan={6} className="text-center text-muted">{tr(t, 'label_no_data', 'No data')}</td>
                    </tr>
                  )}
                  {items.map((item) => {
                    const accountId = Number(item.id)
                    const associations = ((item.task_plan_associations as unknown[]) ?? []) as Record<string, unknown>[]
                    const activePlanNames = associations
                      .filter((assoc) => Boolean(assoc.is_active) && typeof assoc.task_plan === 'object' && assoc.task_plan !== null)
                      .map((assoc) => toText((assoc.task_plan as Record<string, unknown>).name))
                    const config = packConfigs[String(accountId)]
                    const autoPack = autoPackMap[String(accountId)]
                    const targetPack =
                      config
                        ? `${toText(config.set_code, t)}/${toText(config.booster_name, t)}`
                        : autoPack
                          ? `${toText(autoPack.set_code, t)}/${toText(autoPack.booster_name, t)} (${tr(t, 'label_auto', 'Auto')})`
                          : '-'

                    return (
                      <tr key={accountId}>
                        <td className="mono">{toText(item.id)}</td>
                        <td>{toText(item.nickname || item.display_name, t)}</td>
                        <td className="mono">{toText(item.friend_id, t)}</td>
                        <td>{activePlanNames.length > 0 ? activePlanNames.join(', ') : '-'}</td>
                        <td>{targetPack}</td>
                        <td>
                          <div className="filter-row">
                            <Button type="button" size="sm" variant="outline" onClick={() => setEditingAccount(item)}>{tr(t, 'btn_edit', 'Edit')}</Button>
                            <Button type="button" size="sm" variant="outline" onClick={() => openPlansEditor(accountId)}>{tr(t, 'btn_edit_plans', 'Plans')}</Button>
                            <Button type="button" size="sm" variant="outline" onClick={() => openPackConfigEditor(accountId)}>{tr(t, 'btn_pack_config_title', 'Pack Config')}</Button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <Pager
              page={Number(query.data.page ?? 0)}
              hasPrev={Boolean(query.data.has_prev)}
              hasNext={Boolean(query.data.has_next)}
              onPrev={() => setPage((prev) => Math.max(prev - 1, 0))}
              onNext={() => setPage((prev) => prev + 1)}
              t={t}
            />
          </>
        )}
      </div>

      {editingAccount && (
        <div className="dialog-overlay" onClick={() => setEditingAccount(null)}>
          <div className="dialog-card section-stack" onClick={(event) => event.stopPropagation()}>
            <div className="section-title">{tr(t, 'modal_title_edit_account', 'Edit Account')} #{toText(editingAccount.id, t)}</div>
            <label className="section-subtitle">{tr(t, 'label_nickname', 'Nickname')}</label>
            <input
              className="field-input"
              value={toText(editingAccount.nickname)}
              onChange={(event) => setEditingAccount((prev) => (prev ? { ...prev, nickname: event.target.value } : null))}
            />
            <label className="section-subtitle">{tr(t, 'label_remark', 'Remark')}</label>
            <textarea
              className="field-textarea"
              value={toText(editingAccount.remark)}
              onChange={(event) => setEditingAccount((prev) => (prev ? { ...prev, remark: event.target.value } : null))}
            />
            <div className="filter-row">
              <Button type="button" size="sm" onClick={() => saveAccountMutation.mutate({ accountId: Number(editingAccount.id), nickname: toText(editingAccount.nickname), remark: toText(editingAccount.remark) })}>
                {tr(t, 'btn_save', 'Save')}
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={() => setEditingAccount(null)}>{tr(t, 'label_cancel', 'Cancel')}</Button>
            </div>
          </div>
        </div>
      )}

      {editingPlans && (
        <div className="dialog-overlay" onClick={() => setEditingPlans(null)}>
          <div className="dialog-card section-stack" onClick={(event) => event.stopPropagation()}>
            <div className="section-title">{tr(t, 'btn_edit_plans', 'Plans')} #{editingPlans.accountId}</div>
            <div className="section-subtitle">{tr(t, 'label_active_plans', 'Active Plans')}</div>
            <div className="filter-row">
              {currentPlans.map((item) => (
                <span key={toText(item.plan_id, t)} className="tag">{toText((item.task_plan as Record<string, unknown>)?.name, t)}</span>
              ))}
            </div>
            <div className="section-subtitle">{tr(t, 'option_select_plan', 'Select plan')}</div>
            <div className="section-stack">
              {editingPlans.items.map((planItem, index) => {
                const checked = planItem.is_active
                return (
                  <div key={planItem.plan_id} className="filter-row">
                    <label className="filter-row">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(event) => {
                          setEditingPlans((prev) => {
                            if (!prev) {
                              return prev
                            }
                            const nextItems = [...prev.items]
                            nextItems[index] = { ...nextItems[index], is_active: event.target.checked }
                            return { ...prev, items: nextItems }
                          })
                        }}
                      />
                      <span>{planItem.plan_name}</span>
                    </label>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={index === 0}
                      onClick={() => {
                        setEditingPlans((prev) => {
                          if (!prev || index === 0) {
                            return prev
                          }
                          const nextItems = [...prev.items]
                          const tmp = nextItems[index - 1]
                          nextItems[index - 1] = nextItems[index]
                          nextItems[index] = tmp
                          return { ...prev, items: nextItems }
                        })
                      }}
                    >
                      ↑
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={index === editingPlans.items.length - 1}
                      onClick={() => {
                        setEditingPlans((prev) => {
                          if (!prev || index === prev.items.length - 1) {
                            return prev
                          }
                          const nextItems = [...prev.items]
                          const tmp = nextItems[index + 1]
                          nextItems[index + 1] = nextItems[index]
                          nextItems[index] = tmp
                          return { ...prev, items: nextItems }
                        })
                      }}
                    >
                      ↓
                    </Button>
                  </div>
                )
              })}
            </div>
            <div className="filter-row">
              <Button type="button" size="sm" onClick={() => savePlansMutation.mutate(editingPlans)}>{tr(t, 'btn_save', 'Save')}</Button>
              <Button type="button" size="sm" variant="outline" onClick={() => setEditingPlans(null)}>{tr(t, 'label_cancel', 'Cancel')}</Button>
            </div>
          </div>
        </div>
      )}

      {editingPackConfig && (
        <div className="dialog-overlay" onClick={() => setEditingPackConfig(null)}>
          <div className="dialog-card section-stack" onClick={(event) => event.stopPropagation()}>
            <div className="section-title">{tr(t, 'btn_pack_config_title', 'Pack Config')} #{editingPackConfig.accountId}</div>
            <label className="section-subtitle">{tr(t, 'label_target_series', 'Target Series')}</label>
            <select
              className="field-select"
              value={editingPackConfig.setCode}
              onChange={async (event) => {
                const setCode = event.target.value
                if (!setCode) {
                  setBoosterOptions([])
                  setEditingPackConfig((prev) => (prev ? { ...prev, setCode: '', boosterName: '' } : null))
                  return
                }
                const boosters = await fetchJson<Array<{ name: string; display_name: string }>>(`/api/react/management/card-sets/${encodeURIComponent(setCode)}/boosters`)
                setBoosterOptions(boosters)
                setEditingPackConfig((prev) => (prev ? { ...prev, setCode, boosterName: boosters[0]?.name ?? '' } : null))
              }}
            >
              <option value="">{tr(t, 'label_no_pack_auto', 'No target pack (auto select)')}</option>
              {cardSets.map((setItem) => (
                <option key={setItem.code} value={setItem.code}>{setItem.display_name}</option>
              ))}
            </select>

            <label className="section-subtitle">{tr(t, 'label_target_booster', 'Target Booster')}</label>
            <select className="field-select" value={editingPackConfig.boosterName} onChange={(event) => setEditingPackConfig((prev) => (prev ? { ...prev, boosterName: event.target.value } : null))}>
              <option value="">{tr(t, 'label_none', '-- None --')}</option>
              {boosterOptions.map((booster) => (
                <option key={booster.name} value={booster.name}>{booster.display_name}</option>
              ))}
            </select>

            <div className="filter-row">
              <Button type="button" size="sm" onClick={() => savePackConfigMutation.mutate({ accountId: editingPackConfig.accountId, setCode: editingPackConfig.setCode, boosterName: editingPackConfig.boosterName })}>{tr(t, 'btn_save', 'Save')}</Button>
              <Button type="button" size="sm" variant="outline" onClick={() => setEditingPackConfig(null)}>{tr(t, 'label_cancel', 'Cancel')}</Button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

function PlansSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const queryClient = useQueryClient()
  const [q, setQ] = usePersistedState<string>(managementStateKey('plans', 'q'), '')
  const [page, setPage] = usePersistedState<number>(managementStateKey('plans', 'page'), 0)
  const [sortBy, setSortBy] = usePersistedState<string>(managementStateKey('plans', 'sort_by'), 'id')
  const [sortOrder, setSortOrder] = usePersistedState<'asc' | 'desc'>(managementStateKey('plans', 'sort_order'), 'asc')
  const [pageSize, setPageSize] = usePersistedState<number>(managementStateKey('plans', 'page_size'), 10)
  const [editingPlanId, setEditingPlanId] = useState<number | null>(null)
  const [isPlanEditorOpen, setIsPlanEditorOpen] = useState(false)
  const [planName, setPlanName] = useState('')
  const [planDesc, setPlanDesc] = useState('')
  const [taskOptions, setTaskOptions] = useState<string[]>([])
  const [resetTypeOptions, setResetTypeOptions] = useState<string[]>([])
  const [taskOrder, setTaskOrder] = useState<string[]>([])
  const [taskConfigMap, setTaskConfigMap] = useState<Record<string, PlanTaskConfigState>>({})
  const [notice, setNotice] = useState<InlineNoticeState | null>(null)

  const queryString = useMemo(
    () => buildQuery({ lang, q, page, page_size: pageSize, sort_by: sortBy, sort_order: sortOrder }),
    [lang, page, pageSize, q, sortBy, sortOrder]
  )

  const query = useQuery({
    queryKey: ['management-plans', queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/plans?${queryString}`)
  })

  const handleHeaderSort = useCallback((nextSortBy: string) => {
    setPage(0)
    if (sortBy === nextSortBy) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
      return
    }
    setSortBy(nextSortBy)
    setSortOrder('asc')
  }, [sortBy])

  const saveMutation = useMutation({
    mutationFn: (payload: { planId: number | null; name: string; description: string; tasks: string[]; taskConfigMap: Record<string, PlanTaskConfigState> }) => {
      const form = new FormData()
      if (payload.planId !== null) {
        form.set('plan_id', String(payload.planId))
      }
      form.set('name', payload.name)
      form.set('description', payload.description)
      form.set('task_order', JSON.stringify(payload.tasks))
      payload.tasks.forEach((taskType) => {
        form.set(`task_enabled_${taskType}`, 'on')
        const config = payload.taskConfigMap[taskType]
        if (!config) {
          return
        }
        form.set(`task_reset_${taskType}`, config.resetType || 'default')
        if (config.resetType === 'interval' && config.intervalSeconds > 0) {
          form.set(`task_interval_${taskType}`, String(config.intervalSeconds))
        }
      })
      return requestFormJson<{ ok: boolean; message: string; error?: string }>('/api/react/management/plans', {
        method: 'POST',
        body: form
      })
    },
    onSuccess: (result) => {
      if (!result.ok) {
        setNotice({ level: 'error', text: result.message })
        return
      }
      if (result.message) {
        setNotice({ level: 'success', text: result.message })
      }
      setEditingPlanId(null)
      setIsPlanEditorOpen(false)
      queryClient.invalidateQueries({ queryKey: ['management-plans'] })
    }
  })

  const deleteMutation = useMutation({
    mutationFn: (planId: number) => requestJson<{ ok: boolean; message: string }>(`/api/react/management/plans/${planId}`, { method: 'DELETE' }),
    onSuccess: (result) => {
      setNotice({ level: result.ok ? 'success' : 'error', text: result.message })
      queryClient.invalidateQueries({ queryKey: ['management-plans'] })
    }
  })

  async function openEditor(planId: number | null) {
    const data = await fetchJson<Record<string, unknown>>(`/api/react/management/plans/edit?${buildQuery({ lang, plan_id: planId ?? undefined })}`)
    const plan = (data.plan as Record<string, unknown> | null) ?? null
    const availableTasks = ((data.available_tasks as unknown[]) ?? []) as string[]
    const selectedTasks = ((plan?.task_types_list as unknown[]) ?? []) as string[]
    const configDict = (plan?.config_dict as Record<string, Record<string, unknown>> | undefined) ?? {}
    const normalizedTaskOrder = [...selectedTasks, ...availableTasks.filter((task) => !selectedTasks.includes(task))]
    const nextTaskConfigMap: Record<string, PlanTaskConfigState> = {}
    for (const taskType of normalizedTaskOrder) {
      const config = configDict[taskType] ?? {}
      const resetTypeRaw = String(config.reset_type ?? 'default')
      const resetType = resetTypeRaw.length > 0 ? resetTypeRaw : 'default'
      const intervalRaw = Number(config.interval_seconds ?? 3600)
      nextTaskConfigMap[taskType] = {
        enabled: selectedTasks.includes(taskType),
        resetType,
        intervalSeconds: Number.isFinite(intervalRaw) && intervalRaw > 0 ? intervalRaw : 3600
      }
    }

    setTaskOptions(availableTasks)
    setTaskOrder(normalizedTaskOrder)
    setResetTypeOptions(((data.reset_types as unknown[]) ?? []) as string[])
    setTaskConfigMap(nextTaskConfigMap)
    setPlanName(toText(plan?.name ?? ''))
    setPlanDesc(toText(plan?.description ?? ''))
    setEditingPlanId(planId)
    setIsPlanEditorOpen(true)
  }

  const items = ((query.data?.items as unknown[]) ?? []) as Record<string, unknown>[]

  return (
    <section className="section-stack">
      <div className="surface-card section-stack">
        <div className="pagination-row">
          <div className="section-title">{tr(t, 'menu_plans', 'Plans')}</div>
          <div className="filter-row">
            <input className="field-input" value={q} onChange={(event) => setQ(event.target.value)} placeholder={tr(t, 'label_search', 'Search')} />
            <Button type="button" size="sm" variant="outline" onClick={() => setPage(0)}>{tr(t, 'label_search', 'Search')}</Button>
            <Button type="button" size="sm" onClick={() => openEditor(null)}>{tr(t, 'btn_new_plan', 'New')}</Button>
          </div>
        </div>
        <ListQueryControls
          sortBy={sortBy}
          sortOrder={sortOrder}
          pageSize={pageSize}
          sortOptions={[
            { value: 'id', labelKey: 'col_id', fallback: 'ID' },
            { value: 'name', labelKey: 'col_name', fallback: 'Name' }
          ]}
          onSortByChange={(value) => {
            setPage(0)
            setSortBy(value)
          }}
          onSortOrderChange={(value) => {
            setPage(0)
            setSortOrder(value)
          }}
          onPageSizeChange={(value) => {
            setPage(0)
            setPageSize(value)
          }}
          t={t}
        />
        <InlineNotice notice={notice} />

        <DataGrid
          rows={items}
          columns={[
            { key: 'id', label: tr(t, 'col_id', 'ID'), sortKey: 'id' },
            { key: 'name', label: tr(t, 'col_name', 'Name'), sortKey: 'name' },
            { key: 'description', label: tr(t, 'col_description', 'Description') },
            { key: 'task_types_list', label: tr(t, 'col_task', 'Task'), render: (row) => toText(row.task_types_list, t) },
            {
              key: 'actions',
              label: tr(t, 'col_actions', 'Actions'),
              render: (row) => {
                const planId = Number(row.id)
                return `${tr(t, 'btn_edit', 'Edit')}#${planId}`
              }
            }
          ]}
          t={t}
          sortBy={sortBy}
          sortOrder={sortOrder}
          onSortChange={handleHeaderSort}
        />

        <div className="filter-row">
          {items.map((item) => (
            <div key={toText(item.id, t)} className="filter-row">
              <Button type="button" size="sm" variant="outline" onClick={() => openEditor(Number(item.id))}>{tr(t, 'btn_edit', 'Edit')} {toText(item.name, t)}</Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  const template = tr(t, 'confirm_delete_plan', "Delete plan '{name}'?")
                  const name = toText(item.name, t)
                  if (confirm(template.replace('{name}', name))) {
                    deleteMutation.mutate(Number(item.id))
                  }
                }}
              >
                {tr(t, 'btn_delete', 'Delete')}
              </Button>
            </div>
          ))}
        </div>

        <Pager
          page={Number(query.data?.page ?? 0)}
          hasPrev={Boolean(query.data?.has_prev)}
          hasNext={Boolean(query.data?.has_next)}
          onPrev={() => setPage((prev) => Math.max(prev - 1, 0))}
          onNext={() => setPage((prev) => prev + 1)}
          t={t}
        />
      </div>

      {isPlanEditorOpen && (
        <div className="dialog-overlay" onClick={() => { setEditingPlanId(null); setIsPlanEditorOpen(false) }}>
          <div className="dialog-card section-stack" onClick={(event) => event.stopPropagation()}>
            <div className="section-title">
              {editingPlanId ? `${tr(t, 'btn_edit', 'Edit')} #${editingPlanId}` : tr(t, 'modal_title_new_plan', 'New Plan')}
            </div>
            <label className="section-subtitle">{tr(t, 'label_name', 'Name')}</label>
            <input className="field-input" value={planName} onChange={(event) => setPlanName(event.target.value)} />
            <label className="section-subtitle">{tr(t, 'label_description', 'Description')}</label>
            <textarea className="field-textarea" value={planDesc} onChange={(event) => setPlanDesc(event.target.value)} />
            <label className="section-subtitle">{tr(t, 'label_task_config', 'Task Config')}</label>
            <div className="section-stack">
              {(taskOrder.length > 0 ? taskOrder : taskOptions).map((task, index) => {
                const config = taskConfigMap[task] ?? {
                  enabled: false,
                  resetType: 'default',
                  intervalSeconds: 3600
                }
                return (
                  <div key={task} className="surface-card section-stack">
                    <div className="filter-row">
                      <label className="filter-row">
                        <input
                          type="checkbox"
                          checked={config.enabled}
                          onChange={(event) => {
                            const enabled = event.target.checked
                            setTaskConfigMap((prev) => ({
                              ...prev,
                              [task]: { ...config, enabled }
                            }))
                          }}
                        />
                        <span>{taskTypeLabel(t, task)}</span>
                      </label>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={index === 0}
                        onClick={() => {
                          setTaskOrder((prev) => {
                            if (index === 0) {
                              return prev
                            }
                            const next = [...prev]
                            const tmp = next[index - 1]
                            next[index - 1] = next[index]
                            next[index] = tmp
                            return next
                          })
                        }}
                      >
                        ↑
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={index === taskOrder.length - 1}
                        onClick={() => {
                          setTaskOrder((prev) => {
                            if (index === prev.length - 1) {
                              return prev
                            }
                            const next = [...prev]
                            const tmp = next[index + 1]
                            next[index + 1] = next[index]
                            next[index] = tmp
                            return next
                          })
                        }}
                      >
                        ↓
                      </Button>
                    </div>
                    <div className="filter-row">
                      <select
                        className="field-select"
                        value={config.resetType}
                        onChange={(event) => {
                          const resetType = event.target.value
                          setTaskConfigMap((prev) => ({
                            ...prev,
                            [task]: { ...config, resetType }
                          }))
                        }}
                      >
                        {resetTypeOptions.map((resetType) => (
                          <option key={resetType} value={resetType}>
                            {tr(t, `reset_type_${resetType}`, resetType)}
                          </option>
                        ))}
                        {!resetTypeOptions.includes('default') && <option value="default">{tr(t, 'label_default', 'default')}</option>}
                      </select>
                      {config.resetType === 'interval' && (
                        <input
                          className="field-input"
                          type="number"
                          min={1}
                          value={config.intervalSeconds}
                          onChange={(event) => {
                            const intervalSeconds = Number(event.target.value)
                            setTaskConfigMap((prev) => ({
                              ...prev,
                              [task]: {
                                ...config,
                                intervalSeconds: Number.isFinite(intervalSeconds) && intervalSeconds > 0 ? intervalSeconds : 1
                              }
                            }))
                          }}
                          placeholder={tr(t, 'label_interval_seconds', 'seconds')}
                        />
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="filter-row">
              <Button
                type="button"
                size="sm"
                onClick={() => {
                  const enabledOrderedTasks = taskOrder.filter((task) => taskConfigMap[task]?.enabled)
                  saveMutation.mutate({
                    planId: editingPlanId,
                    name: planName.trim(),
                    description: planDesc.trim(),
                    tasks: enabledOrderedTasks,
                    taskConfigMap
                  })
                }}
              >
                {tr(t, 'btn_save', 'Save')}
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={() => { setEditingPlanId(null); setIsPlanEditorOpen(false) }}>{tr(t, 'label_cancel', 'Cancel')}</Button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

function ResourcesSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const [q, setQ] = usePersistedState<string>(managementStateKey('resources', 'q'), '')
  const [page, setPage] = usePersistedState<number>(managementStateKey('resources', 'page'), 0)
  const [view, setView] = usePersistedState<string>(managementStateKey('resources', 'view'), 'stats')
  const [sortBy, setSortBy] = usePersistedState<string>(managementStateKey('resources', 'sort_by'), 'id')
  const [sortOrder, setSortOrder] = usePersistedState<'asc' | 'desc'>(managementStateKey('resources', 'sort_order'), 'asc')
  const [pageSize, setPageSize] = usePersistedState<number>(managementStateKey('resources', 'page_size'), 20)

  const queryString = useMemo(
    () => buildQuery({ lang, q, page, page_size: pageSize, view, sort_by: sortBy, sort_order: sortOrder }),
    [lang, page, pageSize, q, sortBy, sortOrder, view]
  )
  const query = useQuery({
    queryKey: ['management-resources', queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/resources?${queryString}`)
  })

  const handleHeaderSort = useCallback((nextSortBy: string) => {
    setPage(0)
    if (sortBy === nextSortBy) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
      return
    }
    setSortBy(nextSortBy)
    setSortOrder('asc')
  }, [sortBy])

  const items = ((query.data?.items as unknown[]) ?? []) as Record<string, unknown>[]
  const seriesList = (((query.data?.series_list as unknown[]) ?? []) as string[])
  const accountNumber = new Intl.NumberFormat('en-US')
  const sortOptions = useMemo<SortOption[]>(() => {
    if (view === 'pack-points') {
      return [
        { value: 'id', labelKey: 'col_id', fallback: 'ID' },
        { value: 'nickname', labelKey: 'col_nickname', fallback: 'Nickname' },
        { value: 'friend_id', labelKey: 'col_friend_id', fallback: 'Friend ID' },
        ...seriesList.map((seriesCode) => ({
          value: `series:${seriesCode}`,
          labelKey: `series_sort_${seriesCode}`,
          fallback: `Series Points (${seriesCode})`
        }))
      ]
    }
    return [
      { value: 'id', labelKey: 'col_id', fallback: 'ID' },
      { value: 'nickname', labelKey: 'col_nickname', fallback: 'Nickname' },
      { value: 'friend_id', labelKey: 'col_friend_id', fallback: 'Friend ID' },
      { value: 'exchange_points', labelKey: 'col_exchange_points', fallback: 'Exchange Points' },
      { value: 'pack_hourglass_count', labelKey: 'col_pack_hourglass', fallback: 'Pack Hourglass' },
      { value: 'updated_at', labelKey: 'col_updated_at', fallback: 'Updated At' }
    ]
  }, [seriesList, view])

  return (
    <section className="surface-card section-stack">
      <div className="pagination-row">
        <div className="section-title">{tr(t, 'menu_resources', 'Resources')}</div>
        <div className="filter-row">
          <Button
            type="button"
            size="sm"
            variant={view === 'stats' ? 'default' : 'outline'}
            onClick={() => {
              setView('stats')
              setSortBy('id')
              setSortOrder('asc')
              setPage(0)
            }}
          >
            {tr(t, 'tab_resource_stats', 'Stats')}
          </Button>
          <Button
            type="button"
            size="sm"
            variant={view === 'pack-points' ? 'default' : 'outline'}
            onClick={() => {
              setView('pack-points')
              setSortBy('id')
              setSortOrder('asc')
              setPage(0)
            }}
          >
            {tr(t, 'tab_resource_pack_points', 'Pack Points')}
          </Button>
          <input className="field-input" value={q} onChange={(event) => setQ(event.target.value)} placeholder={tr(t, 'filter_account_search_placeholder', 'Search account')} />
          <Button type="button" size="sm" variant="outline" onClick={() => setPage(0)}>{tr(t, 'label_search', 'Search')}</Button>
        </div>
      </div>
      <ListQueryControls
        sortBy={sortBy}
        sortOrder={sortOrder}
        pageSize={pageSize}
        sortOptions={sortOptions.map((option) =>
          option.value.startsWith('series:')
            ? { ...option, fallback: `${tr(t, 'label_series_points', 'Series Points')} (${option.value.split(':')[1]})` }
            : option
        )}
        onSortByChange={(value) => {
          setPage(0)
          setSortBy(value)
        }}
        onSortOrderChange={(value) => {
          setPage(0)
          setSortOrder(value)
        }}
        onPageSizeChange={(value) => {
          setPage(0)
          setPageSize(value)
        }}
        t={t}
        pageSizeOptions={[10, 20, 50, 100]}
      />

      {view === 'stats' ? (
        <div className="table-wrap">
          <table className="grid-table">
            <thead>
              <tr>
                <SortableHeaderCell
                  label={tr(t, 'col_account', 'Account')}
                  sortKey="id"
                  sortBy={sortBy}
                  sortOrder={sortOrder}
                  onToggle={handleHeaderSort}
                />
                <SortableHeaderCell
                  label={tr(t, 'col_exchange_points', 'Exchange Points')}
                  sortKey="exchange_points"
                  sortBy={sortBy}
                  sortOrder={sortOrder}
                  onToggle={handleHeaderSort}
                />
                <SortableHeaderCell
                  label={tr(t, 'col_pack_hourglass', 'Pack Hourglass')}
                  sortKey="pack_hourglass_count"
                  sortBy={sortBy}
                  sortOrder={sortOrder}
                  onToggle={handleHeaderSort}
                />
                <SortableHeaderCell
                  label={tr(t, 'col_updated_at', 'Updated At')}
                  sortKey="updated_at"
                  sortBy={sortBy}
                  sortOrder={sortOrder}
                  onToggle={handleHeaderSort}
                />
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr>
                  <td colSpan={4} className="text-center text-muted">{tr(t, 'empty_resource_stats', 'No resource data')}</td>
                </tr>
              )}
              {items.map((row) => {
                const accountId = Number(row.account_id ?? 0)
                const nickname = toText(row.nickname, t)
                const friendId = toText(row.friend_id, t)
                const exchangePoints = Number(row.exchange_points)
                const hourglass = Number(row.pack_hourglass_count)
                return (
                  <tr key={`resource-stats-${accountId}`}>
                    <td>
                      <div className="mono">#{accountId} {nickname}</div>
                      {friendId !== '-' && (
                        <div className="text-xs text-muted">{tr(t, 'col_friend_id', 'Friend ID')}: {friendId}</div>
                      )}
                    </td>
                    <td className="mono">
                      {Number.isFinite(exchangePoints) ? accountNumber.format(exchangePoints) : '-'}
                    </td>
                    <td className="mono">
                      {Number.isFinite(hourglass) ? accountNumber.format(hourglass) : '-'}
                    </td>
                    <td className="mono">{formatTime(row.updated_at)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="grid-table resource-pack-table">
            <thead>
              <tr>
                <SortableHeaderCell
                  label={tr(t, 'col_account', 'Account')}
                  sortKey="id"
                  sortBy={sortBy}
                  sortOrder={sortOrder}
                  onToggle={handleHeaderSort}
                />
                {seriesList.map((series) => (
                  <SortableHeaderCell
                    key={`series-header-${series}`}
                    label={series}
                    sortKey={`series:${series}`}
                    sortBy={sortBy}
                    sortOrder={sortOrder}
                    onToggle={handleHeaderSort}
                    className="mono"
                  />
                ))}
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr>
                  <td colSpan={Math.max(2, seriesList.length + 1)} className="text-center text-muted">
                    {tr(t, 'empty_resource_pack_points', 'No pack point data')}
                  </td>
                </tr>
              )}
              {items.map((row) => {
                const accountId = Number(row.account_id ?? 0)
                const nickname = toText(row.nickname, t)
                const friendId = toText(row.friend_id, t)
                const seriesPoints = ((row.series_points as Record<string, unknown> | undefined) ?? {})
                return (
                  <tr key={`resource-points-${accountId}`}>
                    <td>
                      <div className="mono">#{accountId} {nickname}</div>
                      {friendId !== '-' && (
                        <div className="text-xs text-muted">{tr(t, 'col_friend_id', 'Friend ID')}: {friendId}</div>
                      )}
                    </td>
                    {seriesList.map((series) => {
                      const points = Number(seriesPoints[series] ?? NaN)
                      return (
                        <td key={`resource-points-${accountId}-${series}`} className="mono">
                          {Number.isFinite(points) ? accountNumber.format(points) : '-'}
                        </td>
                      )
                    })}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <Pager
        page={Number(query.data?.page ?? 0)}
        hasPrev={Boolean(query.data?.has_prev)}
        hasNext={Boolean(query.data?.has_next)}
        onPrev={() => setPage((prev) => Math.max(prev - 1, 0))}
        onNext={() => setPage((prev) => prev + 1)}
        t={t}
      />
    </section>
  )
}

function TasksSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const queryClient = useQueryClient()
  const [page, setPage] = usePersistedState<number>(managementStateKey('tasks', 'page'), 0)
  const [pageSize, setPageSize] = usePersistedState<number>(managementStateKey('tasks', 'page_size'), 20)
  const [status, setStatus] = usePersistedState<string>(managementStateKey('tasks', 'status'), '')
  const [taskType, setTaskType] = usePersistedState<string>(managementStateKey('tasks', 'task_type'), '')
  const [accountKeyword, setAccountKeyword] = usePersistedState<string>(managementStateKey('tasks', 'account_keyword'), '')
  const [sortBy, setSortBy] = usePersistedState<string>(managementStateKey('tasks', 'sort_by'), 'dispatch_priority')
  const [sortOrder, setSortOrder] = usePersistedState<'asc' | 'desc'>(managementStateKey('tasks', 'sort_order'), 'asc')
  const [notice, setNotice] = useState<InlineNoticeState | null>(null)

  const normalizedAccountKeyword = accountKeyword.trim()
  const selectedAccountMatch = normalizedAccountKeyword.match(/^(\d+)/)
  const selectedAccountId = selectedAccountMatch?.[1] ?? ''
  const selectedAccountQuery = selectedAccountId ? '' : normalizedAccountKeyword

  const accountOptionsQuery = useQuery({
    queryKey: ['management-task-account-options', normalizedAccountKeyword],
    queryFn: () =>
      fetchJson<{ accounts: Array<Record<string, unknown>> }>(
        `/api/react/management/tasks/account-options?${buildQuery({ q: normalizedAccountKeyword })}`
      ),
    enabled: normalizedAccountKeyword.length > 0
  })

  const queryString = useMemo(
    () =>
      buildQuery({
        lang,
        page,
        page_size: pageSize,
        status: status || undefined,
        task_type: taskType || undefined,
        account_id: selectedAccountId || undefined,
        account_q: selectedAccountQuery || undefined,
        sort_by: sortBy,
        sort_order: sortOrder
      }),
    [lang, page, pageSize, selectedAccountId, selectedAccountQuery, sortBy, sortOrder, status, taskType]
  )
  const query = useQuery({
    queryKey: ['management-tasks', queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/tasks?${queryString}`)
  })

  const handleHeaderSort = useCallback((nextSortBy: string) => {
    setPage(0)
    if (sortBy === nextSortBy) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
      return
    }
    setSortBy(nextSortBy)
    setSortOrder('asc')
  }, [sortBy])

  const resetMutation = useMutation({
    mutationFn: () =>
      requestJson<{ ok: boolean; message: string }>('/api/react/management/tasks/reset-completed', {
        method: 'POST',
        body: {
          status: status ? [status] : [],
          task_type: taskType ? [taskType] : [],
          account_id: selectedAccountId || null
        }
      }),
    onSuccess: (result) => {
      setNotice({ level: result.ok ? 'success' : 'error', text: result.message })
      queryClient.invalidateQueries({ queryKey: ['management-tasks'] })
    }
  })

  const rows = ((query.data?.items as unknown[]) ?? []) as Record<string, unknown>[]
  const statusOptions = ((query.data?.status_options as unknown[]) ?? []) as string[]
  const taskTypeOptions = ((query.data?.task_types as unknown[]) ?? []) as string[]
  const accountOptions = ((accountOptionsQuery.data?.accounts as unknown[]) ?? []) as Record<string, unknown>[]

  return (
    <section className="surface-card section-stack">
      <div className="section-title">{tr(t, 'menu_tasks', 'Tasks')}</div>

      <div className="table-toolbar-layout table-toolbar--dense management-query-controls">
        <div className="table-toolbar-zone table-toolbar-zone--left">
          <div className="table-filter-item">
            <label className="section-subtitle">{tr(t, 'filter_status', 'Status')}</label>
            <select
              className="field-select table-control"
              value={status}
              onChange={(event) => {
                setPage(0)
                setStatus(event.target.value)
              }}
            >
              <option value="">{tr(t, 'label_all', 'All')}</option>
              {statusOptions.map((item) => (
                <option key={`task-status-${item}`} value={item}>
                  {statusLabel(t, item)}
                </option>
              ))}
            </select>
          </div>

          <div className="table-filter-item">
            <label className="section-subtitle">{tr(t, 'filter_task', 'Task')}</label>
            <select
              className="field-select table-control"
              value={taskType}
              onChange={(event) => {
                setPage(0)
                setTaskType(event.target.value)
              }}
            >
              <option value="">{tr(t, 'label_all', 'All')}</option>
              {taskTypeOptions.map((item) => (
                <option key={`task-type-${item}`} value={item}>
                  {taskTypeLabel(t, item)}
                </option>
              ))}
            </select>
          </div>

          <div className="table-filter-item task-account-filter-item">
            <label className="section-subtitle">{tr(t, 'filter_account', 'Account')}</label>
            <input
              className="field-input table-control"
              list="task-account-options"
              value={accountKeyword}
              onChange={(event) => {
                setPage(0)
                setAccountKeyword(event.target.value)
              }}
              placeholder={tr(t, 'filter_account_id_placeholder', 'Account ID / nickname / friend id')}
            />
            <datalist id="task-account-options">
              {accountOptions.map((item) => {
                const id = toText(item.id, t)
                const displayName = toText(item.display_name || item.nickname, t)
                const friendId = toText(item.friend_id, t)
                const optionLabel = `${id} ${displayName} (${friendId})`
                return <option key={id} value={optionLabel} />
              })}
            </datalist>
          </div>
        </div>

        <div className="table-toolbar-zone table-toolbar-zone--right">
          <Button size="sm" type="button" variant="outline" onClick={() => setPage(0)}>
            {tr(t, 'label_search', 'Search')}
          </Button>
          <Button
            size="sm"
            type="button"
            onClick={() => {
              const warning = tr(
                t,
                'desc_reset_completed_warning',
                'This action will reset completed tasks to pending based on current filters.'
              )
              const ignoreHint = tr(
                t,
                'desc_reset_completed_ignore_init',
                'Init account tasks are always ignored.'
              )
              if (confirm(`${warning}\n${ignoreHint}`)) {
                resetMutation.mutate()
              }
            }}
          >
            {tr(t, 'btn_reset_completed', 'Reset Completed')}
          </Button>
        </div>
      </div>

      <ListQueryControls
        sortBy={sortBy}
        sortOrder={sortOrder}
        pageSize={pageSize}
        sortOptions={[
          { value: 'dispatch_priority', labelKey: 'col_dispatch_priority', fallback: 'Dispatch Priority' },
          { value: 'last_completed_at', labelKey: 'col_last_completed', fallback: 'Last Completed' },
          { value: 'last_duration_seconds', labelKey: 'col_last_duration', fallback: 'Last Duration' },
          { value: 'next_run_at', labelKey: 'col_next_run', fallback: 'Next Run' }
        ]}
        onSortByChange={(value) => {
          setPage(0)
          setSortBy(value)
          if (value === 'dispatch_priority') {
            setSortOrder('asc')
          }
        }}
        onSortOrderChange={(value) => {
          setPage(0)
          setSortOrder(value)
        }}
        onPageSizeChange={(value) => {
          setPage(0)
          setPageSize(value)
        }}
        t={t}
        disableSortOrder={sortBy === 'dispatch_priority'}
      />
      <InlineNotice notice={notice} />

      <DataGrid
        rows={rows}
        columns={[
          { key: 'id', label: tr(t, 'col_id', 'ID') },
          { key: 'account_id', label: tr(t, 'col_account', 'Account') },
          { key: 'task_type', label: tr(t, 'col_task', 'Task'), render: (row) => taskTypeLabel(t, row.task_type) },
          { key: 'status', label: tr(t, 'col_status', 'Status'), render: (row) => statusLabel(t, row.status) },
          {
            key: 'dispatch_rank',
            label: tr(t, 'col_dispatch_priority', 'Dispatch Priority'),
            render: (row) => {
              const rank = Number(row.dispatch_rank ?? 0)
              const total = Number(row.dispatch_rank_total ?? 0)
              if (rank <= 0 || total <= 0) {
                return '-'
              }
              return `${rank}/${total}`
            }
          },
          {
            key: 'last_completed_at_iso',
            label: tr(t, 'col_last_completed', 'Last Completed'),
            sortKey: 'last_completed_at',
            render: (row) => formatTime(row.last_completed_at_iso)
          },
          {
            key: 'last_duration_seconds',
            label: tr(t, 'col_last_duration', 'Last Duration'),
            sortKey: 'last_duration_seconds',
            render: (row) => {
              const duration = Number(row.last_duration_seconds ?? 0)
              if (!Number.isFinite(duration) || duration <= 0) {
                return '-'
              }
              return `${duration.toFixed(1)}s`
            }
          },
          { key: 'reset_type', label: tr(t, 'col_reset_type', 'Reset Type') },
          {
            key: 'next_run_at_iso',
            label: tr(t, 'col_next_run', 'Next Run'),
            sortKey: 'next_run_at',
            render: (row) => formatTime(row.next_run_at_iso)
          },
          { key: 'plan_name', label: tr(t, 'col_plan', 'Plan') },
          { key: 'plan_priority', label: tr(t, 'label_priority', 'Priority') },
          {
            key: 'target_pack_label',
            label: tr(t, 'col_target_pack', 'Target Pack'),
            render: (row) => {
              const value = toText(row.target_pack_label, t)
              if (value === '-') {
                return value
              }
              return Boolean(row.target_pack_auto) ? `${value} (${tr(t, 'label_auto', 'Auto')})` : value
            }
          },
          { key: 'error_message', label: tr(t, 'col_error', 'Error') }
        ]}
        t={t}
        sortBy={sortBy}
        sortOrder={sortOrder}
        onSortChange={handleHeaderSort}
      />

      <Pager
        page={Number(query.data?.page ?? 0)}
        hasPrev={Boolean(query.data?.has_prev)}
        hasNext={Boolean(query.data?.has_next)}
        onPrev={() => setPage((prev) => Math.max(prev - 1, 0))}
        onNext={() => setPage((prev) => prev + 1)}
        t={t}
      />
    </section>
  )
}

function MetadataSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const [uiStep, setUiStep] = useState<1 | 2 | 3>(1)
  const [selectedNodeType, setSelectedNodeType] = usePersistedState<string>(managementStateKey('metadata', 'selected_node_type'), 'root')
  const [selectedNodeId, setSelectedNodeId] = usePersistedState<string>(managementStateKey('metadata', 'selected_node_id'), 'all')
  const [selectedSetCode, setSelectedSetCode] = usePersistedState<string>(managementStateKey('metadata', 'selected_set_code'), '')
  const [selectedPackName, setSelectedPackName] = usePersistedState<string>(managementStateKey('metadata', 'selected_pack_name'), '')
  const [currentAction, setCurrentAction] = usePersistedState<string>(managementStateKey('metadata', 'current_action'), 'update_new_series')
  const [snapshotId, setSnapshotId] = useState('')
  const [forceRefresh, setForceRefresh] = usePersistedState<boolean>(managementStateKey('metadata', 'force_refresh'), false)
  const [previewResult, setPreviewResult] = useState<Record<string, unknown> | null>(null)
  const [executeResult, setExecuteResult] = useState<Record<string, unknown> | null>(null)
  const [checkResult, setCheckResult] = useState<Record<string, unknown> | null>(null)
  const [notice, setNotice] = useState<InlineNoticeState | null>(null)

  const queryString = useMemo(
    () =>
      buildQuery({
        lang,
        ui_step: uiStep,
        selected_node_type: selectedNodeType,
        selected_node_id: selectedNodeId,
        selected_set_code: selectedSetCode || undefined,
        selected_pack_name: selectedPackName || undefined,
        current_action: currentAction,
        snapshot_id: snapshotId || undefined
      }),
    [currentAction, lang, selectedNodeId, selectedNodeType, selectedPackName, selectedSetCode, snapshotId, uiStep]
  )

  const query = useQuery({
    queryKey: ['management-metadata', queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/metadata?${queryString}`)
  })

  const previewMutation = useMutation({
    mutationFn: (action: string) =>
      requestJson<Record<string, unknown>>('/api/react/management/metadata/preview', {
        method: 'POST',
        body: {
          action,
          node_type: selectedNodeType,
          node_id: selectedNodeId,
          force_refresh: forceRefresh
        }
      }),
    onSuccess: (result, action) => {
      const nextSnapshotId = typeof result.snapshot_id === 'string' ? result.snapshot_id : ''
      setCurrentAction(action)
      setPreviewResult(result)
      setExecuteResult(null)
      setSnapshotId(nextSnapshotId)
      setUiStep(2)
    }
  })

  const executeMutation = useMutation({
    mutationFn: () =>
      requestJson<Record<string, unknown>>('/api/react/management/metadata/execute', {
        method: 'POST',
        body: {
          snapshot_id: snapshotId
        }
      }),
    onSuccess: (result) => {
      setExecuteResult(result)
      setNotice({
        level: 'success',
        text: `${tr(t, 'label_success_records', 'Done')}: ${toText(result.status ?? 'ok', t)}`
      })
    }
  })

  const checkMutation = useMutation({
    mutationFn: () => requestJson<Record<string, unknown>>('/api/react/management/metadata/check', { method: 'POST', body: {} }),
    onSuccess: (result) => setCheckResult(result)
  })

  useEffect(() => {
    const nextNodeType = query.data?.selected_node_type
    if (typeof nextNodeType === 'string' && nextNodeType && nextNodeType !== selectedNodeType) {
      setSelectedNodeType(nextNodeType)
    }
    const nextNodeId = query.data?.selected_node_id
    if (typeof nextNodeId === 'string' && nextNodeId && nextNodeId !== selectedNodeId) {
      setSelectedNodeId(nextNodeId)
    }
    const nextSetCode = query.data?.selected_set_code
    if (typeof nextSetCode === 'string' && nextSetCode !== selectedSetCode) {
      setSelectedSetCode(nextSetCode)
    }
    const nextPackName = query.data?.selected_pack_name
    if (typeof nextPackName === 'string' && nextPackName !== selectedPackName) {
      setSelectedPackName(nextPackName)
    }
    const nextAction = query.data?.current_action
    if (typeof nextAction === 'string' && nextAction && nextAction !== currentAction) {
      setCurrentAction(nextAction)
    }
    const nextSnapshotId = query.data?.snapshot_id
    if (
      typeof nextSnapshotId === 'string' &&
      nextSnapshotId &&
      nextSnapshotId !== snapshotId &&
      previewResult === null
    ) {
      setSnapshotId(nextSnapshotId)
    }
  }, [currentAction, previewResult, query.data, selectedNodeId, selectedNodeType, selectedPackName, selectedSetCode, snapshotId])

  const sets = useMemo(
    () => (((query.data?.sets as unknown[]) ?? []) as Record<string, unknown>[]),
    [query.data?.sets]
  )
  const packsBySet = (query.data?.packs_by_set as Record<string, unknown> | undefined) ?? {}
  const packsForSet = (((packsBySet[selectedSetCode] as unknown[]) ?? []) as Record<string, unknown>[])
  const packCards = (((query.data?.selected_pack_cards as unknown[]) ?? []) as Record<string, unknown>[])
  const selectedCardKey = typeof query.data?.selected_card_key === 'string' ? query.data.selected_card_key : ''
  const actionCards = useMemo(
    () => (((query.data?.available_action_cards as unknown[]) ?? []) as Record<string, unknown>[]),
    [query.data?.available_action_cards]
  )
  const effectivePreview = (previewResult ?? ((query.data?.sync_preview as Record<string, unknown> | undefined) ?? null))
  const previewSummary = (effectivePreview?.summary as Record<string, unknown> | undefined) ?? {}
  const previewPayload = (effectivePreview?.payload as Record<string, unknown> | undefined) ?? {}
  const previewItems = ((effectivePreview?.items as unknown[]) ?? []) as Record<string, unknown>[]
  const previewSnapshotId = (typeof effectivePreview?.snapshot_id === 'string' ? effectivePreview.snapshot_id : '') || snapshotId
  const previewSyncKind =
    typeof previewPayload.sync_kind === 'string'
      ? previewPayload.sync_kind
      : currentAction === 'update_new_series'
        ? 'update_new_series'
        : currentAction.includes('chinese')
          ? 'update_chinese'
          : 'update_data'

  function resetToStep1() {
    setUiStep(1)
    setSnapshotId('')
    setPreviewResult(null)
    setExecuteResult(null)
  }

  function selectRoot() {
    setUiStep(1)
    setSelectedNodeType('root')
    setSelectedNodeId('all')
    setSelectedSetCode('')
    setSelectedPackName('')
    setSnapshotId('')
    setPreviewResult(null)
    setExecuteResult(null)
  }

  function selectSet(setCode: string) {
    setUiStep(1)
    setSelectedNodeType('set')
    setSelectedNodeId(setCode)
    setSelectedSetCode(setCode)
    setSelectedPackName('')
    setSnapshotId('')
    setPreviewResult(null)
    setExecuteResult(null)
  }

  function selectPack(setCode: string, packName: string) {
    setUiStep(1)
    setSelectedNodeType('pack')
    setSelectedNodeId(packName)
    setSelectedSetCode(setCode)
    setSelectedPackName(packName)
    setSnapshotId('')
    setPreviewResult(null)
    setExecuteResult(null)
  }

  function selectCard(cardKey: string) {
    setUiStep(1)
    setSelectedNodeType('card')
    setSelectedNodeId(cardKey)
    setSnapshotId('')
    setPreviewResult(null)
    setExecuteResult(null)
  }

  function toNumber(value: unknown): number {
    const parsed = Number(value ?? 0)
    return Number.isFinite(parsed) ? parsed : 0
  }

  return (
    <section className="surface-card section-stack">
      <div className="pagination-row">
        <div>
          <div className="section-title">{tr(t, 'metadata_sync_console_title', 'Metadata Sync Console')}</div>
          <div className="text-xs text-muted">{tr(t, 'metadata_sync_console_desc', 'Three steps: select -> preview -> execute')}</div>
        </div>
        <div className="filter-row">
          <Button type="button" size="sm" variant="outline" onClick={() => checkMutation.mutate()} disabled={checkMutation.isPending}>
            {tr(t, 'btn_recheck_sources', 'Check Sources')}
          </Button>
        </div>
      </div>

      <div className="metadata-step-grid">
        <div className={`metadata-step-card ${uiStep === 1 ? 'is-active' : ''}`}>
          <div className="metadata-step-badge">{tr(t, 'metadata_step_badge_1', 'Step 1')}</div>
          <div>{tr(t, 'metadata_step_select_object', 'Select Object')}</div>
        </div>
        <div className={`metadata-step-card ${uiStep === 2 ? 'is-active' : ''}`}>
          <div className="metadata-step-badge">{tr(t, 'metadata_step_badge_2', 'Step 2')}</div>
          <div>{tr(t, 'metadata_step_preview_diff', 'Preview Diff')}</div>
        </div>
        <div className={`metadata-step-card ${uiStep === 3 ? 'is-active' : ''}`}>
          <div className="metadata-step-badge">{tr(t, 'metadata_step_badge_3', 'Step 3')}</div>
          <div>{tr(t, 'metadata_step_execute', 'Confirm Execute')}</div>
        </div>
      </div>

      {checkResult && (
        <details className="surface-card">
          <summary className="section-subtitle">{tr(t, 'metadata_health_panel', 'Source Health')}</summary>
          <pre className="text-xs mono">{JSON.stringify(checkResult, null, 2)}</pre>
        </details>
      )}

      {query.isLoading && <div className="text-sm text-muted">{tr(t, 'label_loading', 'Loading...')}</div>}
      {query.isError && <div className="text-sm text-danger">{(query.error as Error).message}</div>}
      <InlineNotice notice={notice} />

      {uiStep === 1 && (
        <div className="metadata-workspace">
          <div className="metadata-tree-grid">
            <div className="surface-card section-stack">
              <div className="section-subtitle">{tr(t, 'metadata_col_sets', 'Sets')}</div>
              <button type="button" className={`metadata-node-btn ${selectedNodeType === 'root' ? 'is-active' : ''}`} onClick={selectRoot}>
                {tr(t, 'metadata_node_all', 'All')}
              </button>
              <div className="metadata-node-list">
                {sets.map((setRow) => {
                  const code = toText(setRow.code, t)
                  const isActive = selectedNodeType === 'set' && selectedSetCode === code
                  return (
                    <button
                      key={code}
                      type="button"
                      className={`metadata-node-btn ${isActive ? 'is-active' : ''}`}
                      onClick={() => selectSet(code)}
                    >
                      {code} - {toText(setRow.display_name ?? setRow.name, t)}
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="surface-card section-stack">
              <div className="section-subtitle">{tr(t, 'metadata_col_packs', 'Packs')}</div>
              {selectedSetCode ? (
                <div className="metadata-node-list">
                  {packsForSet.map((packRow) => {
                    const packName = toText(packRow.name, t)
                    const isActive = selectedNodeType === 'pack' && selectedPackName === packName
                    return (
                      <button
                        key={packName}
                        type="button"
                        className={`metadata-node-btn ${isActive ? 'is-active' : ''}`}
                        onClick={() => selectPack(selectedSetCode, packName)}
                      >
                        {toText(packRow.display_name ?? packName, t)}
                      </button>
                    )
                  })}
                </div>
              ) : (
                <div className="text-xs text-muted">{tr(t, 'metadata_select_set_first', 'Select set first')}</div>
              )}
            </div>

            <div className="surface-card section-stack">
              <div className="section-subtitle">{tr(t, 'metadata_col_cards', 'Cards')}</div>
              {selectedPackName ? (
                <div className="metadata-node-list">
                  {packCards.map((cardRow) => {
                    const cardKey = toText(cardRow.key, t)
                    const isActive = selectedNodeType === 'card' && selectedCardKey === cardKey
                    return (
                      <button
                        key={cardKey}
                        type="button"
                        className={`metadata-node-btn ${isActive ? 'is-active' : ''}`}
                        onClick={() => selectCard(cardKey)}
                      >
                        {cardKey} {toText(cardRow.display_name ?? cardRow.name, t)}
                      </button>
                    )
                  })}
                </div>
              ) : (
                <div className="text-xs text-muted">{tr(t, 'metadata_select_pack_first', 'Select pack first')}</div>
              )}
            </div>
          </div>

          <div className="surface-card section-stack">
            <div className="section-title">{tr(t, 'metadata_action_panel_title', 'Node Actions')}</div>
            <div className="text-xs">{tr(t, 'metadata_current_node', 'Current Node')}: {selectedNodeType} / <span className="mono">{selectedNodeId}</span></div>
            <label className="filter-row">
              <input
                type="checkbox"
                checked={forceRefresh}
                onChange={(event) => setForceRefresh(event.target.checked)}
              />
              <span className="text-xs">{tr(t, 'btn_refresh', 'Force refresh remote cache')}</span>
            </label>
            {actionCards.map((actionCard, index) => {
              const buttons = ((actionCard.buttons as unknown[]) ?? []) as Record<string, unknown>[]
              return (
                <div key={`action-card-${index}`} className="metadata-action-card">
                  <div className="section-subtitle">{tr(t, toText(actionCard.title_key, t), toText(actionCard.title_fallback, t))}</div>
                  <div className="filter-row">
                    {buttons.map((button, buttonIndex) => {
                      const action = toText(button.action, t)
                      return (
                        <Button
                          key={`${action}-${buttonIndex}`}
                          type="button"
                          size="sm"
                          variant={currentAction === action ? 'default' : 'outline'}
                          disabled={previewMutation.isPending}
                          onClick={() => previewMutation.mutate(action)}
                        >
                          {tr(t, toText(button.label_key, t), toText(button.label_fallback, t))}
                        </Button>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {uiStep === 2 && (
        <div className="surface-card section-stack">
          <div className="section-title">{tr(t, 'metadata_step_preview_diff', 'Preview Diff')}</div>
          <div className="text-xs text-muted">{tr(t, 'metadata_current_node', 'Current Node')}: {selectedNodeType} / {selectedNodeId}</div>
          {effectivePreview && previewSnapshotId ? (
            <>
              <div className="metadata-summary-grid">
                <div className="metadata-summary-card">
                  <div className="section-subtitle">{tr(t, 'metadata_label_snapshot', 'Snapshot')}</div>
                  <div className="mono text-xs">{previewSnapshotId}</div>
                </div>
                <div className="metadata-summary-card">
                  <div className="section-subtitle">{tr(t, 'metadata_label_mode', 'Mode')}</div>
                  <div>{toText(previewPayload.mode, t)}</div>
                </div>
                <div className="metadata-summary-card">
                  <div className="section-subtitle">{tr(t, 'metadata_label_action', 'Action')}</div>
                  <div>
                    {previewSyncKind === 'update_new_series'
                      ? tr(t, 'metadata_action_update_new_series', 'Update New Series')
                      : previewSyncKind === 'update_chinese'
                        ? tr(t, 'metadata_action_update_chinese', 'Update Chinese')
                        : tr(t, 'metadata_action_update_data', 'Update Data')}
                  </div>
                </div>
              </div>

              <div className="metadata-summary-grid">
                {previewSyncKind === 'update_chinese' ? (
                  <>
                    <div className="metadata-summary-card"><div className="section-subtitle">{tr(t, 'metadata_metric_sets_zh', 'Sets ZH')}</div><div>{toNumber(previewSummary.localization_sets)}</div></div>
                    <div className="metadata-summary-card"><div className="section-subtitle">{tr(t, 'metadata_metric_packs_zh', 'Packs ZH')}</div><div>{toNumber(previewSummary.localization_packs)}</div></div>
                    <div className="metadata-summary-card"><div className="section-subtitle">{tr(t, 'metadata_metric_cards_zh', 'Cards ZH')}</div><div>{toNumber(previewSummary.localization_cards)}</div></div>
                  </>
                ) : previewSyncKind === 'update_new_series' ? (
                  <>
                    <div className="metadata-summary-card"><div className="section-subtitle">{tr(t, 'metadata_metric_new_sets', 'New Sets')}</div><div>{toNumber(previewSummary.upsert_sets)}</div></div>
                    <div className="metadata-summary-card"><div className="section-subtitle">{tr(t, 'metadata_label_source', 'Source')}</div><div>{toText(previewPayload.source, t)}</div></div>
                  </>
                ) : (
                  <>
                    <div className="metadata-summary-card"><div className="section-subtitle">{tr(t, 'metadata_col_sets', 'Sets')}</div><div>{toNumber(previewSummary.upsert_sets)}</div></div>
                    <div className="metadata-summary-card"><div className="section-subtitle">{tr(t, 'metadata_col_packs', 'Packs')}</div><div>{toNumber(previewSummary.upsert_packs)}</div></div>
                    <div className="metadata-summary-card"><div className="section-subtitle">{tr(t, 'metadata_col_cards', 'Cards')}</div><div>{toNumber(previewSummary.card_updates)}</div></div>
                    <div className="metadata-summary-card"><div className="section-subtitle">{tr(t, 'metadata_metric_links_add', 'Links +')}</div><div>{toNumber(previewSummary.card_pack_links_to_add)}</div></div>
                    <div className="metadata-summary-card"><div className="section-subtitle">{tr(t, 'metadata_metric_links_remove', 'Links -')}</div><div>{toNumber(previewSummary.card_pack_links_to_remove)}</div></div>
                    <div className="metadata-summary-card"><div className="section-subtitle">{tr(t, 'metadata_label_source', 'Source')}</div><div>{toText(previewPayload.source, t)}</div></div>
                  </>
                )}
              </div>

              {previewItems.length > 0 && (
                <div className="surface-card section-stack">
                  <div className="section-subtitle">{tr(t, 'metadata_preview_items_title', 'Preview Items')}</div>
                  <div className="metadata-node-list">
                    {previewItems.map((item, index) => (
                      <div key={`preview-item-${index}`} className="metadata-preview-item">
                        <div className="mono text-xs">[{toText(item.type, t)}] {toText(item.id, t)} · {toText(item.name, t)} · {toText(item.action, t)}</div>
                        {toText(item.changes, t) !== '-' && <div className="text-xs text-muted">{toText(item.changes, t)}</div>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <details className="surface-card">
                <summary className="section-subtitle">{tr(t, 'metadata_preview_detail', 'Preview JSON')}</summary>
                <pre className="text-xs mono">{JSON.stringify(effectivePreview, null, 2)}</pre>
              </details>
            </>
          ) : (
            <div className="text-xs text-muted">{tr(t, 'metadata_preview_placeholder', 'Generate preview first')}</div>
          )}

          <div className="filter-row">
            <Button type="button" size="sm" variant="outline" onClick={() => setUiStep(1)}>
              {tr(t, 'metadata_back_select', 'Back to Selection')}
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={!previewSnapshotId}
              onClick={() => {
                setSnapshotId(previewSnapshotId)
                setUiStep(3)
              }}
            >
              {tr(t, 'metadata_next_execute', 'Next: Confirm Execute')}
            </Button>
          </div>
        </div>
      )}

      {uiStep === 3 && (
        <div className="surface-card section-stack">
          <div className="section-title">{tr(t, 'metadata_step_execute', 'Confirm Execute')}</div>
          <div className="text-xs text-muted">{tr(t, 'metadata_current_node', 'Current Node')}: {selectedNodeType} / {selectedNodeId}</div>
          <div className="metadata-summary-card">
            <div className="section-subtitle">{tr(t, 'metadata_label_snapshot_id', 'Snapshot ID')}</div>
            <div className="mono text-xs">{snapshotId || '-'}</div>
          </div>
          {executeResult && (
            <details className="surface-card" open>
              <summary className="section-subtitle">{tr(t, 'metadata_label_result', 'Result')}</summary>
              <pre className="text-xs mono">{JSON.stringify(executeResult, null, 2)}</pre>
            </details>
          )}
          <div className="filter-row">
            <Button type="button" size="sm" variant="outline" onClick={() => setUiStep(2)}>
              {tr(t, 'btn_prev_page', 'Previous')}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={resetToStep1}
            >
              {tr(t, 'metadata_back_select', 'Back to Selection')}
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={!snapshotId || executeMutation.isPending}
              onClick={() => executeMutation.mutate()}
            >
              {tr(t, 'metadata_confirm_execute', 'Execute')}
            </Button>
          </div>
        </div>
      )}

      {previewMutation.isPending && (
        <div className="text-xs text-muted">{tr(t, 'metadata_preview_loading', 'Generating preview...')}</div>
      )}
      {previewMutation.isError && (
        <div className="text-xs text-danger">{(previewMutation.error as Error).message}</div>
      )}
      {executeMutation.isError && (
        <div className="text-xs text-danger">{(executeMutation.error as Error).message}</div>
      )}
      {checkMutation.isError && (
        <div className="text-xs text-danger">{(checkMutation.error as Error).message}</div>
      )}
      {!query.isLoading && !query.isError && actionCards.length === 0 && (
        <div className="text-xs text-muted">{tr(t, 'label_no_data', 'No data')}</div>
      )}
    </section>
  )
}

function DailyGiftSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const [page, setPage] = usePersistedState<number>(managementStateKey('daily-gift', 'page'), 0)
  const [pairPage, setPairPage] = usePersistedState<number>(managementStateKey('daily-gift', 'pair_page'), 0)
  const [pageSize, setPageSize] = usePersistedState<number>(managementStateKey('daily-gift', 'page_size'), 10)
  const [pairPageSize, setPairPageSize] = usePersistedState<number>(managementStateKey('daily-gift', 'pair_page_size'), 10)
  const [sortBy, setSortBy] = usePersistedState<string>(managementStateKey('daily-gift', 'sort_by'), 'updated_at')
  const [sortOrder, setSortOrder] = usePersistedState<'asc' | 'desc'>(managementStateKey('daily-gift', 'sort_order'), 'desc')
  const [date, setDate] = usePersistedState<string>(managementStateKey('daily-gift', 'date'), '')
  const [accountId, setAccountId] = usePersistedState<string>(managementStateKey('daily-gift', 'account_id'), '')

  const queryString = useMemo(
    () =>
      buildQuery({
        lang,
        page,
        page_size: pageSize,
        pair_page: pairPage,
        pair_page_size: pairPageSize,
        sort_by: sortBy,
        sort_order: sortOrder,
        biz_date_local: date || undefined,
        account_id: accountId || undefined
      }),
    [accountId, date, lang, page, pageSize, pairPage, pairPageSize, sortBy, sortOrder]
  )
  const query = useQuery({
    queryKey: ['management-daily-gift', queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/daily-gift?${queryString}`)
  })

  const records = ((query.data?.records as unknown[]) ?? []) as Record<string, unknown>[]
  const pairs = ((query.data?.pair_send_status_rows as unknown[]) ?? []) as Record<string, unknown>[]
  const stats = (query.data?.stats as Record<string, unknown> | undefined) ?? {}
  const recentBizDates = (((query.data?.recent_biz_dates as unknown[]) ?? []) as string[])
  const accounts = (((query.data?.accounts as unknown[]) ?? []) as Record<string, unknown>[])
  const accountNameMap = (query.data?.account_name_map as Record<string, string> | undefined) ?? {}
  const selectedAccountId = toText(query.data?.selected_account_id, t) === '-' ? '' : toText(query.data?.selected_account_id, t)

  useEffect(() => {
    const currentDate = toText(query.data?.selected_biz_date_local, t)
    if (currentDate !== '-' && currentDate !== date) {
      setDate(currentDate)
    }
    if (selectedAccountId !== accountId) {
      setAccountId(selectedAccountId)
    }
  }, [accountId, date, query.data, selectedAccountId, t])

  function accountDisplay(account: Record<string, unknown>): string {
    const id = toText(account.id, t)
    const name = toText(account.display_name, t)
    const friendId = toText(account.friend_id, t)
    return `${id} ${name} (${friendId})`
  }

  return (
    <section className="surface-card section-stack">
      <div className="pagination-row">
        <div className="section-title">{tr(t, 'menu_daily_gift', 'Daily Gift')}</div>
        <div className="filter-row">
          <input className="field-input" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          <select
            className="field-select"
            value={accountId}
            onChange={(event) => {
              setAccountId(event.target.value)
              setPage(0)
              setPairPage(0)
            }}
          >
            <option value="">{tr(t, 'label_all_accounts', 'All Accounts')}</option>
            {accounts.map((account) => (
              <option key={`daily-account-${toText(account.id, t)}`} value={toText(account.id, t)}>
                {accountDisplay(account)}
              </option>
            ))}
          </select>
          <Button type="button" size="sm" variant="outline" onClick={() => { setPage(0); setPairPage(0) }}>{tr(t, 'label_search', 'Search')}</Button>
        </div>
      </div>

      {recentBizDates.length > 0 && (
        <div className="filter-row">
          {recentBizDates.map((item) => (
            <Button
              key={`daily-date-${item}`}
              type="button"
              size="sm"
              variant={date === item ? 'default' : 'outline'}
              onClick={() => {
                setDate(item)
                setPage(0)
                setPairPage(0)
              }}
            >
              {item}
            </Button>
          ))}
        </div>
      )}

      <div className="daily-gift-stats-grid">
        <div className="surface-card daily-gift-stat-card">
          <div className="section-subtitle">{tr(t, 'label_total_records', 'Total')}</div>
          <div className="daily-gift-stat-value">{toText(stats.total, t)}</div>
        </div>
        <div className="surface-card daily-gift-stat-card status-success">
          <div className="section-subtitle">{tr(t, 'label_success_records', 'Success')}</div>
          <div className="daily-gift-stat-value">{toText(stats.success, t)}</div>
        </div>
        <div className="surface-card daily-gift-stat-card status-failed">
          <div className="section-subtitle">{tr(t, 'label_failed_records', 'Failed')}</div>
          <div className="daily-gift-stat-value">{toText(stats.failed, t)}</div>
        </div>
        <div className="surface-card daily-gift-stat-card status-waiting">
          <div className="section-subtitle">{tr(t, 'label_waiting_records', 'Waiting')}</div>
          <div className="daily-gift-stat-value">{toText(stats.waiting, t)}</div>
        </div>
      </div>

      <ListQueryControls
        sortBy={sortBy}
        sortOrder={sortOrder}
        pageSize={pageSize}
        sortOptions={[
          { value: 'updated_at', labelKey: 'col_updated_at', fallback: 'Updated At' },
          { value: 'account_id', labelKey: 'col_account_id', fallback: 'Account ID' },
          { value: 'status', labelKey: 'col_status', fallback: 'Status' }
        ]}
        onSortByChange={(value) => {
          setPage(0)
          setSortBy(value)
        }}
        onSortOrderChange={(value) => {
          setPage(0)
          setSortOrder(value)
        }}
        onPageSizeChange={(value) => {
          setPage(0)
          setPageSize(value)
        }}
        t={t}
      />
      <div className="filter-row">
        <span className="text-xs text-muted">{tr(t, 'label_pair_page_size', 'Pair Page Size')}</span>
        <select
          className="field-select"
          value={String(pairPageSize)}
          onChange={(event) => {
            setPairPage(0)
            setPairPageSize(Number(event.target.value))
          }}
        >
          {[10, 20, 50, 100].map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </div>

      <div className="section-subtitle">{tr(t, 'section_daily_gift_records', 'Gift Records')}</div>
      <div className="table-wrap">
        <table className="grid-table">
          <thead>
            <tr>
              <th>{tr(t, 'col_id', 'ID')}</th>
              <th>{tr(t, 'col_account', 'Account')}</th>
              <th>{tr(t, 'col_friend_id', 'Friend ID')}</th>
              <th>{tr(t, 'col_card', 'Card')}</th>
              <th>{tr(t, 'col_status', 'Status')}</th>
              <th>{tr(t, 'col_count_change', 'Count Change')}</th>
              <th>{tr(t, 'time_label', 'Time')}</th>
            </tr>
          </thead>
          <tbody>
            {records.length === 0 && (
              <tr>
                <td colSpan={7} className="text-center text-muted">{tr(t, 'empty_daily_gift_records', 'No gift records for this date')}</td>
              </tr>
            )}
            {records.map((row) => {
              const accountIdRow = Number(row.account_id ?? 0)
              const targetAccountId = Number(row.target_account_id ?? 0)
              const beforeCount = Number(row.before_count ?? NaN)
              const afterCount = Number(row.after_count ?? NaN)
              return (
                <tr key={`daily-record-${toText(row.id, t)}`}>
                  <td className="mono">#{toText(row.id, t)}</td>
                  <td>
                    <div>{toText(row.account_name, t)}</div>
                    <div className="text-xs text-muted">#{accountIdRow}</div>
                  </td>
                  <td>
                    <div className="mono">{toText(row.target_friend_id, t)}</div>
                    {Number.isFinite(targetAccountId) && targetAccountId > 0 && (
                      <div className="text-xs text-muted">#{targetAccountId} {accountNameMap[String(targetAccountId)] ?? toText(row.target_name, t)}</div>
                    )}
                  </td>
                  <td className="mono">{toText(row.card_label, t)}</td>
                  <td>{giftStatusLabel(t, row.status)}</td>
                  <td className="mono">
                    {Number.isFinite(beforeCount) ? String(beforeCount) : '-'}
                    {' -> '}
                    {Number.isFinite(afterCount) ? String(afterCount) : '-'}
                  </td>
                  <td className="mono">{formatTime(row.updated_at)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <Pager
        page={Number(query.data?.page ?? 0)}
        hasPrev={Boolean(query.data?.has_prev)}
        hasNext={Boolean(query.data?.has_next)}
        onPrev={() => setPage((prev) => Math.max(prev - 1, 0))}
        onNext={() => setPage((prev) => prev + 1)}
        t={t}
      />

      <div className="section-subtitle">{tr(t, 'section_daily_gift_pair_progress', 'Pair Send Progress')}</div>
      <div className="table-wrap">
        <table className="grid-table">
          <thead>
            <tr>
              <th>{tr(t, 'col_pair', 'Pair')}</th>
              <th>{tr(t, 'col_direction_left_to_right', 'A to B')}</th>
              <th>{tr(t, 'col_direction_right_to_left', 'B to A')}</th>
              <th>{tr(t, 'col_progress', 'Progress')}</th>
            </tr>
          </thead>
          <tbody>
            {pairs.length === 0 && (
              <tr>
                <td colSpan={4} className="text-center text-muted">{tr(t, 'empty_daily_gift_pair_progress', 'No pair send status data')}</td>
              </tr>
            )}
            {pairs.map((row, index) => (
              <tr key={`daily-pair-${index}`}>
                <td>
                  <div>{toText(row.left_name, t)} ↔ {toText(row.right_name, t)}</div>
                  <div className="text-xs text-muted">
                    #{toText(row.left_account_id, t)} ↔ #{toText(row.right_account_id, t)}
                  </div>
                </td>
                <td>{giftStatusLabel(t, row.left_to_right_status)}</td>
                <td>{giftStatusLabel(t, row.right_to_left_status)}</td>
                <td>{pairProgressLabel(t, row.pair_progress)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager
        page={Number(query.data?.pair_page ?? 0)}
        hasPrev={Boolean(query.data?.pair_has_prev)}
        hasNext={Boolean(query.data?.pair_has_next)}
        onPrev={() => setPairPage((prev) => Math.max(prev - 1, 0))}
        onNext={() => setPairPage((prev) => prev + 1)}
        t={t}
      />
    </section>
  )
}
function FriendshipsSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const queryClient = useQueryClient()
  const [page, setPage] = usePersistedState<number>(managementStateKey('friendships', 'page'), 0)
  const [pageSize, setPageSize] = usePersistedState<number>(managementStateKey('friendships', 'page_size'), 10)
  const [sortBy, setSortBy] = usePersistedState<string>(managementStateKey('friendships', 'sort_by'), 'created_at')
  const [sortOrder, setSortOrder] = usePersistedState<'asc' | 'desc'>(managementStateKey('friendships', 'sort_order'), 'desc')
  const [q, setQ] = usePersistedState<string>(managementStateKey('friendships', 'q'), '')
  const [accountId, setAccountId] = usePersistedState<string>(managementStateKey('friendships', 'account_id'), '')
  const [fromAccountId, setFromAccountId] = usePersistedState<string>(managementStateKey('friendships', 'from_account_id'), '')
  const [targetAccountId, setTargetAccountId] = useState('')
  const [friendIdInput, setFriendIdInput] = useState('')
  const [notice, setNotice] = useState<InlineNoticeState | null>(null)

  const queryString = useMemo(
    () =>
      buildQuery({
        lang,
        page,
        page_size: pageSize,
        sort_by: sortBy,
        sort_order: sortOrder,
        q,
        account_id: accountId || undefined,
        from_account_id: fromAccountId || undefined
      }),
    [accountId, fromAccountId, lang, page, pageSize, q, sortBy, sortOrder]
  )
  const query = useQuery({
    queryKey: ['management-friendships', queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/friendships?${queryString}`)
  })

  const addMutation = useMutation({
    mutationFn: () =>
      requestJson<{ ok: boolean; message: string }>('/api/react/management/friendships/add', {
        method: 'POST',
        body: {
          from_account_id: Number(fromAccountId || 0),
          to_account_id: Number(targetAccountId || 0),
          to_friend_id: friendIdInput
        }
      }),
    onSuccess: (result) => {
      setNotice({ level: result.ok ? 'success' : 'error', text: result.message })
      queryClient.invalidateQueries({ queryKey: ['management-friendships'] })
    }
  })

  const deleteMutation = useMutation({
    mutationFn: (payload?: { fromAccountId: number; toAccountId: number; friendId: string }) =>
      requestJson<{ ok: boolean; message: string }>('/api/react/management/friendships/delete', {
        method: 'POST',
        body: {
          from_account_id: payload?.fromAccountId ?? Number(fromAccountId || 0),
          to_account_id: payload?.toAccountId ?? Number(targetAccountId || 0),
          friend_id: payload?.friendId ?? friendIdInput
        }
      }),
    onSuccess: (result) => {
      setNotice({ level: result.ok ? 'success' : 'error', text: result.message })
      queryClient.invalidateQueries({ queryKey: ['management-friendships'] })
    }
  })

  const cancelMutation = useMutation({
    mutationFn: (requestId: number) => requestJson<{ ok: boolean; message: string }>(`/api/react/management/friendships/${requestId}/cancel`, { method: 'POST', body: {} }),
    onSuccess: (result) => {
      setNotice({ level: result.ok ? 'success' : 'error', text: result.message })
      queryClient.invalidateQueries({ queryKey: ['management-friendships'] })
    }
  })

  const requests = ((query.data?.requests as unknown[]) ?? []) as Record<string, unknown>[]
  const friendships = ((query.data?.friendships as unknown[]) ?? []) as Record<string, unknown>[]
  const accounts = (((query.data?.accounts as unknown[]) ?? []) as Record<string, unknown>[])
  const accountNameMap = (query.data?.account_name_map as Record<string, string> | undefined) ?? {}

  function accountDisplay(account: Record<string, unknown>): string {
    const id = toText(account.id, t)
    const name = toText(account.display_name, t)
    const friendId = toText(account.friend_id, t)
    return `${id} ${name} (${friendId})`
  }

  return (
    <section className="surface-card section-stack">
      <div className="section-title">{tr(t, 'menu_friendships', 'Friendships')}</div>
      <div className="form-grid">
        <input className="field-input" value={q} onChange={(event) => setQ(event.target.value)} placeholder={tr(t, 'label_search', 'Search')} />
        <select className="field-select" value={accountId} onChange={(event) => setAccountId(event.target.value)}>
          <option value="">{tr(t, 'label_all_accounts', 'All Accounts')}</option>
          {accounts.map((item) => (
            <option key={`friendship-filter-account-${toText(item.id, t)}`} value={toText(item.id, t)}>{accountDisplay(item)}</option>
          ))}
        </select>
        <select className="field-select" value={fromAccountId} onChange={(event) => setFromAccountId(event.target.value)}>
          <option value="">{tr(t, 'label_from_account', 'From Account')}</option>
          {accounts.map((item) => (
            <option key={`friendship-filter-from-${toText(item.id, t)}`} value={toText(item.id, t)}>{accountDisplay(item)}</option>
          ))}
        </select>
        <select className="field-select" value={targetAccountId} onChange={(event) => setTargetAccountId(event.target.value)}>
          <option value="">{tr(t, 'label_target_account_optional', 'Target Account (optional)')}</option>
          {accounts.map((item) => (
            <option key={`friendship-filter-target-${toText(item.id, t)}`} value={toText(item.id, t)}>{accountDisplay(item)}</option>
          ))}
        </select>
        <input className="field-input" value={friendIdInput} onChange={(event) => setFriendIdInput(event.target.value)} placeholder={tr(t, 'placeholder_friend_id', 'Friend ID (optional)')} />
      </div>
      <div className="filter-row">
        <Button type="button" size="sm" variant="outline" onClick={() => setPage(0)}>{tr(t, 'label_search', 'Search')}</Button>
        <Button type="button" size="sm" onClick={() => addMutation.mutate()}>{tr(t, 'btn_create_add_request', 'Create Add Request')}</Button>
        <Button type="button" size="sm" variant="outline" onClick={() => deleteMutation.mutate(undefined)}>{tr(t, 'btn_create_delete_request', 'Create Delete Request')}</Button>
      </div>
      <InlineNotice notice={notice} />
      <ListQueryControls
        sortBy={sortBy}
        sortOrder={sortOrder}
        pageSize={pageSize}
        sortOptions={[
          { value: 'created_at', labelKey: 'label_created_time', fallback: 'Created At' },
          { value: 'updated_at', labelKey: 'col_updated_at', fallback: 'Updated At' },
          { value: 'from_account_id', labelKey: 'label_from_account', fallback: 'From Account' },
          { value: 'to_friend_id', labelKey: 'col_friend_id', fallback: 'Friend ID' },
          { value: 'status', labelKey: 'col_status', fallback: 'Status' },
          { value: 'account_id', labelKey: 'col_account_id', fallback: 'Account ID' },
          { value: 'friend_id', labelKey: 'col_friend_id', fallback: 'Friend ID' }
        ]}
        onSortByChange={(value) => {
          setPage(0)
          setSortBy(value)
        }}
        onSortOrderChange={(value) => {
          setPage(0)
          setSortOrder(value)
        }}
        onPageSizeChange={(value) => {
          setPage(0)
          setPageSize(value)
        }}
        t={t}
      />

      <div className="section-subtitle">{tr(t, 'section_friend_requests', 'Requests')}</div>
      <div className="table-wrap">
        <table className="grid-table">
          <thead>
            <tr>
              <th>{tr(t, 'col_id', 'ID')}</th>
              <th>{tr(t, 'label_from_account', 'From Account')}</th>
              <th>{tr(t, 'col_friend_id', 'Friend ID')}</th>
              <th>{tr(t, 'col_type', 'Type')}</th>
              <th>{tr(t, 'col_status', 'Status')}</th>
              <th>{tr(t, 'label_created_time', 'Created')}</th>
              <th>{tr(t, 'col_actions', 'Actions')}</th>
            </tr>
          </thead>
          <tbody>
            {requests.length === 0 && (
              <tr>
                <td colSpan={7} className="text-center text-muted">{tr(t, 'empty_friend_requests', 'No friend requests')}</td>
              </tr>
            )}
            {requests.map((row) => {
              const fromId = toText(row.from_account_id, t)
              const toId = toText(row.to_account_id, t)
              const canCancel = ['sending', 'sended', 'deleting'].includes(String(row.status ?? ''))
              return (
                <tr key={`friend-request-${toText(row.id, t)}`}>
                  <td className="mono">#{toText(row.id, t)}</td>
                  <td>
                    <div>{accountNameMap[fromId] ?? fromId}</div>
                    <div className="text-xs text-muted">#{fromId}</div>
                  </td>
                  <td>
                    <div className="mono">{toText(row.to_friend_id, t)}</div>
                    {toId !== '-' && <div className="text-xs text-muted">#{toId}</div>}
                  </td>
                  <td>{requestTypeLabel(t, row.request_type)}</td>
                  <td>{requestStatusLabel(t, row.status)}</td>
                  <td className="mono">{formatTime(row.updated_at)}</td>
                  <td>
                    {canCancel ? (
                      <Button type="button" size="sm" variant="outline" onClick={() => cancelMutation.mutate(Number(row.id))}>
                        {tr(t, 'btn_remove_request', 'Delete Request')}
                      </Button>
                    ) : (
                      <span className="text-muted">-</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="section-subtitle">{tr(t, 'section_friendships', 'Friendships')}</div>
      <div className="table-wrap">
        <table className="grid-table">
          <thead>
            <tr>
              <th>{tr(t, 'col_id', 'ID')}</th>
              <th>{tr(t, 'col_account_id', 'Account ID')}</th>
              <th>{tr(t, 'col_friend_id', 'Friend ID')}</th>
              <th>{tr(t, 'label_created_time', 'Created')}</th>
              <th>{tr(t, 'col_actions', 'Actions')}</th>
            </tr>
          </thead>
          <tbody>
            {friendships.length === 0 && (
              <tr>
                <td colSpan={5} className="text-center text-muted">{tr(t, 'empty_friendships', 'No friendships')}</td>
              </tr>
            )}
            {friendships.map((row) => {
              const rowAccountId = Number(row.account_id ?? 0)
              const rowFriendAccountId = Number(row.friend_account_id ?? 0)
              const rowFriendId = toText(row.friend_id, t)
              return (
                <tr key={`friendship-${toText(row.id, t)}`}>
                  <td className="mono">#{toText(row.id, t)}</td>
                  <td>
                    <div>{accountNameMap[String(rowAccountId)] ?? rowAccountId}</div>
                    <div className="text-xs text-muted">#{rowAccountId}</div>
                  </td>
                  <td>
                    <div className="mono">{rowFriendId}</div>
                    {Number.isFinite(rowFriendAccountId) && rowFriendAccountId > 0 && (
                      <div className="text-xs text-muted">#{rowFriendAccountId} {accountNameMap[String(rowFriendAccountId)] ?? ''}</div>
                    )}
                  </td>
                  <td className="mono">{formatTime(row.created_at)}</td>
                  <td>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        deleteMutation.mutate({
                          fromAccountId: rowAccountId,
                          toAccountId: Number.isFinite(rowFriendAccountId) ? rowFriendAccountId : 0,
                          friendId: rowFriendId
                        })
                      }
                    >
                      {tr(t, 'btn_delete_friendship', 'Delete Relationship')}
                    </Button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <Pager
        page={Number(query.data?.page ?? 0)}
        hasPrev={Boolean(query.data?.has_prev)}
        hasNext={Boolean(query.data?.has_next)}
        onPrev={() => setPage((prev) => Math.max(prev - 1, 0))}
        onNext={() => setPage((prev) => prev + 1)}
        t={t}
      />
    </section>
  )
}
function ExchangeCardsSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const queryClient = useQueryClient()
  const [page, setPage] = usePersistedState<number>(managementStateKey('exchange-cards', 'page'), 0)
  const [pageSize, setPageSize] = usePersistedState<number>(managementStateKey('exchange-cards', 'page_size'), 10)
  const [sortBy, setSortBy] = usePersistedState<string>(managementStateKey('exchange-cards', 'sort_by'), 'created_at')
  const [sortOrder, setSortOrder] = usePersistedState<'asc' | 'desc'>(managementStateKey('exchange-cards', 'sort_order'), 'desc')
  const [q, setQ] = usePersistedState<string>(managementStateKey('exchange-cards', 'q'), '')
  const [accountId, setAccountId] = usePersistedState<string>(managementStateKey('exchange-cards', 'account_id'), '')
  const [status, setStatus] = usePersistedState<string>(managementStateKey('exchange-cards', 'status'), '')
  const [notice, setNotice] = useState<InlineNoticeState | null>(null)

  const queryString = useMemo(
    () =>
      buildQuery({
        lang,
        page,
        page_size: pageSize,
        sort_by: sortBy,
        sort_order: sortOrder,
        q,
        account_id: accountId || undefined,
        status: status || undefined
      }),
    [accountId, lang, page, pageSize, q, sortBy, sortOrder, status]
  )
  const query = useQuery({
    queryKey: ['management-exchange-cards', queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/exchange-cards?${queryString}`)
  })

  const cancelMutation = useMutation({
    mutationFn: (requestId: number) => requestJson<{ ok: boolean; message: string }>(`/api/react/management/exchange-cards/${requestId}/cancel`, { method: 'POST', body: {} }),
    onSuccess: (result) => {
      setNotice({ level: result.ok ? 'success' : 'error', text: result.message })
      queryClient.invalidateQueries({ queryKey: ['management-exchange-cards'] })
    }
  })

  const rows = ((query.data?.requests as unknown[]) ?? []) as Record<string, unknown>[]

  return (
    <section className="surface-card section-stack">
      <div className="pagination-row">
        <div className="section-title">{tr(t, 'menu_exchange_cards', 'Exchange Cards')}</div>
        <div className="filter-row">
          <input className="field-input" value={q} onChange={(event) => setQ(event.target.value)} placeholder={tr(t, 'label_search', 'Search')} />
          <input className="field-input" value={accountId} onChange={(event) => setAccountId(event.target.value)} placeholder={tr(t, 'account_id', 'Account ID')} />
          <input className="field-input" value={status} onChange={(event) => setStatus(event.target.value)} placeholder={tr(t, 'filter_status', 'Status')} />
          <Button type="button" size="sm" variant="outline" onClick={() => setPage(0)}>{tr(t, 'label_search', 'Search')}</Button>
        </div>
      </div>
      <InlineNotice notice={notice} />
      <ListQueryControls
        sortBy={sortBy}
        sortOrder={sortOrder}
        pageSize={pageSize}
        sortOptions={[
          { value: 'created_at', labelKey: 'label_created_time', fallback: 'Created At' },
          { value: 'updated_at', labelKey: 'col_updated_at', fallback: 'Updated At' },
          { value: 'target_card_id', labelKey: 'col_card', fallback: 'Card' },
          { value: 'from_account_id', labelKey: 'label_from_account', fallback: 'From Account' }
        ]}
        onSortByChange={(value) => {
          setPage(0)
          setSortBy(value)
        }}
        onSortOrderChange={(value) => {
          setPage(0)
          setSortOrder(value)
        }}
        onPageSizeChange={(value) => {
          setPage(0)
          setPageSize(value)
        }}
        t={t}
      />

      <div className="table-wrap">
        <table className="grid-table">
          <thead>
            <tr>
              <th>{tr(t, 'col_id', 'ID')}</th>
              <th>{tr(t, 'label_from_account', 'From Account')}</th>
              <th>{tr(t, 'col_friend_id', 'Friend ID')}</th>
              <th>{tr(t, 'col_card', 'Card')}</th>
              <th>{tr(t, 'col_status', 'Status')}</th>
              <th>{tr(t, 'col_time', 'Time')}</th>
              <th>{tr(t, 'col_actions', 'Actions')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="text-center text-muted">{tr(t, 'label_no_data', 'No data')}</td>
              </tr>
            )}
            {rows.map((row) => (
              <tr key={toText(row.id, t)}>
                <td className="mono">{toText(row.id, t)}</td>
                <td>{toText(row.from_account_id, t)}</td>
                <td className="mono">{toText(row.to_friend_id, t)}</td>
                <td>{toText(row.target_card_id, t)}</td>
                <td>{exchangeStatusLabel(t, row.status)}</td>
                <td className="mono">{formatTime(row.created_at)}</td>
                <td>
                  {Boolean(row.can_cancel) ? (
                    <Button type="button" size="sm" variant="outline" onClick={() => cancelMutation.mutate(Number(row.id))}>{tr(t, 'btn_cancel_exchange_request', 'Cancel')}</Button>
                  ) : (
                    <span className="text-muted">-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Pager
        page={Number(query.data?.page ?? 0)}
        hasPrev={Boolean(query.data?.has_prev)}
        hasNext={Boolean(query.data?.has_next)}
        onPrev={() => setPage((prev) => Math.max(prev - 1, 0))}
        onNext={() => setPage((prev) => prev + 1)}
        t={t}
      />
    </section>
  )
}

function NotificationsSection({
  lang,
  t,
  assets
}: {
  lang: string
  t: Record<string, string>
  assets: CardImageAssets
}) {
  const queryClient = useQueryClient()
  const [page, setPage] = usePersistedState<number>(managementStateKey('notifications', 'page'), 0)
  const [pageSize, setPageSize] = usePersistedState<number>(managementStateKey('notifications', 'page_size'), 10)
  const [sortBy, setSortBy] = usePersistedState<string>(managementStateKey('notifications', 'sort_by'), 'created_at')
  const [sortOrder, setSortOrder] = usePersistedState<'asc' | 'desc'>(managementStateKey('notifications', 'sort_order'), 'desc')
  const [scene, setScene] = usePersistedState<string>(managementStateKey('notifications', 'scene'), '')
  const [accountId, setAccountId] = usePersistedState<string>(managementStateKey('notifications', 'account_id'), '')
  const [isRead, setIsRead] = usePersistedState<string>(managementStateKey('notifications', 'is_read'), '')
  const [q, setQ] = usePersistedState<string>(managementStateKey('notifications', 'q'), '')
  const [configState, setConfigState] = useState<
    Record<string, { enabled: boolean; enabledWebhook: boolean; extraConfig: Record<string, unknown> }>
  >({})
  const [cardPickerOpen, setCardPickerOpen] = useState(false)
  const [cardPickerScene, setCardPickerScene] = usePersistedState<string>(managementStateKey('notifications', 'picker_scene'), 'rare_card_obtained')
  const [cardPickerQ, setCardPickerQ] = usePersistedState<string>(managementStateKey('notifications', 'picker_q'), '')
  const [cardPickerRarity, setCardPickerRarity] = usePersistedState<string>(managementStateKey('notifications', 'picker_rarity'), '')
  const [cardPickerSetCode, setCardPickerSetCode] = usePersistedState<string>(managementStateKey('notifications', 'picker_set_code'), '')
  const [cardPickerPackName, setCardPickerPackName] = usePersistedState<string>(managementStateKey('notifications', 'picker_pack_name'), '')
  const [cardPickerSortBy, setCardPickerSortBy] = usePersistedState<string>(managementStateKey('notifications', 'picker_sort_by'), 'id')
  const [cardPickerSortOrder, setCardPickerSortOrder] = usePersistedState<'asc' | 'desc'>(managementStateKey('notifications', 'picker_sort_order'), 'asc')
  const [cardPickerPage, setCardPickerPage] = usePersistedState<number>(managementStateKey('notifications', 'picker_page'), 0)
  const [cardPickerPageSize, setCardPickerPageSize] = usePersistedState<number>(managementStateKey('notifications', 'picker_page_size'), 24)
  const [cardPickerSelectedIds, setCardPickerSelectedIds] = useState<number[]>([])
  const [cardPickerCardsAccum, setCardPickerCardsAccum] = useState<Record<string, unknown>[]>([])
  const cardPickerGridRef = useRef<HTMLDivElement | null>(null)
  const [selectedCardNameMap, setSelectedCardNameMap] = useState<Record<number, string>>({})
  const [notice, setNotice] = useState<InlineNoticeState | null>(null)

  const queryString = useMemo(
    () =>
      buildQuery({
        lang,
        page,
        page_size: pageSize,
        sort_by: sortBy,
        sort_order: sortOrder,
        scene: scene || undefined,
        account_id: accountId || undefined,
        is_read: isRead || undefined,
        q
      }),
    [accountId, isRead, lang, page, pageSize, q, scene, sortBy, sortOrder]
  )

  const query = useQuery({
    queryKey: ['management-notifications', queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/notifications?${queryString}`)
  })

  const cardPickerQueryString = useMemo(
    () =>
      buildQuery({
        lang,
        scene: cardPickerScene,
        card_selector_q: cardPickerQ || undefined,
        card_selector_rarity: cardPickerRarity || undefined,
        card_selector_set_code: cardPickerSetCode || undefined,
        card_selector_pack_name: cardPickerPackName || undefined,
        card_selector_sort_by: cardPickerSortBy,
        card_selector_sort_order: cardPickerSortOrder,
        card_selector_page: cardPickerPage,
        card_selector_page_size: cardPickerPageSize,
        notify_card_ids: cardPickerSelectedIds
      }),
    [
      cardPickerPackName,
      cardPickerPage,
      cardPickerPageSize,
      cardPickerQ,
      cardPickerRarity,
      cardPickerScene,
      cardPickerSelectedIds,
      cardPickerSetCode,
      cardPickerSortBy,
      cardPickerSortOrder,
      lang
    ]
  )
  const cardPickerFilterKey = useMemo(
    () =>
      buildQuery({
        scene: cardPickerScene,
        card_selector_q: cardPickerQ || undefined,
        card_selector_rarity: cardPickerRarity || undefined,
        card_selector_set_code: cardPickerSetCode || undefined,
        card_selector_pack_name: cardPickerPackName || undefined,
        card_selector_sort_by: cardPickerSortBy,
        card_selector_sort_order: cardPickerSortOrder,
        card_selector_page_size: cardPickerPageSize
      }),
    [
      cardPickerPackName,
      cardPickerPageSize,
      cardPickerQ,
      cardPickerRarity,
      cardPickerScene,
      cardPickerSetCode,
      cardPickerSortBy,
      cardPickerSortOrder
    ]
  )

  const cardPickerQuery = useQuery({
    enabled: cardPickerOpen,
    queryKey: ['management-notification-card-picker', cardPickerQueryString],
    queryFn: () =>
      fetchJson<Record<string, unknown>>(
        `/api/react/management/notifications/card-picker?${cardPickerQueryString}`
      )
  })

  const markReadMutation = useMutation({
    mutationFn: (notificationId: number) => requestJson<{ ok: boolean }>(`/api/react/management/notifications/${notificationId}/mark-read`, { method: 'POST', body: {} }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['management-notifications'] })
  })

  const markAllMutation = useMutation({
    mutationFn: () => requestJson<{ ok: boolean; message: string }>('/api/react/management/notifications/mark-all-read', {
      method: 'POST',
      body: {
        scene: scene || null,
        account_id: accountId || null
      }
    }),
    onSuccess: (result) => {
      setNotice({ level: result.ok ? 'success' : 'error', text: result.message })
      queryClient.invalidateQueries({ queryKey: ['management-notifications'] })
    }
  })

  const saveConfigMutation = useMutation({
    mutationFn: (payload: { scene: string; enabled: boolean; enabledWebhook: boolean; extraConfig: Record<string, unknown> }) =>
      requestJson<{ ok: boolean; message: string }>('/api/react/management/notifications/config', {
        method: 'POST',
        body: {
          scene: payload.scene,
          enabled: payload.enabled,
          enabled_webhook: payload.enabledWebhook,
          extra_config: payload.extraConfig
        }
      }),
    onSuccess: (result) => {
      setNotice({ level: result.ok ? 'success' : 'error', text: result.message })
      queryClient.invalidateQueries({ queryKey: ['management-notifications'] })
    }
  })

  const testWebhookMutation = useMutation({
    mutationFn: (notificationId: number | null) =>
      requestJson<{ ok: boolean; message: string }>('/api/react/management/notifications/test-webhook', {
        method: 'POST',
        body: {
          notification_id: notificationId,
          scene: scene || null,
          account_id: accountId || null,
          is_read: isRead || null,
          q,
          sort_by: sortBy,
          sort_order: sortOrder,
          page,
          page_size: pageSize
        }
      }),
    onSuccess: (result) => setNotice({ level: result.ok ? 'success' : 'error', text: result.message })
  })

  const notifications = useMemo(
    () => (((query.data?.notifications as unknown[]) ?? []) as Record<string, unknown>[]),
    [query.data?.notifications]
  )
  const configs = useMemo(
    () => (((query.data?.configs as unknown[]) ?? []) as Record<string, unknown>[]),
    [query.data?.configs]
  )
  const sceneOptions = useMemo(
    () =>
      (((query.data?.scene_options as unknown[]) ?? []) as Array<{ value: string; label: string }>),
    [query.data?.scene_options]
  )
  const taskTypeOptions = useMemo(
    () => (((query.data?.task_type_options as unknown[]) ?? []) as string[]),
    [query.data?.task_type_options]
  )
  const taskStatusOptions = useMemo(
    () => (((query.data?.task_status_options as unknown[]) ?? []) as string[]),
    [query.data?.task_status_options]
  )
  const rarityCodes = useMemo(
    () => (((query.data?.rarity_codes as unknown[]) ?? []) as string[]),
    [query.data?.rarity_codes]
  )
  const accountNameMap = useMemo(
    () => ((query.data?.account_name_map as Record<string, string> | undefined) ?? {}),
    [query.data?.account_name_map]
  )
  const cardPickerCards = cardPickerCardsAccum
  const cardPickerRarityCodes = useMemo(
    () => (((cardPickerQuery.data?.rarity_codes as unknown[]) ?? []) as string[]),
    [cardPickerQuery.data?.rarity_codes]
  )
  const cardPickerSetOptions = useMemo(
    () =>
      (((cardPickerQuery.data?.set_codes as unknown[]) ?? []) as Array<{
        value: string
        display_name: string
      }>),
    [cardPickerQuery.data?.set_codes]
  )
  const cardPickerPackOptions = useMemo(
    () =>
      (((cardPickerQuery.data?.pack_names as unknown[]) ?? []) as Array<{
        value: string
        display_name: string
      }>),
    [cardPickerQuery.data?.pack_names]
  )
  const cardPickerSelectedRows = useMemo(
    () => (((cardPickerQuery.data?.selected_cards as unknown[]) ?? []) as Record<string, unknown>[]),
    [cardPickerQuery.data?.selected_cards]
  )
  const cardPickerHasNext = Boolean(cardPickerQuery.data?.card_selector_has_next)
  const cardPickerLoadMore = useCallback(() => {
    if (!cardPickerOpen || cardPickerQuery.isFetching || !cardPickerHasNext) {
      return
    }
    setCardPickerPage((prev) => prev + 1)
  }, [cardPickerHasNext, cardPickerOpen, cardPickerQuery.isFetching])
  const cardPickerSentinelRef = useInfiniteTrigger({
    enabled: cardPickerOpen && cardPickerHasNext && !cardPickerQuery.isFetching,
    onLoadMore: cardPickerLoadMore,
    root: cardPickerGridRef.current
  })

  function parseIdList(value: unknown): number[] {
    if (!Array.isArray(value)) {
      return []
    }
    return value
      .map((item) => Number(item))
      .filter((item) => Number.isFinite(item) && item > 0)
  }

  function openCardPicker(
    sceneKey: string,
    current: { enabled: boolean; enabledWebhook: boolean; extraConfig: Record<string, unknown> }
  ) {
    setCardPickerScene(sceneKey)
    setCardPickerSelectedIds(parseIdList(current.extraConfig.notify_card_ids))
    setCardPickerPage(0)
    setCardPickerCardsAccum([])
    setCardPickerOpen(true)
  }

  function toggleCardSelection(cardId: number, checked: boolean) {
    setCardPickerSelectedIds((prev) => {
      if (checked) {
        if (prev.includes(cardId)) {
          return prev
        }
        return [...prev, cardId]
      }
      return prev.filter((item) => item !== cardId)
    })
  }

  function applyCardPickerSelection() {
    setConfigState((prev) => {
      const current = prev[cardPickerScene]
      if (!current) {
        return prev
      }
      return {
        ...prev,
        [cardPickerScene]: {
          ...current,
          extraConfig: {
            ...current.extraConfig,
            notify_card_ids: cardPickerSelectedIds
          }
        }
      }
    })
    setCardPickerOpen(false)
  }

  useEffect(() => {
    if (!cardPickerOpen) {
      setCardPickerCardsAccum([])
      return
    }
    setCardPickerPage(0)
    setCardPickerCardsAccum([])
  }, [cardPickerFilterKey, cardPickerOpen])

  useEffect(() => {
    if (!cardPickerOpen || !cardPickerQuery.data) {
      return
    }
    const pageCards = (((cardPickerQuery.data.cards as unknown[]) ?? []) as Record<string, unknown>[])
    setCardPickerCardsAccum((prev) => {
      if (cardPickerPage <= 0) {
        return pageCards
      }
      const existingIds = new Set(
        prev
          .map((row) => Number(row.id))
          .filter((id) => Number.isFinite(id) && id > 0)
      )
      const next = [...prev]
      for (const row of pageCards) {
        const rowId = Number(row.id)
        if (!Number.isFinite(rowId) || rowId <= 0 || existingIds.has(rowId)) {
          continue
        }
        next.push(row)
      }
      return next
    })
  }, [cardPickerOpen, cardPickerPage, cardPickerQuery.data])

  useEffect(() => {
    if (!cardPickerOpen) {
      return
    }
    const selectedRows = cardPickerSelectedRows
    if (selectedRows.length === 0) {
      return
    }
    setSelectedCardNameMap((prev) => {
      const next = { ...prev }
      for (const row of selectedRows) {
        const rowId = Number(row.id)
        if (!Number.isFinite(rowId) || rowId <= 0) {
          continue
        }
        const label = toText(row.display_name ?? row.name, t)
        if (label !== '-') {
          next[rowId] = label
        }
      }
      return next
    })
  }, [cardPickerOpen, cardPickerSelectedRows, t])

  useEffect(() => {
    if (!cardPickerOpen) {
      return
    }
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setCardPickerOpen(false)
      }
    }
    window.addEventListener('keydown', onEscape)
    return () => window.removeEventListener('keydown', onEscape)
  }, [cardPickerOpen])

  function updateExtraList(sceneKey: string, field: string, value: string, checked: boolean) {
    setConfigState((prev) => {
      const current = prev[sceneKey]
      if (!current) {
        return prev
      }
      const raw = current.extraConfig[field]
      const currentList = Array.isArray(raw) ? raw.map((item) => String(item)) : []
      const nextList = checked
        ? [...new Set([...currentList, value])]
        : currentList.filter((item) => item !== value)
      return {
        ...prev,
        [sceneKey]: {
          ...current,
          extraConfig: {
            ...current.extraConfig,
            [field]: nextList
          }
        }
      }
    })
  }

  useEffect(() => {
    const nextState: Record<
      string,
      { enabled: boolean; enabledWebhook: boolean; extraConfig: Record<string, unknown> }
    > = {}
    for (const config of configs) {
      const sceneKey = toText(config.scene)
      nextState[sceneKey] = {
        enabled: Boolean(config.enabled),
        enabledWebhook: Boolean(config.enabled_webhook),
        extraConfig: (config.extra_config as Record<string, unknown>) ?? {}
      }
    }
    setConfigState((prev) => {
      const prevKeys = Object.keys(prev)
      const nextKeys = Object.keys(nextState)
      if (prevKeys.length !== nextKeys.length) {
        return nextState
      }
      for (const key of nextKeys) {
        const prevItem = prev[key]
        const nextItem = nextState[key]
        if (!prevItem) {
          return nextState
        }
        if (prevItem.enabled !== nextItem.enabled || prevItem.enabledWebhook !== nextItem.enabledWebhook) {
          return nextState
        }
        if (JSON.stringify(prevItem.extraConfig) !== JSON.stringify(nextItem.extraConfig)) {
          return nextState
        }
      }
      return prev
    })
  }, [configs])

  return (
    <section className="surface-card section-stack">
      <div className="section-title">{tr(t, 'notification_center', 'Notifications')}</div>

      <div className="table-toolbar-layout table-toolbar--dense notification-toolbar-react">
        <div className="table-toolbar-zone table-toolbar-zone--left notification-toolbar-react-left">
          <div className="table-filter-item">
            <label className="section-subtitle">{tr(t, 'col_scene', 'Scene')}</label>
            <select className="field-select table-control" value={scene} onChange={(event) => setScene(event.target.value)}>
              <option value="">{tr(t, 'label_all_scenes', 'All Scenes')}</option>
              {sceneOptions.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>

          <div className="table-filter-item">
            <label className="section-subtitle">{tr(t, 'col_account_id', 'Account ID')}</label>
            <input
              className="field-input table-control"
              value={accountId}
              onChange={(event) => setAccountId(event.target.value)}
              placeholder={tr(t, 'account_id', 'Account ID')}
            />
          </div>

          <div className="table-filter-item">
            <label className="section-subtitle">{tr(t, 'col_status', 'Status')}</label>
            <select className="field-select table-control" value={isRead} onChange={(event) => setIsRead(event.target.value)}>
              <option value="">{tr(t, 'label_all_status', 'All Status')}</option>
              <option value="false">{tr(t, 'label_unread', 'Unread')}</option>
              <option value="true">{tr(t, 'label_read', 'Read')}</option>
            </select>
          </div>

          <div className="table-filter-item notification-filter-item--search">
            <label className="section-subtitle">{tr(t, 'label_search', 'Search')}</label>
            <input
              className="field-input table-control"
              value={q}
              onChange={(event) => setQ(event.target.value)}
              placeholder={tr(t, 'notification_search_placeholder', 'Search title/content/account')}
            />
          </div>
        </div>

        <div className="table-toolbar-zone table-toolbar-zone--right notification-toolbar-react-right">
          <Button type="button" size="sm" variant="outline" onClick={() => setPage(0)}>
            {tr(t, 'label_search', 'Search')}
          </Button>
          <Button type="button" size="sm" onClick={() => markAllMutation.mutate()}>
            {tr(t, 'mark_all_read', tr(t, 'btn_mark_all_read', 'Mark All Read'))}
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={() => testWebhookMutation.mutate(null)}>
            {tr(t, 'btn_test_webhook', 'Test Webhook')}
          </Button>
        </div>
      </div>

      <ListQueryControls
        sortBy={sortBy}
        sortOrder={sortOrder}
        pageSize={pageSize}
        sortOptions={[
          { value: 'created_at', labelKey: 'label_created_time', fallback: 'Created At' },
          { value: 'title', labelKey: 'col_title', fallback: 'Title' },
          { value: 'scene', labelKey: 'col_scene', fallback: 'Scene' }
        ]}
        onSortByChange={(value) => {
          setPage(0)
          setSortBy(value)
        }}
        onSortOrderChange={(value) => {
          setPage(0)
          setSortOrder(value)
        }}
        onPageSizeChange={(value) => {
          setPage(0)
          setPageSize(value)
        }}
        t={t}
      />
      <InlineNotice notice={notice} />

      <div className="section-subtitle">{tr(t, 'page_notification_config', 'Notification Config')}</div>
      <div className="form-grid">
        {configs.map((config) => {
          const sceneKey = toText(config.scene)
          const current = configState[sceneKey] ?? {
            enabled: Boolean(config.enabled),
            enabledWebhook: Boolean(config.enabled_webhook),
            extraConfig: (config.extra_config as Record<string, unknown>) ?? {}
          }
          return (
            <div key={sceneKey} className="surface-card section-stack">
              <div className="section-title">{tr(t, `notification_scene_${sceneKey}`, sceneKey)}</div>
              <label className="filter-row">
                <input
                  type="checkbox"
                  checked={current.enabled}
                  onChange={(event) => {
                    const enabled = event.target.checked
                    const next = { ...current, enabled }
                    setConfigState((prev) => ({ ...prev, [sceneKey]: next }))
                    saveConfigMutation.mutate({
                      scene: sceneKey,
                      enabled,
                      enabledWebhook: current.enabledWebhook,
                      extraConfig: current.extraConfig
                    })
                  }}
                />
                <span>{tr(t, 'label_enabled', 'Enabled')}</span>
              </label>
              <label className="filter-row">
                <input
                  type="checkbox"
                  checked={current.enabledWebhook}
                  onChange={(event) => {
                    const enabledWebhook = event.target.checked
                    const next = { ...current, enabledWebhook }
                    setConfigState((prev) => ({ ...prev, [sceneKey]: next }))
                    saveConfigMutation.mutate({
                      scene: sceneKey,
                      enabled: current.enabled,
                      enabledWebhook,
                      extraConfig: current.extraConfig
                    })
                  }}
                />
                <span>{tr(t, 'label_webhook', 'Webhook')}</span>
              </label>
              {sceneKey === 'rare_card_obtained' && (
                <>
                  <div className="section-subtitle">{tr(t, 'label_notify_by_rarity', 'Notify by Rarity')}</div>
                  <div className="filter-row">
                    {rarityCodes.map((rarity) => {
                      const selectedList = Array.isArray(current.extraConfig.notify_by_rarity) ? current.extraConfig.notify_by_rarity.map((item) => String(item)) : []
                      const checked = selectedList.includes(rarity)
                      return (
                        <label key={`${sceneKey}-rarity-${rarity}`} className="filter-row">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(event) => updateExtraList(sceneKey, 'notify_by_rarity', rarity, event.target.checked)}
                          />
                          <span>{t[`rarity_${rarity}`] ?? rarity}</span>
                        </label>
                      )
                    })}
                  </div>
                  <div className="section-subtitle">{tr(t, 'label_notify_card_ids', 'Target Cards')}</div>
                  <div className="filter-row">
                    {parseIdList(current.extraConfig.notify_card_ids).length === 0 ? (
                      <span className="text-xs text-muted">{tr(t, 'notification_empty', 'No notifications')}</span>
                    ) : (
                      parseIdList(current.extraConfig.notify_card_ids).map((id) => (
                        <span key={`${sceneKey}-card-${id}`} className="tag">
                          #{id} {selectedCardNameMap[id] ?? ''}
                        </span>
                      ))
                    )}
                  </div>
                  <div className="filter-row">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => openCardPicker(sceneKey, current)}
                    >
                      {tr(t, 'btn_select_cards', 'Select Cards')}
                    </Button>
                    <input
                      className="field-input"
                      value={parseIdList(current.extraConfig.notify_card_ids).join(',')}
                      placeholder={tr(t, 'label_notify_card_ids', 'Target Cards') + ' (1,2,3)'}
                      onChange={(event) => {
                        const values = event.target.value
                          .split(',')
                          .map((item) => item.trim())
                          .filter((item) => /^\d+$/.test(item))
                          .map((item) => Number(item))
                        setConfigState((prev) => ({
                          ...prev,
                          [sceneKey]: {
                            ...current,
                            extraConfig: {
                              ...current.extraConfig,
                              notify_card_ids: values
                            }
                          }
                        }))
                      }}
                    />
                  </div>
                </>
              )}
              {sceneKey === 'task_status' && (
                <>
                  <div className="section-subtitle">{tr(t, 'label_notify_task_types', 'Task Types')}</div>
                  <div className="filter-row">
                    {taskTypeOptions.map((taskType) => {
                      const selectedList = Array.isArray(current.extraConfig.notify_task_types) ? current.extraConfig.notify_task_types.map((item) => String(item)) : []
                      const checked = selectedList.includes(taskType)
                      return (
                        <label key={`${sceneKey}-task-${taskType}`} className="filter-row">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(event) => updateExtraList(sceneKey, 'notify_task_types', taskType, event.target.checked)}
                          />
                          <span>{taskTypeLabel(t, taskType)}</span>
                        </label>
                      )
                    })}
                  </div>
                  <div className="section-subtitle">{tr(t, 'label_notify_on', 'Notify On')}</div>
                  <div className="filter-row">
                    {taskStatusOptions.map((status) => {
                      const selectedList = Array.isArray(current.extraConfig.notify_on) ? current.extraConfig.notify_on.map((item) => String(item)) : ['failed', 'blocked', 'timeout']
                      const checked = selectedList.includes(status)
                      return (
                        <label key={`${sceneKey}-status-${status}`} className="filter-row">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(event) => updateExtraList(sceneKey, 'notify_on', status, event.target.checked)}
                          />
                          <span>{statusLabel(t, status)}</span>
                        </label>
                      )
                    })}
                  </div>
                </>
              )}
              <div className="filter-row">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    saveConfigMutation.mutate({
                      scene: sceneKey,
                      enabled: current.enabled,
                      enabledWebhook: current.enabledWebhook,
                      extraConfig: current.extraConfig
                    })
                  }
                >
                  {tr(t, 'btn_save', 'Save')}
                </Button>
              </div>
            </div>
          )
        })}
      </div>

      {cardPickerOpen && (
        <div
          className="dialog-overlay"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setCardPickerOpen(false)
            }
          }}
        >
          <div className="dialog-card notification-picker-dialog" onMouseDown={(event) => event.stopPropagation()}>
            <div className="pagination-row">
              <div className="section-title">{tr(t, 'btn_select_cards', 'Select Cards')}</div>
              <Button type="button" size="sm" variant="outline" onClick={() => setCardPickerOpen(false)}>
                {tr(t, 'label_cancel', 'Cancel')}
              </Button>
            </div>

            <div className="section-stack">
              <div className="filter-row">
                <input
                  className="field-input"
                  value={cardPickerQ}
                  placeholder={tr(t, 'notification_card_search_placeholder', 'Search card name/number/set')}
                  onChange={(event) => {
                    setCardPickerQ(event.target.value)
                    setCardPickerPage(0)
                  }}
                />
                <select
                  className="field-select"
                  value={cardPickerRarity}
                  onChange={(event) => {
                    setCardPickerRarity(event.target.value)
                    setCardPickerPage(0)
                  }}
                >
                  <option value="">{tr(t, 'label_all_rarities', 'All Rarities')}</option>
                  {cardPickerRarityCodes.map((code) => (
                    <option key={`picker-rarity-${code}`} value={code}>
                      {t[`rarity_${code}`] ?? code}
                    </option>
                  ))}
                </select>
                <select
                  className="field-select"
                  value={cardPickerSetCode}
                  onChange={(event) => {
                    setCardPickerSetCode(event.target.value)
                    setCardPickerPage(0)
                  }}
                >
                  <option value="">{tr(t, 'label_all_sets', 'All Sets')}</option>
                  {cardPickerSetOptions.map((option) => (
                    <option key={`picker-set-${option.value}`} value={option.value}>
                      {option.display_name || option.value}
                    </option>
                  ))}
                </select>
                <select
                  className="field-select"
                  value={cardPickerPackName}
                  onChange={(event) => {
                    setCardPickerPackName(event.target.value)
                    setCardPickerPage(0)
                  }}
                >
                  <option value="">{tr(t, 'label_all_packs', 'All Packs')}</option>
                  {cardPickerPackOptions.map((option) => (
                    <option key={`picker-pack-${option.value}`} value={option.value}>
                      {option.display_name || option.value}
                    </option>
                  ))}
                </select>
              </div>

              <div className="filter-row">
                <span className="text-xs text-muted">{tr(t, 'label_sort_by', 'Sort By')}</span>
                <select
                  className="field-select"
                  value={cardPickerSortBy}
                  onChange={(event) => {
                    setCardPickerSortBy(event.target.value)
                    setCardPickerPage(0)
                  }}
                >
                  <option value="id">{tr(t, 'col_id', 'ID')}</option>
                  <option value="number">{tr(t, 'col_number', 'Number')}</option>
                  <option value="name">{tr(t, 'col_name', 'Name')}</option>
                </select>
                <span className="text-xs text-muted">{tr(t, 'label_sort_order', 'Order')}</span>
                <select
                  className="field-select"
                  value={cardPickerSortOrder}
                  onChange={(event) => {
                    setCardPickerSortOrder(event.target.value as 'asc' | 'desc')
                    setCardPickerPage(0)
                  }}
                >
                  <option value="asc">{tr(t, 'sort_order_asc', 'Ascending')}</option>
                  <option value="desc">{tr(t, 'sort_order_desc', 'Descending')}</option>
                </select>
                <span className="text-xs text-muted">{tr(t, 'label_page_size', 'Page Size')}</span>
                <select
                  className="field-select"
                  value={String(cardPickerPageSize)}
                  onChange={(event) => {
                    setCardPickerPageSize(Number(event.target.value))
                    setCardPickerPage(0)
                  }}
                >
                  {[24, 36, 48, 60].map((value) => (
                    <option key={`picker-size-${value}`} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </div>

              <div className="text-xs text-muted">
                {tr(t, 'total_items_label', 'Total')}: {toText(cardPickerQuery.data?.card_selector_total, t)}
                {' · '}
                {tr(t, 'selected_cards_count', 'Selected')}: {cardPickerSelectedIds.length}
              </div>

              {cardPickerQuery.isLoading && (
                <div className="text-xs text-muted">{tr(t, 'label_loading', 'Loading...')}</div>
              )}
              {cardPickerQuery.isError && (
                <div className="text-xs text-danger">{(cardPickerQuery.error as Error).message}</div>
              )}

              <div ref={cardPickerGridRef} className="owned-grid notification-picker-grid">
                {cardPickerCards.map((row) => {
                  const cardId = Number(row.id)
                  if (!Number.isFinite(cardId) || cardId <= 0) {
                    return null
                  }
                  const setCode = toText(row.set_code, t)
                  const cardNumber = Number(row.number)
                  const checked = cardPickerSelectedIds.includes(cardId)
                  const imageUrls = getCardImageUrls(assets, {
                    setCode,
                    cardNumber: Number.isFinite(cardNumber) ? cardNumber : 0
                  }, 240)
                  return (
                    <label
                      key={`picker-card-${cardId}`}
                      className={`owned-card notification-picker-card ${checked ? 'is-selected' : ''}`}
                    >
                      <input
                        className="notification-picker-checkbox"
                        type="checkbox"
                        checked={checked}
                        onChange={(event) => toggleCardSelection(cardId, event.target.checked)}
                      />
                      <div className="owned-card-media">
                        <img
                          src={imageUrls.png}
                          alt={toText(row.display_name ?? row.name, t)}
                          className="owned-card-image"
                          loading="lazy"
                          decoding="async"
                          onError={(event) => {
                            const image = event.currentTarget
                            if (image.dataset.webpTried === '1') {
                              image.src = imageUrls.cdnPng
                              image.dataset.webpTried = '2'
                              return
                            }
                            if (image.dataset.webpTried === '2') {
                              image.src = imageUrls.cdnWebp
                              image.dataset.webpTried = '3'
                              return
                            }
                            image.dataset.webpTried = '1'
                            image.src = imageUrls.webp
                          }}
                        />
                      </div>
                      <div className="notification-picker-meta mono">
                        #{cardId} {setCode}-{String(Math.max(cardNumber, 0)).padStart(3, '0')}
                      </div>
                      <div className="owned-card-name">{toText(row.display_name ?? row.name, t)}</div>
                    </label>
                  )
                })}
                <div ref={cardPickerSentinelRef} className="infinite-sentinel" />
              </div>

              {cardPickerCards.length === 0 && (
                <div className="text-xs text-muted">{tr(t, 'label_no_data', 'No data')}</div>
              )}

              <div className="pagination-row">
                <div className="section-stack">
                  {cardPickerQuery.isFetching && (
                    <div className="text-xs text-muted">{tr(t, 'label_loading_more', 'Loading more...')}</div>
                  )}
                  {!cardPickerHasNext && cardPickerCards.length > 0 && (
                    <div className="text-xs text-muted">{tr(t, 'label_reach_end', 'Reached the end')}</div>
                  )}
                </div>
                <Button type="button" size="sm" onClick={applyCardPickerSelection}>
                  {tr(t, 'btn_apply_selection', 'Apply Selection')}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="table-wrap">
        <table className="grid-table">
          <thead>
            <tr>
              <th>{tr(t, 'col_id', 'ID')}</th>
              <th>{tr(t, 'col_scene', 'Scene')}</th>
              <th>{tr(t, 'col_title', 'Title')}</th>
              <th>{tr(t, 'col_description', 'Content')}</th>
              <th>{tr(t, 'col_account', 'Account')}</th>
              <th>{tr(t, 'label_read', 'Read')}</th>
              <th>{tr(t, 'col_time', 'Time')}</th>
              <th>{tr(t, 'col_actions', 'Actions')}</th>
            </tr>
          </thead>
          <tbody>
            {notifications.length === 0 && (
              <tr>
                <td colSpan={8} className="text-center text-muted">{tr(t, 'notification_empty', 'No notifications')}</td>
              </tr>
            )}
            {notifications.map((row) => (
              <tr key={toText(row.id, t)}>
                <td className="mono">{toText(row.id, t)}</td>
                <td>{toText(row.scene_label, t) || tr(t, `notification_scene_${toText(row.scene, t)}`, toText(row.scene, t))}</td>
                <td>{toText(row.title, t)}</td>
                <td>
                  <div className="notification-row-content">
                    {String(row.image_url ?? '').length > 0 ? (
                      <img
                        src={String(row.image_url)}
                        alt={toText(row.title, t)}
                        className="notification-thumb"
                        loading="lazy"
                        decoding="async"
                        onError={(event) => {
                          const image = event.currentTarget
                          const webpUrl = String(row.image_webp_url ?? '')
                          if (webpUrl && image.dataset.webpTried !== '1') {
                            image.dataset.webpTried = '1'
                            image.src = webpUrl
                            return
                          }
                          image.style.display = 'none'
                        }}
                      />
                    ) : null}
                    <div className="notification-content-text" title={toText(row.content, t)}>
                      {toText(row.content, t)}
                    </div>
                  </div>
                </td>
                <td>
                  {toText(row.related_account_id, t) === '-'
                    ? '-'
                    : accountNameMap[String(row.related_account_id)] ?? toText(row.related_account_id, t)}
                </td>
                <td>{Boolean(row.is_read) ? tr(t, 'label_read', 'Read') : tr(t, 'label_unread', 'Unread')}</td>
                <td className="mono">{formatTime(row.created_at)}</td>
                <td>
                  <div className="filter-row">
                    {!Boolean(row.is_read) && (
                      <Button type="button" size="sm" variant="outline" onClick={() => markReadMutation.mutate(Number(row.id))}>{tr(t, 'btn_mark_read', 'Mark Read')}</Button>
                    )}
                    <Button type="button" size="sm" variant="outline" onClick={() => testWebhookMutation.mutate(Number(row.id))}>{tr(t, 'btn_test_send', 'Test')}</Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Pager
        page={Number(query.data?.page ?? 0)}
        hasPrev={Boolean(query.data?.has_prev)}
        hasNext={Boolean(query.data?.has_next)}
        onPrev={() => setPage((prev) => Math.max(prev - 1, 0))}
        onNext={() => setPage((prev) => prev + 1)}
        t={t}
      />
    </section>
  )
}

function JsonSection({ endpoint, title, lang, t }: { endpoint: string; title: string; lang: string; t: Record<string, string> }) {
  const [page, setPage] = useState(0)
  const queryString = useMemo(() => buildQuery({ lang, page }), [lang, page])
  const query = useQuery({
    queryKey: ['management-generic', endpoint, queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/${endpoint}?${queryString}`)
  })

  const rows = ((query.data?.items as unknown[]) ?? []) as Record<string, unknown>[]
  const columns = useMemo<ColumnDef[]>(() => {
    if (rows.length === 0) {
      return []
    }
    return Object.keys(rows[0]).slice(0, 8).map((key) => ({
      key,
      label: key,
      render: (row) => (key.includes('at') ? formatTime(row[key]) : toText(row[key]))
    }))
  }, [rows])

  return (
    <section className="surface-card section-stack">
      <div className="section-title">{title}</div>
      {query.isLoading && <div className="text-sm text-muted">{tr(t, 'label_loading', 'Loading...')}</div>}
      {query.isError && <div className="text-sm text-danger">{(query.error as Error).message}</div>}
      {columns.length > 0 && <DataGrid rows={rows} columns={columns} t={t} />}
      <Pager
        page={Number(query.data?.page ?? 0)}
        hasPrev={Boolean(query.data?.has_prev)}
        hasNext={Boolean(query.data?.has_next)}
        onPrev={() => setPage((prev) => Math.max(prev - 1, 0))}
        onNext={() => setPage((prev) => prev + 1)}
        t={t}
      />
    </section>
  )
}

function ManagementSectionRouter({
  lang,
  sectionKey,
  t,
  assets
}: {
  lang: string
  sectionKey: string
  t: Record<string, string>
  assets: CardImageAssets
}) {
  if (sectionKey === 'accounts') {
    return <AccountsSection lang={lang} t={t} />
  }
  if (sectionKey === 'plans') {
    return <PlansSection lang={lang} t={t} />
  }
  if (sectionKey === 'resources') {
    return <ResourcesSection lang={lang} t={t} />
  }
  if (sectionKey === 'tasks') {
    return <TasksSection lang={lang} t={t} />
  }
  if (sectionKey === 'metadata') {
    return <MetadataSection lang={lang} t={t} />
  }
  if (sectionKey === 'daily-gift') {
    return <DailyGiftSection lang={lang} t={t} />
  }
  if (sectionKey === 'friendships') {
    return <FriendshipsSection lang={lang} t={t} />
  }
  if (sectionKey === 'exchange-cards') {
    return <ExchangeCardsSection lang={lang} t={t} />
  }
  if (sectionKey === 'notifications') {
    return <NotificationsSection lang={lang} t={t} assets={assets} />
  }
  return <JsonSection endpoint={sectionKey} title={sectionKey} lang={lang} t={t} />
}

export function ManagementPage({ lang, t, assets }: ManagementPageProps) {
  usePersistedSearchParams()

  return (
    <section className="management-shell">
      <aside className="surface-card management-sidebar">
        <nav className="management-sidebar-nav">
          {sections.map((section) => (
            <NavLink key={section.key} to={`/management/${section.key}`}>
              {({ isActive }) => (
                <Button
                  variant={isActive ? 'default' : 'outline'}
                  size="sm"
                  type="button"
                  className="management-side-btn"
                >
                  {t[section.labelKey] ?? section.fallback}
                </Button>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="management-main section-stack">
        <Routes>
          <Route path="/" element={<Navigate to="/management/accounts" replace />} />
          {sections.map((section) => (
            <Route
              key={section.key}
              path={section.key}
              element={<ManagementSectionRouter lang={lang} sectionKey={section.key} t={t} assets={assets} />}
            />
          ))}
        </Routes>
      </div>
    </section>
  )
}
