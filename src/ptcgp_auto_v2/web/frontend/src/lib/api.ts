async function ensureResponseOk(response: Response): Promise<void> {
  if (response.ok) {
    return
  }
  const text = await response.text()
  throw new Error(text || `请求失败: ${response.status}`)
}

async function readJsonResponse<T>(response: Response): Promise<T> {
  await ensureResponseOk(response)
  return (await response.json()) as T
}

export async function fetchText(url: string): Promise<string> {
  const response = await fetch(url, {
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
  await ensureResponseOk(response)
  return response.text()
}

export async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { headers: { Accept: 'application/json' } })
  return readJsonResponse<T>(response)
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
  return readJsonResponse<T>(response)
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
  return readJsonResponse<T>(response)
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
