import { describe, expect, test } from 'vitest'

import { buildManagementDefaultRedirectTo, buildManagementSectionTo } from './management-page'

describe('buildManagementDefaultRedirectTo', () => {
  test('保留当前语言查询参数', () => {
    expect(buildManagementDefaultRedirectTo('?lang=en')).toEqual({
      pathname: '/management/accounts',
      search: '?lang=en',
    })
  })

  test('子导航只保留全局语言参数', () => {
    expect(buildManagementSectionTo('tasks', '?lang=en&page=2')).toEqual({
      pathname: '/management/tasks',
      search: '?lang=en',
    })
  })
})
