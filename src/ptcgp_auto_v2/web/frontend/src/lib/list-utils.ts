export function toggleListItem(current: string[], value: string): string[] {
  if (current.includes(value)) {
    return current.filter((item) => item !== value)
  }
  return [...current, value]
}

export function parseSearchList(params: URLSearchParams, key: string): string[] {
  const values = params.getAll(key)
  return values.map((item) => item.trim()).filter((item) => item.length > 0)
}

export function formatTime(value: string | null | undefined): string {
  if (!value) {
    return '-'
  }
  return value.replace('T', ' ').slice(0, 19)
}

export function reasonTitle(reason: string | null | undefined): string | undefined {
  const text = (reason ?? '').trim()
  if (!text || text === '-') {
    return undefined
  }
  return text
}
