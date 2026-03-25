import { type MutableRefObject, type PointerEvent as ReactPointerEvent, useCallback, useEffect, useRef, useState } from 'react'

// 预览卡牌回弹过渡：与页面原行为保持一致
const PREVIEW_REBOUND_TRANSITION = 'transform 360ms cubic-bezier(0.22, 1, 0.36, 1)'
// 拖拽旋转角度上限，避免卡牌过度倾斜
const PREVIEW_ROTATE_LIMIT = 45
// 鼠标位移到旋转角度的转换系数
const PREVIEW_ROTATE_STEP = 0.5

interface PreviewDragState {
  dragging: boolean
  pointerId: number
  lastX: number
  lastY: number
  rotateX: number
  rotateY: number
}

interface UseCardPreviewDragResult {
  cardRef: MutableRefObject<HTMLDivElement | null>
  shineRef: MutableRefObject<HTMLDivElement | null>
  dragging: boolean
  startDrag: (event: ReactPointerEvent<HTMLDivElement>) => void
  stopDrag: (withRebound?: boolean) => void
  resetTransform: (animated?: boolean) => void
}

export function useCardPreviewDrag(): UseCardPreviewDragResult {
  const [dragging, setDragging] = useState(false)
  const cardRef = useRef<HTMLDivElement | null>(null)
  const shineRef = useRef<HTMLDivElement | null>(null)
  const windowListenersAttachedRef = useRef(false)
  const stopDragRef = useRef<(withRebound?: boolean) => void>(() => {})
  const dragStateRef = useRef<PreviewDragState>({
    dragging: false,
    pointerId: -1,
    lastX: 0,
    lastY: 0,
    rotateX: 0,
    rotateY: 0
  })

  const applyTransform = useCallback((x: number, y: number): void => {
    const cardEl = cardRef.current
    if (cardEl) {
      cardEl.style.transform = `rotateY(${y}deg) rotateX(${x}deg)`
    }
    const shineEl = shineRef.current
    if (shineEl) {
      shineEl.style.transform = `translateX(${-y * 1.4}px) translateY(${x * 1.4}px)`
    }
  }, [])

  const setTransition = useCallback((animated: boolean): void => {
    const transitionValue = animated ? PREVIEW_REBOUND_TRANSITION : 'none'
    const cardEl = cardRef.current
    if (cardEl) {
      cardEl.style.transition = transitionValue
    }
    const shineEl = shineRef.current
    if (shineEl) {
      shineEl.style.transition = transitionValue
    }
  }, [])

  const resetTransform = useCallback((animated = false): void => {
    const state = dragStateRef.current
    state.rotateX = 0
    state.rotateY = 0
    setTransition(animated)
    applyTransform(0, 0)
  }, [applyTransform, setTransition])

  const onWindowPointerMove = useCallback(
    (event: PointerEvent): void => {
      const state = dragStateRef.current
      if (!state.dragging) {
        return
      }
      if (state.pointerId !== -1 && event.pointerId !== state.pointerId) {
        return
      }
      if (event.cancelable) {
        event.preventDefault()
      }
      const deltaX = event.clientX - state.lastX
      const deltaY = event.clientY - state.lastY
      state.lastX = event.clientX
      state.lastY = event.clientY
      state.rotateX = Math.max(-PREVIEW_ROTATE_LIMIT, Math.min(PREVIEW_ROTATE_LIMIT, state.rotateX - deltaY * PREVIEW_ROTATE_STEP))
      state.rotateY = Math.max(-PREVIEW_ROTATE_LIMIT, Math.min(PREVIEW_ROTATE_LIMIT, state.rotateY + deltaX * PREVIEW_ROTATE_STEP))
      applyTransform(state.rotateX, state.rotateY)
    },
    [applyTransform]
  )

  const onWindowPointerEnd = useCallback((): void => {
    stopDragRef.current()
  }, [])

  const attachWindowListeners = useCallback((): void => {
    if (windowListenersAttachedRef.current) {
      return
    }
    windowListenersAttachedRef.current = true
    window.addEventListener('pointermove', onWindowPointerMove, { passive: false })
    window.addEventListener('pointerup', onWindowPointerEnd)
    window.addEventListener('pointercancel', onWindowPointerEnd)
    window.addEventListener('blur', onWindowPointerEnd)
  }, [onWindowPointerEnd, onWindowPointerMove])

  const detachWindowListeners = useCallback((): void => {
    if (!windowListenersAttachedRef.current) {
      return
    }
    windowListenersAttachedRef.current = false
    window.removeEventListener('pointermove', onWindowPointerMove)
    window.removeEventListener('pointerup', onWindowPointerEnd)
    window.removeEventListener('pointercancel', onWindowPointerEnd)
    window.removeEventListener('blur', onWindowPointerEnd)
  }, [onWindowPointerEnd, onWindowPointerMove])

  const stopDrag = useCallback(
    (withRebound = true): void => {
      const state = dragStateRef.current
      const wasDragging = state.dragging
      state.dragging = false
      state.pointerId = -1
      setDragging(false)
      detachWindowListeners()
      if (withRebound && wasDragging) {
        resetTransform(true)
      }
    },
    [detachWindowListeners, resetTransform]
  )

  useEffect(() => {
    stopDragRef.current = stopDrag
  }, [stopDrag])

  const startDrag = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>): void => {
      if (event.button !== 0) {
        return
      }
      event.preventDefault()
      stopDrag(false)
      setTransition(false)
      const state = dragStateRef.current
      state.dragging = true
      state.pointerId = event.pointerId
      state.lastX = event.clientX
      state.lastY = event.clientY
      setDragging(true)
      attachWindowListeners()
    },
    [attachWindowListeners, setTransition, stopDrag]
  )

  useEffect(
    () => () => {
      stopDrag(false)
    },
    [stopDrag]
  )

  return {
    cardRef,
    shineRef,
    dragging,
    startDrag,
    stopDrag,
    resetTransform
  }
}
