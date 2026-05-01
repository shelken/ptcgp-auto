interface SearchableManagementOption {
  value: string
  label: string
  searchText: string
}

export function buildSearchableManagementOptions(
  options: readonly { value: string; label: string }[],
  emptyLabel: string
): SearchableManagementOption[] {
  return [
    { value: '', label: emptyLabel, searchText: emptyLabel },
    ...options.map((item) => ({
      value: item.value,
      label: item.label,
      searchText: `${item.value} ${item.label}`
    }))
  ]
}

export function getManagementFilterOptions<T>(
  data: Record<string, unknown> | undefined,
  key: string,
  legacyKeys: string[] = []
): T[] {
  const filterOptions = data?.filter_options
  if (filterOptions && typeof filterOptions === 'object' && !Array.isArray(filterOptions)) {
    const value = (filterOptions as Record<string, unknown>)[key]
    if (Array.isArray(value)) {
      return value as T[]
    }
  }

  for (const legacyKey of legacyKeys) {
    const value = data?.[legacyKey]
    if (Array.isArray(value)) {
      return value as T[]
    }
  }

  return []
}
