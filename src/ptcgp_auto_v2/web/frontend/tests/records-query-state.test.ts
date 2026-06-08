import { afterEach, describe, expect, test } from 'vitest'

describe('records 查询状态', () => {
  const originalWindow = globalThis.window

  afterEach(() => {
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: originalWindow
    })
  })

  test('应从 URL 参数解析筛选与视图状态', async () => {
    const { parseRecordsSearchState } = await import('../src/pages/records-query')

    const params = new URLSearchParams([
      ['records_rarity', 'SR'],
      ['records_rarity', 'AR'],
      ['records_type', 'fire'],
      ['records_type', 'water'],
      ['records_set', 'A1'],
      ['records_q', ' Pikachu '],
      ['records_view', 'list']
    ])

    expect(parseRecordsSearchState(params)).toEqual({
      selectedRarity: ['SR', 'AR'],
      selectedTypes: ['fire', 'water'],
      selectedSetCodes: ['A1'],
      cardNameQuery: ' Pikachu ',
      viewMode: 'list'
    })
  })

  test('应把筛选状态写回 URL 参数', async () => {
    const { buildRecordsSearchParams } = await import('../src/pages/records-query')

    expect(
      buildRecordsSearchParams(
        {
          selectedRarity: ['SR', 'AR'],
          selectedTypes: ['fire'],
          selectedSetCodes: ['A1'],
          cardNameQuery: ' Pikachu ',
          viewMode: 'list'
        },
        new URLSearchParams('tab=records')
      ).toString()
    ).toBe('tab=records&records_rarity=SR&records_rarity=AR&records_type=fire&records_set=A1&records_q=Pikachu&records_view=list')
  })

  test('URL 清空筛选后应解析为空筛选且写回时不保留旧筛选', async () => {
    const { buildRecordsSearchParams, parseRecordsSearchState } = await import('../src/pages/records-query')

    const emptyState = parseRecordsSearchState(new URLSearchParams('lang=zh-CN'), { fallbackView: 'grid' })

    expect(emptyState).toEqual({
      selectedRarity: [],
      selectedTypes: [],
      selectedSetCodes: [],
      cardNameQuery: '',
      viewMode: 'grid'
    })
    expect(
      buildRecordsSearchParams(
        emptyState,
        new URLSearchParams('lang=zh-CN&records_rarity=SR&records_type=fire&records_set=A1&records_q=Pikachu&records_view=list')
      ).toString()
    ).toBe('lang=zh-CN&records_view=grid')
  })

  test('应统一构造 API 查询参数', async () => {
    const { buildRecordsApiQueryParams } = await import('../src/pages/records-query')

    expect(
      buildRecordsApiQueryParams({
        lang: 'zh-CN',
        page: 2,
        pageSize: 10,
        selectedRarity: ['SR'],
        selectedTypes: ['fire', 'water'],
        selectedSetCodes: ['A1'],
        cardNameQuery: ' Pikachu '
      })
    ).toEqual({
      lang: 'zh-CN',
      page: 2,
      page_size: 10,
      rarity: ['SR'],
      card_type: ['fire', 'water'],
      set_code: ['A1'],
      q: 'Pikachu'
    })
  })

  test('本地视图模式读取受限时使用网格视图', async () => {
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: {
        localStorage: {
          getItem: () => {
            throw new DOMException('blocked', 'SecurityError')
          }
        }
      }
    })

    const { resolveStoredViewMode } = await import('../src/pages/records-page')

    expect(resolveStoredViewMode()).toBe('grid')
  })

  test('十连包交互键应区分同 batch_id 的不同账号', async () => {
    const { resolveRecordBatchKey } = await import('../src/pages/records-page')

    expect(resolveRecordBatchKey({ batch_id: 'shared-batch', account_id: 1, opened_at: '2026-04-14T12:00:00' }, 0)).toBe('1:shared-batch')
    expect(resolveRecordBatchKey({ batch_id: 'shared-batch', account_id: 2, opened_at: '2026-04-14T12:00:00' }, 1)).toBe('2:shared-batch')
  })
})
