import { afterEach, describe, expect, test } from 'vitest'

import { readStorageValue, writeStorageValue } from '../src/lib/storage'
import { loadThemeMode } from '../src/lib/theme'

describe('storage localStorage 边界', () => {
  const originalWindow = globalThis.window

  afterEach(() => {
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: originalWindow
    })
  })

  test('getItem 因浏览器存储限制抛错时按缺失值处理', () => {
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: {
        localStorage: {
          getItem: () => {
            throw new DOMException('blocked', 'SecurityError')
          }
        }
      }
    })

    expect(readStorageValue('management-state')).toBeNull()
  })

  test('setItem 因浏览器存储限制抛错时不影响调用方渲染流程', () => {
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: {
        localStorage: {
          setItem: () => {
            throw new DOMException('quota', 'QuotaExceededError')
          }
        }
      }
    })

    expect(() => writeStorageValue('management-state', '{}')).not.toThrow()
  })

  test('主题偏好读写受限时使用默认浅色模式', () => {
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: {
        localStorage: {
          getItem: () => {
            throw new DOMException('blocked', 'SecurityError')
          },
          setItem: () => {
            throw new DOMException('quota', 'QuotaExceededError')
          }
        }
      }
    })

    expect(loadThemeMode()).toBe('light')
  })
})
