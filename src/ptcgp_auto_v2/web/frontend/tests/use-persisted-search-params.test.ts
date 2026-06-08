import { describe, expect, test } from 'vitest'

import {
  buildRestoredSearchParams,
  hasOnlyGlobalSearchParams,
  mergeCachedSearchParamsWithGlobalParams
} from '../src/hooks/use-persisted-search-params'

describe('usePersistedSearchParams 查询参数合并', () => {
  test('当前 URL 只有 lang 时保留当前语言并恢复页面缓存', () => {
    const cached = new URLSearchParams('account_id=1&page=2&lang=zh_CN')
    const current = new URLSearchParams('lang=en')

    const merged = mergeCachedSearchParamsWithGlobalParams(cached, current)

    expect(merged.toString()).toBe('account_id=1&page=2&lang=en')
  })

  test('当前 URL 有页面级参数时不使用缓存', () => {
    const current = new URLSearchParams('lang=en&page=3')

    expect(hasOnlyGlobalSearchParams(current)).toBe(false)
    expect(buildRestoredSearchParams('account_id=1&page=2&lang=zh_CN', current)).toBeNull()
  })
})
