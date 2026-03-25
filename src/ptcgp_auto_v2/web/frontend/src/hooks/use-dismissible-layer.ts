import { type RefObject, useEffect } from 'react'

interface UseDismissibleLayerOptions {
  open: boolean
  rootRef: RefObject<HTMLElement | null>
  onDismiss: () => void
}

/**
 * 通用浮层关闭行为：点击外部或按 ESC 关闭。
 */
export function useDismissibleLayer({ open, rootRef, onDismiss }: UseDismissibleLayerOptions): void {
  useEffect(() => {
    if (!open) {
      return
    }

    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null
      if (target && rootRef.current && !rootRef.current.contains(target)) {
        onDismiss()
      }
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onDismiss()
      }
    }

    window.addEventListener('pointerdown', onPointerDown)
    window.addEventListener('keydown', onKeyDown)
    return () => {
      window.removeEventListener('pointerdown', onPointerDown)
      window.removeEventListener('keydown', onKeyDown)
    }
  }, [onDismiss, open, rootRef])
}
