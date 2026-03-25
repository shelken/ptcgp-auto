import { useCallback, useEffect, useMemo, useState } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { useCardPreviewDrag } from '@/hooks/use-card-preview-drag'
import { useInfiniteTrigger } from '@/hooks/use-infinite-trigger'
import { usePersistedSearchParams } from '@/hooks/use-persisted-search-params'
import { buildQuery, fetchJson } from '@/lib/api'
import { applyImageFallback } from '@/lib/card-image-fallback'
import { getCardImageUrls, type CardImageAssets } from '@/lib/card-image'
import { tr } from '@/lib/i18n'
import { parseSearchList, toggleListItem } from '@/lib/list-utils'
import { formatAbsoluteDateTime, formatRelativeDateTime } from '@/lib/time-display'
import type { BootstrapOptions } from '@/types/api'

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

function RecordCardTile({
  card,
  assets,
  t,
  onPreview
}: {
  card: RecordCardView
  assets: CardImageAssets
  t: Record<string, string>
  onPreview: (card: PreviewState) => void
}) {
  const setCode = card.set_code ?? card.card?.set_code ?? ''
  const cardNumber = Number(card.card_number ?? card.card?.number ?? 0)
  const hasImage = setCode.length > 0 && cardNumber > 0

  const urls = getCardImageUrls(assets, {
    setCode,
    cardNumber
  })

  return (
    <div className="record-card-tile">
      <button
        type="button"
        className="unstyled-btn"
        onClick={() =>
          onPreview({
            title: card.display_name,
            rarity: card.rarity,
            setCode,
            cardNumber
          })
        }
      >
        {hasImage ? (
          <img
            src={urls.png}
            alt={card.display_name}
            className="record-card-image"
            loading="lazy"
            decoding="async"
            onError={(event) => applyImageFallback(event.currentTarget, [urls.webp, urls.cdnPng, urls.cdnWebp])}
          />
        ) : (
          <div className="record-card-fallback">{tr(t, 'no_image', 'No Image')}</div>
        )}
      </button>
      <div className="record-card-meta">
        <span className="record-card-rarity" title={card.rarity}>{card.rarity}</span>
        {card.is_new ? <span className="record-card-new">{tr(t, 'new_badge', 'NEW')}</span> : null}
      </div>
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
  const setCode = cover?.set_code ?? cover?.card?.set_code ?? ''
  const cardNumber = Number(cover?.card_number ?? cover?.card?.number ?? 0)
  const hasImage = setCode.length > 0 && cardNumber > 0
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
          onError={(event) => applyImageFallback(event.currentTarget, [urls.webp, urls.cdnPng, urls.cdnWebp])}
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
  const RECORDS_VIEW_MODE_KEY = 'ptcgp_view_mode'

  const [searchParams, setSearchParams] = usePersistedSearchParams()
  const [selectedRarity, setSelectedRarity] = useState<string[]>(() => parseSearchList(searchParams, 'records_rarity'))
  const [selectedTypes, setSelectedTypes] = useState<string[]>(() => parseSearchList(searchParams, 'records_type'))
  const [viewMode, setViewMode] = useState<'grid' | 'list'>(() => {
    const stored = window.localStorage.getItem(RECORDS_VIEW_MODE_KEY)
    return stored === 'list' ? 'list' : 'grid'
  })
  const [previewCard, setPreviewCard] = useState<PreviewState | null>(null)
  const [activeBatchPack, setActiveBatchPack] = useState<Record<string, number | null>>({})
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false)
  const {
    cardRef: previewCardRef,
    shineRef: previewShineRef,
    dragging: previewDragging,
    startDrag: startPreviewDrag,
    stopDrag: stopPreviewDrag,
    resetTransform: resetPreviewTransform
  } = useCardPreviewDrag()

  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    next.delete('records_rarity')
    next.delete('records_type')
    next.delete('records_view')
    selectedRarity.forEach((item) => next.append('records_rarity', item))
    selectedTypes.forEach((item) => next.append('records_type', item))
    next.set('records_view', viewMode)
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true, preventScrollReset: true })
    }
  }, [searchParams, selectedRarity, selectedTypes, setSearchParams, viewMode])

  useEffect(() => {
    window.localStorage.setItem(RECORDS_VIEW_MODE_KEY, viewMode)
  }, [viewMode])

  const closePreview = useCallback(() => {
    stopPreviewDrag(false)
    resetPreviewTransform(false)
    setPreviewCard(null)
  }, [resetPreviewTransform, stopPreviewDrag])

  const openPreview = useCallback(
    (card: PreviewState) => {
      stopPreviewDrag(false)
      resetPreviewTransform(false)
      setPreviewCard(card)
    },
    [resetPreviewTransform, stopPreviewDrag]
  )

  useEffect(() => {
    if (!previewCard) {
      stopPreviewDrag(false)
      resetPreviewTransform(false)
      return
    }
    resetPreviewTransform(false)
  }, [previewCard, resetPreviewTransform, stopPreviewDrag])

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

  const queryBaseString = useMemo(
    () =>
      buildQuery({
        page_size: 10,
        lang,
        rarity: selectedRarity,
        card_type: selectedTypes
      }),
    [lang, selectedRarity, selectedTypes]
  )

  const query = useInfiniteQuery({
    queryKey: ['records', queryBaseString],
    queryFn: ({ pageParam }) =>
      fetchJson<RecordsResponse>(
        `/api/react/records?${buildQuery({
          page: pageParam,
          page_size: 10,
          lang,
          rarity: selectedRarity,
          card_type: selectedTypes
        })}`
      ),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => (lastPage.has_next ? lastPage.page + 1 : undefined),
    refetchInterval: 60000
  })

  const pages = query.data?.pages ?? []
  const records = pages.flatMap((page) => page.items)
  const total = pages[0]?.total ?? 0
  const hasNextPage = Boolean(pages[pages.length - 1]?.has_next)

  const sentinelRef = useInfiniteTrigger({
    enabled: hasNextPage && !query.isFetchingNextPage,
    onLoadMore: useCallback(() => {
      if (!query.isFetchingNextPage && query.hasNextPage) {
        void query.fetchNextPage()
      }
    }, [query])
  })

  const clearFilters = () => {
    setSelectedRarity([])
    setSelectedTypes([])
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
          onClick={closePreview}
        >
          <div className="card-preview-container" onClick={(event) => event.stopPropagation()}>
            <div
              ref={previewCardRef}
              className={`card-preview-card ${previewDragging ? 'dragging' : ''}`}
              onPointerDown={startPreviewDrag}
            >
              <div className="card-preview-front">
                <img
                  src={getCardImageUrls(assets, {
                    setCode: previewCard.setCode,
                    cardNumber: previewCard.cardNumber
                  }).cdnPng}
                  alt={previewCard.title}
                  className="card-preview-image"
                  onError={(event) => {
                    const urls = getCardImageUrls(assets, {
                      setCode: previewCard.setCode,
                      cardNumber: previewCard.cardNumber
                    })
                    applyImageFallback(event.currentTarget, [urls.webp, urls.cdnWebp, urls.png])
                  }}
                />
                <div ref={previewShineRef} className="card-preview-shine" />
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
