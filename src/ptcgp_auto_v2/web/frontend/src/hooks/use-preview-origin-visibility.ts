import { type MutableRefObject, useCallback, useRef } from 'react'

interface UsePreviewOriginVisibilityResult {
  hiddenOriginRef: MutableRefObject<HTMLElement | null>
  hideOrigin: (originEl: HTMLElement | null | undefined) => void
  restoreOrigin: (originEl?: HTMLElement | null) => void
}

const PREVIEW_ORIGIN_HIDDEN_CLASS = 'card-preview-origin-hidden'

export function usePreviewOriginVisibility(): UsePreviewOriginVisibilityResult {
  const hiddenOriginRef = useRef<HTMLElement | null>(null)

  const restoreOrigin = useCallback((originEl?: HTMLElement | null): void => {
    const target = originEl ?? hiddenOriginRef.current
    if (!target) {
      return
    }
    target.classList.remove(PREVIEW_ORIGIN_HIDDEN_CLASS)
    if (hiddenOriginRef.current === target) {
      hiddenOriginRef.current = null
    }
  }, [])

  const hideOrigin = useCallback((originEl: HTMLElement | null | undefined): void => {
    restoreOrigin()
    if (!originEl) {
      return
    }
    originEl.classList.add(PREVIEW_ORIGIN_HIDDEN_CLASS)
    hiddenOriginRef.current = originEl
  }, [restoreOrigin])

  return {
    hiddenOriginRef,
    hideOrigin,
    restoreOrigin
  }
}
