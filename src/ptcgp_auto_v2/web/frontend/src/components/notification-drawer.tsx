import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import DOMPurify from 'dompurify'
import { marked } from 'marked'

import { Button } from '@/components/ui/button'
import { buildQuery, fetchJson, requestJson } from '@/lib/api'
import { useInfiniteTrigger } from '@/hooks/use-infinite-trigger'
import { tr } from '@/lib/i18n'

interface NotificationItem {
  id: number
  scene: string
  title: string
  content: string
  image_url: string | null
  image_webp_url: string | null
  is_read: boolean
  relative_time: string
}

interface NotificationPanelResponse {
  notifications: NotificationItem[]
  has_more: boolean
  next_page: number
  unread_count: number
  page: number
  page_size: number
}

marked.setOptions({
  gfm: true,
  breaks: true
})

function extractPlainText(content: string, maxLength = 100) {
  if (!content) {
    return ''
  }
  const result = content
    .replace(/!\[[^\]]*]\([^)]+\)/g, '')
    .replace(/\[([^\]]+)]\([^)]+\)/g, '$1')
    .replace(/[*_`>#-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  if (result.length <= maxLength) {
    return result
  }
  return `${result.slice(0, maxLength)}...`
}

function renderMarkdownSafely(content: string) {
  const rendered = marked.parse(content || '') as string
  const sanitized = DOMPurify.sanitize(rendered, {
    ALLOWED_TAGS: ['a', 'b', 'strong', 'i', 'em', 'p', 'br', 'ul', 'ol', 'li', 'code', 'pre', 'img'],
    ALLOWED_ATTR: ['href', 'title', 'target', 'rel', 'src', 'alt']
  })
  const wrapper = document.createElement('div')
  wrapper.innerHTML = sanitized
  wrapper.querySelectorAll('a[href]').forEach((node) => {
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer')
  })
  return wrapper.innerHTML
}

export function NotificationDrawer({
  lang,
  t,
  open,
  onOpenChange,
  restoreFocusRef
}: {
  lang: string
  t: Record<string, string>
  open: boolean
  onOpenChange: (open: boolean) => void
  restoreFocusRef?: RefObject<HTMLElement | null>
}) {
  const queryClient = useQueryClient()
  const drawerRef = useRef<HTMLElement | null>(null)
  const closeButtonRef = useRef<HTMLButtonElement | null>(null)
  const listRef = useRef<HTMLDivElement | null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const query = useInfiniteQuery({
    queryKey: ['notification-panel', lang],
    queryFn: ({ pageParam }) =>
      fetchJson<NotificationPanelResponse>(
        `/api/react/notifications/panel?${buildQuery({ lang, page: pageParam, page_size: 10 })}`
      ),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => (lastPage.has_more ? lastPage.next_page : undefined),
    enabled: open,
    refetchInterval: 30000
  })

  const hasNextPage = Boolean(query.data?.pages[query.data.pages.length - 1]?.has_more)
  const loadMore = useCallback(() => {
    if (!open || !query.hasNextPage || query.isFetchingNextPage) {
      return
    }
    void query.fetchNextPage()
  }, [open, query])
  const sentinelRef = useInfiniteTrigger({
    enabled: open && hasNextPage && !query.isFetchingNextPage,
    onLoadMore: loadMore,
    root: listRef.current
  })

  const markReadMutation = useMutation({
    mutationFn: (notificationId: number) =>
      requestJson<{ ok: boolean }>(`/api/react/notifications/${notificationId}/mark-read`, { method: 'POST' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notification-count'] })
      queryClient.invalidateQueries({ queryKey: ['notification-panel'] })
      queryClient.invalidateQueries({ queryKey: ['management-notifications'] })
    }
  })

  const markAllMutation = useMutation({
    mutationFn: () => requestJson<{ ok: boolean; count: number }>('/api/react/notifications/mark-all-read', { method: 'POST', body: {} }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notification-count'] })
      queryClient.invalidateQueries({ queryKey: ['notification-panel'] })
      queryClient.invalidateQueries({ queryKey: ['management-notifications'] })
    }
  })

  useEffect(() => {
    if (!open) {
      return
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onOpenChange(false)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onOpenChange, open])

  useEffect(() => {
    if (!open) {
      return
    }
    const previousOverflow = document.body.style.overflow
    const previousPaddingRight = document.body.style.paddingRight
    const scrollBarWidth = window.innerWidth - document.documentElement.clientWidth

    document.body.style.overflow = 'hidden'
    if (scrollBarWidth > 0) {
      document.body.style.paddingRight = `${scrollBarWidth}px`
    }

    return () => {
      document.body.style.overflow = previousOverflow
      document.body.style.paddingRight = previousPaddingRight
    }
  }, [open])

  useEffect(() => {
    if (!open) {
      return
    }

    const drawerElement = drawerRef.current
    if (!drawerElement) {
      return
    }

    closeButtonRef.current?.focus()

    const queryFocusable = () =>
      Array.from(
        drawerElement.querySelectorAll<HTMLElement>(
          'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])'
        )
      )

    const onTrapTab = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') {
        return
      }
      const focusable = queryFocusable()
      if (focusable.length === 0) {
        event.preventDefault()
        drawerElement.focus()
        return
      }
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement as HTMLElement | null
      const inDrawer = active ? drawerElement.contains(active) : false

      if (event.shiftKey) {
        if (!inDrawer || active === first) {
          event.preventDefault()
          last.focus()
        }
        return
      }

      if (!inDrawer || active === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onTrapTab)
    return () => document.removeEventListener('keydown', onTrapTab)
  }, [open])

  useEffect(() => {
    if (open) {
      return
    }
    setExpandedId(null)
    const target = restoreFocusRef?.current
    if (target && typeof target.focus === 'function') {
      target.focus()
    }
  }, [open, restoreFocusRef])

  const pages = query.data?.pages ?? []
  const notifications = pages.flatMap((page) => page.notifications)
  const firstPage = pages[0]
  const markdownById = useMemo(() => {
    const map: Record<number, string> = {}
    for (const item of notifications) {
      map[item.id] = renderMarkdownSafely(item.content || '')
    }
    return map
  }, [notifications])

  if (!open) {
    return null
  }

  return (
    <div className="notification-drawer-backdrop" onClick={() => onOpenChange(false)}>
      <aside
        ref={drawerRef}
        className="notification-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={tr(t, 'notification_center', 'Notifications')}
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="notification-drawer-header">
          <div>
            <div className="section-title">{tr(t, 'notification_center', 'Notifications')}</div>
            <div className="text-xs text-muted">{tr(t, 'notification_panel_description', 'Notification list')}</div>
          </div>
          <div className="filter-row">
            <Button ref={closeButtonRef} type="button" size="sm" variant="outline" onClick={() => onOpenChange(false)}>
              {tr(t, 'label_close', 'Close')}
            </Button>
            <Button type="button" size="sm" onClick={() => markAllMutation.mutate()} disabled={markAllMutation.isPending}>
              {tr(t, 'btn_mark_all_read', 'Mark All Read')}
            </Button>
          </div>
        </div>

        {query.isLoading && <div className="surface-card text-sm text-muted">{tr(t, 'label_loading', 'Loading...')}</div>}
        {query.isError && <div className="surface-card text-sm text-danger">{(query.error as Error).message}</div>}

        {!query.isLoading && notifications.length === 0 && (
          <div className="surface-card text-sm text-muted">{tr(t, 'notification_empty', 'No notifications')}</div>
        )}

        <div ref={listRef} className="notification-list">
          {notifications.map((item) => {
            const expanded = expandedId === item.id
            const plainText = extractPlainText(item.content)
            return (
              <article key={item.id} className={`notification-item ${item.is_read ? 'is-read' : 'is-unread'}`}>
                <button
                  type="button"
                  className="notification-item-summary"
                  onClick={() => {
                    setExpandedId((prev) => (prev === item.id ? null : item.id))
                    if (!item.is_read) {
                      markReadMutation.mutate(item.id)
                    }
                  }}
                >
                  {(item.image_url || item.image_webp_url) && (
                    <img
                      className="notification-thumb"
                      src={item.image_url || item.image_webp_url || ''}
                      alt={item.title}
                      loading="lazy"
                      onError={(event) => {
                        const image = event.currentTarget
                        if (item.image_webp_url && image.src !== item.image_webp_url) {
                          image.src = item.image_webp_url
                        }
                      }}
                    />
                  )}
                  <div className="notification-main">
                    <div className="notification-item-header">
                      <div className="notification-title">{item.title}</div>
                      {!item.is_read && <span className="notification-dot" aria-hidden="true" />}
                    </div>
                    <div className="notification-body">{plainText || '-'}</div>
                    <div className="notification-time">{item.relative_time || '-'}</div>
                  </div>
                </button>
                {expanded && (
                  <div
                    className="notification-detail"
                    dangerouslySetInnerHTML={{ __html: markdownById[item.id] || plainText || '-' }}
                  />
                )}
              </article>
            )
          })}
          {query.isFetchingNextPage && (
            <div className="text-xs text-muted">{tr(t, 'label_loading_more', 'Loading more...')}</div>
          )}
          {!hasNextPage && notifications.length > 0 && (
            <div className="text-xs text-muted">{tr(t, 'label_reach_end', 'Reached the end')}</div>
          )}
          <div ref={sentinelRef} className="infinite-sentinel" />
        </div>

        <div className="notification-drawer-footer">
          <span className="text-xs mono">
            {tr(t, 'label_unread', 'Unread')}: {firstPage?.unread_count ?? 0}
          </span>
          <span className="text-xs text-muted">
            {tr(t, 'label_total_records', 'Total')}: {notifications.length}
          </span>
        </div>
      </aside>
    </div>
  )
}
