import type { ManagementListSpec, ManagementListState } from './list-spec'

type ManagementQueryParamValue =
  | string
  | number
  | boolean
  | Array<string | number>
  | undefined
  | null

function resolveFilterQueryKey(spec: ManagementListSpec, key: string): string {
  const filterSpec = spec.filters?.find((item) => item.key === key)
  return filterSpec?.queryKey ?? key
}

function resolveListQueryKey(
  spec: ManagementListSpec,
  key: 'page' | 'pageSize' | 'sortBy' | 'sortOrder'
): string {
  if (key === 'page') {
    return spec.queryKeys?.page ?? 'page'
  }
  if (key === 'pageSize') {
    return spec.queryKeys?.pageSize ?? 'page_size'
  }
  if (key === 'sortBy') {
    return spec.queryKeys?.sortBy ?? 'sort_by'
  }
  return spec.queryKeys?.sortOrder ?? 'sort_order'
}

export function buildManagementListQueryParams(
  spec: ManagementListSpec,
  state: ManagementListState,
  extraParams: Record<string, ManagementQueryParamValue> = {}
): Record<string, ManagementQueryParamValue> {
  const params: Record<string, ManagementQueryParamValue> = {
    [resolveListQueryKey(spec, 'page')]: state.page,
    [resolveListQueryKey(spec, 'pageSize')]: state.pageSize,
    ...extraParams
  }

  if (spec.sort) {
    params[resolveListQueryKey(spec, 'sortBy')] = state.sortBy
    params[resolveListQueryKey(spec, 'sortOrder')] = state.sortOrder
  }

  for (const [key, rawValue] of Object.entries(state.filters)) {
    const value = rawValue.trim()
    if (!value) {
      continue
    }
    params[resolveFilterQueryKey(spec, key)] = value
  }

  return params
}
