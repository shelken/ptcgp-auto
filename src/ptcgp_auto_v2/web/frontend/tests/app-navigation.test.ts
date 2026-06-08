import { describe, expect, it } from 'vitest'

import { buildNavTo, buildRootRedirectTo } from '../src/App'

describe('buildNavTo', () => {
  it('保留顶部导航的语言查询参数', () => {
    expect(buildNavTo('/records', 'en')).toBe('/records?lang=en')
    expect(buildNavTo('/owned-cards', 'zh_CN')).toBe('/owned-cards?lang=zh_CN')
    expect(buildNavTo('/management', 'en')).toBe('/management?lang=en')
  })
})

describe('buildRootRedirectTo', () => {
  it('根路由重定向到 records 时保留当前 search', () => {
    expect(buildRootRedirectTo('?lang=en')).toEqual({ pathname: '/records', search: '?lang=en' })
    expect(buildRootRedirectTo('?lang=en&records_q=Pikachu')).toEqual({ pathname: '/records', search: '?lang=en&records_q=Pikachu' })
  })
})
