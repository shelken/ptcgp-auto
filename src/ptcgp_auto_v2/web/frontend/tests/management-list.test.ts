import { describe, expect, test } from 'bun:test'

describe('管理页统一列表状态', () => {
  test('非法持久化值应收敛到 spec 默认值与锁定排序方向', async () => {
    const { normalizeManagementListState } = await import('../src/pages/management/list-state-utils')

    const spec = {
      storageKey: 'notifications',
      defaultPageSize: 10,
      pageSizeOptions: [10, 20, 50],
      filters: [
        { key: 'q', kind: 'search' },
        { key: 'scene', kind: 'select', options: ['', 'rare_card_obtained', 'task_status'] }
      ],
      sort: {
        defaultBy: 'created_at',
        defaultOrder: 'desc',
        options: [
          { value: 'created_at' },
          { value: 'title' }
        ],
        lockedOrderBy: {
          created_at: 'desc'
        }
      }
    } as const

    expect(
      normalizeManagementListState(spec, {
        page: -4,
        pageSize: 999,
        sortBy: 'unknown',
        sortOrder: 'asc',
        filters: {
          q: '  system warning  ',
          scene: 'invalid-scene'
        }
      })
    ).toEqual({
      page: 0,
      pageSize: 10,
      sortBy: 'created_at',
      sortOrder: 'desc',
      filters: {
        q: 'system warning',
        scene: ''
      }
    })
  })

  test('动作上下文应从当前查询参数构造并补齐空筛选字段', async () => {
    const { buildManagementListQueryParams } = await import('../src/pages/management/list-query')
    const { buildManagementListActionPayload } = await import('../src/pages/management/list-actions')

    const spec = {
      storageKey: 'notifications',
      defaultPageSize: 10,
      pageSizeOptions: [10, 20, 50],
      filters: [
        { key: 'q', kind: 'search' },
        { key: 'scene', kind: 'select', options: ['', 'rare_card_obtained', 'task_status'] },
        { key: 'account_id', kind: 'select', options: ['', '1', '2'] },
        { key: 'is_read', kind: 'select', options: ['', 'true', 'false'] }
      ],
      sort: {
        defaultBy: 'created_at',
        defaultOrder: 'desc',
        options: [
          { value: 'created_at' },
          { value: 'title' }
        ]
      }
    } as const

    const params = buildManagementListQueryParams(spec, {
      page: 2,
      pageSize: 20,
      sortBy: 'title',
      sortOrder: 'asc',
      filters: {
        q: 'rare card',
        scene: 'task_status',
        account_id: '',
        is_read: 'false'
      }
    })

    expect(
      buildManagementListActionPayload({
        params,
        fields: ['scene', 'account_id', 'is_read', 'q', 'sort_by', 'sort_order', 'page', 'page_size'],
        missingValue: null
      })
    ).toEqual({
      scene: 'task_status',
      account_id: null,
      is_read: 'false',
      q: 'rare card',
      sort_by: 'title',
      sort_order: 'asc',
      page: 2,
      page_size: 20
    })
  })

  test('动态筛选和动态排序选项到达后应收敛旧持久化脏值', async () => {
    const { normalizeManagementListRuntimeState } = await import('../src/pages/management/list-state-utils')

    const spec = {
      storageKey: 'resources',
      defaultPageSize: 20,
      pageSizeOptions: [10, 20, 50, 100],
      filters: [
        {
          key: 'view',
          kind: 'select',
          defaultValue: 'stats',
          includeEmpty: false,
          options: [
            { value: 'stats', label: 'Stats' },
            { value: 'pack-points', label: 'Pack Points' }
          ]
        },
        {
          key: 'account_id',
          kind: 'account-select',
          label: 'Account',
          optionsKey: 'account_id'
        },
        {
          key: 'status',
          kind: 'select',
          label: 'Status',
          optionsKey: 'status'
        }
      ],
      sort: {
        defaultBy: 'id',
        defaultOrder: 'asc',
        options: [
          { value: 'id' },
          { value: 'nickname' }
        ]
      }
    } as const

    expect(
      normalizeManagementListRuntimeState(
        spec,
        {
          page: 0,
          pageSize: 20,
          sortBy: 'series:A2',
          sortOrder: 'desc',
          filters: {
            view: 'stats',
            account_id: '99',
            status: 'done'
          }
        },
        {
          dynamicOptions: {
            account_id: [
              { value: '', label: 'All', searchText: 'All' },
              { value: '1', label: '1 Ash', searchText: '1 Ash' }
            ],
            status: [
              { value: 'pending', label: 'Pending' },
              { value: 'completed', label: 'Completed' }
            ]
          },
          sortOptions: [
            { value: 'id' },
            { value: 'nickname' }
          ]
        }
      )
    ).toEqual({
      page: 0,
      pageSize: 20,
      sortBy: 'id',
      sortOrder: 'desc',
      filters: {
        view: 'stats',
        account_id: '',
        status: ''
      }
    })

    expect(
      normalizeManagementListRuntimeState(
        spec,
        {
          page: 0,
          pageSize: 20,
          sortBy: 'series:A2',
          sortOrder: 'desc',
          filters: {
            view: 'pack-points',
            account_id: '1',
            status: 'completed'
          }
        },
        {
          dynamicOptions: {
            account_id: [
              { value: '', label: 'All', searchText: 'All' },
              { value: '1', label: '1 Ash', searchText: '1 Ash' }
            ],
            status: [
              { value: 'pending', label: 'Pending' },
              { value: 'completed', label: 'Completed' }
            ]
          },
          sortOptions: [
            { value: 'id' },
            { value: 'nickname' },
            { value: 'series:A2' }
          ]
        }
      )
    ).toEqual({
      page: 0,
      pageSize: 20,
      sortBy: 'series:A2',
      sortOrder: 'desc',
      filters: {
        view: 'pack-points',
        account_id: '1',
        status: 'completed'
      }
    })
  })

  test('动态排序字段点击后应生效', async () => {
    const { applyManagementListSortClick } = await import('../src/pages/management/list-state-utils')

    const spec = {
      storageKey: 'resources',
      defaultPageSize: 20,
      pageSizeOptions: [20],
      sort: {
        defaultBy: 'id',
        defaultOrder: 'asc',
        options: [
          { value: 'id' },
          { value: 'nickname' }
        ]
      }
    } as const

    expect(
      applyManagementListSortClick(
        spec,
        {
          page: 3,
          pageSize: 20,
          sortBy: 'id',
          sortOrder: 'asc',
          filters: {}
        },
        'exchange_points',
        [{ value: 'id' }, { value: 'nickname' }, { value: 'exchange_points' }]
      )
    ).toEqual({
      page: 0,
      pageSize: 20,
      sortBy: 'exchange_points',
      sortOrder: 'asc',
      filters: {}
    })
  })

  test('无排序列表应只构造自己的分页参数并省略排序参数', async () => {
    const { normalizeManagementListState } = await import('../src/pages/management/list-state-utils')
    const { buildManagementListQueryParams } = await import('../src/pages/management/list-query')

    const spec = {
      storageKey: 'daily-gift-pairs',
      defaultPageSize: 10,
      pageSizeOptions: [10, 20, 50, 100],
      queryKeys: {
        page: 'pair_page',
        pageSize: 'pair_page_size'
      },
      filters: [
        {
          key: 'account_id',
          kind: 'account-select',
          label: 'Account',
          optionsKey: 'account_id'
        }
      ]
    } as const

    const state = normalizeManagementListState(spec, {
      page: 2,
      pageSize: 50,
      sortBy: 'updated_at',
      sortOrder: 'desc',
      filters: {
        account_id: '12'
      }
    })

    expect(state).toEqual({
      page: 2,
      pageSize: 50,
      sortBy: '',
      sortOrder: 'asc',
      filters: {
        account_id: '12'
      }
    })

    expect(buildManagementListQueryParams(spec, state)).toEqual({
      pair_page: 2,
      pair_page_size: 50,
      account_id: '12'
    })
  })

  test('多表页面应让记录表和配对表各自维护独立 query state', async () => {
    const { buildManagementListQueryParams } = await import('../src/pages/management/list-query')

    const recordSpec = {
      storageKey: 'daily-gift-records',
      defaultPageSize: 10,
      pageSizeOptions: [10, 20, 50, 100],
      filters: [
        {
          key: 'account_id',
          kind: 'account-select',
          label: 'Account',
          optionsKey: 'account_id'
        }
      ],
      sort: {
        defaultBy: 'updated_at',
        defaultOrder: 'desc',
        options: [
          { value: 'updated_at', labelKey: 'col_updated_at', fallback: 'Updated At' },
          { value: 'status', labelKey: 'col_status', fallback: 'Status' }
        ]
      }
    } as const

    const pairSpec = {
      storageKey: 'daily-gift-pairs',
      defaultPageSize: 10,
      pageSizeOptions: [10, 20, 50, 100],
      queryKeys: {
        page: 'pair_page',
        pageSize: 'pair_page_size'
      },
      filters: [
        {
          key: 'account_id',
          kind: 'account-select',
          label: 'Account',
          optionsKey: 'account_id'
        }
      ]
    } as const

    const recordParams = buildManagementListQueryParams(recordSpec, {
      page: 1,
      pageSize: 20,
      sortBy: 'status',
      sortOrder: 'asc',
      filters: {
        account_id: '3'
      }
    })

    const pairParams = buildManagementListQueryParams(pairSpec, {
      page: 4,
      pageSize: 100,
      sortBy: '',
      sortOrder: 'asc',
      filters: {
        account_id: '3'
      }
    })

    expect(recordParams).toEqual({
      page: 1,
      page_size: 20,
      sort_by: 'status',
      sort_order: 'asc',
      account_id: '3'
    })

    expect(pairParams).toEqual({
      pair_page: 4,
      pair_page_size: 100,
      account_id: '3'
    })
  })
  
  test('管理页编辑器查询应统一构造', async () => {
    const {
      buildAccountPlansQuery,
      buildPackConfigQuery,
      buildPlanEditorQuery,
      buildTaskAccountOptionsQuery
    } = await import('../src/pages/management/management-queries')

    expect(buildAccountPlansQuery('zh')).toBe('lang=zh')
    expect(buildPackConfigQuery('en-US')).toBe('lang=en-US')
    expect(buildPlanEditorQuery('en', 3)).toBe('lang=en&plan_id=3')
    expect(buildPlanEditorQuery('en', null)).toBe('lang=en')
    expect(buildTaskAccountOptionsQuery(' foo ')).toBe('q=foo')
    expect(buildTaskAccountOptionsQuery('      ')).toBe('')
  })

  test('metadata 查询参数应由专用 helper 统一构造并省略空字段', async () => {
    const {
      buildMetadataExecutePayload,
      buildMetadataPreviewPayload,
      buildMetadataQueryString
    } = await import('../src/pages/management/metadata-query')

    expect(
      buildMetadataQueryString({
        lang: 'zh-CN',
        uiStep: 2,
        nodeType: 'pack',
        nodeId: 'A2-001',
        setCode: '',
        packName: 'Mew Pack',
        action: 'update_data',
        snapshotId: ''
      })
    ).toBe(
      'lang=zh-CN&ui_step=2&selected_node_type=pack&selected_node_id=A2-001&selected_pack_name=Mew+Pack&current_action=update_data'
    )

    expect(
      buildMetadataQueryString({
        lang: 'en',
        uiStep: 3,
        nodeType: 'card',
        nodeId: '25',
        setCode: 'A2',
        packName: 'Mew Pack',
        action: 'update_chinese',
        snapshotId: 'snap-1'
      })
    ).toBe(
      'lang=en&ui_step=3&selected_node_type=card&selected_node_id=25&selected_set_code=A2&selected_pack_name=Mew+Pack&current_action=update_chinese&snapshot_id=snap-1'
    )

    expect(
      buildMetadataPreviewPayload({
        action: 'update_data',
        nodeType: 'pack',
        nodeId: 'A2-001',
        forceRefresh: true
      })
    ).toEqual({
      action: 'update_data',
      node_type: 'pack',
      node_id: 'A2-001',
      force_refresh: true
    })

    expect(buildMetadataExecutePayload('snap-1')).toEqual({
      snapshot_id: 'snap-1'
    })
  })

  test('metadata helper 应共享当前 action/snapshot 并驱动 preview/execute payload', async () => {
    const {
      buildMetadataExecutePayload,
      buildMetadataPreviewPayload,
      buildMetadataRequestContext
    } = await import('../src/pages/management/metadata-query')

    const context = buildMetadataRequestContext({
      nodeType: 'card',
      nodeId: '05',
      setCode: 'A2',
      packName: 'Mew Pack',
      action: 'update_chinese',
      snapshotId: 'snap-2'
    })

    expect(context).toEqual({
      selected_node_type: 'card',
      selected_node_id: '05',
      selected_set_code: 'A2',
      selected_pack_name: 'Mew Pack',
      current_action: 'update_chinese',
      snapshot_id: 'snap-2'
    })

    expect(
      buildMetadataPreviewPayload({
        action: context.current_action,
        nodeType: context.selected_node_type,
        nodeId: context.selected_node_id,
        forceRefresh: true,
        snapshotId: context.snapshot_id ?? ''
      })
    ).toEqual({
      action: 'update_chinese',
      node_type: 'card',
      node_id: '05',
      force_refresh: true,
      snapshot_id: 'snap-2'
    })

    expect(buildMetadataExecutePayload(context.snapshot_id ?? '')).toEqual({
      snapshot_id: 'snap-2'
    })
  })

  test('管理页应优先读取统一 filter_options 并兼容旧 options 字段', async () => {
    const { getManagementFilterOptions } = await import('../src/pages/management/filter-options')

    expect(
      getManagementFilterOptions(
        {
          filter_options: {
            status: ['pending', 'completed']
          },
          status_options: ['legacy']
        },
        'status',
        ['status_options']
      )
    ).toEqual(['pending', 'completed'])

    expect(
      getManagementFilterOptions(
        {
          status_options: ['sending', 'completed']
        },
        'status',
        ['status_options']
      )
    ).toEqual(['sending', 'completed'])

    expect(
      getManagementFilterOptions(
        {
          filter_options: {
            scene: [{ value: 'task_status', label: 'Task Status' }]
          }
        },
        'scene',
        ['scene_options']
      )
    ).toEqual([{ value: 'task_status', label: 'Task Status' }])
  })

  test('通知场景搜索下拉的空选项也应携带搜索文本', async () => {
    const { buildSearchableManagementOptions } = await import('../src/pages/management/filter-options')

    expect(
      buildSearchableManagementOptions(
        [{ value: 'task_status', label: '任务状态' }],
        '全部场景'
      )
    ).toEqual([
      { value: '', label: '全部场景', searchText: '全部场景' },
      { value: 'task_status', label: '任务状态', searchText: 'task_status 任务状态' }
    ])
  })

  test('每日礼包快捷日期应固定为当前业务日最近七天', async () => {
    const { buildRecentBizDates } = await import('../src/pages/management/daily-gift-utils')

    expect(buildRecentBizDates('2026-04-30')).toEqual([
      '2026-04-30',
      '2026-04-29',
      '2026-04-28',
      '2026-04-27',
      '2026-04-26',
      '2026-04-25',
      '2026-04-24'
    ])
  })
})
