import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { Tooltip } from '@/components/ui/tooltip'
import { useInfiniteTrigger } from '@/hooks/use-infinite-trigger'
import { useManagementListQuery } from '@/hooks/use-management-list-query'
import { usePersistedState } from '@/hooks/use-persisted-state'
import { requestJson } from '@/lib/api'
import { getCardImageUrls, type CardImageAssets } from '@/lib/card-image'
import { tr } from '@/lib/i18n'
import { formatAbsoluteDateTime, formatRelativeDateTime } from '@/lib/time-display'

import { buildManagementListActionPayload } from './list-actions'
import { buildSearchableManagementOptions, getManagementFilterOptions } from './filter-options'
import { buildManagementListQueryParams } from './list-query'
import type { ManagementListOption, ManagementListSpec } from './list-spec'
import { useManagementListState } from './list-state'
import { ManagementListToolbar } from './list-toolbar'
import {
  AccountIdentityCell,
  InlineNotice,
  SortableHeaderCell,
  type InlineNoticeState,
  Pager,
  QueryTotalSummary,
  type SearchableOption,
  buildAccountSelectOptions,
  managementStateKey,
  renderBadge,
  sceneBadgeVariant,
  searchableSelectLocale,
  statusLabel,
  taskTypeLabel,
  toText,
  toTotalCount
} from './shared'

function stripMarkdownImages(content: string): string {
  if (!content) {
    return ''
  }
  return content
    .replace(/!\[[\s\S]*?]\([^)]+\)/g, '')
    .replace(/<img[^>]*>/gi, '')
}

function extractNotificationContentText(content: string): string {
  const cleaned = stripMarkdownImages(content)
    .replace(/\[([^\]]+)]\([^)]+\)/g, '$1')
    .replace(/[*_`>#-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return cleaned || '-'
}

const managementThumbFrameStyle: CSSProperties = {
  width: '3rem',
  height: '4rem',
  border: '1px solid var(--line)',
  borderRadius: '0.45rem',
  background: '#efe8d9',
  overflow: 'hidden',
  flexShrink: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: '0.18rem'
}

const managementThumbImageStyle: CSSProperties = {
  width: '100%',
  height: '100%',
  objectFit: 'contain',
  display: 'block'
}

export function NotificationsSection({
  lang,
  t,
  assets
}: {
  lang: string
  t: Record<string, string>
  assets: CardImageAssets
}) {
  const queryClient = useQueryClient()
  const [configState, setConfigState] = useState<
    Record<string, { enabled: boolean; enabledWebhook: boolean; extraConfig: Record<string, unknown> }>
  >({})
  const [cardPickerOpen, setCardPickerOpen] = useState(false)
  const [cardPickerScene, setCardPickerScene] = usePersistedState<string>(managementStateKey('notifications', 'picker_scene'), 'rare_card_obtained')
  const [cardPickerSelectedIds, setCardPickerSelectedIds] = useState<number[]>([])
  const [cardPickerCardsAccum, setCardPickerCardsAccum] = useState<Record<string, unknown>[]>([])
  const cardPickerGridRef = useRef<HTMLDivElement | null>(null)
  const [selectedCardNameMap, setSelectedCardNameMap] = useState<Record<number, string>>({})
  const [notice, setNotice] = useState<InlineNoticeState | null>(null)
  const selectLocale = useMemo(() => searchableSelectLocale(t), [t])
  const notificationListSpec = useMemo<ManagementListSpec>(() => ({
    storageKey: 'notifications',
    defaultPageSize: 10,
    pageSizeOptions: [10, 20, 50, 100],
    filters: [
      {
        key: 'scene',
        kind: 'account-select',
        label: tr(t, 'col_scene', 'Scene'),
        placeholder: tr(t, 'label_all_scenes', 'All Scenes'),
        optionsKey: 'scene'
      },
      {
        key: 'account_id',
        kind: 'account-select',
        label: tr(t, 'col_account_id', 'Account ID'),
        placeholder: tr(t, 'label_all_accounts', 'All Accounts'),
        optionsKey: 'account_id'
      },
      {
        key: 'is_read',
        kind: 'select',
        label: tr(t, 'col_status', 'Status'),
        emptyLabel: tr(t, 'label_all_status', 'All Status'),
        options: [
          { value: 'false', label: tr(t, 'label_unread', 'Unread') },
          { value: 'true', label: tr(t, 'label_read', 'Read') }
        ]
      },
      {
        key: 'q',
        kind: 'search',
        label: tr(t, 'label_search', 'Search'),
        placeholder: tr(t, 'notification_search_placeholder', 'Search title/content/account')
      }
    ],
    sort: {
      defaultBy: 'created_at',
      defaultOrder: 'desc',
      options: [
        { value: 'created_at', labelKey: 'label_created_time', fallback: 'Created At' },
        { value: 'title', labelKey: 'col_title', fallback: 'Title' },
        { value: 'scene', labelKey: 'col_scene', fallback: 'Scene' }
      ]
    }
  }), [t])
  const notificationCardPickerSpec = useMemo<ManagementListSpec>(() => ({
    storageKey: 'notifications-card-picker',
    defaultPageSize: 24,
    pageSizeOptions: [24, 36, 48, 60],
    queryKeys: {
      page: 'card_selector_page',
      pageSize: 'card_selector_page_size',
      sortBy: 'card_selector_sort_by',
      sortOrder: 'card_selector_sort_order'
    },
    filters: [
      {
        key: 'q',
        kind: 'search',
        queryKey: 'card_selector_q',
        label: tr(t, 'label_search', 'Search'),
        placeholder: tr(t, 'notification_card_search_placeholder', 'Search card name/number/set')
      },
      {
        key: 'rarity',
        kind: 'select',
        queryKey: 'card_selector_rarity',
        label: tr(t, 'label_rarity', 'Rarity'),
        optionsKey: 'rarity',
        emptyLabel: tr(t, 'label_all_rarities', 'All Rarities')
      },
      {
        key: 'set_code',
        kind: 'searchable-select',
        queryKey: 'card_selector_set_code',
        label: tr(t, 'label_set', 'Set'),
        placeholder: tr(t, 'label_all_sets', 'All Sets'),
        optionsKey: 'set_code',
        pageSize: 10
      },
      {
        key: 'pack_name',
        kind: 'searchable-select',
        queryKey: 'card_selector_pack_name',
        label: tr(t, 'label_pack', 'Pack'),
        placeholder: tr(t, 'label_all_packs', 'All Packs'),
        optionsKey: 'pack_name',
        pageSize: 10
      }
    ],
    sort: {
      defaultBy: 'id',
      defaultOrder: 'asc',
      options: [
        { value: 'id', labelKey: 'col_id', fallback: 'ID' },
        { value: 'number', labelKey: 'col_number', fallback: 'Number' },
        { value: 'name', labelKey: 'col_name', fallback: 'Name' }
      ]
    }
  }), [t])
  const {
    state: notificationListState,
    setFilter: setNotificationFilter,
    cycleSort: cycleNotificationSort,
    setPage: setNotificationPage,
    setPageSize: setNotificationPageSize
  } = useManagementListState(notificationListSpec)
  const {
    state: cardPickerListState,
    setFilter: setCardPickerFilter,
    setPage: setCardPickerPage,
    setPageSize: setCardPickerPageSize
  } = useManagementListState(notificationCardPickerSpec)

  const notificationQueryParams = useMemo(
    () => buildManagementListQueryParams(notificationListSpec, notificationListState),
    [notificationListSpec, notificationListState]
  )
  const { query } = useManagementListQuery<Record<string, unknown>>({
    queryKey: 'management-notifications',
    endpoint: 'notifications',
    lang,
    params: notificationQueryParams
  })

  const cardPickerQueryParams = useMemo(
    () => ({
      scene: cardPickerScene,
      ...buildManagementListQueryParams(notificationCardPickerSpec, cardPickerListState),
      notify_card_ids: cardPickerSelectedIds
    }),
    [
      cardPickerScene,
      cardPickerSelectedIds,
      cardPickerListState,
      notificationCardPickerSpec
    ]
  )
  const cardPickerFilterKey = useMemo(
    () => {
      const { card_selector_page: _page, ...params } = buildManagementListQueryParams(
        notificationCardPickerSpec,
        cardPickerListState
      )
      return JSON.stringify({
        scene: cardPickerScene,
        ...params
      })
    },
    [
      cardPickerScene,
      cardPickerListState,
      notificationCardPickerSpec
    ]
  )

  const { query: cardPickerQuery } = useManagementListQuery<Record<string, unknown>>({
    enabled: cardPickerOpen,
    queryKey: 'management-notification-card-picker',
    endpoint: 'notifications/card-picker',
    lang,
    params: cardPickerQueryParams
  })

  const markReadMutation = useMutation({
    mutationFn: (notificationId: number) => requestJson<{ ok: boolean }>(`/api/react/management/notifications/${notificationId}/mark-read`, { method: 'POST', body: {} }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['management-notifications'] })
  })

  const markAllMutation = useMutation({
    mutationFn: () => requestJson<{ ok: boolean; message: string }>('/api/react/management/notifications/mark-all-read', {
      method: 'POST',
      body: buildManagementListActionPayload({
        params: notificationQueryParams,
        fields: ['scene', 'account_id'],
        missingValue: null
      })
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
          ...buildManagementListActionPayload({
            params: notificationQueryParams,
            fields: ['scene', 'account_id', 'is_read', 'q', 'sort_by', 'sort_order', 'page', 'page_size'],
            missingValue: null
          })
        }
      }),
    onSuccess: (result) => setNotice({ level: result.ok ? 'success' : 'error', text: result.message })
  })

  const notifications = useMemo(
    () => (((query.data?.notifications as unknown[]) ?? []) as Record<string, unknown>[]),
    [query.data?.notifications]
  )
  const totalRecords = toTotalCount(query.data?.total, notifications.length)
  const accounts = useMemo(
    () => (((query.data?.accounts as unknown[]) ?? []) as Record<string, unknown>[]),
    [query.data?.accounts]
  )
  const configs = useMemo(
    () => (((query.data?.configs as unknown[]) ?? []) as Record<string, unknown>[]),
    [query.data?.configs]
  )
  const sceneOptions = useMemo(
    () => getManagementFilterOptions<{ value: string; label: string }>(query.data, 'scene', ['scene_options']),
    [query.data]
  )
  const taskTypeOptions = useMemo(
    () => getManagementFilterOptions<string>(query.data, 'task_type', ['task_type_options']),
    [query.data]
  )
  const taskStatusOptions = useMemo(
    () => getManagementFilterOptions<string>(query.data, 'task_status', ['task_status_options']),
    [query.data]
  )
  const rarityCodes = useMemo(
    () => getManagementFilterOptions<string>(query.data, 'rarity_code', ['rarity_codes']),
    [query.data]
  )
  const accountNameMap = useMemo(
    () => ((query.data?.account_name_map as Record<string, string> | undefined) ?? {}),
    [query.data?.account_name_map]
  )
  const sceneSelectOptions = useMemo<SearchableOption[]>(
    () => buildSearchableManagementOptions(sceneOptions, tr(t, 'label_all_scenes', 'All Scenes')),
    [sceneOptions, t]
  )
  const accountSelectOptions = useMemo(
    () => buildAccountSelectOptions(accounts, t, tr(t, 'label_all_accounts', 'All Accounts')),
    [accounts, t]
  )
  const notificationToolbarOptions = useMemo<Record<string, SearchableOption[] | ManagementListOption[]>>(
    () => ({
      scene: sceneSelectOptions,
      account_id: accountSelectOptions
    }),
    [accountSelectOptions, sceneSelectOptions]
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
  const cardPickerCards = cardPickerCardsAccum
  const cardPickerRarityCodes = useMemo(
    () => getManagementFilterOptions<string>(cardPickerQuery.data, 'rarity', ['rarity_codes']),
    [cardPickerQuery.data]
  )
  const cardPickerSetOptions = useMemo(
    () => getManagementFilterOptions<{ value: string; display_name: string }>(cardPickerQuery.data, 'set_code', ['set_codes']),
    [cardPickerQuery.data]
  )
  const cardPickerPackOptions = useMemo(
    () => getManagementFilterOptions<{ value: string; display_name: string }>(cardPickerQuery.data, 'pack_name', ['pack_names']),
    [cardPickerQuery.data]
  )
  const cardPickerSetSelectOptions = useMemo<SearchableOption[]>(
    () => [
      { value: '', label: tr(t, 'label_all_sets', 'All Sets') },
      ...cardPickerSetOptions.map((option) => ({
        value: option.value,
        label: option.display_name || option.value,
        searchText: `${option.value} ${option.display_name || ''}`
      }))
    ],
    [cardPickerSetOptions, t]
  )
  const cardPickerPackSelectOptions = useMemo<SearchableOption[]>(
    () => [
      { value: '', label: tr(t, 'label_all_packs', 'All Packs') },
      ...cardPickerPackOptions.map((option) => ({
        value: option.value,
        label: option.display_name || option.value,
        searchText: `${option.value} ${option.display_name || ''}`
      }))
    ],
    [cardPickerPackOptions, t]
  )
  const cardPickerSelectedRows = useMemo(
    () => (((cardPickerQuery.data?.selected_cards as unknown[]) ?? []) as Record<string, unknown>[]),
    [cardPickerQuery.data?.selected_cards]
  )
  const cardPickerToolbarOptions = useMemo<Record<string, SearchableOption[] | ManagementListOption[]>>(
    () => ({
      rarity: cardPickerRarityCodes.map((code) => ({
        value: code,
        label: t[`rarity_${code}`] ?? code
      })),
      set_code: cardPickerSetSelectOptions,
      pack_name: cardPickerPackSelectOptions
    }),
    [cardPickerPackSelectOptions, cardPickerRarityCodes, cardPickerSetSelectOptions, t]
  )
  const cardPickerHasNext = Boolean(cardPickerQuery.data?.card_selector_has_next)
  const cardPickerLoadMore = useCallback(() => {
    if (!cardPickerOpen || cardPickerQuery.isFetching || !cardPickerHasNext) {
      return
    }
    setCardPickerPage(cardPickerListState.page + 1)
  }, [cardPickerHasNext, cardPickerListState.page, cardPickerOpen, cardPickerQuery.isFetching, setCardPickerPage])
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
      if (cardPickerListState.page <= 0) {
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
  }, [cardPickerListState.page, cardPickerOpen, cardPickerQuery.data])

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
      <ManagementListToolbar
        spec={notificationListSpec}
        state={notificationListState}
        dynamicOptions={notificationToolbarOptions}
        searchableLocale={selectLocale}
        onFilterChange={setNotificationFilter}
        onPageSizeChange={setNotificationPageSize}
        t={t}
        actions={{
          trailing: (
            <>
              <Button type="button" size="sm" className="notification-action-btn" onClick={() => markAllMutation.mutate()}>
                {tr(t, 'mark_all_read', tr(t, 'btn_mark_all_read', 'Mark All Read'))}
              </Button>
              <Button type="button" size="sm" variant="outline" className="notification-action-btn notification-test-btn" onClick={() => testWebhookMutation.mutate(null)}>
                {tr(t, 'btn_test_webhook', 'Test Webhook')}
              </Button>
            </>
          )
        }}
      />
      <InlineNotice notice={notice} />
      <QueryTotalSummary t={t} total={totalRecords} />

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
                  id={`${sceneKey}-enabled`}
                  name={`${sceneKey}-enabled`}
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
                  id={`${sceneKey}-webhook`}
                  name={`${sceneKey}-webhook`}
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
                            id={`${sceneKey}-rarity-${rarity}`}
                            name={`${sceneKey}-rarity-${rarity}`}
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
                      id={`${sceneKey}-notify-card-ids`}
                      name={`${sceneKey}-notify-card-ids`}
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
                            id={`${sceneKey}-task-${taskType}`}
                            name={`${sceneKey}-task-${taskType}`}
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
                            id={`${sceneKey}-status-${status}`}
                            name={`${sceneKey}-status-${status}`}
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
          <div className="dialog-card dialog-card--xl notification-picker-dialog" onMouseDown={(event) => event.stopPropagation()}>
            <div className="pagination-row">
              <div className="section-title">{tr(t, 'btn_select_cards', 'Select Cards')}</div>
              <Button type="button" size="sm" variant="outline" onClick={() => setCardPickerOpen(false)}>
                {tr(t, 'label_cancel', 'Cancel')}
              </Button>
            </div>

            <div className="section-stack">
              <ManagementListToolbar
                spec={notificationCardPickerSpec}
                state={cardPickerListState}
                dynamicOptions={cardPickerToolbarOptions}
                searchableLocale={selectLocale}
                onFilterChange={setCardPickerFilter}
                onPageSizeChange={setCardPickerPageSize}
                t={t}
              />

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
                        id={`notification-picker-card-${cardId}`}
                        name={`notification-picker-card-${cardId}`}
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
              <th className="table-col-id">{tr(t, 'col_id', 'ID')}</th>
              <SortableHeaderCell
                label={tr(t, 'col_scene', 'Scene')}
                sortKey="scene"
                sortBy={notificationListState.sortBy}
                sortOrder={notificationListState.sortOrder}
                onToggle={cycleNotificationSort}
                className="table-col-status"
              />
              <SortableHeaderCell
                label={tr(t, 'col_title', 'Title')}
                sortKey="title"
                sortBy={notificationListState.sortBy}
                sortOrder={notificationListState.sortOrder}
                onToggle={cycleNotificationSort}
              />
              <th className="table-col-image-text">{tr(t, 'col_description', 'Content')}</th>
              <th className="table-col-account">{tr(t, 'col_account', 'Account')}</th>
              <th className="table-col-status">{tr(t, 'label_read', 'Read')}</th>
              <SortableHeaderCell
                label={tr(t, 'col_time', 'Time')}
                sortKey="created_at"
                sortBy={notificationListState.sortBy}
                sortOrder={notificationListState.sortOrder}
                onToggle={cycleNotificationSort}
                className="table-col-time"
              />
              <th className="table-col-actions">{tr(t, 'col_actions', 'Actions')}</th>
            </tr>
          </thead>
          <tbody>
            {notifications.length === 0 && (
              <tr>
                <td colSpan={8} className="text-center text-muted">{tr(t, 'notification_empty', 'No notifications')}</td>
              </tr>
            )}
            {notifications.map((row) => {
              const contentText = extractNotificationContentText(toText(row.content, t))
              return (
                <tr key={toText(row.id, t)}>
                  <td className="mono table-col-id">{toText(row.id, t)}</td>
                  <td className="table-col-status">
                    {renderBadge(
                      toText(row.scene_label, t) || tr(t, `notification_scene_${toText(row.scene, t)}`, toText(row.scene, t)),
                      sceneBadgeVariant(toText(row.scene, t))
                    )}
                  </td>
                  <td>{toText(row.title, t)}</td>
                  <td className="table-col-image-text">
                    <div className="notification-row-content">
                      {String(row.image_url ?? '').length > 0 ? (
                        <div style={managementThumbFrameStyle} className="notification-thumb-frame">
                          <img
                            src={String(row.image_url)}
                            alt={toText(row.title, t)}
                            className="notification-thumb"
                            style={managementThumbImageStyle}
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
                              const wrapper = image.parentElement as HTMLElement | null
                              if (wrapper) {
                                wrapper.style.display = 'none'
                              }
                            }}
                          />
                        </div>
                      ) : null}
                      <div className="notification-content-main">
                        <div className="notification-content-text">{contentText}</div>
                      </div>
                    </div>
                  </td>
                  <td className="table-col-account">
                    {toText(row.related_account_id, t) === '-'
                      ? '-'
                      : (
                          <AccountIdentityCell
                            t={t}
                            accountId={row.related_account_id}
                            name={accountMetaMap[String(row.related_account_id)]?.display_name ?? accountNameMap[String(row.related_account_id)] ?? toText(row.related_account_id, t)}
                            friendId={accountMetaMap[String(row.related_account_id)]?.friend_id}
                            gameId={accountMetaMap[String(row.related_account_id)]?.game_id}
                          />
                        )}
                  </td>
                  <td className="table-col-status">{renderBadge(Boolean(row.is_read) ? tr(t, 'label_read', 'Read') : tr(t, 'label_unread', 'Unread'), Boolean(row.is_read) ? 'muted' : 'warning')}</td>
                  <td className="mono table-col-time">
                    <Tooltip content={formatAbsoluteDateTime(row.created_at)}>
                      <span>{formatRelativeDateTime(row.created_at, lang, t)}</span>
                    </Tooltip>
                  </td>
                  <td className="table-col-actions">
                    <div className="filter-row">
                      {!Boolean(row.is_read) && (
                        <Button type="button" size="sm" variant="outline" onClick={() => markReadMutation.mutate(Number(row.id))}>{tr(t, 'btn_mark_read', 'Mark Read')}</Button>
                      )}
                      <Button type="button" size="sm" variant="outline" className="notification-test-btn" onClick={() => testWebhookMutation.mutate(Number(row.id))}>{tr(t, 'btn_test_send', 'Test')}</Button>
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
        onPrev={() => setNotificationPage(Math.max(notificationListState.page - 1, 0))}
        onNext={() => setNotificationPage(notificationListState.page + 1)}
        t={t}
      />
    </section>
  )
}
