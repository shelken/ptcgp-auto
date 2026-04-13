import type {
  ManagementListFilterSpec,
  ManagementListDynamicOptions,
  ManagementListSortOrder,
  ManagementListSpec,
  ManagementListState
} from './list-spec'

export interface PersistedManagementListState {
  page?: number
  pageSize?: number
  sortBy?: string
  sortOrder?: string
  filters?: Record<string, unknown>
}

function normalizeOptionValues(
  options: ManagementListDynamicOptions[string] | readonly string[] | undefined
): Set<string> {
  const values = new Set<string>([''])
  for (const option of options ?? []) {
    if (typeof option === 'string') {
      values.add(option)
      continue
    }
    values.add(option.value)
  }
  return values
}

function normalizeFilterValue(filter: ManagementListFilterSpec, value: unknown): string {
  const normalized = typeof value === 'string' ? value.trim() : ''
  if (!normalized) {
    return ''
  }
  if (filter.kind !== 'select' || !filter.options || filter.options.length === 0) {
    return normalized
  }

  const allowedValues = new Set(
    filter.options.map((item) => (typeof item === 'string' ? item : item.value))
  )
  return allowedValues.has(normalized) ? normalized : ''
}

function normalizeSortOrder(
  sortOrder: unknown,
  fallback: ManagementListSortOrder
): ManagementListSortOrder {
  return sortOrder === 'asc' || sortOrder === 'desc' ? sortOrder : fallback
}

function normalizeSortState(
  spec: ManagementListSpec,
  rawState: PersistedManagementListState | null | undefined
): Pick<ManagementListState, 'sortBy' | 'sortOrder'> {
  if (!spec.sort) {
    return {
      sortBy: '',
      sortOrder: 'asc'
    }
  }

  const sortOptions = new Set(spec.sort.options.map((item) => item.value))
  const defaultSortBy = sortOptions.has(spec.sort.defaultBy)
    ? spec.sort.defaultBy
    : spec.sort.options[0]?.value ?? ''
  const rawSortBy = typeof rawState?.sortBy === 'string' ? rawState.sortBy : defaultSortBy
  const sortBy = sortOptions.has(rawSortBy) ? rawSortBy : defaultSortBy
  const lockedOrder = spec.sort.lockedOrderBy?.[sortBy]

  return {
    sortBy,
    sortOrder: lockedOrder ?? normalizeSortOrder(rawState?.sortOrder, spec.sort.defaultOrder)
  }
}

export function normalizeManagementListState(
  spec: ManagementListSpec,
  rawState: PersistedManagementListState | null | undefined
): ManagementListState {
  const { sortBy, sortOrder } = normalizeSortState(spec, rawState)

  const filters: Record<string, string> = {}
  for (const filter of spec.filters ?? []) {
    filters[filter.key] = normalizeFilterValue(filter, rawState?.filters?.[filter.key])
  }

  const normalizedPage = Number.isInteger(rawState?.page) && Number(rawState?.page) >= 0
    ? Number(rawState?.page)
    : 0
  const normalizedPageSize = spec.pageSizeOptions.includes(Number(rawState?.pageSize))
    ? Number(rawState?.pageSize)
    : spec.defaultPageSize

  return {
    page: normalizedPage,
    pageSize: normalizedPageSize,
    sortBy,
    sortOrder,
    filters
  }
}

export function normalizeManagementListRuntimeState(
  spec: ManagementListSpec,
  state: ManagementListState,
  runtime?: {
    dynamicOptions?: ManagementListDynamicOptions
    sortOptions?: readonly { value: string }[]
  }
): ManagementListState {
  if (!spec.sort) {
    return {
      ...state,
      sortBy: '',
      sortOrder: 'asc'
    }
  }

  const runtimeSortValues = runtime?.sortOptions?.map((item) => item.value) ?? []
  const allowedSortValues = new Set(
    runtimeSortValues.length > 0
      ? runtimeSortValues
      : spec.sort.options.map((item) => item.value)
  )
  const defaultSortBy = allowedSortValues.has(spec.sort.defaultBy)
    ? spec.sort.defaultBy
    : runtimeSortValues[0] ?? spec.sort.options[0]?.value ?? ''
  const sortBy = allowedSortValues.has(state.sortBy) ? state.sortBy : defaultSortBy
  const sortOrder = spec.sort.lockedOrderBy?.[sortBy] ?? state.sortOrder

  const filters: Record<string, string> = { ...state.filters }
  for (const filter of spec.filters ?? []) {
    if (filter.kind === 'search' || filter.kind === 'text' || ('options' in filter && filter.options)) {
      continue
    }
    if (
      filter.kind !== 'select'
      && filter.kind !== 'account-select'
      && filter.kind !== 'searchable-select'
    ) {
      continue
    }
    const optionKey = filter.optionsKey ?? filter.key
    const dynamicOptions = runtime?.dynamicOptions?.[optionKey]
    if (!dynamicOptions || dynamicOptions.length === 0) {
      continue
    }
    const allowedValues = normalizeOptionValues(dynamicOptions)
    const currentValue = filters[filter.key] ?? ''
    if (!allowedValues.has(currentValue)) {
      filters[filter.key] = ''
    }
  }

  return {
    ...state,
    sortBy,
    sortOrder,
    filters
  }
}
