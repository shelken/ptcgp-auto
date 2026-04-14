import { describe, expect, mock, test } from 'bun:test'

mock.module('@/components/ui/button', () => ({
  Button: () => null
}))
mock.module('@/components/ui/badge', () => ({
  Badge: () => null
}))
mock.module('@/components/ui/select', () => ({
  Select: () => null,
  SelectContent: () => null,
  SelectItem: () => null,
  SelectTrigger: () => null,
  SelectValue: () => null,
  decodeSelectValue: (value: string) => value,
  encodeSelectValue: (value: string) => value
}))
mock.module('@/components/ui/tooltip', () => ({
  Tooltip: () => null
}))
mock.module('@/hooks/use-card-preview-drag', () => ({
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
mock.module('@/hooks/use-card-preview-visual', () => ({
  useCardPreviewVisual: () => ({
    imageUrls: { png: '' },
    cardBackImageUrl: '',
    effectId: '',
    visualStyle: {}
  })
}))
mock.module('@/hooks/use-infinite-trigger', () => ({
  useInfiniteTrigger: () => ({ current: null })
}))
mock.module('@/hooks/use-persisted-search-params', () => ({
  usePersistedSearchParams: () => [new URLSearchParams(), () => undefined]
}))
mock.module('@/hooks/use-preview-origin-visibility', () => ({
  usePreviewOriginVisibility: () => ({
    hiddenOriginRef: { current: null },
    hideOrigin: () => undefined,
    restoreOrigin: () => undefined
  })
}))
mock.module('@/lib/api', () => ({
  buildQuery: () => '',
  fetchJson: async () => ({}),
  requestJson: async () => ({})
}))
mock.module('@/lib/card-image-fallback', () => ({
  applyCardListImageFallback: () => undefined,
  applyCardPreviewImageFallback: () => undefined
}))
mock.module('@/lib/card-image', () => ({
  getCardImageUrls: () => ({ png: '' })
}))
mock.module('@/lib/card-preview-assets', () => ({
  hideBrokenCardBackImage: () => undefined
}))
mock.module('@/lib/flip-transition', () => ({
  clearCardFlipExitGhosts: () => undefined,
  playCardFlipEntrance: async () => undefined,
  playCardFlipExitGhost: async () => undefined,
  snapshotElementRect: () => null
}))
mock.module('@/lib/i18n', () => ({
  tr: (_: Record<string, string>, __: string, fallback: string) => fallback
}))
mock.module('@/lib/list-utils', () => ({
  parseSearchList: () => [],
  reasonTitle: () => '',
  toggleListItem: (current: string[], value: string) => [...current, value]
}))
mock.module('@/lib/time-display', () => ({
  formatAbsoluteDateTime: () => '',
  formatRelativeDateTime: () => ''
}))
mock.module('./management/shared', () => ({
  AccountIdentityCell: () => null
}))

describe('owned-cards 页面 query state', () => {
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
      element: ['fire']
    })
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
})
