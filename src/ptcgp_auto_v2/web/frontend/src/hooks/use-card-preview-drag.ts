import { type MutableRefObject, type PointerEvent as ReactPointerEvent, useCallback, useEffect, useRef, useState } from 'react'

// 拖拽旋转角度上限，避免卡牌过度倾斜
const PREVIEW_ROTATE_LIMIT = 24
// 悬停状态下的轻微倾斜幅度
const PREVIEW_HOVER_ROTATE_LIMIT = 14
// 鼠标位移到旋转角度的转换系数
const PREVIEW_ROTATE_STEP = 0.45
// requestAnimationFrame 插值比例：每帧逼近目标 15%
const PREVIEW_LERP_FACTOR = 0.15
// Idle 漂浮延迟
const PREVIEW_IDLE_DELAY_MS = 1200
// 插值收敛阈值：低于该阈值时停帧
const PREVIEW_SETTLE_ROTATE_EPSILON = 0.02
const PREVIEW_SETTLE_POINTER_EPSILON = 0.0008

interface PreviewPointerMetrics {
  ratioX: number
  ratioY: number
  fromCenterX: number
  fromCenterY: number
}

interface PreviewVisualState {
  rotateX: number
  rotateY: number
  pointer: PreviewPointerMetrics
}

interface PreviewDragState {
  dragging: boolean
  pointerId: number
  lastX: number
  lastY: number
  targetRotateX: number
  targetRotateY: number
  targetPointer: PreviewPointerMetrics
}

interface UseCardPreviewDragResult {
  cardRef: MutableRefObject<HTMLDivElement | null>
  shineRef: MutableRefObject<HTMLDivElement | null>
  dragging: boolean
  startDrag: (event: ReactPointerEvent<HTMLDivElement>) => void
  onPointerMove: (event: ReactPointerEvent<HTMLDivElement>) => void
  onPointerLeave: () => void
  stopDrag: (withRebound?: boolean) => void
  resetTransform: (animated?: boolean) => void
}

const DEFAULT_POINTER_METRICS: PreviewPointerMetrics = {
  ratioX: 0.5,
  ratioY: 0.5,
  fromCenterX: 0,
  fromCenterY: 0
}

function clamp(value: number, min: number, max: number): number {
  if (value < min) {
    return min
  }
  if (value > max) {
    return max
  }
  return value
}

function resolvePointerMetrics(
  cardEl: HTMLDivElement | null,
  clientX: number,
  clientY: number
): PreviewPointerMetrics {
  if (!cardEl) {
    return DEFAULT_POINTER_METRICS
  }

  const rect = cardEl.getBoundingClientRect()
  if (rect.width <= 0 || rect.height <= 0) {
    return DEFAULT_POINTER_METRICS
  }

  const ratioX = clamp((clientX - rect.left) / rect.width, 0, 1)
  const ratioY = clamp((clientY - rect.top) / rect.height, 0, 1)

  return {
    ratioX,
    ratioY,
    fromCenterX: ratioX * 2 - 1,
    fromCenterY: ratioY * 2 - 1
  }
}

function clonePointer(pointer: PreviewPointerMetrics): PreviewPointerMetrics {
  return {
    ratioX: pointer.ratioX,
    ratioY: pointer.ratioY,
    fromCenterX: pointer.fromCenterX,
    fromCenterY: pointer.fromCenterY
  }
}

export function useCardPreviewDrag(): UseCardPreviewDragResult {
  const [dragging, setDragging] = useState(false)
  const cardRef = useRef<HTMLDivElement | null>(null)
  const shineRef = useRef<HTMLDivElement | null>(null)
  const windowListenersAttachedRef = useRef(false)
  const prefersReducedMotionRef = useRef(false)
  const idleTimerRef = useRef<number | null>(null)
  const idleActiveRef = useRef(false)
  const animationFrameRef = useRef<number | null>(null)
  const stopDragRef = useRef<(withRebound?: boolean) => void>(() => {})

  const dragStateRef = useRef<PreviewDragState>({
    dragging: false,
    pointerId: -1,
    lastX: 0,
    lastY: 0,
    targetRotateX: 0,
    targetRotateY: 0,
    targetPointer: clonePointer(DEFAULT_POINTER_METRICS)
  })

  const renderStateRef = useRef<PreviewVisualState>({
    rotateX: 0,
    rotateY: 0,
    pointer: clonePointer(DEFAULT_POINTER_METRICS)
  })

  const applyVisualState = useCallback((state: PreviewVisualState): void => {
    const cardEl = cardRef.current
    const shineEl = shineRef.current

    const pointerDistance = Math.min(1, Math.hypot(state.pointer.fromCenterX, state.pointer.fromCenterY))
    const rotateDistance = Math.min(1, (Math.abs(state.rotateX) + Math.abs(state.rotateY)) / (PREVIEW_ROTATE_LIMIT * 2))
    const tiltStrength = clamp(pointerDistance * 0.45 + rotateDistance * 0.85, 0, 1)
    const holoAngle = ((Math.atan2(state.pointer.fromCenterY, state.pointer.fromCenterX) * 180) / Math.PI + 450) % 360

    const pointerX = `${(state.pointer.ratioX * 100).toFixed(3)}%`
    const pointerY = `${(state.pointer.ratioY * 100).toFixed(3)}%`

    if (cardEl) {
      cardEl.style.setProperty('--preview-pointer-x', pointerX)
      cardEl.style.setProperty('--preview-pointer-y', pointerY)
      cardEl.style.setProperty('--preview-glare-x', pointerX)
      cardEl.style.setProperty('--preview-glare-y', pointerY)
      cardEl.style.setProperty('--preview-pointer-from-center-x', state.pointer.fromCenterX.toFixed(4))
      cardEl.style.setProperty('--preview-pointer-from-center-y', state.pointer.fromCenterY.toFixed(4))
      cardEl.style.setProperty('--preview-pointer-from-center', pointerDistance.toFixed(4))
      cardEl.style.setProperty('--preview-rotate-x', `${state.rotateX.toFixed(3)}deg`)
      cardEl.style.setProperty('--preview-rotate-y', `${state.rotateY.toFixed(3)}deg`)
      cardEl.style.setProperty('--preview-tilt-strength', tiltStrength.toFixed(4))
      cardEl.style.setProperty('--preview-holo-angle', `${holoAngle.toFixed(2)}deg`)
    }

    if (shineEl) {
      shineEl.style.setProperty('--preview-glare-x', pointerX)
      shineEl.style.setProperty('--preview-glare-y', pointerY)
      shineEl.style.setProperty('--preview-pointer-from-center', pointerDistance.toFixed(4))
    }
  }, [])

  const syncRenderToTarget = useCallback((): void => {
    const dragState = dragStateRef.current
    const renderState = renderStateRef.current

    renderState.rotateX = dragState.targetRotateX
    renderState.rotateY = dragState.targetRotateY
    renderState.pointer = clonePointer(dragState.targetPointer)
  }, [])

  const setTargetNeutral = useCallback((): void => {
    const dragState = dragStateRef.current
    dragState.targetRotateX = 0
    dragState.targetRotateY = 0
    dragState.targetPointer = clonePointer(DEFAULT_POINTER_METRICS)
  }, [])

  const clearIdleTimer = useCallback((): void => {
    if (idleTimerRef.current === null) {
      return
    }
    window.clearTimeout(idleTimerRef.current)
    idleTimerRef.current = null
  }, [])

  const stopIdleFloat = useCallback((): void => {
    idleActiveRef.current = false
    const cardEl = cardRef.current
    if (!cardEl) {
      return
    }
    cardEl.classList.remove('preview-idle-float')
    cardEl.removeAttribute('data-preview-idle-variant')
  }, [])

  const startIdleFloat = useCallback((): void => {
    if (prefersReducedMotionRef.current) {
      return
    }
    const dragState = dragStateRef.current
    if (dragState.dragging) {
      return
    }
    const cardEl = cardRef.current
    if (!cardEl) {
      return
    }
    idleActiveRef.current = true
    const idleVariant = String(Math.floor(Math.random() * 3) + 1)
    cardEl.setAttribute('data-preview-idle-variant', idleVariant)
    cardEl.classList.add('preview-idle-float')
  }, [])

  const scheduleIdleFloat = useCallback((): void => {
    clearIdleTimer()
    if (prefersReducedMotionRef.current) {
      return
    }
    idleTimerRef.current = window.setTimeout(() => {
      idleTimerRef.current = null
      startIdleFloat()
    }, PREVIEW_IDLE_DELAY_MS)
  }, [clearIdleTimer, startIdleFloat])

  const markInteraction = useCallback((): void => {
    stopIdleFloat()
    scheduleIdleFloat()
  }, [scheduleIdleFloat, stopIdleFloat])

  const stepAnimation = useCallback((): void => {
    const dragState = dragStateRef.current
    const renderState = renderStateRef.current

    renderState.rotateX += (dragState.targetRotateX - renderState.rotateX) * PREVIEW_LERP_FACTOR
    renderState.rotateY += (dragState.targetRotateY - renderState.rotateY) * PREVIEW_LERP_FACTOR
    renderState.pointer.ratioX += (dragState.targetPointer.ratioX - renderState.pointer.ratioX) * PREVIEW_LERP_FACTOR
    renderState.pointer.ratioY += (dragState.targetPointer.ratioY - renderState.pointer.ratioY) * PREVIEW_LERP_FACTOR
    renderState.pointer.fromCenterX += (dragState.targetPointer.fromCenterX - renderState.pointer.fromCenterX) * PREVIEW_LERP_FACTOR
    renderState.pointer.fromCenterY += (dragState.targetPointer.fromCenterY - renderState.pointer.fromCenterY) * PREVIEW_LERP_FACTOR

    if (cardRef.current || shineRef.current) {
      applyVisualState(renderState)
    }

    const rotateSettled = Math.abs(dragState.targetRotateX - renderState.rotateX) <= PREVIEW_SETTLE_ROTATE_EPSILON
      && Math.abs(dragState.targetRotateY - renderState.rotateY) <= PREVIEW_SETTLE_ROTATE_EPSILON
    const pointerSettled = Math.abs(dragState.targetPointer.ratioX - renderState.pointer.ratioX) <= PREVIEW_SETTLE_POINTER_EPSILON
      && Math.abs(dragState.targetPointer.ratioY - renderState.pointer.ratioY) <= PREVIEW_SETTLE_POINTER_EPSILON
      && Math.abs(dragState.targetPointer.fromCenterX - renderState.pointer.fromCenterX) <= PREVIEW_SETTLE_POINTER_EPSILON
      && Math.abs(dragState.targetPointer.fromCenterY - renderState.pointer.fromCenterY) <= PREVIEW_SETTLE_POINTER_EPSILON

    if (dragState.dragging || !rotateSettled || !pointerSettled) {
      animationFrameRef.current = window.requestAnimationFrame(stepAnimation)
      return
    }

    animationFrameRef.current = null
  }, [applyVisualState])

  const ensureAnimationFrame = useCallback((): void => {
    if (typeof window === 'undefined') {
      return
    }
    if (animationFrameRef.current !== null) {
      return
    }
    animationFrameRef.current = window.requestAnimationFrame(stepAnimation)
  }, [stepAnimation])

  const resetTransform = useCallback((animated = false): void => {
    setTargetNeutral()
    markInteraction()

    if (!animated) {
      syncRenderToTarget()
      applyVisualState(renderStateRef.current)
      if (animationFrameRef.current !== null) {
        window.cancelAnimationFrame(animationFrameRef.current)
        animationFrameRef.current = null
      }
      return
    }
    ensureAnimationFrame()
  }, [applyVisualState, ensureAnimationFrame, markInteraction, setTargetNeutral, syncRenderToTarget])

  const applyHoverState = useCallback((clientX: number, clientY: number): void => {
    const dragState = dragStateRef.current
    if (dragState.dragging) {
      return
    }

    const pointer = resolvePointerMetrics(cardRef.current, clientX, clientY)
    dragState.targetPointer = pointer
    dragState.targetRotateX = clamp(-pointer.fromCenterY * PREVIEW_HOVER_ROTATE_LIMIT, -PREVIEW_HOVER_ROTATE_LIMIT, PREVIEW_HOVER_ROTATE_LIMIT)
    dragState.targetRotateY = clamp(pointer.fromCenterX * PREVIEW_HOVER_ROTATE_LIMIT, -PREVIEW_HOVER_ROTATE_LIMIT, PREVIEW_HOVER_ROTATE_LIMIT)
    markInteraction()
    ensureAnimationFrame()
  }, [ensureAnimationFrame, markInteraction])

  const onWindowPointerMove = useCallback((event: PointerEvent): void => {
    const dragState = dragStateRef.current
    if (!dragState.dragging) {
      return
    }
    if (dragState.pointerId !== -1 && event.pointerId !== dragState.pointerId) {
      return
    }

    if (event.cancelable) {
      event.preventDefault()
    }

    const deltaX = event.clientX - dragState.lastX
    const deltaY = event.clientY - dragState.lastY

    dragState.lastX = event.clientX
    dragState.lastY = event.clientY
    dragState.targetRotateX = clamp(dragState.targetRotateX - deltaY * PREVIEW_ROTATE_STEP, -PREVIEW_ROTATE_LIMIT, PREVIEW_ROTATE_LIMIT)
    dragState.targetRotateY = clamp(dragState.targetRotateY + deltaX * PREVIEW_ROTATE_STEP, -PREVIEW_ROTATE_LIMIT, PREVIEW_ROTATE_LIMIT)
    dragState.targetPointer = resolvePointerMetrics(cardRef.current, event.clientX, event.clientY)

    markInteraction()
    ensureAnimationFrame()
  }, [ensureAnimationFrame, markInteraction])

  const onWindowPointerEnd = useCallback((event: PointerEvent): void => {
    const dragState = dragStateRef.current
    if (dragState.pointerId !== -1 && event.pointerId !== dragState.pointerId) {
      return
    }
    stopDragRef.current()
  }, [])

  const onWindowBlur = useCallback((): void => {
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
    window.addEventListener('blur', onWindowBlur)
  }, [onWindowBlur, onWindowPointerEnd, onWindowPointerMove])

  const detachWindowListeners = useCallback((): void => {
    if (!windowListenersAttachedRef.current) {
      return
    }
    windowListenersAttachedRef.current = false
    window.removeEventListener('pointermove', onWindowPointerMove)
    window.removeEventListener('pointerup', onWindowPointerEnd)
    window.removeEventListener('pointercancel', onWindowPointerEnd)
    window.removeEventListener('blur', onWindowBlur)
  }, [onWindowBlur, onWindowPointerEnd, onWindowPointerMove])

  const stopDrag = useCallback((withRebound = true): void => {
    const dragState = dragStateRef.current
    const wasDragging = dragState.dragging

    dragState.dragging = false
    dragState.pointerId = -1
    setDragging(false)
    detachWindowListeners()

    if (withRebound && wasDragging) {
      resetTransform(true)
      return
    }

    markInteraction()
  }, [detachWindowListeners, markInteraction, resetTransform])

  useEffect(() => {
    stopDragRef.current = stopDrag
  }, [stopDrag])

  const startDrag = useCallback((event: ReactPointerEvent<HTMLDivElement>): void => {
    if (event.pointerType === 'mouse' && event.button !== 0) {
      return
    }

    event.preventDefault()
    stopDrag(false)
    markInteraction()

    try {
      event.currentTarget.setPointerCapture(event.pointerId)
    } catch {
      // 捕获失败时继续，窗口级监听兜底
    }

    const dragState = dragStateRef.current
    dragState.dragging = true
    dragState.pointerId = event.pointerId
    dragState.lastX = event.clientX
    dragState.lastY = event.clientY
    dragState.targetPointer = resolvePointerMetrics(cardRef.current, event.clientX, event.clientY)

    setDragging(true)
    attachWindowListeners()
    ensureAnimationFrame()
  }, [attachWindowListeners, ensureAnimationFrame, markInteraction, stopDrag])

  const onPointerMove = useCallback((event: ReactPointerEvent<HTMLDivElement>): void => {
    applyHoverState(event.clientX, event.clientY)
  }, [applyHoverState])

  const onPointerLeave = useCallback((): void => {
    const dragState = dragStateRef.current
    if (dragState.dragging) {
      return
    }
    setTargetNeutral()
    markInteraction()
    ensureAnimationFrame()
  }, [ensureAnimationFrame, markInteraction, setTargetNeutral])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => {
      prefersReducedMotionRef.current = media.matches
      if (media.matches) {
        clearIdleTimer()
        stopIdleFloat()
        return
      }
      scheduleIdleFloat()
    }

    update()
    media.addEventListener('change', update)
    return () => {
      media.removeEventListener('change', update)
    }
  }, [clearIdleTimer, scheduleIdleFloat, stopIdleFloat])

  useEffect(() => {
    markInteraction()
    return () => {
      stopDrag(false)
      clearIdleTimer()
      stopIdleFloat()
      if (animationFrameRef.current !== null) {
        window.cancelAnimationFrame(animationFrameRef.current)
        animationFrameRef.current = null
      }
    }
  }, [clearIdleTimer, markInteraction, stopDrag, stopIdleFloat])

  return {
    cardRef,
    shineRef,
    dragging,
    startDrag,
    onPointerMove,
    onPointerLeave,
    stopDrag,
    resetTransform
  }
}
