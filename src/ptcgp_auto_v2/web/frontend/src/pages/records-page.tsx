import { useCallback, useEffect, useMemo, useState } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { getCardImageUrls, type CardImageAssets } from '@/lib/card-image'
import { buildQuery, fetchJson } from '@/lib/api'
import { useInfiniteTrigger } from '@/hooks/use-infinite-trigger'
import { tr } from '@/lib/i18n'
import type { BootstrapOptions } from '@/types/api'

interface RecordsPageProps {
  lang: string
  options: BootstrapOptions
  assets: CardImageAssets
  t: Record<string, string>
}

interface RecordCardView {
  display_name: string
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

interface RecordListItem {
  is_batch: boolean
  batch_id?: string
  account_name: string
  opened_at: string
  set_name_display: string
  pack_name_display: string
  pack_type_display: string
  cards?: RecordCardView[]
  batch_packs?: Array<{
    cards: RecordCardView[]
    batch_index: number
    cover_card?: RecordCardView | null
    max_rarity?: string
    has_new?: boolean
  }>
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

function toggleItem(current: string[], value: string): string[] {
  if (current.includes(value)) {
    return current.filter((item) => item !== value)
  }
  return [...current, value]
}

function parseSearchList(params: URLSearchParams, key: string): string[] {
  const values = params.getAll(key)
  return values.map((item) => item.trim()).filter((item) => item.length > 0)
}

function formatTime(value: string) {
  if (!value) {
    return '-'
  }
  return value.replace('T', ' ').slice(0, 19)
}

function CardThumb({
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
  const setCode = card.set_code ?? card.card?.set_code
  const cardNumber = card.card_number ?? card.card?.number
  const urls = getCardImageUrls(assets, {
    setCode,
    cardNumber: typeof cardNumber === 'number' ? cardNumber : Number(cardNumber ?? 0)
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
            setCode: setCode ?? '',
            cardNumber: Number(cardNumber ?? 0)
          })
        }
      >
        <img
          src={urls.png}
          alt={card.display_name}
          className="record-card-image"
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
      </button>
      <div className="record-card-meta">
        <span className="record-card-rarity">{card.rarity}</span>
        {card.is_new ? <span className="record-card-new">{tr(t, 'new_badge', 'NEW')}</span> : null}
      </div>
      <div className="record-card-name" title={card.display_name}>
        {card.display_name}
      </div>
    </div>
  )
}

function BatchOverviewThumb({
  pack,
  assets,
  t,
  onSelect
}: {
  pack: NonNullable<RecordListItem['batch_packs']>[number]
  assets: CardImageAssets
  t: Record<string, string>
  onSelect: (packIndex: number) => void
}) {
  const cover = pack.cover_card ?? null
  const setCode = cover?.set_code ?? cover?.card?.set_code
  const cardNumber = cover?.card_number ?? cover?.card?.number
  const urls = getCardImageUrls(assets, {
    setCode,
    cardNumber: typeof cardNumber === 'number' ? cardNumber : Number(cardNumber ?? 0)
  })

  return (
    <button type="button" className="record-batch-pack" onClick={() => onSelect(pack.batch_index)}>
      {cover ? (
        <img
          src={urls.png}
          alt={cover.display_name}
          className="record-card-image"
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
      ) : (
        <div className="record-batch-pack-fallback">{pack.max_rarity || '☆'}</div>
      )}
      <div className="record-batch-pack-index">#{pack.batch_index + 1}</div>
      {pack.has_new ? <div className="record-batch-pack-new">{tr(t, 'new_badge', 'NEW')}</div> : null}
      {pack.max_rarity ? <div className="record-batch-pack-rarity">{pack.max_rarity}</div> : null}
    </button>
  )
}

export function RecordsPage({ lang, options, assets, t }: RecordsPageProps) {
  const RECORDS_VIEW_MODE_KEY = 'ptcgp_view_mode'
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedRarity, setSelectedRarity] = useState<string[]>(() => parseSearchList(searchParams, 'records_rarity'))
  const [selectedTypes, setSelectedTypes] = useState<string[]>(() => parseSearchList(searchParams, 'records_type'))
  const [viewMode, setViewMode] = useState<'grid' | 'list'>(() => {
    const stored = window.localStorage.getItem(RECORDS_VIEW_MODE_KEY)
    return stored === 'list' ? 'list' : 'grid'
  })
  const [previewCard, setPreviewCard] = useState<PreviewState | null>(null)
  const [previewRotate, setPreviewRotate] = useState({ x: 0, y: 0 })
  const [previewDragging, setPreviewDragging] = useState(false)
  const [activeBatchPack, setActiveBatchPack] = useState<Record<string, number | null>>({})

  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    next.delete('records_rarity')
    next.delete('records_type')
    next.delete('records_view')
    selectedRarity.forEach((item) => next.append('records_rarity', item))
    selectedTypes.forEach((item) => next.append('records_type', item))
    next.set('records_view', viewMode)
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true })
    }
  }, [searchParams, selectedRarity, selectedTypes, setSearchParams, viewMode])

  useEffect(() => {
    window.localStorage.setItem(RECORDS_VIEW_MODE_KEY, viewMode)
  }, [viewMode])

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
    <section className="section-stack">
      <div className="surface-card section-stack">
        <div className="pagination-row">
          <h2 className="section-title">{tr(t, 'filter_title', 'Filters')}</h2>
          <div className="filter-row">
            <Button type="button" size="sm" variant={viewMode === 'list' ? 'default' : 'outline'} onClick={() => setViewMode('list')}>
              {tr(t, 'view_list', 'List')}
            </Button>
            <Button type="button" size="sm" variant={viewMode === 'grid' ? 'default' : 'outline'} onClick={() => setViewMode('grid')}>
              {tr(t, 'view_grid', 'Grid')}
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={() => query.refetch()}>
              {tr(t, 'refresh', 'Refresh')}
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={clearFilters}>
              {tr(t, 'clear_filters', 'Clear')}
            </Button>
          </div>
        </div>

        <div className="section-stack">
          <div className="section-subtitle">{tr(t, 'filter_rarity', 'Rarity')}</div>
          <div className="filter-row">
            {options.rarities.map((rarity) => (
              <Button
                key={rarity}
                type="button"
                size="sm"
                variant={selectedRarity.includes(rarity) ? 'default' : 'outline'}
                onClick={() => {
                  setSelectedRarity((prev) => toggleItem(prev, rarity))
                }}
              >
                {t[`rarity_${rarity}`] ?? rarity}
              </Button>
            ))}
          </div>
        </div>

        <div className="section-stack">
          <div className="section-subtitle">{tr(t, 'filter_type', 'Type')}</div>
          <div className="filter-row">
            {options.card_types.map((cardType) => (
              <Button
                key={cardType}
                type="button"
                size="sm"
                variant={selectedTypes.includes(cardType) ? 'default' : 'outline'}
                onClick={() => {
                  setSelectedTypes((prev) => toggleItem(prev, cardType))
                }}
              >
                {t[`type_${cardType}`] ?? cardType}
              </Button>
            ))}
          </div>
        </div>
      </div>

      {query.isLoading && <div className="surface-card text-sm text-muted">{tr(t, 'label_loading', 'Loading...')}</div>}
      {query.isError && <div className="surface-card text-sm text-danger">{(query.error as Error).message}</div>}

      {pages.length > 0 && (
        <>
          {records.length === 0 && <div className="surface-card text-sm text-muted">{tr(t, 'end_of_records', 'No records')}</div>}
          <div className={`layout-grid ${viewMode === 'list' ? 'layout-grid--list' : ''}`}>
            {records.map((item, index) => (
              <article key={`${item.opened_at}-${index}`} className="card-item">
                <div className="section-stack">
                  <div className="section-title">{item.account_name}</div>
                  <div className="text-xs text-muted">{formatTime(item.opened_at)}</div>
                  <div className="text-xs">
                    <span className="tag">{item.set_name_display}</span>
                    <span className="tag ml-1">{item.pack_name_display}</span>
                  </div>
                  <div className="text-xs text-muted">{item.pack_type_display}</div>
                </div>

                {!item.is_batch && (
                  <div className="record-card-grid">
                    {(item.cards ?? []).map((card) => (
                      <CardThumb
                        key={`${card.position}-${card.display_name}`}
                        card={card}
                        assets={assets}
                        t={t}
                        onPreview={setPreviewCard}
                      />
                    ))}
                  </div>
                )}

                {item.is_batch && (
                  <div className="section-stack">
                    {(() => {
                      const batchKey = item.batch_id || `${item.opened_at}-${index}`
                      const selectedPackIndex = activeBatchPack[batchKey] ?? null
                      const batchPacks = item.batch_packs ?? []
                      const selectedPack = selectedPackIndex === null
                        ? null
                        : batchPacks.find((pack) => pack.batch_index === selectedPackIndex) ?? null

                      if (selectedPack === null) {
                        return (
                          <div className="record-batch-overview-grid">
                            {batchPacks.map((pack) => (
                              <BatchOverviewThumb
                                key={`${batchKey}-${pack.batch_index}`}
                                pack={pack}
                                assets={assets}
                                t={t}
                                onSelect={(packIndex) =>
                                  setActiveBatchPack((prev) => ({ ...prev, [batchKey]: packIndex }))
                                }
                              />
                            ))}
                          </div>
                        )
                      }

                      return (
                        <div className="section-stack">
                          <div className="pagination-row">
                            <div className="text-xs text-muted">
                              {tr(t, 'pack_number', 'Pack')} {selectedPack.batch_index + 1}
                            </div>
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                setActiveBatchPack((prev) => ({ ...prev, [batchKey]: null }))
                              }
                            >
                              {tr(t, 'btn_back_to_overview', 'Overview')}
                            </Button>
                          </div>
                          <div className="record-card-grid">
                            {selectedPack.cards.map((card) => (
                              <CardThumb
                                key={`${selectedPack.batch_index}-${card.position}`}
                                card={card}
                                assets={assets}
                                t={t}
                                onPreview={setPreviewCard}
                              />
                            ))}
                          </div>
                        </div>
                      )
                    })()}
                  </div>
                )}
              </article>
            ))}
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
        <div className="dialog-overlay" onClick={() => {
          setPreviewCard(null)
          setPreviewRotate({ x: 0, y: 0 })
          setPreviewDragging(false)
        }}>
          <div className="dialog-card section-stack" onClick={(event) => event.stopPropagation()}>
            <div className="pagination-row">
              <div className="section-title">{previewCard.title}</div>
              <Button type="button" size="sm" variant="outline" onClick={() => {
                setPreviewCard(null)
                setPreviewRotate({ x: 0, y: 0 })
                setPreviewDragging(false)
              }}>
                {tr(t, 'label_close', 'Close')}
              </Button>
            </div>
            <div
              className={`record-preview-card ${previewDragging ? 'is-dragging' : ''}`}
              style={{ transform: `rotateX(${previewRotate.x}deg) rotateY(${previewRotate.y}deg)` }}
              onPointerDown={(event) => {
                const target = event.currentTarget
                target.dataset.dragging = '1'
                target.dataset.lastX = String(event.clientX)
                target.dataset.lastY = String(event.clientY)
                target.setPointerCapture(event.pointerId)
                setPreviewDragging(true)
              }}
              onPointerMove={(event) => {
                const target = event.currentTarget
                if (target.dataset.dragging !== '1') {
                  return
                }
                const lastX = Number(target.dataset.lastX ?? event.clientX)
                const lastY = Number(target.dataset.lastY ?? event.clientY)
                const deltaX = event.clientX - lastX
                const deltaY = event.clientY - lastY
                target.dataset.lastX = String(event.clientX)
                target.dataset.lastY = String(event.clientY)
                setPreviewRotate((prev) => ({
                  x: Math.max(-45, Math.min(45, prev.x - deltaY * 0.28)),
                  y: Math.max(-45, Math.min(45, prev.y + deltaX * 0.28))
                }))
              }}
              onPointerUp={(event) => {
                const target = event.currentTarget
                target.dataset.dragging = '0'
                target.releasePointerCapture(event.pointerId)
                setPreviewDragging(false)
                setPreviewRotate({ x: 0, y: 0 })
              }}
              onPointerCancel={(event) => {
                const target = event.currentTarget
                target.dataset.dragging = '0'
                target.releasePointerCapture(event.pointerId)
                setPreviewDragging(false)
                setPreviewRotate({ x: 0, y: 0 })
              }}
            >
              <img
                src={getCardImageUrls(assets, {
                  setCode: previewCard.setCode,
                  cardNumber: previewCard.cardNumber
                }).png}
                alt={previewCard.title}
                className="record-preview-image"
              />
            </div>
            <div className="filter-row">
              <span className="tag">{previewCard.rarity}</span>
              <span className="tag">{previewCard.setCode}</span>
              <span className="tag">#{String(previewCard.cardNumber).padStart(3, '0')}</span>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
