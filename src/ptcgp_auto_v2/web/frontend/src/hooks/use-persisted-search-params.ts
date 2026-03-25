import { useEffect, useMemo } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'

import { readStorageValue, writeStorageValue } from '@/lib/storage'

const SEARCH_PARAMS_STORAGE_PREFIX = 'ptcgp_search_params:'

function buildStorageKey(pathname: string): string {
  return `${SEARCH_PARAMS_STORAGE_PREFIX}${pathname}`
}

/**
 * 按路由持久化查询参数：
 * 1. 查询参数变化时写入 localStorage
 * 2. 页面首次进入且 URL 无查询参数时，从缓存恢复
 */
export function usePersistedSearchParams() {
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const storageKey = useMemo(() => buildStorageKey(location.pathname), [location.pathname])

  const cachedSearchParams = useMemo(() => {
    if (searchParams.toString().length > 0) {
      return null
    }
    const raw = readStorageValue(storageKey)
    if (!raw) {
      return null
    }
    return new URLSearchParams(raw)
  }, [searchParams, storageKey])

  useEffect(() => {
    const current = searchParams.toString()
    if (current.length === 0) {
      return
    }
    writeStorageValue(storageKey, current)
  }, [searchParams, storageKey])

  useEffect(() => {
    if (searchParams.toString().length > 0) {
      return
    }
    if (!cachedSearchParams) {
      return
    }
    if (cachedSearchParams.toString().length === 0) {
      return
    }
    setSearchParams(cachedSearchParams, { replace: true, preventScrollReset: true })
  }, [cachedSearchParams, searchParams, setSearchParams])

  const effectiveSearchParams = cachedSearchParams ?? searchParams
  return [effectiveSearchParams, setSearchParams] as const
}
