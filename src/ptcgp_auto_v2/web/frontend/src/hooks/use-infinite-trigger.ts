import { useEffect, useRef } from 'react'

/**
 * 无限滚动触发器：当占位元素进入视口时触发加载下一页。
 */
export function useInfiniteTrigger({
  enabled,
  onLoadMore,
  root = null,
  rootMargin = '160px 0px 160px 0px'
}: {
  enabled: boolean
  onLoadMore: () => void
  root?: HTMLElement | null
  rootMargin?: string
}) {
  const triggerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!enabled) {
      return
    }
    const target = triggerRef.current
    if (!target) {
      return
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          onLoadMore()
        }
      },
      {
        root,
        rootMargin,
        threshold: 0.01
      }
    )
    observer.observe(target)
    return () => observer.disconnect()
  }, [enabled, onLoadMore, root, rootMargin])

  return triggerRef
}
