import { afterEach, describe, expect, test, vi } from 'vitest'

import { resolveCardThemeColor } from './card-theme-color'
import { readStorageValue, writeStorageValue } from './storage'

function stubWindowWithStorage(storage: Pick<Storage, 'getItem' | 'setItem'>): void {
  vi.stubGlobal('window', { localStorage: storage })
}

describe('storage helpers', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  test('无 window 时读取返回 null 且写入不崩溃', () => {
    vi.stubGlobal('window', undefined)

    expect(readStorageValue('missing')).toBeNull()
    expect(() => writeStorageValue('missing', 'value')).not.toThrow()
  })

  test('localStorage DOMException 降级为缺失或 no-op', () => {
    const storageError = new DOMException('blocked')
    const getItem = vi.fn(() => {
      throw storageError
    })
    const setItem = vi.fn(() => {
      throw storageError
    })
    stubWindowWithStorage({ getItem, setItem })

    expect(readStorageValue('blocked')).toBeNull()
    expect(() => writeStorageValue('blocked', 'value')).not.toThrow()
    expect(getItem).toHaveBeenCalledWith('blocked')
    expect(setItem).toHaveBeenCalledWith('blocked', 'value')
  })

  test('localStorage 非 DOMException 继续抛出', () => {
    const storageError = new Error('storage contract broken')
    stubWindowWithStorage({
      getItem: () => {
        throw storageError
      },
      setItem: () => undefined,
    })

    expect(() => readStorageValue('broken')).toThrow(storageError)
  })
})

describe('card theme color storage reuse', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  test('读取颜色缓存遇到非 DOMException 存储错误时继续抛出', async () => {
    const storageError = new Error('storage contract broken')
    stubWindowWithStorage({
      getItem: () => {
        throw storageError
      },
      setItem: () => undefined,
    })

    await expect(
      resolveCardThemeColor({ cacheKey: 'non-dom-storage-error', imageUrl: '' })
    ).rejects.toThrow(storageError)
  })
})
