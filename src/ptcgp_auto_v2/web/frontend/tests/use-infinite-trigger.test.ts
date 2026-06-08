import { afterEach, describe, expect, test, vi } from 'vitest'

import { createInfiniteTriggerObserver } from '../src/hooks/use-infinite-trigger'

describe('useInfiniteTrigger observer root', () => {
  const originalObserver = globalThis.IntersectionObserver

  afterEach(() => {
    globalThis.IntersectionObserver = originalObserver
    vi.restoreAllMocks()
  })

  test('创建 observer 时使用滚动容器 ref 作为 root', () => {
    const scrollRoot = { nodeName: 'DIV' } as Element
    const target = { nodeName: 'SENTINEL' } as Element
    const observe = vi.fn()
    const disconnect = vi.fn()
    const createdOptions: IntersectionObserverInit[] = []

    globalThis.IntersectionObserver = vi.fn(function (_callback, options) {
      createdOptions.push(options ?? {})
      return { observe, disconnect } as unknown as IntersectionObserver
    }) as unknown as typeof IntersectionObserver

    const observer = createInfiniteTriggerObserver({
      target,
      rootRef: { current: scrollRoot },
      rootMargin: '160px 0px 160px 0px',
      onLoadMore: () => undefined
    })

    expect(createdOptions).toEqual([
      {
        root: scrollRoot,
        rootMargin: '160px 0px 160px 0px',
        threshold: 0.01
      }
    ])
    expect(observe).toHaveBeenCalledWith(target)
    expect(observer.disconnect).toBe(disconnect)
  })
})
