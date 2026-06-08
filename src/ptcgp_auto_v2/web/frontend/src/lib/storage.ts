/**
 * 读取 localStorage 字符串值，缺失返回 null。
 */
export function readStorageValue(storageKey: string): string | null {
  try {
    return window.localStorage.getItem(storageKey)
  } catch (error) {
    if (error instanceof DOMException) {
      // 变更原因：受限浏览器可能禁止 localStorage 读取，持久化缺失不应中断页面渲染。
      return null
    }
    throw error
  }
}

/**
 * 写入 localStorage 字符串值。
 */
export function writeStorageValue(storageKey: string, value: string): void {
  try {
    window.localStorage.setItem(storageKey, value)
  } catch (error) {
    if (error instanceof DOMException) {
      // 变更原因：存储配额或权限失败只影响持久化能力，不应打断当前交互。
      return
    }
    throw error
  }
}

/**
 * 读取 localStorage JSON 值，解析失败或缺失时返回默认值。
 */
export function readStorageJson<T>(storageKey: string, fallbackValue: T): T {
  const raw = readStorageValue(storageKey)
  if (raw === null) {
    return fallbackValue
  }
  try {
    return JSON.parse(raw) as T
  } catch {
    return fallbackValue
  }
}
