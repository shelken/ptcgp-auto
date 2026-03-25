import { type CSSProperties, useCallback, useEffect, useMemo, useState } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { useInfiniteTrigger } from '@/hooks/use-infinite-trigger'
import { getCardImageUrls, type CardImageAssets } from '@/lib/card-image'
import { buildQuery, fetchJson, requestJson } from '@/lib/api'
import { tr } from '@/lib/i18n'
import type { BootstrapOptions } from '@/types/api'

interface OwnedCardsPageProps {
  lang: string
  options: BootstrapOptions
  assets: CardImageAssets
  t: Record<string, string>
}

interface CardData {
  id: number
  set_code: string
  number: number
  rarity: string
  type?: string
}

interface OwnedCardItem {
  card: CardData
  card_display_name: string
  total_count: number
  owned_accounts_count: number
  latest_acquired_at: string | null
  ownership_state: string
}

interface OwnedCardsResponse {
  items: OwnedCardItem[]
  page: number
  has_prev: boolean
  has_next: boolean
  total: number
}

interface OwnedStatsResponse {
  filtered_cards_count: number
  rarity_progress: Array<{ rarity: string; owned_count: number; total_count: number }>
}

interface ExchangeAccountRow {
  account_id: number
  nickname: string
  friend_id: string
  count: number
  exchange_points: number | null
  exchange_action: {
    enabled: boolean
    reason_text: string | null
  }
}

interface CardDetailResponse {
  card: CardData
  card_display_name: string
  exchange_blocked: boolean
  total_accounts: number
  total_count: number
  exchange_table: {
    accounts: ExchangeAccountRow[]
  }
}

interface ExchangeAccountsResponse {
  accounts: ExchangeAccountRow[]
  total_items: number
  total_count: number
  page: number
  has_prev: boolean
  has_next: boolean
  q: string
  sort_by: string
  sort_order: string
}

const OWNED_DETAIL_PAGE_SIZE_KEY = 'ptcgp_owned_modal_page_size'
const OWNED_GRID_COLS_KEY = 'ptcgp_owned_cols'

function toggleItems(current: string[], value: string): string[] {
  if (current.includes(value)) {
    return current.filter((item) => item !== value)
  }
  return [...current, value]
}

function parseSearchList(params: URLSearchParams, key: string): string[] {
  const values = params.getAll(key)
  return values.map((item) => item.trim()).filter((item) => item.length > 0)
}

function formatTime(value: string | null) {
  if (!value) {
    return '-'
  }
  return value.replace('T', ' ').slice(0, 19)
}

function calculateDetailPageSize(): number {
  const availableHeight = window.innerHeight - 470
  const rowHeight = 44
  const computed = Math.floor(availableHeight / rowHeight)
  return Math.min(Math.max(computed, 6), 24)
}

function restoreDetailPageSize(): number {
  const value = Number(window.localStorage.getItem(OWNED_DETAIL_PAGE_SIZE_KEY) ?? 0)
  if (!Number.isFinite(value) || value <= 0) {
    return calculateDetailPageSize()
  }
  return Math.min(Math.max(Math.floor(value), 6), 24)
}

function normalizeOwnedGridCols(value: number): number {
  if (!Number.isFinite(value)) {
    return 5
  }
  const integerValue = Math.floor(value)
  if (integerValue < 3) {
    return 3
  }
  if (integerValue > 7) {
    return 7
  }
  return integerValue
}

function restoreOwnedGridCols(): number {
  const value = Number(window.localStorage.getItem(OWNED_GRID_COLS_KEY) ?? 5)
  return normalizeOwnedGridCols(value)
}

async function copyText(value: string, fallbackMessage: string) {
  if (!value) {
    return
  }
  try {
    await navigator.clipboard.writeText(value)
    alert(fallbackMessage)
  } catch {
    alert(fallbackMessage)
  }
}

function CardThumb({
  setCode,
  cardNumber,
  name,
  assets
}: {
  setCode: string
  cardNumber: number
  name: string
  assets: CardImageAssets
}) {
  const urls = getCardImageUrls(assets, { setCode, cardNumber })
  return (
    <img
      src={urls.png}
      alt={name}
      className="owned-thumb"
      loading="lazy"
      decoding="async"
      onError={(event) => {
        const image = event.currentTarget
        if (image.dataset.webpTried === '1') {
          image.src = urls.cdnPng
          image.dataset.webpTried = '2'
          return
        }
        if (image.dataset.webpTried === '2') {
          image.src = urls.cdnWebp
          image.dataset.webpTried = '3'
          return
        }
        image.dataset.webpTried = '1'
        image.src = urls.webp
      }}
    />
  )
}

export function OwnedCardsPage({ lang, options, assets, t }: OwnedCardsPageProps) {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()

  const [accountQuery, setAccountQuery] = useState(() => searchParams.get('owned_account') ?? '')
  const [selectedRarity, setSelectedRarity] = useState<string[]>(() => parseSearchList(searchParams, 'owned_rarity'))
  const [selectedTypes, setSelectedTypes] = useState<string[]>(() => parseSearchList(searchParams, 'owned_type'))
  const [selectedElements, setSelectedElements] = useState<string[]>(() => parseSearchList(searchParams, 'owned_element'))
  const [selectedSetCodes, setSelectedSetCodes] = useState<string[]>(() => parseSearchList(searchParams, 'owned_set'))
  const [selectedPackNames, setSelectedPackNames] = useState<string[]>(() => parseSearchList(searchParams, 'owned_pack'))
  const [sortBy, setSortBy] = useState(() => searchParams.get('owned_sort') ?? 'acquired')
  const [ownershipScope, setOwnershipScope] = useState(() => searchParams.get('owned_scope') ?? 'owned')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>(() => (searchParams.get('owned_view') === 'list' ? 'list' : 'grid'))
  const [gridCols, setGridCols] = useState(() => restoreOwnedGridCols())
  const [showCounts, setShowCounts] = useState(() => searchParams.get('owned_counts') !== 'hide')
  const [listPage, setListPage] = useState(() => {
    const value = Number(searchParams.get('owned_page') ?? 0)
    return Number.isFinite(value) && value >= 0 ? value : 0
  })

  const [detailCardId, setDetailCardId] = useState<number | null>(null)
  const [friendInputByAccount, setFriendInputByAccount] = useState<Record<number, string>>({})
  const [detailPage, setDetailPage] = useState(0)
  const [detailQ, setDetailQ] = useState('')
  const [detailSortBy, setDetailSortBy] = useState('account_id')
  const [detailSortOrder, setDetailSortOrder] = useState<'asc' | 'desc'>('asc')
  const [detailPageSize, setDetailPageSize] = useState(() => restoreDetailPageSize())

  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    next.delete('owned_rarity')
    next.delete('owned_type')
    next.delete('owned_element')
    next.delete('owned_set')
    next.delete('owned_pack')
    next.delete('owned_account')
    next.delete('owned_sort')
    next.delete('owned_scope')
    next.delete('owned_view')
    next.delete('owned_counts')
    next.delete('owned_page')
    selectedRarity.forEach((item) => next.append('owned_rarity', item))
    selectedTypes.forEach((item) => next.append('owned_type', item))
    selectedElements.forEach((item) => next.append('owned_element', item))
    selectedSetCodes.forEach((item) => next.append('owned_set', item))
    selectedPackNames.forEach((item) => next.append('owned_pack', item))
    next.set('owned_account', accountQuery)
    next.set('owned_sort', sortBy)
    next.set('owned_scope', ownershipScope)
    next.set('owned_view', viewMode)
    next.set('owned_counts', showCounts ? 'show' : 'hide')
    if (viewMode === 'list') {
      next.set('owned_page', String(listPage))
    }
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true })
    }
  }, [
    accountQuery,
    ownershipScope,
    viewMode,
    showCounts,
    listPage,
    searchParams,
    selectedElements,
    selectedPackNames,
    selectedRarity,
    selectedSetCodes,
    selectedTypes,
    setSearchParams,
    sortBy
  ])

  const baseParams = useMemo(
    () => ({
      lang,
      account_id: accountQuery,
      sort_by: sortBy,
      ownership_scope: ownershipScope,
      rarity: selectedRarity,
      card_type: selectedTypes,
      element: selectedElements,
      set_code: selectedSetCodes,
      pack_name: selectedPackNames
    }),
    [accountQuery, lang, ownershipScope, selectedElements, selectedPackNames, selectedRarity, selectedSetCodes, selectedTypes, sortBy]
  )

  const listQueryString = useMemo(
    () =>
      buildQuery({
        ...baseParams,
        page: listPage,
        page_size: 40
      }),
    [baseParams, listPage]
  )

  const statsQueryString = useMemo(
    () =>
      buildQuery({
        lang,
        account_id: accountQuery,
        ownership_scope: ownershipScope,
        rarity: selectedRarity,
        card_type: selectedTypes,
        element: selectedElements,
        set_code: selectedSetCodes,
        pack_name: selectedPackNames
      }),
    [accountQuery, lang, ownershipScope, selectedElements, selectedPackNames, selectedRarity, selectedSetCodes, selectedTypes]
  )

  const listQuery = useQuery({
    queryKey: ['owned-list', listQueryString],
    queryFn: () => fetchJson<OwnedCardsResponse>(`/api/react/owned-cards?${listQueryString}`),
    enabled: viewMode === 'list',
    refetchInterval: 60000
  })

  const gridQuery = useInfiniteQuery({
    queryKey: ['owned-grid', baseParams],
    queryFn: ({ pageParam }) =>
      fetchJson<OwnedCardsResponse>(
        `/api/react/owned-cards?${buildQuery({
          ...baseParams,
          page: pageParam,
          page_size: 40
        })}`
      ),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => (lastPage.has_next ? lastPage.page + 1 : undefined),
    enabled: viewMode === 'grid',
    refetchInterval: 60000
  })

  const statsQuery = useQuery({
    queryKey: ['owned-stats', statsQueryString],
    queryFn: () => fetchJson<OwnedStatsResponse>(`/api/react/owned-cards/stats?${statsQueryString}`),
    refetchInterval: 60000
  })

  const detailQuery = useQuery({
    queryKey: ['owned-detail', detailCardId, lang, ownershipScope, detailPageSize],
    queryFn: () =>
      fetchJson<CardDetailResponse>(
        `/api/react/owned-cards/${detailCardId}/detail?${buildQuery({
          lang,
          ownership_state: ownershipScope,
          page_size: detailPageSize
        })}`
      ),
    enabled: detailCardId !== null
  })

  const detailTableQueryString = useMemo(
    () =>
      detailCardId === null
        ? ''
        : buildQuery({
            lang,
            page: detailPage,
            page_size: detailPageSize,
            q: detailQ,
            sort_by: detailSortBy,
            sort_order: detailSortOrder
          }),
    [detailCardId, detailPage, detailPageSize, detailQ, detailSortBy, detailSortOrder, lang]
  )

  const detailTableQuery = useQuery({
    queryKey: ['owned-detail-table', detailCardId, detailTableQueryString],
    queryFn: () =>
      fetchJson<ExchangeAccountsResponse>(
        `/api/react/owned-cards/${detailCardId}/exchange-accounts?${detailTableQueryString}`
      ),
    enabled: detailCardId !== null && detailTableQueryString.length > 0
  })

  const exchangeMutation = useMutation({
    mutationFn: (payload: { from_account_id: number; to_account_id: number | null; to_friend_id: string; target_card_id: number; target_card_rarity: string }) =>
      requestJson<{ ok: boolean; message: string }>('/api/react/exchange-cards/requests', {
        method: 'POST',
        body: payload
      }),
    onSuccess: (result) => {
      alert(result.message)
      queryClient.invalidateQueries({ queryKey: ['owned-detail', detailCardId, lang] })
      queryClient.invalidateQueries({ queryKey: ['owned-detail-table', detailCardId] })
    }
  })

  useEffect(() => {
    if (detailCardId === null) {
      return
    }

    const syncPageSize = () => {
      const nextSize = calculateDetailPageSize()
      setDetailPageSize(nextSize)
      window.localStorage.setItem(OWNED_DETAIL_PAGE_SIZE_KEY, String(nextSize))
    }
    syncPageSize()
    window.addEventListener('resize', syncPageSize)
    return () => window.removeEventListener('resize', syncPageSize)
  }, [detailCardId])

  useEffect(() => {
    window.localStorage.setItem(OWNED_GRID_COLS_KEY, String(normalizeOwnedGridCols(gridCols)))
  }, [gridCols])

  const gridCards = (gridQuery.data?.pages ?? []).flatMap((page) => page.items)
  const cards = viewMode === 'grid' ? gridCards : (listQuery.data?.items ?? [])
  const totalCards = viewMode === 'grid' ? (gridQuery.data?.pages[0]?.total ?? 0) : (listQuery.data?.total ?? 0)
  const gridHasNextPage = Boolean(gridQuery.data?.pages[gridQuery.data.pages.length - 1]?.has_next)
  const gridLoadMore = useCallback(() => {
    if (viewMode !== 'grid') {
      return
    }
    if (!gridQuery.isFetchingNextPage && gridQuery.hasNextPage) {
      void gridQuery.fetchNextPage()
    }
  }, [gridQuery, viewMode])
  const gridSentinelRef = useInfiniteTrigger({
    enabled: viewMode === 'grid' && gridHasNextPage && !gridQuery.isFetchingNextPage,
    onLoadMore: gridLoadMore
  })
  const isListLoading = viewMode === 'list' ? listQuery.isLoading : gridQuery.isLoading
  const isListError = viewMode === 'list' ? listQuery.isError : gridQuery.isError
  const listError = (viewMode === 'list' ? listQuery.error : gridQuery.error) as Error | null

  const clearFilters = () => {
    setListPage(0)
    setAccountQuery('')
    setSelectedRarity([])
    setSelectedTypes([])
    setSelectedElements([])
    setSelectedSetCodes([])
    setSelectedPackNames([])
    setSortBy('acquired')
    setOwnershipScope('owned')
    setViewMode('grid')
    setShowCounts(true)
  }

  return (
    <section className="section-stack">
      <div className="surface-card section-stack">
        <div className="pagination-row">
          <h2 className="section-title">{tr(t, 'filter_title', 'Filters')}</h2>
          <Button type="button" size="sm" variant="outline" onClick={clearFilters}>
            {tr(t, 'clear_filters', 'Clear')}
          </Button>
        </div>

        <div className="filter-row">
          <input
            className="field-input"
            value={accountQuery}
            onChange={(event) => {
              setListPage(0)
              setAccountQuery(event.target.value)
            }}
            placeholder={tr(t, 'filter_account_id_placeholder', 'Account ID')}
          />
        </div>

        <div className="filter-row">
          <Button type="button" size="sm" variant={ownershipScope === 'owned' ? 'default' : 'outline'} onClick={() => { setListPage(0); setOwnershipScope('owned') }}>
            {tr(t, 'owned_scope_owned', 'Owned')}
          </Button>
          <Button type="button" size="sm" variant={ownershipScope === 'missing' ? 'default' : 'outline'} onClick={() => { setListPage(0); setOwnershipScope('missing') }}>
            {tr(t, 'owned_scope_missing', 'Missing')}
          </Button>
          <Button type="button" size="sm" variant={ownershipScope === 'all' ? 'default' : 'outline'} onClick={() => { setListPage(0); setOwnershipScope('all') }}>
            {tr(t, 'owned_scope_all', 'All')}
          </Button>
        </div>

        <div className="filter-row">
          <Button type="button" size="sm" variant={sortBy === 'acquired' ? 'default' : 'outline'} onClick={() => { setListPage(0); setSortBy('acquired') }}>
            {tr(t, 'owned_sort_acquired', 'Acquired')}
          </Button>
          <Button type="button" size="sm" variant={sortBy === 'rarity' ? 'default' : 'outline'} onClick={() => { setListPage(0); setSortBy('rarity') }}>
            {tr(t, 'owned_sort_rarity', 'Rarity')}
          </Button>
          <Button type="button" size="sm" variant={sortBy === 'count' ? 'default' : 'outline'} onClick={() => { setListPage(0); setSortBy('count') }}>
            {tr(t, 'owned_sort_count', 'Count')}
          </Button>
        </div>

        <div className="filter-row">
          <Button
            type="button"
            size="sm"
            variant={viewMode === 'grid' ? 'default' : 'outline'}
            onClick={() => setViewMode('grid')}
          >
            {tr(t, 'view_grid', 'Grid')}
          </Button>
          <Button
            type="button"
            size="sm"
            variant={viewMode === 'list' ? 'default' : 'outline'}
            onClick={() => setViewMode('list')}
          >
            {tr(t, 'view_list', 'List')}
          </Button>
          {viewMode === 'grid' && (
            <>
              {[4, 5, 6].map((value) => (
                <Button
                  key={`grid-${value}`}
                  type="button"
                  size="sm"
                  variant={gridCols === value ? 'default' : 'outline'}
                  onClick={() => setGridCols(value)}
                >
                  {value} {tr(t, 'owned_cols_label', 'Cols')}
                </Button>
              ))}
              <Button type="button" size="sm" variant="outline" onClick={() => setShowCounts((prev) => !prev)}>
                {showCounts
                  ? tr(t, 'owned_counts_hide', 'Hide Counts')
                  : tr(t, 'owned_counts_toggle', 'Show Counts')}
              </Button>
            </>
          )}
        </div>

        <details>
          <summary className="section-subtitle">{tr(t, 'filter_rarity', 'Rarity')}</summary>
          <div className="filter-row mt-2">
            {options.rarities.map((rarity) => (
              <Button key={rarity} type="button" size="sm" variant={selectedRarity.includes(rarity) ? 'default' : 'outline'} onClick={() => { setListPage(0); setSelectedRarity((prev) => toggleItems(prev, rarity)) }}>
                {t[`rarity_${rarity}`] ?? rarity}
              </Button>
            ))}
          </div>
        </details>

        <details>
          <summary className="section-subtitle">{tr(t, 'filter_type', 'Type')}</summary>
          <div className="filter-row mt-2">
            {options.card_types.map((cardType) => (
              <Button key={cardType} type="button" size="sm" variant={selectedTypes.includes(cardType) ? 'default' : 'outline'} onClick={() => { setListPage(0); setSelectedTypes((prev) => toggleItems(prev, cardType)) }}>
                {t[`type_${cardType}`] ?? cardType}
              </Button>
            ))}
          </div>
        </details>

        <details>
          <summary className="section-subtitle">{tr(t, 'filter_set', 'Set')}</summary>
          <div className="filter-row mt-2">
            {options.card_sets.map((item) => (
              <Button key={item.code} type="button" size="sm" variant={selectedSetCodes.includes(item.code) ? 'default' : 'outline'} onClick={() => { setListPage(0); setSelectedSetCodes((prev) => toggleItems(prev, item.code)) }}>
                {item.display_name}
              </Button>
            ))}
          </div>
        </details>

        <details>
          <summary className="section-subtitle">{tr(t, 'filter_pack', 'Pack')}</summary>
          <div className="filter-row mt-2">
            {options.packs.map((item) => (
              <Button key={item.name} type="button" size="sm" variant={selectedPackNames.includes(item.name) ? 'default' : 'outline'} onClick={() => { setListPage(0); setSelectedPackNames((prev) => toggleItems(prev, item.name)) }}>
                {item.display_name}
              </Button>
            ))}
          </div>
        </details>

        <details>
          <summary className="section-subtitle">{tr(t, 'filter_element', 'Element')}</summary>
          <div className="filter-row mt-2">
            {options.elements.map((item) => (
              <Button key={item} type="button" size="sm" variant={selectedElements.includes(item) ? 'default' : 'outline'} onClick={() => { setListPage(0); setSelectedElements((prev) => toggleItems(prev, item)) }}>
                {t[`element_${item}`] ?? item}
              </Button>
            ))}
          </div>
        </details>
      </div>

      {statsQuery.data && (
        <div className="surface-card section-stack">
          <div className="text-sm">{tr(t, 'owned_filtered_cards_label', 'Filtered Cards')}: <span className="mono">{statsQuery.data.filtered_cards_count}</span></div>
          <div className="filter-row">
            {statsQuery.data.rarity_progress.map((item) => (
              <span key={item.rarity} className="tag">{item.rarity}: {item.owned_count}/{item.total_count}</span>
            ))}
          </div>
        </div>
      )}

      {isListLoading && <div className="surface-card text-sm text-muted">{tr(t, 'label_loading', 'Loading...')}</div>}
      {isListError && <div className="surface-card text-sm text-danger">{listError?.message}</div>}

      {(viewMode === 'grid' ? gridQuery.data : listQuery.data) && (
        <>
          {viewMode === 'grid' ? (
            <div className="surface-card">
              {cards.length === 0 ? (
                <div className="text-center text-muted py-8">
                  {ownershipScope === 'missing'
                    ? tr(t, 'owned_cards_missing_empty', 'No missing cards')
                    : ownershipScope === 'all'
                      ? tr(t, 'owned_cards_all_empty', 'No cards')
                      : tr(t, 'owned_cards_empty', 'No owned cards')}
                </div>
              ) : (
                <div
                  className={`owned-grid ${showCounts ? 'owned-grid-show-counts' : ''}`}
                  style={{ '--owned-grid-cols': String(normalizeOwnedGridCols(gridCols)) } as CSSProperties}
                >
                  {cards.map((item) => {
                    const urls = getCardImageUrls(assets, {
                      setCode: item.card.set_code,
                      cardNumber: item.card.number
                    })
                    return (
                      <button
                        key={item.card.id}
                        type="button"
                        className={`owned-card ${item.ownership_state === 'missing' ? 'owned-card--missing' : ''}`}
                        onClick={() => {
                          setDetailCardId(item.card.id)
                          setDetailPage(0)
                          setDetailQ('')
                          setDetailSortBy('account_id')
                          setDetailSortOrder('asc')
                        }}
                      >
                        <div className="owned-card-media">
                          <img
                            src={urls.png}
                            alt={item.card_display_name}
                            className="owned-card-image"
                            loading="lazy"
                            decoding="async"
                            onError={(event) => {
                              const image = event.currentTarget
                              if (image.dataset.webpTried === '1') {
                                image.src = urls.cdnPng
                                image.dataset.webpTried = '2'
                                return
                              }
                              if (image.dataset.webpTried === '2') {
                                image.src = urls.cdnWebp
                                image.dataset.webpTried = '3'
                                return
                              }
                              image.dataset.webpTried = '1'
                              image.src = urls.webp
                            }}
                          />
                        </div>
                        {showCounts ? (
                          <div className="owned-card-count">
                            {item.ownership_state === 'missing' ? 0 : item.owned_accounts_count}
                          </div>
                        ) : null}
                        <div className="owned-card-name" title={item.card_display_name}>
                          {item.card_display_name}
                        </div>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          ) : (
            <div className="surface-card table-wrap">
              <table className="grid-table">
                <thead>
                  <tr>
                    <th>{tr(t, 'col_card', 'Card')}</th>
                    <th>{tr(t, 'label_card_number', 'No.')}</th>
                    <th>{tr(t, 'label_rarity', 'Rarity')}</th>
                    <th>{tr(t, 'col_count', 'Count')}</th>
                    <th>{tr(t, 'owned_accounts_total', 'Accounts')}</th>
                    <th>{tr(t, 'col_updated_at', 'Updated')}</th>
                    <th>{tr(t, 'col_actions', 'Actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {cards.length === 0 && (
                    <tr>
                      <td colSpan={7} className="text-center text-muted">
                        {ownershipScope === 'missing'
                          ? tr(t, 'owned_cards_missing_empty', 'No missing cards')
                          : ownershipScope === 'all'
                            ? tr(t, 'owned_cards_all_empty', 'No cards')
                            : tr(t, 'owned_cards_empty', 'No owned cards')}
                      </td>
                    </tr>
                  )}
                  {cards.map((item) => (
                    <tr key={item.card.id}>
                      <td>
                        <div className="owned-card-cell">
                          <CardThumb
                            setCode={item.card.set_code}
                            cardNumber={item.card.number}
                            name={item.card_display_name}
                            assets={assets}
                          />
                          <span>{item.card_display_name}</span>
                        </div>
                      </td>
                      <td className="mono">{item.card.set_code}-{String(item.card.number).padStart(3, '0')}</td>
                      <td>{item.card.rarity}</td>
                      <td className="mono">{item.total_count}</td>
                      <td className="mono">{item.owned_accounts_count}</td>
                      <td className="mono">{formatTime(item.latest_acquired_at)}</td>
                      <td>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setDetailCardId(item.card.id)
                            setDetailPage(0)
                            setDetailQ('')
                            setDetailSortBy('account_id')
                            setDetailSortOrder('asc')
                          }}
                        >
                          {tr(t, 'label_detail', 'Detail')}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {viewMode === 'grid' ? (
            <div className="surface-card section-stack">
              <div className="text-xs text-muted">{tr(t, 'total_text', 'Total')}: {totalCards}</div>
              {gridQuery.isFetchingNextPage && (
                <div className="text-xs text-muted">{tr(t, 'label_loading_more', 'Loading more...')}</div>
              )}
              {!gridHasNextPage && cards.length > 0 && (
                <div className="text-xs text-muted">{tr(t, 'label_reach_end', 'Reached the end')}</div>
              )}
              <div ref={gridSentinelRef} className="infinite-sentinel" />
            </div>
          ) : (
            <div className="surface-card pagination-row">
              <div className="text-xs text-muted">{tr(t, 'total_text', 'Total')}: {totalCards}</div>
              <div className="filter-row">
                <Button type="button" size="sm" variant="outline" disabled={!listQuery.data?.has_prev} onClick={() => setListPage((prev) => Math.max(prev - 1, 0))}>{tr(t, 'btn_prev_page', 'Previous')}</Button>
                <span className="text-xs mono px-2 py-1">{listPage + 1}</span>
                <Button type="button" size="sm" variant="outline" disabled={!listQuery.data?.has_next} onClick={() => setListPage((prev) => prev + 1)}>{tr(t, 'btn_next_page', 'Next')}</Button>
              </div>
            </div>
          )}
        </>
      )}

      {detailCardId !== null && (
        <div
          className="dialog-overlay"
          onClick={() => {
            setDetailCardId(null)
            setDetailPage(0)
            setDetailQ('')
            setDetailSortBy('account_id')
            setDetailSortOrder('asc')
          }}
        >
          <div className="dialog-card section-stack" onClick={(event) => event.stopPropagation()}>
            <div className="pagination-row">
              <div className="section-title">{tr(t, 'owned_cards_detail_title', 'Card Detail')}</div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  setDetailCardId(null)
                  setDetailPage(0)
                  setDetailQ('')
                  setDetailSortBy('account_id')
                  setDetailSortOrder('asc')
                }}
              >
                {tr(t, 'label_close', 'Close')}
              </Button>
            </div>

            {detailQuery.isLoading && <div className="text-sm text-muted">{tr(t, 'label_loading', 'Loading...')}</div>}
            {detailQuery.isError && <div className="text-sm text-danger">{(detailQuery.error as Error).message}</div>}

            {detailQuery.data && (
              <>
                <div className="surface-card section-stack">
                  <div className="section-title">{detailQuery.data.card_display_name}</div>
                  <CardThumb
                    setCode={detailQuery.data.card.set_code}
                    cardNumber={detailQuery.data.card.number}
                    name={detailQuery.data.card_display_name}
                    assets={assets}
                  />
                  <div className="filter-row">
                    <span className="tag">{detailQuery.data.card.set_code}</span>
                    <span className="tag">#{String(detailQuery.data.card.number).padStart(3, '0')}</span>
                    <span className="tag">{detailQuery.data.card.rarity}</span>
                    <span className="tag">{tr(t, 'owned_accounts_total', 'Accounts')} {detailQuery.data.total_accounts}</span>
                    <span className="tag">{tr(t, 'owned_count_total', 'Total Count')} {detailQuery.data.total_count}</span>
                  </div>
                </div>

                <div className="table-wrap">
                  <div className="surface-card section-stack">
                    <div className="filter-row">
                      <input
                        className="field-input"
                        value={detailQ}
                        onChange={(event) => {
                          setDetailPage(0)
                          setDetailQ(event.target.value)
                        }}
                        placeholder={tr(t, 'exchange_search_accounts', 'Search Account ID / nickname / friend id')}
                      />
                      <select
                        className="field-select"
                        value={detailSortBy}
                        onChange={(event) => {
                          setDetailPage(0)
                          setDetailSortBy(event.target.value)
                        }}
                      >
                        <option value="account_id">{tr(t, 'col_account_id', 'Account ID')}</option>
                        <option value="friend_id">{tr(t, 'col_friend_id', 'Friend ID')}</option>
                        <option value="nickname">{tr(t, 'col_nickname', 'Nickname')}</option>
                        <option value="count">{tr(t, 'col_count', 'Count')}</option>
                        <option value="exchange_points">{tr(t, 'col_exchange_points', 'Exchange Points')}</option>
                      </select>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setDetailPage(0)
                          setDetailSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
                        }}
                      >
                        {detailSortOrder === 'asc' ? tr(t, 'sort_order_asc', 'Ascending') : tr(t, 'sort_order_desc', 'Descending')}
                      </Button>
                    </div>
                  </div>
                  <table className="grid-table">
                    <thead>
                      <tr>
                        <th>{tr(t, 'col_account', 'Account')}</th>
                        <th>{tr(t, 'col_friend_id', 'Friend ID')}</th>
                        <th>{tr(t, 'col_count', 'Count')}</th>
                        <th>{tr(t, 'col_exchange_points', 'Exchange Points')}</th>
                        <th>{tr(t, 'col_actions', 'Actions')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(detailTableQuery.data?.accounts ?? []).length === 0 && (
                        <tr>
                          <td colSpan={5} className="text-center text-muted">{tr(t, 'exchange_entry_no_available_accounts', 'No eligible accounts')}</td>
                        </tr>
                      )}
                      {(detailTableQuery.data?.accounts ?? []).map((row) => {
                        const defaultFriendId = friendInputByAccount[row.account_id] ?? row.friend_id ?? ''
                        return (
                          <tr key={row.account_id}>
                            <td>{row.nickname || `#${row.account_id}`}</td>
                            <td>
                              <div className="filter-row">
                                <input
                                  className="field-input w-full"
                                  value={defaultFriendId}
                                  onChange={(event) =>
                                    setFriendInputByAccount((prev) => ({
                                      ...prev,
                                      [row.account_id]: event.target.value
                                    }))
                                  }
                                  placeholder={tr(t, 'exchange_input_friend_id', 'Target Friend ID')}
                                />
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => copyText(defaultFriendId, tr(t, 'msg_copied', 'Copied'))}
                                  disabled={defaultFriendId.trim().length === 0}
                                >
                                  {tr(t, 'label_copy', 'Copy')}
                                </Button>
                              </div>
                            </td>
                            <td className="mono">{row.count}</td>
                            <td className="mono">{row.exchange_points ?? '-'}</td>
                            <td>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                disabled={!row.exchange_action.enabled || exchangeMutation.isPending}
                                onClick={() => {
                                  exchangeMutation.mutate({
                                    from_account_id: row.account_id,
                                    to_account_id: null,
                                    to_friend_id: (friendInputByAccount[row.account_id] ?? row.friend_id ?? '').trim(),
                                    target_card_id: detailQuery.data.card.id,
                                    target_card_rarity: detailQuery.data.card.rarity
                                  })
                                }}
                              >
                                {tr(t, 'exchange_entry_action', 'Exchange')}
                              </Button>
                              {!row.exchange_action.enabled && (
                                <div className="text-xs text-danger mt-1">{row.exchange_action.reason_text ?? tr(t, 'exchange_entry_blocked_rarity', 'Not exchangeable')}</div>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                  <div className="surface-card pagination-row">
                    <div className="text-xs text-muted">{tr(t, 'owned_accounts_total', 'Accounts')}: {detailTableQuery.data?.total_items ?? 0}</div>
                    <div className="filter-row">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={!detailTableQuery.data?.has_prev}
                        onClick={() => setDetailPage((prev) => Math.max(prev - 1, 0))}
                      >
                        {tr(t, 'btn_prev_page', 'Previous')}
                      </Button>
                      <span className="text-xs mono px-2 py-1">{(detailTableQuery.data?.page ?? 0) + 1}</span>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={!detailTableQuery.data?.has_next}
                        onClick={() => setDetailPage((prev) => prev + 1)}
                      >
                        {tr(t, 'btn_next_page', 'Next')}
                      </Button>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
