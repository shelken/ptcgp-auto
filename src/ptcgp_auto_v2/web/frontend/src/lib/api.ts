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
  const response = await fetch(url, {
    headers: {
      Accept: 'application/json'
    }
  })
  if (!response.ok) {
    throw new Error(`请求失败: ${response.status}`)
  }
  return (await response.json()) as T
}
