import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { DatePicker } from '@/components/ui/date-picker'
import { SearchableSelect } from '@/components/ui/searchable-select'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, decodeSelectValue, encodeSelectValue } from '@/components/ui/select'
import { Tooltip } from '@/components/ui/tooltip'
import { useManagementListQuery } from '@/hooks/use-management-list-query'
import { usePersistedState } from '@/hooks/use-persisted-state'
import { usePersistedSearchParams } from '@/hooks/use-persisted-search-params'
import { fetchJson, requestFormJson, requestJson } from '@/lib/api'
import { type CardImageAssets } from '@/lib/card-image'
import { tr } from '@/lib/i18n'
import {
  formatDateYmd,
  formatDurationExact,
} from '@/lib/time-display'

import { NotificationsSection } from './management/notifications-section'
import { buildRecentBizDates } from './management/daily-gift-utils'
import { getManagementFilterOptions } from './management/filter-options'
import {
  buildMetadataExecutePayload,
  buildMetadataPreviewPayload,
  buildMetadataQueryString,
  buildMetadataRequestContext
} from './management/metadata-query'
import { buildManagementListQueryParams } from './management/list-query'
import type { ManagementListOption, ManagementListSpec } from './management/list-spec'
import { useManagementListState } from './management/list-state'
import { ManagementListToolbar } from './management/list-toolbar'
import { buildTaskTableColumns } from './management/task-table'
import { buildResetCompletedTasksPayload, resolveManagementTaskAccountFilter } from './management/task-filters'
import {
  buildAccountPlansQuery,
  buildPackConfigQuery,
  buildPlanEditorQuery,
  buildTaskAccountOptionsQuery
} from './management/management-queries'
import {
  AccountIdentityCell,
  CopyableFriendId,
  InlineNotice,
  ManagementDataGrid,
  Pager,
  QueryTotalSummary,
  SortableHeaderCell,
  TruncatedText,
  buildAccountSelectOptions,
  managementStateKey,
  renderBadge,
  renderRelativeTime,
  renderStatusBadgeWithReason,
  searchableSelectLocale,
  statusBadgeVariant,
  statusLabel,
  taskTypeLabel,
  toText,
  toTotalCount,
  type ManagementColumnDef,
  type InlineNoticeState,
  type SearchableOption,
  type SortOption
} from './management/shared'

interface ManagementPageProps {
  lang: string
  t: Record<string, string>
  assets: CardImageAssets
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

export function buildManagementSectionTo(sectionKey: string, search: string) {
  const params = new URLSearchParams(search)
  const lang = params.get('lang')
  return {
    pathname: `/management/${sectionKey}`,
    // 变更原因：管理子页筛选和分页属于当前子页，侧边栏切换只应保留全局语言。
    search: lang ? `?lang=${lang}` : ''
  }
}

function stringKey(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function prefixedLabel(t: Record<string, string>, prefix: string, value: unknown): string {
  const key = stringKey(value)
  if (!key) {
    return '-'
  }
  return tr(t, `${prefix}_${key}`, key)
}

function disabledReasonLabel(
  t: Record<string, string>,
  messageKey: string,
  fallback: string,
  status: unknown,
  formatStatusLabel: (t: Record<string, string>, value: unknown) => string
): string {
  return `${tr(t, messageKey, fallback)} (${formatStatusLabel(t, status)})`
}

function moveItemByOffset<T>(items: T[], index: number, offset: -1 | 1): T[] {
  const targetIndex = index + offset
  if (targetIndex < 0 || targetIndex >= items.length) {
    return items
  }
  const nextItems = [...items]
  const current = nextItems[index]
  nextItems[index] = nextItems[targetIndex]
  nextItems[targetIndex] = current
  return nextItems
}

function moveItemToIndex<T>(items: T[], sourceIndex: number, targetIndex: number): T[] {
  if (
    sourceIndex < 0 ||
    targetIndex < 0 ||
    sourceIndex >= items.length ||
    targetIndex >= items.length ||
    sourceIndex === targetIndex
  ) {
    return items
  }
  const nextItems = [...items]
  const [moved] = nextItems.splice(sourceIndex, 1)
  nextItems.splice(targetIndex, 0, moved)
  return nextItems
}

function moveTaskOrderWithFallback(
  currentOrder: string[],
  fallbackOrder: string[],
  index: number,
  offset: -1 | 1
): string[] {
  const sourceOrder = currentOrder.length > 0 ? [...currentOrder] : [...fallbackOrder]
  const nextOrder = moveItemByOffset(sourceOrder, index, offset)
  if (nextOrder === sourceOrder) {
    return currentOrder.length > 0 ? currentOrder : sourceOrder
  }
  return nextOrder
}

type IntervalPartKey = 'days' | 'hours' | 'minutes' | 'seconds'

interface IntervalParts {
  days: number
  hours: number
  minutes: number
  seconds: number
}

const INTERVAL_SECONDS_PER_DAY = 86400
const INTERVAL_SECONDS_PER_HOUR = 3600
const INTERVAL_SECONDS_PER_MINUTE = 60

function parseNonNegativeInt(value: string): number {
  const parsed = Number.parseInt(value, 10)
  if (!Number.isFinite(parsed) || parsed < 0) {
    return 0
  }
  return parsed
}

function splitIntervalSeconds(totalSeconds: number): IntervalParts {
  const normalized = Number.isFinite(totalSeconds) && totalSeconds > 0 ? Math.floor(totalSeconds) : 0
  const days = Math.floor(normalized / INTERVAL_SECONDS_PER_DAY)
  const hours = Math.floor((normalized % INTERVAL_SECONDS_PER_DAY) / INTERVAL_SECONDS_PER_HOUR)
  const minutes = Math.floor((normalized % INTERVAL_SECONDS_PER_HOUR) / INTERVAL_SECONDS_PER_MINUTE)
  const seconds = normalized % INTERVAL_SECONDS_PER_MINUTE
  return { days, hours, minutes, seconds }
}

function mergeIntervalSeconds(parts: IntervalParts): number {
  return (
    parts.days * INTERVAL_SECONDS_PER_DAY
    + parts.hours * INTERVAL_SECONDS_PER_HOUR
    + parts.minutes * INTERVAL_SECONDS_PER_MINUTE
    + parts.seconds
  )
}

function updateIntervalPart(totalSeconds: number, key: IntervalPartKey, rawValue: string): number {
  const nextParts = splitIntervalSeconds(totalSeconds)
  nextParts[key] = parseNonNegativeInt(rawValue)
  return mergeIntervalSeconds(nextParts)
}

function currentGameBizDate(): string {
  const now = new Date()
  const businessDate = new Date(now)
  if (now.getHours() < 14) {
    businessDate.setDate(businessDate.getDate() - 1)
  }
  return formatDateYmd(businessDate)
}

function giftStatusLabel(t: Record<string, string>, value: unknown): string {
  return prefixedLabel(t, 'gift_status', value)
}

function pairProgressLabel(t: Record<string, string>, value: unknown): string {
  return prefixedLabel(t, 'gift_pair_progress', value)
}

function taskTypesListLabel(t: Record<string, string>, value: unknown): string {
  if (!Array.isArray(value) || value.length === 0) {
    return '-'
  }
  const labels = value
    .map((item) => taskTypeLabel(t, item))
    .filter((item) => item && item !== '-')
  if (labels.length === 0) {
    return '-'
  }
  return labels.join(', ')
}

function requestTypeLabel(t: Record<string, string>, value: unknown): string {
  return prefixedLabel(t, 'friend_request_type', value)
}

function requestStatusLabel(t: Record<string, string>, value: unknown): string {
  return prefixedLabel(t, 'friend_request_status', value)
}

function exchangeStatusLabel(t: Record<string, string>, value: unknown): string {
  return prefixedLabel(t, 'exchange_request_status', value)
}

function exchangeCancelDisabledReason(t: Record<string, string>, status: unknown): string {
  return disabledReasonLabel(
    t,
    'msg_exchange_request_cancel_failed',
    'Only sending/sended requests can be cancelled',
    status,
    exchangeStatusLabel
  )
}

function requestCancelDisabledReason(t: Record<string, string>, status: unknown): string {
  return disabledReasonLabel(
    t,
    'msg_request_cancel_failed',
    'Only pending request records can be removed',
    status,
    requestStatusLabel
  )
}

function reasonTitle(reason: string | null | undefined): string | undefined {
  const text = (reason ?? '').trim()
  if (!text || text === '-') {
    return undefined
  }
  return text
}

function parseBool(value: unknown): boolean {
  if (value === true) {
    return true
  }
  if (value === false) {
    return false
  }
  if (typeof value === 'number') {
    return value === 1
  }
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase()
    return normalized === '1' || normalized === 'true'
  }
  return false
}

function datePickerLocale(t: Record<string, string>) {
  return {
    selectDateLabel: tr(t, 'date_picker_select_date', 'Select date'),
    todayLabel: tr(t, 'btn_today', 'Today'),
    clearLabel: tr(t, 'date_picker_clear', 'Clear'),
    prevMonthLabel: tr(t, 'date_picker_prev_month', 'Previous month'),
    nextMonthLabel: tr(t, 'date_picker_next_month', 'Next month'),
    weekdayLabels: [
      tr(t, 'date_picker_weekday_mon', 'Mon'),
      tr(t, 'date_picker_weekday_tue', 'Tue'),
      tr(t, 'date_picker_weekday_wed', 'Wed'),
      tr(t, 'date_picker_weekday_thu', 'Thu'),
      tr(t, 'date_picker_weekday_fri', 'Fri'),
      tr(t, 'date_picker_weekday_sat', 'Sat'),
      tr(t, 'date_picker_weekday_sun', 'Sun')
    ]
  }
}

function AccountsSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const queryClient = useQueryClient()
  const [editingAccount, setEditingAccount] = useState<Record<string, unknown> | null>(null)
  const [editingPlans, setEditingPlans] = useState<{ accountId: number; items: AccountPlanItemState[] } | null>(null)
  const [currentPlans, setCurrentPlans] = useState<AccountPlanItemState[]>([])
  const [editingPackConfig, setEditingPackConfig] = useState<{ accountId: number; setCode: string; boosterName: string } | null>(null)
  const [cardSets, setCardSets] = useState<Array<{ code: string; display_name: string }>>([])
  const [boosterOptions, setBoosterOptions] = useState<Array<{ name: string; display_name: string }>>([])
  const [notice, setNotice] = useState<InlineNoticeState | null>(null)
  const selectLocale = useMemo(() => searchableSelectLocale(t), [t])
  const accountListSpec = useMemo<ManagementListSpec>(() => ({
    storageKey: 'accounts',
    defaultPageSize: 10,
    pageSizeOptions: [10, 20, 50, 100],
    filters: [
      {
        key: 'q',
        kind: 'search',
        label: tr(t, 'label_search', 'Search'),
        placeholder: tr(t, 'filter_account_id_placeholder', 'Search account')
      }
    ],
    sort: {
      defaultBy: 'id',
      defaultOrder: 'asc',
      options: [
        { value: 'id', labelKey: 'col_id', fallback: 'ID' },
        { value: 'nickname', labelKey: 'col_nickname', fallback: 'Nickname' },
        { value: 'friend_id', labelKey: 'col_friend_id', fallback: 'Friend ID' }
      ]
    }
  }), [t])
  const {
    state: accountListState,
    setFilter: setAccountFilter,
    cycleSort: cycleAccountSort,
    setPage: setAccountPage,
    setPageSize: setAccountPageSize
  } = useManagementListState(accountListSpec)
  const accountQueryParams = useMemo(
    () => buildManagementListQueryParams(accountListSpec, accountListState),
    [accountListSpec, accountListState]
  )
  const { query } = useManagementListQuery<Record<string, unknown>>({
    queryKey: 'management-accounts',
    endpoint: 'accounts',
    lang,
    params: accountQueryParams
  })
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
        body: payload.items.map((item) => ({ plan_id: item.plan_id, is_active: item.is_active === true }))
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
      queryClient.invalidateQueries({ queryKey: ['management-account-packs'] })
    }
  })

  const items = ((query.data?.items as unknown[]) ?? []) as Record<string, unknown>[]
  const accountIdsStr = useMemo(() => items.map((i) => String(i.id ?? '')).filter(Boolean).join(','), [items])
  const totalRecords = toTotalCount(query.data?.total, items.length)

  const packsQuery = useQuery<{ packs: Record<string, Record<string, unknown>>; pack_configs: Record<string, Record<string, unknown>> }>({
    queryKey: ['management-account-packs', lang, accountIdsStr],
    queryFn: () => fetchJson(`/api/react/management/accounts/packs?lang=${lang}&account_ids=${accountIdsStr}`),
    enabled: accountIdsStr.length > 0,
    staleTime: 60_000,
    refetchInterval: (q) => (q.state.data && Object.keys(q.state.data.packs ?? {}).length > 0 ? false : 3_000),
    retry: 10,
  })
  const packConfigs = packsQuery.data?.pack_configs ?? {}
  const autoPackMap = packsQuery.data?.packs ?? {}

  async function openPlansEditor(accountId: number) {
    const data = await fetchJson<Record<string, unknown>>(
      `/api/react/management/accounts/${accountId}/plans?${buildAccountPlansQuery(lang)}`
    )
    const current = ((data.current_assocs as unknown[]) ?? []) as Record<string, unknown>[]
    const available = ((data.available_plans as unknown[]) ?? []) as Record<string, unknown>[]

    const currentItems = current
      .map((item) => ({
        plan_id: Number(item.task_plan_id ?? item.plan_id ?? (item.task_plan as Record<string, unknown> | undefined)?.id),
        plan_name: toText((item.task_plan as Record<string, unknown>)?.name ?? item.name, t),
        is_active: parseBool(item.is_active),
        priority: Number(item.priority ?? 0)
      }))
      .filter((item) => Number.isFinite(item.plan_id))
      .sort((a, b) => b.priority - a.priority)
      .map(({ plan_id, plan_name, is_active }) => ({ plan_id, plan_name, is_active }))

    const existingIds = new Set(currentItems.map((item) => item.plan_id))
    const candidateItems = available
      .map((item) => ({
        plan_id: Number(item.id ?? item.plan_id ?? item.task_plan_id),
        plan_name: toText(item.name, t),
        is_active: parseBool(item.is_active)
      }))
      .filter((item) => Number.isFinite(item.plan_id) && !existingIds.has(item.plan_id))

    setCurrentPlans(currentItems.filter((item) => item.is_active))
    setEditingPlans({ accountId, items: [...currentItems, ...candidateItems] })
  }

  async function openPackConfigEditor(accountId: number) {
    const [config, sets] = await Promise.all([
      fetchJson<Record<string, unknown>>(
        `/api/react/management/accounts/${accountId}/pack-config?${buildPackConfigQuery(lang)}`
      ),
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

  const setSelectOptions = useMemo<SearchableOption[]>(
    () => [
      { value: '', label: tr(t, 'label_no_pack_auto', 'No target pack (auto select)') },
      ...cardSets.map((item) => ({
        value: item.code,
        label: item.display_name,
        searchText: `${item.code} ${item.display_name}`
      }))
    ],
    [cardSets, t]
  )

  const boosterSelectOptions = useMemo<SearchableOption[]>(
    () => [
      { value: '', label: tr(t, 'label_none', '-- None --') },
      ...boosterOptions.map((booster) => ({
        value: booster.name,
        label: booster.display_name,
        searchText: `${booster.name} ${booster.display_name}`
      }))
    ],
    [boosterOptions, t]
  )

  const moveEditingPlanItem = useCallback((index: number, offset: -1 | 1) => {
    setEditingPlans((prev) => {
      if (!prev) {
        return prev
      }
      const nextItems = moveItemByOffset(prev.items, index, offset)
      if (nextItems === prev.items) {
        return prev
      }
      return { ...prev, items: nextItems }
    })
  }, [])

  return (
    <section className="section-stack">
      <div className="surface-card section-stack">
        <div className="section-title">{tr(t, 'menu_accounts', 'Accounts')}</div>
        <ManagementListToolbar
          spec={accountListSpec}
          state={accountListState}
          searchableLocale={selectLocale}
          onFilterChange={setAccountFilter}
          onPageSizeChange={setAccountPageSize}
          t={t}
        />

        {query.isLoading && <div className="text-sm text-muted">{tr(t, 'label_loading', 'Loading...')}</div>}
        {query.isError && <div className="text-sm text-danger">{(query.error as Error).message}</div>}
        <InlineNotice notice={notice} />
        <QueryTotalSummary t={t} total={totalRecords} />

        {query.data && (
          <>
            <div className="table-wrap">
              <table className="grid-table">
                <thead>
                  <tr>
                    <SortableHeaderCell
                      label={tr(t, 'col_account', 'Account')}
                      sortKey="id"
                      sortBy={accountListState.sortBy}
                      sortOrder={accountListState.sortOrder}
                      onToggle={cycleAccountSort}
                    />
                    <th>{tr(t, 'col_plans', 'Plans')}</th>
                    <th>{tr(t, 'col_target_pack', 'Target Pack')}{' '}{packsQuery.isFetching && <span className="text-muted text-xs">({tr(t, 'label_loading', '...')})</span>}</th>
                    <th>{tr(t, 'col_actions', 'Actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.length === 0 && (
                    <tr>
                      <td colSpan={4} className="text-center text-muted">{tr(t, 'label_no_data', 'No data')}</td>
                    </tr>
                  )}
                  {items.map((item) => {
                    const accountId = Number(item.id)
                    const associations = ((item.task_plan_associations as unknown[]) ?? []) as Record<string, unknown>[]
                    const activePlanNames = associations
                      .filter((assoc) => parseBool(assoc.is_active) && typeof assoc.task_plan === 'object' && assoc.task_plan !== null)
                      .map((assoc) => toText((assoc.task_plan as Record<string, unknown>).name))
                    const config = packConfigs[String(accountId)]
                    const autoPack = autoPackMap[String(accountId)]
                    const targetPack =
                      config
                        ? `${toText(config.set_code, t)}/${toText(config.booster_name, t)}`
                        : autoPack
                          ? `${toText(autoPack.set_code, t)}/${toText(autoPack.booster_name, t)} (${tr(t, 'label_auto', 'Auto')})`
                          : packsQuery.isFetching || (!config && !autoPack && (packsQuery.data?.packs == null || Object.keys(packsQuery.data.packs).length === 0))
                            ? tr(t, 'label_loading', '计算中...')
                            : '-'

                    return (
                      <tr key={accountId}>
                        <td>
                          <AccountIdentityCell
                            t={t}
                            accountId={item.id}
                            name={item.nickname || item.display_name}
                            friendId={item.friend_id}
                            gameId={item.game_id}
                          />
                        </td>
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
              onPrev={() => setAccountPage(Math.max(accountListState.page - 1, 0))}
              onNext={() => setAccountPage(accountListState.page + 1)}
              t={t}
            />
          </>
        )}
      </div>

      {editingAccount && (
        <div className="dialog-overlay" onClick={() => setEditingAccount(null)}>
          <div className="dialog-card dialog-card--sm section-stack" onClick={(event) => event.stopPropagation()}>
            <div className="section-title">{tr(t, 'modal_title_edit_account', 'Edit Account')} #{toText(editingAccount.id, t)}</div>
            <label className="section-subtitle">{tr(t, 'label_nickname', 'Nickname')}</label>
            <input
              id="account-nickname"
              className="field-input"
              name="account-nickname"
              value={toText(editingAccount.nickname)}
              onChange={(event) => setEditingAccount((prev) => (prev ? { ...prev, nickname: event.target.value } : null))}
            />
            <label className="section-subtitle">{tr(t, 'label_remark', 'Remark')}</label>
            <textarea
              id="account-remark"
              className="field-textarea"
              name="account-remark"
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
          <div className="dialog-card dialog-card--md section-stack plan-editor-dialog account-plan-assoc-dialog" onClick={(event) => event.stopPropagation()}>
            <div className="section-title">{tr(t, 'btn_edit_plans', 'Plans')} #{editingPlans.accountId}</div>
            <div className="section-subtitle">{tr(t, 'label_active_plans', 'Active Plans')}</div>
            <div className="filter-row">
              {currentPlans.map((item) => (
                <span key={item.plan_id} className="tag">{item.plan_name}</span>
              ))}
            </div>
            <div className="section-subtitle">{tr(t, 'option_select_plan', 'Select plan')}</div>
            <div className="section-stack plan-assoc-list">
              {editingPlans.items.map((planItem, index) => {
                const checked = planItem.is_active
                const isFirst = index === 0
                const isLast = index === editingPlans.items.length - 1
                return (
                  <div key={planItem.plan_id} className="plan-assoc-item">
                    <label className="filter-row plan-assoc-main">
                      <input
                        id={`account-plan-active-${planItem.plan_id}`}
                        type="checkbox"
                        name={`account-plan-active-${planItem.plan_id}`}
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
                      <span className="plan-assoc-name">{planItem.plan_name}</span>
                    </label>
                    <div className="plan-assoc-actions">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={isFirst}
                        onClick={() => moveEditingPlanItem(index, -1)}
                      >
                        ↑
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={isLast}
                        onClick={() => moveEditingPlanItem(index, 1)}
                      >
                        ↓
                      </Button>
                    </div>
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
          <div className="dialog-card dialog-card--sm section-stack pack-config-dialog" onClick={(event) => event.stopPropagation()}>
            <div className="section-title">{tr(t, 'btn_pack_config_title', 'Pack Config')} #{editingPackConfig.accountId}</div>
            <label className="section-subtitle">{tr(t, 'label_target_series', 'Target Series')}</label>
            <SearchableSelect
              value={editingPackConfig.setCode}
              options={setSelectOptions}
              onValueChange={async (setCode) => {
                if (!setCode) {
                  setBoosterOptions([])
                  setEditingPackConfig((prev) => (prev ? { ...prev, setCode: '', boosterName: '' } : null))
                  return
                }
                const boosters = await fetchJson<Array<{ name: string; display_name: string }>>(`/api/react/management/card-sets/${encodeURIComponent(setCode)}/boosters`)
                setBoosterOptions(boosters)
                setEditingPackConfig((prev) => (prev ? { ...prev, setCode, boosterName: boosters[0]?.name ?? '' } : null))
              }}
              {...selectLocale}
              placeholder={tr(t, 'label_target_series', 'Target Series')}
              pageSize={10}
            />

            <label className="section-subtitle">{tr(t, 'label_target_booster', 'Target Booster')}</label>
            <SearchableSelect
              value={editingPackConfig.boosterName}
              options={boosterSelectOptions}
              onValueChange={(boosterName) => setEditingPackConfig((prev) => (prev ? { ...prev, boosterName } : null))}
              {...selectLocale}
              placeholder={tr(t, 'label_target_booster', 'Target Booster')}
              pageSize={10}
            />

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
  const [editingPlanId, setEditingPlanId] = useState<number | null>(null)
  const [isPlanEditorOpen, setIsPlanEditorOpen] = useState(false)
  const [planName, setPlanName] = useState('')
  const [planDesc, setPlanDesc] = useState('')
  const [taskOptions, setTaskOptions] = useState<string[]>([])
  const [resetTypeOptions, setResetTypeOptions] = useState<string[]>([])
  const [taskOrder, setTaskOrder] = useState<string[]>([])
  const [taskConfigMap, setTaskConfigMap] = useState<Record<string, PlanTaskConfigState>>({})
  const [draggingTask, setDraggingTask] = useState<string | null>(null)
  const draggingTaskRef = useRef<string | null>(null)
  const [dragOverTask, setDragOverTask] = useState<string | null>(null)
  const [notice, setNotice] = useState<InlineNoticeState | null>(null)
  const [pendingDeletePlan, setPendingDeletePlan] = useState<{ id: number; name: string } | null>(null)
  const planListSpec = useMemo<ManagementListSpec>(() => ({
    storageKey: 'plans',
    defaultPageSize: 10,
    pageSizeOptions: [10, 20, 50, 100],
    filters: [
      {
        key: 'q',
        kind: 'search',
        label: tr(t, 'label_search', 'Search'),
        placeholder: tr(t, 'label_search', 'Search')
      }
    ],
    sort: {
      defaultBy: 'id',
      defaultOrder: 'asc',
      options: [
        { value: 'id', labelKey: 'col_id', fallback: 'ID' },
        { value: 'name', labelKey: 'col_name', fallback: 'Name' }
      ]
    }
  }), [t])
  const {
    state: planListState,
    setFilter: setPlanFilter,
    cycleSort: cyclePlanSort,
    setPage: setPlanPage,
    setPageSize: setPlanPageSize
  } = useManagementListState(planListSpec)
  const planQueryParams = useMemo(
    () => buildManagementListQueryParams(planListSpec, planListState),
    [planListSpec, planListState]
  )
  const { query } = useManagementListQuery<Record<string, unknown>>({
    queryKey: 'management-plans',
    endpoint: 'plans',
    lang,
    params: planQueryParams
  })
  const reorderTaskByDrag = useCallback((sourceTask: string, targetTask: string) => {
    setTaskOrder((prev) => {
      const sourceOrder = prev.length > 0 ? [...prev] : [...taskOptions]
      const sourceIndex = sourceOrder.indexOf(sourceTask)
      const targetIndex = sourceOrder.indexOf(targetTask)
      const nextOrder = moveItemToIndex(sourceOrder, sourceIndex, targetIndex)
      if (nextOrder === sourceOrder) {
        return prev.length > 0 ? prev : sourceOrder
      }
      return nextOrder
    })
  }, [taskOptions])

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
        if (config.resetType === 'interval') {
          form.set(`task_interval_${taskType}`, String(Math.max(0, config.intervalSeconds)))
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
      setPendingDeletePlan(null)
      queryClient.invalidateQueries({ queryKey: ['management-plans'] })
    }
  })

  async function openEditor(planId: number | null) {
    setPendingDeletePlan(null)
    const data = await fetchJson<Record<string, unknown>>(
      `/api/react/management/plans/edit?${buildPlanEditorQuery(lang, planId)}`
    )
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
        intervalSeconds: Number.isFinite(intervalRaw) && intervalRaw >= 0 ? intervalRaw : 3600
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
  const totalRecords = toTotalCount(query.data?.total, items.length)
  const orderedTasks: string[] = taskOrder.length > 0 ? taskOrder : taskOptions
  const moveTaskOrder = useCallback((index: number, offset: -1 | 1) => {
    setTaskOrder((prev) => moveTaskOrderWithFallback(prev, orderedTasks, index, offset))
  }, [orderedTasks])

  return (
    <section className="section-stack">
      <div className="surface-card section-stack">
        <div className="section-title">{tr(t, 'menu_plans', 'Plans')}</div>
        <ManagementListToolbar
          spec={planListSpec}
          state={planListState}
          searchableLocale={searchableSelectLocale(t)}
          onFilterChange={setPlanFilter}
          onPageSizeChange={setPlanPageSize}
          t={t}
          actions={{
            trailing: (
              <Button type="button" size="sm" onClick={() => openEditor(null)}>
                {tr(t, 'btn_new_plan', 'New')}
              </Button>
            )
          }}
        />
        <InlineNotice notice={notice} />
        <QueryTotalSummary t={t} total={totalRecords} />
        {pendingDeletePlan && (
          <div className="surface-card section-stack">
            <div className="text-xs text-danger">
              {tr(t, 'confirm_delete_plan', "Delete plan '{name}'?").replace('{name}', pendingDeletePlan.name)}
            </div>
            <div className="filter-row">
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => deleteMutation.mutate(pendingDeletePlan.id)}
              >
                {tr(t, 'label_confirm', 'Confirm')}
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={() => setPendingDeletePlan(null)}>
                {tr(t, 'label_cancel', 'Cancel')}
              </Button>
            </div>
          </div>
        )}

        <div className="table-wrap">
          <table className="grid-table">
            <thead>
              <tr>
                <SortableHeaderCell
                  label={tr(t, 'col_id', 'ID')}
                  sortKey="id"
                  sortBy={planListState.sortBy}
                  sortOrder={planListState.sortOrder}
                  onToggle={cyclePlanSort}
                />
                <SortableHeaderCell
                  label={tr(t, 'col_name', 'Name')}
                  sortKey="name"
                  sortBy={planListState.sortBy}
                  sortOrder={planListState.sortOrder}
                  onToggle={cyclePlanSort}
                />
                <th>{tr(t, 'col_description', 'Description')}</th>
                <th>{tr(t, 'col_task', 'Task')}</th>
                <th>{tr(t, 'col_actions', 'Actions')}</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-center text-muted">{tr(t, 'label_no_data', 'No data')}</td>
                </tr>
              )}
              {items.map((item) => {
                const planId = Number(item.id)
                const planName = toText(item.name, t)
                const description = toText(item.description, t)
                const tasksLabel = taskTypesListLabel(t, item.task_types_list)
                return (
                  <tr key={planId}>
                    <td className="mono">{planId}</td>
                    <td>{planName}</td>
                    <td>
                      <TruncatedText text={description} />
                    </td>
                    <td>
                      <TruncatedText text={tasksLabel} />
                    </td>
                    <td>
                      <div className="filter-row">
                        <Button type="button" size="sm" variant="outline" onClick={() => openEditor(planId)}>
                          {tr(t, 'btn_edit', 'Edit')}
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => setPendingDeletePlan({ id: planId, name: planName })}
                        >
                          {tr(t, 'btn_delete', 'Delete')}
                        </Button>
                      </div>
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
          onPrev={() => setPlanPage(Math.max(planListState.page - 1, 0))}
          onNext={() => setPlanPage(planListState.page + 1)}
          t={t}
        />
      </div>

      {isPlanEditorOpen && (
        <div className="dialog-overlay" onClick={() => { setEditingPlanId(null); setIsPlanEditorOpen(false) }}>
          <div className="dialog-card dialog-card--lg section-stack plan-editor-dialog" onClick={(event) => event.stopPropagation()}>
            <div className="section-title">
              {editingPlanId ? `${tr(t, 'btn_edit', 'Edit')} #${editingPlanId}` : tr(t, 'modal_title_new_plan', 'New Plan')}
            </div>
            <label className="section-subtitle">{tr(t, 'label_name', 'Name')}</label>
            <input id="plan-name" className="field-input" name="plan-name" value={planName} onChange={(event) => setPlanName(event.target.value)} />
            <label className="section-subtitle">{tr(t, 'label_description', 'Description')}</label>
            <textarea id="plan-description" className="field-textarea" name="plan-description" value={planDesc} onChange={(event) => setPlanDesc(event.target.value)} />
            <label className="section-subtitle">{tr(t, 'label_task_config', 'Task Config')}</label>
            <div className="section-stack plan-editor-task-list">
              {orderedTasks.map((task, index) => {
                const config = taskConfigMap[task] ?? {
                  enabled: false,
                  resetType: 'default',
                  intervalSeconds: 3600
                }
                const intervalParts = splitIntervalSeconds(config.intervalSeconds)
                const isFirst = index === 0
                const isLast = index === orderedTasks.length - 1
                return (
                  <div
                    key={task}
                    className={`surface-card section-stack plan-editor-task-item ${dragOverTask === task ? 'is-drag-over' : ''} ${draggingTask === task ? 'is-dragging' : ''}`}
                    onDragOver={(event) => {
                      event.preventDefault()
                      const sourceTask = draggingTaskRef.current || event.dataTransfer.getData('text/plain') || draggingTask
                      if (sourceTask && sourceTask !== task && dragOverTask !== task) {
                        setDragOverTask(task)
                      }
                    }}
                    onDrop={(event) => {
                      event.preventDefault()
                      const sourceTask = draggingTaskRef.current || event.dataTransfer.getData('text/plain') || draggingTask
                      if (!sourceTask || sourceTask === task) {
                        draggingTaskRef.current = null
                        setDragOverTask(null)
                        setDraggingTask(null)
                        return
                      }
                      reorderTaskByDrag(sourceTask, task)
                      draggingTaskRef.current = null
                      setDraggingTask(null)
                      setDragOverTask(null)
                    }}
                  >
                    <div className="filter-row plan-editor-task-row">
                      <label className="filter-row plan-editor-task-main">
                        <input
                          id={`plan-task-enabled-${task}`}
                          type="checkbox"
                          name={`plan-task-enabled-${task}`}
                          checked={config.enabled}
                          onChange={(event) => {
                            const enabled = event.target.checked
                            setTaskConfigMap((prev) => ({
                              ...prev,
                              [task]: { ...config, enabled }
                            }))
                          }}
                        />
                        <span className="plan-editor-task-name">{taskTypeLabel(t, task)}</span>
                      </label>
                      <div className="plan-editor-task-actions">
                        <button
                          type="button"
                          className="plan-editor-drag-handle"
                          aria-label={tr(t, 'label_drag_reorder', '拖拽排序')}
                          draggable={orderedTasks.length > 1}
                          onDragStart={(event) => {
                            const taskItem = event.currentTarget.closest('.plan-editor-task-item')
                            if (taskItem instanceof HTMLElement) {
                              const rect = taskItem.getBoundingClientRect()
                              event.dataTransfer.setDragImage(taskItem, event.clientX - rect.left, event.clientY - rect.top)
                            }
                            draggingTaskRef.current = task
                            setDraggingTask(task)
                            setDragOverTask(null)
                            event.dataTransfer.effectAllowed = 'move'
                            event.dataTransfer.setData('text/plain', task)
                          }}
                          onDragEnd={() => {
                            draggingTaskRef.current = null
                            setDraggingTask(null)
                            setDragOverTask(null)
                          }}
                        >
                          ⋮⋮
                        </button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={isFirst}
                          onClick={() => moveTaskOrder(index, -1)}
                        >
                          ↑
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={isLast}
                          onClick={() => moveTaskOrder(index, 1)}
                        >
                          ↓
                        </Button>
                      </div>
                    </div>
                    <div className="filter-row plan-editor-config-row">
                      <Select
                        value={encodeSelectValue(config.resetType)}
                        onValueChange={(value) => {
                          const resetType = decodeSelectValue(value)
                          setTaskConfigMap((prev) => ({
                            ...prev,
                            [task]: { ...config, resetType }
                          }))
                        }}
                      >
                        <SelectTrigger className="field-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {resetTypeOptions.map((resetType) => (
                            <SelectItem key={resetType} value={resetType}>
                              {tr(t, `reset_type_${resetType}`, tr(t, 'label_unknown', 'Unknown'))}
                            </SelectItem>
                          ))}
                          {!resetTypeOptions.includes('default') && <SelectItem value="default">{tr(t, 'label_default', 'default')}</SelectItem>}
                        </SelectContent>
                      </Select>
                      {config.resetType === 'interval' && (
                        <div className="section-stack">
                          <div className="plan-editor-interval-grid">
                            {([
                              { key: 'days', label: tr(t, 'relative_days', 'day') },
                              { key: 'hours', label: tr(t, 'relative_hours', 'hr') },
                              { key: 'minutes', label: tr(t, 'relative_minutes', 'min') },
                              { key: 'seconds', label: tr(t, 'relative_seconds', 'sec') }
                            ] as Array<{ key: IntervalPartKey; label: string }>).map(({ key, label }) => (
                              <label key={`${task}-${key}`} className="plan-editor-interval-field" htmlFor={`plan-${task}-${key}`}>
                                <span className="section-subtitle">{label}</span>
                                <input
                                  id={`plan-${task}-${key}`}
                                  name={`plan-${task}-${key}`}
                                  className="field-input plan-editor-interval-input"
                                  type="number"
                                  min={0}
                                  value={intervalParts[key]}
                                  onChange={(event) => {
                                    setTaskConfigMap((prev) => ({
                                      ...prev,
                                      [task]: {
                                        ...config,
                                        intervalSeconds: updateIntervalPart(config.intervalSeconds, key, event.target.value)
                                      }
                                    }))
                                  }}
                                />
                              </label>
                            ))}
                          </div>
                          <div className="text-xs text-muted">{formatDurationExact(config.intervalSeconds)}</div>
                        </div>
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
                  const enabledOrderedTasks = orderedTasks.filter((task) => taskConfigMap[task]?.enabled)
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
  const resourceListSpec = useMemo<ManagementListSpec>(() => ({
    storageKey: 'resources',
    defaultPageSize: 20,
    pageSizeOptions: [10, 20, 50, 100],
    filters: [
      {
        key: 'view',
        kind: 'select',
        label: tr(t, 'label_view', 'View'),
        defaultValue: 'stats',
        includeEmpty: false,
        options: [
          { value: 'stats', label: tr(t, 'tab_resource_stats', 'Stats') },
          { value: 'pack-points', label: tr(t, 'tab_resource_pack_points', 'Pack Points') }
        ]
      },
      {
        key: 'q',
        kind: 'search',
        label: tr(t, 'label_search', 'Search'),
        placeholder: tr(t, 'filter_account_search_placeholder', 'Search account')
      }
    ],
    sort: {
      defaultBy: 'id',
      defaultOrder: 'asc',
      options: [
        { value: 'id', labelKey: 'col_id', fallback: 'ID' },
        { value: 'nickname', labelKey: 'col_nickname', fallback: 'Nickname' },
        { value: 'friend_id', labelKey: 'col_friend_id', fallback: 'Friend ID' }
      ]
    }
  }), [t])
  const [seriesList, setSeriesList] = useState<string[]>([])
  const resourceSortOptions = useMemo<SortOption[]>(() => {
    return [
      { value: 'id', labelKey: 'col_id', fallback: 'ID' },
      { value: 'nickname', labelKey: 'col_nickname', fallback: 'Nickname' },
      { value: 'friend_id', labelKey: 'col_friend_id', fallback: 'Friend ID' },
      { value: 'exchange_points', labelKey: 'col_exchange_points', fallback: 'Exchange Points' },
      { value: 'pack_hourglass_count', labelKey: 'col_pack_hourglass', fallback: 'Pack Hourglass' },
      { value: 'updated_at', labelKey: 'col_updated_at', fallback: 'Updated At' },
      ...seriesList.map((seriesCode) => ({
        value: `series:${seriesCode}`,
        labelKey: `series_sort_${seriesCode}`,
        fallback: `Series Points (${seriesCode})`
      }))
    ]
  }, [seriesList])
  const {
    state: resourceListState,
    setFilter: setResourceFilter,
    setSort: setResourceSort,
    cycleSort: cycleResourceSort,
    setPage: setResourcePage,
    setPageSize: setResourcePageSize
  } = useManagementListState(resourceListSpec, {
    sortOptions: resourceSortOptions
  })
  const resourceQueryParams = useMemo(
    () => buildManagementListQueryParams(resourceListSpec, resourceListState),
    [resourceListSpec, resourceListState]
  )
  const { query } = useManagementListQuery<Record<string, unknown>>({
    queryKey: 'management-resources',
    endpoint: 'resources',
    lang,
    params: resourceQueryParams
  })
  const items = ((query.data?.items as unknown[]) ?? []) as Record<string, unknown>[]
  useEffect(() => {
    setSeriesList((((query.data?.series_list as unknown[]) ?? []) as string[]))
  }, [query.data?.series_list])
  const view = resourceListState.filters.view || 'stats'
  useEffect(() => {
    const statsSortFields = new Set(['id', 'nickname', 'friend_id', 'exchange_points', 'pack_hourglass_count', 'updated_at'])
    const packPointSortFields = new Set(['id', 'nickname', 'friend_id'])
    const isSeriesSort = resourceListState.sortBy.startsWith('series:')
    if (view === 'stats' && (isSeriesSort || !statsSortFields.has(resourceListState.sortBy))) {
      setResourceSort('id', 'asc')
      return
    }
    if (view === 'pack-points' && !isSeriesSort && !packPointSortFields.has(resourceListState.sortBy)) {
      setResourceSort('id', 'asc')
    }
  }, [resourceListState.sortBy, setResourceSort, view])
  const accountNumber = new Intl.NumberFormat('en-US')

  return (
    <section className="surface-card section-stack">
      <div className="section-title">{tr(t, 'menu_resources', 'Resources')}</div>
      <ManagementListToolbar
        spec={resourceListSpec}
        state={resourceListState}
        searchableLocale={searchableSelectLocale(t)}
        onFilterChange={setResourceFilter}
        onPageSizeChange={setResourcePageSize}
        t={t}
      />

      {view === 'stats' ? (
        <div className="table-wrap">
          <table className="grid-table">
            <thead>
              <tr>
                <SortableHeaderCell
                  label={tr(t, 'col_account', 'Account')}
                  sortKey="id"
                  sortBy={resourceListState.sortBy}
                  sortOrder={resourceListState.sortOrder}
                  onToggle={cycleResourceSort}
                />
                <SortableHeaderCell
                  label={tr(t, 'col_exchange_points', 'Exchange Points')}
                  sortKey="exchange_points"
                  sortBy={resourceListState.sortBy}
                  sortOrder={resourceListState.sortOrder}
                  onToggle={cycleResourceSort}
                />
                <SortableHeaderCell
                  label={tr(t, 'col_pack_hourglass', 'Pack Hourglass')}
                  sortKey="pack_hourglass_count"
                  sortBy={resourceListState.sortBy}
                  sortOrder={resourceListState.sortOrder}
                  onToggle={cycleResourceSort}
                />
                <SortableHeaderCell
                  label={tr(t, 'col_updated_at', 'Updated At')}
                  sortKey="updated_at"
                  sortBy={resourceListState.sortBy}
                  sortOrder={resourceListState.sortOrder}
                  onToggle={cycleResourceSort}
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
                const exchangePoints = Number(row.exchange_points)
                const hourglass = Number(row.pack_hourglass_count)
                return (
                  <tr key={`resource-stats-${accountId}`}>
                    <td>
                      <AccountIdentityCell
                        t={t}
                        accountId={row.account_id}
                        name={row.nickname}
                        friendId={row.friend_id}
                        gameId={row.game_id}
                      />
                    </td>
                    <td className="mono">
                      {Number.isFinite(exchangePoints) ? accountNumber.format(exchangePoints) : '-'}
                    </td>
                    <td className="mono">
                      {Number.isFinite(hourglass) ? accountNumber.format(hourglass) : '-'}
                    </td>
                    <td className="mono">{renderRelativeTime(row.updated_at, lang, t)}</td>
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
                  sortBy={resourceListState.sortBy}
                  sortOrder={resourceListState.sortOrder}
                  onToggle={cycleResourceSort}
                />
                {seriesList.map((series) => (
                  <SortableHeaderCell
                    key={`series-header-${series}`}
                    label={series}
                    sortKey={`series:${series}`}
                    sortBy={resourceListState.sortBy}
                    sortOrder={resourceListState.sortOrder}
                    onToggle={cycleResourceSort}
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
                const seriesPoints = ((row.series_points as Record<string, unknown> | undefined) ?? {})
                return (
                  <tr key={`resource-points-${accountId}`}>
                    <td>
                      <AccountIdentityCell
                        t={t}
                        accountId={row.account_id}
                        name={row.nickname}
                        friendId={row.friend_id}
                        gameId={row.game_id}
                      />
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
        onPrev={() => setResourcePage(Math.max(resourceListState.page - 1, 0))}
        onNext={() => setResourcePage(resourceListState.page + 1)}
        t={t}
      />
    </section>
  )
}

function TasksSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const queryClient = useQueryClient()
  const [notice, setNotice] = useState<InlineNoticeState | null>(null)
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const taskListSpec = useMemo<ManagementListSpec>(() => ({
    storageKey: 'tasks',
    defaultPageSize: 20,
    pageSizeOptions: [10, 20, 50, 100],
    filters: [
      {
        key: 'status',
        kind: 'select',
        label: tr(t, 'filter_status', 'Status'),
        emptyLabel: tr(t, 'label_all', 'All'),
        optionsKey: 'status'
      },
      {
        key: 'task_type',
        kind: 'select',
        label: tr(t, 'filter_task', 'Task'),
        emptyLabel: tr(t, 'label_all', 'All'),
        optionsKey: 'task_type'
      },
      {
        key: 'account_keyword',
        kind: 'text',
        label: tr(t, 'filter_account', 'Account'),
        placeholder: tr(t, 'filter_account_id_placeholder', 'Account ID / nickname / friend id'),
        datalistKey: 'account_keyword'
      }
    ],
    sort: {
      defaultBy: 'dispatch_priority',
      defaultOrder: 'asc',
      options: [
        { value: 'dispatch_priority', labelKey: 'col_dispatch_priority', fallback: 'Dispatch Priority' },
        { value: 'last_completed_at', labelKey: 'col_last_completed', fallback: 'Last Completed' },
        { value: 'last_duration_seconds', labelKey: 'col_last_duration', fallback: 'Last Duration' },
        { value: 'next_run_at', labelKey: 'col_next_run', fallback: 'Next Run' }
      ],
      lockedOrderBy: {
        dispatch_priority: 'asc'
      }
    }
  }), [t])
  const {
    state: taskListState,
    setFilter: setTaskFilter,
    cycleSort: cycleTaskSort,
    setPage: setTaskPage,
    setPageSize: setTaskPageSize
  } = useManagementListState(taskListSpec)
  const status = taskListState.filters.status ?? ''
  const taskType = taskListState.filters.task_type ?? ''
  const accountKeyword = taskListState.filters.account_keyword ?? ''

  const normalizedAccountKeyword = accountKeyword.trim()
  const { selectedAccountId, selectedAccountQuery } = resolveManagementTaskAccountFilter(accountKeyword)

  const accountOptionsQuery = useQuery({
    queryKey: ['management-task-account-options', normalizedAccountKeyword],
    queryFn: () =>
      fetchJson<{ accounts: Array<Record<string, unknown>> }>(
        `/api/react/management/tasks/account-options?${buildTaskAccountOptionsQuery(accountKeyword)}`
      ),
    enabled: normalizedAccountKeyword.length > 0
  })

  const taskQueryParams = useMemo(
    () => ({
      ...buildManagementListQueryParams(taskListSpec, taskListState),
      status: status || undefined,
      task_type: taskType || undefined,
      account_id: selectedAccountId || undefined,
      account_q: selectedAccountQuery || undefined
    }),
    [selectedAccountId, selectedAccountQuery, status, taskListSpec, taskListState, taskType]
  )
  const { query } = useManagementListQuery<Record<string, unknown>>({
    queryKey: 'management-tasks',
    endpoint: 'tasks',
    lang,
    params: taskQueryParams
  })

  const resetMutation = useMutation({
    mutationFn: () =>
      requestJson<{ ok: boolean; message: string }>('/api/react/management/tasks/reset-completed', {
        method: 'POST',
        body: buildResetCompletedTasksPayload({
          status,
          taskType,
          accountKeyword
        })
      }),
    onSuccess: (result) => {
      setNotice({ level: result.ok ? 'success' : 'error', text: result.message })
      setShowResetConfirm(false)
      queryClient.invalidateQueries({ queryKey: ['management-tasks'] })
    }
  })

  const rows = ((query.data?.items as unknown[]) ?? []) as Record<string, unknown>[]
  const accountIdsForPacks = useMemo(() => {
    const ids = new Set<string>()
    for (const row of rows) {
      if (row.task_type === 'open_pack' && Boolean(row.target_pack_auto) && !row.target_pack_label) {
        const id = String(row.account_id ?? '')
        if (id) ids.add(id)
      }
    }
    return [...ids].join(',')
  }, [rows])

  const packsQuery = useQuery({
    queryKey: ['management-task-packs', accountIdsForPacks],
    queryFn: () =>
      fetchJson<{ packs: Record<string, unknown> }>(
        `/api/react/management/accounts/packs?account_ids=${accountIdsForPacks}`
      ),
    enabled: accountIdsForPacks.length > 0
  })

  const statusOptions = getManagementFilterOptions<string>(query.data, 'status', ['status_options'])
  const taskTypeOptions = getManagementFilterOptions<string>(query.data, 'task_type', ['task_types'])
  const accountOptions = ((accountOptionsQuery.data?.accounts as unknown[]) ?? []) as Record<string, unknown>[]
  const totalRecords = toTotalCount(query.data?.total, rows.length)
  const taskToolbarOptions = useMemo<Record<string, string[] | ManagementListOption[]>>(
    () => ({
      status: statusOptions.map((value) => ({ value, label: statusLabel(t, value) })),
      task_type: taskTypeOptions.map((value) => ({ value, label: taskTypeLabel(t, value) })),
      account_keyword: accountOptions.map((item) => {
        const id = toText(item.id, t)
        const displayName = toText(item.display_name || item.nickname, t)
        const friendId = toText(item.friend_id, t)
        return `${id} ${displayName} (${friendId})`
      })
    }),
    [accountOptions, statusOptions, t, taskTypeOptions]
  )

  return (
    <section className="surface-card section-stack">
      <div className="section-title">{tr(t, 'menu_tasks', 'Tasks')}</div>
      <ManagementListToolbar
        spec={taskListSpec}
        state={taskListState}
        dynamicOptions={taskToolbarOptions}
        searchableLocale={searchableSelectLocale(t)}
        onFilterChange={setTaskFilter}
        onPageSizeChange={setTaskPageSize}
        t={t}
        actions={{
          trailing: (
            <Button
              size="sm"
              type="button"
              onClick={() => setShowResetConfirm((previous) => !previous)}
            >
              {tr(t, 'btn_reset_completed', 'Reset Completed')}
            </Button>
          )
        }}
      />
      {showResetConfirm && (
        <div className="surface-card section-stack">
          <div className="text-xs text-danger">
            {tr(
              t,
              'desc_reset_completed_warning',
              'This action will reset completed tasks to pending based on current filters.'
            )}
          </div>
          <div className="text-xs text-muted">
            {tr(
              t,
              'desc_reset_completed_ignore_init',
              'Init account tasks are always ignored.'
            )}
          </div>
          <div className="filter-row">
            <Button type="button" size="sm" variant="outline" onClick={() => resetMutation.mutate()}>
              {tr(t, 'label_confirm', 'Confirm')}
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={() => setShowResetConfirm(false)}>
              {tr(t, 'label_cancel', 'Cancel')}
            </Button>
          </div>
        </div>
      )}
      <InlineNotice notice={notice} />
      <QueryTotalSummary t={t} total={totalRecords} />

      <ManagementDataGrid
        rows={rows}
        columns={buildTaskTableColumns({ lang, t, packs: packsQuery.data?.packs ?? {} })}
        t={t}
        sortBy={taskListState.sortBy}
        sortOrder={taskListState.sortOrder}
        onSortChange={cycleTaskSort}
      />

      <Pager
        page={Number(query.data?.page ?? 0)}
        hasPrev={Boolean(query.data?.has_prev)}
        hasNext={Boolean(query.data?.has_next)}
        onPrev={() => setTaskPage(Math.max(taskListState.page - 1, 0))}
        onNext={() => setTaskPage(taskListState.page + 1)}
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
  const metadataRequestContext = useMemo(
    () =>
      buildMetadataRequestContext({
        nodeType: selectedNodeType,
        nodeId: selectedNodeId,
        setCode: selectedSetCode,
        packName: selectedPackName,
        action: currentAction,
        snapshotId
      }),
    [currentAction, selectedNodeId, selectedNodeType, selectedPackName, selectedSetCode, snapshotId]
  )

  const queryString = useMemo(
    () =>
      buildMetadataQueryString({
        lang,
        uiStep,
        nodeType: selectedNodeType,
        nodeId: selectedNodeId,
        setCode: selectedSetCode,
        packName: selectedPackName,
        action: currentAction,
        snapshotId
      }),
    [lang, metadataRequestContext, uiStep]
  )

  const query = useQuery({
    queryKey: ['management-metadata', queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/metadata?${queryString}`),
    placeholderData: (previous) => previous
  })

  const previewMutation = useMutation({
    mutationFn: (action: string) =>
      requestJson<Record<string, unknown>>('/api/react/management/metadata/preview', {
        method: 'POST',
        body: buildMetadataPreviewPayload({
          action,
          nodeType: metadataRequestContext.selected_node_type,
          nodeId: metadataRequestContext.selected_node_id,
          forceRefresh,
          snapshotId: metadataRequestContext.snapshot_id
        })
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
        body: buildMetadataExecutePayload(metadataRequestContext.snapshot_id ?? '')
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
                id="metadata-force-refresh"
                type="checkbox"
                name="metadata-force-refresh"
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
  const [date, setDate] = useState<string>(() => currentGameBizDate())
  const [selectedAccountIdState, setSelectedAccountIdState] = usePersistedState<string>(
    managementStateKey('daily-gift', 'account_id'),
    ''
  )
  const selectLocale = useMemo(() => searchableSelectLocale(t), [t])
  const datePickerText = useMemo(() => datePickerLocale(t), [t])
  const dailyGiftRecordSpec = useMemo<ManagementListSpec>(() => ({
    storageKey: 'daily-gift-records',
    defaultPageSize: 10,
    pageSizeOptions: [10, 20, 50, 100],
    sort: {
      defaultBy: 'updated_at',
      defaultOrder: 'desc',
      options: [
        { value: 'updated_at', labelKey: 'col_updated_at', fallback: 'Updated At' },
        { value: 'account_id', labelKey: 'col_account_id', fallback: 'Account ID' },
        { value: 'status', labelKey: 'col_status', fallback: 'Status' }
      ]
    }
  }), [t])
  const dailyGiftPairSpec = useMemo<ManagementListSpec>(() => ({
    storageKey: 'daily-gift-pairs',
    defaultPageSize: 10,
    pageSizeOptions: [10, 20, 50, 100],
    queryKeys: {
      page: 'pair_page',
      pageSize: 'pair_page_size'
    }
  }), [])
  const {
    state: dailyGiftRecordState,
    cycleSort: cycleDailyGiftRecordSort,
    setPage: setDailyGiftRecordPage,
    setPageSize: setDailyGiftRecordPageSize
  } = useManagementListState(dailyGiftRecordSpec)
  const {
    state: dailyGiftPairState,
    setPage: setDailyGiftPairPage,
    setPageSize: setDailyGiftPairPageSize
  } = useManagementListState(dailyGiftPairSpec)
  const queryParams = useMemo(
    () => ({
      ...buildManagementListQueryParams(dailyGiftRecordSpec, dailyGiftRecordState, {
        biz_date_local: date || undefined,
        account_id: selectedAccountIdState || undefined
      }),
      ...buildManagementListQueryParams(dailyGiftPairSpec, dailyGiftPairState)
    }),
    [
      dailyGiftPairSpec,
      dailyGiftPairState,
      dailyGiftRecordSpec,
      dailyGiftRecordState,
      date,
      selectedAccountIdState
    ]
  )
  const { query } = useManagementListQuery<Record<string, unknown>>({
    queryKey: 'management-daily-gift',
    endpoint: 'daily-gift',
    lang,
    params: queryParams
  })

  const records = ((query.data?.records as unknown[]) ?? []) as Record<string, unknown>[]
  const pairs = ((query.data?.pair_send_status_rows as unknown[]) ?? []) as Record<string, unknown>[]
  const stats = (query.data?.stats as Record<string, unknown> | undefined) ?? {}
  const totalRecords = toTotalCount(query.data?.records_total, records.length)
  const accounts = (((query.data?.accounts as unknown[]) ?? []) as Record<string, unknown>[])
  const accountNameMap = (query.data?.account_name_map as Record<string, string> | undefined) ?? {}
  const selectedAccountId = toText(query.data?.selected_account_id, t) === '-' ? '' : toText(query.data?.selected_account_id, t)
  const currentBizDateLocal = toText(query.data?.current_biz_date_local, t) === '-' ? '' : toText(query.data?.current_biz_date_local, t)
  const recentBizDates = buildRecentBizDates(currentBizDateLocal || currentGameBizDate())
  const accountOptions = useMemo(
    () => buildAccountSelectOptions(accounts, t, tr(t, 'label_all_accounts', 'All Accounts')),
    [accounts, t]
  )
  const accountMetaMap = useMemo(() => {
    const map: Record<string, Record<string, unknown>> = {}
    for (const account of accounts) {
      const key = toText(account.id, t)
      if (key !== '-') {
        map[key] = account
      }
    }
    return map
  }, [accounts, t])

  useEffect(() => {
    if (selectedAccountId !== selectedAccountIdState) {
      setSelectedAccountIdState(selectedAccountId)
    }
  }, [selectedAccountId, selectedAccountIdState, setSelectedAccountIdState])

  return (
    <section className="surface-card section-stack">
      <div className="pagination-row">
        <div className="section-title">{tr(t, 'menu_daily_gift', 'Daily Gift')}</div>
        <div className="filter-row">
          <DatePicker
            value={date}
            onChange={(value) => {
              setDate(value)
              setDailyGiftRecordPage(0)
              setDailyGiftPairPage(0)
            }}
            placeholder={tr(t, 'date_label', 'Date')}
            todayValue={currentBizDateLocal || currentGameBizDate()}
            i18n={datePickerText}
          />
          <div className="table-filter-item">
            <label className="section-subtitle">{tr(t, 'col_account', 'Account')}</label>
            <SearchableSelect
              value={selectedAccountIdState}
              options={accountOptions}
              onValueChange={(value) => {
                setSelectedAccountIdState(value)
                setDailyGiftRecordPage(0)
                setDailyGiftPairPage(0)
              }}
              {...selectLocale}
              placeholder={tr(t, 'label_all_accounts', 'All Accounts')}
              pageSize={12}
              className="management-inline-select"
            />
          </div>
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
                setDailyGiftRecordPage(0)
                setDailyGiftPairPage(0)
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

      <ManagementListToolbar
        spec={dailyGiftRecordSpec}
        state={dailyGiftRecordState}
        searchableLocale={selectLocale}
        onFilterChange={() => {}}
        onPageSizeChange={setDailyGiftRecordPageSize}
        t={t}
      />
      <QueryTotalSummary t={t} total={totalRecords} />

      <div className="section-subtitle">{tr(t, 'section_daily_gift_records', 'Gift Records')}</div>
      <div className="table-wrap">
        <table className="grid-table">
          <thead>
            <tr>
              <th>{tr(t, 'col_id', 'ID')}</th>
              <SortableHeaderCell
                label={tr(t, 'col_account', 'Account')}
                sortKey="account_id"
                sortBy={dailyGiftRecordState.sortBy}
                sortOrder={dailyGiftRecordState.sortOrder}
                onToggle={cycleDailyGiftRecordSort}
              />
              <th>{tr(t, 'col_friend_id', 'Friend ID')}</th>
              <th>{tr(t, 'col_card', 'Card')}</th>
              <SortableHeaderCell
                label={tr(t, 'col_status', 'Status')}
                sortKey="status"
                sortBy={dailyGiftRecordState.sortBy}
                sortOrder={dailyGiftRecordState.sortOrder}
                onToggle={cycleDailyGiftRecordSort}
              />
              <th>{tr(t, 'col_count_change', 'Count Change')}</th>
              <SortableHeaderCell
                label={tr(t, 'time_label', 'Time')}
                sortKey="updated_at"
                sortBy={dailyGiftRecordState.sortBy}
                sortOrder={dailyGiftRecordState.sortOrder}
                onToggle={cycleDailyGiftRecordSort}
              />
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
                    <AccountIdentityCell
                      t={t}
                      accountId={accountIdRow}
                      name={row.account_name}
                      friendId={accountMetaMap[String(accountIdRow)]?.friend_id}
                      gameId={accountMetaMap[String(accountIdRow)]?.game_id}
                    />
                  </td>
                  <td>
                    <CopyableFriendId t={t} value={toText(row.target_friend_id, t)} />
                    {Number.isFinite(targetAccountId) && targetAccountId > 0 && (
                      <div className="text-xs text-muted">#{targetAccountId} {accountNameMap[String(targetAccountId)] ?? toText(row.target_name, t)}</div>
                    )}
                  </td>
                  <td className="mono">{toText(row.card_label, t)}</td>
                  <td>
                    {renderStatusBadgeWithReason(
                      giftStatusLabel(t, row.status),
                      statusBadgeVariant(row.status),
                      row.error_message
                    )}
                  </td>
                  <td className="mono">
                    {Number.isFinite(beforeCount) ? String(beforeCount) : '-'}
                    {' -> '}
                    {Number.isFinite(afterCount) ? String(afterCount) : '-'}
                  </td>
                  <td className="mono">{renderRelativeTime(row.updated_at, lang, t)}</td>
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
        onPrev={() => setDailyGiftRecordPage(Math.max(dailyGiftRecordState.page - 1, 0))}
        onNext={() => setDailyGiftRecordPage(dailyGiftRecordState.page + 1)}
        t={t}
      />

      <div className="section-subtitle">{tr(t, 'section_daily_gift_pair_progress', 'Pair Send Progress')}</div>
      <ManagementListToolbar
        spec={dailyGiftPairSpec}
        state={dailyGiftPairState}
        searchableLocale={selectLocale}
        onFilterChange={() => {}}
        onPageSizeChange={setDailyGiftPairPageSize}
        t={t}
      />
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
                <td>{renderBadge(giftStatusLabel(t, row.left_to_right_status), statusBadgeVariant(row.left_to_right_status))}</td>
                <td>{renderBadge(giftStatusLabel(t, row.right_to_left_status), statusBadgeVariant(row.right_to_left_status))}</td>
                <td>{renderBadge(pairProgressLabel(t, row.pair_progress), statusBadgeVariant(row.pair_progress))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager
        page={Number(query.data?.pair_page ?? 0)}
        hasPrev={Boolean(query.data?.pair_has_prev)}
        hasNext={Boolean(query.data?.pair_has_next)}
        onPrev={() => setDailyGiftPairPage(Math.max(dailyGiftPairState.page - 1, 0))}
        onNext={() => setDailyGiftPairPage(dailyGiftPairState.page + 1)}
        t={t}
      />
    </section>
  )
}
function FriendshipsSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const queryClient = useQueryClient()
  const [q, setQ] = usePersistedState<string>(managementStateKey('friendships', 'q'), '')
  const [accountId, setAccountId] = usePersistedState<string>(managementStateKey('friendships', 'account_id'), '')
  const [fromAccountId, setFromAccountId] = usePersistedState<string>(managementStateKey('friendships', 'from_account_id'), '')
  const [targetAccountId, setTargetAccountId] = useState('')
  const [friendIdInput, setFriendIdInput] = useState('')
  const [notice, setNotice] = useState<InlineNoticeState | null>(null)
  const selectLocale = useMemo(() => searchableSelectLocale(t), [t])
  const requestListSpec = useMemo<ManagementListSpec>(() => ({
    storageKey: 'friendships-requests',
    defaultPageSize: 10,
    pageSizeOptions: [10, 20, 50, 100],
    queryKeys: {
      page: 'request_page',
      pageSize: 'request_page_size',
      sortBy: 'request_sort_by',
      sortOrder: 'request_sort_order'
    },
    sort: {
      defaultBy: 'created_at',
      defaultOrder: 'desc',
      options: [
        { value: 'created_at', labelKey: 'label_created_time', fallback: 'Created At' },
        { value: 'from_account_id', labelKey: 'label_from_account', fallback: 'From Account' },
        { value: 'to_friend_id', labelKey: 'col_friend_id', fallback: 'Friend ID' },
        { value: 'status', labelKey: 'col_status', fallback: 'Status' }
      ]
    }
  }), [t])
  const friendshipListSpec = useMemo<ManagementListSpec>(() => ({
    storageKey: 'friendships-list',
    defaultPageSize: 10,
    pageSizeOptions: [10, 20, 50, 100],
    queryKeys: {
      page: 'friendship_page',
      pageSize: 'friendship_page_size',
      sortBy: 'friendship_sort_by',
      sortOrder: 'friendship_sort_order'
    },
    sort: {
      defaultBy: 'created_at',
      defaultOrder: 'desc',
      options: [
        { value: 'created_at', labelKey: 'label_created_time', fallback: 'Created At' },
        { value: 'account_id', labelKey: 'col_account_id', fallback: 'Account ID' },
        { value: 'friend_id', labelKey: 'col_friend_id', fallback: 'Friend ID' }
      ]
    }
  }), [t])
  const {
    state: requestListState,
    cycleSort: cycleRequestSort,
    setPage: setRequestPage,
    setPageSize: setRequestPageSize
  } = useManagementListState(requestListSpec)
  const {
    state: friendshipListState,
    cycleSort: cycleFriendshipSort,
    setPage: setFriendshipPage,
    setPageSize: setFriendshipPageSize
  } = useManagementListState(friendshipListSpec)

  const friendshipQueryParams = useMemo(
    () => ({
      q,
      account_id: accountId || undefined,
      from_account_id: fromAccountId || undefined,
      ...buildManagementListQueryParams(requestListSpec, requestListState),
      ...buildManagementListQueryParams(friendshipListSpec, friendshipListState)
    }),
    [accountId, friendshipListSpec, friendshipListState, fromAccountId, q, requestListSpec, requestListState]
  )
  const { query } = useManagementListQuery<Record<string, unknown>>({
    queryKey: 'management-friendships',
    endpoint: 'friendships',
    lang,
    params: friendshipQueryParams
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
  const requestsTotal = toTotalCount(query.data?.request_total, requests.length)
  const friendshipsTotal = toTotalCount(query.data?.friendship_total, friendships.length)
  const accounts = (((query.data?.accounts as unknown[]) ?? []) as Record<string, unknown>[])
  const accountNameMap = (query.data?.account_name_map as Record<string, string> | undefined) ?? {}
  const allAccountOptions = useMemo(
    () => buildAccountSelectOptions(accounts, t, tr(t, 'label_all_accounts', 'All Accounts')),
    [accounts, t]
  )
  const fromAccountOptions = useMemo(
    () => buildAccountSelectOptions(accounts, t, tr(t, 'label_from_account', 'From Account')),
    [accounts, t]
  )
  const targetAccountOptions = useMemo(
    () => buildAccountSelectOptions(accounts, t, tr(t, 'label_target_account_optional', 'Target Account (optional)')),
    [accounts, t]
  )
  const accountMetaMap = useMemo(() => {
    const map: Record<string, Record<string, unknown>> = {}
    for (const account of accounts) {
      const key = toText(account.id, t)
      if (key !== '-') {
        map[key] = account
      }
    }
    return map
  }, [accounts, t])

  return (
    <section className="surface-card section-stack">
      <div className="section-title">{tr(t, 'menu_friendships', 'Friendships')}</div>
      <div className="form-grid">
        <input
          id="friendships-search"
          className="field-input"
          name="friendships-search"
          value={q}
          onChange={(event) => {
            setQ(event.target.value)
            setRequestPage(0)
            setFriendshipPage(0)
          }}
          placeholder={tr(t, 'label_search', 'Search')}
        />
        <SearchableSelect
          value={accountId}
          options={allAccountOptions}
          onValueChange={(value) => {
            setAccountId(value)
            setRequestPage(0)
            setFriendshipPage(0)
          }}
          {...selectLocale}
          placeholder={tr(t, 'label_all_accounts', 'All Accounts')}
          pageSize={12}
        />
        <SearchableSelect
          value={fromAccountId}
          options={fromAccountOptions}
          onValueChange={(value) => {
            setFromAccountId(value)
            setRequestPage(0)
          }}
          {...selectLocale}
          placeholder={tr(t, 'label_from_account', 'From Account')}
          pageSize={12}
        />
        <SearchableSelect
          value={targetAccountId}
          options={targetAccountOptions}
          onValueChange={setTargetAccountId}
          {...selectLocale}
          placeholder={tr(t, 'label_target_account_optional', 'Target Account (optional)')}
          pageSize={12}
        />
        <input
          id="friendships-target-friend-id"
          className="field-input"
          name="friendships-target-friend-id"
          value={friendIdInput}
          onChange={(event) => setFriendIdInput(event.target.value)}
          placeholder={tr(t, 'placeholder_friend_id', 'Friend ID (optional)')}
        />
      </div>
      <div className="filter-row">
        <Button type="button" size="sm" onClick={() => addMutation.mutate()}>{tr(t, 'btn_create_add_request', 'Create Add Request')}</Button>
        <Button type="button" size="sm" variant="outline" onClick={() => deleteMutation.mutate(undefined)}>{tr(t, 'btn_create_delete_request', 'Create Delete Request')}</Button>
      </div>
      <InlineNotice notice={notice} />
      <div className="section-stack">
        <QueryTotalSummary t={t} total={requestsTotal} label={tr(t, 'section_friend_requests', 'Requests')} />
        <QueryTotalSummary t={t} total={friendshipsTotal} label={tr(t, 'section_friendships', 'Friendships')} />
      </div>

      <div className="section-subtitle">{tr(t, 'section_friend_requests', 'Requests')}</div>
      <ManagementListToolbar
        spec={requestListSpec}
        state={requestListState}
        dynamicOptions={{}}
        searchableLocale={selectLocale}
        onFilterChange={() => {}}
        onPageSizeChange={setRequestPageSize}
        t={t}
      />
      <div className="table-wrap">
        <table className="grid-table">
          <thead>
            <tr>
              <th>{tr(t, 'col_id', 'ID')}</th>
              <SortableHeaderCell
                label={tr(t, 'label_from_account', 'From Account')}
                sortKey="from_account_id"
                sortBy={requestListState.sortBy}
                sortOrder={requestListState.sortOrder}
                onToggle={cycleRequestSort}
              />
              <SortableHeaderCell
                label={tr(t, 'col_friend_id', 'Friend ID')}
                sortKey="to_friend_id"
                sortBy={requestListState.sortBy}
                sortOrder={requestListState.sortOrder}
                onToggle={cycleRequestSort}
              />
              <th>{tr(t, 'col_type', 'Type')}</th>
              <SortableHeaderCell
                label={tr(t, 'col_status', 'Status')}
                sortKey="status"
                sortBy={requestListState.sortBy}
                sortOrder={requestListState.sortOrder}
                onToggle={cycleRequestSort}
              />
              <SortableHeaderCell
                label={tr(t, 'label_created_time', 'Created')}
                sortKey="created_at"
                sortBy={requestListState.sortBy}
                sortOrder={requestListState.sortOrder}
                onToggle={cycleRequestSort}
              />
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
                    <AccountIdentityCell
                      t={t}
                      accountId={fromId}
                      name={accountNameMap[fromId] ?? fromId}
                      friendId={accountMetaMap[fromId]?.friend_id}
                      gameId={accountMetaMap[fromId]?.game_id}
                    />
                  </td>
                  <td>
                    <CopyableFriendId t={t} value={toText(row.to_friend_id, t)} />
                    {toId !== '-' && <div className="text-xs text-muted">#{toId}</div>}
                  </td>
                  <td>{requestTypeLabel(t, row.request_type)}</td>
                  <td>{renderBadge(requestStatusLabel(t, row.status), statusBadgeVariant(row.status))}</td>
                  <td className="mono">{renderRelativeTime(row.created_at, lang, t)}</td>
                  <td>
                    {canCancel ? (
                      <Button type="button" size="sm" variant="outline" onClick={() => cancelMutation.mutate(Number(row.id))}>
                        {tr(t, 'btn_remove_request', 'Delete Request')}
                      </Button>
                    ) : (
                      <Tooltip content={reasonTitle(requestCancelDisabledReason(t, row.status)) ?? ''}>
                        <Button type="button" size="sm" variant="outline" disabled>
                          {tr(t, 'btn_remove_request', 'Delete Request')}
                        </Button>
                      </Tooltip>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <Pager
        page={Number(query.data?.request_page ?? 0)}
        hasPrev={Boolean(query.data?.request_has_prev)}
        hasNext={Boolean(query.data?.request_has_next)}
        onPrev={() => setRequestPage(Math.max(requestListState.page - 1, 0))}
        onNext={() => setRequestPage(requestListState.page + 1)}
        t={t}
      />

      <div className="section-subtitle">{tr(t, 'section_friendships', 'Friendships')}</div>
      <ManagementListToolbar
        spec={friendshipListSpec}
        state={friendshipListState}
        dynamicOptions={{}}
        searchableLocale={selectLocale}
        onFilterChange={() => {}}
        onPageSizeChange={setFriendshipPageSize}
        t={t}
      />
      <div className="table-wrap">
        <table className="grid-table">
          <thead>
            <tr>
              <th>{tr(t, 'col_id', 'ID')}</th>
              <SortableHeaderCell
                label={tr(t, 'col_account_id', 'Account ID')}
                sortKey="account_id"
                sortBy={friendshipListState.sortBy}
                sortOrder={friendshipListState.sortOrder}
                onToggle={cycleFriendshipSort}
              />
              <SortableHeaderCell
                label={tr(t, 'col_friend_id', 'Friend ID')}
                sortKey="friend_id"
                sortBy={friendshipListState.sortBy}
                sortOrder={friendshipListState.sortOrder}
                onToggle={cycleFriendshipSort}
              />
              <SortableHeaderCell
                label={tr(t, 'label_created_time', 'Created')}
                sortKey="created_at"
                sortBy={friendshipListState.sortBy}
                sortOrder={friendshipListState.sortOrder}
                onToggle={cycleFriendshipSort}
              />
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
                    <AccountIdentityCell
                      t={t}
                      accountId={rowAccountId}
                      name={accountNameMap[String(rowAccountId)] ?? rowAccountId}
                      friendId={accountMetaMap[String(rowAccountId)]?.friend_id}
                      gameId={accountMetaMap[String(rowAccountId)]?.game_id}
                    />
                  </td>
                  <td>
                    <CopyableFriendId t={t} value={rowFriendId} />
                    {Number.isFinite(rowFriendAccountId) && rowFriendAccountId > 0 && (
                      <div className="text-xs text-muted">#{rowFriendAccountId} {accountNameMap[String(rowFriendAccountId)] ?? ''}</div>
                    )}
                  </td>
                  <td className="mono">{renderRelativeTime(row.created_at, lang, t)}</td>
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
        page={Number(query.data?.friendship_page ?? 0)}
        hasPrev={Boolean(query.data?.friendship_has_prev)}
        hasNext={Boolean(query.data?.friendship_has_next)}
        onPrev={() => setFriendshipPage(Math.max(friendshipListState.page - 1, 0))}
        onNext={() => setFriendshipPage(friendshipListState.page + 1)}
        t={t}
      />
    </section>
  )
}
function ExchangeCardsSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const queryClient = useQueryClient()
  const [notice, setNotice] = useState<InlineNoticeState | null>(null)
  const selectLocale = useMemo(() => searchableSelectLocale(t), [t])
  const exchangeListSpec = useMemo<ManagementListSpec>(() => ({
    storageKey: 'exchange-cards',
    defaultPageSize: 10,
    pageSizeOptions: [10, 20, 50, 100],
    filters: [
      {
        key: 'q',
        kind: 'search',
        label: tr(t, 'label_search', 'Search'),
        placeholder: tr(t, 'label_search', 'Search')
      },
      {
        key: 'account_id',
        kind: 'account-select',
        label: tr(t, 'col_account_id', 'Account ID'),
        placeholder: tr(t, 'label_all_accounts', 'All Accounts'),
        optionsKey: 'account_id'
      },
      {
        key: 'status',
        kind: 'select',
        label: tr(t, 'filter_status', 'Status'),
        emptyLabel: tr(t, 'label_all_status', 'All Status'),
        optionsKey: 'status'
      }
    ],
    sort: {
      defaultBy: 'created_at',
      defaultOrder: 'desc',
      options: [
        { value: 'created_at', labelKey: 'label_created_time', fallback: 'Created At' },
        { value: 'target_card_id', labelKey: 'col_card', fallback: 'Card' },
        { value: 'from_account_id', labelKey: 'label_from_account', fallback: 'From Account' }
      ]
    }
  }), [t])
  const {
    state: exchangeListState,
    setFilter: setExchangeFilter,
    cycleSort: cycleExchangeSort,
    setPage: setExchangePage,
    setPageSize: setExchangePageSize
  } = useManagementListState(exchangeListSpec)

  const exchangeQueryParams = useMemo(
    () => buildManagementListQueryParams(exchangeListSpec, exchangeListState),
    [exchangeListSpec, exchangeListState]
  )
  const { query } = useManagementListQuery<Record<string, unknown>>({
    queryKey: 'management-exchange-cards',
    endpoint: 'exchange-cards',
    lang,
    params: exchangeQueryParams
  })

  const cancelMutation = useMutation({
    mutationFn: (requestId: number) => requestJson<{ ok: boolean; message: string }>(`/api/react/management/exchange-cards/${requestId}/cancel`, { method: 'POST', body: {} }),
    onSuccess: (result) => {
      setNotice({ level: result.ok ? 'success' : 'error', text: result.message })
      queryClient.invalidateQueries({ queryKey: ['management-exchange-cards'] })
    }
  })

  const rows = ((query.data?.requests as unknown[]) ?? []) as Record<string, unknown>[]
  const totalRecords = toTotalCount(query.data?.total_items, rows.length)
  const accounts = (((query.data?.accounts as unknown[]) ?? []) as Record<string, unknown>[])
  const statusOptions = useMemo(
    () => getManagementFilterOptions<string>(query.data, 'status', ['status_options']),
    [query.data]
  )
  const accountOptions = useMemo(
    () => buildAccountSelectOptions(accounts, t, tr(t, 'label_all_accounts', 'All Accounts')),
    [accounts, t]
  )
  const exchangeToolbarOptions = useMemo<Record<string, SearchableOption[] | ManagementListOption[]>>(
    () => ({
      account_id: accountOptions,
      status: statusOptions.map((value) => ({
        value,
        label: exchangeStatusLabel(t, value)
      }))
    }),
    [accountOptions, statusOptions, t]
  )
  const accountMetaMap = useMemo(() => {
    const map: Record<string, Record<string, unknown>> = {}
    for (const account of accounts) {
      const key = toText(account.id, t)
      if (key !== '-') {
        map[key] = account
      }
    }
    return map
  }, [accounts, t])

  return (
    <section className="surface-card section-stack">
      <div className="section-title">{tr(t, 'menu_exchange_cards', 'Exchange Cards')}</div>
      <InlineNotice notice={notice} />
      <ManagementListToolbar
        spec={exchangeListSpec}
        state={exchangeListState}
        dynamicOptions={exchangeToolbarOptions}
        searchableLocale={selectLocale}
        onFilterChange={setExchangeFilter}
        onPageSizeChange={setExchangePageSize}
        t={t}
      />
      <QueryTotalSummary t={t} total={totalRecords} />

      <div className="table-wrap">
        <table className="grid-table">
          <thead>
            <tr>
              <th>{tr(t, 'col_id', 'ID')}</th>
              <SortableHeaderCell
                label={tr(t, 'label_from_account', 'From Account')}
                sortKey="from_account_id"
                sortBy={exchangeListState.sortBy}
                sortOrder={exchangeListState.sortOrder}
                onToggle={cycleExchangeSort}
              />
              <th>{tr(t, 'col_friend_id', 'Friend ID')}</th>
              <SortableHeaderCell
                label={tr(t, 'col_card', 'Card')}
                sortKey="target_card_id"
                sortBy={exchangeListState.sortBy}
                sortOrder={exchangeListState.sortOrder}
                onToggle={cycleExchangeSort}
              />
              <th>{tr(t, 'col_status', 'Status')}</th>
              <SortableHeaderCell
                label={tr(t, 'col_time', 'Time')}
                sortKey="created_at"
                sortBy={exchangeListState.sortBy}
                sortOrder={exchangeListState.sortOrder}
                onToggle={cycleExchangeSort}
              />
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
                <td>
                  <AccountIdentityCell
                    t={t}
                    accountId={row.from_account_id}
                    name={accountMetaMap[toText(row.from_account_id, t)]?.display_name ?? accountMetaMap[toText(row.from_account_id, t)]?.nickname ?? row.from_account_id}
                    friendId={accountMetaMap[toText(row.from_account_id, t)]?.friend_id}
                    gameId={accountMetaMap[toText(row.from_account_id, t)]?.game_id}
                  />
                </td>
                <td><CopyableFriendId t={t} value={toText(row.to_friend_id, t)} /></td>
                <td>{toText(row.target_card_id, t)}</td>
                <td>{renderBadge(exchangeStatusLabel(t, row.status), statusBadgeVariant(row.status))}</td>
                <td className="mono">{renderRelativeTime(row.created_at, lang, t)}</td>
                <td>
                  {Boolean(row.can_cancel) ? (
                    <Button type="button" size="sm" variant="outline" onClick={() => cancelMutation.mutate(Number(row.id))}>{tr(t, 'btn_cancel_exchange_request', 'Cancel')}</Button>
                  ) : (
                    <Tooltip content={reasonTitle(exchangeCancelDisabledReason(t, row.status)) ?? ''}>
                      <Button type="button" size="sm" variant="outline" disabled>{tr(t, 'btn_cancel_exchange_request', 'Cancel')}</Button>
                    </Tooltip>
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
        onPrev={() => setExchangePage(Math.max(exchangeListState.page - 1, 0))}
        onNext={() => setExchangePage(exchangeListState.page + 1)}
        t={t}
      />
    </section>
  )
}

function JsonSection({ endpoint, title, lang, t }: { endpoint: string; title: string; lang: string; t: Record<string, string> }) {
  const [page, setPage] = useState(0)
  const params = useMemo(() => ({ page }), [page])
  const { query } = useManagementListQuery<Record<string, unknown>>({
    queryKey: `management-generic-${endpoint}`,
    endpoint,
    lang,
    params
  })

  const rows = ((query.data?.items as unknown[]) ?? []) as Record<string, unknown>[]
  const columns = useMemo<ManagementColumnDef[]>(() => {
    if (rows.length === 0) {
      return []
    }
    return Object.keys(rows[0]).slice(0, 8).map((key) => ({
      key,
      label: key,
      render: (row) => (key.includes('at') ? renderRelativeTime(row[key], lang, t) : toText(row[key]))
    }))
  }, [lang, rows, t])

  return (
    <section className="surface-card section-stack">
      <div className="section-title">{title}</div>
      {query.isLoading && <div className="text-sm text-muted">{tr(t, 'label_loading', 'Loading...')}</div>}
      {query.isError && <div className="text-sm text-danger">{(query.error as Error).message}</div>}
      {columns.length > 0 && <ManagementDataGrid rows={rows} columns={columns} t={t} />}
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
  const sectionMap: Record<string, () => ReactNode> = {
    accounts: () => <AccountsSection lang={lang} t={t} />,
    plans: () => <PlansSection lang={lang} t={t} />,
    resources: () => <ResourcesSection lang={lang} t={t} />,
    tasks: () => <TasksSection lang={lang} t={t} />,
    metadata: () => <MetadataSection lang={lang} t={t} />,
    'daily-gift': () => <DailyGiftSection lang={lang} t={t} />,
    friendships: () => <FriendshipsSection lang={lang} t={t} />,
    'exchange-cards': () => <ExchangeCardsSection lang={lang} t={t} />,
    notifications: () => <NotificationsSection lang={lang} t={t} assets={assets} />
  }

  const renderSection = sectionMap[sectionKey]
  if (renderSection) {
    return renderSection()
  }
  return <JsonSection endpoint={sectionKey} title={sectionKey} lang={lang} t={t} />
}

export function buildManagementDefaultRedirectTo(search: string) {
  // 变更原因：默认子路由重定向不继承当前 search，会导致 lang 丢失并回到旧缓存语言。
  return { pathname: '/management/accounts', search }
}

export function ManagementPage({ lang, t, assets }: ManagementPageProps) {
  usePersistedSearchParams()
  const location = useLocation()

  return (
    <section className="management-shell">
      <aside className="surface-card management-sidebar">
        <nav className="management-sidebar-nav">
          {sections.map((section) => (
            <NavLink key={section.key} to={buildManagementSectionTo(section.key, location.search)}>
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
          <Route path="/" element={<Navigate to={buildManagementDefaultRedirectTo(location.search)} replace />} />
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
