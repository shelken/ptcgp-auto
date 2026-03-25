import { useEffect, useState } from 'react'

import { readStorageJson, writeStorageValue } from '@/lib/storage'

/**
 * localStorage 持久化状态
 */
export function usePersistedState<T>(storageKey: string, initialValue: T) {
  const [value, setValue] = useState<T>(() => readStorageJson<T>(storageKey, initialValue))

  useEffect(() => {
    writeStorageValue(storageKey, JSON.stringify(value))
  }, [storageKey, value])

  return [value, setValue] as const
}
