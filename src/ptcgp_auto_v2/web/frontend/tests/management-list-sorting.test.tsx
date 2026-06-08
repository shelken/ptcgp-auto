import { describe, expect, test } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'

import type { ManagementListSpec, ManagementListState } from '../src/pages/management/list-spec'
import { applyManagementListSortClick } from '../src/pages/management/list-state-utils'
import { buildTaskTableColumns } from '../src/pages/management/task-table'
import { ListQueryControls } from '../src/pages/management/shared'

function buildState(overrides: Partial<ManagementListState> = {}): ManagementListState {
  return {
    page: 3,
    pageSize: 20,
    sortBy: 'created_at',
    sortOrder: 'desc',
    filters: {},
    ...overrides
  }
}

describe('管理页表头排序', () => {
  test('点击普通列应按三态循环并重置到第一页', () => {
    const spec: ManagementListSpec = {
      storageKey: 'notifications',
      defaultPageSize: 20,
      pageSizeOptions: [10, 20, 50],
      sort: {
        defaultBy: 'created_at',
        defaultOrder: 'desc',
        options: [
          { value: 'created_at', labelKey: 'created_at', fallback: 'Created At' },
          { value: 'title', labelKey: 'title', fallback: 'Title' }
        ]
      }
    }

    expect(applyManagementListSortClick(spec, buildState(), 'title')).toEqual({
      page: 0,
      pageSize: 20,
      sortBy: 'title',
      sortOrder: 'asc',
      filters: {}
    })

    expect(
      applyManagementListSortClick(
        spec,
        buildState({ page: 1, sortBy: 'title', sortOrder: 'asc' }),
        'title'
      )
    ).toEqual({
      page: 0,
      pageSize: 20,
      sortBy: 'title',
      sortOrder: 'desc',
      filters: {}
    })

    expect(
      applyManagementListSortClick(
        spec,
        buildState({ page: 1, sortBy: 'title', sortOrder: 'desc' }),
        'title'
      )
    ).toEqual({
      page: 0,
      pageSize: 20,
      sortBy: 'created_at',
      sortOrder: 'desc',
      filters: {}
    })
  })

  test('点击锁定方向列应使用锁定方向并可回到列表默认排序', () => {
    const spec: ManagementListSpec = {
      storageKey: 'tasks',
      defaultPageSize: 20,
      pageSizeOptions: [10, 20, 50],
      sort: {
        defaultBy: 'created_at',
        defaultOrder: 'desc',
        options: [
          { value: 'created_at', labelKey: 'created_at', fallback: 'Created At' },
          { value: 'dispatch_priority', labelKey: 'dispatch_priority', fallback: 'Dispatch Priority' }
        ],
        lockedOrderBy: {
          dispatch_priority: 'asc'
        }
      }
    }

    expect(
      applyManagementListSortClick(spec, buildState(), 'dispatch_priority')
    ).toEqual({
      page: 0,
      pageSize: 20,
      sortBy: 'dispatch_priority',
      sortOrder: 'asc',
      filters: {}
    })

    expect(
      applyManagementListSortClick(
        spec,
        buildState({ page: 2, sortBy: 'dispatch_priority', sortOrder: 'asc' }),
        'dispatch_priority'
      )
    ).toEqual({
      page: 0,
      pageSize: 20,
      sortBy: 'created_at',
      sortOrder: 'desc',
      filters: {}
    })
  })

  test('列表查询控件只保留分页大小', () => {
    const html = renderToStaticMarkup(
      <ListQueryControls
        pageSize={20}
        onPageSizeChange={() => {}}
        t={{}}
      />
    )

    expect(html).toContain('Page Size')
    expect(html).not.toContain('Sort By')
    expect(html).not.toContain('Order')
  })

  test('tasks 的调度优先级列应声明可排序字段', () => {
    const columns = buildTaskTableColumns({
      lang: 'zh-CN',
      t: {}
    })

    expect(columns.find((column) => column.key === 'dispatch_rank')).toMatchObject({
      sortKey: 'dispatch_priority'
    })
  })
})
