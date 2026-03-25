import { useEffect, useState } from 'react'

/**
 * localStorage 持久化状态
 */
export function usePersistedState<T>(storageKey: string, initialValue: T) {
  const [value, setValue] = useState<T>(() => {
    const raw = window.localStorage.getItem(storageKey)
    if (raw === null) {
      return initialValue
    }
    try {
      return JSON.parse(raw) as T
    } catch {
      return initialValue
    }
  })

  useEffect(() => {
    window.localStorage.setItem(storageKey, JSON.stringify(value))
  }, [storageKey, value])

  return [value, setValue] as const
}
