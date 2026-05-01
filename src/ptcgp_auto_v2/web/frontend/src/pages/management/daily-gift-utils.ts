import { formatDateYmd, parseDateYmd } from '@/lib/time-display'

export function buildRecentBizDates(currentBizDate: string, count = 7): string[] {
  const startDate = parseDateYmd(currentBizDate)
  if (!startDate) {
    throw new Error(`无效业务日期: ${currentBizDate}`)
  }

  return Array.from({ length: count }, (_, index) => {
    const date = new Date(startDate)
    date.setDate(startDate.getDate() - index)
    return formatDateYmd(date)
  })
}
