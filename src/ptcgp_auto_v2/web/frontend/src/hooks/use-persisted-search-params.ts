import { useEffect, useMemo } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'

import { readStorageValue, writeStorageValue } from '@/lib/storage'

const SEARCH_PARAMS_STORAGE_PREFIX = 'ptcgp_search_params:'
const GLOBAL_SEARCH_PARAM_NAMES = new Set(['lang'])

function buildStorageKey(pathname: string): string {
  return `${SEARCH_PARAMS_STORAGE_PREFIX}${pathname}`
}

export function hasOnlyGlobalSearchParams(searchParams: URLSearchParams): boolean {
  if (searchParams.toString().length === 0) {
    return false
  }
  return Array.from(searchParams.keys()).every((key) => GLOBAL_SEARCH_PARAM_NAMES.has(key))
}

function hasPageSearchParams(searchParams: URLSearchParams): boolean {
  return Array.from(searchParams.keys()).some((key) => !GLOBAL_SEARCH_PARAM_NAMES.has(key))
}

export function mergeCachedSearchParamsWithGlobalParams(cachedSearchParams: URLSearchParams, currentSearchParams: URLSearchParams) {
  const merged = new URLSearchParams(cachedSearchParams)
  for (const key of GLOBAL_SEARCH_PARAM_NAMES) {
    const currentValue = currentSearchParams.get(key)
    if (currentValue !== null) {
      merged.set(key, currentValue)
    }
  }
  return merged
}

export function buildRestoredSearchParams(rawCachedSearchParams: string | null, currentSearchParams: URLSearchParams) {
  if (hasPageSearchParams(currentSearchParams)) {
    return null
  }
  if (!rawCachedSearchParams) {
    return null
  }
  const cached = new URLSearchParams(rawCachedSearchParams)
  if (hasOnlyGlobalSearchParams(currentSearchParams)) {
    return mergeCachedSearchParamsWithGlobalParams(cached, currentSearchParams)
  }
  return cached
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
    if (hasPageSearchParams(searchParams)) {
      return null
    }
    return buildRestoredSearchParams(readStorageValue(storageKey), searchParams)
  }, [searchParams, storageKey])

  useEffect(() => {
    const current = searchParams.toString()
    if (current.length === 0 || hasOnlyGlobalSearchParams(searchParams)) {
      return
    }
    writeStorageValue(storageKey, current)
  }, [searchParams, storageKey])

  useEffect(() => {
    if (hasPageSearchParams(searchParams)) {
      return
    }
    if (!cachedSearchParams) {
      return
    }
    if (cachedSearchParams.toString().length === 0) {
      return
    }
    if (cachedSearchParams.toString() === searchParams.toString()) {
      return
    }
    // 变更原因：顶部导航只携带 lang 时仍需恢复目标页筛选、排序和分页缓存。
    setSearchParams(cachedSearchParams, { replace: true, preventScrollReset: true })
  }, [cachedSearchParams, searchParams, setSearchParams])

  const effectiveSearchParams = cachedSearchParams ?? searchParams
  return [effectiveSearchParams, setSearchParams] as const
}
