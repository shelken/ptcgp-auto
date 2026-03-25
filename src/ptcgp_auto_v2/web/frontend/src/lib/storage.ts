/**
 * 读取 localStorage 字符串值，缺失返回 null。
 */
export function readStorageValue(storageKey: string): string | null {
  return window.localStorage.getItem(storageKey)
}

/**
 * 写入 localStorage 字符串值。
 */
export function writeStorageValue(storageKey: string, value: string): void {
  window.localStorage.setItem(storageKey, value)
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
