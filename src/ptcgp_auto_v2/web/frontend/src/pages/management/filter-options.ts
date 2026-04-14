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
