import { describe, expect, test } from 'vitest'

import {
  buildResetCompletedTasksPayload,
  resolveManagementTaskAccountFilter
} from '../src/pages/management/task-filters'

describe('任务页筛选参数', () => {
  test('账号关键字输入应保留为 account_q', () => {
    expect(resolveManagementTaskAccountFilter('  Ash  ')).toEqual({
      selectedAccountId: '',
      selectedAccountQuery: 'Ash'
    })
  })

  test('重置已完成请求体应携带当前账号关键字', () => {
    expect(
      buildResetCompletedTasksPayload({
        status: 'completed',
        taskType: 'open_pack',
        accountKeyword: 'Misty'
      })
    ).toEqual({
      status: ['completed'],
      task_type: ['open_pack'],
      account_id: null,
      account_q: 'Misty'
    })
  })
})
