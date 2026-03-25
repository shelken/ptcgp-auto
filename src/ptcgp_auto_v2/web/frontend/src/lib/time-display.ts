/**
 * 时间解析：统一处理 ISO / 空格分隔时间字符串。
 */
function parseDateTime(value: unknown): Date | null {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value
  }
  if (typeof value !== 'string') {
    return null
  }
  const text = value.trim()
  if (!text) {
    return null
  }

  const candidate = text.includes('T') ? text : text.replace(' ', 'T')
  const date = new Date(candidate)
  if (!Number.isNaN(date.getTime())) {
    return date
  }
  const fallback = new Date(text)
  if (!Number.isNaN(fallback.getTime())) {
    return fallback
  }
  return null
}

/**
 * 绝对时间：本地时间 YYYY-MM-DD HH:mm:ss。
 */
export function formatAbsoluteDateTime(value: unknown): string {
  const date = parseDateTime(value)
  if (!date) {
    return '-'
  }
  const year = String(date.getFullYear()).padStart(4, '0')
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  const second = String(date.getSeconds()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`
}

function formatRelativeCore(seconds: number, lang: string, t: Record<string, string>, future: boolean): string {
  let value = 0
  let unit = ''
  if (seconds < 3600) {
    value = Math.round(seconds / 60)
    unit = t.relative_minutes || 'min'
  } else if (seconds < 86400) {
    value = Math.round(seconds / 3600)
    unit = t.relative_hours || 'hr'
  } else {
    value = Math.round(seconds / 86400)
    unit = t.relative_days || 'day'
  }
  const agoText = t.relative_ago || 'ago'
  const inText = t.relative_in || 'in'
  if (lang === 'en') {
    return future ? `${inText} ${value} ${unit}` : `${value} ${unit} ${agoText}`
  }
  return future ? `${value}${unit}${inText}` : `${value}${unit}${agoText}`
}

/**
 * 相对时间：与通知中心逻辑保持一致。
 */
export function formatRelativeDateTime(
  value: unknown,
  lang: string,
  t: Record<string, string>
): string {
  const date = parseDateTime(value)
  if (!date) {
    return '-'
  }
  const now = Date.now()
  const diffSeconds = (now - date.getTime()) / 1000
  if (diffSeconds < 0) {
    const futureSeconds = Math.abs(diffSeconds)
    if (futureSeconds < 60) {
      return t.relative_soon || 'soon'
    }
    return formatRelativeCore(futureSeconds, lang, t, true)
  }
  if (diffSeconds < 60) {
    return t.relative_just_now || 'just now'
  }
  return formatRelativeCore(diffSeconds, lang, t, false)
}

/**
 * 时长短格式：用于“上次耗时”等字段。
 */
export function formatDurationShort(secondsValue: unknown): string {
  const seconds = Number(secondsValue)
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return '-'
  }
  if (seconds < 60) {
    return `${seconds.toFixed(1).replace(/\.0$/, '')}s`
  }

  const totalSeconds = Math.round(seconds)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const secs = totalSeconds % 60
  if (hours > 0) {
    return `${hours}h ${minutes}m ${secs}s`
  }
  return `${minutes}m ${secs}s`
}

/**
 * 时长精确值：悬浮提示展示。
 */
export function formatDurationExact(secondsValue: unknown): string {
  const seconds = Number(secondsValue)
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return '-'
  }
  return `${seconds.toFixed(1)}s`
}
