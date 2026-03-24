import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useRef } from 'react'

import { fetchText } from '@/lib/api'

interface HtmlFragmentProps {
  url: string
  queryKey: string[]
  className?: string
  loadingText?: string
  emptyText?: string
}

export function HtmlFragment({
  url,
  queryKey,
  className,
  loadingText = '加载中...',
  emptyText = '暂无内容'
}: HtmlFragmentProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  const stableUrl = useMemo(() => url, [url])
  const query = useQuery({
    queryKey: [...queryKey, stableUrl],
    queryFn: () => fetchText(stableUrl),
    staleTime: 5_000
  })

  useEffect(() => {
    if (!query.data || !containerRef.current) {
      return
    }
    containerRef.current.innerHTML = query.data
    if (window.htmx) {
      window.htmx.process(containerRef.current)
    }
  }, [query.data])

  if (query.isLoading) {
    return <div className="brutal-card p-4 text-sm text-muted">{loadingText}</div>
  }

  if (query.isError) {
    return (
      <div className="brutal-card p-4 text-sm text-red-600">
        {(query.error as Error).message}
      </div>
    )
  }

  if (!query.data?.trim()) {
    return <div className="brutal-card p-4 text-sm text-muted">{emptyText}</div>
  }

  return <div ref={containerRef} className={className} />
}
