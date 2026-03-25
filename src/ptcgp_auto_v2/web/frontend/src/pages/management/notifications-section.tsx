import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { SearchableSelect } from '@/components/ui/searchable-select'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, decodeSelectValue, encodeSelectValue } from '@/components/ui/select'
import { useInfiniteTrigger } from '@/hooks/use-infinite-trigger'
import { useManagementListQuery } from '@/hooks/use-management-list-query'
import { usePersistedState } from '@/hooks/use-persisted-state'
import { buildQuery, requestJson } from '@/lib/api'
import { getCardImageUrls, type CardImageAssets } from '@/lib/card-image'
import { tr } from '@/lib/i18n'

import {
  InlineNotice,
  type InlineNoticeState,
  ListQueryControls,
  Pager,
  QueryTotalSummary,
  type SearchableOption,
  TruncatedText,
  buildAccountSelectOptions,
  formatTime,
  managementStateKey,
  renderBadge,
  sceneBadgeVariant,
  searchableSelectLocale,
  statusLabel,
  taskTypeLabel,
  toText,
  toTotalCount
} from './shared'

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
  const selectLocale = useMemo(() => searchableSelectLocale(t), [t])

  const notificationQueryParams = useMemo(
    () => ({
      page,
      page_size: pageSize,
      sort_by: sortBy,
      sort_order: sortOrder,
      scene: scene || undefined,
      account_id: accountId || undefined,
      is_read: isRead || undefined,
      q
    }),
    [accountId, isRead, page, pageSize, q, scene, sortBy, sortOrder]
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
      cardPickerSortOrder
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
  const sceneSelectOptions = useMemo<SearchableOption[]>(
    () => [
      { value: '', label: tr(t, 'label_all_scenes', 'All Scenes') },
      ...sceneOptions.map((item) => ({
        value: item.value,
        label: item.label,
        searchText: `${item.value} ${item.label}`
      }))
    ],
    [sceneOptions, t]
  )
  const accountSelectOptions = useMemo(
    () => buildAccountSelectOptions(accounts, t, tr(t, 'label_all_accounts', 'All Accounts')),
    [accounts, t]
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
  const cardPickerRaritySelectOptions = useMemo<SearchableOption[]>(
    () => [
      { value: '', label: tr(t, 'label_all_rarities', 'All Rarities') },
      ...cardPickerRarityCodes.map((code) => ({
        value: code,
        label: t[`rarity_${code}`] ?? code,
        searchText: code
      }))
    ],
    [cardPickerRarityCodes, t]
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
            <SearchableSelect
              value={scene}
              options={sceneSelectOptions}
              onValueChange={(value) => {
                setPage(0)
                setScene(value)
              }}
              {...selectLocale}
              placeholder={tr(t, 'label_all_scenes', 'All Scenes')}
              pageSize={8}
            />
          </div>

          <div className="table-filter-item">
            <label className="section-subtitle">{tr(t, 'col_account_id', 'Account ID')}</label>
            <SearchableSelect
              value={accountId}
              options={accountSelectOptions}
              onValueChange={(value) => {
                setPage(0)
                setAccountId(value)
              }}
              {...selectLocale}
              placeholder={tr(t, 'label_all_accounts', 'All Accounts')}
              pageSize={10}
            />
          </div>

          <div className="table-filter-item">
            <label className="section-subtitle">{tr(t, 'col_status', 'Status')}</label>
            <Select value={encodeSelectValue(isRead)} onValueChange={(value) => setIsRead(decodeSelectValue(value))}>
              <SelectTrigger className="field-select table-control">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={encodeSelectValue('')}>{tr(t, 'label_all_status', 'All Status')}</SelectItem>
                <SelectItem value="false">{tr(t, 'label_unread', 'Unread')}</SelectItem>
                <SelectItem value="true">{tr(t, 'label_read', 'Read')}</SelectItem>
              </SelectContent>
            </Select>
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
          <Button type="button" size="sm" variant="outline" className="notification-action-btn" onClick={() => setPage(0)}>
            {tr(t, 'label_search', 'Search')}
          </Button>
          <Button type="button" size="sm" className="notification-action-btn" onClick={() => markAllMutation.mutate()}>
            {tr(t, 'mark_all_read', tr(t, 'btn_mark_all_read', 'Mark All Read'))}
          </Button>
          <Button type="button" size="sm" variant="outline" className="notification-action-btn notification-test-btn" onClick={() => testWebhookMutation.mutate(null)}>
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
          <div className="dialog-card dialog-card--xl notification-picker-dialog" onMouseDown={(event) => event.stopPropagation()}>
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
                <SearchableSelect
                  value={cardPickerRarity}
                  options={cardPickerRaritySelectOptions}
                  onValueChange={(value) => {
                    setCardPickerRarity(value)
                    setCardPickerPage(0)
                  }}
                  {...selectLocale}
                  placeholder={tr(t, 'label_all_rarities', 'All Rarities')}
                  pageSize={10}
                />
                <SearchableSelect
                  value={cardPickerSetCode}
                  options={cardPickerSetSelectOptions}
                  onValueChange={(value) => {
                    setCardPickerSetCode(value)
                    setCardPickerPage(0)
                  }}
                  {...selectLocale}
                  placeholder={tr(t, 'label_all_sets', 'All Sets')}
                  pageSize={10}
                />
                <SearchableSelect
                  value={cardPickerPackName}
                  options={cardPickerPackSelectOptions}
                  onValueChange={(value) => {
                    setCardPickerPackName(value)
                    setCardPickerPage(0)
                  }}
                  {...selectLocale}
                  placeholder={tr(t, 'label_all_packs', 'All Packs')}
                  pageSize={10}
                />
              </div>

              <div className="filter-row">
                <span className="text-xs text-muted">{tr(t, 'label_sort_by', 'Sort By')}</span>
                <Select
                  value={encodeSelectValue(cardPickerSortBy)}
                  onValueChange={(value) => {
                    setCardPickerSortBy(decodeSelectValue(value))
                    setCardPickerPage(0)
                  }}
                >
                  <SelectTrigger className="field-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="id">{tr(t, 'col_id', 'ID')}</SelectItem>
                    <SelectItem value="number">{tr(t, 'col_number', 'Number')}</SelectItem>
                    <SelectItem value="name">{tr(t, 'col_name', 'Name')}</SelectItem>
                  </SelectContent>
                </Select>
                <span className="text-xs text-muted">{tr(t, 'label_sort_order', 'Order')}</span>
                <Select
                  value={encodeSelectValue(cardPickerSortOrder)}
                  onValueChange={(value) => {
                    setCardPickerSortOrder(decodeSelectValue(value) as 'asc' | 'desc')
                    setCardPickerPage(0)
                  }}
                >
                  <SelectTrigger className="field-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="asc">{tr(t, 'sort_order_asc', 'Ascending')}</SelectItem>
                    <SelectItem value="desc">{tr(t, 'sort_order_desc', 'Descending')}</SelectItem>
                  </SelectContent>
                </Select>
                <span className="text-xs text-muted">{tr(t, 'label_page_size', 'Page Size')}</span>
                <Select
                  value={encodeSelectValue(String(cardPickerPageSize))}
                  onValueChange={(value) => {
                    setCardPickerPageSize(Number(decodeSelectValue(value)))
                    setCardPickerPage(0)
                  }}
                >
                  <SelectTrigger className="field-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[24, 36, 48, 60].map((value) => (
                      <SelectItem key={`picker-size-${value}`} value={String(value)}>
                        {value}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
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
                <td>
                  {renderBadge(
                    toText(row.scene_label, t) || tr(t, `notification_scene_${toText(row.scene, t)}`, toText(row.scene, t)),
                    sceneBadgeVariant(toText(row.scene, t))
                  )}
                </td>
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
                    <TruncatedText text={toText(row.content, t)} className="notification-content-text" />
                  </div>
                </td>
                <td>
                  {toText(row.related_account_id, t) === '-'
                    ? '-'
                    : accountNameMap[String(row.related_account_id)] ?? toText(row.related_account_id, t)}
                </td>
                <td>{renderBadge(Boolean(row.is_read) ? tr(t, 'label_read', 'Read') : tr(t, 'label_unread', 'Unread'), Boolean(row.is_read) ? 'muted' : 'warning')}</td>
                <td className="mono">{formatTime(row.created_at)}</td>
                <td>
                  <div className="filter-row">
                    {!Boolean(row.is_read) && (
                      <Button type="button" size="sm" variant="outline" onClick={() => markReadMutation.mutate(Number(row.id))}>{tr(t, 'btn_mark_read', 'Mark Read')}</Button>
                    )}
                    <Button type="button" size="sm" variant="outline" className="notification-test-btn" onClick={() => testWebhookMutation.mutate(Number(row.id))}>{tr(t, 'btn_test_send', 'Test')}</Button>
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
