import { useCallback, useDeferredValue, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { useCardPreviewDrag } from '@/hooks/use-card-preview-drag'
import { useCardPreviewVisual } from '@/hooks/use-card-preview-visual'
import { useInfiniteTrigger } from '@/hooks/use-infinite-trigger'
import { usePersistedSearchParams } from '@/hooks/use-persisted-search-params'
import { usePreviewOriginVisibility } from '@/hooks/use-preview-origin-visibility'
import { buildQuery, fetchJson } from '@/lib/api'
import { applyCardListImageFallback, applyCardPreviewImageFallback } from '@/lib/card-image-fallback'
import { getCardImageUrls, type CardImageAssets } from '@/lib/card-image'
import { hideBrokenCardBackImage } from '@/lib/card-preview-assets'
import { clearCardFlipExitGhosts, playCardFlipEntrance, playCardFlipExitGhost, snapshotElementRect, type PreviewRectLike } from '@/lib/flip-transition'
import { tr } from '@/lib/i18n'
import { toggleListItem } from '@/lib/list-utils'
import { formatAbsoluteDateTime, formatRelativeDateTime } from '@/lib/time-display'
import type { BootstrapOptions } from '@/types/api'

import {
  buildRecordsApiQueryParams,
  buildRecordsSearchParams,
  parseRecordsSearchState,
  type RecordsViewMode
} from './records-query'

interface RecordsPageProps {
  lang: string
  options: BootstrapOptions
  assets: CardImageAssets
  t: Record<string, string>
}

interface RecordCardView {
  display_name: string
  card_name?: string
  rarity: string
  is_new: boolean
  position: number
  set_code?: string
  card_number?: number
  card?: {
    set_code?: string
    number?: number
    image_url?: string | null
  }
}

interface RecordMeta {
  set_code?: string
}

interface BatchPackView {
  cards: RecordCardView[]
  batch_index: number
  cover_card?: RecordCardView | null
  max_rarity?: string
  has_new?: boolean
}

interface RecordListItem {
  is_batch: boolean
  batch_id?: string
  account_name: string
  opened_at: string
  set_name_display: string
  pack_name_display: string
  pack_type_display: string
  cards?: RecordCardView[]
  batch_packs?: BatchPackView[]
  total_cards?: number
  current_points?: number | null
  series?: string
  layout?: string
  record?: RecordMeta
}

interface RecordsResponse {
  items: RecordListItem[]
  page: number
  has_prev: boolean
  has_next: boolean
  total: number
}

interface PreviewState {
  title: string
  rarity: string
  setCode: string
  cardNumber: number
}

const RECORDS_PAGE_SIZE = 10
const RECORDS_VIEW_MODE_KEY = 'ptcgp_view_mode'

function resolveStoredViewMode(): RecordsViewMode {
  const stored = window.localStorage.getItem(RECORDS_VIEW_MODE_KEY)
  return stored === 'list' ? 'list' : 'grid'
}

function resolveLayoutByCount(cardCount: number): string {
  if (cardCount === 6) {
    return 'layout-6'
  }
  if (cardCount === 5) {
    return 'layout-5'
  }
  if (cardCount === 4) {
    return 'layout-4'
  }
  return 'layout-3'
}

function resolveRecordSetCode(item: RecordListItem): string {
  const primary = item.series?.trim()
  if (primary) {
    return primary
  }
  const nested = item.record?.set_code?.trim()
  if (nested) {
    return nested
  }
  return ''
}

function resolveCardImageMeta(card: {
  set_code?: string
  card_number?: number
  card?: {
    set_code?: string
    number?: number
  }
}): { setCode: string; cardNumber: number; hasImage: boolean } {
  const setCode = card.set_code ?? card.card?.set_code ?? ''
  const cardNumber = Number(card.card_number ?? card.card?.number ?? 0)
  return { setCode, cardNumber, hasImage: setCode.length > 0 && cardNumber > 0 }
}

function RecordCardTile({
  card,
  assets,
  t,
  onPreview
}: {
  card: RecordCardView
  assets: CardImageAssets
  t: Record<string, string>
  onPreview: (card: PreviewState, originEl: HTMLElement) => void
}) {
  const { setCode, cardNumber, hasImage } = resolveCardImageMeta(card)

  const urls = getCardImageUrls(assets, {
    setCode,
    cardNumber
  })

  return (
    <div className="record-card-tile">
      <button
        type="button"
        className="unstyled-btn"
        onClick={(event) =>
          onPreview({
            title: card.display_name,
            rarity: card.rarity,
            setCode,
            cardNumber
          }, event.currentTarget)
        }
      >
        {hasImage ? (
          <img
            src={urls.png}
            alt={card.display_name}
            className="record-card-image"
            loading="lazy"
            decoding="async"
            onError={(event) => applyCardListImageFallback(event.currentTarget, urls)}
          />
        ) : (
          <div className="record-card-fallback">{tr(t, 'no_image', 'No Image')}</div>
        )}
      </button>
      {card.rarity ? <span className="record-card-rarity" title={card.rarity}>{card.rarity}</span> : null}
      {card.is_new ? <span className="record-card-new">{tr(t, 'new_badge', 'NEW')}</span> : null}
      <div className="record-card-name" title={card.display_name || card.card_name || '-'}>
        {card.display_name || card.card_name || '-'}
      </div>
    </div>
  )
}

function BatchOverviewTile({
  pack,
  assets,
  t,
  onSelect
}: {
  pack: BatchPackView
  assets: CardImageAssets
  t: Record<string, string>
  onSelect: (packIndex: number) => void
}) {
  const cover = pack.cover_card ?? null
  const { setCode, cardNumber, hasImage } = resolveCardImageMeta(cover ?? {})
  const urls = getCardImageUrls(assets, { setCode, cardNumber })

  return (
    <button type="button" className="record-batch-pack" onClick={() => onSelect(pack.batch_index)}>
      {hasImage ? (
        <img
          src={urls.png}
          alt={cover?.display_name ?? `${tr(t, 'pack_number', 'Pack')} ${pack.batch_index}`}
          className="record-card-image"
          loading="lazy"
          decoding="async"
          onError={(event) => applyCardListImageFallback(event.currentTarget, urls)}
        />
      ) : (
        <div className="record-batch-pack-fallback">{pack.max_rarity || '☆'}</div>
      )}
      <div className="record-batch-pack-index">#{pack.batch_index}</div>
      {pack.has_new ? <div className="record-batch-pack-new">{tr(t, 'new_badge', 'NEW')}</div> : null}
      {pack.max_rarity ? <div className="record-batch-pack-rarity">{pack.max_rarity}</div> : null}
    </button>
  )
}

export function RecordsPage({ lang, options, assets, t }: RecordsPageProps) {
  const [searchParams, setSearchParams] = usePersistedSearchParams()
  const [selectedRarity, setSelectedRarity] = useState<string[]>(
    () => parseRecordsSearchState(searchParams).selectedRarity
  )
  const [selectedTypes, setSelectedTypes] = useState<string[]>(
    () => parseRecordsSearchState(searchParams).selectedTypes
  )
  const [selectedSetCodes, setSelectedSetCodes] = useState<string[]>(
    () => parseRecordsSearchState(searchParams).selectedSetCodes
  )
  const [cardNameQuery, setCardNameQuery] = useState(
    () => parseRecordsSearchState(searchParams).cardNameQuery
  )
  const deferredCardNameQuery = useDeferredValue(cardNameQuery)
  const [viewMode, setViewMode] = useState<RecordsViewMode>(
    () => parseRecordsSearchState(searchParams, { fallbackView: resolveStoredViewMode() }).viewMode
  )
  const [previewCard, setPreviewCard] = useState<PreviewState | null>(null)
  const [previewOriginRect, setPreviewOriginRect] = useState<PreviewRectLike | null>(null)
  const [activeBatchPack, setActiveBatchPack] = useState<Record<string, number | null>>({})
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false)
  const previewMotionRef = useRef<HTMLDivElement | null>(null)
  const previewOriginRef = useRef<HTMLElement | null>(null)
  const exitRestoringOriginRef = useRef<HTMLElement | null>(null)
  const previewAnimatedKeyRef = useRef('')
  const { hiddenOriginRef: hiddenPreviewOriginRef, hideOrigin: hidePreviewOrigin, restoreOrigin: restorePreviewOrigin } = usePreviewOriginVisibility()
  const {
    cardRef: previewCardRef,
    shineRef: previewShineRef,
    dragging: previewDragging,
    startDrag: startPreviewDrag,
    onDragMove: onPreviewDragMove,
    stopDrag: stopPreviewDrag,
    resetTransform: resetPreviewTransform
  } = useCardPreviewDrag()
  const resetPreviewState = useCallback(() => {
    stopPreviewDrag(false)
    resetPreviewTransform(false)
  }, [resetPreviewTransform, stopPreviewDrag])

  useEffect(() => {
    const next = buildRecordsSearchParams(
      {
        selectedRarity,
        selectedTypes,
        selectedSetCodes,
        cardNameQuery,
        viewMode
      },
      searchParams
    )
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true, preventScrollReset: true })
    }
  }, [cardNameQuery, searchParams, selectedRarity, selectedSetCodes, selectedTypes, setSearchParams, viewMode])

  useEffect(() => {
    window.localStorage.setItem(RECORDS_VIEW_MODE_KEY, viewMode)
  }, [viewMode])

  const closePreview = useCallback(() => {
    const cardEl = previewCardRef.current
    const motionRect = snapshotElementRect(previewMotionRef.current)
    const originRect = previewOriginRect
    const hiddenOrigin = hiddenPreviewOriginRef.current
    if (cardEl && originRect && hiddenOrigin) {
      exitRestoringOriginRef.current = hiddenOrigin
      void playCardFlipExitGhost({
        from: cardEl,
        fromRect: motionRect,
        to: previewOriginRef.current,
        toRect: originRect
      }).finally(() => {
        restorePreviewOrigin(hiddenOrigin)
        if (exitRestoringOriginRef.current === hiddenOrigin) {
          exitRestoringOriginRef.current = null
        }
      })
    } else if (hiddenOrigin) {
      restorePreviewOrigin(hiddenOrigin)
    }
    resetPreviewState()
    setPreviewCard(null)
    setPreviewOriginRect(null)
    previewOriginRef.current = null
    previewAnimatedKeyRef.current = ''
  }, [previewCardRef, previewOriginRect, resetPreviewState, restorePreviewOrigin])

  const openPreview = useCallback(
    (card: PreviewState, originEl: HTMLElement) => {
      clearCardFlipExitGhosts()
      resetPreviewState()
      previewOriginRef.current = originEl
      hidePreviewOrigin(originEl)
      setPreviewOriginRect(snapshotElementRect(originEl))
      setPreviewCard(card)
    },
    [hidePreviewOrigin, resetPreviewState]
  )

  useEffect(() => {
    if (!previewCard) {
      resetPreviewState()
      if (exitRestoringOriginRef.current) {
        return
      }
      restorePreviewOrigin()
      return
    }
    resetPreviewTransform(false)
  }, [previewCard, resetPreviewState, resetPreviewTransform, restorePreviewOrigin])

  useLayoutEffect(() => {
    if (!previewCard) {
      return
    }
    let cancelled = false
    let rafId = 0
    const animationKey = `${previewCard.setCode}-${previewCard.cardNumber}-${previewCard.title}`

    const run = () => {
      if (cancelled) {
        return
      }
      const motionEl = previewMotionRef.current
      const rotateEl = previewCardRef.current
      if (!motionEl || !rotateEl) {
        rafId = window.requestAnimationFrame(run)
        return
      }
      if (previewAnimatedKeyRef.current === animationKey) {
        return
      }
      previewAnimatedKeyRef.current = animationKey
      void playCardFlipEntrance({
        fromRect: previewOriginRect,
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
  }, [previewCard, previewOriginRect, previewCardRef])

  useEffect(() => {
    if (!previewCard) {
      return
    }
    const onEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') {
        return
      }
      closePreview()
    }
    window.addEventListener('keydown', onEscape)
    return () => window.removeEventListener('keydown', onEscape)
  }, [closePreview, previewCard])

  const recordsQueryBaseParams = useMemo(
    () => buildQuery(
      buildRecordsApiQueryParams({
        lang,
        page: 0,
        pageSize: RECORDS_PAGE_SIZE,
        selectedRarity,
        selectedTypes,
        selectedSetCodes,
        cardNameQuery: deferredCardNameQuery
      })
    ),
    [deferredCardNameQuery, lang, selectedRarity, selectedSetCodes, selectedTypes]
  )

  const query = useInfiniteQuery({
    queryKey: ['records', recordsQueryBaseParams],
    queryFn: ({ pageParam }) =>
      fetchJson<RecordsResponse>(
        `/api/react/records?${buildQuery({
          ...buildRecordsApiQueryParams({
            lang,
            page: Number(pageParam),
            pageSize: RECORDS_PAGE_SIZE,
            selectedRarity,
            selectedTypes,
            selectedSetCodes,
            cardNameQuery: deferredCardNameQuery
          })
        })}`
      ),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => (lastPage.has_next ? lastPage.page + 1 : undefined),
    refetchInterval: 60000
  })
  const previewCacheKey = previewCard
    ? `${previewCard.setCode}-${previewCard.cardNumber}-${previewCard.title}`
    : ''
  const {
    imageUrls: previewImageUrls,
    cardBackImageUrl: previewCardBackImageUrl,
    effectId: previewEffectId,
    visualStyle: previewVisualStyle
  } = useCardPreviewVisual({
    assets,
    enabled: previewCard !== null,
    setCode: previewCard?.setCode ?? '',
    cardNumber: previewCard?.cardNumber ?? 0,
    rarity: previewCard?.rarity ?? '',
    cacheKey: previewCacheKey
  })

  const pages = query.data?.pages ?? []
  const records = pages.flatMap((page) => page.items)
  const total = pages[0]?.total ?? 0
  const hasNextPage = Boolean(pages[pages.length - 1]?.has_next)
  const isFetchingNextRecordsPage = query.isFetchingNextPage
  const hasQueryNextRecordsPage = query.hasNextPage
  const fetchNextRecordsPage = query.fetchNextPage

  const sentinelRef = useInfiniteTrigger({
    enabled: hasNextPage && !isFetchingNextRecordsPage,
    onLoadMore: useCallback(() => {
      if (!isFetchingNextRecordsPage && hasQueryNextRecordsPage) {
        void fetchNextRecordsPage()
      }
    }, [fetchNextRecordsPage, hasQueryNextRecordsPage, isFetchingNextRecordsPage])
  })

  const clearFilters = () => {
    setSelectedRarity([])
    setSelectedTypes([])
    setSelectedSetCodes([])
    setCardNameQuery('')
  }

  return (
    <section className="records-page section-stack">
      <div className="surface-card records-filter-shell">
        <div className="records-filters-mobile-trigger">
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="records-filter-toggle-btn"
            onClick={() => setMobileFiltersOpen((prev) => !prev)}
          >
            {tr(t, 'filter_title', 'Filters')}
          </Button>
        </div>

        <div className={`records-filter-panel ${mobileFiltersOpen ? 'is-open' : 'is-collapsed'}`}>
          <div className="records-filter-toolbar">
            <div className="records-filter-tool-group">
              <span className="records-filter-label">{tr(t, 'view_mode', 'View')}</span>
              <Button
                type="button"
                size="sm"
                variant={viewMode === 'list' ? 'default' : 'outline'}
                onClick={() => setViewMode('list')}
              >
                {tr(t, 'view_list', 'List')}
              </Button>
              <Button
                type="button"
                size="sm"
                variant={viewMode === 'grid' ? 'default' : 'outline'}
                onClick={() => setViewMode('grid')}
              >
                {tr(t, 'view_grid', 'Grid')}
              </Button>
            </div>

            <div className="records-filter-tool-group records-filter-actions">
              <Button type="button" size="sm" variant="outline" onClick={() => query.refetch()}>
                {tr(t, 'refresh', 'Refresh')}
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={clearFilters}>
                {tr(t, 'clear_filters', 'Clear')}
              </Button>
            </div>
          </div>

          <div className="records-filter-group">
            <div className="records-filter-group-title">{tr(t, 'filter_card_name', 'Card Name')}</div>
            <input
              id="records-card-name-query"
              name="records-card-name-query"
              className="field-input records-filter-search"
              value={cardNameQuery}
              onChange={(event) => setCardNameQuery(event.target.value)}
              placeholder={tr(t, 'filter_card_name_placeholder', 'Search card name')}
            />
          </div>

          <div className="records-filter-group">
            <div className="records-filter-group-title">{tr(t, 'filter_set', 'Set')}</div>
            <div className="records-filter-chip-row">
              {options.card_sets.map((item) => (
                <Button
                  key={item.code}
                  type="button"
                  size="sm"
                  variant={selectedSetCodes.includes(item.code) ? 'default' : 'outline'}
                  onClick={() => setSelectedSetCodes((prev) => toggleListItem(prev, item.code))}
                >
                  {item.display_name}
                </Button>
              ))}
            </div>
          </div>

          <div className="records-filter-group">
            <div className="records-filter-group-title">{tr(t, 'filter_rarity', 'Rarity')}</div>
            <div className="records-filter-chip-row">
              {options.rarities.map((rarity) => (
                <Button
                  key={rarity}
                  type="button"
                  size="sm"
                  variant={selectedRarity.includes(rarity) ? 'default' : 'outline'}
                  onClick={() => setSelectedRarity((prev) => toggleListItem(prev, rarity))}
                >
                  {t[`rarity_${rarity}`] ?? rarity}
                </Button>
              ))}
            </div>
          </div>

          <div className="records-filter-group">
            <div className="records-filter-group-title">{tr(t, 'filter_type', 'Type')}</div>
            <div className="records-filter-chip-row">
              {options.card_types.map((cardType) => (
                <Button
                  key={cardType}
                  type="button"
                  size="sm"
                  variant={selectedTypes.includes(cardType) ? 'default' : 'outline'}
                  onClick={() => setSelectedTypes((prev) => toggleListItem(prev, cardType))}
                >
                  {t[`type_${cardType}`] ?? cardType}
                </Button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {query.isLoading && <div className="surface-card text-sm text-muted">{tr(t, 'label_loading', 'Loading...')}</div>}
      {query.isError && <div className="surface-card text-sm text-danger">{(query.error as Error).message}</div>}

      {pages.length > 0 && (
        <>
          {records.length === 0 && <div className="surface-card text-sm text-muted">{tr(t, 'end_of_records', 'No records')}</div>}

          <div className={`records-list ${viewMode === 'list' ? 'records-list--list' : 'records-list--grid'}`}>
            {records.map((item, index) => {
              const batchPacks = item.batch_packs ?? []
              const isBatchRecord = item.is_batch || batchPacks.length > 0
              const cardCount = isBatchRecord ? Number(item.total_cards ?? 0) : Number(item.cards?.length ?? 0)
              const layoutClass = item.layout || resolveLayoutByCount(isBatchRecord ? 3 : cardCount)
              const batchKey = item.batch_id || `${item.opened_at}-${index}`
              const selectedPackIndex = activeBatchPack[batchKey] ?? null
              const selectedPack = selectedPackIndex === null
                ? null
                : batchPacks.find((pack) => pack.batch_index === selectedPackIndex) ?? null
              const setCode = resolveRecordSetCode(item)

              return (
                <article key={`${item.opened_at}-${index}`} className="records-entry">
                  <aside className="records-meta-rail">
                    <div className="records-meta-top">
                      {setCode ? <span className="records-set-badge">{setCode}</span> : null}
                      <span className="records-pack-type">{item.pack_type_display}</span>
                    </div>

                    <h2 className="records-pack-name">
                      {setCode ? item.pack_name_display || item.set_name_display : item.pack_type_display}
                    </h2>

                    <div className="records-account">
                      {tr(t, 'col_account', 'Account')} · {item.account_name}
                    </div>

                    <div className="records-divider" aria-hidden="true" />

                    <div className="records-meta-bottom">
                      <div className="records-time" title={formatAbsoluteDateTime(item.opened_at)}>
                        {formatRelativeDateTime(item.opened_at, lang, t)}
                      </div>
                      <div className="records-metric-row">
                        <span className="records-metric-chip">{cardCount} {tr(t, 'cards_count_suffix', 'Cards')}</span>
                        {item.current_points !== null && item.current_points !== undefined ? (
                          <span className="records-metric-chip records-metric-chip--accent">PT {item.current_points}</span>
                        ) : null}
                      </div>
                    </div>
                  </aside>

                  <div className="records-content-panel">
                    {!isBatchRecord && (
                      <div className={`pack-grid record-card-grid ${layoutClass}`}>
                        {(item.cards ?? []).map((card) => (
                          <RecordCardTile
                            key={`${item.opened_at}-${card.position}-${card.display_name}`}
                            card={card}
                            assets={assets}
                            t={t}
                            onPreview={openPreview}
                          />
                        ))}
                      </div>
                    )}

                    {isBatchRecord && (
                      <>
                        {batchPacks.length > 0 && selectedPack === null ? (
                          <div className="record-batch-overview-grid">
                            {batchPacks.map((pack) => (
                              <BatchOverviewTile
                                key={`${batchKey}-${pack.batch_index}`}
                                pack={pack}
                                assets={assets}
                                t={t}
                                onSelect={(packIndex) => {
                                  setActiveBatchPack((prev) => ({ ...prev, [batchKey]: packIndex }))
                                }}
                              />
                            ))}
                          </div>
                        ) : batchPacks.length > 0 && selectedPack ? (
                          <div className="records-batch-detail">
                            <div className="records-batch-detail-head">
                              <div className="text-xs text-muted">
                                {tr(t, 'pack_number', 'Pack')} {selectedPack.batch_index}
                              </div>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => setActiveBatchPack((prev) => ({ ...prev, [batchKey]: null }))}
                              >
                                {tr(t, 'btn_back_to_overview', 'Overview')}
                              </Button>
                            </div>
                            <div className={`pack-grid record-card-grid ${resolveLayoutByCount(selectedPack.cards.length)}`}>
                              {selectedPack.cards.map((card) => (
                                <RecordCardTile
                                  key={`${selectedPack.batch_index}-${card.position}-${card.display_name}`}
                                  card={card}
                                  assets={assets}
                                  t={t}
                                  onPreview={openPreview}
                                />
                              ))}
                            </div>
                          </div>
                        ) : (
                          <div className="text-xs text-muted">{tr(t, 'label_no_data', 'No data')}</div>
                        )}
                      </>
                    )}
                  </div>
                </article>
              )
            })}
          </div>

          <div className="surface-card section-stack">
            <div className="text-xs text-muted">{tr(t, 'total_text', 'Total')}: {total}</div>
            {query.isFetchingNextPage && (
              <div className="text-xs text-muted">{tr(t, 'label_loading_more', 'Loading more...')}</div>
            )}
            {!hasNextPage && records.length > 0 && (
              <div className="text-xs text-muted">{tr(t, 'label_reach_end', 'Reached the end')}</div>
            )}
            <div ref={sentinelRef} className="infinite-sentinel" />
          </div>
        </>
      )}

      {previewCard && (
        <div
          className="dialog-overlay card-preview-overlay active"
          style={previewVisualStyle}
          onClick={closePreview}
        >
          <div className="card-preview-container" onClick={(event) => event.stopPropagation()}>
            <div
              ref={previewMotionRef}
              className="card-preview-motion"
            >
              <div
                ref={previewCardRef}
                className={`card-preview-card card-preview-surface ${previewDragging ? 'dragging' : ''}`}
                style={previewVisualStyle}
                data-preview-effect={previewEffectId}
                onPointerDown={startPreviewDrag}
                onPointerMove={onPreviewDragMove}
              >
                <div className="card-preview-face card-preview-front">
                  <img
                    src={previewImageUrls?.cdnPng ?? ''}
                    alt={previewCard.title}
                    className="card-preview-image"
                    onError={(event) => {
                      if (!previewImageUrls) {
                        return
                      }
                      applyCardPreviewImageFallback(event.currentTarget, previewImageUrls)
                    }}
                  />
                  <div className="card-preview-layer card-preview-layer--foil" />
                  <div ref={previewShineRef} className="card-preview-layer card-preview-layer--glare card-preview-shine" />
                  <div className="card-preview-layer card-preview-layer--spark" />
                </div>
                <div className="card-preview-face card-preview-back" aria-hidden="true">
                  {previewCardBackImageUrl.length > 0 ? (
                    <img
                      src={previewCardBackImageUrl}
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
            <div className="card-preview-info">
              <div className="card-preview-name">{previewCard.title}</div>
              <div className="card-preview-meta">
                <span className="card-preview-rarity">{previewCard.rarity}</span>
                <span className="card-preview-set">{previewCard.setCode}</span>
                <span className="card-preview-number">#{String(previewCard.cardNumber).padStart(3, '0')}</span>
              </div>
            </div>
            <div className="card-preview-hint">{tr(t, 'card_preview_hint', '拖动旋转查看 / Drag to rotate')}</div>
          </div>
        </div>
      )}
    </section>
  )
}
