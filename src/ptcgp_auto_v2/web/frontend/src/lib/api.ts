export async function fetchText(url: string): Promise<string> {
  const response = await fetch(url, {
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
  if (!response.ok) {
    throw new Error(`请求失败: ${response.status}`)
  }
  return response.text()
}

export async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { headers: { Accept: 'application/json' } })
  if (!response.ok) {
    throw new Error(`请求失败: ${response.status}`)
  }
  return (await response.json()) as T
}

interface JsonRequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
}

export async function requestJson<T>(url: string, options: JsonRequestOptions = {}): Promise<T> {
  const response = await fetch(url, {
    method: options.method ?? 'GET',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json'
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body)
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `请求失败: ${response.status}`)
  }
  return (await response.json()) as T
}

interface FormRequestOptions {
  method?: 'POST' | 'PUT' | 'DELETE'
  body: FormData
}

export async function requestFormJson<T>(url: string, options: FormRequestOptions): Promise<T> {
  const response = await fetch(url, {
    method: options.method ?? 'POST',
    headers: {
      Accept: 'application/json'
    },
    body: options.body
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `请求失败: ${response.status}`)
  }
  return (await response.json()) as T
}

export function buildQuery(params: Record<string, string | number | boolean | Array<string | number> | undefined | null>) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') {
      continue
    }
    if (Array.isArray(value)) {
      value.forEach((item) => search.append(key, String(item)))
      continue
    }
    search.set(key, String(value))
  }
  return search.toString()
}
