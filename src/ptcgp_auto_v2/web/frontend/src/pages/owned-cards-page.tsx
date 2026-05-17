import { type CSSProperties, useCallback, useDeferredValue, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, decodeSelectValue, encodeSelectValue } from '@/components/ui/select'
import { Tooltip } from '@/components/ui/tooltip'
import { useCardPreviewDrag } from '@/hooks/use-card-preview-drag'
import { useCardPreviewVisual } from '@/hooks/use-card-preview-visual'
import { useInfiniteTrigger } from '@/hooks/use-infinite-trigger'
import { usePersistedSearchParams } from '@/hooks/use-persisted-search-params'
import { usePreviewOriginVisibility } from '@/hooks/use-preview-origin-visibility'
import { buildQuery, fetchJson, requestJson } from '@/lib/api'
import { applyCardListImageFallback, applyCardPreviewImageFallback } from '@/lib/card-image-fallback'
import { getCardImageUrls, type CardImageAssets } from '@/lib/card-image'
import { hideBrokenCardBackImage } from '@/lib/card-preview-assets'
import { clearCardFlipExitGhosts, playCardFlipEntrance, playCardFlipExitGhost, snapshotElementRect, type PreviewRectLike } from '@/lib/flip-transition'
import { tr } from '@/lib/i18n'
import { parseSearchList, reasonTitle, toggleListItem } from '@/lib/list-utils'
import { formatAbsoluteDateTime, formatRelativeDateTime } from '@/lib/time-display'
import type { BootstrapOptions } from '@/types/api'

import { AccountIdentityCell } from './management/shared'
import {
  buildOwnedCardDetailQueryParams,
  buildOwnedCardExchangeAccountsQueryParams,
  buildOwnedCardsListQueryParams,
  buildOwnedCardsStatsQueryParams,
  type OwnedCardExchangeAccountsQueryState,
  type OwnedCardsMainQueryState
} from './owned-cards-query'

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
  game_id?: string | null
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
const OWNED_PAGE_SIZE = 40
const DETAIL_TABLE_ROW_HEIGHT = 44
const DETAIL_MODAL_RESERVED_HEIGHT = 470
const DETAIL_PAGE_SIZE_MIN = 6
const DETAIL_PAGE_SIZE_MAX = 24
const OWNED_GRID_COLS_MIN = 3
const OWNED_GRID_COLS_MAX = 7
const OWNED_GRID_COLS_DEFAULT = 5
type DetailSortField = 'account_id' | 'friend_id' | 'nickname' | 'count' | 'exchange_points'
type DetailNoticeLevel = 'success' | 'error'
type OwnedCardsViewMode = 'grid' | 'list'

interface DetailNoticeState {
  level: DetailNoticeLevel
  text: string
}

function calculateDetailPageSize(): number {
  const availableHeight = window.innerHeight - DETAIL_MODAL_RESERVED_HEIGHT
  const computed = Math.floor(availableHeight / DETAIL_TABLE_ROW_HEIGHT)
  return Math.min(Math.max(computed, DETAIL_PAGE_SIZE_MIN), DETAIL_PAGE_SIZE_MAX)
}

function restoreDetailPageSize(): number {
  const value = Number(window.localStorage.getItem(OWNED_DETAIL_PAGE_SIZE_KEY) ?? 0)
  if (!Number.isFinite(value) || value <= 0) {
    return calculateDetailPageSize()
  }
  return Math.min(Math.max(Math.floor(value), DETAIL_PAGE_SIZE_MIN), DETAIL_PAGE_SIZE_MAX)
}

function normalizeOwnedGridCols(value: number): number {
  if (!Number.isFinite(value)) {
    return OWNED_GRID_COLS_DEFAULT
  }
  const integerValue = Math.floor(value)
  if (integerValue < OWNED_GRID_COLS_MIN) {
    return OWNED_GRID_COLS_MIN
  }
  if (integerValue > OWNED_GRID_COLS_MAX) {
    return OWNED_GRID_COLS_MAX
  }
  return integerValue
}

function restoreOwnedGridCols(): number {
  const value = Number(window.localStorage.getItem(OWNED_GRID_COLS_KEY) ?? OWNED_GRID_COLS_DEFAULT)
  return normalizeOwnedGridCols(value)
}

function ownedEmptyText(ownershipScope: string, t: Record<string, string>): string {
  if (ownershipScope === 'missing') {
    return tr(t, 'owned_cards_missing_empty', 'No missing cards')
  }
  if (ownershipScope === 'all') {
    return tr(t, 'owned_cards_all_empty', 'No cards')
  }
  return tr(t, 'owned_cards_empty', 'No owned cards')
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
      onError={(event) => applyCardListImageFallback(event.currentTarget, urls)}
    />
  )
}

interface OwnedFilterOption {
  value: string
  label: string
}

interface OwnedFilterGroupProps {
  title: string
  clearLabel: string
  options: OwnedFilterOption[]
  selected: string[]
  open: boolean
  onToggleOpen: () => void
  onToggleItem: (value: string) => void
  onClear: () => void
}

function OwnedFilterGroup({
  title,
  clearLabel,
  options,
  selected,
  open,
  onToggleOpen,
  onToggleItem,
  onClear
}: OwnedFilterGroupProps) {
  return (
    <div className={`owned-filter-group ${open ? 'is-open' : ''}`}>
      <div className="owned-filter-header">
        <button type="button" className="owned-filter-toggle" onClick={onToggleOpen}>
          <span>{title}</span>
          <span className="owned-filter-chevron">▾</span>
        </button>
        <button
          type="button"
          className="owned-filter-clear"
          onClick={onClear}
          disabled={selected.length === 0}
        >
          {clearLabel}
        </button>
      </div>
      <div className={`owned-filter-summary ${selected.length > 0 ? 'has-items' : ''}`}>
        {selected.map((value) => {
          const option = options.find((item) => item.value === value)
          return (
            <span key={`${title}-${value}`} className="owned-filter-chip">
              {option?.label ?? value}
            </span>
          )
        })}
      </div>
      <div className="owned-filter-content">
        <div className="filter-row">
          {options.map((item) => (
            <Button
              key={`${title}-${item.value}`}
              type="button"
              size="sm"
              variant={selected.includes(item.value) ? 'default' : 'outline'}
              onClick={() => onToggleItem(item.value)}
            >
              {item.label}
            </Button>
          ))}
        </div>
      </div>
    </div>
  )
}

export function OwnedCardsPage({ lang, options, assets, t }: OwnedCardsPageProps) {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = usePersistedSearchParams()

  const [accountQuery, setAccountQuery] = useState(() => searchParams.get('owned_account') ?? '')
  const [cardNameQuery, setCardNameQuery] = useState(() => searchParams.get('owned_q') ?? '')
  const deferredCardNameQuery = useDeferredValue(cardNameQuery)
  const [selectedRarity, setSelectedRarity] = useState<string[]>(() => parseSearchList(searchParams, 'owned_rarity'))
  const [selectedTypes, setSelectedTypes] = useState<string[]>(() => parseSearchList(searchParams, 'owned_type'))
  const [selectedElements, setSelectedElements] = useState<string[]>(() => parseSearchList(searchParams, 'owned_element'))
  const [selectedSetCodes, setSelectedSetCodes] = useState<string[]>(() => parseSearchList(searchParams, 'owned_set'))
  const [selectedPackNames, setSelectedPackNames] = useState<string[]>(() => parseSearchList(searchParams, 'owned_pack'))
  const [sortBy, setSortBy] = useState(() => searchParams.get('owned_sort') ?? 'acquired')
  const [ownershipScope, setOwnershipScope] = useState(() => searchParams.get('owned_scope') ?? 'owned')
  const [viewMode, setViewMode] = useState<OwnedCardsViewMode>(() => (searchParams.get('owned_view') === 'list' ? 'list' : 'grid'))
  const [gridCols, setGridCols] = useState(() => restoreOwnedGridCols())
  const [showCounts, setShowCounts] = useState(() => searchParams.get('owned_counts') !== 'hide')
  const [listPage, setListPage] = useState(() => {
    const value = Number(searchParams.get('owned_page') ?? 0)
    return Number.isFinite(value) && value >= 0 ? value : 0
  })

  const [detailCardId, setDetailCardId] = useState<number | null>(null)
  const [selectedExchangeAccountId, setSelectedExchangeAccountId] = useState<number | null>(null)
  const [targetFriendIdInput, setTargetFriendIdInput] = useState('')
  const [detailPage, setDetailPage] = useState(0)
  const [detailQ, setDetailQ] = useState('')
  const [detailSortBy, setDetailSortBy] = useState<DetailSortField>('account_id')
  const [detailSortOrder, setDetailSortOrder] = useState<'asc' | 'desc'>('asc')
  const [detailPageSize, setDetailPageSize] = useState(() => restoreDetailPageSize())
  const [detailNotice, setDetailNotice] = useState<DetailNoticeState | null>(null)
  const [detailPreviewOriginRect, setDetailPreviewOriginRect] = useState<PreviewRectLike | null>(null)
  const detailPreviewAnimatedKeyRef = useRef('')
  const detailPreviewMotionRef = useRef<HTMLDivElement | null>(null)
  const detailPreviewOriginRef = useRef<HTMLElement | null>(null)
  const exitRestoringOriginRef = useRef<HTMLElement | null>(null)
  const { hiddenOriginRef: hiddenDetailOriginRef, hideOrigin: hideDetailOrigin, restoreOrigin: restoreDetailOrigin } = usePreviewOriginVisibility()
  const {
    cardRef: detailPreviewCardRef,
    shineRef: detailPreviewShineRef,
    dragging: detailPreviewDragging,
    startDrag: startDetailPreviewDrag,
    onDragMove: onDetailPreviewDragMove,
    stopDrag: stopDetailPreviewDrag,
    resetTransform: resetDetailPreviewTransform
  } = useCardPreviewDrag()
  const [openFilterGroups, setOpenFilterGroups] = useState({
    rarity: true,
    type: false,
    set: false,
    pack: false,
    element: false
  })

  const filterOptions = useMemo(
    () => ({
      rarity: options.rarities.map((rarity) => ({
        value: rarity,
        label: t[`rarity_${rarity}`] ?? rarity
      })),
      type: options.card_types.map((cardType) => ({
        value: cardType,
        label: t[`type_${cardType}`] ?? cardType
      })),
      set: options.card_sets.map((item) => ({
        value: item.code,
        label: item.display_name
      })),
      pack: options.packs.map((item) => ({
        value: item.name,
        label: item.display_name
      })),
      element: options.elements.map((element) => ({
        value: element,
        label: t[`element_${element}`] ?? element
      }))
    }),
    [options.card_sets, options.card_types, options.elements, options.packs, options.rarities, t]
  )

  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    next.delete('owned_rarity')
    next.delete('owned_type')
    next.delete('owned_element')
    next.delete('owned_set')
    next.delete('owned_pack')
    next.delete('owned_account')
    next.delete('owned_q')
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
    if (cardNameQuery.trim()) {
      next.set('owned_q', cardNameQuery.trim())
    }
    next.set('owned_sort', sortBy)
    next.set('owned_scope', ownershipScope)
    next.set('owned_view', viewMode)
    next.set('owned_counts', showCounts ? 'show' : 'hide')
    if (viewMode === 'list') {
      next.set('owned_page', String(listPage))
    }
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true, preventScrollReset: true })
    }
  }, [
    accountQuery,
    cardNameQuery,
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

  const mainQueryState = useMemo<OwnedCardsMainQueryState>(
    () => ({
      accountId: accountQuery,
      ownershipScope,
      cardNameQuery: deferredCardNameQuery,
      rarity: selectedRarity,
      cardType: selectedTypes,
      setCode: selectedSetCodes,
      packName: selectedPackNames,
      element: selectedElements,
      sortBy,
      page: listPage,
      pageSize: OWNED_PAGE_SIZE
    }),
    [
      accountQuery,
      deferredCardNameQuery,
      ownershipScope,
      selectedRarity,
      selectedTypes,
      selectedSetCodes,
      selectedPackNames,
      selectedElements,
      sortBy,
      listPage
    ]
  )

  const mainStatsQueryParams = useMemo(
    () => buildOwnedCardsStatsQueryParams(mainQueryState),
    [mainQueryState]
  )

  const mainListBaseQueryParams = useMemo(
    () => ({
      ...mainStatsQueryParams,
      sort_by: mainQueryState.sortBy
    }),
    [mainQueryState.sortBy, mainStatsQueryParams]
  )

  const listQueryString = useMemo(
    () =>
      buildQuery({
        lang,
        ...buildOwnedCardsListQueryParams(mainQueryState)
      }),
    [lang, mainQueryState]
  )

  const statsQueryString = useMemo(
    () =>
      buildQuery({
        lang,
        ...mainStatsQueryParams
      }),
    [lang, mainStatsQueryParams]
  )

  const listQuery = useQuery({
    queryKey: ['owned-list', listQueryString],
    queryFn: () => fetchJson<OwnedCardsResponse>(`/api/react/owned-cards?${listQueryString}`),
    enabled: viewMode === 'list',
    refetchInterval: 60000
  })

  const gridQuery = useInfiniteQuery({
    queryKey: ['owned-grid', lang, mainListBaseQueryParams],
    queryFn: ({ pageParam }) =>
      fetchJson<OwnedCardsResponse>(
        `/api/react/owned-cards?${buildQuery({
          lang,
          ...mainListBaseQueryParams,
          page: pageParam,
          page_size: OWNED_PAGE_SIZE
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

  const detailQueryParams = useMemo(
    () =>
      buildOwnedCardDetailQueryParams({
        lang,
        ownershipScope,
        pageSize: detailPageSize
      }),
    [detailPageSize, lang, ownershipScope]
  )

  const detailQuery = useQuery({
    queryKey: ['owned-detail', detailCardId, lang, ownershipScope, detailPageSize],
    queryFn: () =>
      fetchJson<CardDetailResponse>(
        `/api/react/owned-cards/${detailCardId}/detail?${buildQuery(detailQueryParams)}`
      ),
    enabled: detailCardId !== null
  })

  const detailAccountsQueryState = useMemo<OwnedCardExchangeAccountsQueryState>(
    () => ({
      lang,
      q: detailQ,
      sortBy: detailSortBy,
      sortOrder: detailSortOrder,
      page: detailPage,
      pageSize: detailPageSize
    }),
    [detailPage, detailPageSize, detailQ, detailSortBy, detailSortOrder, lang]
  )

  const detailTableQueryString = useMemo(
    () =>
      detailCardId === null
        ? ''
        : buildQuery(buildOwnedCardExchangeAccountsQueryParams(detailAccountsQueryState)),
    [detailAccountsQueryState, detailCardId]
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
      setDetailNotice({
        level: 'success',
        text: result.message
      })
      setSelectedExchangeAccountId(null)
      setTargetFriendIdInput('')
      queryClient.invalidateQueries({ queryKey: ['owned-detail', detailCardId, lang] })
      queryClient.invalidateQueries({ queryKey: ['owned-detail-table', detailCardId] })
    },
    onError: (error) => {
      setDetailNotice({
        level: 'error',
        text: error instanceof Error ? error.message : tr(t, 'label_request_failed', 'Request failed')
      })
    }
  })

  const resetDetailModalState = useCallback((cardId: number | null) => {
    stopDetailPreviewDrag(false)
    resetDetailPreviewTransform(false)
    setDetailNotice(null)
    setSelectedExchangeAccountId(null)
    setTargetFriendIdInput('')
    setDetailCardId(cardId)
    setDetailPage(0)
    setDetailQ('')
    setDetailSortBy('account_id')
    setDetailSortOrder('asc')
    if (cardId === null) {
      setDetailPreviewOriginRect(null)
      detailPreviewAnimatedKeyRef.current = ''
    }
  }, [resetDetailPreviewTransform, stopDetailPreviewDrag])
  const openDetailModal = useCallback((cardId: number, originEl?: HTMLElement | null) => {
    clearCardFlipExitGhosts()
    resetDetailModalState(cardId)
    hideDetailOrigin(originEl)
    detailPreviewOriginRef.current = originEl ?? null
    setDetailPreviewOriginRect(snapshotElementRect(originEl))
    detailPreviewAnimatedKeyRef.current = ''
  }, [hideDetailOrigin, resetDetailModalState])
  const closeDetailModal = useCallback(() => {
    const cardEl = detailPreviewCardRef.current
    const motionRect = snapshotElementRect(detailPreviewMotionRef.current)
    const originRect = detailPreviewOriginRect
    const hiddenOrigin = hiddenDetailOriginRef.current
    if (cardEl && originRect && hiddenOrigin) {
      exitRestoringOriginRef.current = hiddenOrigin
      void playCardFlipExitGhost({
        from: cardEl,
        fromRect: motionRect,
        to: detailPreviewOriginRef.current,
        toRect: originRect
      }).finally(() => {
        restoreDetailOrigin(hiddenOrigin)
        if (exitRestoringOriginRef.current === hiddenOrigin) {
          exitRestoringOriginRef.current = null
        }
      })
    } else if (hiddenOrigin) {
      restoreDetailOrigin(hiddenOrigin)
    }
    resetDetailModalState(null)
    detailPreviewOriginRef.current = null
  }, [detailPreviewCardRef, detailPreviewOriginRect, resetDetailModalState, restoreDetailOrigin])

  const applyDetailSort = useCallback(
    (nextSortBy: DetailSortField) => {
      setDetailPage(0)
      if (detailSortBy === nextSortBy) {
        setDetailSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
        return
      }
      setDetailSortBy(nextSortBy)
      setDetailSortOrder('asc')
    },
    [detailSortBy]
  )

  const getDetailSortIndicator = useCallback(
    (field: DetailSortField) => {
      if (detailSortBy !== field) {
        return ''
      }
      return detailSortOrder === 'asc' ? '↑' : '↓'
    },
    [detailSortBy, detailSortOrder]
  )

  useEffect(() => {
    if (detailCardId === null) {
      stopDetailPreviewDrag(false)
      resetDetailPreviewTransform(false)
      if (exitRestoringOriginRef.current) {
        return
      }
      restoreDetailOrigin()
      return
    }
    resetDetailPreviewTransform(false)
  }, [detailCardId, resetDetailPreviewTransform, restoreDetailOrigin, stopDetailPreviewDrag])

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
    if (detailCardId === null) {
      return
    }
    const onEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') {
        return
      }
      closeDetailModal()
    }
    window.addEventListener('keydown', onEscape)
    return () => window.removeEventListener('keydown', onEscape)
  }, [closeDetailModal, detailCardId])

  useEffect(() => {
    if (detailCardId === null) {
      return
    }
    const previousOverflow = document.body.style.overflow
    const previousPaddingRight = document.body.style.paddingRight
    const scrollBarWidth = window.innerWidth - document.documentElement.clientWidth

    document.body.style.overflow = 'hidden'
    if (scrollBarWidth > 0) {
      document.body.style.paddingRight = `${scrollBarWidth}px`
    }

    return () => {
      document.body.style.overflow = previousOverflow
      document.body.style.paddingRight = previousPaddingRight
    }
  }, [detailCardId])

  useEffect(() => {
    if (selectedExchangeAccountId === null) {
      return
    }
    const rows = detailTableQuery.data?.accounts ?? []
    const stillExists = rows.some((row) => row.account_id === selectedExchangeAccountId)
    if (!stillExists) {
      setSelectedExchangeAccountId(null)
    }
  }, [detailTableQuery.data?.accounts, selectedExchangeAccountId])

  useEffect(() => {
    window.localStorage.setItem(OWNED_GRID_COLS_KEY, String(normalizeOwnedGridCols(gridCols)))
  }, [gridCols])
  const detailData = detailQuery.data?.card.id === detailCardId ? detailQuery.data : null
  const detailPreviewCacheKey = detailData
    ? `${detailData.card.id}-${detailData.card.set_code}-${detailData.card.number}`
    : ''
  const {
    imageUrls: detailPreviewImageUrls,
    cardBackImageUrl: detailCardBackImageUrl,
    effectId: detailPreviewEffectId,
    visualStyle: detailPreviewStyle
  } = useCardPreviewVisual({
    assets,
    enabled: detailCardId !== null && detailData !== null,
    setCode: detailData?.card.set_code ?? '',
    cardNumber: detailData?.card.number ?? 0,
    rarity: detailData?.card.rarity ?? '',
    cacheKey: detailPreviewCacheKey
  })

  useLayoutEffect(() => {
    if (detailCardId === null || !detailData) {
      return
    }
    let cancelled = false
    let rafId = 0
    const animationKey = `${detailCardId}-${detailData.card.id}`

    const run = () => {
      if (cancelled) {
        return
      }
      const motionEl = detailPreviewMotionRef.current
      const rotateEl = detailPreviewCardRef.current
      if (!motionEl || !rotateEl) {
        rafId = window.requestAnimationFrame(run)
        return
      }
      if (detailPreviewAnimatedKeyRef.current === animationKey) {
        return
      }
      detailPreviewAnimatedKeyRef.current = animationKey
      void playCardFlipEntrance({
        fromRect: detailPreviewOriginRect,
        to: motionEl,
        rotateTarget: rotateEl
      })
    }

    run()

    return () => {
      cancelled = true
      if (rafId !== 0) {
        window.cancelAnimationFrame(rafId)
      }
    }
  }, [detailCardId, detailData, detailPreviewMotionRef, detailPreviewCardRef, detailPreviewOriginRect])

  const gridCards = (gridQuery.data?.pages ?? []).flatMap((page) => page.items)
  const cards = viewMode === 'grid' ? gridCards : (listQuery.data?.items ?? [])
  const totalCards = viewMode === 'grid' ? (gridQuery.data?.pages[0]?.total ?? 0) : (listQuery.data?.total ?? 0)
  const gridHasNextPage = Boolean(gridQuery.data?.pages[gridQuery.data.pages.length - 1]?.has_next)
  const isFetchingNextGridPage = gridQuery.isFetchingNextPage
  const hasQueryNextGridPage = gridQuery.hasNextPage
  const fetchNextGridPage = gridQuery.fetchNextPage
  const gridLoadMore = useCallback(() => {
    if (viewMode !== 'grid') {
      return
    }
    if (!isFetchingNextGridPage && hasQueryNextGridPage) {
      void fetchNextGridPage()
    }
  }, [fetchNextGridPage, hasQueryNextGridPage, isFetchingNextGridPage, viewMode])
  const gridSentinelRef = useInfiniteTrigger({
    enabled: viewMode === 'grid' && gridHasNextPage && !isFetchingNextGridPage,
    onLoadMore: gridLoadMore
  })
  const isListLoading = viewMode === 'list' ? listQuery.isLoading : gridQuery.isLoading
  const isListError = viewMode === 'list' ? listQuery.isError : gridQuery.isError
  const listError = (viewMode === 'list' ? listQuery.error : gridQuery.error) as Error | null
  const emptyCardsText = ownedEmptyText(ownershipScope, t)
  const detailAccounts = detailTableQuery.data?.accounts ?? []
  const selectedExchangeAccount = detailAccounts.find((row) => row.account_id === selectedExchangeAccountId) ?? null
  const normalizedTargetFriendId = targetFriendIdInput.trim()
  const selectedExchangeDisabledReason = selectedExchangeAccount?.exchange_action.enabled
    ? ''
    : (selectedExchangeAccount?.exchange_action.reason_text ?? '')
  const canSubmitExchange = Boolean(
    detailData
      && selectedExchangeAccount
      && selectedExchangeAccount.exchange_action.enabled
      && normalizedTargetFriendId.length > 0
      && !exchangeMutation.isPending
  )

  const clearFilters = () => {
    setListPage(0)
    setAccountQuery('')
    setCardNameQuery('')
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
    <section className="owned-page section-stack">
      <div className="owned-page-layout">
        <aside className="owned-page-sidebar">
          <div className="surface-card section-stack">
            <div className="pagination-row">
              <h2 className="section-title">{tr(t, 'filter_title', 'Filters')}</h2>
              <Button type="button" size="sm" variant="outline" onClick={clearFilters}>
                {tr(t, 'clear_filters', 'Clear')}
              </Button>
            </div>

            <div className="filter-row">
              <input
                id="owned-account-query"
                name="owned-account-query"
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
              <input
                id="owned-card-name-query"
                name="owned-card-name-query"
                className="field-input"
                value={cardNameQuery}
                onChange={(event) => {
                  setListPage(0)
                  setCardNameQuery(event.target.value)
                }}
                placeholder={tr(t, 'filter_card_name_placeholder', 'Search card name')}
              />
            </div>

            <OwnedFilterGroup
              title={tr(t, 'filter_rarity', 'Rarity')}
              clearLabel={tr(t, 'clear_filters', 'Clear')}
              options={filterOptions.rarity}
              selected={selectedRarity}
              open={openFilterGroups.rarity}
              onToggleOpen={() => setOpenFilterGroups((prev) => ({ ...prev, rarity: !prev.rarity }))}
              onToggleItem={(value) => {
                setListPage(0)
                setSelectedRarity((prev) => toggleListItem(prev, value))
              }}
              onClear={() => {
                setListPage(0)
                setSelectedRarity([])
              }}
            />

            <OwnedFilterGroup
              title={tr(t, 'filter_type', 'Type')}
              clearLabel={tr(t, 'clear_filters', 'Clear')}
              options={filterOptions.type}
              selected={selectedTypes}
              open={openFilterGroups.type}
              onToggleOpen={() => setOpenFilterGroups((prev) => ({ ...prev, type: !prev.type }))}
              onToggleItem={(value) => {
                setListPage(0)
                setSelectedTypes((prev) => toggleListItem(prev, value))
              }}
              onClear={() => {
                setListPage(0)
                setSelectedTypes([])
              }}
            />

            <OwnedFilterGroup
              title={tr(t, 'filter_set', 'Set')}
              clearLabel={tr(t, 'clear_filters', 'Clear')}
              options={filterOptions.set}
              selected={selectedSetCodes}
              open={openFilterGroups.set}
              onToggleOpen={() => setOpenFilterGroups((prev) => ({ ...prev, set: !prev.set }))}
              onToggleItem={(value) => {
                setListPage(0)
                setSelectedSetCodes((prev) => toggleListItem(prev, value))
              }}
              onClear={() => {
                setListPage(0)
                setSelectedSetCodes([])
              }}
            />

            <OwnedFilterGroup
              title={tr(t, 'filter_pack', 'Pack')}
              clearLabel={tr(t, 'clear_filters', 'Clear')}
              options={filterOptions.pack}
              selected={selectedPackNames}
              open={openFilterGroups.pack}
              onToggleOpen={() => setOpenFilterGroups((prev) => ({ ...prev, pack: !prev.pack }))}
              onToggleItem={(value) => {
                setListPage(0)
                setSelectedPackNames((prev) => toggleListItem(prev, value))
              }}
              onClear={() => {
                setListPage(0)
                setSelectedPackNames([])
              }}
            />

            <OwnedFilterGroup
              title={tr(t, 'filter_element', 'Element')}
              clearLabel={tr(t, 'clear_filters', 'Clear')}
              options={filterOptions.element}
              selected={selectedElements}
              open={openFilterGroups.element}
              onToggleOpen={() => setOpenFilterGroups((prev) => ({ ...prev, element: !prev.element }))}
              onToggleItem={(value) => {
                setListPage(0)
                setSelectedElements((prev) => toggleListItem(prev, value))
              }}
              onClear={() => {
                setListPage(0)
                setSelectedElements([])
              }}
            />
          </div>
        </aside>

        <div className="owned-page-main section-stack">
          <div className="surface-card owned-controls-panel">
            <div className="owned-controls-row">
              <div className="owned-scope-segmented" role="group" aria-label={tr(t, 'owned_scope_label', 'Scope')}>
                {(['owned', 'missing', 'all'] as const).map((scope) => (
                  <button
                    key={`scope-${scope}`}
                    type="button"
                    className={`owned-scope-btn ${ownershipScope === scope ? 'is-active' : ''}`}
                    onClick={() => {
                      setListPage(0)
                      setOwnershipScope(scope)
                    }}
                  >
                    {tr(t, `owned_scope_${scope}`, scope)}
                  </button>
                ))}
              </div>

              <div className="filter-row">
                <span className="section-subtitle">{tr(t, 'owned_sort_label', 'Sort')}</span>
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
            </div>

            <div className="owned-controls-row">
              <div className="filter-row">
                <Button type="button" size="sm" variant={viewMode === 'grid' ? 'default' : 'outline'} onClick={() => setViewMode('grid')}>
                  {tr(t, 'view_grid', 'Grid')}
                </Button>
                <Button type="button" size="sm" variant={viewMode === 'list' ? 'default' : 'outline'} onClick={() => setViewMode('list')}>
                  {tr(t, 'view_list', 'List')}
                </Button>

                {viewMode === 'grid' && (
                  <div className="owned-cols-segmented">
                    {[4, 5, 6].map((value) => (
                      <button
                        key={`grid-${value}`}
                        type="button"
                        className={`owned-cols-btn ${gridCols === value ? 'is-active' : ''}`}
                        onClick={() => setGridCols(value)}
                      >
                        {value}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="filter-row">
                <Button type="button" size="sm" variant="outline" onClick={() => viewMode === 'grid' ? gridQuery.refetch() : listQuery.refetch()}>
                  {tr(t, 'refresh', 'Refresh')}
                </Button>
                <Button type="button" size="sm" variant="outline" onClick={() => setShowCounts((prev) => !prev)}>
                  {showCounts
                    ? tr(t, 'owned_counts_hide', 'Hide Counts')
                    : tr(t, 'owned_counts_toggle', 'Show Counts')}
                </Button>
              </div>
            </div>
          </div>

          {statsQuery.data && (
            <div className="owned-stats-bar surface-card">
              <div className="owned-stat-chip owned-stat-chip--primary">
                <span className="owned-stat-label">{tr(t, 'owned_filtered_cards_label', 'Filtered Cards')}</span>
                <span className="owned-stat-value">{statsQuery.data.filtered_cards_count}</span>
              </div>
              {statsQuery.data.rarity_progress.map((item) => (
                <div key={item.rarity} className="owned-stat-chip">
                  <span className="owned-stat-label">{t[`rarity_${item.rarity}`] ?? item.rarity}</span>
                  <span className="owned-stat-value">{item.owned_count}/{item.total_count}</span>
                </div>
              ))}
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
                  {emptyCardsText}
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
                        onClick={(event) => openDetailModal(item.card.id, event.currentTarget)}
                      >
                        <div className="owned-card-media">
                          <img
                            src={urls.png}
                            alt={item.card_display_name}
                            className="owned-card-image"
                            loading="lazy"
                            decoding="async"
                            onError={(event) => applyCardListImageFallback(event.currentTarget, urls)}
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
                        {emptyCardsText}
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
                      <td className="mono">
                        <Tooltip content={formatAbsoluteDateTime(item.latest_acquired_at)}>
                          <span>{formatRelativeDateTime(item.latest_acquired_at, lang, t)}</span>
                        </Tooltip>
                      </td>
                      <td>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={(event) => {
                            const row = event.currentTarget.closest('tr')
                            const thumb = row?.querySelector('.owned-thumb')
                            openDetailModal(item.card.id, (thumb as HTMLElement | null) ?? event.currentTarget)
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

        </div>
      </div>

      {detailCardId !== null && (
        <div
          className="dialog-overlay card-preview-overlay active"
          style={detailPreviewStyle}
          onClick={closeDetailModal}
        >
          <div className="dialog-card owned-detail-modal" onClick={(event) => event.stopPropagation()}>
            {detailCardId !== null && !detailData && detailQuery.isFetching && (
              <div className="text-sm text-muted">{tr(t, 'label_loading', 'Loading...')}</div>
            )}
            {detailQuery.isError && <div className="text-sm text-danger">{(detailQuery.error as Error).message}</div>}

            {detailData && (
              <div className="owned-card-modal-layout">
                <aside className="owned-card-modal-left">
                  <div className="surface-card section-stack">
                    <div className="section-title">{detailData.card_display_name}</div>
                    <div className="filter-row">
                      <span className="tag">{detailData.card.set_code}</span>
                      <span className="tag">#{String(detailData.card.number).padStart(3, '0')}</span>
                      <span className="tag">{detailData.card.rarity}</span>
                    </div>
                    <div className="owned-card-preview-wrap">
                      <div
                        ref={detailPreviewMotionRef}
                        className="owned-card-preview-motion"
                      >
                        <div
                          ref={detailPreviewCardRef}
                          className={`owned-card-preview card-preview-surface owned-card-draggable ${detailPreviewDragging ? 'dragging' : ''}`}
                          style={detailPreviewStyle}
                          data-preview-effect={detailPreviewEffectId}
                          onPointerDown={startDetailPreviewDrag}
                          onPointerMove={onDetailPreviewDragMove}
                        >
                          <div className="card-preview-face card-preview-front">
                            <img
                              src={detailPreviewImageUrls?.cdnPng ?? ''}
                              alt={detailData.card_display_name}
                              className="owned-card-preview-image card-preview-image"
                              loading="lazy"
                              decoding="async"
                              draggable={false}
                              onError={(event) => {
                                if (!detailPreviewImageUrls) {
                                  return
                                }
                                applyCardPreviewImageFallback(event.currentTarget, detailPreviewImageUrls)
                              }}
                            />
                            <div className="card-preview-layer card-preview-layer--foil" />
                            <div ref={detailPreviewShineRef} className="card-preview-layer card-preview-layer--glare owned-card-shine" />
                            <div className="card-preview-layer card-preview-layer--spark" />
                          </div>
                          <div className="card-preview-face card-preview-back" aria-hidden="true">
                            {detailCardBackImageUrl.length > 0 ? (
                              <img
                                src={detailCardBackImageUrl}
                                alt=""
                                className="card-preview-back-image"
                                loading="lazy"
                                decoding="async"
                                draggable={false}
                                onError={(event) => hideBrokenCardBackImage(event.currentTarget)}
                              />
                            ) : null}
                          </div>
                        </div>
                      </div>
                    </div>
                    <div className="text-xs text-muted text-center">{tr(t, 'card_preview_hint', '拖动旋转查看')}</div>
                  </div>
                </aside>

                <section className="owned-card-modal-right">
                  <div className="owned-card-modal-head">
                    <h4 className="section-title">{tr(t, 'owned_accounts_title', 'Owned Accounts')}</h4>
                    <button type="button" className="owned-card-modal-close" onClick={closeDetailModal}>✕</button>
                  </div>
                  <div className="text-xs text-muted">
                    {tr(t, 'owned_accounts_total', 'Accounts')}: {detailData.total_accounts}
                    {' ｜ '}
                    {tr(t, 'owned_count_total', 'Total Count')}: {detailData.total_count}
                  </div>
                  {detailNotice && (
                    <div className={`surface-card text-sm ${detailNotice.level === 'error' ? 'text-danger' : 'text-muted'}`}>
                      {detailNotice.text}
                    </div>
                  )}
                  <div className="owned-modal-exchange-row surface-card">
                    <div className="owned-modal-exchange-account">
                      <div className="text-xs text-muted">{tr(t, 'exchange_from_account', 'Source Account')}</div>
                      {selectedExchangeAccount ? (
                        <AccountIdentityCell
                          t={t}
                          accountId={selectedExchangeAccount.account_id}
                          name={selectedExchangeAccount.nickname || `#${selectedExchangeAccount.account_id}`}
                          friendId={selectedExchangeAccount.friend_id}
                          gameId={selectedExchangeAccount.game_id}
                        />
                      ) : (
                        <div className="mono">{tr(t, 'exchange_select_account_first', 'Select one account first')}</div>
                      )}
                    </div>
                    <div className="owned-modal-exchange-target">
                      <label
                        className="text-xs text-muted"
                        htmlFor="owned-exchange-target-friend-id"
                      >
                        {tr(t, 'exchange_input_friend_id', 'Target Friend ID')}
                      </label>
                      <input
                        id="owned-exchange-target-friend-id"
                        name="owned-exchange-target-friend-id"
                        className="field-input"
                        value={targetFriendIdInput}
                        onChange={(event) => setTargetFriendIdInput(event.target.value)}
                        placeholder={tr(t, 'exchange_input_friend_id', 'Target Friend ID')}
                      />
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      variant="default"
                      disabled={!canSubmitExchange}
                      onClick={() => {
                        if (!detailData || !selectedExchangeAccount) {
                          return
                        }
                        exchangeMutation.mutate({
                          from_account_id: selectedExchangeAccount.account_id,
                          to_account_id: null,
                          to_friend_id: normalizedTargetFriendId,
                          target_card_id: detailData.card.id,
                          target_card_rarity: detailData.card.rarity
                        })
                      }}
                    >
                      {tr(t, 'exchange_entry_action', 'Exchange')}
                    </Button>
                  </div>
                  {selectedExchangeDisabledReason.length > 0 && (
                    <div className="text-xs text-danger">{selectedExchangeDisabledReason}</div>
                  )}
                  {selectedExchangeAccount && normalizedTargetFriendId.length === 0 && (
                    <div className="text-xs text-danger">
                      {tr(t, 'exchange_friend_id_required', 'Please input target friend ID')}
                    </div>
                  )}

                  <div className="owned-modal-query-row">
                    <input
                      id="owned-modal-account-query"
                      name="owned-modal-account-query"
                      className="field-input"
                      value={detailQ}
                      onChange={(event) => {
                        setDetailPage(0)
                        setDetailQ(event.target.value)
                      }}
                      placeholder={tr(t, 'exchange_search_accounts', 'Search Account ID / nickname / friend id')}
                    />
                    <Select
                      value={encodeSelectValue(detailSortBy)}
                      onValueChange={(value) => {
                        setDetailPage(0)
                        setDetailSortBy(decodeSelectValue(value) as DetailSortField)
                      }}
                    >
                      <SelectTrigger className="field-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="account_id">{tr(t, 'col_account_id', 'Account ID')}</SelectItem>
                        <SelectItem value="friend_id">{tr(t, 'col_friend_id', 'Friend ID')}</SelectItem>
                        <SelectItem value="nickname">{tr(t, 'col_nickname', 'Nickname')}</SelectItem>
                        <SelectItem value="count">{tr(t, 'col_count', 'Count')}</SelectItem>
                        <SelectItem value="exchange_points">{tr(t, 'col_exchange_points', 'Exchange Points')}</SelectItem>
                      </SelectContent>
                    </Select>
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
                    <Button type="button" size="sm" variant="outline" onClick={() => detailTableQuery.refetch()}>
                      {tr(t, 'refresh', 'Refresh')}
                    </Button>
                  </div>

                  <div className="owned-card-modal-table-shell">
                    <div className="owned-card-exchange-table-frame">
                      <table className="grid-table">
                        <thead>
                          <tr>
                            <th className="table-col-account">
                              <button type="button" className="owned-modal-sort-btn" onClick={() => applyDetailSort('account_id')}>
                                {tr(t, 'col_account', 'Account')} {getDetailSortIndicator('account_id')}
                              </button>
                            </th>
                            <th className="table-col-count">
                              <button type="button" className="owned-modal-sort-btn" onClick={() => applyDetailSort('count')}>
                                {tr(t, 'col_count', 'Count')} {getDetailSortIndicator('count')}
                              </button>
                            </th>
                            <th className="table-col-count">
                              <button type="button" className="owned-modal-sort-btn" onClick={() => applyDetailSort('exchange_points')}>
                                {tr(t, 'col_exchange_points', 'Exchange Points')} {getDetailSortIndicator('exchange_points')}
                              </button>
                            </th>
                            <th className="table-col-actions">{tr(t, 'col_actions', 'Actions')}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {detailAccounts.length === 0 && (
                            <tr>
                              <td colSpan={4} className="text-center text-muted">{tr(t, 'exchange_entry_no_available_accounts', 'No eligible accounts')}</td>
                            </tr>
                          )}
                          {detailAccounts.map((row) => {
                            const isSelectedRow = selectedExchangeAccountId === row.account_id
                            return (
                              <tr key={row.account_id} className={isSelectedRow ? 'owned-exchange-row--selected' : ''}>
                                <td className="table-col-account">
                                  <AccountIdentityCell
                                    t={t}
                                    accountId={row.account_id}
                                    name={row.nickname || `#${row.account_id}`}
                                    friendId={row.friend_id}
                                    gameId={row.game_id}
                                  />
                                </td>
                                <td className="mono table-col-count">{row.count}</td>
                                <td className="mono table-col-count">{row.exchange_points ?? '-'}</td>
                                <td className="table-col-actions">
                                  {row.exchange_action.enabled ? (
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant={isSelectedRow ? 'default' : 'outline'}
                                      disabled={exchangeMutation.isPending}
                                      onClick={() => {
                                        setSelectedExchangeAccountId(row.account_id)
                                        setDetailNotice(null)
                                      }}
                                    >
                                      {isSelectedRow
                                        ? tr(t, 'exchange_source_account_selected', '已选为来源')
                                        : tr(t, 'exchange_set_source_account', '设为来源')}
                                    </Button>
                                  ) : (
                                    <Tooltip content={reasonTitle(row.exchange_action.reason_text) ?? ''}>
                                      <Button
                                        type="button"
                                        size="sm"
                                        variant="outline"
                                        disabled
                                      >
                                        {tr(t, 'exchange_entry_action', 'Exchange')}
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
                    <div className="pagination-row">
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
                </section>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
