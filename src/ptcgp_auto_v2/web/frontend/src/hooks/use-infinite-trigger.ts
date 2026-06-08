import { useEffect, useRef, type RefObject } from 'react'

export function createInfiniteTriggerObserver({
  target,
  rootRef,
  rootMargin,
  onLoadMore
}: {
  target: Element
  rootRef?: RefObject<Element | null>
  rootMargin: string
  onLoadMore: () => void
}) {
  const observer = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        onLoadMore()
      }
    },
    {
      // 变更原因：root 必须在 ref 挂载后读取，否则首帧 null 会让 observer 退回 viewport。
      root: rootRef?.current ?? null,
      rootMargin,
      threshold: 0.01
    }
  )
  observer.observe(target)
  return observer
}

/**
 * 无限滚动触发器：当占位元素进入视口时触发加载下一页。
 */
export function useInfiniteTrigger({
  enabled,
  onLoadMore,
  rootRef,
  rootMargin = '160px 0px 160px 0px'
}: {
  enabled: boolean
  onLoadMore: () => void
  rootRef?: RefObject<Element | null>
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
    const observer = createInfiniteTriggerObserver({
      target,
      rootRef,
      rootMargin,
      onLoadMore
    })
    return () => observer.disconnect()
  }, [enabled, onLoadMore, rootRef, rootMargin])

  return triggerRef
}
