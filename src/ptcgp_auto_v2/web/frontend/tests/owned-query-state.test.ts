import { afterEach, describe, expect, test, vi } from 'vitest'

vi.mock('@/components/ui/button', () => ({
  Button: () => null
}))
vi.mock('@/components/ui/badge', () => ({
  Badge: () => null
}))
vi.mock('@/components/ui/select', () => ({
  Select: () => null,
  SelectContent: () => null,
  SelectItem: () => null,
  SelectTrigger: () => null,
  SelectValue: () => null,
  decodeSelectValue: (value: string) => value,
  encodeSelectValue: (value: string) => value
}))
vi.mock('@/components/ui/tooltip', () => ({
  Tooltip: () => null
}))
vi.mock('@/hooks/use-card-preview-drag', () => ({
  useCardPreviewDrag: () => ({
    cardRef: { current: null },
    shineRef: { current: null },
    dragging: false,
    startDrag: () => undefined,
    onDragMove: () => undefined,
    stopDrag: () => undefined,
    resetTransform: () => undefined
  })
}))
vi.mock('@/hooks/use-card-preview-visual', () => ({
  useCardPreviewVisual: () => ({
    imageUrls: { png: '' },
    cardBackImageUrl: '',
    effectId: '',
    visualStyle: {}
  })
}))
vi.mock('@/hooks/use-infinite-trigger', () => ({
  useInfiniteTrigger: () => ({ current: null })
}))
vi.mock('@/hooks/use-persisted-search-params', () => ({
  usePersistedSearchParams: () => [new URLSearchParams(), () => undefined]
}))
vi.mock('@/hooks/use-preview-origin-visibility', () => ({
  usePreviewOriginVisibility: () => ({
    hiddenOriginRef: { current: null },
    hideOrigin: () => undefined,
    restoreOrigin: () => undefined
  })
}))
vi.mock('@/lib/api', () => ({
  buildQuery: () => '',
  fetchJson: async () => ({}),
  requestJson: async () => ({})
}))
vi.mock('@/lib/card-image-fallback', () => ({
  applyCardListImageFallback: () => undefined,
  applyCardPreviewImageFallback: () => undefined
}))
vi.mock('@/lib/card-image', () => ({
  getCardImageUrls: () => ({ png: '' })
}))
vi.mock('@/lib/card-preview-assets', () => ({
  hideBrokenCardBackImage: () => undefined
}))
vi.mock('@/lib/flip-transition', () => ({
  clearCardFlipExitGhosts: () => undefined,
  playCardFlipEntrance: async () => undefined,
  playCardFlipExitGhost: async () => undefined,
  snapshotElementRect: () => null
}))
vi.mock('@/lib/i18n', () => ({
  tr: (_: Record<string, string>, __: string, fallback: string) => fallback
}))
vi.mock('@/lib/list-utils', () => ({
  parseSearchList: () => [],
  reasonTitle: () => '',
  toggleListItem: (current: string[], value: string) => [...current, value]
}))
vi.mock('@/lib/time-display', () => ({
  formatAbsoluteDateTime: () => '',
  formatRelativeDateTime: () => ''
}))
vi.mock('./management/shared', () => ({
  AccountIdentityCell: () => null
}))

describe('owned-cards 页面 query state', () => {
  const originalWindow = globalThis.window

  afterEach(() => {
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: originalWindow
    })
  })

  test('主列表与统计应复用同一筛选协议并统一字段命名', async () => {
    const {
      buildOwnedCardsListQueryParams,
      buildOwnedCardsStatsQueryParams
    } = await import('../src/pages/owned-cards-query')

    const mainState = {
      accountId: ' 10001 ',
      ownershipScope: 'missing',
      rarity: [' SR ', 'AR'],
      cardType: [' pokemon '],
      setCode: ['A1'],
      packName: [' Mewtwo '],
      element: [' fire '],
      cardNameQuery: ' Pikachu ',
      sortBy: 'count',
      page: 2,
      pageSize: 40
    } as const

    expect(buildOwnedCardsListQueryParams(mainState)).toEqual({
      account_id: '10001',
      ownership_scope: 'missing',
      rarity: ['SR', 'AR'],
      card_type: ['pokemon'],
      set_code: ['A1'],
      pack_name: ['Mewtwo'],
      element: ['fire'],
      q: 'Pikachu',
      sort_by: 'count',
      page: 2,
      page_size: 40
    })

    expect(buildOwnedCardsStatsQueryParams(mainState)).toEqual({
      account_id: '10001',
      ownership_scope: 'missing',
      rarity: ['SR', 'AR'],
      card_type: ['pokemon'],
      set_code: ['A1'],
      pack_name: ['Mewtwo'],
      element: ['fire'],
      q: 'Pikachu'
    })
  })

  test('主列表 URL 清空筛选后应解析为空筛选且写回时不保留旧筛选', async () => {
    const {
      buildOwnedCardsSearchParams,
      parseOwnedCardsSearchState
    } = await import('../src/pages/owned-cards-query')

    const emptyState = parseOwnedCardsSearchState(new URLSearchParams('lang=zh-CN'))

    expect(emptyState).toEqual({
      accountQuery: '',
      cardNameQuery: '',
      selectedRarity: [],
      selectedTypes: [],
      selectedElements: [],
      selectedSetCodes: [],
      selectedPackNames: [],
      sortBy: 'acquired',
      ownershipScope: 'owned',
      viewMode: 'grid',
      showCounts: true,
      listPage: 0
    })
    expect(
      buildOwnedCardsSearchParams(
        emptyState,
        new URLSearchParams('lang=zh-CN&owned_account=10001&owned_q=Pikachu&owned_rarity=SR&owned_type=pokemon&owned_element=fire&owned_set=A1&owned_pack=Mewtwo&owned_sort=count&owned_scope=missing&owned_view=list&owned_counts=hide&owned_page=3')
      ).toString()
    ).toBe('lang=zh-CN&owned_account=&owned_sort=acquired&owned_scope=owned&owned_view=grid&owned_counts=show')
  })

  test('详情弹窗账号表应复用统一搜索/排序/分页协议', async () => {
    const {
      buildOwnedCardDetailQueryParams,
      buildOwnedCardExchangeAccountsQueryParams
    } = await import('../src/pages/owned-cards-query')

    expect(
      buildOwnedCardDetailQueryParams({
        ownershipScope: 'all',
        pageSize: 24,
        lang: 'zh-CN'
      })
    ).toEqual({
      lang: 'zh-CN',
      ownership_scope: 'all',
      page_size: 24
    })

    expect(
      buildOwnedCardExchangeAccountsQueryParams({
        q: ' ash ',
        sortBy: 'nickname',
        sortOrder: 'desc',
        page: 3,
        pageSize: 12,
        lang: 'zh-CN'
      })
    ).toEqual({
      lang: 'zh-CN',
      q: 'ash',
      sort_by: 'nickname',
      sort_order: 'desc',
      page: 3,
      page_size: 12
    })
  })

  test('本地详情分页和网格列数读取受限时使用默认计算值', async () => {
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: {
        innerHeight: 910,
        localStorage: {
          getItem: () => {
            throw new DOMException('blocked', 'SecurityError')
          }
        }
      }
    })

    const { restoreDetailPageSize, restoreOwnedGridCols } = await import('../src/pages/owned-cards-page')

    expect(restoreDetailPageSize()).toBe(10)
    expect(restoreOwnedGridCols()).toBe(5)
  })
})
