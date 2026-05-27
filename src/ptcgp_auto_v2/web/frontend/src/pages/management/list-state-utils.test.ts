import { describe, expect, test } from 'vitest'
import { normalizeManagementListState } from './list-state-utils'

describe('normalizeManagementListState with runtime sort options', () => {

  const spec = {
    storageKey: 'test',
    defaultPageSize: 20,
    pageSizeOptions: [10, 20, 50],
    sort: {
      defaultBy: 'id',
      defaultOrder: 'asc' as const,
      options: [
        { value: 'id', labelKey: 'col_id', fallback: 'ID' },
        { value: 'nickname', labelKey: 'col_nickname', fallback: 'Nickname' },
        { value: 'friend_id', labelKey: 'col_friend_id', fallback: 'Friend ID' },
      ],
    },
  }

  const runtimeSortOptions = [
    { value: 'id', labelKey: 'col_id', fallback: 'ID' },
    { value: 'exchange_points', labelKey: 'col_exchange_points', fallback: 'Exchange Points' },
    { value: 'pack_hourglass_count', labelKey: 'col_pack_hourglass', fallback: 'Pack Hourglass' },
  ]

  test('persisted runtime sort key is preserved when runtime options include it', () => {
    const persisted = {
      sortBy: 'exchange_points',
      sortOrder: 'desc',
      page: 0,
      pageSize: 20,
      filters: {},
    }

    const result = normalizeManagementListState(spec, persisted, runtimeSortOptions)

    expect(result.sortBy).toBe('exchange_points')
    expect(result.sortOrder).toBe('desc')
  })

  test('unknown persisted sort key falls back to default when no runtime options', () => {
    const persisted = {
      sortBy: 'exchange_points',
      sortOrder: 'desc',
      page: 0,
      pageSize: 20,
      filters: {},
    }

    const result = normalizeManagementListState(spec, persisted)

    // Without runtime options, only spec.sort.options are valid → 'exchange_points' is unknown → reset sortBy
    expect(result.sortBy).toBe('id')
    // sortOrder from persisted state is preserved (desc), not reset to default
    expect(result.sortOrder).toBe('desc')
  })
})
