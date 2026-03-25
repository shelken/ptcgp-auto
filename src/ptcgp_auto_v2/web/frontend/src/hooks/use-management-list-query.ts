import { useMemo } from 'react'
import { useQuery, type UseQueryResult } from '@tanstack/react-query'

import { buildQuery, fetchJson } from '@/lib/api'

interface UseManagementListQueryOptions {
  queryKey: string
  endpoint: string
  lang: string
  params: Record<string, unknown>
  enabled?: boolean
}

/**
 * 管理页列表查询模板：统一 queryString 与 useQuery 结构
 */
export function useManagementListQuery<TData extends Record<string, unknown>>({
  queryKey,
  endpoint,
  lang,
  params,
  enabled = true
}: UseManagementListQueryOptions): {
  queryString: string
  query: UseQueryResult<TData, Error>
} {
  const queryParams = useMemo(
    () => ({
      lang,
      ...params
    }),
    [lang, params]
  )

  const queryString = useMemo(() => buildQuery(queryParams), [queryParams])

  const query = useQuery<TData, Error>({
    enabled,
    queryKey: [queryKey, queryString],
    queryFn: () => fetchJson<TData>(`/api/react/management/${endpoint}?${queryString}`)
  })

  return { queryString, query }
}
