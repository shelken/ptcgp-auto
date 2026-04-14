import { describe, expect, test } from 'bun:test'

describe('records 查询状态', () => {
  test('应从 URL 参数解析筛选与视图状态', async () => {
    const { parseRecordsSearchState } = await import('../src/pages/records-query')

    const params = new URLSearchParams([
      ['records_rarity', 'SR'],
      ['records_rarity', 'AR'],
      ['records_type', 'fire'],
      ['records_type', 'water'],
      ['records_view', 'list']
    ])

    expect(parseRecordsSearchState(params)).toEqual({
      selectedRarity: ['SR', 'AR'],
      selectedTypes: ['fire', 'water'],
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
          viewMode: 'list'
        },
        new URLSearchParams('tab=records')
      ).toString()
    ).toBe('tab=records&records_rarity=SR&records_rarity=AR&records_type=fire&records_view=list')
  })

  test('应统一构造 API 查询参数', async () => {
    const { buildRecordsApiQueryParams } = await import('../src/pages/records-query')

    expect(
      buildRecordsApiQueryParams({
        lang: 'zh-CN',
        page: 2,
        pageSize: 10,
        selectedRarity: ['SR'],
        selectedTypes: ['fire', 'water']
      })
    ).toEqual({
      lang: 'zh-CN',
      page: 2,
      page_size: 10,
      rarity: ['SR'],
      card_type: ['fire', 'water']
    })
  })
})
